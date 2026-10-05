<!--
  TuilesChiffres.svelte — des chiffres posés côte à côte : un libellé, une valeur,
  un détail.

  Extrait de `SyntheseTuiles` (M2 de la synthèse d'une affaire, #1643) le
  04/10/2026, quand le bilan de l'exercice du carnet (#1645) et la fiche d'un
  prestataire (#1646) ont demandé les mêmes tuiles pour des MOYENNES : trois
  écrans, un balisage et un style. Ce composant ne calcule rien — l'appelant
  décide des chiffres et de leur libellé.
-->
<script lang="ts">
	/** Une tuile : `detail` vide = pas de troisième ligne. */
	export let tuiles: { libelle: string; valeur: string; detail?: string }[];
	/** Le nom de la liste, lu par un lecteur d'écran (« Chiffres de l'affaire »). */
	export let libelle: string;
</script>

<ul class="tuiles" aria-label={libelle}>
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
