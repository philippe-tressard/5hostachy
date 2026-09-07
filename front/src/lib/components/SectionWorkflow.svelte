<!--
  La section **3. Workflow** du cadre : l'intitulé, l'état courant en badge, et
  la rangée de pastilles.

  Elle était écrite au mot près dans `FormulaireTicket` et `EvolForm` — le
  commentaire de ce dernier le disait lui-même : *« Même forme que la section
  Workflow de `FormulaireTicket`, au mot près »*. Une duplication déclarée reste
  une duplication : la déclarer dit qu'on l'a vue, pas qu'elle est saine.
  Extraite le 01/09/2026, sur refus de modularité.

  🔴 **PASTILLES, jamais un `<select>` nu** (cadre R3, #423). L'état courant est
  actif à l'ouverture : on voit où en est l'objet, et en changer est un clic.

  🔴 **Section à UN champ : le titre EST le libellé** (`ux-patterns` §9 septies),
  et il porte l'état actuel en badge à droite (§9 quater) — la même forme que la
  carte, deux centimètres plus haut.

  ⚠️ `lecture` n'est **qu'un confort** : ce que l'interface interdit, le serveur
  le refait (liste blanche CS). Ne jamais s'en servir comme d'un droit.
-->
<script lang="ts">
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import WorkflowPastilles from '$lib/components/WorkflowPastilles.svelte';

	/** Identifiant du titre — c'est lui qui labellise la rangée. */
	export let idTitre: string;
	export let options: { value: string; label: string }[] = [];
	export let valeur = '';
	/** L'état actuel, en badge à droite de l'intitulé. Vide : pas de badge. */
	export let badge = '';
	/** Première section rendue : elle ne porte pas de filet au-dessus. */
	export let premiere = false;
	/** Rangée en lecture seule — confort d'interface, jamais un droit. */
	export let lecture = false;
</script>

<SectionFormulaire {premiere} titre="Workflow" requis {badge} {idTitre}>
	<div class="field champ-large">
		<WorkflowPastilles {options} {valeur} {lecture} {idTitre} on:choisir />
		<slot />
	</div>
</SectionFormulaire>
