<!--
  Une SECTION de formulaire : un intitulé, une séparation, et son contenu.

  POURQUOI CE COMPOSANT (16/08/2026). L'ordre des champs avait été fixé — Titre,
  champs spécifiques, Workflow, Périmètre, Destinataires, Description, Photos,
  Documents, Diffusion — mais **rien ne le montrait à l'écran** : les champs se
  suivaient sans respiration, et l'utilisateur a demandé le sous-titre manquant
  avant de constater qu'aucune section n'était nommée nulle part.

  « Sépare bien chaque section, il y a peut-être l'UX à revoir pour cela. »

  Ordonner ne suffit pas : une suite de dix champs sans repère se lit comme une
  liste, pas comme des groupes de décisions. Le titre dit CE QU'ON DÉCIDE ici
  (à qui ça s'adresse, comment ça se diffuse), le filet le sépare de ce qui suit.

  DEUX NIVEAUX DE MARQUAGE, volontairement discrets :
    • un intitulé en petites capitales, gris — il structure sans concurrencer les
      libellés de champs, qui restent l'information principale ;
    • un filet fin au-dessus, sauf pour la première section : un trait avant le
      premier groupe séparerait la section de son propre titre de formulaire.

  Le composant ne décide de RIEN d'autre : ni de l'ordre (c'est l'écran qui le
  porte, selon la skill `ux-patterns` §9 sexies), ni du contenu. Il ne fait que
  rendre visible un groupement qui existait déjà dans l'intention.
-->
<script lang="ts">
	/** Intitulé de la section — ex. « Diffusion ». Vide : aucun titre, mais la
	    séparation reste, ce qui sert aux groupes évidents (le titre d'un objet). */
	export let titre = '';

	/** Première section du formulaire : pas de filet au-dessus. */
	export let premiere = false;
</script>

<section class="section-formulaire" class:premiere>
	{#if titre}<h4 class="section-titre">{titre}</h4>{/if}
	<slot />
</section>

<style>
	.section-formulaire {
		border-top: 1px solid var(--color-border);
		padding-top: .9rem;
		margin-top: .9rem;
	}
	/*  La première section n'est séparée de rien : le titre de la boîte
	    (`FormulaireCreation`) joue déjà ce rôle au-dessus d'elle. */
	.premiere {
		border-top: none;
		padding-top: 0;
		margin-top: 0;
	}
	/*  Petites capitales grises : l'intitulé de section doit se lire comme un
	    repère de structure, pas comme un libellé de champ — sinon il entre en
	    concurrence avec « Titre », « Description » et le reste. */
	.section-titre {
		margin: 0 0 .6rem;
		font-size: .72rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: .06em;
		color: var(--color-text-muted);
	}
</style>
