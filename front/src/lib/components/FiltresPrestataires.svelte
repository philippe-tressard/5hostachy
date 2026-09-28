<!--
  La barre de FILTRES de l'annuaire des prestataires — métier, cadre, équipement.

  Extraite de `prestataires/+page.svelte` le 28/09/2026 (#1444) : le filtre
  « sous contrat » l'aurait fait grossir, et la page dépasse déjà 500 lignes
  (`standards/02` §6, « on découpe QUAND on y touche »). La règle de tri, elle,
  vit dans `$lib/prestataires` (`filtrerPrestataires`) — le composant ne fait
  que la saisir.

  Trois rangées et le champ « Catégorie » du formulaire : UN motif, porté par
  `ChoixPastilles` (#491). Il était écrit deux fois dans la page, à trois mots
  près — la duplication la plus discrète, celle qu'aucun contrôle inter-fichiers
  ne voit. `avecDetail` sur les catégories seules : leur description vivait dans
  un `title`, donc invisible au tactile. Les équipements n'en portent pas.
-->
<script lang="ts">
	import ChoixPastilles from './ChoixPastilles.svelte';
	import {
		EQUIPEMENTS,
		FILTRES_CONTRAT,
		TYPES_PRESTATAIRE,
		type FiltresPrestataires,
	} from '$lib/prestataires';

	export let filtres: FiltresPrestataires;
</script>

<ChoixPastilles
	options={TYPES_PRESTATAIRE}
	bind:valeur={filtres.type}
	avecDetail
	libelle="Filtrer par type de prestataire"
/>
<!--  Le CADRE, séparé du métier (#1444) : il se lit sur les contrats actifs. -->
<ChoixPastilles
	options={FILTRES_CONTRAT}
	bind:valeur={filtres.contrat}
	libelle="Filtrer par contrat"
/>
<ChoixPastilles
	options={EQUIPEMENTS}
	bind:valeur={filtres.equipement}
	tous="Tous équipements"
	libelle="Filtrer par équipement"
/>
