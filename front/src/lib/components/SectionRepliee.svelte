<!--
  SectionRepliee.svelte — un bandeau « 📁 Historique (12) ▼ » et ce qu'il cache.

  ## Pourquoi (18/08/2026)

  Les petites annonces ont reçu leur Historique — *« les annonces restent à
  l'état vendu pendant 1 mois et sont archivées dans une section pliée par
  défaut »*. Les actualités en avaient un depuis #356, avec ses **onze règles de
  style** écrites dans `HistoriqueActualites.svelte`.

  Les recopier en aurait fait deux — et la duplication n'est pas livrable
  (rang 1, `standards/02`). Elles vivent donc ici, une fois, et les deux écrans
  les héritent.

  ⚠️ Le composant porte son balisage **et** son style. C'est la leçon de
  `Pastille.svelte` (v2.67.11) : un style laissé dans la page hôte n'atteint pas
  le balisage d'un enfant, et le composant part nu en production.

  ## Ce qu'il ne décide pas

  Ni ce qu'il y a dedans, ni quand le charger. `ouvert` est **lié** : c'est
  l'appelant qui déclenche son chargement différé au premier dépliage — la
  section ne connaît aucune API et ne doit pas en connaître.
-->
<script lang="ts">
	/** L'intitulé, emoji compris — c'est l'appelant qui nomme sa section. */
	export let titre: string;
	/**  Le compteur affiché à droite du titre. `null` = rien : une section dont le
	 *   contenu n'est pas encore chargé ne doit pas annoncer « 0 », ce qui se lit
	 *   comme « il n'y a rien » alors qu'on n'a pas regardé. */
	export let compte: number | null = null;
	/** Déplié ? Lié, pour que l'appelant puisse charger au premier dépliage. */
	export let ouvert = false;
</script>

<div class="sr-section">
	<button class="sr-entete" on:click={() => (ouvert = !ouvert)} aria-expanded={ouvert}>
		<span class="sr-titre">{titre}</span>
		{#if compte !== null}<span class="sr-compte">{compte}</span>{/if}
		<span class="sr-chevron">{ouvert ? '▲' : '▼'}</span>
	</button>
	{#if ouvert}
		<div class="sr-contenu"><slot /></div>
	{/if}
</div>

<style>
	.sr-section { margin-top: 2rem; padding-top: 1.5rem; border-top: 2px solid var(--color-border); }
	.sr-entete {
		display: flex; align-items: center; gap: .5rem; width: 100%;
		background: none; border: none; padding: 0; cursor: pointer;
		font-size: 1rem; font-weight: 600; color: var(--color-text); text-align: left;
	}
	.sr-entete:hover { color: var(--color-primary); }
	.sr-titre { flex: 1; }
	.sr-compte {
		display: inline-flex; align-items: center; justify-content: center;
		background: var(--color-primary); color: #fff;
		font-size: .75rem; font-weight: 700; padding: .15rem .5rem;
		border-radius: 12px; min-width: 1.5rem;
	}
	.sr-chevron { font-size: .8rem; color: var(--color-text-muted); flex-shrink: 0; transition: transform .2s; }
	.sr-entete[aria-expanded='true'] .sr-chevron { transform: scaleY(-1); }
	.sr-contenu { margin-top: 1rem; display: flex; flex-direction: column; gap: 0; }

	/*  Cible tactile (socle 11 §10) : le bandeau est le seul geste de la section. */
	@media (max-width: 480px) {
		.sr-entete { min-height: 40px; }
	}
</style>
