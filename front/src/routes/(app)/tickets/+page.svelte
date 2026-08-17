<script lang="ts">
	import EntetePage from '$lib/components/EntetePage.svelte';
	import { onMount } from 'svelte';
	import { revelerCible } from '$lib/deepLink';
	import { isCS, isAdmin } from '$lib/stores/auth';
	import { tickets as ticketsApi, ApiError, type Ticket, type TicketEvolution } from '$lib/api';
	import { getPageConfig, configStore, siteNomStore, defautsDePage } from '$lib/stores/pageConfig';
	import { safeHtml, safeDescription } from '$lib/sanitize';
	import { toast } from '$lib/components/Toast.svelte';
	import { fmtDate, fmtDatetime, isNouveau } from '$lib/date';
	import { perimetreLabel, estPerimetreParDefaut } from '$lib/utils';
	import EvolForm from '$lib/components/EvolForm.svelte';
	import PiecesJointes from '$lib/components/PiecesJointes.svelte';
	import ApercuCarte from '$lib/components/ApercuCarte.svelte';
	import FormulaireTicket from '$lib/components/FormulaireTicket.svelte';
	import AvertissementUrgence from '$lib/components/AvertissementUrgence.svelte';
	import {
		STATUT_TICKET_BADGE as STATUT_BADGE,
		STATUT_TICKET_LABELS as STATUT_LABELS,
		STATUT_TICKET_OPTIONS as TICKET_STATUT_OPTIONS,
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

	// Expansion
	let expandedTickets = new Set<number>();
	let expandedEvols = new Set<number>();
	// Évolutions par ticket (chargées à la demande)
	let evolsMap: Record<number, TicketEvolution[]> = {};
	let evolsLoaded = new Set<number>();
	// Formulaire d'évolution
	let showEvolForm: number | null = null;
	let evolSaving = false;

	//  Badges, libellés et options du workflow viennent de `$lib/tickets` — la
	//  divergence que le commentaire d'ici signalait « sans la trancher » l'a été
	//  le 17/08/2026 (#415) : elle est réglée à la source, pas écran par écran.
	const CAT_ICON: Record<string, string> = {
		panne: '\u{1F6E0}️', nuisance: '\u{1F4E2}', question: '❓', urgence: '\u{1F6A8}', bug: '\u{1F41B}',
	};


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
					await toggleTicket(target.id);
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

	async function toggleTicket(id: number) {
		if (expandedTickets.has(id)) {
			expandedTickets.delete(id);
			expandedTickets = new Set(expandedTickets);
			showEvolForm = showEvolForm === id ? null : showEvolForm;
		} else {
			expandedTickets = new Set([id]);
			showEvolForm = null;
			if (!evolsLoaded.has(id)) await loadEvolutions(id);
		}
	}

	async function loadEvolutions(id: number) {
		try {
			evolsMap[id] = await ticketsApi.evolutions(id);
			evolsLoaded = new Set([...evolsLoaded, id]);
			evolsMap = { ...evolsMap };
		} catch { /* silencieux */ }
	}

	function openEvolForm(id: number) {
		//  Les champs du formulaire ne sont plus remis à zéro ici : `EvolForm` porte
		//  son propre état, et le `{#key showEvolForm}` du gabarit le remonte à neuf
		//  à chaque ouverture — y compris les pièces jointes déjà téléversées, qui
		//  ne doivent surtout pas se retrouver sur le ticket suivant.
		showEvolForm = id;
		expandedTickets = new Set([id]);
	}

	//  Reçoit l'événement `submit` d'`EvolForm` — même contrat que la fiche détail
	//  (`tickets/[id]`), y compris `fichiers_urls` : c'est ce qui apporte les pièces
	//  jointes à une réaction depuis cette page, où le formulaire était réécrit à la
	//  main et n'en proposait aucune.
	async function addEvolFromForm(t: Ticket, e: CustomEvent) {
		const data = e.detail;
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
				ticketList = ticketList.map(x => x.id === t.id ? { ...x, statut: data.nouveau_statut } : x);
			}
			await loadEvolutions(t.id);
			showEvolForm = null;
			toast('success', data.type === 'etat' ? 'Statut mis à jour' : 'Commentaire ajouté');
		} catch (e2) {
			toast('error', e2 instanceof ApiError ? e2.message : 'Erreur');
		} finally { evolSaving = false; }
	}

	async function deleteTicket(t: Ticket) {
		if (!confirm(`Supprimer définitivement le ticket #${t.numero} ? Cette action est irréversible.`)) return;
		try {
			await ticketsApi.delete(t.id);
			ticketList = ticketList.filter(x => x.id !== t.id);
			toast('success', 'Ticket supprimé');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}

	// ── Édition admin ──
	//  Le formulaire est celui de la CRÉATION, paramétré par le ticket à modifier
	//  (`FormulaireTicket ticket={t}`). Il était réécrit à la main ici : quatre
	//  champs bruts, sans section nommée, avec « Périmètre » écrit deux fois et des
	//  `style=` en ligne recomposant `.field` (#425). Ne restent dans la page que
	//  l'ouverture, la fermeture, et ce qu'il faut rafraîchir après coup.
	let editingTicket: number | null = null;

	function openEditForm(id: number) {
		editingTicket = id;
		expandedTickets = new Set([id]);
		showEvolForm = null;
	}

	//  Le PATCH inscrit une évolution « Modification : … » dans le fil : sans ce
	//  rechargement, la carte affiche le ticket modifié au-dessus d'un historique
	//  qui n'en dit rien.
	async function ticketModifie(e: CustomEvent<Ticket>) {
		const maj = e.detail;
		ticketList = ticketList.map(x => x.id === maj.id ? { ...x, ...maj } : x);
		await loadEvolutions(maj.id);
		editingTicket = null;
	}
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<!--  `alignerSaisie` quand le formulaire est ouvert : sans lui, « ✕ Annuler » se
      pose au bord DROIT DE LA PAGE, à plusieurs centaines de pixels de la boîte
      qu'il annule, laquelle s'arrête à 720 px (#367). -->
<EntetePage titre={_pc.titre} icone={_pc.icone || 'message-square-text'} alignerSaisie={showForm}>
	<button class="btn btn-primary page-header-btn" on:click={() => (showForm = !showForm)}>
		{showForm ? '✕ Annuler' : '+ Nouveau ticket'}
	</button>
</EntetePage>
<div class="page-subtitle">{@html safeHtml(_pc.descriptif)}</div>

{#if showForm}
	<FormulaireTicket on:cree={ticketCree} />
{/if}

<AvertissementUrgence />

<div class="filters">
	<span class="filter-group">
		<button class="btn btn-sm" class:btn-primary={filterStatut === ''} on:click={() => filterStatut = ''}>Tous</button>
		{#each STATUTS_TICKET_FILTRE as s}
			<button class="btn btn-sm" class:btn-primary={filterStatut === s.value}
				on:click={() => filterStatut = s.value}>{s.label}</button>
		{/each}
	</span>
	<span class="filter-sep"></span>
	<span class="filter-group">
		<button class="btn btn-sm" class:btn-primary={filterCat === ''} on:click={() => filterCat = ''}>Toutes</button>
		<button class="btn btn-sm" class:btn-primary={filterCat === 'panne'} on:click={() => filterCat = 'panne'}>&#x1F6E0;️ Panne</button>
		<button class="btn btn-sm" class:btn-primary={filterCat === 'nuisance'} on:click={() => filterCat = 'nuisance'}>&#x1F4E2; Nuisance</button>
		<button class="btn btn-sm" class:btn-primary={filterCat === 'question'} on:click={() => filterCat = 'question'}>❓ Question</button>
		<button class="btn btn-sm" class:btn-primary={filterCat === 'urgence'} on:click={() => filterCat = 'urgence'}>&#x1F6A8; Urgence</button>
		<button class="btn btn-sm" class:btn-primary={filterCat === 'bug'} on:click={() => filterCat = 'bug'}>&#x1F41B; Bug</button>
	</span>
</div>

{#if loading}
	<p style="color:var(--color-text-muted)">Chargement…</p>
{:else if filtered.length === 0}
	<div class="empty-state">
		<h3>Aucune demande</h3>
		<p>Signalez un problème ou posez une question au conseil syndical.</p>
	</div>
{:else}
	{#each filtered as t (t.id)}
		{@const expanded = expandedTickets.has(t.id)}
		{@const evols = evolsMap[t.id] ?? []}
		<div id="ticket-{t.id}" class="carte-liste tk-expand" class:expanded class:urgent={t.categorie === 'urgence'}
			role="button" tabindex="0"
			on:click={() => toggleTicket(t.id)}
			on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && toggleTicket(t.id)}>

			<div class="tk-row">
				<div class="tk-row-inner">
					<span class="tk-cat" title={t.categorie}>{CAT_ICON[t.categorie] ?? '\u{1F4CB}'}</span>
					<span class="tk-row-titre">{t.titre}
					{#if isNouveau(t.cree_le, t.mis_a_jour_le)}<span class="badge badge-gray" style="margin-left:.5em;font-size:.82em;font-weight:500;vertical-align:middle">NEW</span>{/if}
					</span>
					<span class="badge {STATUT_BADGE[t.statut] ?? 'badge-gray'}" style="flex-shrink:0">{STATUT_LABELS[t.statut] ?? t.statut}</span>
					{#if t.priorite === 'haute'}
						<span class="badge badge-orange" style="flex-shrink:0">⚡ Urgente</span>
					{/if}
				</div>
				<div class="tk-row-right">
					<span class="tk-row-date">{fmtDate(t.mis_a_jour_le ?? t.cree_le)}</span>
					{#if $isCS}
						<button class="btn-icon" aria-label="Commenter / changer état" title="Commenter / état"
							on:click|stopPropagation={() => openEvolForm(t.id)}>&#x1F4AC;</button>
					{/if}
					{#if $isAdmin}						<button class="btn-icon" aria-label="Modifier" title="Modifier le ticket"
							on:click|stopPropagation={() => openEditForm(t.id)}>✏️</button>						<button class="btn-icon-danger" aria-label="Supprimer" title="Supprimer définitivement"
							on:click|stopPropagation={() => deleteTicket(t)}>&#x1F5D1;️</button>
					{/if}
					<span class="chevron" class:open={expanded}>›</span>
				</div>
			</div>

			{#if !expanded}
				<ApercuCarte contenu={t.description} photos={t.photos_urls ?? []} />
			{/if}

			{#if expanded}
				<div class="tk-body" on:click|stopPropagation on:keydown|stopPropagation>
					{#if editingTicket === t.id}
						<!--  Édition du ticket — LE MÊME formulaire que la création, paramétré
						      par le ticket. `{#key}` le remonte à neuf d'un ticket à l'autre :
						      ses valeurs initiales sont lues à la construction, comme pour
						      `EvolForm` juste en dessous. -->
						<div class="evol-form">
							{#key editingTicket}
								<FormulaireTicket ticket={t}
									on:modifie={ticketModifie}
									on:annule={() => (editingTicket = null)}
								/>
							{/key}
						</div>
					{:else if showEvolForm === t.id}
						<!-- Formulaire d'évolution — composant partagé `EvolForm` -->
						<div class="evol-form">
							{#key showEvolForm}
								<EvolForm idPrefixe="tk-evol-{t.id}"
									statutOptions={TICKET_STATUT_OPTIONS}
									statutLabels={STATUT_LABELS}
									currentStatut={t.statut}
									showNotifs={$isCS || $isAdmin}
									showFiles={true}
									separatePhotosAndDocs={true}
									saving={evolSaving}
									on:submit={(e) => addEvolFromForm(t, e)}
									on:cancel={() => (showEvolForm = null)}
								/>
							{/key}
						</div>
					{:else}
						<!-- Corps normal -->
						<div class="rich-content" style="font-size:.875rem;line-height:1.6;margin-bottom:.5rem">{@html safeDescription(t.description)}</div>
						{#if t.photos_urls?.length}
							<PiecesJointes urls={t.photos_urls} format="grand" />
						{/if}
						{#if !estPerimetreParDefaut(t.perimetre_cible)}
							<p style="font-size:.8rem;color:var(--color-text-muted);margin:.25rem 0 .5rem">🔹 {perimetreLabel(t.perimetre_cible)}</p>
						{/if}
						<small style="color:var(--color-text-muted);font-size:.78rem">
							Créé le {fmtDate(t.cree_le)}
							<span style="font-family:monospace"> · #{t.numero}</span>
						</small>

						<!-- Fil de suivi -->
						{#if evols.length > 0}
							{@const evolsSorted = [...evols].sort((a, b) => new Date(b.cree_le).getTime() - new Date(a.cree_le).getTime())}
							{@const evolCompact = evolsSorted.length > 7 && !expandedEvols.has(t.id)}
							{@const evolsVisible = evolCompact ? evolsSorted.slice(0, 5) : evolsSorted}
							<div class="evol-list">
								{#each evolsVisible as evol, i (evol.id)}
									{#if i > 0}<hr class="evol-sep" />{/if}
									<div class="evol-item evol-{evol.type}">
										<span class="evol-icon">
											{#if evol.type === 'etat'}&#x1F504;{:else if evol.type === 'reponse'}&#x1F4AC;{:else}&#x1F4DD;{/if}
										</span>
										<div class="evol-body">
											<span class="evol-meta">{fmtDatetime(evol.cree_le)}{#if evol.auteur_nom} · {evol.auteur_nom}{/if}</span>
											{#if evol.type === 'etat'}
												<span class="evol-text">
													Statut : <strong>{STATUT_LABELS[evol.ancien_statut ?? ''] || 'Aucun'}</strong> → <strong>{STATUT_LABELS[evol.nouveau_statut ?? ''] || evol.nouveau_statut}</strong>
												</span>
											{#if evol.contenu}
												<div class="evol-content rich-content">{@html safeDescription(evol.contenu)}</div>
											{/if}
										{:else if evol.type === 'reponse' || evol.type === 'commentaire'}
											{#if evol.contenu}
												<div class="evol-content rich-content">{@html safeDescription(evol.contenu)}</div>
											{/if}
											{/if}
											<!-- Pièces jointes de l'évolution — même rendu que la fiche détail -->
											{#if evol.fichiers_urls?.length}
												<div class="evol-pj" style="margin-top:.4rem">
													<PiecesJointes urls={evol.fichiers_urls} size={72} compact />
												</div>
											{/if}
										</div>
									</div>
								{/each}
								{#if evolCompact}
									<hr class="evol-sep" />
									<button class="evol-more" on:click|stopPropagation={() => { expandedEvols.add(t.id); expandedEvols = expandedEvols; }}>
										Voir les {evolsSorted.length - 5} entrées plus anciennes
									</button>
								{/if}
							</div>
						{/if}
					{/if}
				</div>
			{/if}
		</div>
	{/each}
{/if}

<!-- Section Historique -->
{#if historyTickets.length > 0}
		<div class="history-section">
			<button class="history-header" on:click={() => (historyExpanded = !historyExpanded)} aria-expanded={historyExpanded}>
				<span class="history-title">&#x1F4AD; Historique</span>
				<span class="history-count">{historyTickets.length}</span>
				<span class="history-chevron">{historyExpanded ? '▲' : '▼'}</span>
			</button>
			{#if historyExpanded}
				<div class="history-content">
					{#each historyByYear as [year, yearTickets]}
						<div class="history-year">
							<button class="history-year-header" on:click|stopPropagation={() => { if (expandedYears.has(year)) { expandedYears.delete(year); } else { expandedYears.add(year); } expandedYears = expandedYears; }} aria-expanded={expandedYears.has(year)}>
								<span class="history-year-label">{year}</span>
								<span class="history-count" style="font-size:.7rem">{yearTickets.length}</span>
								<span class="history-chevron">{expandedYears.has(year) ? '▲' : '▼'}</span>
							</button>
							{#if expandedYears.has(year)}
								{#each yearTickets as t (t.id)}
									{@const expanded = expandedTickets.has(t.id)}
									{@const evols = evolsMap[t.id] ?? []}
						<div class="tk-expand history-item" class:expanded class:urgent={t.categorie === 'urgence'}
							role="button" tabindex="0"
							on:click={() => toggleTicket(t.id)}
							on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && toggleTicket(t.id)}>

							<div class="tk-row">
								<div class="tk-row-inner">
									<span class="tk-cat" title={t.categorie}>{CAT_ICON[t.categorie] ?? '\u{1F4CB}'}</span>
									<span class="tk-row-titre">{t.titre}</span>
									<span class="badge {STATUT_BADGE[t.statut] ?? 'badge-gray'}" style="flex-shrink:0">{STATUT_LABELS[t.statut] ?? t.statut}</span>
									{#if t.priorite === 'haute'}
										<span class="badge badge-orange" style="flex-shrink:0">⚡ Urgente</span>
									{/if}
								</div>
								<div class="tk-row-right">
									<span class="tk-row-date">{fmtDate(t.mis_a_jour_le ?? t.cree_le)}</span>
									{#if $isCS}
										<button class="btn-icon" aria-label="Commenter / changer état" title="Commenter / état"
											on:click|stopPropagation={() => openEvolForm(t.id)}>&#x1F4AC;</button>
									{/if}
									{#if $isAdmin}
										<button class="btn-icon-danger" aria-label="Supprimer" title="Supprimer définitivement"
											on:click|stopPropagation={() => deleteTicket(t)}>&#x1F5D1;️</button>
									{/if}
									<span class="chevron" class:open={expanded}>›</span>
								</div>
							</div>

							{#if !expanded}
								<ApercuCarte contenu={t.description} photos={t.photos_urls ?? []} />
							{/if}

							{#if expanded}
								<div class="tk-body" on:click|stopPropagation on:keydown|stopPropagation>
									{#if showEvolForm === t.id}
										<!-- Formulaire d'évolution — composant partagé `EvolForm` -->
										<div class="evol-form">
											{#key showEvolForm}
												<EvolForm idPrefixe="tk-arch-evol-{t.id}"
													statutOptions={TICKET_STATUT_OPTIONS}
													statutLabels={STATUT_LABELS}
													currentStatut={t.statut}
													showNotifs={$isCS || $isAdmin}
													showFiles={true}
													separatePhotosAndDocs={true}
													saving={evolSaving}
													on:submit={(e) => addEvolFromForm(t, e)}
													on:cancel={() => (showEvolForm = null)}
												/>
											{/key}
										</div>
									{:else}
										<!-- Corps normal -->
										<div class="rich-content" style="font-size:.875rem;line-height:1.6;margin-bottom:.5rem">{@html safeDescription(t.description)}</div>
										{#if t.photos_urls?.length}
							<PiecesJointes urls={t.photos_urls} format="grand" />
						{/if}
										{#if !estPerimetreParDefaut(t.perimetre_cible)}
											<p style="font-size:.8rem;color:var(--color-text-muted);margin:.25rem 0 .5rem">🔹 {perimetreLabel(t.perimetre_cible)}</p>
										{/if}
										<small style="color:var(--color-text-muted);font-size:.78rem">
											Créé le {fmtDate(t.cree_le)}
											<span style="font-family:monospace"> · #{t.numero}</span>
										</small>

										<!-- Fil de suivi -->
										{#if evols.length > 0}
											{@const evolsSorted = [...evols].sort((a, b) => new Date(b.cree_le).getTime() - new Date(a.cree_le).getTime())}
											{@const evolCompact = evolsSorted.length > 7 && !expandedEvols.has(t.id)}
											{@const evolsVisible = evolCompact ? evolsSorted.slice(0, 5) : evolsSorted}
											<div class="evol-list">
												{#each evolsVisible as evol, i (evol.id)}
													{#if i > 0}<hr class="evol-sep" />{/if}
													<div class="evol-item evol-{evol.type}">
														<span class="evol-icon">
															{#if evol.type === 'etat'}&#x1F504;{:else if evol.type === 'reponse'}&#x1F4AC;{:else}&#x1F4DD;{/if}
														</span>
														<div class="evol-body">
															<span class="evol-meta">{fmtDatetime(evol.cree_le)}{#if evol.auteur_nom} · {evol.auteur_nom}{/if}</span>
															{#if evol.type === 'etat'}
																<span class="evol-text">
																	Statut : <strong>{STATUT_LABELS[evol.ancien_statut ?? ''] || 'Aucun'}</strong> → <strong>{STATUT_LABELS[evol.nouveau_statut ?? ''] || evol.nouveau_statut}</strong>
																</span>
															{#if evol.contenu}
																<div class="evol-content rich-content">{@html safeDescription(evol.contenu)}</div>
															{/if}
														{:else if evol.type === 'reponse' || evol.type === 'commentaire'}
															{#if evol.contenu}
																<div class="evol-content rich-content">{@html safeDescription(evol.contenu)}</div>
															{/if}
														{/if}
														<!-- Pièces jointes de l'évolution — même rendu que la fiche détail -->
														{#if evol.fichiers_urls?.length}
															<div class="evol-pj" style="margin-top:.4rem">
																<PiecesJointes urls={evol.fichiers_urls} size={72} compact />
															</div>
														{/if}
														</div>
													</div>
												{/each}
												{#if evolCompact}
													<hr class="evol-sep" />
													<button class="evol-more" on:click|stopPropagation={() => { expandedEvols.add(t.id); expandedEvols = expandedEvols; }}>
														Voir les {evolsSorted.length - 5} entrées plus anciennes
													</button>
												{/if}
											</div>
										{/if}
									{/if}
								</div>
							{/if}
						</div>
					{/each}
							{/if}
						</div>
					{/each}
				</div>
			{/if}
		</div>
	{/if}

<style>

	/* Filtres (style identique à calendrier) */
	.filters { display: flex; gap: .4rem; flex-wrap: wrap; margin-bottom: 1.25rem; align-items: center; }
	.filter-group { display: flex; gap: .4rem; flex-wrap: wrap; }
	.filter-sep { width: 1px; height: 1.2rem; background: var(--color-border); margin: 0 .3rem; }

	/* Carte ticket expansible */
	/*  Conteneur, survol, urgence : `.carte-liste` (app.css). Ne reste ici que
	    le débordement visible, requis par le badge d'épingle qui sort du cadre. */
	.tk-row:hover { background: var(--color-bg); }
	.tk-row-inner { display: flex; align-items: center; gap: .4rem; flex: 1; min-width: 0; overflow: hidden; }
	.tk-cat { flex-shrink: 0; font-size: .95rem; }
	.tk-row-titre { font-size: .9rem; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.tk-row-right { display: flex; align-items: center; gap: .3rem; flex-shrink: 0; }
	.tk-row-date { font-size: .78rem; color: var(--color-text-muted); margin-right: .3rem; white-space: nowrap; }

	.tk-body { padding: .75rem 1rem 1rem; border-top: 1px solid var(--color-border); }
	.tk-body :global(p) { margin: 0 0 .5em; }


	/* Évolutions */
	.evol-list { margin-top: .9rem; border: 1px solid var(--color-border); border-radius: 6px; overflow: hidden; }
	.evol-sep { margin: 0; border: none; border-top: 1px solid var(--color-border); }
	.evol-item { display: flex; gap: .5rem; padding: .5rem .75rem; font-size: .82rem; }
	.evol-icon { flex-shrink: 0; font-size: .9rem; margin-top: .1rem; }
	.evol-body { display: flex; flex-direction: column; gap: .15rem; }
	.evol-meta { font-size: .75rem; color: var(--color-text-muted); }
	.evol-text { color: var(--color-text); line-height: 1.5; }
	.evol-content { margin-top: .2rem; color: var(--color-text); line-height: 1.6; font-size: .85rem; }
	.evol-content :global(p) { margin: 0 0 .3em; }
	.evol-etat { background: #f0f9ff; }
	.evol-reponse { background: #f0fdf4; }
	.evol-commentaire { background: #fafafa; }
	.evol-form { padding: .25rem 0 .25rem; }
	.evol-more { width: 100%; background: none; border: none; padding: .45rem; font-size: .8rem; color: var(--color-primary); cursor: pointer; text-align: center; }
	.evol-more:hover { background: var(--color-bg); }

	/*  `.form-actions` n'est plus redéfini ici : la seule rangée de boutons de la
	    page vivait dans le formulaire d'édition écrit à la main, parti dans
	    `FormulaireTicket` (#425). app.css porte la règle pour tout le site. */
	.pill { padding: .3rem .85rem; border-radius: 999px; border: 1.5px solid var(--color-border); background: var(--color-bg); font-size: .85rem; cursor: pointer; transition: background .15s, border-color .15s, color .15s; white-space: nowrap; line-height: 1.6; }
	.pill:hover { border-color: var(--color-primary); color: var(--color-primary); }
	.pill-active { background: var(--color-primary); border-color: var(--color-primary); color: #fff; }

	:global(.badge-orange) { background: #fef3c7; color: #92400e; }

	/* Section historique */
	.history-section { margin-top: 2rem; padding-top: 1.5rem; border-top: 2px solid var(--color-border); }
	.history-header { display: flex; align-items: center; gap: .5rem; width: 100%; background: none; border: none; padding: 0; cursor: pointer; font-size: 1rem; font-weight: 600; color: var(--color-text); text-align: left; }
	.history-header:hover { color: var(--color-primary); }
	.history-title { flex: 1; }
	.history-count { display: inline-flex; align-items: center; justify-content: center; background: var(--color-primary); color: white; font-size: .75rem; font-weight: 700; padding: .15rem .5rem; border-radius: 12px; min-width: 1.5rem; }
	.history-chevron { font-size: .8rem; color: var(--color-text-muted); flex-shrink: 0; transition: transform .2s; }
	.history-header[aria-expanded="true"] .history-chevron { transform: scaleY(-1); }
	.history-content { margin-top: 1rem; display: flex; flex-direction: column; gap: 0; }
	.history-year { margin-bottom: .5rem; }
	.history-year-header { display: flex; align-items: center; gap: .5rem; width: 100%; background: var(--color-bg); border: 1px solid var(--color-border); border-radius: var(--radius); padding: .5rem .75rem; cursor: pointer; font-size: .9rem; font-weight: 600; color: var(--color-text); }
	.history-year-header:hover { border-color: var(--color-primary); color: var(--color-primary); }
	.history-year-label { flex: 1; text-align: left; }
	.history-item { border-left: 4px solid var(--color-border); border-radius: var(--radius); background: var(--color-surface); opacity: .8; transition: opacity .15s, border-left-color .15s; }
	.history-item:hover { opacity: 1; }
	.history-item.expanded { opacity: 1; }

	/* Avertissement urgence */
</style>
