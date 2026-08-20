<script lang="ts">
	/**
	 * Onglet **Visites** de l'écran Prestataires.
	 *
	 * ## Pourquoi cette extraction (#453)
	 *
	 * `prestataires/+page.svelte` pesait **2 099 lignes**, et le garde-fou de
	 * modularité (rang 1) refuse qu'un fichier de plus de 500 lignes grossisse.
	 * Le 18/08, il a refusé **trois** ajouts de deux lignes ; trois fois, la
	 * réponse a été de ramener des attributs sur une seule ligne — c'est-à-dire
	 * de satisfaire le contrôle par la mise en forme, pas par la structure.
	 *
	 * La couture était dessinée : **cinq onglets**, chacun un bloc cohérent. Même
	 * découpage que `admin/+page.svelte` le 19/08, qui a donné ses `Onglet*`.
	 *
	 * ## Ce que l'extraction a supprimé au passage
	 *
	 * 🔴 Les deux listes — « en retard » et « en cours » — étaient **quarante
	 * lignes recopiées à l'identique**, à deux différences près. Elles passent par
	 * `CarteVisite`, écrite une fois. Déplacer une duplication ne la corrige pas :
	 * elle serait simplement devenue une duplication dans un fichier plus petit.
	 *
	 * ## Ce que ce composant NE fait pas
	 *
	 * ⚠️ Il ne charge rien et ne décide rien. Les données, l'état déplié et les
	 * gestes restent à la page : quatre onglets partagent `contrats`,
	 * `prestataires` et `expandedContrats`, et déplacer cet état ici en ferait une
	 * seconde source. On extrait un RENDU, pas une moitié de logique.
	 */
	import { createEventDispatcher } from 'svelte';
	import CarteVisite from '$lib/components/CarteVisite.svelte';

	/**  Tous les contrats qui portent une visite planifiée — sert au décompte. */
	export let visites: any[] = [];
	export let visitesEnRetard: any[] = [];
	export let visitesAJour: any[] = [];
	export let prestataires: any[] = [];
	/**  Les identifiants de contrats dépliés. L'ensemble vit dans la page : une
	 *   seule carte ouverte à la fois, sur les quatre onglets. */
	export let expandedContrats: Set<number> = new Set();

	const dispatch = createEventDispatcher();

	function nomDu(contrat: any): string | null {
		return prestataires.find((p) => p.id === contrat.prestataire_id)?.nom ?? null;
	}
</script>

<div class="visites-summary">
	<div class="visites-kpi">
		<span class="visites-kpi-value">{visites.length}</span>
		<span class="visites-kpi-label">visites planifiées</span>
	</div>
	{#if visitesEnRetard.length > 0}
		<div class="visites-kpi visites-kpi--danger">
			<span class="visites-kpi-value">{visitesEnRetard.length}</span>
			<span class="visites-kpi-label">en retard</span>
		</div>
	{/if}
	<div class="visites-kpi visites-kpi--ok">
		<span class="visites-kpi-value">{visitesAJour.length}</span>
		<span class="visites-kpi-label">en cours</span>
	</div>
</div>

{#if visites.length === 0}
	<div class="empty-state card">
		<h3>Aucune visite planifiée</h3>
		<p>Les visites récurrentes apparaîtront ici dès qu'un contrat avec fréquence sera créé.</p>
	</div>
{:else}
	<!--  Les retards d'abord : c'est ce qu'on vient chercher. -->
	{#if visitesEnRetard.length > 0}
		<h2 class="section-title" style="color:var(--color-danger)">⚠️ Visites en retard</h2>
		{#each visitesEnRetard as c (c.id)}
			<CarteVisite
				contrat={c}
				prestataireNom={nomDu(c)}
				ouverte={expandedContrats.has(c.id)}
				enRetard
				on:basculer={() => dispatch('basculer', c.id)}
				on:modifier={() => dispatch('modifier', c)}
				on:noter={() => dispatch('noter', c)}
			/>
		{/each}
	{/if}

	{#if visitesAJour.length > 0}
		<h2 class="section-title" style="margin-top:1rem">✅ Visites en cours</h2>
		{#each visitesAJour as c (c.id)}
			<CarteVisite
				contrat={c}
				prestataireNom={nomDu(c)}
				ouverte={expandedContrats.has(c.id)}
				on:basculer={() => dispatch('basculer', c.id)}
				on:modifier={() => dispatch('modifier', c)}
				on:noter={() => dispatch('noter', c)}
			/>
		{/each}
	{/if}
{/if}

<style>
	/*  Reprises À LA LETTRE de `prestataires/+page.svelte` : ces quatre classes ne
	    servaient QUE cet onglet, elles voyagent donc avec lui. Un déplacement de
	    balisage ne change pas l'apparence. */
	.visites-summary { display: flex; gap: .75rem; margin-bottom: 1.25rem; flex-wrap: wrap; }
	.visites-kpi { display: flex; flex-direction: column; align-items: center; padding: .6rem 1rem; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius); min-width: 90px; }
	.visites-kpi-value { font-size: 1.5rem; font-weight: 700; color: var(--color-primary); }
	.visites-kpi-label { font-size: .75rem; color: var(--color-text-muted); }
	.visites-kpi--danger .visites-kpi-value { color: var(--color-danger, #dc2626); }
	.visites-kpi--ok .visites-kpi-value { color: #16a34a; }
</style>
