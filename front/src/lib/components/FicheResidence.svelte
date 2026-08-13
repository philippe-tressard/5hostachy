<script lang="ts">
	/**
	 * Fiche d'identité de la résidence — adresse, immatriculation, lots,
	 * assurance, et composition par bâtiment.
	 *
	 * Extrait de `routes/(app)/residence/+page.svelte` le 13/08/2026 : cette page
	 * fait 1 459 lignes et la règle de modularité (rang 1) refuse qu'elle grossisse
	 * — or il fallait y ajouter le second décompte de lots de la fiche ANAH.
	 *
	 * La coupe emporte le bloc AVEC sa feuille de style. Les classes `info-*` et
	 * `batiment-table` étaient à portée locale (styles Svelte scopés) : les laisser
	 * derrière aurait rendu ce composant sans style, et les recopier aurait créé
	 * une seconde source pour les mêmes règles. Elles ne servaient nulle part
	 * ailleurs dans la page — la coupe est donc nette, sans duplication.
	 */
	import { fmtDateShort as fmt } from '$lib/date';

	export let copropriete: any;
	export let batiments: any[] = [];

	$: hasOrphanLots = (copropriete?.nb_parkings_communs ?? 0) > 0;
	$: totalAppart  = batiments.reduce((s, b) => s + (b.nb_appartements ?? 0), 0);
	$: totalCave    = batiments.reduce((s, b) => s + (b.nb_caves ?? 0), 0);
	$: totalParking = batiments.reduce((s, b) => s + (b.nb_parkings ?? 0), 0) + (copropriete?.nb_parkings_communs ?? 0);
	$: totalLocaux  = batiments.reduce((s, b) => s + (b.nb_locaux_commerciaux ?? 0), 0);
</script>

<div class="card" style="padding:1.25rem">
	{#if copropriete.adresse}
		<div style="margin-bottom:1rem">
			<span class="info-label">Adresse</span>
			<div class="info-value" style="margin-top:.25rem">{copropriete.adresse}</div>
		</div>
	{/if}

	{#if copropriete.numero_immatriculation || copropriete.assurance_compagnie || copropriete.nb_lots_total || copropriete.nb_lots_principaux}
		<div class="info-grid" style="margin-bottom:1.25rem">
			{#if copropriete.numero_immatriculation}
				<div class="info-item">
					<span class="info-label">N° immatriculation</span>
					<span class="info-value info-highlight">{copropriete.numero_immatriculation}</span>
				</div>
			{/if}
		{#if copropriete.nb_lots_principaux}
			<div class="info-item">
				<span class="info-label">Lots d'habitation, commerces et bureaux</span>
				<span class="info-value">{copropriete.nb_lots_principaux}</span>
			</div>
		{/if}
		{#if copropriete.nb_lots_total}
			<div class="info-item">
				<span class="info-label">Lots au total</span>
				<span class="info-value">{copropriete.nb_lots_total}</span>
			</div>
		{/if}
			{#if copropriete.assurance_compagnie}
				<div class="info-item">
					<span class="info-label">Assurance</span>
					<span class="info-value">{copropriete.assurance_compagnie}{#if copropriete.assurance_echeance} — échéance {fmt(copropriete.assurance_echeance)}{/if}</span>
				</div>
			{/if}
		</div>
	{/if}

	{#if batiments.length > 0}
		<div style="border-top:1px solid var(--color-border);padding-top:1rem">
			<p class="info-label" style="margin-bottom:.6rem">Composition</p>
			<table class="batiment-table">
				<thead>
					<tr>
						<th>Bâtiment</th>
						<th>Parkings</th>
						<th>Caves</th>
						<th>Appartements</th>
						<th>Loc. commerciaux</th>
					</tr>
				</thead>
				<tbody>
					{#each batiments as b}
						<tr>
							<td style="font-weight:600">Bât. {b.numero}</td>
							<td>{(b.nb_parkings ?? 0) > 0 ? b.nb_parkings : '—'}</td>
							<td>{(b.nb_caves ?? 0) > 0 ? b.nb_caves : '—'}</td>
							<td>{(b.nb_appartements ?? 0) > 0 ? b.nb_appartements : '—'}</td>
							<td>{(b.nb_locaux_commerciaux ?? 0) > 0 ? b.nb_locaux_commerciaux : '—'}</td>
						</tr>
					{/each}
					{#if hasOrphanLots}
						<tr>
							<td style="color:var(--color-text-muted);font-style:italic">Communs</td>
							<td>{copropriete.nb_parkings_communs}</td>
							<td>—</td>
							<td>—</td>
							<td>—</td>
						</tr>
					{/if}
				</tbody>
				<tfoot>
					<tr>
						<td>Total</td>
						<td>{totalParking > 0 ? totalParking : '—'}</td>
						<td>{totalCave > 0 ? totalCave : '—'}</td>
						<td>{totalAppart > 0 ? totalAppart : '—'}</td>
						<td>{totalLocaux > 0 ? totalLocaux : '—'}</td>
					</tr>
				</tfoot>
			</table>
		</div>
	{/if}
</div>

<style>
	/* ── Infos résidence ────────────────────────────────────────── */
	.info-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(220px, 100%), 1fr));
		gap: .6rem;
	}
	.info-item { display: flex; flex-direction: column; gap: .1rem; }
	.info-label {
		font-size: .72rem;
		color: var(--color-text-muted);
		text-transform: uppercase;
		letter-spacing: .04em;
		font-weight: 600;
	}
	.info-value { font-size: .9rem; font-weight: 500; }
	.info-highlight { color: var(--color-primary); font-weight: 700; }

	/* ── Tableau bâtiments ────────────────────────────────────────────── */
	.batiment-table { width: 100%; border-collapse: collapse; font-size: .875rem; margin-top: .25rem; }
	.batiment-table th {
		text-align: left;
		padding: .4rem .75rem;
		font-size: .72rem;
		text-transform: uppercase;
		letter-spacing: .04em;
		color: var(--color-text-muted);
		border-bottom: 2px solid var(--color-border);
		font-weight: 600;
	}
	.batiment-table td { padding: .4rem .75rem; border-bottom: 1px solid var(--color-border); }
	.batiment-table tfoot td { font-weight: 700; border-top: 2px solid var(--color-border); border-bottom: none; }
</style>
