<!--
  SectionIntervenant.svelte — la section 6 du cadre : qui intervient.

  Construite le 23/09/2026 (#1092, lot 5). Elle était déclarée « pas encore
  construite » (#1097) et rendue grisée à son rang : les événements du
  calendrier, qui portaient leur prestataire, deviennent des affaires, et ce
  lien ne devait pas se perdre en chemin (seize événements le portent).

  Le conseil seul y désigne le prestataire, et seulement pour une catégorie du
  bâti : ailleurs, la section est rendue INACTIVE par la déclaration `TICKET`
  (`inactivePour`), pas par cette page. Les règles serveur vivent dans
  `api/app/utils/intervenant.py`.
-->
<script lang="ts">
	import { SECTIONS_LIBELLE } from '$lib/entites/types';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import ChargementPartiel from '$lib/components/ChargementPartiel.svelte';

	/** L'identifiant du prestataire retenu, ou `null`. */
	export let prestataireId: number | null = null;
	/** Les prestataires proposables — chargés par l'appelant, qui connaît ses droits. */
	export let prestataires: { id: number; nom: string; actif?: boolean }[] = [];
	/** L'échec de chargement de la liste — un menu vide n'est pas « aucun prestataire ». */
	export let erreur = '';
	export let idPrefixe = 'intervenant';
	/** Relayé par l'appelant depuis la déclaration (`lint:pliage-transmis`). */
	export let pliable = false;

	//  `<select>` rend des chaînes : la valeur se lit et s'écrit ici, une fois.
	let choix = prestataireId === null ? '' : String(prestataireId);
	$: prestataireId = choix === '' ? null : Number(choix);
	$: retenu = prestataires.find((p) => p.id === prestataireId);
</script>

<SectionFormulaire
	titre={SECTIONS_LIBELLE.intervenant}
	{pliable}
	resume={retenu?.nom ?? 'aucun'}
	valeurModifiee={prestataireId !== null}
	pour="{idPrefixe}-prestataire"
>
	<ChargementPartiel
		{erreur}
		consequence="Le menu des prestataires est vide : ce n'est pas qu'il n'en existe aucun."
	/>
	<select id="{idPrefixe}-prestataire" bind:value={choix}>
		<option value="">— Aucun —</option>
		{#each prestataires.filter((p) => p.actif !== false || p.id === prestataireId) as p (p.id)}
			<option value={String(p.id)}>{p.nom}</option>
		{/each}
	</select>
</SectionFormulaire>
