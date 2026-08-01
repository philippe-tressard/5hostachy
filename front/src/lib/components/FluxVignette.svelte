<!--
  Vignette d'aperçu d'une carte du fil d'activité (état PLIÉ).

  Pourquoi une vignette carrée à droite, et pas une bannière pleine largeur :
  le fil est une chronologie dense, où chaque carte doit garder la même hauteur
  pour que l'œil descende sans à-coups. Une image pleine largeur ferait sauter le
  rythme et écraserait les cartes sans photo. Une vignette signale « il y a une
  image » sans rien déplacer.

  Pourquoi à DROITE : la gauche porte déjà l'icône de type (📌, 🔨, 📰). Y ajouter
  l'image créerait deux ancres visuelles en concurrence sur la même colonne.

  Le composant sert toutes les rubriques : événements et tickets (plusieurs
  photos → pastille « +N »), publications (une illustration). Le fil n'a donc
  qu'une implémentation d'aperçu, quelle que soit la nature de l'élément.
-->
<script lang="ts">
	export let photos: string[] = [];
	export let image: string | null = null;
	export let size = 56;

	$: premiere = photos[0] ?? image ?? null;
	$: reste = Math.max(0, photos.length - 1);
</script>

{#if premiere}
	<div class="flux-vignette" style="--taille:{size}px">
		<!-- alt vide : l'image est décorative ici, le titre de la carte porte déjà
		     l'information. L'annoncer une seconde fois alourdirait la lecture au
		     lecteur d'écran sans rien apprendre. La galerie dépliée, elle, est
		     décrite. -->
		<img src={premiere} alt="" loading="lazy" />
		{#if reste > 0}<span class="flux-vignette-compte">+{reste}</span>{/if}
	</div>
{/if}

<style>
	.flux-vignette {
		position: relative;
		width: var(--taille);
		height: var(--taille);
		flex-shrink: 0;
		border-radius: 8px;
		overflow: hidden;
		border: 1px solid var(--color-border);
		background: var(--color-bg-alt, #f2f2f2);
	}
	.flux-vignette img {
		width: 100%;
		height: 100%;
		object-fit: cover;
		display: block;
	}
	.flux-vignette-compte {
		position: absolute;
		right: 2px;
		bottom: 2px;
		padding: 0 .3rem;
		border-radius: 6px;
		background: rgba(0, 0, 0, .62);
		color: #fff;
		font-size: .68rem;
		font-weight: 600;
		line-height: 1.35;
	}
	@media (max-width: 640px) {
		.flux-vignette { width: 48px; height: 48px; }
	}
</style>
