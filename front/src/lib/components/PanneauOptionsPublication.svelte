<!--
  PanneauOptionsPublication.svelte — les options d'une actualité, modifiables
  seules, sans passer par l'édition ni par un commentaire.

  Sorti d'`actualites/+page.svelte` le 05/09/2026, sur refus du contrôle de
  modularité : la page accueillait les mêmes options DANS le formulaire de
  commentaire (demande de l'utilisateur), et dépassait son plafond.

  ⚠️ **Deux chemins mènent désormais aux mêmes quatre options** : ce panneau, et
  la section 2 du formulaire de commentaire. C'est un écart connu au principe
  « un geste, un endroit » (`ux-patterns` §10 bis) — ils ne répondent pas tout à
  fait à la même question (« je corrige une option » contre « je commente, et
  j'en profite pour revalider le ciblage »), mais s'il faut n'en garder qu'un,
  c'est celui-ci qui part : le formulaire de commentaire fait les deux.

  Le composant ne décide de rien : la page tient la copie de travail et appelle
  le serveur. Il montre, et dit ce qu'on a cliqué.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import OptionsPublication from '$lib/components/OptionsPublication.svelte';
	import type { Publication } from '$lib/api';

	/** La publication concernée — pour son périmètre et son épinglage actuel. */
	export let pub: Publication;
	/** La copie de travail, tenue par la page : on n'écrit qu'après le serveur. */
	export let options: {
		epingle: boolean;
		urgente: boolean;
		brouillon: boolean;
		confidentiel: boolean;
	};
	export let enregistrement = false;

	const dispatch = createEventDispatcher<{ enregistrer: void; annuler: void }>();
</script>

<!--  ── Options de publication ──
      LE MÊME composant qu'à la création et à l'édition
      (`OptionsPublication`, section 2 du cadre #430) : ni copie, ni
      variante. Il porte déjà la règle « Confidentiel exige un
      périmètre restreint », qu'un panneau réécrit n'aurait pas eue.
      `role="presentation"` : ce conteneur n'est qu'un relais, il
      arrête la propagation pour que cocher ne referme pas la carte. -->
<div class="options-form" role="presentation" on:click|stopPropagation on:keydown|stopPropagation>
	<h4 class="options-titre">Options de publication</h4>
	<OptionsPublication
		perimetreCible={pub.perimetre_cible ?? []}
		dejaEpingle={pub.epingle ?? false}
		bind:epingle={options.epingle}
		bind:urgente={options.urgente}
		bind:brouillon={options.brouillon}
		bind:confidentiel={options.confidentiel}
	/>
	<!--  L'annulation vit à côté d'« Enregistrer » — norme du
	      18/08/2026, la même que sur Tickets et sur l'édition. -->
	<div class="options-actions">
		<button
			class="btn btn-primary btn-sm"
			disabled={enregistrement}
			on:click={() => dispatch('enregistrer')}
			>{enregistrement ? 'Enregistrement…' : 'Enregistrer'}</button
		>
		<button
			class="btn btn-outline btn-sm"
			disabled={enregistrement}
			on:click={() => dispatch('annuler')}>Annuler</button
		>
	</div>
</div>

<style>
	.options-form {
		padding: 0.5rem 0;
	}
	.options-titre {
		margin: 0 0 0.6rem;
		font-size: 0.9rem;
		font-weight: 600;
	}
	.options-actions {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	/*  Sur téléphone, les deux boutons prennent toute la largeur plutôt que de
	    se serrer — même règle que les autres formulaires du site. */
	@media (max-width: 480px) {
		.options-actions {
			flex-direction: column;
		}
		.options-actions :global(.btn) {
			width: 100%;
			min-height: 44px;
		}
	}
</style>
