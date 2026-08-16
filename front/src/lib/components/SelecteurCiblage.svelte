<!--
  Un sélecteur de ciblage : un titre, un badge d'état, des pastilles à bascule, et
  un bouton de réinitialisation quand la sélection n'est plus le défaut.

  POURQUOI CE COMPOSANT (16/08/2026). L'écran Sondages portait ce bloc DEUX FOIS —
  « Périmètre géographique » et « Profils destinataires » — avec exactement la même
  structure et le même comportement (vide = tout, clic = bascule, bouton pour
  revenir au défaut). Deux copies d'un même geste, dans le même fichier : la
  première chose qui diverge quand on touche à l'une des deux.

  Il porte aussi le BADGE D'ÉTAT que l'utilisateur a demandé d'étendre au standard
  (skill `ux-patterns` §9 quater) : « Profils destinataires [Tous] », « Périmètre
  [Toute la résidence] ». On lit l'état choisi sans avoir à dépiler les pastilles.

  Les pastilles utilisent `.pill` / `.pill-active` d'app.css — les mêmes que
  `PerimetrePicker` et que les filtres du site. Ce bloc en avait une TROISIÈME
  définition locale (`.ciblage-option`), aux mêmes valeurs à quelques pixels près :
  invisible à la relecture, divergente à l'usage.

  ⚠️ CE N'EST PAS `PerimetrePicker`, et c'est délibéré ici : le sondage stocke des
  `batiments_ids`, alors que ce composant-là rend des CODES de périmètre incluant
  parking, AFUL et espaces verts, que le modèle du sondage ne sait pas enregistrer.
  Les réunir demande de passer au champ `perimetre_cible` — un changement de
  contrat avec migration, pas un remplacement de composant. Suivi en #367.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	/** Intitulé du bloc — ex. « Profils destinataires ». */
	export let titre: string;

	/** Options proposées, dans l'ordre d'affichage. */
	export let options: { val: string | number; label: string }[] = [];

	/** Valeurs retenues. **Vide = tout**, ce que le badge annonce. */
	export let selection: (string | number)[] = [];

	/** Ce que « rien de sélectionné » veut dire — ex. « Tous ». */
	export let libelleDefaut: string;

	const dispatch = createEventDispatcher<{ basculer: string | number; reinitialiser: void }>();

	//  Le défaut n'est pas « aucune cible » mais « toutes » : une sélection vide
	//  vise tout le monde. Le badge existe pour que cela ne se devine pas.
	$: estDefaut = selection.length === 0;
</script>

<div class="field champ-large ciblage">
	<div class="ciblage-titre">
		{titre}
		{#if estDefaut}<span class="badge badge-green ciblage-badge">{libelleDefaut}</span>{/if}
	</div>
	<div class="perimetre-pills">
		{#each options as o (o.val)}
			<button type="button" class="pill" class:pill-active={selection.includes(o.val)}
				on:click={() => dispatch('basculer', o.val)}>{o.label}</button>
		{/each}
	</div>
	{#if !estDefaut}
		<button type="button" class="btn btn-sm btn-outline ciblage-reinit"
			on:click={() => dispatch('reinitialiser')}>
			Réinitialiser ({libelleDefaut.toLowerCase()})
		</button>
	{/if}
</div>

<style>
	.ciblage { margin-bottom: .75rem; }
	.ciblage-titre { font-size: .9rem; font-weight: 600; margin-bottom: .4rem; }
	.ciblage-badge { font-size: .72rem; margin-left: .4rem; }
	.ciblage-reinit { margin-top: .35rem; }
</style>
