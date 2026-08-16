<script lang="ts">
	/**
	 * `donnees` — imports et audits, qui alimentent les comptes et les accès.
	 * `configuration` — ce qui DÉCRIT la copropriété : sa fiche, ses périmètres.
	 *   Placé juste après « Paramétrage site », dont il est le prolongement.
	 *
	 * Les deux groupes existent parce que « Fiche copropriété » et « Périmètres »
	 * se trouvaient sous 👥 Gestion utilisateurs, où ils n'ont rien à faire :
	 * ils ne décrivent pas des personnes mais l'immeuble (signalé le 12/08/2026).
	 */
	import Onglet from '$lib/components/Onglet.svelte';

	export let groupe: 'donnees' | 'configuration' = 'donnees';
</script>

<!--
	Les écrans d'administration qui vivent sur leur PROPRE route, par opposition
	aux onglets internes d'`admin/+page.svelte`.

	Extrait le 12/08/2026 en reliant `copropriete` et `sauvegardes` (#307) :
	`admin/+page.svelte` est à 2259 lignes et le garde-fou de modularité — rang 1,
	sans exception — refuse qu'un fichier de plus de 500 lignes grossisse.

	⚠️ Les adresses restent écrites EN TOUTES LETTRES, une par lien. Les produire
	par un `{#each}` sur un tableau de routes ferait disparaître le littéral
	`/admin/…`, et `scripts/check-routes-atteignables.mjs` — le contrôle né de
	#307, qui cherche exactement ce littéral — déclarerait alors ces écrans
	orphelins. Un raccourci d'écriture qui aveugle son propre garde-fou coûte plus
	qu'il ne rapporte. Le découpage en deux groupes se fait donc par `{#if}`, qui
	laisse les littéraux intacts.
-->
{#if groupe === 'donnees'}
	<Onglet href="/admin/lots-import">Import Lots</Onglet>
	<Onglet href="/admin/telecommandes-import">Import TC</Onglet>
	<Onglet href="/admin/vigiks-import">Import Vigik</Onglet>
	<Onglet href="/admin/audit-lots">Audit lots</Onglet>
{:else}
	<Onglet href="/admin/copropriete">Fiche copropriété</Onglet>
	<Onglet href="/admin/patrimoine">Périmètres</Onglet>
{/if}
