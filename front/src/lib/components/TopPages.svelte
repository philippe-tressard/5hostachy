<script lang="ts">
	/**
	 * Top pages de la télémétrie — tableau et sa ligne de total.
	 *
	 * Extrait de `routes/(app)/admin/+page.svelte` le 13/08/2026 : le total des
	 * vues manquait (signalé par l'utilisateur), et ce fichier dépasse 2 200
	 * lignes — le contrôle de modularité refuse qu'il grossisse. L'étoffer sur
	 * place aurait été refusé au pré-check ; le découper est ce que la règle
	 * « au fil de l'eau » demande.
	 *
	 * 🔴 Plus de colonne « Utilisateurs » ni de note sur les vues « non
	 * rattachées » depuis le 02/10/2026 (#1545) : la mesure d'audience ne porte
	 * plus d'identifiant, il n'y a plus de personnes à compter par page.
	 */
	export let pages: { page: string; total: number }[] = [];

	//  Calculé UNE fois. Il l'était à l'intérieur de la boucle, donc recalculé
	//  pour chaque ligne : sans effet visible, mais quadratique.
	$: totalVues = pages.reduce((s, p) => s + p.total, 0);
	//  Le `|| 1` protège la division, jamais l'affichage : un total de 0 doit
	//  s'afficher 0, pas 1 (`standards/04` : ne pas présenter une valeur de repli
	//  comme une mesure).
	$: diviseur = totalVues || 1;
</script>

{#if pages.length > 0}
	<div class="card" style="margin-top:1.25rem">
		<h3 class="titre-panneau">&#x1F3C6; Top pages</h3>
		<table class="table">
			<thead>
				<tr>
					<th>Page</th>
					<th style="text-align:right">Vues</th>
					<th style="text-align:right">%</th>
				</tr>
			</thead>
			<tbody>
				{#each pages as p (p.page)}
					<tr>
						<td><code style="font-size:var(--fs-md)">{p.page}</code></td>
						<td style="text-align:right;font-weight:600">{p.total}</td>
						<td style="text-align:right;color:var(--color-text-muted)">
							{((p.total / diviseur) * 100).toFixed(1)}%
						</td>
					</tr>
				{/each}
			</tbody>
			<tfoot>
				<tr class="total">
					<td>Total — {pages.length} page{pages.length > 1 ? 's' : ''}</td>
					<td style="text-align:right">{totalVues}</td>
					<td style="text-align:right;color:var(--color-text-muted)">
						{totalVues > 0 ? '100.0%' : '—'}
					</td>
				</tr>
			</tfoot>
		</table>
		<p class="muted" style="font-size:var(--fs-sm);margin:.5rem 0 0">
			Les pourcentages se rapportent aux vues des pages listées ci-dessus, pas au total du site.
		</p>
	</div>
{/if}

<style>
	tfoot tr.total > td {
		border-top: 2px solid var(--color-border);
		font-weight: 700;
		padding-top: 0.5rem;
	}
	/*  L'intitulé d'un panneau de télémétrie. Il s'appelait `.tl-section-title`
	    et sa règle vivait dans la PAGE : `TopPages` étant un composant à part, il
	    ne l'a jamais reçue — un composant enfant n'hérite pas d'un style scopé
	    (#495). Renommé pour ne pas laisser croire qu'il partage une définition. */
	.titre-panneau {
		font-size: var(--fs-lg);
		font-weight: 600;
		margin: 0 0 0.75rem;
		padding: 0.75rem 1rem 0;
	}
</style>
