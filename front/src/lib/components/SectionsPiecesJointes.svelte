<!--
  Les sections **7. Photos** et **8. Documents** du cadre, écrites une fois.

  Elles l'étaient deux fois : `ChampsCommuns` (six formulaires de création) et
  `EvolForm` (le fil de quatre entités). La section Photos y était **identique au
  caractère près** — même intitulé, même `champ-large`, même `size={80}` — et
  celle des Documents ne différait que par le régime de téléversement.

  🔴 **Deux sections, jamais une seule** (cadre #430) : même voisines, même
  courtes, même vides. Les fusionner créerait une dixième section que rien ne
  déclare. C'est pour cela que ce composant en rend deux et ne les mélange pas.

  ⚠️ Le régime de téléversement est un **paramètre de l'objet**, il ne
  s'uniformise pas : une publication manipule des `Document` avec un identifiant
  (l'écran fournit alors son propre contrôle par le créneau `documents`), une
  évolution ne connaît qu'une liste d'URLs. Ce qui s'uniformise, c'est la
  SECTION — son rang, son intitulé, sa séparation.
-->
<script lang="ts">
	import FichiersUpload from '$lib/components/FichiersUpload.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import { ACCEPT_PHOTOS } from '$lib/fichiers';

	/** Préfixe des identifiants — l'écran en ouvre parfois plusieurs à la fois. */
	export let idPrefixe: string;

	export let avecPhotos = false;
	export let photos: string[] = [];

	export let avecDocuments = false;
	export let documents: string[] = [];
	/**  `'interne'` : la liste d'URLs ci-dessus · `'slot'` : l'écran fournit son
	 *   propre contrôle (documents d'une publication, qui ont un identifiant). */
	export let documentsControle: 'interne' | 'slot' = 'interne';
	/** Téléversement différé — les fichiers attendent que l'objet existe. */
	export let documentsDifferes = false;
	export let documentsFichiers: File[] = [];
	/**  Le suffixe d'identifiant des documents. ⚠️ Il diffère entre les deux
	 *   appelants (`-documents` et `-docs`) : le figer casserait le `for` d'un
	 *   libellé existant, ce que `lint:labels` refuse à juste titre. */
	export let idDocuments = 'documents';
</script>

{#if avecPhotos}
	<SectionFormulaire titre="Photos" pour="{idPrefixe}-photos">
		<div class="field champ-large">
			<FichiersUpload
				id="{idPrefixe}-photos"
				bind:urls={photos}
				titre=""
				label="Ajouter une photo"
				accept={ACCEPT_PHOTOS}
				size={80}
			/>
		</div>
	</SectionFormulaire>
{/if}

{#if avecDocuments}
	<SectionFormulaire titre="Documents" pour="{idPrefixe}-{idDocuments}">
		<div class="field champ-large">
			{#if documentsControle === 'slot'}
				<slot name="documents" />
			{:else}
				<FichiersUpload
					id="{idPrefixe}-{idDocuments}"
					mode="documents"
					titre=""
					differe={documentsDifferes}
					bind:urls={documents}
					bind:fichiers={documentsFichiers}
				/>
			{/if}
		</div>
	</SectionFormulaire>
{/if}
