<!--
  Reporting CS — **analyse des tickets** sur une période glissante : volume,
  urgences, répartition par catégorie et par bâtiment.

  Extrait d'`espace-cs/+page.svelte` avec #453. La liste arrive en prop : c'est
  celle de l'onglet Tickets, jamais une seconde requête pour la même donnée.
-->
<script lang="ts">
	import Pastille from '$lib/components/Pastille.svelte';
	import { daysSince } from '$lib/date';
	import { estTicketActif, ticketScope } from '$lib/tickets';
	import type { Ticket } from '$lib/api';

	export let tickets: Ticket[] = [];

	let reportPeriodDays: 30 | 90 | 365 = 90;

	$: reportTicketSource = tickets.filter((t) => daysSince(t.cree_le) <= reportPeriodDays);
	$: reportTicketCategories = Object.entries(reportTicketSource.reduce((acc: Record<string, { total: number; ouverts: number }>, t) => {
		const key = t.categorie || 'autre';
		if (!acc[key]) acc[key] = { total: 0, ouverts: 0 };
		acc[key].total += 1;
		if (estTicketActif(t.statut)) acc[key].ouverts += 1;
		return acc;
	}, {})).map(([categorie, data]) => ({ categorie, ...data })).sort((a, b) => b.total - a.total);
	$: reportTicketBuildings = Object.entries(reportTicketSource.reduce((acc: Record<string, { total: number; ouverts: number }>, t) => {
		const key = ticketScope(t);
		if (!acc[key]) acc[key] = { total: 0, ouverts: 0 };
		acc[key].total += 1;
		if (estTicketActif(t.statut)) acc[key].ouverts += 1;
		return acc;
	}, {})).map(([batiment, data]) => ({ batiment, ...data })).sort((a, b) => b.total - a.total);
</script>

<div class="reporting-toolbar no-print" style="margin-top:0;margin-bottom:1rem">
	<div class="reporting-switch">
		<Pastille active={reportPeriodDays === 30} on:click={() => (reportPeriodDays = 30)}>30 jours</Pastille>
		<Pastille active={reportPeriodDays === 90} on:click={() => (reportPeriodDays = 90)}>90 jours</Pastille>
		<Pastille active={reportPeriodDays === 365} on:click={() => (reportPeriodDays = 365)}>12 mois</Pastille>
	</div>
</div>

<div class="kpi-row" style="margin-bottom:1rem">
	<div class="kpi-card"><div class="kpi-value">{reportTicketSource.length}</div><div class="kpi-label">Tickets sur la période</div></div>
	<div class="kpi-card"><div class="kpi-value">{reportTicketSource.filter((t) => t.categorie === 'urgence').length}</div><div class="kpi-label">Urgences</div></div>
	<div class="kpi-card"><div class="kpi-value">{reportTicketBuildings.length}</div><div class="kpi-label">Périmètres / bâtiments touchés</div></div>
</div>

<div class="report-grid-2">
	<section class="report-card">
		<h3>Répartition par catégorie</h3>
		<div class="report-table-wrap">
			<table class="report-table compact">
				<thead><tr><th>Catégorie</th><th>Total</th><th>Ouverts / en cours</th></tr></thead>
				<tbody>
					{#each reportTicketCategories as row}
						<tr><td>{row.categorie}</td><td>{row.total}</td><td>{row.ouverts}</td></tr>
					{/each}
				</tbody>
			</table>
		</div>
	</section>

	<section class="report-card">
		<h3>Répartition par bâtiment / périmètre</h3>
		<div class="report-table-wrap">
			<table class="report-table compact">
				<thead><tr><th>Bâtiment / périmètre</th><th>Total</th><th>Ouverts / en cours</th></tr></thead>
				<tbody>
					{#each reportTicketBuildings as row}
						<tr><td>{row.batiment}</td><td>{row.total}</td><td>{row.ouverts}</td></tr>
					{/each}
				</tbody>
			</table>
		</div>
	</section>
</div>
