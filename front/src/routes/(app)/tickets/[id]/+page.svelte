<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { page } from '$app/stores';
	import { currentUser, isCS, isAdmin } from '$lib/stores/auth';
	import { tickets as ticketsApi, ApiError, type TicketEvolution, type TicketMessage } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import RichEditor from '$lib/components/RichEditor.svelte';
	import EvolForm from '$lib/components/EvolForm.svelte';
	import PiecesJointes from '$lib/components/PiecesJointes.svelte';
	import FichiersUpload from '$lib/components/FichiersUpload.svelte';
	import { ACCEPT_PHOTOS, fichiersDepuisUrls } from '$lib/fichiers';
	import { siteNomStore } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';
	import { fmtDatetime, fmtDateLong, fmtDateShort } from '$lib/date';
	import { perimetreLabel } from '$lib/utils';

	$: _siteNom = $siteNomStore;

	let ticket: any = null;
	let messages: TicketMessage[] = [];
	let evolutions: TicketEvolution[] = [];
	let loading = true;
	let newContent = '';
	let newInterne = false;
	let sending = false;
	let updatingStatus = false;
	let msgPhotos: string[] = [];
	let msgDocs: string[] = [];
	let msgEmailExterne = '';

	// Évolutions
	let showEvolForm = false;
	let evolSaving = false;
	let expandedEvols = false;
	let editingEvolId: number | null = null;
	let editEvolSaving = false;

	async function addEvolFromForm(e: CustomEvent) {
		const data = e.detail;
		evolSaving = true;
		try {
			await ticketsApi.addEvolution(ticketId, {
				type: data.type,
				contenu: data.contenu || undefined,
				nouveau_statut: data.nouveau_statut,
				fichiers_urls: data.fichiers_urls,
				email_externe: data.email_externe,
				partager_whatsapp: data.partager_whatsapp || undefined,
				envoyer_syndic: data.envoyer_syndic || undefined,
				envoyer_cs: data.envoyer_cs || undefined,
			});
			await loadEvolutions();
			if (data.type === 'etat') {
				ticket = await ticketsApi.get(ticketId);
			}
			showEvolForm = false;
			toast('success', data.type === 'etat' ? 'Statut mis à jour' : 'Commentaire ajouté');
		} catch (err: any) {
			toast('error', err instanceof ApiError ? err.message : 'Erreur');
		} finally { evolSaving = false; }
	}

	async function saveEvolEdit(e: CustomEvent) {
		if (editingEvolId === null) return;
		editEvolSaving = true;
		try {
			await ticketsApi.updateEvolution(ticketId, editingEvolId, {
				contenu: e.detail.contenu || undefined,
				fichiers_urls: e.detail.fichiers_urls,
			});
			await loadEvolutions();
			editingEvolId = null;
			toast('success', 'Commentaire mis à jour');
		} catch { toast('error', 'Erreur de mise à jour'); }
		finally { editEvolSaving = false; }
	}

	$: ticketId = Number($page.params.id);

	const STATUTS = [
		{ value: 'ouvert',   label: 'Ouvert',   cls: 'badge-blue' },
		{ value: 'en_cours', label: 'En cours', cls: 'badge-orange' },
		{ value: 'résolu',   label: 'Résolu',   cls: 'badge-green' },
		{ value: 'annulé',   label: 'Annulé',   cls: 'badge-gray' },
	];

	const STATUT_LABELS: Record<string, string> = {
		ouvert: 'Ouvert', en_cours: 'En cours', 'résolu': 'Résolu', 'annulé': 'Annulé',
	};

	const TICKET_STATUT_OPTIONS = [
		{ value: 'ouvert',   label: '🔵 Ouvert' },
		{ value: 'en_cours', label: '🟡 En cours' },
		{ value: 'résolu',   label: '🟢 Résolu' },
		{ value: 'fermé',    label: '⚫ Fermé' },
	];

	const CATEGORIES: Record<string, string> = {
		panne:    '\u{1F6E0}️ Panne',
		nuisance: '\u{1F4E2} Nuisance',
		question: '❓ Question',
		urgence:  '\u{1F6A8} Urgence',
		bug:      '\u{1F41B} Bug',
	};

	const PRIORITE: Record<string, { label: string; cls: string }> = {
		basse:   { label: 'Priorité basse',   cls: 'badge-gray' },
		normale: { label: 'Priorité normale', cls: 'badge-default' },
		haute:   { label: 'Priorité haute',   cls: 'badge-orange' },
	};

	function renderContent(c: string): string {
		const t = c.trimStart();
		const raw = t.startsWith('<') ? c : `<p>${c.replace(/\n/g, '<br>')}</p>`;
		return safeHtml(raw);
	}

	$: statusInfo = STATUTS.find((s) => s.value === ticket?.statut) ?? STATUTS[0];
	$: canReply = ticket && !['fermé'].includes(ticket.statut);

	// ── Lire d'abord, écrire ensuite ───────────────────────────────────────
	// Cette page est atteinte surtout par un lien de notification (WhatsApp,
	// e-mail) : on y vient pour LIRE. Or l'éditeur, les photos, les documents et
	// le champ e-mail formaient un écran entier de contrôles avant même l'échange
	// — sur mobile, toute la page. Pire, un ticket déjà résolu proposait un
	// éditeur complet, suggérant une action que personne n'avait demandée.
	// Le bloc de réponse est donc replié derrière un bouton, et ne s'ouvre
	// d'emblée que sur une intention explicite (`?repondre=1`), que les liens de
	// notification ne portent pas.
	let repondreOuvert = false;
	let msgVise: number | null = null;
	$: clos = ticket && ['résolu', 'annulé', 'fermé'].includes(ticket.statut);

	async function loadEvolutions() {
		try { evolutions = await ticketsApi.evolutions(ticketId); } catch { /* silencieux */ }
	}

	onMount(async () => {
		// Intention explicite : un lien « répondre » ouvre l'éditeur d'emblée.
		// Les liens de notification, eux, mènent à la lecture.
		repondreOuvert = new URLSearchParams(window.location.search).get('repondre') === '1';
		// Ancre `#msg-42` : les notifications de réponse pointent sur le message qui
		// a déclenché l'alerte. Sans ce défilement, le lecteur atterrissait en haut
		// d'un fil parfois long, à lui de retrouver la nouveauté.
		const ancre = window.location.hash.match(/^#msg-(\d+)$/);
		if (ancre) msgVise = Number(ancre[1]);
		try {
			[ticket, messages] = await Promise.all([
				ticketsApi.get(ticketId),
				ticketsApi.messages(ticketId),
			]);
			await loadEvolutions();
			if (msgVise !== null) {
				await tick();
				document.getElementById(`msg-${msgVise}`)?.scrollIntoView({ block: 'center' });
			}
		} catch {
			toast('error', 'Ticket introuvable');
		} finally {
			loading = false;
		}
	});

	async function sendMessage() {
		if (!newContent.trim()) return;
		sending = true;
		try {
			const msg = await ticketsApi.addMessage(ticketId, {
				contenu: newContent,
				interne: newInterne,
				fichiers_urls: [...msgPhotos, ...msgDocs],
				email_externe: msgEmailExterne.trim() || undefined,
			});
			messages = [...messages, msg];
			newContent = '';
			newInterne = false;
			msgPhotos = []; msgDocs = [];
			msgEmailExterne = '';
			await loadEvolutions();
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			sending = false;
		}
	}

	// Le téléversement du formulaire de réponse est celui de `FichiersUpload` :
	// c'était la quatrième copie de la même fonction dans le projet.

	async function updateStatus(s: string) {
		updatingStatus = true;
		try {
			ticket = await ticketsApi.update(ticketId, { statut: s });
			await loadEvolutions();
			toast('success', 'Statut mis à jour');
		} catch {
			toast('error', 'Erreur de mise à jour');
		} finally {
			updatingStatus = false;
		}
	}



	async function deleteTicket() {
		if (!confirm(`Supprimer définitivement le ticket #${ticket.numero} ? Cette action est irréversible.`)) return;
		try {
			await ticketsApi.delete(ticketId);
			toast('success', 'Ticket supprimé');
			window.location.href = '/tickets';
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}
</script>

<svelte:head><title>Ticket #{ticketId} — {_siteNom}</title></svelte:head>

<a href="/tickets" class="back-link">← Retour aux tickets</a>

{#if loading}
	<p style="color:var(--color-text-muted)">Chargement…</p>
{:else if !ticket}
	<div class="empty-state"><h3>Ticket introuvable</h3></div>
{:else}
	<div class="ticket-header card" style="max-width:720px;margin-bottom:1rem">
		<div class="ticket-meta">
			<span class="badge {statusInfo.cls}">{statusInfo.label}</span>
			<span class="badge badge-default">{CATEGORIES[ticket.categorie] ?? ticket.categorie}</span>
			{#if ticket.priorite && ticket.priorite !== 'normale'}
				<span class="badge {PRIORITE[ticket.priorite]?.cls ?? 'badge-default'}">{PRIORITE[ticket.priorite]?.label}</span>
			{/if}
		</div>
		<h1 style="font-size:1.1rem;font-weight:700;margin:.6rem 0 .3rem">{ticket.titre}</h1>
		<p style="font-size:.875rem;color:var(--color-text-muted)">
			{fmtDateLong(ticket.cree_le)}
			{#if ticket.mis_a_jour_le && ticket.mis_a_jour_le !== ticket.cree_le}
				&middot; mis à jour le {fmtDateShort(ticket.mis_a_jour_le)}
			{/if}
		</p>
		{#if ticket.perimetre_cible?.length}
			<p style="font-size:.8rem;color:var(--color-text-muted);margin-top:.2rem">
				&#x1F539; {perimetreLabel(ticket.perimetre_cible)}
			</p>
		{/if}
		{#if ticket.description}
			<div class="rich-content ticket-desc">{@html renderContent(ticket.description)}</div>
		{/if}

		{#if ticket.photos_urls?.length || ticket.fichiers_urls?.length}
			<div style="margin-top:.75rem">
				<!-- La fiche EST le contenu déplié : c'est ici qu'on regarde la
				     photo du dégât, pas qu'on la survole. Les fils de messages et
				     d'évolutions gardent leurs vignettes — y empiler des grandes
				     photos rendrait la discussion interminable à parcourir. -->
				<PiecesJointes urls={[...(ticket.photos_urls ?? []), ...(ticket.fichiers_urls ?? [])]} format="grand" />
			</div>
		{/if}

		{#if ticket.destinataire_syndic}
			<p style="font-size:.8rem;color:var(--color-text-muted);margin-top:.5rem">
				📧 Envoyé au syndic
			</p>
		{/if}

		{#if ticket.saisi_pour_affichage && $isCS}
			<p style="font-size:.85rem;color:var(--color-text-muted);margin-top:.5rem;padding:.5rem .75rem;background:var(--color-bg-muted,#f5f5f5);border-radius:var(--radius)">
				👤 Saisi par <strong>{ticket.auteur_nom ?? 'inconnu'}</strong> pour <strong>{ticket.saisi_pour_affichage}</strong>
				{#if ticket.saisi_pour_email}
					· <a href="mailto:{ticket.saisi_pour_email}">{ticket.saisi_pour_email}</a>
				{/if}
			</p>
		{/if}

		{#if $isCS}
			<div class="status-actions" style="margin-top:.75rem;padding-top:.75rem;border-top:1px solid var(--color-border)">
				<span style="font-size:.8rem;font-weight:500;color:var(--color-text-muted)">Changer le statut :</span>
				<div style="display:flex;gap:.4rem;flex-wrap:wrap;margin-top:.3rem">
					{#each STATUTS as s}
						<button
							class="btn btn-sm {ticket.statut === s.value ? 'btn-primary' : 'btn-secondary'}"
							disabled={updatingStatus || ticket.statut === s.value}
							on:click={() => updateStatus(s.value)}
						>{s.label}</button>
					{/each}
				</div>
			</div>
		{/if}
	</div>

	<!-- Thread messages -->
	<div class="messages" style="max-width:720px">
		{#each messages as msg}
			{@const isOwn = msg.auteur?.id === $currentUser?.id}
			{#if !msg.interne || $isCS}
				<div id="msg-{msg.id}" class="message-bubble" class:own={isOwn} class:interne={msg.interne}
					class:message-vise={msgVise === msg.id}>
					<div class="msg-header">
						<strong>{msg.auteur?.prenom} {msg.auteur?.nom}</strong>
						{#if msg.interne}<span class="badge badge-yellow" style="font-size:.65rem">interne</span>{/if}
						<span class="msg-time">{fmtDatetime(msg.cree_le)}</span>
					</div>
					<div class="msg-body">{@html renderContent(msg.contenu)}</div>
					{#if msg.fichiers_urls?.length}
						<div style="margin-top:.4rem">
							<PiecesJointes urls={msg.fichiers_urls} size={80} />
						</div>
					{/if}
				</div>
			{/if}
		{/each}

		{#if canReply && !repondreOuvert}
			<div class="card" style="text-align:center;padding:.9rem">
				<button type="button" class="btn btn-outline" on:click={() => (repondreOuvert = true)}>
					{clos ? '↩️ Rouvrir la discussion' : '💬 Répondre'}
				</button>
			</div>
		{/if}

		{#if canReply && repondreOuvert}
			<form class="reply-form card" on:submit|preventDefault={sendMessage}>
				<RichEditor bind:value={newContent} placeholder="Votre réponse…" minHeight="80px" />
				{#if $isCS}
					<label class="checkbox-field" style="margin:.5rem 0">
						<input type="checkbox" bind:checked={newInterne} />
						Message interne (visible par le CS uniquement)
					</label>
					{#if !newInterne}
						<div style="margin:.4rem 0">
							<label for="msg-photos" style="font-size:.8rem;font-weight:500;color:var(--color-text-muted)">&#x1F4F7; Photos</label>
							<FichiersUpload id="msg-photos" bind:urls={msgPhotos} max={5}
								label="Ajouter une photo" accept={ACCEPT_PHOTOS} />
						</div>
						<div style="margin:.4rem 0">
							<label for="msg-docs" style="font-size:.8rem;font-weight:500;color:var(--color-text-muted)">&#x1F4CE; Documents (PDF, Word, Excel)</label>
							<FichiersUpload id="msg-docs" bind:urls={msgDocs} max={5}
								label="Ajouter un document" />
						</div>
					{/if}
					<!-- Email externe -->
					{#if !newInterne}
						<div style="margin:.4rem 0">
							<label for="msg-email-ext" style="font-size:.8rem;font-weight:500;color:var(--color-text-muted)">📧 Notifier une adresse email externe (optionnel)</label>
							<input id="msg-email-ext" type="email" bind:value={msgEmailExterne}
								placeholder="contact@exemple.fr"
								style="padding:.35rem .6rem;border:1px solid var(--color-border);border-radius:6px;font-size:.85rem;width:100%;max-width:320px;margin-top:.25rem;display:block" />
						</div>
					{/if}
				{/if}
				<div class="form-actions">
					<button type="submit" class="btn btn-primary" disabled={sending}>
						{sending ? 'Envoi…' : 'Envoyer'}
					</button>
				</div>
			</form>
		{:else}
			<p style="font-size:.875rem;color:var(--color-text-muted);text-align:center;padding:1rem">
				Ce ticket est fermé.
			</p>
		{/if}
	</div>

	<!-- Fil de suivi (évolutions) -->
	<div style="max-width:720px;margin-top:1.5rem">
		<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.5rem">
			<h2 style="font-size:1rem;font-weight:600;margin:0">&#x1F4CB; Fil de suivi</h2>
			{#if $isCS}
				<button class="btn btn-outline btn-sm" on:click={() => { showEvolForm = !showEvolForm; }}>
					{showEvolForm ? '✕ Annuler' : '\u{1F4AC} Commenter / état'}
				</button>
			{/if}
		</div>

		{#if showEvolForm}
			<div class="evol-form card" style="margin-bottom:.75rem">
				<h4 style="font-size:.875rem;font-weight:600;margin:0 0 .6rem">Ajouter une évolution</h4>
				{#key showEvolForm}
				<EvolForm
					statutOptions={TICKET_STATUT_OPTIONS}
					statutLabels={STATUT_LABELS}
					currentStatut={ticket?.statut ?? ''}
					showNotifs={$isCS}
					showEmail={$isCS}
					showFiles={true}
					separatePhotosAndDocs={true}
					saving={evolSaving}
					on:submit={addEvolFromForm}
					on:cancel={() => (showEvolForm = false)}
				/>
				{/key}
			</div>
		{/if}

		{#if evolutions.length === 0}
			<p style="font-size:.85rem;color:var(--color-text-muted)">Aucune évolution enregistrée.</p>
		{:else}
			{@const evolsSorted = [...evolutions].sort((a, b) => new Date(b.cree_le).getTime() - new Date(a.cree_le).getTime())}
			{@const evolCompact = evolsSorted.length > 7 && !expandedEvols}
			{@const evolsVisible = evolCompact ? evolsSorted.slice(0, 5) : evolsSorted}
			<div class="evol-list">
				{#each evolsVisible as evol, i (evol.id)}
					{#if i > 0}<hr class="evol-sep" />{/if}
					<div class="evol-item evol-{evol.type}">
						<span class="evol-icon">
							{#if evol.type === 'etat'}&#x1F504;{:else if evol.type === 'reponse'}&#x1F4AC;{:else}&#x1F4DD;{/if}
						</span>
						<div class="evol-body">
							<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:.5rem">
								<span class="evol-meta">{fmtDatetime(evol.cree_le)}{#if evol.auteur_nom} · {evol.auteur_nom}{/if}</span>
								{#if evol.type === 'commentaire' && $isCS && editingEvolId !== evol.id}
								<button type="button" title="Modifier" on:click={() => editingEvolId = evol.id}
									style="border:1px solid var(--color-border);background:var(--color-bg-alt);color:var(--color-text);cursor:pointer;padding:.15rem .4rem;font-size:.75rem;flex-shrink:0;border-radius:5px;line-height:1.4" aria-label="Modifier">✏️ Modifier</button>
								{/if}
							</div>
							{#if evol.type === 'etat'}
								<span class="evol-text">
									Statut : <strong>{STATUT_LABELS[evol.ancien_statut ?? ''] || 'Aucun'}</strong> → <strong>{STATUT_LABELS[evol.nouveau_statut ?? ''] || evol.nouveau_statut}</strong>
								</span>
							{:else if evol.type === 'reponse'}
								<span class="evol-text">Nouvelle réponse{#if evol.contenu} ({evol.contenu}){/if}</span>
							{/if}
						{#if evol.type === 'commentaire' || evol.type === 'etat'}
								{#if editingEvolId === evol.id}
								<div style="margin:.4rem 0;border:1px solid var(--color-border);border-radius:8px;padding:.75rem;background:var(--color-bg)">
									{#key editingEvolId}
									<EvolForm
										editMode={true}
										initialContenu={evol.contenu || ''}
										initialFichiers={fichiersDepuisUrls(evol.fichiers_urls)}
										showFiles={true}
										separatePhotosAndDocs={true}
										saving={editEvolSaving}
										on:submit={saveEvolEdit}
										on:cancel={() => editingEvolId = null}
									/>
									{/key}
								</div>
							{:else if evol.contenu}
									<span class="evol-text rich-content" style="font-size:.875rem">{@html safeHtml(evol.contenu)}</span>
								{/if}
							{/if}
							{#if evol.fichiers_urls?.length && editingEvolId !== evol.id}
								<div style="margin-top:.3rem">
									<PiecesJointes urls={evol.fichiers_urls} size={72} compact />
								</div>
							{/if}
						</div>
					</div>
				{/each}
				{#if evolCompact}
					<hr class="evol-sep" />
					<button class="evol-more" on:click={() => { expandedEvols = true; }}>
						Voir les {evolsSorted.length - 5} évolutions plus anciennes
					</button>
				{/if}
			</div>
		{/if}
	</div>

	<!-- Suppression admin -->
	{#if $isAdmin}
		<div style="max-width:720px;margin-top:2rem;padding-top:1rem;border-top:1px solid var(--color-border)">
			<button class="btn btn-outline btn-sm" style="color:var(--color-danger);border-color:var(--color-danger)" on:click={deleteTicket}>
				&#x1F5D1;️ Supprimer définitivement
			</button>
		</div>
	{/if}
{/if}

<style>
	/* Message pointé par l'ancre d'une notification : un cadre suffit à le
	   situer, sans clignotement ni couleur criarde — on vient lire, pas être
	   alerté une seconde fois. */
	.message-vise { outline: 2px solid var(--color-primary); outline-offset: 3px; border-radius: 10px; }
	.back-link { display: inline-flex; align-items: center; gap: .3rem; font-size: .85rem; color: var(--color-text-muted); text-decoration: none; margin-bottom: .75rem; }
	.back-link:hover { color: var(--color-primary); }
	.ticket-meta { display: flex; gap: .4rem; flex-wrap: wrap; margin-bottom: .4rem; }
	.ticket-header { border-left: 4px solid var(--color-primary); }
	.status-actions {}
	.messages { display: flex; flex-direction: column; gap: .75rem; }
	.message-bubble {
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: .75rem 1rem;
		align-self: flex-start;
		max-width: 90%;
	}
	.message-bubble.own {
		background: #eff6ff;
		align-self: flex-end;
		border-color: #bfdbfe;
	}
	.message-bubble.interne {
		background: #fefce8;
		border-color: #fef08a;
		opacity: .9;
	}
	.msg-header {
		display: flex;
		align-items: center;
		gap: .4rem;
		font-size: .78rem;
		margin-bottom: .3rem;
		flex-wrap: wrap;
	}
	.msg-header strong { font-size: .85rem; }
	.msg-time { color: var(--color-text-muted); margin-left: auto; }
	.msg-body { font-size: .875rem; line-height: 1.55; margin: 0; }
	.msg-body :global(p) { margin: 0 0 .4em; }
	.msg-body :global(p:last-child) { margin-bottom: 0; }
	.msg-body :global(ul), .msg-body :global(ol) { padding-left: 1.3em; margin: 0 0 .4em; }
	.msg-body :global(strong) { font-weight: 600; }
	.ticket-desc { font-size: .875rem; margin-top: .75rem; }
	.ticket-desc :global(p) { margin: 0 0 .5em; }
	.ticket-desc :global(p:last-child) { margin-bottom: 0; }
	.ticket-desc :global(ul), .ticket-desc :global(ol) { padding-left: 1.3em; margin: 0 0 .5em; }
	.reply-form { margin-top: .5rem; }
	.checkbox-field { display: flex; align-items: center; gap: .4rem; font-size: .875rem; cursor: pointer; }
	.form-actions { display: flex; justify-content: flex-end; }

	/* Évolutions */
	.evol-list { border: 1px solid var(--color-border); border-radius: 6px; overflow: hidden; }
	.evol-sep { margin: 0; border: none; border-top: 1px solid var(--color-border); }
	.evol-item { display: flex; gap: .5rem; padding: .5rem .75rem; font-size: .82rem; }
	.evol-icon { flex-shrink: 0; font-size: .9rem; margin-top: .1rem; }
	.evol-body { display: flex; flex-direction: column; gap: .15rem; }
	.evol-meta { font-size: .75rem; color: var(--color-text-muted); }
	.evol-text { color: var(--color-text); line-height: 1.5; }
	.evol-etat { background: #f0f9ff; }
	.evol-reponse { background: #f0fdf4; }
	.evol-form { padding: .75rem; }
	.evol-more { width: 100%; background: none; border: none; padding: .45rem; font-size: .8rem; color: var(--color-primary); cursor: pointer; text-align: center; }
	.evol-more:hover { background: var(--color-bg); }
	.pill { padding: .3rem .85rem; border-radius: 999px; border: 1.5px solid var(--color-border); background: var(--color-bg); font-size: .85rem; cursor: pointer; transition: background .15s, border-color .15s, color .15s; white-space: nowrap; line-height: 1.6; }
	.pill:hover { border-color: var(--color-primary); color: var(--color-primary); }
	.pill-active { background: var(--color-primary); border-color: var(--color-primary); color: #fff; }

	.ticket-photo-link { display: block; }
	.ticket-photo {
		width: 100px;
		height: 100px;
		object-fit: cover;
		border-radius: var(--radius);
		border: 1px solid var(--color-border);
		cursor: pointer;
		transition: opacity .15s;
	}
	.ticket-photo:hover { opacity: .8; }
</style>
