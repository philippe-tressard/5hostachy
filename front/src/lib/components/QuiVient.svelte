<script lang="ts">
	/**
	 * **Qui vient** — la part des comptes venus sur la période (#1628), par profil,
	 * par type de résident et par bâtiment. Présentation arbitrée sur maquette le
	 * 03/10/2026 (proposition A).
	 *
	 * Chaque ligne porte ses DEUX nombres avec le taux : « 33 % » d'un bâtiment de
	 * trois comptes ne veut rien dire seul. Les profils sont des rôles CUMULÉS —
	 * un copropriétaire du conseil compte sous les deux —, donc leurs lignes ne
	 * s'additionnent pas, et l'écran le dit. La règle de calcul : `utils/adoption.py`.
	 */
	import PanneauTelemetrie from '$lib/components/PanneauTelemetrie.svelte';
	import type { Adoption, LigneAdoption } from '$lib/api';

	export let adoption: Adoption;

	$: groupes = [
		{ titre: 'Par profil', lignes: adoption.par_profil },
		{ titre: 'Par type de résident', lignes: adoption.par_type },
		{ titre: 'Par bâtiment', lignes: adoption.par_batiment },
	] satisfies { titre: string; lignes: LigneAdoption[] }[];

	const pourcentage = (l: LigneAdoption) => (l.taux == null ? '—' : `${l.taux} %`);
</script>

<PanneauTelemetrie titre="👥 Qui vient" periode="{adoption.jours} derniers jours">
	<div class="table-wrap">
		<table class="table">
			<thead>
				<tr><th></th><th class="nombre">Venus / comptes</th><th class="nombre">%</th></tr>
			</thead>
			<tbody>
				<tr class="global">
					<td>{adoption.global.libelle}</td>
					<td class="nombre">{adoption.global.actifs} / {adoption.global.comptes}</td>
					<td class="nombre">{pourcentage(adoption.global)}</td>
				</tr>
			</tbody>
			{#each groupes as g (g.titre)}
				{#if g.lignes.length}
					<tbody>
						<tr><th colspan="3" class="groupe">{g.titre}</th></tr>
						{#each g.lignes as l (l.libelle)}
							<tr>
								<td>{l.libelle}</td>
								<td class="nombre">{l.actifs} / {l.comptes}</td>
								<td class="nombre">{pourcentage(l)}</td>
							</tr>
						{/each}
					</tbody>
				{/if}
			{/each}
		</table>
	</div>
	<svelte:fragment slot="pied">
		<p>
			Un compte est « venu » s’il a ouvert au moins une page sur la période. Un compte peut avoir
			plusieurs profils : leurs lignes ne s’additionnent pas.
			{#if adoption.refus}
				{adoption.refus} compte{adoption.refus > 1 ? 's ont' : ' a'} refusé la mesure d’audience : exclu{adoption.refus >
				1
					? 's'
					: ''} du calcul.
			{/if}
		</p>
	</svelte:fragment>
</PanneauTelemetrie>

<style>
	.global > td {
		font-weight: 700;
	}
	.groupe {
		text-align: left;
	}
</style>
