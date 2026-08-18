<script lang="ts">
	import EntetePage from '$lib/components/EntetePage.svelte';
	import { onMount } from 'svelte';
	import { revelerCible } from '$lib/deepLink';
	import { isCS, isAdmin } from '$lib/stores/auth';
	import { tickets as ticketsApi, ApiError, type Ticket, type TicketEvolution } from '$lib/api';
	import { getPageConfig, configStore, siteNomStore, defautsDePage } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';
	import { toast } from '$lib/components/Toast.svelte';
	import ListeTickets from '$lib/components/ListeTickets.svelte';
	import FormulaireTicket from '$lib/components/FormulaireTicket.svelte';
	import AvertissementUrgence from '$lib/components/AvertissementUrgence.svelte';
	import {
		CATEGORIES_TICKET,
		STATUTS_TICKET_FILTRE,
		estTicketClos,
	} from '$lib/tickets';

$: _pc = getPageConfig($configStore, 'mes-demandes', defautsDePage('mes-demandes'));
	$: _siteNom = $siteNomStore;

	let ticketList: Ticket[] = [];
	let loading = true;
	let filterStatut = '';
	let filterCat = '';

	// Création : boîte dans la page, comme partout ailleurs sur le site (#367).
	// Ce fut le dernier écran à créer un objet par page dédiée — cf. l'en-tête de
	// FormulaireTicket.svelte.
	let showForm = false;

	function ticketCree(e: CustomEvent<Ticket>) {
		ticketList = [e.detail, ...ticketList];
		showForm = false;
	}

	//  Ce que la page décide, et qu'elle est seule à savoir : quel ticket est
	//  déplié, lequel est ouvert en correction, lequel attend une entrée
	//  d'Historique. Le rendu, lui, vit dans `ListeTickets` → `CarteTicket`, et
	//  l'affichage suit la déclaration `TICKET` (`$lib/entites/ticket`).
	let expandedTickets = new Set<number>();
	// Évolutions par ticket (chargées à la demande)
	let evolsMap: Record<number, TicketEvolution[]> = {};
	let evolsLoaded = new Set<number>();
	let showEvolForm: number | null = null;
	let editingTicket: number | null = null;
	let evolSaving = false;

	//  Badges, libellés, options du workflow ET catégories viennent de
	//  `$lib/tickets` : quatre listes de statuts avaient divergé (#415), et les
	//  catégories étaient à leur tour écrites en quatre endroits — dont ces six
	//  boutons de filtre, en dur dans le balisage (#431).

	onMount(async () => {
		try {
			ticketList = await ticketsApi.list();
			const params = new URLSearchParams(window.location.search);
			// `?nouveau=1` ouvre directement la boîte de création. C'est ce qui
			// remplace l'ancienne page `/tickets/nouveau` : les liens qui menaient
			// à un écran de saisie doivent continuer à y mener, pas atterrir sur la
			// liste en laissant l'utilisateur chercher le bouton.
			if (params.get('nouveau')) showForm = true;
			// Auto-ouverture depuis ?open=TK-XXXXX (lien profond depuis le tableau de bord)
			const openNum = params.get('open');
			if (openNum) {
				const target = ticketList.find(t => t.numero === openNum);
				if (target) {
					if (estArchive(target)) {
						historyExpanded = true;
						const yr = new Date(target.mis_a_jour_le ?? target.cree_le).getFullYear();
						expandedYears = new Set([yr]);
					}
					await toggleTicket(target);
					revelerCible(`ticket-${target.id}`);
				}
			}
		}
		finally { loading = false; }
	});

	// Délai de grâce : un ticket clôturé reste visible dans la liste principale
	// pendant 7 jours après sa clôture, puis bascule dans l'Historique.
	const HISTORIQUE_DELAI_MS = 7 * 24 * 60 * 60 * 1000;
	function estArchive(t: { statut: string; mis_a_jour_le?: string; cree_le: string }): boolean {
		if (!estTicketClos(t.statut)) return false;
		return Date.now() - new Date(t.mis_a_jour_le ?? t.cree_le).getTime() > HISTORIQUE_DELAI_MS;
	}

	$: filtered = ticketList.filter((t) => {
		if (estArchive(t)) return false;
		if (filterStatut && t.statut !== filterStatut) return false;
		if (filterCat && t.categorie !== filterCat) return false;
		return true;
	});

	// Historique : tickets clôturés depuis plus de 7 jours, limité à 3 ans, groupés par année décroissante
	const THREE_YEARS_AGO = new Date();
	THREE_YEARS_AGO.setFullYear(THREE_YEARS_AGO.getFullYear() - 3);

	$: historyTickets = ticketList
		.filter((t) => estArchive(t) && new Date(t.mis_a_jour_le ?? t.cree_le) >= THREE_YEARS_AGO)
		.sort((a, b) => new Date(b.mis_a_jour_le ?? b.cree_le).getTime() - new Date(a.mis_a_jour_le ?? a.cree_le).getTime());

	$: historyByYear = (() => {
		const groups = new Map<number, typeof historyTickets>();
		for (const t of historyTickets) {
			const year = new Date(t.mis_a_jour_le ?? t.cree_le).getFullYear();
			if (!groups.has(year)) groups.set(year, []);
			groups.get(year)!.push(t);
		}
		return [...groups.entries()].sort(([a], [b]) => b - a);
	})();

	let historyExpanded = false;
	let expandedYears = new Set<number>();

	function basculerAnnee(year: number) {
		if (expandedYears.has(year)) expandedYears.delete(year);
		else expandedYears.add(year);
		expandedYears = expandedYears;
	}

	async function toggleTicket(t: Ticket) {
		if (expandedTickets.has(t.id)) {
			expandedTickets.delete(t.id);
			expandedTickets = new Set(expandedTickets);
			fermerFormulaires();
		} else {
			expandedTickets = new Set([t.id]);
			fermerFormulaires();
			if (!evolsLoaded.has(t.id)) await loadEvolutions(t.id);
		}
	}

	function fermerFormulaires() {
		showEvolForm = null;
		editingTicket = null;
	}

	async function loadEvolutions(id: number) {
		try {
			evolsMap[id] = await ticketsApi.evolutions(id);
			evolsLoaded = new Set([...evolsLoaded, id]);
			evolsMap = { ...evolsMap };
		} catch { /* silencieux */ }
	}

	//  Ouvrir un formulaire déplie sa carte et referme l'autre : deux formulaires
	//  ouverts sur le même écran, c'est deux « Enregistrer » pour deux gestes
	//  différents à quelques centimètres.
	//  UN point d'entrée (#426) : le formulaire porte les DEUX gestes, et lequel a
	//  été fait se lit dans les pastilles — celle de l'état courant est active, la
	//  laisser telle quelle ne change rien.
	function openEvolForm(t: Ticket) {
		editingTicket = null;
		showEvolForm = t.id;
		expandedTickets = new Set([t.id]);
	}

	function openEditForm(t: Ticket) {
		showEvolForm = null;
		editingTicket = t.id;
		expandedTickets = new Set([t.id]);
	}

	//  Reçoit l'événement `evoluer` de la carte — même contrat que la fiche détail
	//  (`tickets/[id]`), y compris `fichiers_urls` : c'est ce qui apporte les pièces
	//  jointes à une réaction depuis cette page.
	type PayloadEvolution = {
		type: string;
		contenu?: string;
		nouveau_statut?: string;
		fichiers_urls?: string[];
		email_externe?: string;
		partager_whatsapp?: boolean;
		envoyer_syndic?: boolean;
		envoyer_cs?: boolean;
	};

	//  ── Correction d'une entrée du fil ──────────────────────────────────────
	//  Le crayon existait dans `RubriqueHistorique` depuis #431 et servait la
	//  FICHE d'un ticket ; la liste ne le branchait pas. Même entité, deux
	//  rendus, une capacité sur deux — signalé à l'écran le 18/08/2026.
	let evolEnEdition: number | null = null;
	let evolCorrectionEnCours = false;

	//  🔴 Effacer une entrée du fil — ADMIN seulement, et le serveur le revérifie
	//  (`require_admin`). Une transition d'état est refusée côté serveur (422) et
	//  n'affiche pas de corbeille côté écran : l'écran dit la même chose que le
	//  serveur, ni plus ni moins.
	//
	//  ⚠️ Pas de confirmation : le geste est réservé à l'admin, porte une corbeille
	//  explicite, et le fil se recharge aussitôt — l'effet est immédiatement
	//  visible. Une modale de plus sur un geste déjà restreint et déjà rare
	//  ajouterait un clic sans ajouter de sécurité.
	async function supprimerEvolution(e: CustomEvent<{ ticket: Ticket; evolId: number }>) {
		const { ticket: t, evolId } = e.detail;
		try {
			await ticketsApi.deleteEvolution(t.id, evolId);
			await loadEvolutions(t.id);
			toast('success', 'Entrée supprimée');
		} catch (e2) {
			toast('error', e2 instanceof ApiError ? e2.message : 'Erreur');
		}
	}

	async function corrigerEvolution(e: CustomEvent<{ ticket: Ticket; data: any }>) {
		if (evolEnEdition === null) return;
		const t = e.detail.ticket;
		evolCorrectionEnCours = true;
		try {
			//  🔴 Ni `type` ni `nouveau_statut` : une CORRECTION n'est pas une
			//  transition. Les envoyer ferait apparaître dans le fil une étape que le
			//  ticket n'a jamais franchie (`test_correction_pas_transition.py`).
			await ticketsApi.updateEvolution(t.id, evolEnEdition, {
				contenu: e.detail.data.contenu ?? '',
				fichiers_urls: e.detail.data.fichiers_urls,
			});
			await loadEvolutions(t.id);
			evolEnEdition = null;
			toast('success', 'Entrée corrigée');
		} catch (e2) {
			toast('error', e2 instanceof ApiError ? e2.message : 'Erreur');
		} finally { evolCorrectionEnCours = false; }
	}

	async function addEvolution(e: CustomEvent<{ ticket: Ticket; data: unknown }>) {
		const t = e.detail.ticket;
		const data = e.detail.data as PayloadEvolution;
		evolSaving = true;
		try {
			await ticketsApi.addEvolution(t.id, {
				type: data.type,
				contenu: data.contenu || undefined,
				nouveau_statut: data.nouveau_statut,
				fichiers_urls: data.fichiers_urls,
				email_externe: data.email_externe,
				partager_whatsapp: data.partager_whatsapp || undefined,
				envoyer_syndic: data.envoyer_syndic || undefined,
				envoyer_cs: data.envoyer_cs || undefined,
			});
			if (data.type === 'etat') {
				ticketList = ticketList.map(x => x.id === t.id ? { ...x, statut: data.nouveau_statut ?? x.statut } : x);
			}
			await loadEvolutions(t.id);
			showEvolForm = null;
			toast('success', data.type === 'etat' ? 'Statut mis à jour' : 'Commentaire ajouté');
		} catch (e2) {
			toast('error', e2 instanceof ApiError ? e2.message : 'Erreur');
		} finally { evolSaving = false; }
	}

	async function deleteTicket(e: CustomEvent<Ticket>) {
		const t = e.detail;
		if (!confirm(`Supprimer définitivement le ticket #${t.numero} ? Cette action est irréversible.`)) return;
		try {
			await ticketsApi.delete(t.id);
			ticketList = ticketList.filter(x => x.id !== t.id);
			toast('success', 'Ticket supprimé');
		} catch (err) {
			toast('error', err instanceof ApiError ? err.message : 'Erreur');
		}
	}

	//  Le PATCH inscrit une CORRECTION dans le fil (« Correction : État … ») :
	//  sans ce rechargement, la carte affiche le ticket corrigé au-dessus d'un
	//  historique qui n'en dit rien.
	async function ticketModifie(e: CustomEvent<Ticket>) {
		const maj = e.detail;
		ticketList = ticketList.map(x => x.id === maj.id ? { ...x, ...maj } : x);
		await loadEvolutions(maj.id);
		editingTicket = null;
	}
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<EntetePage titre={_pc.titre} icone={_pc.icone || 'message-square-text'}>
	<!--  L'en-tête n'OUVRE plus que le formulaire : l'annulation vit à côté
	      d'« Enregistrer », dans le formulaire (18/08/2026). Le bouton s'efface
	      pendant la saisie — le laisser en « ✕ Annuler » ferait deux commandes
	      d'annulation pour un seul formulaire (#367). -->
	{#if !showForm}
		<button class="btn btn-primary page-header-btn" on:click={() => (showForm = true)}>
			+ Nouveau ticket
		</button>
	{/if}
</EntetePage>
<div class="page-subtitle">{@html safeHtml(_pc.descriptif)}</div>

{#if showForm}
	<FormulaireTicket on:cree={ticketCree} on:annule={() => (showForm = false)} />
{/if}

<AvertissementUrgence />

<div class="filters">
	<span class="filter-group">
		<button class="btn btn-sm" class:btn-primary={filterStatut === ''} on:click={() => filterStatut = ''}>Tous</button>
		{#each STATUTS_TICKET_FILTRE as s (s.value)}
			<button class="btn btn-sm" class:btn-primary={filterStatut === s.value}
				on:click={() => filterStatut = s.value}>{s.label}</button>
		{/each}
	</span>
	<span class="filter-sep"></span>
	<span class="filter-group">
		<button class="btn btn-sm" class:btn-primary={filterCat === ''} on:click={() => filterCat = ''}>Toutes</button>
		{#each CATEGORIES_TICKET as c (c.value)}
			<button class="btn btn-sm" class:btn-primary={filterCat === c.value}
				on:click={() => filterCat = c.value}>{c.emoji} {c.label}</button>
		{/each}
	</span>
</div>

{#if loading}
	<p class="etat-chargement">Chargement…</p>
{:else if filtered.length === 0}
	<div class="empty-state">
		<h3>Aucune demande</h3>
		<p>Signalez un problème ou posez une question au conseil syndical.</p>
	</div>
{:else}
	<ListeTickets
		tickets={filtered}
		expandedIds={expandedTickets}
		{evolsMap}
		ticketEnEdition={editingTicket}
		ticketEnEvolution={showEvolForm}
		evolutionEnCours={evolSaving}
		{evolEnEdition}
		{evolCorrectionEnCours}
		peutAdministrer={$isAdmin}
		on:basculer={(e) => toggleTicket(e.detail)}
		on:evoluer_ouvrir={(e) => openEvolForm(e.detail)}
		on:modifier={(e) => openEditForm(e.detail)}
		on:supprimer={deleteTicket}
		on:evoluer={addEvolution}
		on:evol_modifier={(e) => (evolEnEdition = e.detail)}
		on:evol_corriger={corrigerEvolution}
		on:evol_supprimer={supprimerEvolution}
		on:modifie={ticketModifie}
		on:annuler={fermerFormulaires}
	/>
{/if}

<!--  Section Historique — les tickets clos depuis plus du délai de grâce.
      ⚠️ Ce mot désigne ici l'ARCHIVE d'une liste, et non le fil d'évolutions que
      le cadre #430 appelle « Historique ». Les deux acceptions coexistent aussi
      sur les Actualités : les départager est un renommage visible qui traverse
      deux menus, il se propose (R5) et ne se décide pas dans ce lot. -->
{#if historyTickets.length > 0}
	<div class="history-section">
		<button class="history-header" on:click={() => (historyExpanded = !historyExpanded)} aria-expanded={historyExpanded}>
			<span class="history-title">&#x1F4AD; Historique</span>
			<span class="history-count">{historyTickets.length}</span>
			<span class="history-chevron">{historyExpanded ? '▲' : '▼'}</span>
		</button>
		{#if historyExpanded}
			<div class="history-content">
				{#each historyByYear as [year, yearTickets] (year)}
					<div class="history-year">
						<button class="history-year-header" on:click|stopPropagation={() => basculerAnnee(year)}
							aria-expanded={expandedYears.has(year)}>
							<span class="history-year-label">{year}</span>
							<span class="history-count history-count-annee">{yearTickets.length}</span>
							<span class="history-chevron">{expandedYears.has(year) ? '▲' : '▼'}</span>
						</button>
						{#if expandedYears.has(year)}
							<ListeTickets
								tickets={yearTickets}
								archive
								expandedIds={expandedTickets}
								{evolsMap}
								ticketEnEdition={editingTicket}
								ticketEnEvolution={showEvolForm}
								evolutionEnCours={evolSaving}
								{evolEnEdition}
								{evolCorrectionEnCours}
								peutAdministrer={$isAdmin}
								on:basculer={(e) => toggleTicket(e.detail)}
								on:evoluer_ouvrir={(e) => openEvolForm(e.detail)}
								on:modifier={(e) => openEditForm(e.detail)}
								on:supprimer={deleteTicket}
								on:evoluer={addEvolution}
								on:evol_modifier={(e) => (evolEnEdition = e.detail)}
								on:evol_corriger={corrigerEvolution}
								on:evol_supprimer={supprimerEvolution}
								on:modifie={ticketModifie}
								on:annuler={fermerFormulaires}
							/>
						{/if}
					</div>
				{/each}
			</div>
		{/if}
	</div>
{/if}

<style>
	.etat-chargement { color: var(--color-text-muted); }

	/* Filtres (style identique à calendrier) */
	.filters { display: flex; gap: .4rem; flex-wrap: wrap; margin-bottom: 1.25rem; align-items: center; }
	.filter-group { display: flex; gap: .4rem; flex-wrap: wrap; }
	.filter-sep { width: 1px; height: 1.2rem; background: var(--color-border); margin: 0 .3rem; }

	/*  ⚠️ HÉRITÉ, ET SUSPECT. `app.css` définit déjà `.badge-orange` (#FDF3E0 /
	    #B07D1E) ; cette règle la réécrit en GLOBAL depuis une page, donc pour
	    tout l'onglet une fois le style de cette page chargé — le badge « ⚡ Urgente »
	    n'a pas la même teinte selon qu'on soit passé par cette page ou non. Elle est
	    conservée telle quelle : la retirer change ce que voit le résident, et cela se
	    constate à l'écran avant de se décider. Signalé dans le lot #431. */
	:global(.badge-orange) { background: #fef3c7; color: #92400e; }

	/*  Section historique. L'allure des cartes d'archive, elle, vit dans
	    `CarteTicket` : le `<style>` d'une page n'atteint pas le balisage d'un
	    composant enfant — c'est la panne des pastilles nues (v2.67.11). */
	.history-section { margin-top: 2rem; padding-top: 1.5rem; border-top: 2px solid var(--color-border); }
	.history-header { display: flex; align-items: center; gap: .5rem; width: 100%; background: none; border: none; padding: 0; cursor: pointer; font-size: 1rem; font-weight: 600; color: var(--color-text); text-align: left; }
	.history-header:hover { color: var(--color-primary); }
	.history-title { flex: 1; }
	.history-count { display: inline-flex; align-items: center; justify-content: center; background: var(--color-primary); color: white; font-size: .75rem; font-weight: 700; padding: .15rem .5rem; border-radius: 12px; min-width: 1.5rem; }
	.history-count-annee { font-size: .7rem; }
	.history-chevron { font-size: .8rem; color: var(--color-text-muted); flex-shrink: 0; transition: transform .2s; }
	.history-header[aria-expanded="true"] .history-chevron { transform: scaleY(-1); }
	.history-content { margin-top: 1rem; display: flex; flex-direction: column; gap: 0; }
	.history-year { margin-bottom: .5rem; }
	.history-year-header { display: flex; align-items: center; gap: .5rem; width: 100%; background: var(--color-bg); border: 1px solid var(--color-border); border-radius: var(--radius); padding: .5rem .75rem; cursor: pointer; font-size: .9rem; font-weight: 600; color: var(--color-text); }
	.history-year-header:hover { border-color: var(--color-primary); color: var(--color-primary); }
	.history-year-label { flex: 1; text-align: left; }
</style>
