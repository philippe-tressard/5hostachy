<!--
  La barre de FILTRES de l'annuaire des prestataires — métier, cadre, recherche.

  Extraite de `prestataires/+page.svelte` le 28/09/2026 (#1444) : le filtre
  « sous contrat » l'aurait fait grossir, et la page dépasse déjà 500 lignes
  (`standards/02` §6, « on découpe QUAND on y touche »). La règle de tri, elle,
  vit dans `$lib/prestataires` (`filtrerPrestataires`) — le composant ne fait
  que la saisir.

  Les rangées et le champ « Catégorie » du formulaire : UN motif, porté par
  `ChoixPastilles` (#491). `avecDetail` sur les catégories : leur description
  vivait dans un `title`, donc invisible au tactile.

  🔴 **Deux lignes sur ordinateur** (28/09/2026, demandé à l'écran) : le métier
  sur la première, le cadre et la RECHERCHE sur la seconde. La rangée des douze
  équipements, qui défilait sous les deux autres, a cédé la place à la
  recherche — `ChampRecherche`, le même champ que la page Affaires ; un
  équipement se retrouve en le tapant.
-->
<script lang="ts">
	import ChoixPastilles from './ChoixPastilles.svelte';
	import ChampRecherche from './ChampRecherche.svelte';
	import { FILTRES_CONTRAT, TYPES_PRESTATAIRE, type FiltresPrestataires } from '$lib/prestataires';

	export let filtres: FiltresPrestataires;
	/** Combien l'annuaire en montre — porté par la pastille retenue de chaque rangée. */
	export let affiches: number | null = null;
</script>

<div class="filters filters--groupes filtres-prestataires">
	<ChoixPastilles
		options={TYPES_PRESTATAIRE}
		bind:valeur={filtres.type}
		avecDetail
		compte={affiches}
		libelle="Filtrer par type de prestataire"
	/>
	<span class="filtre-saut"></span>
	<!--  Le CADRE, séparé du métier (#1444) : il se lit sur les contrats actifs. -->
	<ChoixPastilles
		options={FILTRES_CONTRAT}
		bind:valeur={filtres.contrat}
		compte={affiches}
		libelle="Filtrer par contrat"
	/>
	<ChampRecherche
		id="recherche-prestataires"
		bind:valeur={filtres.recherche}
		placeholder="Nom, métier, équipement, contact, téléphone…"
	/>
</div>

<style>
	/*  `.filters--groupes` vient de la feuille commune : le saut force le métier
	    seul sur sa ligne, le cadre et la recherche partagent la seconde. */
	.filtres-prestataires {
		column-gap: 1rem;
	}
</style>
