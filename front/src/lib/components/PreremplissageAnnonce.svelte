<!--
  **« Pré-remplir depuis une annonce de hall »** — le raccourci, et lui seul.

  🔴 Le MIROIR exact du mécanisme de `FormulaireAnnonceHall`, qui propose
  « Pré-remplir depuis une actualité » depuis le 01/09/2026. Le conseil syndical
  compose souvent l'affiche du hall d'abord ; le geste n'existait que dans un
  sens (#832).

  ⚠️ **Ce n'est PAS une section du cadre #430** : c'est un raccourci qui REMPLIT
  le formulaire. Il reste donc AVANT le titre — le placer après reviendrait à
  proposer de réécrire ce qu'on vient de saisir.

  ⚠️ Uniquement en CRÉATION : pré-remplir une actualité qu'on corrige écraserait
  le texte publié, et l'écran de correction n'a pas à proposer un geste qui
  défait ce qu'il sert à ajuster.

  ## Ce que ce composant fait, et ce qu'il laisse à l'écran

  Il va CHERCHER l'annonce et l'annonce par `on:remplir` ; c'est l'écran qui
  décide des champs à remplir, puisque lui seul les connaît. Couper là évite au
  composant de connaître le formulaire qui l'héberge.

  Extrait de `FormulaireActualite.svelte` le 15/09/2026, au fil de l'eau : le
  garde-fou de modularité (rang 1) a refusé que cet écran grossisse pour recevoir
  « Saisi pour », et ce bloc est ce qu'il portait de plus autonome.
-->
<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';

	import { publications as pubsApi, annoncesHall as annoncesHallApi, ApiError } from '$lib/api';
	import type { ActualitePrefill, AnnonceHall } from '$lib/api';
	import { essayer } from '$lib/chargement';
	import { fmtDateShort } from '$lib/date';
	import { MAX_SOURCES_PREREMPLISSAGE } from '$lib/publications';
	import { toast } from '$lib/components/Toast.svelte';

	/** Le raccourci ne s'offre qu'à la création — voir l'en-tête. */
	export let modeEdition = false;

	const dispatch = createEventDispatcher<{ remplir: ActualitePrefill }>();

	let annonces: AnnonceHall[] = [];
	let annonceSourceId: number | '' = '';

	onMount(async () => {
		if (modeEdition) return;
		//  ⚠️ Non bloquant : si la liste ne vient pas, la saisie libre reste
		//  possible et le sélecteur ne s'affiche simplement pas. C'est la règle
		//  qu'applique déjà l'autre sens.
		const [liste] = await essayer(annoncesHallApi.list(true), [] as AnnonceHall[]);
		annonces = liste
			.sort((a, b) => new Date(b.cree_le).getTime() - new Date(a.cree_le).getTime())
			.slice(0, MAX_SOURCES_PREREMPLISSAGE);
	});

	async function choisir(annonceId: number | '') {
		annonceSourceId = annonceId;
		if (annonceId === '') return;
		try {
			dispatch('remplir', await pubsApi.depuisAnnonceHall(annonceId));
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur lors du pré-remplissage');
		}
	}
</script>

{#if !modeEdition && annonces.length}
	<div class="field">
		<label for="pub-source-hall">Pré-remplir depuis une annonce de hall</label>
		<select
			id="pub-source-hall"
			value={annonceSourceId}
			on:change={(e) =>
				choisir(
					(e.currentTarget as HTMLSelectElement).value === ''
						? ''
						: Number((e.currentTarget as HTMLSelectElement).value),
				)}
		>
			<option value="">— Saisie libre —</option>
			{#each annonces as annonce (annonce.id)}
				<option value={annonce.id}>{fmtDateShort(annonce.cree_le)} · {annonce.titre}</option>
			{/each}
		</select>
	</div>
	<p class="aide">
		Reprend le titre, le message, le périmètre et les images de l'affiche. Tout reste modifiable
		ci-dessous : l'actualité est indépendante de l'annonce d'origine.
	</p>
	<hr class="separateur-prefill" />
{/if}
