<!--
  La section **Pièces jointes** du cadre, écrite une fois.

  Elle l'était deux fois : `ChampsCommuns` (six formulaires de création) et
  `EvolForm` (le fil de quatre entités), à l'identique au caractère près.

  ## 🔴 UNE section depuis le 21/09/2026 (#1095), deux auparavant

  Le cadre #430 disait, en rouge : *« Deux sections, jamais une seule […] les
  fusionner créerait une dixième section que rien ne déclare. »* **L'utilisateur
  a tranché l'inverse le 20/09/2026** : une seule section, photos et/ou
  documents.

  ⚠️ Et la clause du cadre a été réécrite dans le MÊME lot (`entites/types.ts`),
  sinon elle réclamerait encore la séparation qu'on vient d'abandonner — et
  quelqu'un la rétablirait de bonne foi. Ce n'est pas la règle qui s'assouplit,
  c'est la TABLE qui a changé : la fusion se déclare, donc elle se contrôle.

  ## Une section, deux réservoirs — et c'est le serveur qui l'impose

  Le régime de téléversement est un **paramètre de l'objet** : une publication
  manipule des `Document` avec un identifiant (l'écran fournit alors son propre
  contrôle par le créneau `documents`), une évolution ne connaît qu'une liste
  d'URLs. Le modèle distingue `photos_urls` et les `Document`, et ce lot ne
  touche pas au modèle.

  Ce qui s'uniformise est la SECTION — son rang, son intitulé unique, et le fait
  que **tout fichier y porte un nom affiché**.

  🔴 **Le gain demandé** (20/09/2026) : le champ « nom affiché » vaut désormais
  pour une photo comme pour un PDF. Il ne coûte aucune migration — `avecLibelle`
  renomme le FICHIER avant l'envoi (`FichiersUpload.renommer`), il ne dépend
  d'aucune colonne.
-->
<script lang="ts">
	import FichiersUpload from '$lib/components/FichiersUpload.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import { SECTIONS_LIBELLE } from '$lib/entites/types';
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
	/**  Le libellé que l'auteur donne au document — vide, c'est le nom du fichier
	 *   qui sert. L'appelant le lit au moment d'envoyer (même règle de repli que
	 *   les contrats : `libelle.trim() || fichier.name`). */
	export let documentsLibelle = '';
	/**  Le même, pour une photo (#1095). **Distinct** de `documentsLibelle` et ce
	 *   n'est pas un détail : partagé, taper un nom pour une photo écraserait
	 *   celui d'un document en attente, dans la même section et sous les yeux de
	 *   l'auteur. */
	export let photosLibelle = '';
	/**  Le suffixe d'identifiant des documents. ⚠️ Il diffère entre les deux
	 *   appelants (`-documents` et `-docs`) : le figer casserait le `for` d'un
	 *   libellé existant, ce que `lint:labels` refuse à juste titre. */
	export let idDocuments = 'documents';
</script>

<!--  ⚠️ L'intitulé ne s'écrit PAS ici : il vient de `SECTIONS_LIBELLE`, où la
      table le déclare une fois. L'écrire en dur rouvrirait la divergence que
      `lint:etats` existe pour refuser.

      Le `pour` vise les photos quand elles sont là, les documents sinon : un
      libellé de section pointe le PREMIER champ qu'il introduit. -->
{#if avecPhotos || avecDocuments}
	<SectionFormulaire
		titre={SECTIONS_LIBELLE.pieces_jointes}
		pour="{idPrefixe}-{avecPhotos ? 'photos' : idDocuments}"
	>
		{#if avecPhotos}
			<div class="field champ-large">
				<FichiersUpload
					id="{idPrefixe}-photos"
					bind:urls={photos}
					titre=""
					label="Ajouter une photo"
					accept={ACCEPT_PHOTOS}
					avecLibelle
					bind:libelleFichier={photosLibelle}
					size={80}
				/>
			</div>
		{/if}
		{#if avecDocuments}
			<div class="field champ-large">
				{#if documentsControle === 'slot'}
					<slot name="documents" />
				{:else}
					<!--  `avecLibelle` : le champ que les CONTRATS portaient seuls jusqu'au
				      11/09/2026, remonté dans `FichiersUpload` et rendu à tous ses
				      appelants. Un document de ticket ne portait que le nom que son
				      auteur lui avait donné sur son disque. -->
					<FichiersUpload
						id="{idPrefixe}-{idDocuments}"
						mode="documents"
						titre=""
						avecLibelle
						bind:libelleFichier={documentsLibelle}
						differe={documentsDifferes}
						bind:urls={documents}
						bind:fichiers={documentsFichiers}
					/>
				{/if}
			</div>
		{/if}
	</SectionFormulaire>
{/if}
