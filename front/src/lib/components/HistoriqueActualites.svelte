<!--
  Historique des publications archivées : replié par défaut, groupé par année,
  chargé seulement au premier dépliage.

  Extrait de `actualites/+page.svelte` (#356) : la page dépassait le plafond de
  500 lignes, et cette section est autonome — elle a sa propre source de données
  (`list(true)`), son propre état de dépliage et sa propre suppression. Rien de
  ce qu'elle manipule n'est partagé avec le fil principal.

  La carte, elle, est la MÊME que celle du fil : `CarteActualite`, en variante
  `historique`. C'est tout l'objet du ticket — les deux rendus ne peuvent plus
  diverger.
-->
<script lang="ts">
	import CarteActualite from '$lib/components/CarteActualite.svelte';
	import { isAdmin } from '$lib/stores/auth';
	import { publications as pubsApi, ApiError, type Publication } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { grouperParAnnee } from '$lib/publications';

	let archivedPubs: Publication[] = [];
	let archivedPubsLoaded = false;
	let historyExpanded = false;
	let expandedHistoryYears = new Set<number>();
	let expandedHistoryItems = new Set<number>();

	async function loadArchivedPubs() {
		if (archivedPubsLoaded) return;
		archivedPubsLoaded = true;
		try { archivedPubs = await pubsApi.list(true); } catch { /* silencieux */ }
	}

	$: if (historyExpanded) loadArchivedPubs();

	$: historyByYear = grouperParAnnee(archivedPubs);

	function toggleAnnee(year: number) {
		if (expandedHistoryYears.has(year)) { expandedHistoryYears.delete(year); } else { expandedHistoryYears.add(year); }
		expandedHistoryYears = expandedHistoryYears;
	}

	function toggleHistoryItem(id: number) {
		expandedHistoryItems = expandedHistoryItems.has(id) ? new Set() : new Set([id]);
	}

	async function deleteArchivedPub(pub: Publication) {
		if (!confirm(`Supprimer définitivement « ${pub.titre} » ?`)) return;
		try {
			await pubsApi.delete(pub.id);
			archivedPubs = archivedPubs.filter(p => p.id !== pub.id);
			toast('success', 'Publication supprimée');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Impossible de supprimer');
		}
	}
</script>

<div class="history-section">
	<button class="history-header" on:click={() => (historyExpanded = !historyExpanded)} aria-expanded={historyExpanded}>
		<span class="history-title">&#x1F4C1; Historique</span>
		{#if archivedPubsLoaded}<span class="history-count">{archivedPubs.length}</span>{/if}
		<span class="history-chevron">{historyExpanded ? '▲' : '▼'}</span>
	</button>
	{#if historyExpanded}
		<div class="history-content">
			{#if archivedPubsLoaded && archivedPubs.length === 0}
				<p style="color:var(--color-text-muted);font-size:.875rem;margin:.5rem 0 0">Aucune publication archivée.</p>
			{:else}
				{#each historyByYear as [year, yearPubs]}
					<div class="history-year">
						<button class="history-year-header" on:click|stopPropagation={() => toggleAnnee(year)} aria-expanded={expandedHistoryYears.has(year)}>
							<span class="history-year-label">{year}</span>
							<span class="history-count" style="font-size:.7rem">{yearPubs.length}</span>
							<span class="history-chevron">{expandedHistoryYears.has(year) ? '▲' : '▼'}</span>
						</button>
						{#if expandedHistoryYears.has(year)}
							{#each yearPubs as pub (pub.id)}
								<CarteActualite {pub} variante="historique"
									expanded={expandedHistoryItems.has(pub.id)}
									on:toggle={() => toggleHistoryItem(pub.id)}>
									<svelte:fragment slot="actions">
										{#if $isAdmin}
											<button class="btn-icon" aria-label="Supprimer" title="Supprimer définitivement" style="color:var(--color-danger)"
												on:click|stopPropagation={() => deleteArchivedPub(pub)}>🗑️</button>
										{/if}
									</svelte:fragment>
								</CarteActualite>
							{/each}
						{/if}
					</div>
				{/each}
			{/if}
		</div>
	{/if}
</div>

<style>
	.history-section { margin-top: 2rem; padding-top: 1.5rem; border-top: 2px solid var(--color-border); }
	.history-header { display: flex; align-items: center; gap: .5rem; width: 100%; background: none; border: none; padding: 0; cursor: pointer; font-size: 1rem; font-weight: 600; color: var(--color-text); text-align: left; }
	.history-header:hover { color: var(--color-primary); }
	.history-title { flex: 1; }
	.history-count { display: inline-flex; align-items: center; justify-content: center; background: var(--color-primary); color: white; font-size: .75rem; font-weight: 700; padding: .15rem .5rem; border-radius: 12px; min-width: 1.5rem; }
	.history-chevron { font-size: .8rem; color: var(--color-text-muted); flex-shrink: 0; transition: transform .2s; }
	.history-header[aria-expanded="true"] .history-chevron { transform: scaleY(-1); }
	.history-content { margin-top: 1rem; display: flex; flex-direction: column; gap: 0; }
	.history-year { margin-bottom: .5rem; }
	.history-year-header { display: flex; align-items: center; gap: .5rem; width: 100%; background: var(--color-bg); border: 1px solid var(--color-border); border-radius: var(--radius); padding: .5rem .75rem; cursor: pointer; font-size: .9rem; font-weight: 600; color: var(--color-text); margin-bottom: .3rem; }
	.history-year-header:hover { border-color: var(--color-primary); color: var(--color-primary); }
	.history-year-label { flex: 1; text-align: left; }
</style>
