<!--
  Reporting CS — **devis et interventions** : le suivi des devis actifs et leur
  répartition par statut.

  Extrait d'`espace-cs/+page.svelte` avec #453.
-->
<script lang="ts">
	import { fmtDate } from '$lib/date';
	import { fmtMontant } from '$lib/utils';
	import { REPORT_DEVIS_LABELS, REPORT_DEVIS_BADGES, type ReportDevis, type ReportPrestataire } from '$lib/reporting';

	export let reportDevisList: ReportDevis[] = [];
	export let reportPrestataires: ReportPrestataire[] = [];

	function reportPrestataireName(prestataireId: number) {
		return reportPrestataires.find((p) => p.id === prestataireId)?.nom ?? `Prestataire #${prestataireId}`;
	}

	$: reportDevisActifs = reportDevisList.filter((d) => d.statut === 'en_attente' || d.statut === 'accepte');
	$: reportDevisSummary = Object.entries(reportDevisList.reduce((acc: Record<string, number>, d) => {
		acc[d.statut] = (acc[d.statut] ?? 0) + 1;
		return acc;
	}, {})).map(([statut, total]) => ({ statut, total })).sort((a, b) => b.total - a.total);
</script>

<div class="kpi-row" style="margin-bottom:1rem">
	<div class="kpi-card"><div class="kpi-value">{reportDevisActifs.length}</div><div class="kpi-label">Devis / interventions actifs</div></div>
	<div class="kpi-card"><div class="kpi-value">{reportDevisList.filter((d) => d.statut === 'en_attente').length}</div><div class="kpi-label">En attente</div></div>
	<div class="kpi-card"><div class="kpi-value">{reportDevisList.filter((d) => d.statut === 'accepte').length}</div><div class="kpi-label">Acceptés non clos</div></div>
</div>

<div class="report-grid-2 report-grid-2-wide">
	<section class="report-card">
		<h3>Suivi des devis et interventions</h3>
		{#if reportDevisActifs.length === 0}
			<div class="empty-state"><h3>Aucun devis actif</h3></div>
		{:else}
			<div class="report-table-wrap">
				<table class="report-table">
					<thead>
						<tr>
							<th>Objet</th>
							<th>Prestataire</th>
							<th>Périmètre</th>
							<th>Échéance</th>
							<th>Montant</th>
							<th>Statut</th>
						</tr>
					</thead>
					<tbody>
						{#each reportDevisActifs as d}
							<tr>
								<td><strong>{d.titre}</strong>{#if d.frequence_type && d.frequence_valeur}<br /><span class="text-muted-sm">Récurrent : {d.frequence_valeur} {d.frequence_type}</span>{/if}</td>
								<td>{reportPrestataireName(d.prestataire_id)}</td>
								<td>{d.perimetre}{#if d.batiment_id}<br /><span class="text-muted-sm">Bât. {d.batiment_id}</span>{/if}</td>
								<td>{d.date_prestation ? fmtDate(d.date_prestation) : 'Non planifiée'}</td>
								<td>{fmtMontant(d.montant_estime)}</td>
								<td><span class="badge {REPORT_DEVIS_BADGES[d.statut] ?? 'badge-gray'}">{REPORT_DEVIS_LABELS[d.statut] ?? d.statut}</span></td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</section>

	<section class="report-card">
		<h3>Répartition par statut</h3>
		<div class="report-table-wrap">
			<table class="report-table compact">
				<thead><tr><th>Statut</th><th>Total</th></tr></thead>
				<tbody>
					{#each reportDevisSummary as row}
						<tr><td>{REPORT_DEVIS_LABELS[row.statut] ?? row.statut}</td><td>{row.total}</td></tr>
					{/each}
				</tbody>
			</table>
		</div>
	</section>
</div>
