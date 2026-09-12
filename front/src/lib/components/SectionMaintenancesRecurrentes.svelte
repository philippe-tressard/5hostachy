<!--
  SectionMaintenancesRecurrentes.svelte — le repli « 🔄 Maintenances récurrentes »
  de la vue Liste du calendrier.

  ## Pourquoi (12/09/2026)

  La page du calendrier a reçu le panneau d'options rapides, et le plafond de
  modularité a refusé qu'elle grossisse. Ce bloc était le bon candidat : c'est
  une **rubrique à part**, repliée, avec son propre état d'ouverture et sa propre
  rangée d'actions — rien à voir avec la liste chronologique au-dessus, qu'elle
  ne fait qu'accompagner.

  ⚠️ Il ne décide de rien : la page calcule `maintenances` (les événements dont
  le type est récurrent), passe ses libellés, et reçoit le clic de correction.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import RangeeCalendrier from './RangeeCalendrier.svelte';
	import { KANBAN_COLS } from '$lib/kanban';

	export let maintenances: any[] = [];
	/** Le repli est-il ouvert ? La page le porte — elle le ferme en changeant de vue. */
	export let ouvert = false;
	/** Le lecteur peut-il corriger ? (conseil syndical) */
	export let peutAgir = false;
	export let typeLabel: (t: string) => string;
	export let formatDate: (d: string) => string;

	const dispatch = createEventDispatcher<{ basculer: void; modifier: any }>();
</script>

<div class="recurring-section">
	<button class="recurring-toggle" on:click={() => dispatch('basculer')}>
		🔄 Maintenances récurrentes
		<span style="font-size:.8rem;font-weight:400;color:var(--color-text-muted)"
			>({maintenances.length})</span
		>
		<span class="chevron" class:open={ouvert} style="margin-left:auto">›</span>
	</button>
	{#if ouvert}
		{#each maintenances as ev (ev.id)}
			{@const col = ev.statut_kanban
				? KANBAN_COLS.find((c) => c.id === ev.statut_kanban)
				: undefined}
			<RangeeCalendrier
				typeTexte={typeLabel(ev.type)}
				titre={ev.titre}
				metas={[
					...(ev.prestataire_nom ? [`\u{1F3AF} ${ev.prestataire_nom}`] : []),
					...(ev.lieu ? [`\u{1F4CD} ${ev.lieu}`] : []),
				]}
				dates={[
					{ texte: formatDate(ev.debut) },
					...(ev.fin ? [{ texte: `→ ${formatDate(ev.fin)}`, attenue: true }] : []),
				]}
				perimetre={ev.perimetre}
				badgeKanban={col ? { texte: col.label, couleur: col.color } : null}
				avecActions={peutAgir}
			>
				<svelte:fragment slot="actions">
					<button
						class="btn-icon-edit"
						aria-label="Modifier"
						title="Modifier"
						on:click={() => dispatch('modifier', ev)}>✏️</button
					>
				</svelte:fragment>
			</RangeeCalendrier>
		{/each}
	{/if}
</div>

<style>
	/*  🔴 Les styles VOYAGENT avec le balisage : Svelte les scope au fichier, et
	    les laisser dans la page livrerait ce repli sans sa carte bleue. */
	.recurring-section {
		margin-top: 1.5rem;
		padding: 0.5rem 0;
	}
	.recurring-toggle {
		background: #f0f9ff;
		border: 1px solid #bae6fd;
		border-radius: var(--radius);
		cursor: pointer;
		font-size: 0.875rem;
		font-weight: 600;
		color: #0369a1;
		padding: 0.5rem 0.9rem;
		width: 100%;
		text-align: left;
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.recurring-toggle:hover {
		background: #e0f2fe;
	}
</style>
