<!--
  FiltresAffaires.svelte — la barre de filtres de la page Affaires : Nature,
  Suivi, puis la RECHERCHE libre.

  Sortie de la page le 23/09/2026 (variante A arbitrée à l'écran) : la page
  était à son plafond de 500 lignes, et la barre y portait déjà son propre
  style. Elle ne décide rien — elle expose des valeurs liées.

  🔴 La ligne « Catégorie » a cédé la place à la recherche le 27/09/2026
  (maquette A, avec l'extrait et les Archives de la C) : on cherche un mot, pas
  une case — et la catégorie reste trouvable, le serveur cherche aussi son
  libellé (`app/utils/recherche_affaires.py`).
-->
<script lang="ts">
	import ChoixPastilles from '$lib/components/ChoixPastilles.svelte';
	import { OPTIONS_FILTRE_NATURE } from '$lib/tickets';
	import type { EtatRecherche } from '$lib/recherche-affaires';

	/** Les états présents dans la liste — calculés par la page, qui la connaît. */
	export let optionsStatut: { value: string; label: string }[] = [];
	export let nature = '';
	export let statut = '';
	export let recherche = '';
	export let inclureArchives = false;
	/** Où en est la recherche — tenu par `rechercheAffaires()`. */
	export let etat: EtatRecherche;
	/** Combien la liste en montre, et combien d'archivées elle tait. */
	export let affichees = 0;
	export let archivees = 0;

	const pluriel = (n: number, mot: string) => `${n} ${mot}${n > 1 ? 's' : ''}`;
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
      l'écran) : « Nature » et « Suivi » se confondaient ; la recherche a sa ligne. -->
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
	<div class="field champ-en-ligne recherche-affaires">
		<label class="libelle-groupe libelle-devant" for="recherche-affaires">Recherche</label>
		<div class="recherche-saisie">
			<input
				id="recherche-affaires"
				type="search"
				placeholder="Un mot, un nom, un n° d'affaire…"
				aria-describedby="recherche-affaires-aide"
				bind:value={recherche}
			/>
			<label class="case">
				<input type="checkbox" bind:checked={inclureArchives} />
				Inclure les Archives
			</label>
		</div>
		<p class="aide" id="recherche-affaires-aide">
			Cherche partout : n°, titre, description, catégorie, lieu, auteur, prestataire, équipement,
			suites, messages et pièces jointes — sans tenir compte des accents ni des majuscules.
		</p>
	</div>
</div>

{#if etat.terme || etat.enCours || etat.erreur}
	<p class="bilan-recherche" role="status">
		{#if etat.erreur}
			La recherche n'a pas abouti : {etat.erreur}
		{:else if etat.enCours && !etat.resultats}
			Recherche…
		{:else}
			<strong>{pluriel(affichees, 'affaire')}</strong> pour « {etat.terme} »
			{#if archivees && !inclureArchives}
				· {pluriel(archivees, 'autre')} aux Archives
				<button
					type="button"
					class="btn btn-outline btn-sm"
					on:click={() => (inclureArchives = true)}>Les inclure</button
				>
			{/if}
		{/if}
		<button type="button" class="btn btn-outline btn-sm effacer" on:click={() => (recherche = '')}
			>Effacer la recherche</button
		>
	</p>
{/if}

<style>
	/*  `.filters` vient de la feuille commune (#446) ; ici, le filet entre
	    Nature et Suivi et le saut avant la recherche (variante A, 23/09/2026).
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
	/*  Le libellé DEVANT, comme « Nature » et « Suivi » : `.field` est une
	    colonne, la recherche est une ligne. L'aide passe dessous, alignée sur le
	    champ. */
	.recherche-affaires {
		flex: 1;
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		column-gap: 0.5rem;
		row-gap: 0.25rem;
		align-items: center;
		max-width: 52rem;
	}
	.recherche-saisie {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem 1rem;
		align-items: center;
	}
	.recherche-saisie input[type='search'] {
		flex: 1;
		min-width: 12rem;
	}
	.recherche-affaires .aide {
		grid-column: 2;
		margin: 0;
	}
	.bilan-recherche {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
		align-items: baseline;
		margin: -0.5rem 0 1rem;
		font-size: 0.875rem;
		color: var(--color-text-muted);
	}
	.bilan-recherche strong {
		color: var(--color-text);
	}
	.effacer {
		margin-left: auto;
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
		.recherche-affaires {
			grid-template-columns: minmax(0, 1fr);
		}
		.recherche-affaires .aide {
			grid-column: 1;
		}
	}
</style>
