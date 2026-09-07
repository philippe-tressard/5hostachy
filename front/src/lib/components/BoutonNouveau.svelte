<!--
  Le bouton d'en-tête qui ouvre un formulaire de création, et qui bascule en
  « ✕ Annuler » tant qu'il est ouvert.

  POURQUOI CE COMPOSANT (16/08/2026). Ce geste est la règle 1 du paradigme unique
  (#367) : la commande d'annulation vit dans l'en-tête, où le bouton d'ouverture
  se retourne — jamais un second bouton dans la boîte. Il était réécrit à la main
  sur chaque écran, et l'écran Prestataires montrait ce que ça produit : sur ses
  QUATRE onglets, deux basculaient correctement et deux affichaient encore
  « + Nouvelle prestation » / « + Nouveau contrat » avec le formulaire déjà
  ouvert, sans aucun moyen de renoncer depuis l'en-tête. Même fichier, même
  intention, deux comportements — signalé par l'utilisateur.

  Écrire la bascule ici la rend non-oubliable : un écran qui utilise ce composant
  ne PEUT plus afficher « + … » sur un formulaire ouvert.

  Le libellé reçu est celui de l'ouverture (« Nouvelle prestation ») : le « + » et
  le « ✕ Annuler » sont posés par le composant, pour que le préfixe et la formule
  d'annulation soient identiques partout. C'est le même raisonnement que pour le
  chevron ou l'indicateur d'attente d'app.css — un signal d'interface se décide
  une fois.

  `page-header-btn` et `btn btn-primary` viennent d'app.css : aucune règle locale
  ici, donc rien à faire suivre si le balisage bouge.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	/** Le formulaire est-il ouvert ? C'est ce qui décide du libellé. */
	export let ouvert = false;

	/** Libellé d'ouverture, SANS le « + » — ex. « Nouvelle prestation ». */
	export let libelle: string;

	const dispatch = createEventDispatcher<{ basculer: void }>();
</script>

<button class="btn btn-primary page-header-btn" on:click={() => dispatch('basculer')}>
	{ouvert ? '✕ Annuler' : `+ ${libelle}`}
</button>
