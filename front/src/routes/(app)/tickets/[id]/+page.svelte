<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { page } from '$app/stores';
	import { currentUser, isCS, isAdmin } from '$lib/stores/auth';
	import { tickets as ticketsApi, ApiError, type TicketEvolution, type TicketMessage } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import EvolForm from '$lib/components/EvolForm.svelte';
	import PiecesJointes from '$lib/components/PiecesJointes.svelte';
	import FicheLecture from '$lib/components/FicheLecture.svelte';
	import HistoriqueTicket from '$lib/components/HistoriqueTicket.svelte';
	import { TICKET } from '$lib/entites/ticket';
	import { siteNomStore } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';
	import { fmtDatetime, fmtDateLong, fmtDateShort } from '$lib/date';
	import {
		STATUTS_TICKET,
		STATUT_TICKET_BADGE,
		STATUT_TICKET_LABELS as STATUT_LABELS,
		categorieTicketLabel,
		estTicketClos,
	} from '$lib/tickets';

	$: _siteNom = $siteNomStore;

	let ticket: any = null;
	let messages: TicketMessage[] = [];
	let evolutions: TicketEvolution[] = [];
	let loading = true;
	let sending = false;
	let updatingStatus = false;
	//  Lié à `EvolForm` : le formulaire de réponse le propose en section
	//  Diffusion, la page décide de ce qu'il masque (pièces jointes et adresse
	//  externe n'ont pas de sens sur un message qui ne sort pas du CS).
	let newInterne = false;

	// Évolutions
	//  ⚠️ Les quatre états du fil (formulaire ouvert, entrée en correction, deux
	//  drapeaux d'enregistrement) et leurs trois handlers vivaient ICI. Ils sont
	//  partis dans `HistoriqueTicket` avec le balisage qu'ils servaient : c'est
	//  ce qui garantit qu'un geste ajouté au fil arrivera sur les DEUX écrans, la
	//  liste et cette fiche, au lieu d'un seul (18/08/2026).
	$: ticketId = Number($page.params.id);

	//  ── Un seul geste pour changer d'état, sur cet écran comme ailleurs ──────
	//  Cette page portait DEUX commandes pour le même geste, à quelques
	//  centimètres l'une de l'autre : les boutons « Changer le statut » (qui
	//  proposaient `annulé`) et le formulaire d'évolution (qui proposait `fermé`
	//  à la place). Arbitré le 17/08/2026 (#415) : les boutons restent, le
	//  formulaire d'évolution ne sert plus qu'au commentaire.

	const PRIORITE: Record<string, { label: string; cls: string }> = {
		basse:   { label: 'Priorité basse',   cls: 'badge-gray' },
		normale: { label: 'Priorité normale', cls: 'badge-default' },
		haute:   { label: 'Priorité haute',   cls: 'badge-orange' },
	};

	//  Les messages du fil sont d'anciens textes bruts pour certains : un contenu
	//  qui ne commence pas par une balise est enveloppé avant assainissement.
	//  La DESCRIPTION du ticket, elle, passe par `FicheLecture` — un objet se rend
	//  toujours de la même façon (R3).
	function renderContent(c: string): string {
		const t = c.trimStart();
		const raw = t.startsWith('<') ? c : `<p>${c.replace(/\n/g, '<br>')}</p>`;
		return safeHtml(raw);
	}

	$: statutBadge = STATUT_TICKET_BADGE[ticket?.statut ?? ''] ?? 'badge-gray';
	$: statutLabel = STATUT_LABELS[ticket?.statut ?? ''] ?? ticket?.statut ?? '';
	//  `canReply` valait `statut !== 'fermé'` — le seul état qui interdisait de
	//  répondre, et il n'existe plus (#415, migration 0149). La condition n'est
	//  pas transposée à `clos` : elle fermerait la discussion sur les tickets
	//  résolus, qui l'acceptent aujourd'hui. Répondre reste donc toujours
	//  possible ; c'est `clos` qui change le libellé du bouton, plus bas.

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
	$: clos = ticket && estTicketClos(ticket.statut);

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

	//  ── UNE seule forme d'évolution sur cet écran (#431) ─────────────────────
	//  Cette page portait `EvolForm` **et** un formulaire de réponse écrit à la
	//  main, à quelques centimètres : jeux de champs presque identiques, deux
	//  libellés de bouton pour le même geste (« Envoyer » contre « Enregistrer »),
	//  et une case « Message interne » posée au milieu du commentaire alors que
	//  c'est une décision de diffusion. Le formulaire à la main a disparu ; ce que
	//  la réponse enregistre — un `TicketMessage`, qui alimente le fil de bulles —
	//  n'a pas changé.
	async function sendMessage(e: CustomEvent) {
		const data = e.detail;
		if (!data.contenu?.trim()) return;
		sending = true;
		try {
			const msg = await ticketsApi.addMessage(ticketId, {
				contenu: data.contenu,
				interne: !!data.interne,
				fichiers_urls: data.fichiers_urls ?? [],
				email_externe: data.email_externe,
			});
			messages = [...messages, msg];
			newInterne = false;
			repondreOuvert = false;
			await loadEvolutions();
		} catch (err) {
			toast('error', err instanceof ApiError ? err.message : 'Erreur');
		} finally {
			sending = false;
		}
	}

	//  ── Le changement d'état est une TRANSITION, pas une correction ──────────
	//  Ces boutons passaient par `PATCH /tickets/{id}`, qui écrivait lui-même une
	//  évolution « Statut : X → Y ». Depuis que l'édition rouvre le workflow
	//  (cadre #430), le `PATCH` ne peut plus produire de transition — il écrirait
	//  une étape de suivi à chaque faute de frappe rattrapée. Il écrit désormais
	//  une **correction**, et la transition passe par l'endpoint qui la trace
	//  vraiment : date, auteur, courriel à l'auteur du ticket.
	async function updateStatus(s: string) {
		updatingStatus = true;
		try {
			await ticketsApi.addEvolution(ticketId, { type: 'etat', nouveau_statut: s });
			ticket = await ticketsApi.get(ticketId);
			await loadEvolutions();
			toast('success', 'Statut mis à jour');
		} catch (err) {
			toast('error', err instanceof ApiError ? err.message : 'Erreur de mise à jour');
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
	<p class="etat-chargement">Chargement…</p>
{:else if !ticket}
	<div class="empty-state"><h3>Ticket introuvable</h3></div>
{:else}
	<!--  La fiche suit l'ORDRE DES NEUF SECTIONS, comme les formulaires : c'est
	      `FicheLecture` qui le lit dans la déclaration `TICKET`, et les slots ne
	      peuvent donc pas atterrir ailleurs qu'à la place de leur section.
	      Avant #431, l'écran commençait par le badge d'état (section 3) puis le
	      titre (section 1), et rendait `[...photos_urls, ...fichiers_urls]` dans
	      UN seul bloc — la fusion des sections 7 et 8, que le cadre interdit. -->
	<div class="ticket-header card">
		<FicheLecture
			entite={TICKET}
			perimetre={ticket.perimetre_cible ?? []}
			description={ticket.description}
			photos={ticket.photos_urls ?? []}
			documents={ticket.fichiers_urls ?? []}
		>
			<svelte:fragment slot="titre">
				<div class="ticket-meta">
					<span class="badge badge-default">{categorieTicketLabel(ticket.categorie)}</span>
				</div>
				<h1 class="ticket-titre">{ticket.titre}</h1>
				<p class="ticket-dates">
					{fmtDateLong(ticket.cree_le)}
					{#if ticket.mis_a_jour_le && ticket.mis_a_jour_le !== ticket.cree_le}
						&middot; mis à jour le {fmtDateShort(ticket.mis_a_jour_le)}
					{/if}
				</p>
			</svelte:fragment>

			<svelte:fragment slot="specifiques">
				{#if ticket.saisi_pour_affichage && $isCS}
					<p class="ticket-saisi-pour">
						👤 Saisi par <strong>{ticket.auteur_nom ?? 'inconnu'}</strong> pour <strong>{ticket.saisi_pour_affichage}</strong>
						{#if ticket.saisi_pour_email}
							· <a href="mailto:{ticket.saisi_pour_email}">{ticket.saisi_pour_email}</a>
						{/if}
					</p>
				{/if}
			</svelte:fragment>

			<svelte:fragment slot="workflow">
				<div class="ticket-meta">
					<span class="badge {statutBadge}">{statutLabel}</span>
					{#if ticket.priorite && ticket.priorite !== 'normale'}
						<span class="badge {PRIORITE[ticket.priorite]?.cls ?? 'badge-default'}">{PRIORITE[ticket.priorite]?.label}</span>
					{/if}
				</div>
				{#if $isCS}
					<div class="status-actions">
						<span class="status-label">Changer le statut :</span>
						<div class="status-boutons">
							{#each STATUTS_TICKET as s}
								<button
									class="btn btn-sm {ticket.statut === s.value ? 'btn-primary' : 'btn-secondary'}"
									disabled={updatingStatus || ticket.statut === s.value}
									on:click={() => updateStatus(s.value)}
								>{s.label}</button>
							{/each}
						</div>
					</div>
				{/if}
			</svelte:fragment>

			<svelte:fragment slot="pied">
				{#if ticket.destinataire_syndic}
					<p class="ticket-envoi">📧 Envoyé au syndic</p>
				{/if}
			</svelte:fragment>
		</FicheLecture>
	</div>

	<!-- Thread messages -->
	<div class="messages">
		{#each messages as msg}
			{@const isOwn = msg.auteur?.id === $currentUser?.id}
			{#if !msg.interne || $isCS}
				<div id="msg-{msg.id}" class="message-bubble" class:own={isOwn} class:interne={msg.interne}
					class:message-vise={msgVise === msg.id}>
					<div class="msg-header">
						<strong>{msg.auteur?.prenom} {msg.auteur?.nom}</strong>
						{#if msg.interne}<span class="badge badge-yellow msg-badge">interne</span>{/if}
						<span class="msg-time">{fmtDatetime(msg.cree_le)}</span>
					</div>
					<div class="msg-body">{@html renderContent(msg.contenu)}</div>
					{#if msg.fichiers_urls?.length}
						<div class="msg-pj">
							<PiecesJointes urls={msg.fichiers_urls} size={80} />
						</div>
					{/if}
				</div>
			{/if}
		{/each}

		{#if !repondreOuvert}
			<div class="card carte-repondre">
				<button type="button" class="btn btn-outline" on:click={() => (repondreOuvert = true)}>
					{clos ? '↩️ Rouvrir la discussion' : '💬 Répondre'}
				</button>
			</div>
		{:else}
			<div class="card reply-form">
				{#key repondreOuvert}
					<EvolForm idPrefixe="tk-msg" titre="Répondre"
						showFiles={!newInterne}
						showEmail={$isCS && !newInterne}
						avecInterne={$isCS}
						bind:interne={newInterne}
						saving={sending}
						on:submit={sendMessage}
						on:cancel={() => (repondreOuvert = false)}
					/>
				{/key}
			</div>
		{/if}
	</div>

	<!--  L'HISTORIQUE — le fil, avec ses gestes. Extrait le 18/08/2026 dans
	      `HistoriqueTicket` : la liste et cette fiche le rendaient chacune de
	      leur côté, et les deux câblages ont divergé DEUX FOIS, dans les deux
	      sens — le crayon manquait à la liste, la corbeille manquait ici. -->
	<HistoriqueTicket ticketId={ticketId} statutCourant={ticket?.statut ?? ''}
		{evolutions} on:change={loadEvolutions} />

	<!-- Suppression admin -->
	{#if $isAdmin}
		<div class="zone-suppression">
			<button class="btn btn-outline btn-sm btn-supprimer" on:click={deleteTicket}>
				&#x1F5D1;️ Supprimer définitivement
			</button>
		</div>
	{/if}
{/if}

<style>
	/*  ⚠️ Le fil d'évolutions n'a plus AUCUN style ici : `.evol-list`, `.evol-item`,
	    `.evol-meta`… vivent dans `RubriqueHistorique`, avec le balisage qu'ils
	    habillent. Les laisser ici en aurait fait la quatrième copie d'un même
	    bloc, et Svelte ne les aurait de toute façon pas appliqués au composant. */

	.etat-chargement { color: var(--color-text-muted); }

	/* Message pointé par l'ancre d'une notification : un cadre suffit à le
	   situer, sans clignotement ni couleur criarde — on vient lire, pas être
	   alerté une seconde fois. */
	.message-vise { outline: 2px solid var(--color-primary); outline-offset: 3px; border-radius: 10px; }
	.back-link { display: inline-flex; align-items: center; gap: .3rem; font-size: .85rem; color: var(--color-text-muted); text-decoration: none; margin-bottom: .75rem; }
	.back-link:hover { color: var(--color-primary); }

	/*  La colonne de lecture : la même largeur pour la fiche, le fil et
	    l'Historique — elle valait 720 px écrits en ligne quatre fois. */
	.ticket-header, .messages, .bloc-historique, .zone-suppression { max-width: 720px; }
	.ticket-header { border-left: 4px solid var(--color-primary); margin-bottom: 1rem; }
	.ticket-meta { display: flex; gap: .4rem; flex-wrap: wrap; margin-bottom: .4rem; }
	.ticket-titre { font-size: 1.1rem; font-weight: 700; margin: .6rem 0 .3rem; }
	.ticket-dates { font-size: .875rem; color: var(--color-text-muted); }
	.ticket-envoi { font-size: .8rem; color: var(--color-text-muted); margin-top: .5rem; }
	.ticket-saisi-pour {
		font-size: .85rem;
		color: var(--color-text-muted);
		margin: .5rem 0;
		padding: .5rem .75rem;
		background: var(--color-bg-muted, #f5f5f5);
		border-radius: var(--radius);
	}
	.status-actions { margin-top: .75rem; padding-top: .75rem; border-top: 1px solid var(--color-border); }
	.status-label { font-size: .8rem; font-weight: 500; color: var(--color-text-muted); }
	.status-boutons { display: flex; gap: .4rem; flex-wrap: wrap; margin-top: .3rem; }

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
	.msg-badge { font-size: .65rem; }
	.msg-time { color: var(--color-text-muted); margin-left: auto; }
	.msg-body { font-size: .875rem; line-height: 1.55; margin: 0; }
	.msg-body :global(p) { margin: 0 0 .4em; }
	.msg-body :global(p:last-child) { margin-bottom: 0; }
	.msg-body :global(ul), .msg-body :global(ol) { padding-left: 1.3em; margin: 0 0 .4em; }
	.msg-body :global(strong) { font-weight: 600; }
	.msg-pj { margin-top: .4rem; }

	.carte-repondre { text-align: center; padding: .9rem; }
	.reply-form { margin-top: .5rem; }

	.bloc-historique { margin-top: 1.5rem; }
	.evol-form { padding: .75rem; margin-top: .75rem; }

	.zone-suppression { margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--color-border); }
	.btn-supprimer { color: var(--color-danger); border-color: var(--color-danger); }
</style>
