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
	import { onMount } from 'svelte';
	import { safeHtml } from '$lib/sanitize';

	/** Contenu HTML de la publication (assaini avant rendu). */
	export let contenu: string;
	/** URLs des photos ; la première sert de vignette. */
	export let photos: string[] = [];

	//  Le dégradé de fin ne doit apparaître QUE si le texte est réellement coupé.
	//  Appliqué sans condition, il efface la dernière ligne d'un aperçu court —
	//  constaté à l'écran : un texte de deux lignes devenait illisible, et le
	//  dégradé annonçait une suite qui n'existait pas. Aucun sélecteur CSS ne sait
	//  dire « ce texte déborde », d'où cette mesure après rendu.
	let bloc: HTMLElement;
	let tronque = false;
	onMount(() => {
		if (bloc) tronque = bloc.scrollHeight > bloc.clientHeight + 1;
	});
</script>

<div class="pub-apercu">
	<div class="pub-preview rich-content clamp-5" class:tronque bind:this={bloc}>{@html safeHtml(contenu)}</div>
	<FluxVignette {photos} />
</div>

<style>
	/*  `min-width:0` : sans lui un enfant flex ne rétrécit pas sous la largeur de
	    son contenu, et le `-webkit-line-clamp` de .clamp-5 n'est jamais appliqué. */
	.pub-apercu { display: flex; align-items: flex-start; gap: .85rem; padding: 0 .95rem .85rem; }
	.pub-apercu .pub-preview { flex: 1; min-width: 0; }
	.pub-preview { font-size: .875rem; line-height: 1.6; color: var(--color-text-muted); position: relative; }
	.pub-preview :global(p) { margin: 0 0 .4em; }

	/*  Le texte tronqué était coupé NET au ras du bord : rien ne disait s'il
	    continuait ou si la carte s'arrêtait là, et deux cartes voisines formaient
	    un pavé continu. Le dégradé le dit, sans ajouter ni bouton ni libellé.
	    `pointer-events:none` : il couvre le texte, il ne doit pas manger le clic
	    qui déplie la carte. */
	.pub-preview.tronque::after {
		content: "";
		position: absolute;
		left: 0; right: 0; bottom: 0;
		height: 2.2em;
		pointer-events: none;
		background: linear-gradient(to bottom, transparent, var(--color-surface));
	}

	@media (max-width: 640px) {
		.pub-apercu { padding: 0 .75rem .7rem; gap: .6rem; }
	}
</style>
