<script lang="ts">
	/**
	 * Une visite planifiée — la carte, écrite **une fois**.
	 *
	 * ## Pourquoi ce composant (#453, 20/08/2026)
	 *
	 * L'onglet Visites de `prestataires/+page.svelte` rendait **deux listes** —
	 * « en retard » et « en cours » — avec **quarante lignes recopiées à
	 * l'identique**. Deux différences seulement les séparaient :
	 *
	 *   • la classe `visite-card--retard` sur le conteneur ;
	 *   • la date, affichée telle quelle d'un côté, remplacée par « Non
	 *     planifiée » de l'autre quand elle manque.
	 *
	 * 🔴 Deux copies d'accord entre elles ne prouvent rien : elles divergent au
	 * premier enrichissement demandé d'un seul côté. C'est exactement ce qui est
	 * arrivé aux six formulaires de création avant `ChampsCommuns`, et aux cartes
	 * avant `EnteteCarte`.
	 *
	 * Le composant porte donc les deux cas, et l'appelant dit lequel par
	 * `enRetard` — un booléen, pas deux blocs.
	 *
	 * ⚠️ Les styles voyagent AVEC le balisage. Svelte scope les styles au
	 * fichier : les laisser dans la page aurait rendu cette carte nue, comme les
	 * pastilles de la v2.67.11 et les six écrans d'admin du 19/08.
	 */
	import { createEventDispatcher } from 'svelte';
	import { isCS } from '$lib/stores/auth';
	import { fmtDateShort } from '$lib/date';
	import { equipLabel, frequenceLabel } from '$lib/prestataires';

	export let contrat: any;
	export let prestataireNom: string | null = null;
	/**  Déplié ou non. L'état vit dans la page : une seule carte ouverte à la
	 *   fois, et c'est elle qui arbitre. */
	export let ouverte = false;
	/**  Change l'accent de la carte et la façon de rendre la date. */
	export let enRetard = false;

	const dispatch = createEventDispatcher();
</script>

<div class="visite-card card" class:visite-card--retard={enRetard} class:expanded={ouverte}>
	<!--  ⚠️ `role="button"` + `tabindex` + `on:keydown` : la rangée n'est pas un
	      `<button>`, elle doit donc porter le clavier elle-même
	      (`ux-patterns` §3). -->
	<div class="visite-row"
		role="button" tabindex="0"
		on:click={() => dispatch('basculer')}
		on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && dispatch('basculer')}>
		<div class="visite-main">
			<strong>{prestataireNom ?? '—'}</strong>
			<span class="badge badge-blue">{equipLabel(contrat.type_equipement)}</span>
		</div>
		<div class="visite-freq">
			{#if contrat.frequence_type}
				<span class="badge badge-blue" style="font-size:.75rem">{frequenceLabel(contrat)}</span>
			{/if}
		</div>
		<div class="visite-date" class:visite-date--retard={enRetard}>
			{#if contrat.prochaine_visite}
				🗓 {fmtDateShort(contrat.prochaine_visite)}
			{:else}
				<span style="color:var(--color-text-muted)">Non planifiée</span>
			{/if}
		</div>
		<span class="toggle-arrow">{ouverte ? '▲' : '▼'}</span>
	</div>

	{#if ouverte}
		<div class="visite-detail">
			<div class="detail-grid">
				<div><span class="detail-label">Contrat</span>{contrat.libelle}</div>
				{#if contrat.numero_contrat}
					<div><span class="detail-label">N° contrat</span>{contrat.numero_contrat}</div>
				{/if}
				<div><span class="detail-label">Date début</span>📅 {fmtDateShort(contrat.date_debut)}</div>
				{#if contrat.duree_initiale_valeur}
					<div>
						<span class="detail-label">Durée</span>
						{contrat.duree_initiale_valeur} {contrat.duree_initiale_unite}
					</div>
				{/if}
			</div>
			{#if $isCS}
				<div class="visite-actions">
					<button class="btn btn-sm btn-outline" on:click|stopPropagation={() => dispatch('modifier')}>
						✏️ Modifier
					</button>
					<button class="btn btn-sm visite-noter" on:click|stopPropagation={() => dispatch('noter')}>
						⭐ Noter
					</button>
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	/*  🔴 CES RÈGLES SONT CELLES DE LA PAGE, REPRISES À LA LETTRE.
	    Le premier jet les avait RÉÉCRITES — plus propres, et différentes : une
	    grille au lieu d'un `flex`, d'autres couleurs, d'autres épaisseurs. Un
	    déplacement de balisage ne change pas l'apparence ; le jour où on veut la
	    changer, on le demande et on le montre.

	    ⚠️ `toggle-arrow`, `detail-grid` et `detail-label` NE SONT PAS ICI : elles
	    servent aussi les onglets Prestations et Contrats. Les emporter les aurait
	    rendues nues là-bas — la régression des pastilles de la v2.67.11. Elles
	    sont remontées dans `app.css`, où elles sont globales et assumées. */
	.visite-card { margin-bottom: .5rem; border-left: 3px solid var(--color-border); overflow: hidden; transition: border-color .12s; }
	.visite-card:hover, .visite-card.expanded { border-left-color: var(--color-primary); }
	.visite-card--retard { border-left-color: var(--color-danger, #dc2626) !important; }
	.visite-row { display: flex; align-items: center; gap: .75rem; padding: .7rem 1rem; cursor: pointer; flex-wrap: wrap; }
	.visite-main { display: flex; align-items: center; gap: .5rem; flex: 1; min-width: 150px; flex-wrap: wrap; }
	.visite-freq { flex-shrink: 0; }
	.visite-date { font-size: .85rem; font-weight: 600; color: var(--color-primary); flex-shrink: 0; }
	.visite-date--retard { color: var(--color-danger, #dc2626) !important; }
	.visite-detail { padding: .75rem 1rem; border-top: 1px solid var(--color-border); background: var(--color-bg-secondary, #f8f9fa); }
	.visite-actions { display: flex; gap: .4rem; margin-top: .5rem; flex-wrap: wrap; }
	.visite-noter { color: #f59e0b; }

	/*  Reprise du bloc responsive de la page : sous 600 px, la rangée resserre son
	    espacement. `flex-wrap` fait le reste — les éléments passent à la ligne
	    d'eux-mêmes, ce qui est déjà le comportement d'aujourd'hui. */
	@media (max-width: 600px) {
		.visite-row { gap: .4rem; }
	}
</style>
