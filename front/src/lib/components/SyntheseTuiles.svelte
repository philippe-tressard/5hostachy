<!--
  SyntheseTuiles.svelte — M2, les six chiffres d'une affaire close (#1643).

  Durée totale · étape la plus longue · Suites · relances (et la réaction du
  syndic après la dernière) · première réponse du syndic · semaines muettes.
  Tout est CALCULÉ par le serveur et figé à la production : ce composant ne
  mesure rien, il pose les chiffres côte à côte.
-->
<script lang="ts">
	import type { MetriquesSynthese } from '$lib/api';
	import { fmtJours, libelleEtape } from '$lib/synthese';

	export let metriques: MetriquesSynthese;

	$: plusLongue = metriques.etapes.find((e) => e.statut === metriques.etape_plus_longue);
	$: tuiles = [
		{ libelle: 'Durée totale', valeur: fmtJours(metriques.duree_totale), detail: 'jours ouvrés' },
		{
			libelle: 'Étape la plus longue',
			valeur: plusLongue ? fmtJours(plusLongue.jours) : '—',
			detail: plusLongue ? libelleEtape(plusLongue.statut) : '',
		},
		{ libelle: 'Suites', valeur: String(metriques.suites), detail: '' },
		{
			libelle: 'Relances',
			valeur: String(metriques.relances),
			detail: metriques.relances > 0 ? `réaction : ${fmtJours(metriques.reaction_relance)}` : '',
		},
		{
			libelle: '1ʳᵉ réponse du syndic',
			valeur: fmtJours(metriques.premiere_reponse_syndic),
			detail: "après l'ouverture",
		},
		{
			libelle: 'Semaines muettes',
			valeur: String(metriques.semaines_muettes),
			detail: `sur ${metriques.semaines.length}`,
		},
	];
</script>

<ul class="tuiles" aria-label="Chiffres de l'affaire">
	{#each tuiles as t (t.libelle)}
		<li class="tuile">
			<span class="tuile-libelle">{t.libelle}</span>
			<span class="tuile-valeur">{t.valeur}</span>
			{#if t.detail}<span class="tuile-detail">{t.detail}</span>{/if}
		</li>
	{/each}
</ul>

<style>
	.tuiles {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 0.5rem;
	}
	.tuile {
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
		padding: 0.5rem 0.6rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
		min-width: 0;
	}
	.tuile-libelle {
		font-size: var(--fs-xs);
		color: var(--color-text-muted);
	}
	.tuile-valeur {
		font-size: var(--fs-lg);
		font-weight: 600;
		color: var(--color-text);
		font-variant-numeric: tabular-nums;
	}
	.tuile-detail {
		font-size: var(--fs-xs);
		color: var(--color-text-muted);
	}
	@media (max-width: 480px) {
		.tuiles {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}
</style>
