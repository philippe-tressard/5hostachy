<!--
  Galerie de photos éditable (sélection multiple + suppression), bâtie sur Vignette.
  Le téléversement est délégué à l'appelant : chaque rubrique conserve son endpoint
  (fichier générique, photo d'annonce…) sans dupliquer l'UI.

  Props :
    - urls     : liste des URLs (bindable)
    - max      : nombre maximum de photos
    - size     : côté des vignettes en px
    - label    : libellé du bouton d'ajout
    - readonly : affichage seul (ni ajout ni suppression)
    - upload   : (file) => Promise<url> — obligatoire hors readonly
    - remove   : (url) => Promise<url[] | void> — suppression serveur optionnelle ;
                 si elle retourne une liste, elle fait foi
    - accept   : types MIME acceptés
  Events :
    - change(detail: string[]) — après ajout ou suppression
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import Vignette from './Vignette.svelte';
	import { toast } from './Toast.svelte';

	export let urls: string[] = [];
	export let max = 4;
	export let size = 72;
	export let label = 'Photo';
	export let readonly = false;
	export let upload: ((file: File) => Promise<string>) | null = null;
	export let remove: ((url: string) => Promise<string[] | void>) | null = null;
	export let accept = 'image/jpeg,image/png,image/webp';

	const dispatch = createEventDispatcher<{ change: string[] }>();

	let uploading = false;

	$: complet = urls.length >= max;

	async function ajouter(e: Event) {
		const input = e.target as HTMLInputElement;
		const file = input.files?.[0];
		input.value = '';
		if (!file || !upload || complet) return;
		uploading = true;
		try {
			const url = await upload(file);
			urls = [...urls, url];
			dispatch('change', urls);
		} catch (err) {
			toast('error', err instanceof Error ? err.message : "Erreur lors de l'envoi de la photo");
		} finally {
			uploading = false;
		}
	}

	async function retirer(url: string) {
		try {
			const maj = remove ? await remove(url) : null;
			urls = Array.isArray(maj) ? maj : urls.filter((u) => u !== url);
			dispatch('change', urls);
		} catch (err) {
			toast('error', err instanceof Error ? err.message : 'Erreur lors de la suppression');
		}
	}
</script>

<div class="photos-upload">
	{#if urls.length}
		<div class="photos-row">
			{#each urls as url (url)}
				<Vignette src={url} alt="" {size}>
					{#if !readonly}
						<button type="button" class="btn-photo-del" title="Retirer cette photo"
							aria-label="Retirer cette photo" on:click={() => retirer(url)}>×</button>
					{/if}
				</Vignette>
			{/each}
		</div>
	{/if}

	{#if !readonly && upload}
		<label class="btn btn-sm btn-outline photos-add" class:disabled={complet || uploading}>
			{uploading ? '⏳ Envoi…' : `&#x1F4F7; ${label}`}
			<input type="file" {accept} disabled={complet || uploading} on:change={ajouter} />
		</label>
		<span class="photos-compte">{urls.length}/{max}</span>
	{/if}
</div>

<style>
	.photos-upload { display: flex; flex-direction: column; gap: .5rem; align-items: flex-start; }
	.photos-row { display: flex; gap: .5rem; flex-wrap: wrap; }
	.photos-add {
		cursor: pointer;
		display: inline-flex;
		align-items: center;
		gap: .3rem;
	}
	.photos-add.disabled { opacity: .5; cursor: default; }
	.photos-add input { display: none; }
	.photos-compte { font-size: .72rem; color: var(--color-text-muted); }
	.btn-photo-del {
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
</style>
