<!--
  FiltresAffaires.svelte — la barre de filtres de la page Affaires : Nature,
  Suivi, Catégorie.

  Sortie de la page le 23/09/2026 (variante A arbitrée à l'écran) : la page
  était à son plafond de 500 lignes, et la barre y portait déjà son propre
  style. Elle ne décide rien — elle expose trois valeurs liées.
-->
<script lang="ts">
	import ChoixPastilles from '$lib/components/ChoixPastilles.svelte';
	import { OPTIONS_FILTRE_CATEGORIE, OPTIONS_FILTRE_NATURE } from '$lib/tickets';

	/** Les états présents dans la liste — calculés par la page, qui la connaît. */
	export let optionsStatut: { value: string; label: string }[] = [];
	export let nature = '';
	export let statut = '';
	export let categorie = '';
</script>

<!--  🔴 DEUX rangées écrites à la main, soit la deuxième et la troisième
      écriture du motif « choisir une entrée d'une liste courte » —
      `ChoixPastilles` (#491) le porte, avec l'entrée qui ne choisit rien, le
      défilement horizontal et le libellé de groupe accessible.

      ⚠️ Le libellé N'EST PAS un `<label>` : une rangée de `<button>` n'est pas
      labelable, et un `for` posé dessus n'associe rien **en silence**
      (`ux-patterns` §9 septies). Le composant pose `role="group"` +
      `aria-labelledby` — c'est une des raisons d'être de ce composant, et elle
      se perdait à chaque recopie.
      Chaque rangée porte son libellé DEVANT (23/09/2026, variante A arbitrée à
      l'écran) : « Nature » et « Suivi » se confondaient ; Catégorie a sa ligne. -->
<div class="filters filtres-affaires">
	<ChoixPastilles
		options={OPTIONS_FILTRE_NATURE}
		bind:valeur={nature}
		tous="Tous"
		libelle="Nature"
		libelleDevant
	/>
	<span class="filter-sep"></span>
	<ChoixPastilles
		options={optionsStatut.map((s) => ({ val: s.value, label: s.label }))}
		bind:valeur={statut}
		tous="Tous"
		libelle="Suivi"
		libelleDevant
	/>
	<span class="filtre-saut"></span>
	<ChoixPastilles
		options={OPTIONS_FILTRE_CATEGORIE}
		bind:valeur={categorie}
		tous="Toutes"
		libelle="Catégorie"
		libelleDevant
	/>
</div>

<style>
	/*  `.filters` vient de la feuille commune (#446) ; ici, le filet entre
	    Nature et Suivi et le saut avant Catégorie (variante A, 23/09/2026).
	    Sur téléphone, un groupe par ligne : un filet en bout de ligne ne
	    séparerait plus rien. */
	.filtres-affaires {
		row-gap: 0.6rem;
	}
	.filter-sep {
		width: 1px;
		height: 1.6rem;
		background: var(--color-border);
		margin: 0 0.75rem;
	}
	.filtre-saut {
		flex-basis: 100%;
	}
	@media (max-width: 767px) {
		.filtres-affaires {
			flex-direction: column;
			align-items: stretch;
		}
		.filter-sep,
		.filtre-saut {
			display: none;
		}
	}
</style>
