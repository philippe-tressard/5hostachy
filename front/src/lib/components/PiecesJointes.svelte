<!--
  Affichage en lecture seule d'une liste de pièces jointes : vignettes pour les
  images, liens nommés pour les documents.

  Ce bloc était réécrit à l'identique dans quatre pages (fiche ticket, actualité,
  espace CS, affaires) — avec à chaque fois sa propre expression régulière pour
  décider ce qui est une image, et son propre `split('/').pop()` pour le nom
  affiché. La règle vit désormais dans `$lib/fichiers.ts`, le rendu ici.

  Props :
    - urls   : liste d'URLs internes (/uploads/…)
    - size   : côté des vignettes en px
    - compact: réduit la typographie des liens (fils d'évolutions)
-->
<script lang="ts">
	import Vignette from './Vignette.svelte';
	import { nomFichier, separerFichiers } from '$lib/fichiers';

	export let urls: string[] | null | undefined = [];
	export let size = 72;
	export let compact = false;

	$: ({ photos, documents } = separerFichiers(urls));
</script>

{#if photos.length || documents.length}
	<div class="pj">
		{#if photos.length}
			<div class="pj-photos">
				{#each photos as url (url)}
					<a href={url} target="_blank" rel="noopener" aria-label="Ouvrir {nomFichier(url)}">
						<Vignette src={url} alt="" {size} title={nomFichier(url)} />
					</a>
				{/each}
			</div>
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

<style>
	.pj { display: flex; flex-direction: column; gap: .4rem; }
	.pj-photos { display: flex; gap: .5rem; flex-wrap: wrap; }
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
