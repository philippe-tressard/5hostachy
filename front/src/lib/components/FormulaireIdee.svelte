<!--
  Le formulaire de dépôt d'une idée — extrait de `sondages/+page.svelte` le
  16/08/2026.

  POURQUOI. La page portait TROIS formulaires de création (sondage, idée, annonce)
  et 868 lignes : le garde-fou de modularité a refusé qu'elle grossisse encore
  (`standards/02` §6). La règle est de découper quand on y touche, et c'est ce
  bloc-ci qui part — le plus autonome des trois, avec son propre état et sa propre
  responsabilité.

  Il suit le contrat de `FormulaireActualite` et `FormulaireTicket` : il porte sa
  boîte `FormulaireCreation` et signale la création par l'événement `cree`.

  ⚠️ Deux défauts d'UX corrigés au passage, tous deux du même genre que ceux
  signalés par l'utilisateur sur les autres écrans :
    • le bouton « Soumettre » était posé NU dans le formulaire, donc cadré à
      GAUCHE, alors que `.form-actions` aligne à droite partout ailleurs ;
    • le champ Titre portait une mise en forme en `style=` au lieu d'hériter de
      `.field`, et n'occupait pas la ligne entière alors que c'est un texte libre
      (skill `ux-patterns` §9 bis).
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import FormulaireCreation from '$lib/components/FormulaireCreation.svelte';
	import RichEditor from '$lib/components/RichEditor.svelte';
	import { idees as ideesApi, ApiError } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';

	//  L'API des idées ne rend pas de type dédié : l'événement porte l'objet créé
	//  tel quel, et la page recharge sa liste depuis le serveur.
	const dispatch = createEventDispatcher<{ cree: unknown }>();

	let form = { titre: '', description: '' };
	let submitting = false;

	async function creer() {
		if (!form.titre || !form.description) {
			toast('error', 'Titre et description obligatoires');
			return;
		}
		submitting = true;
		try {
			const idee = await ideesApi.create(form);
			form = { titre: '', description: '' };
			toast('success', 'Idée soumise !');
			dispatch('cree', idee);
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			submitting = false;
		}
	}
</script>

<FormulaireCreation titre="Nouvelle idée">
	<form on:submit|preventDefault={creer}>
		<label class="field champ-large">
			Titre *
			<input bind:value={form.titre} placeholder="Ex. Vélos électriques en libre-service" required />
		</label>
		<div class="field champ-large">
			<label for="idee-description">Description *</label>
			<RichEditor id="idee-description" bind:value={form.description}
				placeholder="Décrivez votre idée…" minHeight="100px" />
		</div>
		<!--  Pas de bouton « Annuler » ici : la commande vit dans l'en-tête de page,
		      où le bouton d'ouverture bascule (#367). -->
		<div class="form-actions">
			<button class="btn btn-primary" disabled={submitting}>{submitting ? 'Envoi…' : 'Soumettre'}</button>
		</div>
	</form>
</FormulaireCreation>
