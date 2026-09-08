<!--
  **Corriger un document de la page Résidence** — plan, règlement ou CR d'AG.

  ## Pourquoi ce composant (#852, 08/09/2026)

  Signalé à l'écran : *« l'édition est en bas de page et non dans la section
  sélectionnée […] quand on édite on ne se retrouve pas en bas de page mais à
  l'endroit où on édite (faire de même que la référence Actualité ou ticket) »*.

  Les sept formulaires de Résidence étaient rendus à la **fin** du fichier, après
  toutes les sections. Cliquer ✏️ sur un plan ouvrait donc une boîte quatre cents
  pixels plus bas, sous les diagnostics — hors de l'écran, et sans rapport visible
  avec le geste qu'on venait de faire.

  🔴 **Les ramener dans leur section a fait apparaître le vrai problème** : le
  formulaire d'édition est **un seul** pour **trois** sections, discriminé par
  `editingDocMode`. Le recopier trois fois l'aurait fait diverger au premier champ
  ajouté — c'est-à-dire tout de suite, puisque le même lot en ajoute trois. Un
  objet, monté trois fois, sous la condition de sa section.

  ⚠️ Et `svelte-check` l'a dit avant moi : dans la copie de « Plans », le
  sous-bloc « Année / Date d'AG » comparait `'plan'` à `'ag'` — *« this comparison
  appears to be unintentional »*. Une branche morte que la relecture laissait
  passer, parce qu'elle est correcte partout ailleurs.

  ## Ce qu'il rend, et dans l'ordre du cadre

  1. **Titre** · 2. **Année et date d'AG**, pour les CR d'AG seulement ·
  4. **Périmètre** · 6. **Description** · 8. **Fichier**.

  Les numéros sautent : ce sont ceux du cadre (`ux-patterns` §0), et un document
  n'a ni workflow, ni destinataires, ni diffusion. Les garder rend l'ordre
  vérifiable d'un coup d'œil.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	import FormulaireDocument from '$lib/components/FormulaireDocument.svelte';

	const dispatch = createEventDispatcher<{ annuler: void; enregistrer: void }>();

	/**  La section d'où vient le document. Seul `ag` porte l'année et la date —
	 *   les deux autres n'en ont pas, et les afficher promettrait un champ que le
	 *   serveur ignore pour eux. */
	export let mode: 'plan' | 'reglement' | 'ag' = 'plan';

	export let titre = '';
	export let annee: string | number = '';
	export let dateAg = '';
	/** Section 4 — `[]` signifie « toute la copropriété », valide ici. */
	export let perimetre: string[] = [];
	/** Section 6 — ajoutée le 08/09/2026, elle n'existait sur aucun document. */
	export let description = '';
	export let enregistrement = false;
</script>

<FormulaireDocument
	edition
	intitule="Modifier le document"
	bind:titre
	avecPerimetre
	bind:perimetre
	avecFichier={false}
	{enregistrement}
	complet={!!titre.trim()}
	on:annuler={() => dispatch('annuler')}
	on:enregistrer={() => dispatch('enregistrer')}
>
	<svelte:fragment slot="specifiques">
		{#if mode === 'ag'}
			<div class="paire">
				<label class="field" for="edit-doc-annee">
					Année
					<input id="edit-doc-annee" type="number" bind:value={annee} min="1900" max="2100" />
				</label>
				<label class="field" for="edit-doc-date">
					Date de l'AG
					<input id="edit-doc-date" type="date" bind:value={dateAg} />
				</label>
			</div>
		{/if}
	</svelte:fragment>

	<label class="field" for="edit-doc-description" slot="description">
		Description
		<textarea
			id="edit-doc-description"
			bind:value={description}
			placeholder="Ce que ce document couvre, d'où il vient, ce qu'il ne dit pas…"
			rows="3"></textarea>
	</label>
</FormulaireDocument>

<style>
	/*  Deux champs courts qui vont ensemble — année et date d'AG. La règle
	    voyage AVEC le balisage : laissée dans la page que le balisage vient de
	    quitter, elle ne s'appliquerait plus à rien, Svelte scopant les styles
	    (#344, refait le 15/08/2026 sur `FormulaireEvenement`). */
	.paire {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.5rem;
	}
</style>
