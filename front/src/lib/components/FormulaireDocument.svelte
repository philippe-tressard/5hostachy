<!--
  L'OBJET « formulaire de document » — titre, périmètre, fichier(s), et le cadre
  qui va avec le geste.

  ## Pourquoi il existe (31/08/2026)

  L'écran Résidence portait **six** formulaires — plan, règlement, CR d'AG,
  rapport de diagnostic, et les deux éditions — tous bâtis du même vocabulaire :
  un titre, parfois un périmètre, un fichier, et deux boutons. Ils avaient été
  écrits l'un après l'autre, par copie, et la copie s'était déjà payée :

  🔴 **La modale « Ajouter un plan » liait son sélecteur de périmètre à
  `newCrAgPerimetre`** — la variable du CR d'AG. Choisir un périmètre sur un plan
  ne faisait donc rien pour le plan (`addPlan` envoyait `newPlanPerimetre`, un
  reliquat que plus aucun contrôle ne modifiait depuis #470) et **pré-remplissait
  en douce le formulaire d'AG**. Rien ne levait : les deux variables existaient,
  les deux types concordaient, `svelte-check` était vert.

  C'est la duplication qui produit ce défaut-là, et lui seul : deux formulaires
  distincts n'auraient pas pu échanger leur état.

  ## Ce qu'il porte, et dans l'ordre du cadre

  1. **Titre** — et lui seul (`ux-patterns` §0) ;
  2. `<slot name="specifiques" />` — ce qui qualifie CE document (année et date
     d'AG, date de diagnostic) ;
  4. **Périmètre**, par `PerimetrePicker` — jamais un sélecteur écrit à la main ;
  6. `<slot name="description" />` — la synthèse d'un rapport ;
  8. **Fichier(s)**.

  ⚠️ Les numéros sautent parce que ce sont ceux du cadre : un document n'a ni
  workflow, ni destinataires, ni diffusion. Les garder rend l'ordre vérifiable.

  ## Le cadre suit le GESTE, et c'est le composant qui le pose

  Création → `FormulaireCreation` (la boîte dans la page, #367) ·
  Édition → `Modale` (#640). Écrit **une fois**, par `<svelte:component>` : sans
  lui, le corps du formulaire existerait en deux exemplaires dans le même
  fichier, ce qui est le défaut qu'on vient de corriger.

  `fermetureAuFond={false}` en édition : on saisit ici un titre et une synthèse,
  et un clic à côté effaçait tout sans prévenir (leçon d'`OngletPerimetres`).
-->
<script lang="ts" context="module">
	/** Compteur d'instances — voir `uid` plus bas : il remplace `Math.random()`. */
	let compteur = 0;
</script>

<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	import FormulaireCreation from '$lib/components/FormulaireCreation.svelte';
	import Modale from '$lib/components/Modale.svelte';
	import PerimetrePicker from '$lib/components/PerimetrePicker.svelte';

	/** L'intitulé du formulaire — en-tête de la boîte, ou titre de la modale. */
	export let intitule: string;
	/**  Le geste : `false` on crée (boîte dans la page), `true` on corrige un
	 *   objet existant (modale). C'est la seule chose qui change de cadre. */
	export let edition = false;

	/** Section 1 — le titre, et lui seul. */
	export let titre = '';
	export let libelleTitre = 'Titre';
	/**  Un titre facultatif se marque en ne mettant PAS d'astérisque, et en
	 *   disant ce qui se passe sans lui — jamais « (optionnel) » (cadre R3). */
	export let titreRequis = true;
	export let placeholderTitre = '';
	export let aideTitre = '';

	/** Section 4 — `[]` signifie « toute la copropriété », ce qui est valide ici. */
	export let avecPerimetre = false;
	export let perimetre: string[] = [];

	/** Section 8 — un fichier, ou plusieurs. */
	export let avecFichier = true;
	export let multiple = false;
	export let fichiers: FileList | null = null;
	export let libelleFichier = 'Fichier';
	export let accept = '.pdf,.jpg,.jpeg,.png,.webp';

	/** L'enregistrement est-il en cours, et peut-on l'engager ? */
	export let enregistrement = false;
	export let complet = true;

	const dispatch = createEventDispatcher<{ annuler: void; enregistrer: void }>();

	//  Un identifiant propre à CHAQUE instance : deux formulaires ouverts sur la
	//  même page partageraient sinon le `for` de leurs libellés, et cliquer sur
	//  l'un donnerait le focus à l'autre — ce que `lint:labels` ne voit pas,
	//  puisque chaque `for` a bien sa cible.
	//
	//  ⚠️ Un compteur, pas `Math.random()` : le rendu serveur et le rendu client
	//  doivent produire le MÊME identifiant, sinon l'hydratation se plaint et
	//  remplace le nœud — un champ en cours de saisie y perdrait son contenu.
	const uid = `fd-${++compteur}`;

	//  Le nom du ou des fichiers retenus : sans ce retour, on ne sait pas ce
	//  qu'on s'apprête à envoyer.
	$: choisis = fichiers ? Array.from(fichiers) : [];
</script>

<svelte:component
	this={edition ? Modale : FormulaireCreation}
	{...edition
		? { edition: true, titre: intitule, classeBoite: 'modal-box', fermetureAuFond: false }
		: { titre: intitule }}
	on:fermer={() => dispatch('annuler')}
>
	<label class="field" for="{uid}-titre">
		{libelleTitre}{titreRequis ? ' *' : ''}
		<input id="{uid}-titre" type="text" bind:value={titre} placeholder={placeholderTitre} />
		{#if aideTitre}<span class="field-hint">{aideTitre}</span>{/if}
	</label>

	<slot name="specifiques" />

	{#if avecPerimetre}
		<!--  🔴 `PerimetrePicker`, l'objet du site — plus un sélecteur écrit à la
		      main (#470). `requis={false}` : un document qui concerne toute la
		      copropriété ne cible rien, et l'absence est ici une réponse valide. -->
		<div class="field">
			<PerimetrePicker bind:value={perimetre} titre="Périmètre" requis={false} />
		</div>
	{/if}

	<slot name="description" />

	{#if avecFichier}
		<label class="field" for="{uid}-fichier">
			{libelleFichier} *
			<input
				id="{uid}-fichier"
				type="file"
				{multiple}
				{accept}
				on:change={(e) => (fichiers = (e.target as HTMLInputElement).files)}
			/>
			{#if choisis.length === 1}
				<span class="field-hint">{choisis[0].name}</span>
			{:else if choisis.length > 1}
				<span class="field-hint">{choisis.length} fichiers sélectionnés</span>
			{/if}
		</label>
	{/if}

	<div class="form-actions">
		<button class="btn btn-outline" on:click={() => dispatch('annuler')}>Annuler</button>
		<button
			class="btn btn-primary"
			disabled={enregistrement || !complet}
			on:click={() => dispatch('enregistrer')}
		>
			{enregistrement ? 'Enregistrement…' : 'Enregistrer'}
		</button>
	</div>
</svelte:component>
