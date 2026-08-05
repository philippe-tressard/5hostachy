<!--
  Affichage en lecture seule d'une liste de pièces jointes : vignettes pour les
  images, liens nommés pour les documents.

  Ce bloc était réécrit à l'identique dans quatre pages (fiche ticket, actualité,
  espace CS, affaires) — avec à chaque fois sa propre expression régulière pour
  décider ce qui est une image, et son propre `split('/').pop()` pour le nom
  affiché. La règle vit désormais dans `$lib/fichiers.ts`, le rendu ici.

  Props :
    - urls   : liste d'URLs internes (/uploads/…)
    - size   : côté des vignettes en px (format « vignette » uniquement)
    - compact: réduit la typographie des liens (fils d'évolutions)
    - format : « vignette » (aperçu) ou « grand » (contenu déplié)

  Deux formats, parce que la vignette ne répond pas à la même question. Dans une
  liste ou un fil d'évolutions, elle signale « il y a une photo » sans casser le
  rythme de lecture. Une fois le contenu déplié, l'utilisateur a demandé à voir :
  lui laisser un timbre-poste de 72 px l'oblige à un clic de plus pour ce qu'il
  vient justement de demander.

  Le format « grand » ne coûte aucun octet supplémentaire : il n'existe pas de
  miniature côté serveur, les photos sont réduites à 1600 px au téléversement, et
  la vignette téléchargeait déjà ce fichier-là pour l'afficher en 72 px.

  `object-fit: contain` en grand format, et non `cover` : une photo portrait
  affichée dans un cadre carré perd ses bords haut et bas. Sur un dégât des eaux,
  c'est précisément ce qu'on cherchait à montrer.
-->
<script lang="ts">
	import Lightbox from './Lightbox.svelte';
	import Vignette from './Vignette.svelte';
	import { nomFichier, separerFichiers } from '$lib/fichiers';

	export let urls: string[] | null | undefined = [];
	export let size = 72;
	export let compact = false;
	export let format: 'vignette' | 'grand' = 'vignette';

	$: ({ photos, documents } = separerFichiers(urls));

	//  null = visionneuse fermée. Le clic n'ouvre plus un onglet : il ouvrait le
	//  fichier brut hors de la PWA, et le retour ramenait sur un article refermé.
	let photoOuverte: number | null = null;
</script>

{#if photos.length || documents.length}
	<div class="pj">
		{#if photos.length}
			{#if format === 'grand'}
				<div class="pj-grandes">
					{#each photos as url, i (url)}
						<button
							type="button"
							class="pj-grande"
							aria-label="Agrandir {nomFichier(url)}"
							on:click|stopPropagation={() => (photoOuverte = i)}
						>
							<img src={url} alt={nomFichier(url)} loading="lazy" />
						</button>
					{/each}
				</div>
			{:else}
				<div class="pj-photos">
					{#each photos as url, i (url)}
						<button
							type="button"
							class="pj-vignette"
							aria-label="Agrandir {nomFichier(url)}"
							on:click|stopPropagation={() => (photoOuverte = i)}
						>
							<Vignette src={url} alt="" {size} title={nomFichier(url)} />
						</button>
					{/each}
				</div>
			{/if}
		{/if}
		{#if documents.length}
			<div class="pj-docs">
				{#each documents as url (url)}
					<a class="pj-doc" class:pj-doc-compact={compact} href={url} target="_blank" rel="noopener">
						<span aria-hidden="true">&#x1F4C4;</span>
						<span class="pj-doc-nom">{nomFichier(url)}</span>
					</a>
				{/each}
			</div>
		{/if}
	</div>
{/if}

{#if photoOuverte !== null}
	<Lightbox {photos} index={photoOuverte} on:fermer={() => (photoOuverte = null)} />
{/if}

<style>
	.pj { display: flex; flex-direction: column; gap: .4rem; }
	.pj-photos { display: flex; gap: .5rem; flex-wrap: wrap; }

	/*  Boutons et non liens : l'action reste dans la page. Le style par défaut du
	    bouton est neutralisé pour que seule la photo se voie. */
	.pj-vignette,
	.pj-grande {
		padding: 0;
		border: none;
		background: none;
		cursor: zoom-in;
		display: block;
		line-height: 0;
	}
	.pj-grandes { display: flex; flex-direction: column; gap: .5rem; }
	.pj-grande { width: 100%; }
	.pj-grande img {
		width: 100%;
		/*  Plafond de hauteur : une photo portrait 1200×1600 affichée pleine
		    largeur occuperait deux écrans sur mobile et repousserait commentaires
		    et actions hors de vue. `contain` préserve les proportions. */
		max-height: 60vh;
		object-fit: contain;
		border-radius: var(--radius);
		border: 1px solid var(--color-border);
		background: var(--color-bg-alt, #f5f5f5);
	}
	.pj-docs { display: flex; gap: .35rem; flex-wrap: wrap; }
	.pj-doc {
		display: inline-flex;
		align-items: center;
		gap: .3rem;
		max-width: 100%;
		padding: .2rem .5rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-bg-alt, #f5f5f5);
		color: var(--color-primary);
		font-size: .82rem;
		text-decoration: none;
	}
	.pj-doc-compact { font-size: .75rem; }
	.pj-doc:hover { border-color: var(--color-primary); }
	/* Un nom long ne doit pas pousser la carte hors de l'écran sur mobile. */
	.pj-doc-nom {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		max-width: 220px;
	}
	@media (max-width: 480px) {
		.pj-doc-nom { max-width: 62vw; }
	}
</style>
