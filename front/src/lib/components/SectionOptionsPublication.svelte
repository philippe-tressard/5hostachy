<!--
  SectionOptionsPublication.svelte — la section 2 du cadre #430, telle qu'elle se
  rend partout : le titre « Options de publication » et les cases.

  ## Pourquoi (05/09/2026)

  Le couple « `SectionFormulaire` + `OptionsPublication` » était écrit quatre fois
  — création d'actualité, panneau d'options, commentaire d'actualité, et le
  ticket qui venait de le recevoir. Quatre écritures d'une même section, donc
  quatre occasions de diverger sur le titre, l'ordre ou le filet.

  Demandé à l'écran : *« Faire ces évolutions au niveau de l'objet pour ne pas
  dupliquer le code. Donc sur actualité et Ticket mettre la section Options de
  publication. »*

  ## Ce que ce composant N'EST PAS

  Il ne décide pas des options : c'est `options` qui le dit, et la table
  (`$lib/options-publication`) qui porte glyphes et libellés. Un ticket n'en rend
  qu'une — il n'a ni colonne d'épinglage ni colonne d'urgence.

  ⚠️ Les liaisons restent nommées (`bind:epingle`…) et non regroupées dans un
  objet : `bind:` a besoin d'une variable, et un objet intermédiaire obligerait
  chaque hôte à le défaire ensuite.
-->
<script lang="ts">
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import OptionsPublication from '$lib/components/OptionsPublication.svelte';
	import type { CleOptionPublication } from '$lib/options-publication';

	/** Le nom de l'objet décrit, pour les libellés qui le nomment. */
	export let objet = 'publication';
	/** Les options rendues, dans l'ordre de la table. */
	export let options: CleOptionPublication[] = ['epingle', 'urgente', 'brouillon', 'confidentiel'];
	/** Première section du formulaire : pas de filet au-dessus. */
	export let premiere = false;

	export let epingle = false;
	export let urgente = false;
	export let brouillon = false;
	export let confidentiel = false;
	/** Le périmètre visé, qui décide si « Confidentiel » a un sens. */
	export let perimetreCible: string[] = [];
	/** L'objet édité était-il DÉJÀ épinglé ? (évite un double comptage) */
	export let dejaEpingle = false;
	/** 🔒 Motif pour lequel l'objet est TOUJOURS restreint — relayé tel quel. */
	export let confidentielAcquis = '';
</script>

<SectionFormulaire titre="Options de publication" {premiere} idTitre="{objet}-options-titre">
	<OptionsPublication
		{objet}
		{options}
		{perimetreCible}
		{dejaEpingle}
		{confidentielAcquis}
		bind:epingle
		bind:urgente
		bind:brouillon
		bind:confidentiel
	/>
</SectionFormulaire>
