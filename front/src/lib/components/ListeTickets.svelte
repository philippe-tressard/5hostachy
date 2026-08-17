<!--
  ListeTickets.svelte — une suite de `CarteTicket`, et le câblage qui va avec.

  ## Pourquoi (17/08/2026, #431)

  `tickets/+page.svelte` porte DEUX listes du même objet : les tickets actifs, et
  ceux de la section Historique, groupés par année. Extraire la carte a supprimé
  115 lignes recopiées, mais laissait le **branchement** de la carte — quel mode,
  quel gestionnaire pour chacun des six événements — écrit deux fois. Une
  duplication de 14 lignes n'est pas moins une duplication qu'une de 115 : c'est
  seulement plus discret, et donc plus durable.

  Ce composant ne décide rien. Il ne connaît ni l'API, ni l'ordre de tri, ni le
  délai de grâce : la page reste propriétaire de l'état (*quel ticket est déplié,
  lequel est en correction*) et des appels. Il n'apporte qu'une chose — que les
  deux listes se câblent forcément pareil.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import CarteTicket from './CarteTicket.svelte';
	import type { Ticket, TicketEvolution } from '$lib/api';

	export let tickets: Ticket[] = [];
	/** Allure d'archive — les tickets clos depuis plus du délai de grâce. */
	export let archive = false;
	export let expandedIds: Set<number> = new Set();
	export let evolsMap: Record<number, TicketEvolution[]> = {};
	/** Le ticket ouvert en correction, s'il y en a un. */
	export let ticketEnEdition: number | null = null;
	/** Le ticket ouvert en nouvelle entrée d'Historique, s'il y en a un. */
	export let ticketEnEvolution: number | null = null;
	/**  Le GESTE demandé sur ce ticket — celui du bouton cliqué (#426). Il ne se
	     redemande pas dans le formulaire : `💬` dit « commenter », `🔄` dit
	     « changer l'état ». */
	export let gesteEvolution: 'commentaire' | 'etat' = 'commentaire';
	export let evolutionEnCours = false;
	export let peutCommenter = false;
	export let peutAdministrer = false;

	const dispatch = createEventDispatcher<{
		basculer: Ticket;
		commenter: Ticket;
		changerEtat: Ticket;
		modifier: Ticket;
		supprimer: Ticket;
		evoluer: { ticket: Ticket; data: unknown };
	}>();
</script>

{#each tickets as t (t.id)}
	<CarteTicket
		ticket={t}
		evolutions={evolsMap[t.id] ?? []}
		expanded={expandedIds.has(t.id)}
		{archive}
		{evolutionEnCours}
		{peutCommenter}
		{peutAdministrer}
		mode={ticketEnEdition === t.id
			? 'edition'
			: ticketEnEvolution === t.id
				? gesteEvolution
				: 'lecture'}
		on:basculer={() => dispatch('basculer', t)}
		on:commenter={() => dispatch('commenter', t)}
		on:changerEtat={() => dispatch('changerEtat', t)}
		on:modifier={() => dispatch('modifier', t)}
		on:supprimer={() => dispatch('supprimer', t)}
		on:evoluer={(e) => dispatch('evoluer', { ticket: t, data: e.detail })}
		on:modifie
		on:annuler
	/>
{/each}
