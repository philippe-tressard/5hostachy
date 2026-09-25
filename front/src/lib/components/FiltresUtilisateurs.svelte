<!--
  La barre de filtres de la liste des utilisateurs (Admin) — recherche, type,
  compte, et les compteurs.

  🔴 Sortie de `admin/+page.svelte` le 26/09/2026 (#1329) : ses deux filtres
  étaient des `<select>` natifs repeints à la main (`.role-select`), à côté
  d'une barre de filtres partout ailleurs en pastilles. `ux-patterns` : au-delà
  de six entrées, `PastilleDeroulante` ; en dessous, des pastilles.
  `lint:seuil-listes` ne l'a pas vu — il cherchait la classe `filter-select`,
  qui n'existait plus nulle part.

  Le FILTRAGE reste dans la page : ce composant ne dit que ce qu'on a choisi.
-->
<script lang="ts">
	import PastilleDeroulante from '$lib/components/PastilleDeroulante.svelte';
	import ChoixPastilles from '$lib/components/ChoixPastilles.svelte';
	import { LIBELLES_STATUT_ABREGE } from '$lib/roles';

	export let recherche = '';
	export let statut = '';
	export let compte = '';
	/** Les compteurs affichés à droite. */
	export let affiches = 0;
	export let total = 0;
	export let nbCS = 0;

	const OPTIONS_STATUT = Object.entries(LIBELLES_STATUT_ABREGE).map(([val, label]) => ({
		val,
		label,
	}));
	const OPTIONS_COMPTE = [
		{ val: 'actif', label: 'Actifs' },
		{ val: 'inactif', label: 'En attente' },
	];
</script>

<div class="filtres-utilisateurs">
	<!--  Un champ LIBELLÉ, comme la recherche des badges (`BadgesCopropriete`) :
	      il était repeint à la main (`.user-search`), sans libellé. -->
	<div class="field recherche">
		<label for="admin-recherche-utilisateur">Rechercher par nom ou e-mail</label>
		<input
			id="admin-recherche-utilisateur"
			type="search"
			placeholder="Dupont, dupont@…"
			bind:value={recherche}
		/>
	</div>
	<PastilleDeroulante
		options={OPTIONS_STATUT}
		bind:valeur={statut}
		tous="Tous les types"
		libelle="Filtrer par type d’utilisateur"
	/>
	<ChoixPastilles
		options={OPTIONS_COMPTE}
		bind:valeur={compte}
		tous="Tous comptes"
		libelle="Filtrer par compte"
	/>
	<span class="aide">
		{affiches} / {total} utilisateur{total > 1 ? 's' : ''}
		&nbsp;·&nbsp;
		{nbCS} membre{nbCS > 1 ? 's' : ''} CS
	</span>
</div>

<style>
	.filtres-utilisateurs {
		display: flex;
		align-items: flex-end;
		gap: 0.75rem 1rem;
		margin-bottom: 1rem;
		flex-wrap: wrap;
	}
	.recherche {
		flex: 1;
		min-width: 200px;
		max-width: 340px;
		margin-bottom: 0;
	}
</style>
