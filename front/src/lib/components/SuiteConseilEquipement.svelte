<!--
  L'Équipement d'une Suite 🔄 d'affaire, À SON RANG : avant le Suivi (#1326).

  Il vivait dans `SectionsSuiteConseil`, rendu après le Suivi. Il en est sorti
  pour prendre le créneau `avant_suivi` d'`EvolForm` ; l'état reste partagé
  (`$lib/suite-conseil`), car l'Équipement propose l'Intervenant, rendu après.
-->
<script lang="ts">
	import type { Writable } from 'svelte/store';
	import type { Ticket } from '$lib/api';
	import { isCS } from '$lib/stores/auth';
	import { equipementDansLaSuite, etatSuite } from '$lib/suite-conseil';
	import SectionEquipement from './SectionEquipement.svelte';

	export let ticket: Ticket;
	export let partage: Writable<Record<string, unknown>>;

	const etat = etatSuite(partage, ticket);
</script>

{#if equipementDansLaSuite(ticket, $isCS)}
	<SectionEquipement idPrefixe="suite-{ticket.id}" pliable bind:equipement={$etat.equipement} />
{/if}
