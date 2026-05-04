<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { currentUser, isCS, isAdmin } from '$lib/stores/auth';
	import { tickets as ticketsApi, fichiersApi, ApiError, type TicketEvolution } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import RichEditor from '$lib/components/RichEditor.svelte';
	import { siteNomStore } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';
	import { fmtDatetime, fmtDateLong, fmtDateShort } from '$lib/date';

	$: _siteNom = $siteNomStore;

	interface Message {
		id: number;
		contenu: string;
		interne: boolean;
		auteur: { id: number; prenom: string; nom: string; role: string };
		cree_le: string;
		fichiers_urls?: string[];
	}

	let ticket: any = null;
	let messages: Message[] = [];
	let evolutions: TicketEvolution[] = [];
	let loading = true;
	let newContent = '';
	let newInterne = false;
	let sending = false;
	let updatingStatus = false;
	let msgPhotos: { url: string; nom: string; type: string }[] = [];
	let msgDocs: { url: string; nom: string; type: string }[] = [];
	let msgEmailExterne = '';
	let uploadingMsgPhoto = false;
	let uploadingMsgDoc = false;

	// Évolutions
	let showEvolForm = false;
	let evolType: 'commentaire' | 'etat' = 'commentaire';
	let evolContenu = '';
	let evolNouveauStatut = '';
	let evolSaving = false;
	let expandedEvols = false;
	let evolPhotos: { url: string; nom: string; type: string }[] = [];
	let evolDocs: { url: string; nom: string; type: string }[] = [];
	let evolEmailExterne = '';
	let uploadingEvolPhoto = false;
	let uploadingEvolDoc = false;
	let evolPartagerWhatsapp = false;
	let evolEnvoyerSyndic = false;
	let evolEnvoyerCs = false;

	// Édition d'un commentaire existant
	let editingEvolId: number | null = null;
	let editEvolContenu = '';
	let editEvolPhotos: { url: string; nom: string }[] = [];
	let editEvolDocs: { url: string; nom: string }[] = [];
	let editEvolSaving = false;
	let uploadingEditPhoto = false;
	let uploadingEditDoc = false;

	function startEditEvol(evol: any) {
		editingEvolId = evol.id;
		editEvolContenu = evol.contenu || '';
		const photos = (evol.fichiers_urls || []).filter((u: string) => /\.(jpe?g|png|webp)$/i.test(u));
		const docs   = (evol.fichiers_urls || []).filter((u: string) => !/\.(jpe?g|png|webp)$/i.test(u));
		editEvolPhotos = photos.map((u: string) => ({ url: u, nom: u.split('/').pop() || u }));
		editEvolDocs   = docs.map((u: string) => ({ url: u, nom: u.split('/').pop() || u }));
	}

	async function uploadEditPhoto(event: Event) {
		const input = event.target as HTMLInputElement;
		const file = input.files?.[0]; if (!file) return;
		uploadingEditPhoto = true;
		try {
			const r = await fichiersApi.upload(file);
			editEvolPhotos = [...editEvolPhotos, { url: r.url, nom: r.nom || file.name }];
		} catch { toast('error', 'Erreur upload photo'); }
		finally { uploadingEditPhoto = false; input.value = ''; }
	}

	async function uploadEditDoc(event: Event) {
		const input = event.target as HTMLInputElement;
		const file = input.files?.[0]; if (!file) return;
		uploadingEditDoc = true;
		try {
			const r = await fichiersApi.upload(file);
			editEvolDocs = [...editEvolDocs, { url: r.url, nom: r.nom || file.name }];
		} catch { toast('error', 'Erreur upload document'); }
		finally { uploadingEditDoc = false; input.value = ''; }
	}

	async function saveEvolEdit() {
		if (editingEvolId === null) return;
		editEvolSaving = true;
		try {
			await ticketsApi.updateEvolution(ticketId, editingEvolId, {
				contenu: editEvolContenu || undefined,
				fichiers_urls: [...editEvolPhotos.map(f => f.url), ...editEvolDocs.map(f => f.url)],
			});
			await loadEvolutions();
			editingEvolId = null;
			toast('success', 'Commentaire mis à jour');
		} catch { toast('error', 'Erreur de mise à jour'); }
		finally { editEvolSaving = false; }
	}

	const richEmpty = (html: string) => !html || html.replace(/<[^>]+>/g, '').trim() === '';

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

	function perimetreLabel(items: string[]): string {
		const map: Record<string, string> = {
			'résidence': 'Copropriété entière',
			'bat:1': 'Bât. 1', 'bat:2': 'Bât. 2', 'bat:3': 'Bât. 3', 'bat:4': 'Bât. 4',
			parking: 'Parking', cave: 'Cave', aful: 'AFUL',
		};
		return items.map((i: string) => map[i] ?? i).join(' · ');
	}

	function renderContent(c: string): string {
		const t = c.trimStart();
		const raw = t.startsWith('<') ? c : `<p>${c.replace(/\n/g, '<br>')}</p>`;
		return safeHtml(raw);
	}

	$: statusInfo = STATUTS.find((s) => s.value === ticket?.statut) ?? STATUTS[0];
	$: canReply = ticket && !['fermé'].includes(ticket.statut);

	async function loadEvolutions() {
		try { evolutions = await ticketsApi.evolutions(ticketId); } catch { /* silencieux */ }
	}

	onMount(async () => {
		try {
			[ticket, messages] = await Promise.all([
				ticketsApi.get(ticketId),
				ticketsApi.messages(ticketId),
			]);
			await loadEvolutions();
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
				fichiers_urls: [...msgPhotos.map(f => f.url), ...msgDocs.map(f => f.url)],
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

	async function uploadMsgPhoto(event: Event) {
		const input = event.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;
		uploadingMsgPhoto = true;
		try {
			const result = await fichiersApi.upload(file);
			msgPhotos = [...msgPhotos, result];
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur upload');
		} finally { uploadingMsgPhoto = false; input.value = ''; }
	}

	async function uploadMsgDoc(event: Event) {
		const input = event.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;
		uploadingMsgDoc = true;
		try {
			const result = await fichiersApi.upload(file);
			msgDocs = [...msgDocs, result];
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur upload');
		} finally { uploadingMsgDoc = false; input.value = ''; }
	}

	async function uploadEvolPhoto(event: Event) {
		const input = event.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;
		uploadingEvolPhoto = true;
		try {
			const result = await fichiersApi.upload(file);
			evolPhotos = [...evolPhotos, result];
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur upload');
		} finally { uploadingEvolPhoto = false; input.value = ''; }
	}

	async function uploadEvolDoc(event: Event) {
		const input = event.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;
		uploadingEvolDoc = true;
		try {
			const result = await fichiersApi.upload(file);
			evolDocs = [...evolDocs, result];
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur upload');
		} finally { uploadingEvolDoc = false; input.value = ''; }
	}

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

	async function addEvolution() {
		if (evolType === 'etat' && !evolNouveauStatut) return;
		if (evolType === 'commentaire' && richEmpty(evolContenu)) return;
		evolSaving = true;
		try {
			await ticketsApi.addEvolution(ticketId, {
				type: evolType,
				contenu: evolContenu || undefined,
				nouveau_statut: evolType === 'etat' ? evolNouveauStatut : undefined,
				fichiers_urls: [...evolPhotos.map(f => f.url), ...evolDocs.map(f => f.url)],
				email_externe: evolEmailExterne.trim() || undefined,
				partager_whatsapp: evolPartagerWhatsapp || undefined,
				envoyer_syndic: evolEnvoyerSyndic || undefined,
				envoyer_cs: evolEnvoyerCs || undefined,
			});
			await loadEvolutions();
			if (evolType === 'etat') {
				ticket = await ticketsApi.get(ticketId);
			}
			showEvolForm = false;
			evolContenu = '';
			evolNouveauStatut = '';
			evolPhotos = []; evolDocs = [];
			evolEmailExterne = '';
			evolPartagerWhatsapp = false; evolEnvoyerSyndic = false; evolEnvoyerCs = false;
			toast('success', evolType === 'etat' ? 'Statut mis à jour' : 'Commentaire ajouté');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally { evolSaving = false; }
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

		{#if ticket.photos_urls?.length}
			<div class="ticket-photos" style="margin-top:.75rem;display:flex;gap:.5rem;flex-wrap:wrap">
				{#each ticket.photos_urls as photoUrl}
					<a href={photoUrl} target="_blank" rel="noopener" class="ticket-photo-link">
						<img src={photoUrl} alt="Photo ticket" class="ticket-photo" />
					</a>
				{/each}
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
				<div class="message-bubble" class:own={isOwn} class:interne={msg.interne}>
					<div class="msg-header">
						<strong>{msg.auteur?.prenom} {msg.auteur?.nom}</strong>
						{#if msg.interne}<span class="badge badge-yellow" style="font-size:.65rem">interne</span>{/if}
						<span class="msg-time">{fmtDatetime(msg.cree_le)}</span>
					</div>
					<div class="msg-body">{@html renderContent(msg.contenu)}</div>
					{#if msg.fichiers_urls?.length}
					{@const photos = msg.fichiers_urls.filter(u => /\.(jpe?g|png|webp)$/i.test(u))}
					{@const docs = msg.fichiers_urls.filter(u => !/\.(jpe?g|png|webp)$/i.test(u))}
					{#if photos.length}
						<div style="display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.4rem">
							{#each photos as fUrl}
								<a href={fUrl} target="_blank" rel="noopener">
									<img src={fUrl} alt="Photo" style="width:80px;height:80px;object-fit:cover;border-radius:6px;border:1px solid var(--color-border)" />
								</a>
							{/each}
						</div>
					{/if}
					{#if docs.length}
						<div style="display:flex;flex-wrap:wrap;gap:.3rem;margin-top:.3rem">
							{#each docs as fUrl}
								<a href={fUrl} target="_blank" rel="noopener" style="font-size:.78rem;display:flex;align-items:center;gap:.25rem;color:var(--color-primary)">📄 {fUrl.split('/').pop()}</a>
							{/each}
						</div>
					{/if}
					{/if}
				</div>
			{/if}
		{/each}

		{#if canReply}
			<form class="reply-form card" on:submit|preventDefault={sendMessage}>
				<RichEditor bind:value={newContent} placeholder="Votre réponse…" minHeight="80px" />
				{#if $isCS}
					<label class="checkbox-field" style="margin:.5rem 0">
						<input type="checkbox" bind:checked={newInterne} />
						Message interne (visible par le CS uniquement)
					</label>
					<!-- Photos réponse -->
					{#if !newInterne}
						<div style="margin:.4rem 0">
							<label style="font-size:.8rem;font-weight:500;color:var(--color-text-muted)">📷 Photos</label>
							<div style="display:flex;flex-wrap:wrap;gap:.4rem;margin:.3rem 0">
								{#each msgPhotos as f, i}
									<div style="position:relative">
										<img src={f.url} alt={f.nom} style="width:64px;height:64px;object-fit:cover;border-radius:6px;border:1px solid var(--color-border)" />
										<button type="button" on:click={() => msgPhotos = msgPhotos.filter((_, j) => j !== i)}
											style="position:absolute;top:-5px;right:-5px;border:none;background:var(--color-danger);color:#fff;border-radius:50%;width:18px;height:18px;font-size:.7rem;cursor:pointer;line-height:18px;padding:0;text-align:center">✕</button>
									</div>
								{/each}
							</div>
							<label class="btn btn-outline" style="cursor:pointer;font-size:.8rem;padding:.3rem .6rem;display:inline-block">
								{uploadingMsgPhoto ? 'Upload…' : '+ Ajouter une photo'}
								<input type="file" accept="image/jpeg,image/png,image/webp"
									on:change={uploadMsgPhoto} style="display:none" disabled={uploadingMsgPhoto} />
							</label>
						</div>
						<!-- Documents réponse -->
						<div style="margin:.4rem 0">
							<label style="font-size:.8rem;font-weight:500;color:var(--color-text-muted)">📎 Documents (PDF, Word, Excel)</label>
							<div style="display:flex;flex-wrap:wrap;gap:.3rem;margin:.3rem 0">
								{#each msgDocs as f, i}
									<div style="display:flex;align-items:center;gap:.3rem;background:var(--color-bg-alt);border:1px solid var(--color-border);border-radius:5px;padding:.2rem .4rem;font-size:.78rem">
										<span>📄</span>
										<span style="max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{f.nom}</span>
										<button type="button" on:click={() => msgDocs = msgDocs.filter((_, j) => j !== i)}
											style="border:none;background:none;color:var(--color-danger);cursor:pointer;font-size:.9rem;padding:0;line-height:1">✕</button>
									</div>
								{/each}
							</div>
							<label class="btn btn-outline" style="cursor:pointer;font-size:.8rem;padding:.3rem .6rem;display:inline-block">
								{uploadingMsgDoc ? 'Upload…' : '+ Ajouter un document'}
								<input type="file" accept="application/pdf,.doc,.docx,.xls,.xlsx"
									on:change={uploadMsgDoc} style="display:none" disabled={uploadingMsgDoc} />
							</label>
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
				<button class="btn btn-outline btn-sm" on:click={() => { showEvolForm = !showEvolForm; evolType = 'commentaire'; evolContenu = ''; evolNouveauStatut = ''; }}>
					{showEvolForm ? '✕ Annuler' : '\u{1F4AC} Commenter / état'}
				</button>
			{/if}
		</div>

		{#if showEvolForm}
			<div class="evol-form card" style="margin-bottom:.75rem">
				<h4 style="font-size:.875rem;font-weight:600;margin:0 0 .6rem">Ajouter une évolution</h4>
				<div style="display:flex;gap:.5rem;margin-bottom:.6rem;flex-wrap:wrap">
					<button type="button" class="pill" class:pill-active={evolType === 'commentaire'}
						on:click={() => (evolType = 'commentaire')}>&#x1F4AC; Commentaire</button>
					<button type="button" class="pill" class:pill-active={evolType === 'etat'}
						on:click={() => (evolType = 'etat')}>&#x1F504; Changement d'état</button>
				</div>
				{#if evolType === 'etat'}
					<div class="field">
						<label for="evol-statut">Nouvel état *</label>
						{#if ticket?.statut}
							<div style="font-size:.8rem;color:var(--color-text-muted);margin-bottom:.35rem">État actuel : <strong>{STATUT_LABELS[ticket.statut] || ticket.statut}</strong></div>
						{/if}
						<select id="evol-statut" bind:value={evolNouveauStatut}>
							<option value="">— Choisir —</option>
							<option value="ouvert">&#x1F535; Ouvert</option>
							<option value="en_cours">&#x1F7E1; En cours</option>
							<option value="résolu">&#x1F7E2; Résolu</option>
							<option value="fermé">⚫ Fermé</option>
						</select>
					</div>
				{/if}
				<div class="field">
					<label>{evolType === 'etat' ? 'Commentaire (optionnel)' : 'Commentaire *'}</label>
					<RichEditor bind:value={evolContenu}
						placeholder={evolType === 'etat' ? 'Précisions sur ce changement…' : 'Ajoutez un commentaire de suivi…'}
						minHeight="90px" />
				</div>
				<!-- Options de partage -->
				<div style="margin:.5rem 0 .6rem;display:flex;flex-wrap:wrap;gap:.75rem">
					<label class="checkbox-field">
						<input type="checkbox" bind:checked={evolPartagerWhatsapp} />
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="#25D366" style="flex-shrink:0" aria-label="WhatsApp">
							<path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51a12.66 12.66 0 0 0-.57-.01c-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 0 1-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 0 1-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 0 1 2.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0 0 12.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 0 0 5.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 0 0-3.48-8.413Z"/>
						</svg>
						<span style="font-size:.82rem">Partager sur le groupe</span>
					</label>
					<label class="checkbox-field">
						<input type="checkbox" bind:checked={evolEnvoyerSyndic} />
						<span style="font-size:.82rem">✉️ Envoyer au syndic</span>
					</label>
					<label class="checkbox-field">
						<input type="checkbox" bind:checked={evolEnvoyerCs} />
						<span style="font-size:.82rem">✉️ Envoyer au CS</span>
					</label>
				</div>
				<!-- Photos évolution -->
				{#if evolType === 'commentaire'}
					<div style="margin:.4rem 0">
						<label style="font-size:.8rem;font-weight:500;color:var(--color-text-muted)">📷 Photos</label>
						<div style="display:flex;flex-wrap:wrap;gap:.4rem;margin:.3rem 0">
							{#each evolPhotos as f, i}
								<div style="position:relative">
									<img src={f.url} alt={f.nom} style="width:64px;height:64px;object-fit:cover;border-radius:6px;border:1px solid var(--color-border)" />
									<button type="button" on:click={() => evolPhotos = evolPhotos.filter((_, j) => j !== i)}
										style="position:absolute;top:-5px;right:-5px;border:none;background:var(--color-danger);color:#fff;border-radius:50%;width:18px;height:18px;font-size:.7rem;cursor:pointer;line-height:18px;padding:0;text-align:center">✕</button>
								</div>
							{/each}
						</div>
						<label class="btn btn-outline" style="cursor:pointer;font-size:.8rem;padding:.3rem .6rem;display:inline-block">
							{uploadingEvolPhoto ? 'Upload…' : '+ Ajouter une photo'}
							<input type="file" accept="image/jpeg,image/png,image/webp"
								on:change={uploadEvolPhoto} style="display:none" disabled={uploadingEvolPhoto} />
						</label>
					</div>
					<!-- Documents évolution -->
					<div style="margin:.4rem 0">
						<label style="font-size:.8rem;font-weight:500;color:var(--color-text-muted)">📎 Documents (PDF, Word, Excel)</label>
						<div style="display:flex;flex-wrap:wrap;gap:.3rem;margin:.3rem 0">
							{#each evolDocs as f, i}
								<div style="display:flex;align-items:center;gap:.3rem;background:var(--color-bg-alt);border:1px solid var(--color-border);border-radius:5px;padding:.2rem .4rem;font-size:.78rem">
									<span>📄</span>
									<span style="max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{f.nom}</span>
									<button type="button" on:click={() => evolDocs = evolDocs.filter((_, j) => j !== i)}
										style="border:none;background:none;color:var(--color-danger);cursor:pointer;font-size:.9rem;padding:0;line-height:1">✕</button>
								</div>
							{/each}
						</div>
						<label class="btn btn-outline" style="cursor:pointer;font-size:.8rem;padding:.3rem .6rem;display:inline-block">
							{uploadingEvolDoc ? 'Upload…' : '+ Ajouter un document'}
							<input type="file" accept="application/pdf,.doc,.docx,.xls,.xlsx"
								on:change={uploadEvolDoc} style="display:none" disabled={uploadingEvolDoc} />
						</label>
					</div>
				{/if}
				<!-- Email externe évolution -->
				<div style="margin:.4rem 0">
					<label for="evol-email-ext" style="font-size:.8rem;font-weight:500;color:var(--color-text-muted)">📧 Notifier une adresse email externe (optionnel)</label>
					<input id="evol-email-ext" type="email" bind:value={evolEmailExterne}
						placeholder="contact@exemple.fr"
						style="padding:.35rem .6rem;border:1px solid var(--color-border);border-radius:6px;font-size:.85rem;width:100%;max-width:320px;margin-top:.25rem;display:block" />
				</div>
				<div class="form-actions" style="gap:.5rem">
					<button type="button" class="btn btn-outline" on:click={() => (showEvolForm = false)}>Annuler</button>
					<button type="button" class="btn btn-primary"
						disabled={evolSaving || (evolType === 'etat' && !evolNouveauStatut) || (evolType === 'commentaire' && richEmpty(evolContenu))}
						on:click={addEvolution}>
						{evolSaving ? 'Envoi…' : 'Valider'}
					</button>
				</div>
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
									<button type="button" title="Modifier" on:click={() => startEditEvol(evol)}
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
							{#if evol.type === 'commentaire'}
								{#if editingEvolId === evol.id}
									<!-- Formulaire d'édition inline -->
									<div style="margin:.4rem 0;border:1px solid var(--color-border);border-radius:8px;padding:.75rem;background:var(--color-bg)">
										<RichEditor bind:value={editEvolContenu} minHeight="80px" />
										<!-- Photos -->
										<div style="margin:.5rem 0">
											<label style="font-size:.78rem;font-weight:500;color:var(--color-text-muted)">📷 Photos</label>
											<div style="display:flex;flex-wrap:wrap;gap:.35rem;margin:.3rem 0">
												{#each editEvolPhotos as f, i}
													<div style="position:relative">
														<img src={f.url} alt={f.nom} style="width:56px;height:56px;object-fit:cover;border-radius:6px;border:1px solid var(--color-border)" />
														<button type="button" on:click={() => editEvolPhotos = editEvolPhotos.filter((_,j)=>j!==i)}
															style="position:absolute;top:-5px;right:-5px;border:none;background:var(--color-danger);color:#fff;border-radius:50%;width:16px;height:16px;font-size:.65rem;cursor:pointer;line-height:16px;padding:0;text-align:center">✕</button>
													</div>
												{/each}
											</div>
											<label class="btn btn-outline" style="cursor:pointer;font-size:.78rem;padding:.25rem .5rem;display:inline-block">
												{uploadingEditPhoto ? 'Upload…' : '+ Photo'}
												<input type="file" accept="image/jpeg,image/png,image/webp" on:change={uploadEditPhoto} style="display:none" disabled={uploadingEditPhoto} />
											</label>
										</div>
										<!-- Documents -->
										<div style="margin:.4rem 0">
											<label style="font-size:.78rem;font-weight:500;color:var(--color-text-muted)">📎 Documents</label>
											<div style="display:flex;flex-wrap:wrap;gap:.3rem;margin:.3rem 0">
												{#each editEvolDocs as f, i}
													<div style="display:flex;align-items:center;gap:.25rem;background:var(--color-bg-alt);border:1px solid var(--color-border);border-radius:5px;padding:.15rem .35rem;font-size:.75rem">
														<span>📄</span>
														<span style="max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{f.nom}</span>
														<button type="button" on:click={() => editEvolDocs = editEvolDocs.filter((_,j)=>j!==i)}
															style="border:none;background:none;color:var(--color-danger);cursor:pointer;font-size:.85rem;padding:0;line-height:1">✕</button>
													</div>
												{/each}
											</div>
											<label class="btn btn-outline" style="cursor:pointer;font-size:.78rem;padding:.25rem .5rem;display:inline-block">
												{uploadingEditDoc ? 'Upload…' : '+ Document'}
												<input type="file" accept="application/pdf,.doc,.docx,.xls,.xlsx" on:change={uploadEditDoc} style="display:none" disabled={uploadingEditDoc} />
											</label>
										</div>
										<div style="display:flex;gap:.5rem;margin-top:.5rem">
											<button class="btn btn-outline btn-sm" on:click={() => editingEvolId = null}>Annuler</button>
											<button class="btn btn-primary btn-sm" disabled={editEvolSaving || richEmpty(editEvolContenu)} on:click={saveEvolEdit}>
												{editEvolSaving ? 'Enregistrement…' : 'Enregistrer'}
											</button>
										</div>
									</div>
								{:else if evol.contenu}
									<span class="evol-text rich-content" style="font-size:.875rem">{@html safeHtml(evol.contenu)}</span>
								{/if}
							{/if}
							{#if evol.fichiers_urls?.length && editingEvolId !== evol.id}
								{@const photos = evol.fichiers_urls.filter(u => /\.(jpe?g|png|webp)$/i.test(u))}
								{@const docs = evol.fichiers_urls.filter(u => !/\.(jpe?g|png|webp)$/i.test(u))}
								{#if photos.length}
									<div style="display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.3rem">
										{#each photos as fUrl}
											<a href={fUrl} target="_blank" rel="noopener">
												<img src={fUrl} alt="" style="width:72px;height:72px;object-fit:cover;border-radius:6px;border:1px solid var(--color-border)" />
											</a>
										{/each}
									</div>
								{/if}
								{#if docs.length}
									<div style="display:flex;flex-wrap:wrap;gap:.3rem;margin-top:.25rem">
										{#each docs as fUrl}
											<a href={fUrl} target="_blank" rel="noopener" style="font-size:.75rem;display:flex;align-items:center;gap:.2rem;color:var(--color-primary)">📄 {fUrl.split('/').pop()}</a>
										{/each}
									</div>
								{/if}
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
