<!--
  Visionneuse plein écran — regarder une photo sans quitter l'application.

  Avant, une photo cliquée s'ouvrait via `<a target="_blank">` : on sortait de la
  PWA vers un onglet brut, et le retour ramenait sur une page dont l'article
  s'était refermé. Sur mobile, c'était le geste le plus coûteux de l'écran.

  Les photos sont déjà réduites à 1600 px au téléversement (`uploads._save_image`),
  il n'existe aucune miniature : le fichier affiché ici est celui que la vignette
  avait déjà téléchargé. Ouvrir en grand ne coûte donc aucun octet de plus.

  Props :
    - photos : URLs à parcourir
    - index  : photo affichée à l'ouverture
  Événement : `fermer`
-->
<script lang="ts">
	import { createEventDispatcher, onDestroy } from 'svelte';

	export let photos: string[] = [];
	export let index = 0;

	const dispatch = createEventDispatcher();

	//  Le défilement du fond est un état PARTAGÉ : s'il n'était pas restauré, la
	//  page entière resterait bloquée jusqu'au rechargement (standards/11 §12).
	//  D'où une fonction idempotente, appelée depuis chaque sortie — fermeture,
	//  touche Échap, clic sur le fond — ET depuis `onDestroy`, car l'utilisateur
	//  peut naviguer ailleurs sans jamais fermer la visionneuse.
	let defilementBloque = false;

	function bloquerDefilement() {
		if (defilementBloque || typeof document === 'undefined') return;
		document.body.style.overflow = 'hidden';
		defilementBloque = true;
	}

	function restaurerDefilement() {
		if (!defilementBloque || typeof document === 'undefined') return;
		document.body.style.overflow = '';
		defilementBloque = false;
	}

	function fermer() {
		restaurerDefilement();
		dispatch('fermer');
	}

	function precedente() {
		index = (index - 1 + photos.length) % photos.length;
	}

	function suivante() {
		index = (index + 1) % photos.length;
	}

	function auClavier(e: KeyboardEvent) {
		if (e.key === 'Escape') fermer();
		else if (e.key === 'ArrowLeft' && photos.length > 1) precedente();
		else if (e.key === 'ArrowRight' && photos.length > 1) suivante();
	}

	//  Le blocage est posé au montage et non dans un `on:click` : la visionneuse
	//  peut être ouverte au clavier comme à la souris.
	bloquerDefilement();
	onDestroy(restaurerDefilement);
</script>

<svelte:window on:keydown={auClavier} />

<div
	class="lb-fond"
	role="dialog"
	aria-modal="true"
	aria-label="Photo en plein écran"
	tabindex="-1"
	on:click={(e) => e.target === e.currentTarget && fermer()}
	on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && e.target === e.currentTarget && fermer()}
>
	<button class="lb-fermer" aria-label="Fermer la photo" on:click|stopPropagation={fermer}>×</button>

	{#if photos.length > 1}
		<button class="lb-nav lb-prec" aria-label="Photo précédente" on:click|stopPropagation={precedente}>‹</button>
		<button class="lb-nav lb-suiv" aria-label="Photo suivante" on:click|stopPropagation={suivante}>›</button>
	{/if}

	<!-- Aucun écouteur sur l'image : la fermeture ne se déclenche que si la cible
	     du clic est le fond LUI-MÊME (`e.target === e.currentTarget`). Cliquer la
	     photo ne referme donc pas, sans avoir à poser un `stopPropagation` sur un
	     élément non interactif — ce que l'analyse d'accessibilité refuse à juste
	     titre : un lecteur d'écran annoncerait une image cliquable qui n'est pas
	     une commande. -->
	<img class="lb-image" src={photos[index]} alt="Photo {index + 1} sur {photos.length}" />

	{#if photos.length > 1}
		<p class="lb-compteur">{index + 1} / {photos.length}</p>
	{/if}
</div>

<style>
	.lb-fond {
		position: fixed;
		inset: 0;
		z-index: 200;
		background: rgba(0, 0, 0, .88);
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 1rem;
	}
	.lb-image {
		max-width: 100%;
		max-height: 92vh;
		object-fit: contain;
		border-radius: 4px;
		cursor: default;
	}
	.lb-fermer,
	.lb-nav {
		position: absolute;
		background: rgba(0, 0, 0, .45);
		color: #fff;
		border: none;
		border-radius: 50%;
		cursor: pointer;
		line-height: 1;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	/*  44 px partout : cible tactile minimale (standards/11 §10). Le bouton de
	    fermeture était à 40 px — mesuré en vérification mobile, donc corrigé. Sur
	    téléphone, c'est le bouton le plus utilisé de cet écran. */
	.lb-fermer {
		top: 1rem;
		right: 1rem;
		width: 44px;
		height: 44px;
		font-size: 1.6rem;
	}
	.lb-nav {
		top: 50%;
		transform: translateY(-50%);
		width: 44px;
		height: 44px;
		font-size: 2rem;
	}
	.lb-prec { left: .75rem; }
	.lb-suiv { right: .75rem; }
	.lb-fermer:hover,
	.lb-nav:hover { background: rgba(0, 0, 0, .75); }
	.lb-compteur {
		position: absolute;
		bottom: 1rem;
		left: 50%;
		transform: translateX(-50%);
		margin: 0;
		color: #fff;
		font-size: .85rem;
		background: rgba(0, 0, 0, .45);
		padding: .2rem .7rem;
		border-radius: 999px;
	}
</style>
