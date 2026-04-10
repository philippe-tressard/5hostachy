<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import { onMount } from 'svelte';
	import { isCS, isAdmin } from '$lib/stores/auth';
	import { tickets as ticketsApi, ApiError, type Ticket, type TicketEvolution } from '$lib/api';
	import { getPageConfig, configStore, siteNomStore } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';
	import { toast } from '$lib/components/Toast.svelte';
	import { fmtDate, fmtDatetime } from '$lib/date';

$: _pc = getPageConfig($configStore, 'mes-demandes', { titre: 'Mes Tickets', navLabel: 'Tickets', icone: 'message-square-text', descriptif: "Signalez un problème, une nuisance ou posez une question au conseil syndical. Suivez l’avancement de vos tickets." });
	$: _siteNom = $siteNomStore;

	let ticketList: Ticket[] = [];
	let loading = true;
	let filterStatut = '';
	let disclaimerOpen = false;
	let filterCat = '';

	// Expansion
	let expandedTickets = new Set<number>();
	let expandedEvols = new Set<number>();
	// Évolutions par ticket (chargées à la demande)
	let evolsMap: Record<number, TicketEvolution[]> = {};
	let evolsLoaded = new Set<number>();
	// Formulaire d'évolution
	let showEvolForm: number | null = null;
	let evolType: 'commentaire' | 'etat' = 'commentaire';
	let evolContenu = '';
	let evolNouveauStatut = '';
	let evolSaving = false;

	const STATUT_BADGE: Record<string, string> = {
		ouvert: 'badge-blue', en_cours: 'badge-orange', résolu: 'badge-green', annulé: 'badge-gray',
	};
	const STATUT_LABELS: Record<string, string> = {
		ouvert: 'Ouvert', en_cours: 'En cours', résolu: 'Résolu', annulé: 'Annulé',
	};
	const CAT_ICON: Record<string, string> = {
		panne: '\u{1F6E0}️', nuisance: '\u{1F4E2}', question: '❓', urgence: '\u{1F6A8}', bug: '\u{1F41B}',
	};

	function renderDesc(c: string) {
		const t = c.trimStart();
		return safeHtml(t.startsWith('<') ? c : `<p>${c.replace(/\n/g, '<br>')}</p>`);
	}

	onMount(async () => {
		try { ticketList = await ticketsApi.list(); }
		finally { loading = false; }
	});

	$: filtered = ticketList.filter((t) => {
		if (['résolu', 'annulé', 'fermé'].includes(t.statut)) return false;
		if (filterStatut && t.statut !== filterStatut) return false;
		if (filterCat && t.categorie !== filterCat) return false;
		return true;
	});

	// Historique : tickets résolus/annulés/fermés, limité à 3 ans, groupés par année décroissante
	const THREE_YEARS_AGO = new Date();
	THREE_YEARS_AGO.setFullYear(THREE_YEARS_AGO.getFullYear() - 3);

	$: historyTickets = ticketList
		.filter((t) => ['résolu', 'annulé', 'fermé'].includes(t.statut) && new Date(t.mis_a_jour_le ?? t.cree_le) >= THREE_YEARS_AGO)
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
		showEvolForm = id;
		evolType = 'commentaire';
		evolContenu = '';
		evolNouveauStatut = '';
		expandedTickets = new Set([id]);
	}

	async function addEvolution(t: Ticket) {
		if (evolType === 'etat' && !evolNouveauStatut) return;
		if (evolType === 'commentaire' && !evolContenu.trim()) return;
		evolSaving = true;
		try {
			await ticketsApi.addEvolution(t.id, {
				type: evolType,
				contenu: evolContenu.trim() || undefined,
				nouveau_statut: evolType === 'etat' ? evolNouveauStatut : undefined,
			});
			if (evolType === 'etat') {
				ticketList = ticketList.map(x => x.id === t.id ? { ...x, statut: evolNouveauStatut } : x);
			}
			await loadEvolutions(t.id);
			showEvolForm = null;
			toast('success', evolType === 'etat' ? 'Statut mis à jour' : 'Commentaire ajouté');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
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
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<div class="page-header">
	<h1 style="display:flex;align-items:center;gap:.4rem"><Icon name={_pc.icone || 'message-square-text'} size={20} />{_pc.titre}</h1>
	<a href="/tickets/nouveau" class="btn btn-primary page-header-btn">+ Nouveau ticket</a>
</div>
<div class="page-subtitle">{@html safeHtml(_pc.descriptif)}</div>

<div class="urgence-disclaimer" role="note" aria-label="Avertissement tickets urgence">
	<button class="urgence-disclaimer-toggle" on:click={() => disclaimerOpen = !disclaimerOpen} aria-expanded={disclaimerOpen}>
		<span class="urgence-disclaimer-title">&#x1F6A8; Tickets de type Urgence — Avertissement légal</span>
		<span class="urgence-disclaimer-chevron">{disclaimerOpen ? '▲' : '▼'}</span>
	</button>
	{#if disclaimerOpen}
	<p>
		Le dépôt d'un ticket <strong>Urgence</strong> dans cette application a pour seul objet la
		<strong>traçabilité de votre signalement</strong>. Il ne constitue ni un moyen d'alerte des
		secours, ni un engagement de prise en charge dans un délai déterminé, ni une garantie de
		résultat de la part du conseil syndical ou du syndicat des copropriétaires.
	</p>
	<p class="urgence-disclaimer-steps">
		<strong>En cas de danger pour les personnes ou de sinistre, vous devez impérativement :</strong>
	</p>
	<ul>
		<li>&#x1F4DE; <strong>Alerter les secours</strong> — 15 (SAMU) · 17 (Police secours) · 18 (Sapeurs-pompiers) · 112 (urgences européennes)</li>
		<li>&#x1F3E2; <strong>Prévenir le syndic</strong> via ses coordonnées d'urgence (voir <a href="/annuaire">Annuaire</a>)</li>
		<li>&#x1F4CB; <strong>Déclarer le sinistre à votre assureur</strong> dans les délais prévus au contrat (généralement 5 jours ouvrés à compter de la connaissance du sinistre — art. L113-2 Code des Assurances)</li>
	</ul>
	<p class="urgence-disclaimer-legal">
		La responsabilité du syndicat des copropriétaires, du conseil syndical et de l'administrateur
		de la plateforme ne saurait être engagée en cas de préjudice résultant de l'absence de
		signalement par les voies officielles ci-dessus.
	</p>
	{/if}
</div>

<div class="filters">
	<span class="filter-group">
		<button class="btn btn-sm" class:btn-primary={filterStatut === ''} on:click={() => filterStatut = ''}>Tous</button>
		<button class="btn btn-sm" class:btn-primary={filterStatut === 'ouvert'} on:click={() => filterStatut = 'ouvert'}>&#x1F535; Ouvert</button>
		<button class="btn btn-sm" class:btn-primary={filterStatut === 'en_cours'} on:click={() => filterStatut = 'en_cours'}>&#x1F7E1; En cours</button>
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
		<div class="tk-expand" class:expanded class:urgent={t.categorie === 'urgence'}
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
				<div class="tk-preview clamp-5">{@html renderDesc(t.description)}</div>
			{/if}

			{#if expanded}
				<div class="tk-body" on:click|stopPropagation on:keydown|stopPropagation>
					{#if showEvolForm === t.id}
						<!-- Formulaire d'évolution -->
						<div class="evol-form">
							<div style="display:flex;gap:.5rem;margin-bottom:.6rem;flex-wrap:wrap">
								<button type="button" class="pill" class:pill-active={evolType === 'commentaire'}
									on:click={() => (evolType = 'commentaire')}>&#x1F4AC; Commentaire</button>
								<button type="button" class="pill" class:pill-active={evolType === 'etat'}
									on:click={() => (evolType = 'etat')}>&#x1F504; Changement d'état</button>
							</div>
							{#if evolType === 'etat'}
								<div class="field">
									<label for="evol-statut-{t.id}">Nouvel état *</label>
									<select id="evol-statut-{t.id}" bind:value={evolNouveauStatut}>
										<option value="">— Choisir —</option>
										<option value="ouvert">&#x1F535; Ouvert</option>
										<option value="en_cours">&#x1F7E1; En cours</option>
										<option value="résolu">&#x1F7E2; Résolu</option>
									<option value="annulé">⚫ Annulé</option>
									</select>
								</div>
							{/if}
							<div class="field">
								<label for="evol-contenu-{t.id}">{evolType === 'etat' ? 'Commentaire (optionnel)' : 'Commentaire *'}</label>
								<textarea id="evol-contenu-{t.id}" bind:value={evolContenu} rows="3"
									placeholder={evolType === 'etat' ? 'Précisions sur ce changement…' : 'Ajoutez un commentaire de suivi…'}
									style="width:100%;padding:.4rem .6rem;border:1px solid var(--color-border);border-radius:6px;font-size:.875rem;resize:vertical"
								></textarea>
							</div>
							<div class="form-actions" style="gap:.5rem">
								<button type="button" class="btn btn-outline" on:click={() => (showEvolForm = null)}>Annuler</button>
								<button type="button" class="btn btn-primary"
									disabled={evolSaving || (evolType === 'etat' && !evolNouveauStatut) || (evolType === 'commentaire' && !evolContenu.trim())}
									on:click={() => addEvolution(t)}>
									{evolSaving ? 'Envoi…' : 'Valider'}
								</button>
							</div>
						</div>
					{:else}
						<!-- Corps normal -->
						<div class="rich-content" style="font-size:.875rem;line-height:1.6;margin-bottom:.5rem">{@html renderDesc(t.description)}</div>
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
												<div class="evol-content rich-content">{@html renderDesc(evol.contenu)}</div>
											{/if}
										{:else if evol.type === 'reponse' || evol.type === 'commentaire'}
											{#if evol.contenu}
												<div class="evol-content rich-content">{@html renderDesc(evol.contenu)}</div>
											{/if}
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
								<div class="tk-preview clamp-5">{@html renderDesc(t.description)}</div>
							{/if}

							{#if expanded}
								<div class="tk-body" on:click|stopPropagation on:keydown|stopPropagation>
									{#if showEvolForm === t.id}
										<!-- Formulaire d'évolution -->
										<div class="evol-form">
											<div style="display:flex;gap:.5rem;margin-bottom:.6rem;flex-wrap:wrap">
												<button type="button" class="pill" class:pill-active={evolType === 'commentaire'}
													on:click={() => (evolType = 'commentaire')}>&#x1F4AC; Commentaire</button>
												<button type="button" class="pill" class:pill-active={evolType === 'etat'}
													on:click={() => (evolType = 'etat')}>&#x1F504; Changement d'état</button>
											</div>
											{#if evolType === 'etat'}
												<div class="field">
													<label for="evol-statut-{t.id}">Nouvel état *</label>
													<select id="evol-statut-{t.id}" bind:value={evolNouveauStatut}>
														<option value="">— Choisir —</option>
														<option value="ouvert">&#x1F535; Ouvert</option>
														<option value="en_cours">&#x1F7E1; En cours</option>
														<option value="résolu">&#x1F7E2; Résolu</option>
														<option value="annulé">⚫ Annulé</option>
													</select>
												</div>
											{/if}
											<div class="field">
												<label for="evol-contenu-{t.id}">{evolType === 'etat' ? 'Commentaire (optionnel)' : 'Commentaire *'}</label>
												<textarea id="evol-contenu-{t.id}" bind:value={evolContenu} rows="3"
													placeholder={evolType === 'etat' ? 'Précisions sur ce changement…' : 'Ajoutez un commentaire de suivi…'}
													style="width:100%;padding:.4rem .6rem;border:1px solid var(--color-border);border-radius:6px;font-size:.875rem;resize:vertical"
												></textarea>
											</div>
											<div class="form-actions" style="gap:.5rem">
												<button type="button" class="btn btn-outline" on:click={() => (showEvolForm = null)}>Annuler</button>
												<button type="button" class="btn btn-primary"
													disabled={evolSaving || (evolType === 'etat' && !evolNouveauStatut) || (evolType === 'commentaire' && !evolContenu.trim())}
													on:click={() => addEvolution(t)}>
													{evolSaving ? 'Envoi…' : 'Valider'}
												</button>
											</div>
										</div>
									{:else}
										<!-- Corps normal -->
										<div class="rich-content" style="font-size:.875rem;line-height:1.6;margin-bottom:.5rem">{@html renderDesc(t.description)}</div>
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
																<div class="evol-content rich-content">{@html renderDesc(evol.contenu)}</div>
															{/if}
														{:else if evol.type === 'reponse' || evol.type === 'commentaire'}
															{#if evol.contenu}
																<div class="evol-content rich-content">{@html renderDesc(evol.contenu)}</div>
															{/if}
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
	.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
	.page-header h1 { font-size: 1.4rem; font-weight: 700; }

	/* Filtres (style identique à calendrier) */
	.filters { display: flex; gap: .4rem; flex-wrap: wrap; margin-bottom: 1.25rem; align-items: center; }
	.filter-group { display: flex; gap: .4rem; flex-wrap: wrap; }
	.filter-sep { width: 1px; height: 1.2rem; background: var(--color-border); margin: 0 .3rem; }

	/* Carte ticket expansible */
	.tk-expand { margin-bottom: .3rem; border-left: 4px solid var(--color-border); border-radius: var(--radius); overflow: visible; position: relative; background: var(--color-surface); transition: border-left-color .12s; }
	.tk-expand:hover, .tk-expand.expanded { border-left-color: var(--color-primary); }
	.tk-expand.urgent { border-left-color: var(--color-danger); }

	.tk-row { display: flex; align-items: center; gap: .6rem; padding: .6rem .9rem; cursor: pointer; user-select: none; transition: background .12s; }
	.tk-row:hover { background: var(--color-bg); }
	.tk-row-inner { display: flex; align-items: center; gap: .4rem; flex: 1; min-width: 0; overflow: hidden; }
	.tk-cat { flex-shrink: 0; font-size: .95rem; }
	.tk-row-titre { font-size: .9rem; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.tk-row-right { display: flex; align-items: center; gap: .3rem; flex-shrink: 0; }
	.tk-row-date { font-size: .78rem; color: var(--color-text-muted); margin-right: .3rem; white-space: nowrap; }

	.tk-preview { padding: .4rem 1rem .6rem; font-size: .875rem; line-height: 1.6; color: var(--color-text-muted); }
	.tk-preview :global(p) { margin: 0 0 .4em; }
	.tk-body { padding: .75rem 1rem 1rem; border-top: 1px solid var(--color-border); }
	.tk-body :global(p) { margin: 0 0 .5em; }

	.chevron { font-size: 1.1rem; color: var(--color-text-muted); transition: transform .15s; display: inline-block; line-height: 1; }
	.chevron.open { transform: rotate(90deg); }

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

	.form-actions { display: flex; justify-content: flex-end; }
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
	.urgence-disclaimer { background: #fff7ed; border: 1.5px solid #fed7aa; border-left: 5px solid #ea580c; border-radius: var(--radius); padding: 0; margin-bottom: 1.25rem; font-size: .85rem; line-height: 1.6; color: #431407; overflow: hidden; }
	.urgence-disclaimer-toggle { display: flex; justify-content: space-between; align-items: center; width: 100%; background: none; border: none; padding: .7rem 1.1rem; cursor: pointer; text-align: left; gap: .5rem; }
	.urgence-disclaimer-toggle:hover { background: #fed7aa44; }
	.urgence-disclaimer-title { font-weight: 700; font-size: .95rem; color: #9a3412; }
	.urgence-disclaimer-chevron { font-size: .7rem; color: #9a3412; flex-shrink: 0; }
	.urgence-disclaimer p { margin: 0 0 .45rem; padding: 0 1.1rem; }
	.urgence-disclaimer p:first-of-type { padding-top: .2rem; }
	.urgence-disclaimer ul { margin: .3rem 0 .45rem 1.1rem; padding: 0 1.1rem 0 0; display: flex; flex-direction: column; gap: .25rem; }
	.urgence-disclaimer li { list-style: none; }
	.urgence-disclaimer a { color: #9a3412; text-decoration: underline; }
	.urgence-disclaimer-steps { margin-top: .45rem !important; }
	.urgence-disclaimer-legal { font-size: .78rem; color: #7c2d12; font-style: italic; margin-top: .3rem !important; border-top: 1px solid #fed7aa; padding: .45rem 1.1rem .85rem !important; }
</style>
