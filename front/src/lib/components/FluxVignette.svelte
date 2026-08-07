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

  Les pièces jointes NON-images (PDF, Word, tableur) suivent la même logique
  (07/08/2026) : une carte qui en portait ne le signalait par rien, alors qu'une
  carte avec photo le disait d'un coup d'œil. Deux cas, une seule place :

  - pas d'image mais des documents → une tuile de MÊME gabarit, trombone et
    décompte. Même emplacement, même taille : le rythme vertical du fil ne bouge
    pas, ce qui est toute la raison d'être de ce composant ;
  - image ET documents → la photo reste (elle informe davantage) et un petit
    trombone se pose dans l'angle. Deux tuiles côte à côte auraient déséquilibré
    la carte pour une information secondaire.

  ⚠️ Contrairement à la photo, cette tuile n'est PAS décorative : elle porte la
  seule mention de la pièce jointe dans l'état plié. Elle est donc annoncée aux
  lecteurs d'écran, là où l'image reste en `alt=""`.
-->
<script lang="ts">
	export let photos: string[] = [];
	export let image: string | null = null;
	export let size = 56;

	/** Pièces jointes non-images de l'élément (PDF, documents…). */
	export let fichiers: string[] = [];

	$: premiere = photos[0] ?? image ?? null;
	$: reste = Math.max(0, photos.length - 1);
	$: nbFichiers = fichiers.length;
	$: libelleFichiers = nbFichiers > 1 ? `${nbFichiers} pièces jointes` : '1 pièce jointe';
</script>

{#if premiere}
	<div class="flux-vignette" style="--taille:{size}px">
		<!-- alt vide : l'image est décorative ici, le titre de la carte porte déjà
		     l'information. L'annoncer une seconde fois alourdirait la lecture au
		     lecteur d'écran sans rien apprendre. La galerie dépliée, elle, est
		     décrite. -->
		<img src={premiere} alt="" loading="lazy" />
		{#if reste > 0}<span class="flux-vignette-compte">+{reste}</span>{/if}
		{#if nbFichiers > 0}
			<span class="flux-vignette-pj" title={libelleFichiers} aria-label={libelleFichiers}
				>📎{#if nbFichiers > 1}&nbsp;{nbFichiers}{/if}</span>
		{/if}
	</div>
{:else if nbFichiers > 0}
	<div class="flux-vignette flux-vignette-doc" style="--taille:{size}px"
		role="img" aria-label={libelleFichiers}>
		<span class="flux-vignette-doc-icone" aria-hidden="true">📎</span>
		{#if nbFichiers > 1}<span class="flux-vignette-compte">{nbFichiers}</span>{/if}
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
	/*  Tuile « documents » : même gabarit que la vignette photo, fond neutre.
	    Elle occupe la place d'une image absente, donc la carte garde sa hauteur. */
	.flux-vignette-doc {
		display: flex;
		align-items: center;
		justify-content: center;
		background: var(--color-surface-alt, #F4F5F7);
		border-style: dashed;
	}
	.flux-vignette-doc-icone { font-size: 1.35rem; line-height: 1; opacity: .75; }
	/*  Trombone posé sur une vignette photo : la photo prime, ceci n'est qu'un
	    rappel secondaire — d'où l'angle et la taille réduite. */
	.flux-vignette-pj {
		position: absolute;
		left: 3px;
		bottom: 3px;
		display: inline-flex;
		align-items: center;
		padding: 1px 4px;
		border-radius: 6px;
		background: rgba(0, 0, 0, .58);
		color: #FFF;
		font-size: .62rem;
		font-weight: 600;
		line-height: 1.35;
	}
	@media (max-width: 640px) {
		.flux-vignette { width: 48px; height: 48px; }
		.flux-vignette-doc-icone { font-size: 1.15rem; }
	}
</style>
