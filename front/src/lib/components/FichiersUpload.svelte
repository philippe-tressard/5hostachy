<!--
  Saisie de pièces jointes : liste retirable + bouton d'ajout. Les images
  s'affichent en vignettes, les documents en pastilles nommées — c'est `accept`
  qui décide de ce qu'on peut ajouter, pas le rendu.

  Pendant de `PhotosUpload.svelte`, qui reste le composant des rubriques dont les
  photos ont leur propre endpoint (avatar, résidence, annonces).

  Contrairement à `PhotosUpload`, le téléversement n'est PAS délégué à
  l'appelant : les documents n'ont qu'un seul endpoint (`POST /uploads/fichier`,
  qui valide le type MIME), là où chaque rubrique a le sien pour les photos.
  Un point d'entrée unique, donc pas de prop `upload` à recopier par page.

  Le fichier est téléversé immédiatement — avant même que l'élément parent
  existe — et l'URL obtenue part dans le `fichiers_urls` de la création. C'est ce
  qui permet à un ticket envoyé au syndic de partir avec ses documents joints,
  ce que le flux « créer puis téléverser » des photos ne permet pas.

  Props :
    - urls     : liste des URLs (bindable)
    - max      : nombre maximum de documents
    - label    : libellé du bouton d'ajout
    - accept   : filtre du sélecteur de fichiers
    - id       : posé sur l'input, pour qu'un `<label for="…">` le désigne
    - disabled : désactive l'ajout
  Events :
    - change(detail: string[]) — après ajout ou retrait
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import Vignette from './Vignette.svelte';
	import { fichiersApi } from '$lib/api';
	import { toast } from './Toast.svelte';
	import { ACCEPT_DOCUMENTS, nomFichier, separerFichiers } from '$lib/fichiers';

	export let urls: string[] = [];
	export let max = 5;
	export let label = 'Ajouter un document';
	export let accept = ACCEPT_DOCUMENTS;
	export let id: string | undefined = undefined;
	export let disabled = false;
	/** Côté des vignettes d'image, en px. */
	export let size = 64;

	const dispatch = createEventDispatcher<{ change: string[] }>();

	let envoi = false;

	$: complet = urls.length >= max;
	$: ({ photos, documents } = separerFichiers(urls));

	async function ajouter(e: Event) {
		const input = e.target as HTMLInputElement;
		const fichiers = Array.from(input.files ?? []);
		input.value = '';
		if (!fichiers.length || complet) return;
		envoi = true;
		try {
			for (const file of fichiers.slice(0, max - urls.length)) {
				const r = await fichiersApi.upload(file);
				urls = [...urls, r.url];
			}
			dispatch('change', urls);
		} catch (err) {
			toast('error', err instanceof Error ? err.message : "Erreur lors de l'envoi du document");
		} finally {
			envoi = false;
		}
	}

	function retirer(url: string) {
		urls = urls.filter((u) => u !== url);
		dispatch('change', urls);
	}
</script>

<div class="fichiers-upload">
	{#if photos.length}
		<div class="fichiers-liste">
			{#each photos as url (url)}
				<Vignette src={url} alt="" {size} title={nomFichier(url)}>
					<button type="button" class="photo-retirer" title="Retirer cette photo"
						aria-label="Retirer {nomFichier(url)}" on:click={() => retirer(url)}>×</button>
				</Vignette>
			{/each}
		</div>
	{/if}
	{#if documents.length}
		<div class="fichiers-liste">
			{#each documents as url (url)}
				<span class="fichier-chip">
					<span aria-hidden="true">&#x1F4C4;</span>
					<span class="fichier-nom">{nomFichier(url)}</span>
					<button type="button" class="fichier-retirer" title="Retirer ce document"
						aria-label="Retirer {nomFichier(url)}" on:click={() => retirer(url)}>×</button>
				</span>
			{/each}
		</div>
	{/if}

	<label class="btn btn-sm btn-outline fichiers-ajout" class:disabled={complet || envoi || disabled}>
		{envoi ? '⏳ Envoi…' : `\u{1F4CE} ${label}`}
		<input {id} type="file" multiple {accept} disabled={complet || envoi || disabled} on:change={ajouter} />
	</label>
	<span class="fichiers-compte">{urls.length}/{max}</span>
</div>

<style>
	.fichiers-upload { display: flex; flex-direction: column; gap: .5rem; align-items: flex-start; }
	.fichiers-liste { display: flex; gap: .35rem; flex-wrap: wrap; }
	.fichier-chip {
		display: inline-flex;
		align-items: center;
		gap: .3rem;
		max-width: 100%;
		padding: .2rem .45rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-bg-alt, #f5f5f5);
		font-size: .8rem;
	}
	.fichier-nom {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		max-width: 200px;
	}
	.fichier-retirer {
		border: none;
		background: none;
		color: var(--color-danger);
		cursor: pointer;
		font-size: 1rem;
		line-height: 1;
		padding: 0;
	}
	.photo-retirer {
		position: absolute;
		top: 2px;
		right: 2px;
		background: rgba(0, 0, 0, .6);
		color: #fff;
		border: none;
		border-radius: 50%;
		width: 18px;
		height: 18px;
		font-size: .75rem;
		cursor: pointer;
		line-height: 1;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.fichiers-ajout { cursor: pointer; display: inline-flex; align-items: center; gap: .3rem; }
	.fichiers-ajout.disabled { opacity: .5; cursor: default; }
	.fichiers-ajout input { display: none; }
	.fichiers-compte { font-size: .72rem; color: var(--color-text-muted); }
	@media (max-width: 480px) {
		.fichier-nom { max-width: 58vw; }
	}
</style>
