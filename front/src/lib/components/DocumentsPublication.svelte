<!--
  Les documents d'une publication DÉJÀ créée : la liste, le retrait, l'ajout.

  Extrait de `FormulaireActualite` le 31/08/2026, sur refus du contrôle de
  modularité — et le contrôle désignait un placement, comme les quatre fois
  précédentes. Ce bloc ne parle pas du formulaire d'actualité : il parle de
  documents attachés à un objet qui existe, avec son identifiant.

  ⚠️ Il ne sert QU'EN CORRECTION. À la création, la publication n'a pas encore
  d'identifiant : les fichiers sont retenus par `ChampsCommuns` et téléversés
  après coup (`attacherAPublication`). Les deux régimes ne se ressemblent qu'en
  apparence — l'un manipule des `Document` avec un `id`, l'autre des `File`.

  🔴 Le style voyage AVEC le balisage qui l'emploie : un style laissé chez le
  parent n'atteint pas le balisage d'un enfant (v2.67.11).
-->
<script lang="ts">
	import { onMount } from 'svelte';

	import { documents as docsApi, ApiError } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { ACCEPT_DOCUMENTS, attacherAPublication, nomFichier } from '$lib/fichiers';

	/** L'identifiant de la publication — elle existe forcément ici. */
	export let publicationId: number;

	let docs: { id: number; titre?: string; fichier_nom?: string }[] = [];
	let enCours = false;

	onMount(async () => {
		try {
			docs = await docsApi.listByPublication(publicationId);
		} catch {
			/* la liste reste vide : l'ajout demeure possible */
		}
	});

	async function ajouter(e: Event) {
		const input = e.target as HTMLInputElement;
		if (!input.files?.length) return;
		enCours = true;
		try {
			docs = [...docs, ...(await attacherAPublication(publicationId, Array.from(input.files)))];
		} catch (err) {
			toast('error', err instanceof ApiError ? err.message : 'Téléversement impossible');
		} finally {
			enCours = false;
			input.value = '';
		}
	}

	async function retirer(id: number) {
		try {
			await docsApi.delete(id);
			docs = docs.filter((d) => d.id !== id);
		} catch (err) {
			toast('error', err instanceof ApiError ? err.message : 'Erreur');
		}
	}
</script>

{#if docs.length}
	<ul class="docs-liste">
		{#each docs as doc (doc.id)}
			<li>
				<span class="docs-nom">📎 {doc.titre || nomFichier(doc.fichier_nom ?? '')}</span>
				<button
					type="button"
					class="btn-icon-danger"
					aria-label="Retirer ce document"
					title="Retirer ce document"
					on:click={() => retirer(doc.id)}>🗑️</button
				>
			</li>
		{/each}
	</ul>
{/if}
<label class="btn btn-outline btn-sm docs-ajout">
	{enCours ? 'Téléversement…' : '+ Ajouter un document'}
	<input type="file" multiple accept={ACCEPT_DOCUMENTS} disabled={enCours} on:change={ajouter} />
</label>

<style>
	.docs-liste {
		list-style: none;
		margin: 0 0 0.6rem;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
	}
	.docs-liste li {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-size: 0.85rem;
	}
	.docs-nom {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.docs-ajout {
		display: inline-flex;
		cursor: pointer;
	}
	.docs-ajout input[type='file'] {
		display: none;
	}
</style>
