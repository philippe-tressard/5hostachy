<!--
  SectionEquipement.svelte — la section 3 du cadre : SUR QUOI porte l'affaire.

  Sortie de `SectionsSpecifiquesTicket` le 24/09/2026 (#1207) : la Suite du
  conseil en a besoin à son tour, et la recopier aurait fait deux listes, deux
  aides et deux résumés pour le même champ. Le conseil la désigne, pour une
  catégorie du bâti ; les règles serveur vivent dans `utils/intervenant`.
-->
<script lang="ts">
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import { SECTIONS_LIBELLE } from '$lib/entites/types';
	import { EQUIPEMENTS_AFFAIRE, equipLabel } from '$lib/prestataires';

	/** La valeur de `TypeEquipement`, ou `''`. */
	export let equipement = '';
	export let idPrefixe = 'ticket';
	/** Relayé depuis la déclaration (`lint:pliage-transmis`). */
	export let pliable = false;
	/** Le motif d'extinction (`inactivePour`), ou `''`. */
	export let inactive = '';
</script>

<SectionFormulaire
	titre={SECTIONS_LIBELLE.equipement}
	{pliable}
	{inactive}
	resume={equipement ? equipLabel(equipement) : 'aucun'}
	valeurModifiee={equipement !== ''}
	pour="{idPrefixe}-equipement"
>
	<div class="field">
		<select id="{idPrefixe}-equipement" bind:value={equipement}>
			<option value="">— Aucun —</option>
			{#each EQUIPEMENTS_AFFAIRE as e (e.val)}<option value={e.val}>{e.label}</option>{/each}
		</select>
	</div>
	<p class="aide">Au carnet d’entretien, l’affaire résolue se range sous cet équipement.</p>
</SectionFormulaire>
