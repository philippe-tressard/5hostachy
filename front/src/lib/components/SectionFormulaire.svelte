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
    • un intitulé en petites capitales — il structure sans concurrencer les
      libellés de champs, qui restent l'information principale ;
    • un filet fin au-dessus, sauf pour la première section : un trait avant le
      premier groupe séparerait la section de son propre titre de formulaire.

  ## Le titre EST le libellé quand la section n'a qu'un champ (16/08/2026)

  Première livraison, l'écran affichait :

      PÉRIMÈTRE
      Périmètre *                      [Copropriété entière]

  Le nom deux fois de suite, en deux typographies. Signalé par l'utilisateur,
  capture à l'appui, dès la mise en production. La redondance venait de ce que le
  champ portait déjà son intitulé (`PerimetrePicker`, `DestinatairePicker`,
  `FichiersUpload` le portent tous) et que la section en ajoutait un second.

  **Règle** : une section qui ne contient qu'UN champ ne répète pas son nom. Le
  titre de section devient le libellé — il porte l'astérisque du requis (`requis`)
  et le badge d'état (`badge`) —, et le champ n'écrit plus rien (`titre=""`).
  Les sections à PLUSIEURS champs (Détails, Clôture, Diffusion) gardent leur
  titre de groupe **et** les libellés de leurs champs : là, il n'y a pas
  redondance mais hiérarchie.

  ## L'accessibilité y gagne, et ce n'est pas un effet de bord

  `Périmètre *` était un `<div>` : décoratif pour un lecteur d'écran, qui
  annonçait donc un groupe de boutons sans nom. Le titre de section est
  désormais :
    • un vrai `<label for>` quand la section porte un contrôle labelable
      (`<select>`, `<input>`) — l'association est alors native ;
    • un `<h4 id>` sinon, l'appelant reliant son groupe par `aria-labelledby`.
      C'est le cas des pastilles et de l'éditeur riche, qui ne sont PAS des
      contrôles labelables : `for` n'y produirait aucune association, en silence.
-->
<script lang="ts">
	import Icon from './Icon.svelte';

	/** Intitulé de la section — ex. « Diffusion ». Vide : aucun titre, mais la
	    séparation reste, ce qui sert aux groupes évidents (le titre d'un objet). */
	export let titre = '';

	/** Icône du catalogue partagé (`$lib/icones-svg.json`), devant l’intitulé.
	    Les titres portaient des ÉMOJI ; l’en-tête de page, lui, prenait déjà ses
	    tracés dans le catalogue. Deux façons de désigner une section, dont une
	    qui dépend de la police du système (19/08/2026). */
	export let icone = '';

	/** Première section du formulaire : pas de filet au-dessus. */
	export let premiere = false;

	/** Ajoute l'astérisque des champs requis au titre. */
	export let requis = false;

	/** État résumé, à droite du titre — « Copropriété entière », « Tous les
	    résidents ». On lit ce qui est retenu sans dépiler les pastilles
	    (`ux-patterns` §9 quater). Vide : aucun badge. */
	export let badge = '';

	/** `id` du contrôle labelable unique de la section : le titre devient alors
	    un `<label for>`. Ne l'utiliser QUE pour `<select>`, `<input>`, `<textarea>` —
	    sur un `contenteditable` ou un groupe de boutons, `for` n'associe rien. */
	export let pour = '';

	/** `id` posé sur le titre, pour qu'un groupe s'y relie par `aria-labelledby`. */
	export let idTitre = '';
</script>

<section class="section-formulaire" class:premiere>
	{#if titre}
		{#if pour}
			<label class="section-titre" for={pour} id={idTitre || undefined}>
				{#if icone}<Icon name={icone} size={15} />{/if}{titre}{#if requis} *{/if}
				{#if badge}<span class="badge badge-green section-badge">{badge}</span>{/if}
			</label>
		{:else}
			<h4 class="section-titre" id={idTitre || undefined}>
				{#if icone}<Icon name={icone} size={15} />{/if}{titre}{#if requis} *{/if}
				{#if badge}<span class="badge badge-green section-badge">{badge}</span>{/if}
			</h4>
		{/if}
	{/if}
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
	/*  Petites capitales : l'intitulé de section se lit comme un repère de
	    structure. Il était gris ; il reprend la couleur du texte depuis qu'il
	    porte AUSSI le libellé du champ, l'astérisque du requis et le badge —
	    un intitulé de champ en gris clair se lit moins bien que ce qu'il nomme. */
	.section-titre {
		display: flex;
		align-items: center;
		gap: .4rem;
		flex-wrap: wrap;
		margin: 0 0 .6rem;
		font-size: .72rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: .06em;
		color: var(--color-text);
	}
	/*  Un `<label>` de section désigne un contrôle : il doit se cliquer. */
	label.section-titre {
		cursor: pointer;
	}
	/*  Le badge ne suit PAS les petites capitales du titre : c'est une valeur,
	    pas un intitulé — la lire en majuscules espacées la rendrait illisible. */
	.section-badge {
		font-size: .72rem;
		text-transform: none;
		letter-spacing: normal;
		font-weight: 600;
	}
</style>
