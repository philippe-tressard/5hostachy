<script lang="ts">
	/**
	 * **Un panneau de l'onglet Télémétrie** — sa carte, son intitulé, sa période,
	 * son pied de notes. Écrit une fois (03/10/2026, #1628 #1632).
	 *
	 * 🔴 L'intitulé d'un panneau était écrit DEUX fois au caractère près —
	 * `.tl-section-title` dans `OngletTelemetrie`, `.titre-panneau` dans `TopPages`
	 * (#495 : un style scopé ne passe pas dans un composant enfant, d'où la copie).
	 * Les panneaux « Qui vient » et « Durées d'affichage » en auraient fait une
	 * troisième et une quatrième : ils passent tous par ici, et les deux copies
	 * sont parties.
	 *
	 * Le contenu (tableaux, notes) est écrit par l'appelant ; les paragraphes du
	 * pied sont stylés ICI. Une cellule chiffrée prend `.nombre` et un texte
	 * discret `.text-muted-sm`, tous deux partagés (`src/styles/`) : un style
	 * posé ici pour les cellules de l'appelant ne le suivrait pas (#562).
	 */
	/** Avec son pictogramme : « ⚠️ Erreurs vues par les résidents ». */
	export let titre: string;
	/** Ce que couvrent les chiffres (« aujourd’hui », « 30 derniers jours »). */
	export let periode = '';
</script>

<div class="card panneau">
	<h3 class="titre">
		{titre}
		{#if periode}<span class="periode">{periode}</span>{/if}
	</h3>
	<slot />
	{#if $$slots.pied}
		<div class="pied"><slot name="pied" /></div>
	{/if}
</div>

<style>
	.panneau {
		margin-top: 1.25rem;
	}
	.titre {
		font-size: var(--fs-lg);
		font-weight: 600;
		margin: 0 0 0.75rem;
		padding: 0.75rem 1rem 0;
	}
	.periode {
		font-size: var(--fs-sm);
		font-weight: 400;
		color: var(--color-text-muted);
		margin-left: 0.4rem;
	}
	.pied :global(p) {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		line-height: 1.5;
		margin: 0.5rem 1rem 0.75rem;
	}
</style>
