<!--
  Reporting CS — **suivi des dossiers** : les événements du calendrier
  rangés par colonne de kanban, avec l'ancienneté de chacun.

  Extrait d'`espace-cs/+page.svelte` avec #453. Il ne charge rien : les événements
  arrivent en prop d'`OngletReporting`, qui les a demandés une seule fois pour les
  vues qui les partagent.

  ⚠️ Cette vue s'appelait « Dossiers AG / CS / Syndic », ici, sur sa pastille et
  dans son titre d'impression — trois énumérations figées d'une liste qui vient
  de changer : la colonne « Prestataire (en cours) », rétablie avec
  `REPORT_KANBAN_COLS`, les rendait toutes les trois fausses. Un libellé qui
  ÉNUMÈRE ce qu'un écran contient diverge au premier ajout, et rien ne le
  signale — c'est la même faute que la liste de colonnes recopiée, un cran plus
  haut. Le nom ne décrit donc plus le contenu mais l'usage (#603).
-->
<script lang="ts">
	import { safeDescription } from '$lib/sanitize';
	import { fmtDate, daysSince } from '$lib/date';
	import { REPORT_KANBAN_COLS, KANBAN_COLORS, TYPE_LABELS, type ReportEvenement } from '$lib/reporting';

	export let reportEvenements: ReportEvenement[] = [];

	//  🔴 Les colonnes étaient écrites en dur ICI, deux fois — dans le filtre et
	//  dans la boucle —, et il en manquait une : `fournisseur`. Un dossier passé
	//  chez le prestataire n'apparaissait donc NULLE PART dans le suivi du CS, et
	//  ne comptait pas non plus dans « Dossiers en cours ». Une colonne absente ne
	//  laisse pas de trou à l'écran : rien ne pouvait le signaler.
	//  `REPORT_KANBAN_COLS` dérive de `KANBAN_COLS` — une seule liste, un seul
	//  endroit où l'oubli serait visible.
	const colonnesSuivies = REPORT_KANBAN_COLS.map((c) => c.id);
	$: reportKanbanEvents = reportEvenements
		.filter((ev) => !!ev.statut_kanban && colonnesSuivies.includes(ev.statut_kanban))
		.sort((a, b) => daysSince(b.cree_le) - daysSince(a.cree_le));
	$: reportKanbanByCol = REPORT_KANBAN_COLS.map((c) => ({
		col: c.id,
		label: c.label,
		badge: KANBAN_COLORS[c.id],
		items: reportKanbanEvents.filter((ev) => ev.statut_kanban === c.id),
	}));
</script>

<div class="kpi-row" style="margin-bottom:1rem">
	<div class="kpi-card"><div class="kpi-value">{reportKanbanEvents.filter(ev => ev.statut_kanban !== 'annule').length}</div><div class="kpi-label">Dossiers en cours</div></div>
	{#each reportKanbanByCol as col}
		<div class="kpi-card"><div class="kpi-value">{col.items.length}</div><div class="kpi-label">{col.label}</div></div>
	{/each}
</div>
{#each reportKanbanByCol as col}
	<section class="report-card" style="margin-bottom:1.5rem">
		<h3><span class="badge {col.badge}">{col.label}</span> — {col.items.length} dossier{col.items.length > 1 ? 's' : ''}</h3>
		{#if col.items.length === 0}
			<div class="empty-state"><h3>Aucun dossier dans cette colonne</h3></div>
		{:else}
			<div class="report-table-wrap">
				<table class="report-table">
					<thead>
						<tr>
							<th>Événement</th>
							<th>Contexte</th>
							<th>Dates</th>
						</tr>
					</thead>
					<tbody>
						{#each col.items as ev (ev.id)}
							<tr>
								<td>
									<strong class="report-event-title">{ev.titre}</strong>
									{#if ev.description}
										<div class="report-event-desc rich-content">{@html safeDescription(ev.description)}</div>
									{/if}
								</td>
								<td>
									<div>{TYPE_LABELS[ev.type] ?? ev.type}</div>
									{#if ev.prestataire_nom}<div class="text-muted-sm">{ev.prestataire_nom}</div>{/if}
									<div class="text-muted-sm">{ev.perimetre}{#if ev.batiment_id} · Bât. {ev.batiment_id}{/if}</div>
									{#if ev.auteur_nom}<div class="text-muted-sm">Par {ev.auteur_nom}</div>{/if}
								</td>
								<td>
									<div>Créé le {fmtDate(ev.cree_le)}</div>
									<div>{daysSince(ev.cree_le)} jour(s)</div>
									<div class="text-muted-sm">MAJ : {fmtDate(ev.mis_a_jour_le ?? ev.cree_le)}</div>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</section>
{/each}

<style>
	.report-event-title { display: block; margin-bottom: .25rem; }
	.report-event-desc { color: var(--color-text); }
	.report-event-desc :global(p:last-child) { margin-bottom: 0; }
</style>
