<script lang="ts">
	/**
	 * Top pages de la télémétrie — tableau et sa ligne de total.
	 *
	 * Extrait de `routes/(app)/admin/+page.svelte` le 13/08/2026 : le total des
	 * vues manquait (signalé par l'utilisateur), et ce fichier dépasse 2 200
	 * lignes — le contrôle de modularité refuse qu'il grossisse. L'étoffer sur
	 * place aurait été refusé au pré-check ; le découper est ce que la règle
	 * « au fil de l'eau » demande.
	 */
	export let pages: { page: string; total: number; uniques: number }[] = [];

	/** Vues comptées ici mais rattachées à aucun utilisateur (#354).
	    Ce tableau compte TOUTES les vues ; celui des utilisateurs n'en retient que
	    les attribuables. Deux nombres côte à côte sur un même écran engagent une
	    promesse de cohérence : quand ils diffèrent, l'écran doit le dire — c'est
	    plus important que la cause. */
	export let vuesNonAttribuees = 0;

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
					<th style="text-align:right">Utilisateurs</th>
					<th style="text-align:right">%</th>
				</tr>
			</thead>
			<tbody>
				{#each pages as p}
					<tr>
						<td><code style="font-size:.82rem">{p.page}</code></td>
						<td style="text-align:right;font-weight:600">{p.total}</td>
						<td style="text-align:right;color:var(--color-text-muted)">{p.uniques}</td>
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
						<!--  Additionner la colonne serait FAUX : un même utilisateur compte
						      dans chaque page qu'il a vue, et la somme dirait « 17 personnes »
						      là où il n'y en a qu'une. Le nombre réel d'utilisateurs distincts
						      est celui de l'indicateur en tête d'écran. -->
						<span
							title="La somme des utilisateurs par page compterait plusieurs fois la même personne. Le nombre d'utilisateurs distincts est donné par l'indicateur « Utilisateurs » en haut de cette page."
							>—</span
						>
					</td>
					<td style="text-align:right;color:var(--color-text-muted)">
						{totalVues > 0 ? '100.0%' : '—'}
					</td>
				</tr>
			</tfoot>
		</table>
		{#if vuesNonAttribuees > 0}
			<p class="tl-note">
				Dont <strong>{vuesNonAttribuees}</strong> vue{vuesNonAttribuees > 1 ? 's' : ''}
				non rattachée{vuesNonAttribuees > 1 ? 's' : ''} à un utilisateur — enregistrée{vuesNonAttribuees >
				1
					? 's'
					: ''}
				avant l'ouverture de la session ou après son expiration. C'est ce qui explique l'écart avec le
				tableau « Utilisateurs les plus actifs ».
			</p>
		{/if}
		<p class="muted" style="font-size:.78rem;margin:.5rem 0 0">
			Les pourcentages se rapportent aux vues des pages listées ci-dessus, pas au total du site.
		</p>
	</div>
{/if}

<style>
	.tl-note {
		font-size: 0.8rem;
		color: var(--color-text-muted);
		line-height: 1.5;
		margin: 0.6rem 0 0;
	}
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
		font-size: 0.95rem;
		font-weight: 600;
		margin: 0 0 0.75rem;
		padding: 0.75rem 1rem 0;
	}
</style>
