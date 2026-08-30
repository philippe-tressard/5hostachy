<script lang="ts">
	/**
	 * Le formulaire d'un contrat d'entretien — **un seul rendu**, deux enveloppes.
	 *
	 * ## Pourquoi ce composant (#640, 30/08/2026)
	 *
	 * `prestataires/+page.svelte` rendait ce formulaire **deux fois**, à 110 lignes
	 * d'écart : une fois en boîte de page, une fois déplié dans la carte du
	 * contrat. Les deux montaient `ChampsContrat` puis `DocumentsContrat` — donc
	 * la même intention, écrite deux fois.
	 *
	 * 🔴 **Et les deux avaient déjà divergé**, sans que personne l'ait décidé :
	 *
	 * | | boîte de page | déplié dans la carte |
	 * |---|---|---|
	 * | barre d'actions | `.form-actions` (à droite, `ux-patterns` §9 quinquies) | un flex écrit à la main, **à gauche** |
	 * | taille des boutons | normale | `btn-sm` |
	 * | intitulé | titre du formulaire | « Infos contrat » |
	 *
	 * C'est le mécanisme ordinaire de la duplication : personne n'a choisi que le
	 * même geste aurait deux apparences, ce sont les deux copies qui l'ont produit.
	 *
	 * ⚠️ **Le second rendu était en outre INATTEIGNABLE** — du code mort. Sa garde
	 * demandait `contratFormPrestId !== -1`, et `startEditContrat()` posait
	 * `contratFormPrestId = -1` à la ligne suivant `editContratId = c.id`. Aucun
	 * chemin ne pouvait donc l'afficher. Rien ne le signalait : un bloc `{#if}`
	 * toujours faux compile, se formate et passe `svelte-check` sans un mot.
	 *
	 * ## Ce que ce composant décide, et ce qu'il laisse à l'appelant
	 *
	 * Il porte **le formulaire** : les champs, les documents, la barre d'actions et
	 * leurs libellés. Il ne porte **pas son cadre** — c'est le geste qui le choisit,
	 * et c'est la règle `ux-patterns` §14 bis :
	 *
	 * - **créer** → `<FormulaireCreation>`, la boîte dans la page ;
	 * - **éditer** → `<Modale edition>`, qui isole le geste sans décaler la liste.
	 *
	 * Mettre le cadre ici obligerait le composant à connaître le geste pour
	 * choisir son enveloppe — alors que c'est l'écran qui sait lequel il déclenche.
	 */
	import ChampsContrat from './ChampsContrat.svelte';
	import DocumentsContrat from './DocumentsContrat.svelte';

	/** L'état du formulaire, lié dans les deux sens par l'appelant. */
	export let contratForm: any;
	export let prestataires: any[] = [];
	export let equipements: readonly { val: string; label: string }[] = [];

	/**
	 * L'identifiant du contrat édité, ou `null` en création.
	 *
	 * 🔴 C'est **lui seul** qui décide de la rubrique Documents, et non un
	 * booléen de plus : un document se rattache à un contrat, donc il n'y a rien
	 * à rattacher tant que le contrat n'existe pas. Un drapeau séparé pourrait
	 * dire « avec documents » sans identifiant, et `DocumentsContrat` recevrait
	 * alors `contratId={0}` — c'est ce que l'ancien code écrivait
	 * (`contratId={editContratId ?? 0}`), un repli qui ne pouvait désigner
	 * aucun contrat.
	 */
	export let contratId: number | null = null;
	export let documents: any[] = [];
	export let onSupprimer: (contratId: number, docId: number) => void = () => {};
	export let onAjoute: (contratId: number) => void = () => {};

	/** Envoi en cours — le bouton le dit, et se verrouille. */
	export let submitting = false;

	export let onAnnuler: () => void;
	/** Appelé à la soumission du `<form>` — donc aussi sur la touche Entrée. */
	export let onEnregistrer: () => void;
</script>

<!--
	🔴 UN VRAI `<form>`, et ce n'est pas cosmétique.

	Les deux rendus précédents n'en avaient pas : des `<button on:click>` posés
	dans un `<div>`. Trois conséquences, dont la dernière est la plus coûteuse :

	1. la touche **Entrée** ne soumettait pas — dans un formulaire de dix champs,
	   c'est le geste attendu ;
	2. la validation native (`required`) n'avait aucun événement où s'accrocher ;
	3. 🔒 `lint:formulaires` ne regarde QUE les modales contenant un `<form>`.
	   Sans lui, la déclaration `edition` de la modale appelante n'était surveillée
	   par rien : on pouvait la retirer, `fermetureAuFond` redevenait vrai, et un
	   clic à côté effaçait une correction en cours — en silence. Le garde-fou et
	   la sémantique correcte sont ici la même chose.
-->
<form on:submit|preventDefault={onEnregistrer}>
	<ChampsContrat bind:contratForm {prestataires} {equipements} />
	{#if contratId !== null}
		<div class="bloc-documents">
			<DocumentsContrat
				{contratId}
				{documents}
				{onSupprimer}
				{onAjoute}
				idChamp="contrat-{contratId}-doc"
			/>
		</div>
	{/if}

	<!--
		`.form-actions` porte `justify-content: flex-end` (app.css) : le bouton
		primaire est à droite, partout. Le rendu déplié l'écrivait à la main, donc
		à gauche. Le libellé est celui de tout le site — `ux-patterns` §9 quinquies bis.
	-->
	<div class="form-actions">
		<button type="button" class="btn btn-outline" on:click={onAnnuler}>Annuler</button>
		<button type="submit" class="btn btn-primary" disabled={submitting}>
			{submitting ? 'Enregistrement…' : 'Enregistrer'}
		</button>
	</div>
</form>

<style>
	.bloc-documents {
		margin-top: 0.8rem;
	}
</style>
