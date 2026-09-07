<!--
  Aperçu d'une carte repliée : les cinq premières lignes du texte, et la vignette
  de sa photo à droite. Sert les actualités ET les tickets — d'où le nom neutre :
  un composant partagé qui porte le nom d'une seule rubrique finit par être
  recopié plutôt que réutilisé.

  Pourquoi un composant pour si peu : quatre listes affichent le même aperçu —
  actualités (fil + historique) et tickets (fil + archives) — et le rendaient
  chacune de leur côté. Le 15/08/2026, il a fallu leur ajouter la vignette : deux
  fois d'abord (#351), puis deux autres quand l'utilisateur a constaté que les
  tickets n'en avaient pas. Exactement le geste qui finit par diverger le jour où
  l'on ne pense qu'à l'un des quatre.

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
	import { safeDescription } from '$lib/sanitize';

	/**  Contenu de l'élément, brut. `safeDescription` l'assainit ET enveloppe le
	 *   texte non-HTML dans un paragraphe : les descriptions de tickets sont parfois
	 *   du texte simple, dont `safeHtml` seul perdrait les retours à la ligne. */
	export let contenu: string;
	/** URLs des photos ; la première sert de vignette. */
	export let photos: string[] = [];
	/**  Documents joints, quand l'écran les connaît déjà. `FluxVignette` rend
	 *   alors une tuile 📎 plutôt que rien.
	 *
	 *   ⚠️ NE PAS les verser dans `photos` : la vignette prend `photos[0]` et le
	 *   pose dans un `<img>`. Un événement dont la seule pièce est un devis PDF
	 *   sortait donc en image cassée — c'est ce que faisait `CarteEvenement`.
	 *
	 *   Les ACTUALITÉS n'en passent pas : leurs documents sont des entités
	 *   `Document` chargées au dépliage, et les compter ici coûterait une requête
	 *   par carte pour afficher un trombone. */
	export let fichiers: string[] = [];

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

<div class="carte-apercu">
	<div class="carte-preview rich-content clamp-5" class:tronque bind:this={bloc}>
		{@html safeDescription(contenu)}
	</div>
	<FluxVignette {photos} {fichiers} />
</div>

<style>
	/*  `min-width:0` : sans lui un enfant flex ne rétrécit pas sous la largeur de
	    son contenu, et le `-webkit-line-clamp` de .clamp-5 n'est jamais appliqué. */
	.carte-apercu {
		display: flex;
		align-items: flex-start;
		gap: 0.85rem;
		padding: 0 0.95rem 0.85rem;
	}
	.carte-apercu .carte-preview {
		flex: 1;
		min-width: 0;
	}
	.carte-preview {
		font-size: 0.875rem;
		line-height: 1.6;
		color: var(--color-text-muted);
		position: relative;
	}
	.carte-preview :global(p) {
		margin: 0 0 0.4em;
	}

	/*  Le texte tronqué était coupé NET au ras du bord : rien ne disait s'il
	    continuait ou si la carte s'arrêtait là, et deux cartes voisines formaient
	    un pavé continu. Le dégradé le dit, sans ajouter ni bouton ni libellé.
	    `pointer-events:none` : il couvre le texte, il ne doit pas manger le clic
	    qui déplie la carte. */
	.carte-preview.tronque::after {
		content: '';
		position: absolute;
		left: 0;
		right: 0;
		bottom: 0;
		height: 2.2em;
		pointer-events: none;
		background: linear-gradient(to bottom, transparent, var(--color-surface));
	}

	@media (max-width: 640px) {
		.carte-apercu {
			padding: 0 0.75rem 0.7rem;
			gap: 0.6rem;
		}
	}
</style>
