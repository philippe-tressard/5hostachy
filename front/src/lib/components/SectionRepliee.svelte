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
	/*  🔴 LE BANDEAU DE SECTION DU SITE — « le meilleur des trois mondes »
	    (demandé à l'écran le 20/08/2026, #516).

	    Trois écrans rendaient cette même notion de trois façons :
	      • Tableau de bord — une CARTE cliquable (fond, bordure, survol), chevron
	        à gauche, compteur gris pâle ;
	      • Actualités — un titre nu avec son emoji, chevron à droite, sans compteur ;
	      • Tickets — un titre avec un compteur BIEN VISIBLE.

	    Ce qui est repris de chacun : la **carte cliquable** du tableau de bord (on
	    voit que ça se clique, et la zone de clic est franche), le **badge coloré**
	    des tickets (on sait combien avant d'ouvrir), le **chevron à droite qui
	    pivote** des actualités (il suit l'état au lieu de changer de glyphe).

	    ⚠️ L'emoji reste dans le `titre` : le catalogue d'icônes ne porte ni
	    « dossier » ni « archive », et en ajouter une pour ce seul bandeau
	    dépasserait le lot. */
	.sr-section { margin-top: 2rem; padding-top: 1.5rem; border-top: 2px solid var(--color-border); }
	.sr-entete {
		display: flex; align-items: center; gap: .6rem; width: 100%;
		padding: .7rem 1rem;
		background: var(--color-surface); border: 1px solid var(--color-border);
		border-radius: var(--radius); cursor: pointer;
		font-size: .95rem; font-weight: 600; color: var(--color-text); text-align: left;
		transition: background .15s, border-color .15s, color .15s;
	}
	.sr-entete:hover { background: var(--color-bg); border-color: var(--color-primary); color: var(--color-primary); }
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
		.sr-entete { min-height: 44px; }
	}
</style>
