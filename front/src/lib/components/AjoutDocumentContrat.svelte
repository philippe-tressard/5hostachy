<!--
  Ajout d'un document à un CONTRAT : un titre, un fichier, un bouton.

  ## Pourquoi ce composant existe (27/08/2026, #370)

  Ce bloc était écrit **DEUX FOIS** dans `prestataires/+page.svelte`, à l'identique
  — mêmes variables (`contratUploadTitre`, `contratUploadFile`, `uploadInputKey`),
  même gestionnaire, même mise en forme en ligne — une fois dans le formulaire
  d'édition d'un contrat, une fois dans la carte dépliée. Deux copies d'un même
  geste, dans un seul fichier : la divergence n'était qu'une question de temps, et
  c'est exactement ce que `standards/02` §2 décrit.

  Elles partageaient aussi leur ÉTAT : sélectionner un fichier dans l'une le
  faisait apparaître dans l'autre, puisque `contratUploadFile` était unique pour
  toute la page. Ici chaque instance porte le sien.

  ## Ce qui change à l'écran

  L'`<input type="file">` NU disparaît au profit de `FichiersUpload` en mode
  différé : c'est le composant unique de saisie de pièces jointes du site, et il
  était déjà employé six lignes plus haut pour les fichiers d'un devis. Le rendu
  « Choisir des fichiers · Aucun fichier n'a été sélectionné » du navigateur —
  qui ne ressemblait à rien d'autre sur le site — laisse place à la pastille
  nommée et au bouton d'ajout de partout ailleurs.

  ⚠️ Le mode DIFFÉRÉ est obligatoire ici : un document de contrat devient une
  entité `Document` rattachée à `contrat_id` par un endpoint PROPRE
  (`docsApi.uploadForContrat`), il ne peut pas partir par l'endpoint générique à
  la sélection. Le composant retient donc le `File` et c'est ce bloc-ci qui
  l'envoie — même raison que pour les documents d'une actualité.
-->
<script lang="ts">
	import FichiersUpload from '$lib/components/FichiersUpload.svelte';
	import { documents as docsApi, ApiError } from '$lib/api';
	import { toast } from './Toast.svelte';
	import { createEventDispatcher } from 'svelte';

	/** Le contrat auquel le document est rattaché. */
	export let contratId: number;
	/** Rend l'identifiant du champ unique quand la page en affiche plusieurs. */
	export let id: string;

	const dispatch = createEventDispatcher<{ ajoute: void }>();

	let titre = '';
	let fichiers: File[] = [];
	let envoi = false;

	async function ajouter() {
		const fichier = fichiers[0];
		if (!fichier) return;
		envoi = true;
		try {
			await docsApi.uploadForContrat(titre.trim() || fichier.name, contratId, fichier);
			//  Remis à zéro AVANT de prévenir le parent : il recharge la liste, et
			//  un champ encore rempli laisserait croire que l'ajout n'a pas eu lieu.
			titre = '';
			fichiers = [];
			toast('success', 'Document ajouté');
			dispatch('ajoute');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			envoi = false;
		}
	}
</script>

<div class="ajout-doc">
	<input
		type="text"
		placeholder="Titre"
		aria-label="Titre du document"
		bind:value={titre}
		class="ajout-doc-titre"
	/>
	<FichiersUpload
		{id}
		mode="documents"
		differe
		max={1}
		label="Choisir un document"
		bind:fichiers
		disabled={envoi}
	/>
	<button
		class="btn btn-sm btn-primary"
		disabled={fichiers.length === 0 || envoi}
		on:click|stopPropagation={ajouter}>{envoi ? '…' : '+ Document'}</button
	>
</div>

<style>
	/*  Le style vit AVEC le balisage : les deux copies portaient leurs règles en
	    ligne (`style="display:flex;gap:.4rem;…"`), donc rien n'empêchait l'une de
	    changer sans l'autre. C'est la leçon de `Pastille.svelte`. */
	.ajout-doc {
		display: flex;
		gap: 0.4rem;
		flex-wrap: wrap;
		align-items: center;
		margin-top: 0.5rem;
	}
	/*  `flex-wrap` + `min-width` : sur téléphone les trois éléments passent à la
	    ligne au lieu de déborder — le titre garde une largeur utilisable
	    (`standards/11` §10). */
	.ajout-doc-titre {
		font-size: 0.82rem;
		flex: 1;
		min-width: 110px;
	}
</style>
