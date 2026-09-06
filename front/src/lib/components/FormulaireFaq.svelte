<!--
  Le formulaire d'une question de la FAQ.

  Extrait de `faq/+page.svelte` le 31/08/2026, quand le contrôle de modularité a
  refusé que la page grossisse pour recevoir son cadre. Ce n'est pas un découpage
  de confort : les six autres entités du site ont chacune leur objet
  `Formulaire<Entité>` — actualité, annonce, contrat, idée, sondage, ticket — et
  la FAQ écrivait le sien à même la page. C'était le dernier écart de cette
  famille.

  ## Ce que ce composant décide, et ce qu'il laisse à la page

  Il porte **le formulaire ET son cadre**, parce qu'il reçoit le geste
  (`modeEdition`) : c'est la règle `ux-patterns` §14 bis — *le cadre se pose là
  où le geste est connu.* La page garde l'état et la décision d'enregistrer.

  🔴 L'écran ouvrait une **modale pour la création** aussi, ce que #367 a supprimé
  après trois signalements. Il a survécu parce que `lint:formulaires` cherchait un
  `<form>` : cette modale n'en a jamais porté, seulement des `.field` et un
  éditeur riche. Le contrôle compte les champs depuis ce lot.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	import CadreFormulaire from '$lib/components/CadreFormulaire.svelte';
	import RichEditor from '$lib/components/RichEditor.svelte';

	const dispatch = createEventDispatcher<{ annule: void }>();

	/**  Corrige-t-on une question existante, ou en crée-t-on une ? La page le sait
	 *   (`editingItem`), le formulaire non — il reçoit les mêmes champs dans les
	 *   deux cas. C'est le seul discriminant du cadre. */
	export let modeEdition = false;
	/** Les champs, liés dans les deux sens : la page porte leur cycle de vie. */
	export let categorie = '';
	export let nouvelleCategorie = '';
	export let estNouvelleCategorie = false;
	export let question = '';
	export let reponse = '';
	/** Les catégories déjà en service, proposées avant d'en inventer une. */
	export let categories: string[] = [];
	export let enregistrement = false;
	/** Appelé à la soumission. La page garde la décision d'enregistrer. */
	export let onEnregistrer: () => void;

	$: titreCadre = modeEdition ? 'Modifier la question' : 'Nouvelle question';

	//  ⚠️ Le champ se vide quand on CHOISIT « nouvelle catégorie », pour repartir
	//  d'une saisie propre — et non quand on revient à une catégorie existante.
	//  L'inverse paraît symétrique et ne l'est pas : il effacerait le nom qu'on
	//  vient de taper au premier aller-retour dans la liste.
	function surChangementCategorie() {
		estNouvelleCategorie = categorie === '__new__';
		if (estNouvelleCategorie) nouvelleCategorie = '';
	}
</script>

<!--
	Un seul montage du formulaire, deux cadres possibles — et le CHOIX du cadre
	n'est plus écrit ici. `CadreFormulaire` le porte pour les six formulaires qui
	en ont besoin : il s'y écrivait cinq fois, et les copies avaient commencé à
	diverger (02/09/2026).

	Ce qui reste ici : `edition`, qui déclare le GESTE. Ce n'est pas décoratif —
	`lint:formulaires` l'exige, et c'est lui qui distingue « créer » de
	« corriger », ce que rien dans le balisage ne permettrait de deviner.
-->
<CadreFormulaire edition={modeEdition} titre={titreCadre} on:fermer={() => dispatch('annule')}>
	<div class="form-grid" class:modal-body={modeEdition}>
		<label class="field"
			>Catégorie *
			<select bind:value={categorie} on:change={surChangementCategorie}>
				<option value="" disabled>— Choisir une catégorie —</option>
				{#each categories as cat (cat)}
					<option value={cat}>{cat}</option>
				{/each}
				<option value="__new__">➕ Nouvelle catégorie…</option>
			</select>
		</label>
		{#if estNouvelleCategorie}
			<label class="field"
				>Nom de la nouvelle catégorie *<input
					type="text"
					bind:value={nouvelleCategorie}
					placeholder="Ex : 🗑️ Tri des déchets"
				/></label
			>
		{/if}

		<label class="field"
			>Question *<input type="text" bind:value={question} placeholder="La question…" /></label
		>

		<div class="field">
			<label for="faq-reponse">Réponse *</label
			><!-- RichEditor : pas labelable, donc pas d'enveloppement -->
			<RichEditor
				id="faq-reponse"
				bind:value={reponse}
				placeholder="La réponse…"
				minHeight="120px"
			/>
		</div>
	</div>
	<!--  `.form-actions` d'`app.css` : Annuler en `btn-outline` PUIS la soumission
	      en `btn-primary`. Un ordre qui change d'un écran à l'autre fait cliquer
	      de travers par mémoire du geste (`lint:soumission`). -->
	<div class="form-actions">
		<button class="btn btn-outline" on:click={() => dispatch('annule')} disabled={enregistrement}
			>Annuler</button
		>
		<button class="btn btn-primary" on:click={onEnregistrer} disabled={enregistrement}>
			{enregistrement ? 'Enregistrement…' : 'Enregistrer'}
		</button>
	</div>
</CadreFormulaire>

<style>
	/*  🔴 SURCHARGE ASSUMÉE de `.form-grid` (`composants.css`), qui est une grille
	    en `auto-fit` à deux colonnes dès 440 px. Dans une modale de 500 px, deux
	    colonnes écraseraient la question et l'éditeur : ici c'est une colonne.

	    Elle voyage AVEC le balisage, et c'est la leçon de #344 — reproduite le
	    15/08/2026 sur `FormulaireEvenement` : une règle laissée dans la page que
	    le balisage vient de quitter ne s'applique plus à rien, Svelte scopant les
	    styles. Le formulaire s'affichait alors en une colonne écrasée. */
	.form-grid {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
</style>
