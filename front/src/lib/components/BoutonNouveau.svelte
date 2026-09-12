<!--
  Le bouton d'en-tête qui ouvre un formulaire de création — et qui S'EFFACE tant
  qu'il est ouvert.

  ## 🔴 Il a porté la règle INVERSE pendant quatre semaines (corrigé le 12/09/2026)

  Ce composant est né le 16/08/2026 avec la bascule « + … » ⇆ « ✕ Annuler », et
  son en-tête affirmait porter *« la règle 1 du paradigme unique (#367) »*.

  **Cette règle a été révisée le 18/08**, sur Tickets, en ces termes :

  > L'en-tête n'OUVRE plus que le formulaire : l'annulation vit à côté
  > d'« Enregistrer », dans le formulaire. Le bouton s'efface pendant la saisie —
  > le laisser en « ✕ Annuler » ferait **deux commandes d'annulation pour un seul
  > formulaire**.

  Tickets et Actualités l'ont adoptée. Ce composant, non — et Prestataires, son
  unique appelant, est resté seul sur l'ancienne norme pendant que son en-tête
  continuait d'affirmer porter la bonne. **Une consigne fausse est pire
  qu'absente** : elle a fait lire l'écart comme une décision.

  Signalé à l'écran le 12/09/2026 : *« quand on est en édition, il y a un bouton
  annuler qui apparaît en haut à droite — c'est hors standard UX »*. Et en
  édition, c'était pire encore : on n'annule pas une création qui n'a pas lieu.

  ## Pourquoi le composant SUBSISTE malgré tout

  Il reste la bonne réponse à ce qu'il a été créé pour corriger : sur les quatre
  onglets de Prestataires, deux affichaient « + Nouveau contrat » **avec le
  formulaire déjà ouvert**. Le geste s'écrivait à la main sur chaque écran, et
  c'est ce qui produisait la divergence.

  Tickets et Actualités écrivaient le leur à la main — deuxième et troisième
  écriture du même bouton, avec le même commentaire recopié. Ils passent par ici
  depuis le 12/09 : le comportement n'y change pas d'un pixel, c'est l'écriture
  qui cesse d'être triple.

  `page-header-btn` et `btn btn-primary` viennent d'app.css : aucune règle locale
  ici, donc rien à faire suivre si le balisage bouge.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	/**  Le formulaire est-il ouvert ? Le bouton s'efface alors — il ne bascule
	 *   PAS en « ✕ Annuler » : le pied du formulaire porte déjà cette commande,
	 *   et deux annulations pour une saisie, c'est le défaut de #367. */
	export let ouvert = false;

	/** Libellé d'ouverture, SANS le « + » — ex. « Nouvelle prestation ». */
	export let libelle: string;

	const dispatch = createEventDispatcher<{ basculer: void }>();
</script>

{#if !ouvert}
	<button class="btn btn-primary page-header-btn" on:click={() => dispatch('basculer')}>
		+ {libelle}
	</button>
{/if}
