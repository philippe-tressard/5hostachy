<!--
  Aperçu d'une actualité repliée : les cinq premières lignes du texte, et la
  vignette de sa photo à droite.

  Pourquoi un composant pour si peu : le fil principal et la section Historique
  de `/actualites` affichent le même aperçu, et le rendaient chacun de leur côté.
  Le 15/08/2026 (#351), il a fallu leur ajouter la vignette — deux fois, au même
  moment, exactement le geste qui finit par diverger le jour où l'on ne pense
  qu'à l'un des deux.

  Le placement suit `ux-patterns` §11 : vignette là où l'on survole, grand format
  là où l'on a demandé à voir. La vignette est à DROITE, comme dans le fil
  d'activité — la gauche porte déjà le bord coloré de la carte.

  ⚠️ Seules les PHOTOS sont connues à ce stade. Les documents joints ne sont
  chargés qu'au dépliage : les compter ici coûterait une requête par carte pour
  afficher un trombone.
-->
<script lang="ts">
	import FluxVignette from '$lib/components/FluxVignette.svelte';
	import { safeHtml } from '$lib/sanitize';

	/** Contenu HTML de la publication (assaini avant rendu). */
	export let contenu: string;
	/** URLs des photos ; la première sert de vignette. */
	export let photos: string[] = [];
</script>

<div class="pub-apercu">
	<div class="pub-preview rich-content clamp-5">{@html safeHtml(contenu)}</div>
	<FluxVignette {photos} />
</div>

<style>
	/*  `min-width:0` : sans lui un enfant flex ne rétrécit pas sous la largeur de
	    son contenu, et le `-webkit-line-clamp` de .clamp-5 n'est jamais appliqué. */
	.pub-apercu { display: flex; align-items: flex-start; gap: .75rem; padding-right: 1rem; }
	.pub-apercu .pub-preview { flex: 1; min-width: 0; padding-right: 0; }
	.pub-preview { padding: .4rem 1rem .6rem; font-size: .875rem; line-height: 1.6; color: var(--color-text-muted); }
	.pub-preview :global(p) { margin: 0 0 .4em; }
</style>
