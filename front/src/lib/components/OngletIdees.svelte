<!--
  L'onglet **Boîte à idées** de la Communauté — son formulaire de dépôt, ses
  filtres d'état et sa liste.

  ## Pourquoi il existe (#519)

  La page `sondages/+page.svelte` porte TROIS onglets et n'en avait extrait qu'un
  seul (`OngletAnnonces`). Le garde-fou de modularité a refusé de la laisser
  grossir en recevant les états d'erreur de #519 — et il disait vrai : une page
  de 500 lignes qui rend trois rubriques n'a pas un problème de taille, elle a un
  problème de découpage. Celui-ci rétablit la symétrie.

  ## Ce qui reste chez le parent, et pourquoi

  **Le rendu part, les gestes restent.** Voter, changer un état, supprimer,
  répondre : tout cela touche l'API et l'état partagé de la page (la liste est
  rechargée après chaque action). Les passer en callbacks garde un seul endroit
  qui parle au serveur — dupliquer les appels ici donnerait deux vérités sur
  l'état d'une idée.
-->
<script lang="ts">
	import FormulaireIdee from '$lib/components/FormulaireIdee.svelte';
	import EtatListe from '$lib/components/EtatListe.svelte';
	import ListeIdees from '$lib/components/ListeIdees.svelte';
	import SectionRepliee from '$lib/components/SectionRepliee.svelte';
	import { TITRE_ARCHIVES } from '$lib/archives';
	import { STATUTS_IDEE_FILTRE } from '$lib/idees';

	export let idees: any[] = [];
	export let chargement = false;
	/** Non vide = on n'a PAS pu charger. Distinct de « chargé et vide » (#519). */
	export let erreur = '';
	export let filtreStatut = '';
	export let showForm = false;
	export let currentUserId: number | undefined = undefined;
	export let estCS = false;
	export let estAdmin = false;
	export let statutClass: (s: string) => string;

	//  Les gestes vivent chez le parent : c'est lui qui parle à l'API et qui
	//  recharge la liste. Voir l'en-tête.
	export let onVoter: (id: number) => void;
	export let onChangerStatut: (id: number, statut: string) => void;
	export let onSupprimer: (id: number) => void;
	export let onSignaler: (cibleType: string, cibleId: number) => void;
	export let onRepondre: (id: number, contenu: string) => Promise<void> | void;
	export let onSupprimerReponse: (id: number, reponseId: number) => void;

	//  🔴 `idee.archivee` est calculé par le SERVEUR (`app/utils/archivage.py`,
	//  règle du site, un seul délai). Refaire le calcul ici en ferait une seconde
	//  règle, et les deux trancheraient différemment le jour où le délai change.
	$: courantes = idees.filter((i) => !i.archivee);
	$: archivees = idees.filter((i) => i.archivee);
	//  La FENÊTRE de correction (#783). Une seule idée à la fois, et l'état vit
	//  ICI : `ListeIdees` est rendu DEUX fois (courantes et Archives), l'y mettre
	//  en aurait monté deux exemplaires. Même construction que `OngletAnnonces`,
	//  qui a rencontré le problème le 02/09.
	let editIdee: any = null;
	const modifier = (i: any) => (editIdee = editIdee?.id === i.id ? null : i);

	function appliquerModification(maj: any) {
		idees = idees.map((i) => (i.id === maj.id ? maj : i));
		editIdee = null;
	}
	//  ⚠️ Le message d'état vide ne cite PAS le délai. Il vaut 30 jours par
	//  défaut mais se règle en administration : l'écrire ici en dur ferait mentir
	//  l'écran au premier ajustement, et le transporter avec chaque idée serait
	//  un champ par objet pour une valeur du site. Même formulation que les
	//  annonces, qui ont tranché la question le 18/08.
</script>

{#if showForm}
	<FormulaireIdee on:cree on:annule />
{/if}

<!--  La fenêtre de correction, montée UNE seule fois et hors des deux listes
      — `ListeIdees` est rendu deux fois (courantes et Archives).

      `{#key}` remonte le composant d'une idée à l'autre : ses champs sont
      initialisés une seule fois, à la construction. -->
{#if editIdee}
	{#key editIdee.id}
		<FormulaireIdee
			idee={editIdee}
			on:modifie={(e) => appliquerModification(e.detail)}
			on:annule={() => (editIdee = null)}
		/>
	{/key}
{/if}

<div class="filters">
	{#each STATUTS_IDEE_FILTRE as s (s.val)}
		<button
			class="btn btn-sm"
			class:btn-primary={filtreStatut === s.val}
			on:click={() => (filtreStatut = s.val)}>{s.label}</button
		>
	{/each}
</div>

<EtatListe
	{chargement}
	{erreur}
	vide={idees.length === 0}
	titreErreur="Impossible d'afficher les idées"
	titreVide="Aucune idée pour l'instant"
	messageVide="Soyez le premier à proposer une idée !"
>
	{#if courantes.length === 0 && archivees.length > 0}
		<div class="empty-state">
			<h3>Aucune idée en cours</h3>
			<p>Les idées décidées sont rangées dans les Archives, ci-dessous.</p>
		</div>
	{/if}
	<ListeIdees
		idees={courantes}
		{currentUserId}
		{estCS}
		{estAdmin}
		{statutClass}
		{onVoter}
		{onChangerStatut}
		{onSupprimer}
		{onSignaler}
		{onRepondre}
		{onSupprimerReponse}
		onModifier={modifier}
	/>

	<!--  Les Archives : même bandeau que les annonces et les actualités
	      (`SectionRepliee`), et les MÊMES cartes — `ListeIdees`, appelé une
	      seconde fois. Recopier le bloc sous la section repliée aurait créé deux
	      rendus libres de diverger, ce qui est arrivé six fois au fil des
	      tickets (#431). -->
	{#if archivees.length}
		<SectionRepliee titre={TITRE_ARCHIVES} compte={archivees.length}>
			<ListeIdees
				idees={archivees}
				{currentUserId}
				{estCS}
				{estAdmin}
				{statutClass}
				{onVoter}
				{onChangerStatut}
				{onSupprimer}
				{onSignaler}
				{onRepondre}
				{onSupprimerReponse}
				onModifier={modifier}
			/>
		</SectionRepliee>
	{/if}
</EtatListe>
