<script lang="ts">
	import EntetePage from '$lib/components/EntetePage.svelte';
	import { onMount } from 'svelte';
	import { revelerCible } from '$lib/deepLink';
	import { isAdmin } from '$lib/stores/auth';
	import { tickets as ticketsApi, ApiError, type Ticket, type TicketEvolution } from '$lib/api';
	import { getPageConfig, configStore, siteNomStore, defautsDePage } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';
	import { toast } from '$lib/components/Toast.svelte';
	import ListeTickets from '$lib/components/ListeTickets.svelte';
	import ArchivesParAnnee from '$lib/components/ArchivesParAnnee.svelte';
	import type { ChargeUtileEvolution } from '$lib/evolutions';
	import FormulaireTicket from '$lib/components/FormulaireTicket.svelte';
	import AvertissementUrgence from '$lib/components/AvertissementUrgence.svelte';
	import { CATEGORIES_TICKET, statutsPresents, estTicketClos } from '$lib/tickets';

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
				const target = ticketList.find((t) => t.numero === openNum);
				if (target) {
					if (estArchive(target)) {
						historyExpanded = true;
						//  On DÉSIGNE l'année ; le composant l'ouvre. Cette page posait
						//  auparavant l'état interne du groupement, ce qui l'obligeait
						//  à en porter sa propre copie.
						anneeVisee = new Date(target.mis_a_jour_le ?? target.cree_le).getFullYear();
					}
					await toggleTicket(target);
					revelerCible(`ticket-${target.id}`);
				}
			}
		} finally {
			loading = false;
		}
	});

	// Délai de grâce : un ticket clôturé reste visible dans la liste principale
	// pendant 7 jours après sa clôture, puis bascule dans l'Historique.
	const HISTORIQUE_DELAI_MS = 7 * 24 * 60 * 60 * 1000;
	function estArchive(t: { statut: string; mis_a_jour_le?: string; cree_le: string }): boolean {
		if (!estTicketClos(t.statut)) return false;
		return Date.now() - new Date(t.mis_a_jour_le ?? t.cree_le).getTime() > HISTORIQUE_DELAI_MS;
	}

	//  Ce que la liste principale peut montrer, AVANT le filtre d'état : c'est
	//  cet ensemble-là qui donne les boutons du filtre. Le calculer après
	//  n'en laisserait qu'un seul, celui qu'on vient de choisir.
	$: affichables = ticketList.filter((t) => !estArchive(t));
	$: optionsStatut = statutsPresents(affichables);
	//  ⚠️ Un filtre retenu sur un état qui vient de disparaître de la liste — le
	//  dernier ticket résolu bascule dans l'Historique — laisserait un écran vide
	//  ET plus aucun bouton pour en sortir. On retombe alors sur « Tous ».
	$: if (filterStatut && !optionsStatut.some((o) => o.value === filterStatut)) filterStatut = '';

	$: filtered = affichables.filter((t) => {
		if (filterStatut && t.statut !== filterStatut) return false;
		if (filterCat && t.categorie !== filterCat) return false;
		return true;
	});

	// Historique : tickets clôturés depuis plus de 7 jours, limité à 3 ans, groupés par année décroissante
	const THREE_YEARS_AGO = new Date();
	THREE_YEARS_AGO.setFullYear(THREE_YEARS_AGO.getFullYear() - 3);

	$: historyTickets = ticketList
		.filter((t) => estArchive(t) && new Date(t.mis_a_jour_le ?? t.cree_le) >= THREE_YEARS_AGO)
		.sort(
			(a, b) =>
				new Date(b.mis_a_jour_le ?? b.cree_le).getTime() -
				new Date(a.mis_a_jour_le ?? a.cree_le).getTime(),
		);

	//  ⚠️ Le groupement par année vivait ici — troisième copie du même bloc,
	//  avec l'Espace CS et `ArchivesParAnnee` lui-même. Il est parti dans le
	//  composant ; ce qui reste est le FILTRE, propre à cet écran.
	let historyExpanded = false;
	/**  L'année à ouvrir, désignée par un lien profond `?open=TK-…`. C'est la
	 *   SEULE chose que cette page ait besoin de dire au groupement — et la
	 *   capacité qui lui manquait pour adopter le composant (#516). */
	let anneeVisee: number | null = null;

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
		} catch {
			/* silencieux */
		}
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

	//  🔴 Ce type était RÉÉCRIT ici, et il lui manquait `perimetre_cible` — alors
	//  que son commentaire affirmait « même contrat que la fiche détail ». Deux
	//  contrats d'accord sur le papier et divergents dans les faits : c'est le
	//  défaut de #415 (statuts) et #413 (champs), sur un troisième objet (#529).
	//  Il vit désormais dans `$lib/evolutions`, avec le reste du vocabulaire.

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
				//  🔴 La correction du périmètre part AUSSI (01/09/2026) : le
				//  sélecteur s'affiche désormais en correction, et un champ affiché
				//  qui ne part pas est le défaut de la veille, rejoué.
				perimetre_cible: e.detail.data.perimetre_cible,
			});
			await loadEvolutions(t.id);
			evolEnEdition = null;
			toast('success', 'Entrée corrigée');
		} catch (e2) {
			toast('error', e2 instanceof ApiError ? e2.message : 'Erreur');
		} finally {
			evolCorrectionEnCours = false;
		}
	}

	async function addEvolution(e: CustomEvent<{ ticket: Ticket; data: unknown }>) {
		const t = e.detail.ticket;
		const data = e.detail.data as ChargeUtileEvolution;
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
				envoyer_auteur: data.envoyer_auteur || undefined,
				//  🔴 MANQUAIT jusqu'au 20/08/2026, et cela se voyait à l'écran :
				//  `CarteTicket` propose bien la section Périmètre
				//  (`avecPerimetre`), `EvolForm` la collecte et l'émet — et cette
				//  ligne-ci la jetait avant l'appel. Le périmètre resserré ne
				//  parvenait donc JAMAIS au serveur depuis la liste des tickets,
				//  alors qu'il y parvient depuis la fiche, qui relaie la charge
				//  utile entière (`HistoriqueTicket`).
				//
				//  ⚠️ Le défaut ne lève rien : le formulaire dit avoir enregistré,
				//  le serveur enregistre une évolution valide, et seul le périmètre
				//  affiché ensuite trahit la perte. Signalé à l'écran (#529).
				perimetre_cible: data.perimetre_cible,
			});
			if (data.type === 'etat') {
				ticketList = ticketList.map((x) =>
					x.id === t.id ? { ...x, statut: data.nouveau_statut ?? x.statut } : x,
				);
			}
			await loadEvolutions(t.id);
			showEvolForm = null;
			toast('success', data.type === 'etat' ? 'Statut mis à jour' : 'Commentaire ajouté');
		} catch (e2) {
			toast('error', e2 instanceof ApiError ? e2.message : 'Erreur');
		} finally {
			evolSaving = false;
		}
	}

	async function deleteTicket(e: CustomEvent<Ticket>) {
		const t = e.detail;
		if (
			!confirm(`Supprimer définitivement le ticket #${t.numero} ? Cette action est irréversible.`)
		)
			return;
		try {
			await ticketsApi.delete(t.id);
			ticketList = ticketList.filter((x) => x.id !== t.id);
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
		ticketList = ticketList.map((x) => (x.id === maj.id ? { ...x, ...maj } : x));
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
		<button
			class="btn btn-sm"
			class:btn-primary={filterStatut === ''}
			on:click={() => (filterStatut = '')}>Tous</button
		>
		{#each optionsStatut as s (s.value)}
			<button
				class="btn btn-sm"
				class:btn-primary={filterStatut === s.value}
				on:click={() => (filterStatut = s.value)}>{s.label}</button
			>
		{/each}
	</span>
	<span class="filter-sep"></span>
	<span class="filter-group">
		<button
			class="btn btn-sm"
			class:btn-primary={filterCat === ''}
			on:click={() => (filterCat = '')}>Toutes</button
		>
		{#each CATEGORIES_TICKET as c (c.value)}
			<button
				class="btn btn-sm"
				class:btn-primary={filterCat === c.value}
				on:click={() => (filterCat = c.value)}>{c.emoji} {c.label}</button
			>
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
		on:evol_annuler={() => (evolEnEdition = null)}
		on:evol_corriger={corrigerEvolution}
		on:evol_supprimer={supprimerEvolution}
		on:modifie={ticketModifie}
		on:annuler={fermerFormulaires}
	/>
{/if}

<!--  Section ARCHIVES — les tickets clos depuis plus du délai de grâce.
      ⚠️ Elle s'appelait « Historique », et ce mot est réservé au FIL d'évolutions
      d'un objet (cadre #430). Les deux acceptions coexistaient ici même, sur le
      même écran : le fil d'un ticket et l'archive de la liste. Départagé le
      20/08/2026 (#516).

      Le bandeau vient de `SectionRepliee`, comme les Actualités, les Petites
      annonces et le tableau de bord — il était réécrit ici pour la troisième
      fois, et c'est l'audit de factorisation qui l'a dit.

      ⚠️ Le groupement par ANNÉE, lui, reste écrit ici : cet écran ouvre une année
      précise sur lien profond (l. 69-71), ce qu'`ArchivesParAnnee` ne sait pas
      encore porter. Unifier les deux demande d'exposer l'année ouverte — ça se
      fait, mais pas en même temps qu'un renommage. Suivi en #516. -->
{#if historyTickets.length > 0}
	<div>
		<ArchivesParAnnee
			items={historyTickets}
			dateDe={(t) => t.mis_a_jour_le ?? t.cree_le}
			compte={historyTickets.length}
			charge
			anneeOuverte={anneeVisee}
			bind:ouvert={historyExpanded}
			let:objet={ticketArchive}
		>
			<ListeTickets
				tickets={[ticketArchive]}
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
				on:evol_annuler={() => (evolEnEdition = null)}
				on:evol_corriger={corrigerEvolution}
				on:evol_supprimer={supprimerEvolution}
				on:modifie={ticketModifie}
				on:annuler={fermerFormulaires}
			/>
		</ArchivesParAnnee>
	</div>
{/if}

<style>
	.etat-chargement {
		color: var(--color-text-muted);
	}

	/* Filtres (style identique à calendrier) */
	/*  `.filters` vient d'`app.css` — sa marge basse et son `align-items` y sont
	    remontés (#446). Ne restent ici que le groupe et le séparateur, qui n'ont
	    pas d'équivalent ailleurs. */
	.filter-group {
		display: flex;
		gap: 0.4rem;
		flex-wrap: wrap;
	}
	.filter-sep {
		width: 1px;
		height: 1.2rem;
		background: var(--color-border);
		margin: 0 0.3rem;
	}

	/*  Le badge « ⚡ Urgente » réécrivait ici `.badge-orange` en `:global(…)`, donc
	    pour tout le site une fois la feuille de cette page chargée : sa teinte
	    dépendait des écrans déjà visités. Le diagnostic était écrit ici depuis #431
	    et la règle est quand même restée — un commentaire n'est pas un garde-fou.
	    Retiré (#562) ; la charte de `styles/composants.css` s'applique désormais
	    seule, et `lint:classes-nues` refuse le retour de cette forme. */

	/*  Section historique. L'allure des cartes d'archive, elle, vit dans
	    `CarteTicket` : le `<style>` d'une page n'atteint pas le balisage d'un
	    composant enfant — c'est la panne des pastilles nues (v2.67.11). */
	/*  🔴 Douze règles sont parties avec `ArchivesParAnnee` : le bandeau, son
	    compteur, son chevron, et tout le groupement par année. Elles décrivaient
	    un balisage que cette page ne rend plus — et les laisser aurait entretenu
	    l'illusion qu'on règle ici l'aspect des Archives (#516).

	    Ne reste que l'encadré de la section, seul balisage encore rendu ici. */
	/*  Le séparateur est celui de `SectionRepliee` — il était dessiné ici AUSSI,
	    d'où deux traits (#536). Le pourquoi est dans le composant. */
</style>
