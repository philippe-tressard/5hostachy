<!--
  SyntheseFil.svelte — la synthèse d'une affaire close, côté FIL (#1643).

  Ce que le fil d'une affaire close demande au serveur — la synthèse lisible,
  et si l'on peut en produire une —, puis ce qu'il en montre au-dessus de
  l'Historique : le bouton « 🧾 Produire la synthèse » (le conseil, affaire du
  carnet close sans synthèse) ou la mention qu'elle est en préparation.

  🔴 Il est monté par les DEUX rendus du fil, la fiche (`HistoriqueTicket`) et la
  carte dépliée de la liste (`CarteTicket`), qui ne partagent pas leur câblage.
  Livré d'abord dans la seule fiche (v2.99.0), le bouton manquait à la liste et
  la Suite y paraissait vide — trouvé à l'écran par l'utilisateur, pas par un
  contrôle.

  La Suite elle-même se rend par l'hôte, dans le créneau `synthese` de
  `RubriqueHistorique`, avec `etat` que ce composant tient (`bind:etat`) ; un
  geste sur elle appelle `recharger()`.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { syntheses, type EtatSynthese, type Ticket } from '$lib/api';
	import { messageErreur } from '$lib/erreurs';
	import { isCS } from '$lib/stores/auth';
	import { estTicketClos } from '$lib/tickets';
	import EtatListe from './EtatListe.svelte';
	import { toast } from './Toast.svelte';

	export let ticket: Pick<Ticket, 'id' | 'statut'> | null;
	/** Le fil : relu à chaque écriture, il fait relire la synthèse avec lui. */
	export let evolutions: unknown[] = [];
	/** L'état lu — l'hôte en rend la Suite (`bind:etat`). */
	export let etat: EtatSynthese | null = null;

	const dispatch = createEventDispatcher<{ change: void }>();

	let erreur = '';
	let enCours = false;
	$: cle = ticket && estTicketClos(ticket.statut) ? `${ticket.id}:${evolutions.length}` : null;
	$: if (cle) recharger();
	$: if (!cle) etat = null;

	export async function recharger() {
		if (!ticket) return;
		erreur = '';
		try {
			etat = await syntheses.lire(ticket.id);
		} catch (e) {
			etat = null;
			erreur = messageErreur(e);
		}
	}

	async function produire() {
		if (!ticket) return;
		enCours = true;
		try {
			await syntheses.produire(ticket.id);
			dispatch('change');
			toast('success', 'Synthèse produite — à relire, puis valider');
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			enCours = false;
		}
	}
</script>

<EtatListe compact {erreur} />
{#if $isCS && etat?.produisible}
	<div class="synthese-fil">
		<button class="btn btn-outline btn-sm" disabled={enCours} on:click={produire}
			>{enCours ? 'Rédaction…' : '🧾 Produire la synthèse'}</button
		>
	</div>
{:else if $isCS && etat?.en_attente}
	<p class="aide">
		🧾 La synthèse de l’affaire est en préparation : elle paraîtra dans le fil sous quarante
		minutes.
	</p>
{/if}

<style>
	.synthese-fil {
		display: flex;
		justify-content: flex-end;
		margin-bottom: 0.5rem;
	}
</style>
