<!--
  LA pastille de sélection — le bouton arrondi qu'on trouve sur Périmètre,
  Destinataires, les filtres et les profils. Un seul objet, qui porte son
  balisage ET son style.

  POURQUOI CE COMPOSANT EXISTE (16/08/2026, régression livrée en v2.67.11).
  Ces règles ne vivaient que dans `PerimetrePicker.svelte`, donc scopées à lui
  par Svelte. Le jour où un second composant a repris le même balisage (l'ancien
  `SelecteurCiblage`, qui servait au ciblage des sondages avant que celui-ci
  rejoigne le standard le 16/08/2026), il a hérité de la structure SANS le
  style : les pastilles sont parties en production nues, sous forme de
  rectangles collés — « Bâtiment 1Bâtiment 2Bâtiment 3 ».

  ⚠️ RIEN NE L'AVAIT SIGNALÉ, et c'est le vrai enseignement. `svelte-check` sait
  dire qu'un sélecteur défini n'est pas utilisé ; il ne sait PAS dire qu'une
  classe utilisée n'est définie nulle part. Le contrôle qui a sauvé les autres
  extractions (« aucun Unused CSS selector nouveau ») est aveugle dans ce sens-là.

  Et la réparation évidente — monter `.pill` dans `app.css` — a été écartée par
  l'utilisateur : « le CSS doit être associé à l'objet pour ne pas avoir des
  divergences ». Un style séparé de son balisage peut être modifié d'un côté sans
  l'autre ; réunis dans un composant, ils ne peuvent plus diverger, et le style
  ne peut plus manquer à l'appel puisqu'il voyage avec.

  UTILISATION :
    <Pastille active={…} on:click={…}>Bâtiment 1</Pastille>
    <Pastille active icone="building-2" chevron>Bâtiment 2</Pastille>
    <Pastille petite active={…}>Hall</Pastille>
    <Pastille active={…}>
      Plomberie
      <span slot="detail">fuites, sanitaires</span>
    </Pastille>
-->
<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';

	/** Pastille retenue — fond plein. */
	export let active = false;

	/** Variante réduite, pour un second niveau de précision. */
	export let petite = false;

	/**  Cet espace est-il PRIVATIF — un logement, une cave, une place attribuée ?
	 *   Demandé le 31/08/2026 : l'arborescence n'avait pas de mot pour dire que
	 *   « Logement » est chez quelqu'un quand « Hall d'entrée » est à tout le
	 *   monde, alors que c'est la première question devant une demande.
	 *
	 *   Le repère est un **contour discontinu** : il se lit sans couleur — donc
	 *   sans entrer en concurrence avec l'état RETENU, qui est le plein — et sans
	 *   ajouter de symbole, la pastille portant déjà son icône.
	 *
	 *   ⚠️ **L'appelant ne le passe QUE sur une pastille pleine.** Dès qu'une
	 *   rangée se contracte, la pastille résume plusieurs espaces à la fois : un
	 *   contour qui dirait « privatif » y parlerait d'un seul d'entre eux. Le
	 *   repère disparaît donc avec la contraction, ce qui est la règle demandée. */
	export let privatif = false;

	/** Icône Lucide facultative, affichée avant le libellé. */
	export let icone = '';

	/** Chevron « › » : annonce qu'un second niveau existe derrière cette pastille.
	    Sans lui, rien n'indiquait qu'un bâtiment cachait neuf espaces, et personne
	    ne cliquait (signalé le 12/08/2026). */
	export let chevron = false;

	/**
	 * Rendre un **vrai bouton radio** plutôt qu'un `<button>` — `{ nom, valeur }`,
	 * `nom` étant le groupe et `valeur` ce que cette pastille sélectionne.
	 *
	 * ## Pourquoi (30/08/2026, signalé à l'écran)
	 *
	 * > « Dans tickets tu ne peux pas réduire ces pastilles à la même taille que
	 * >   nouveau prestataire »
	 *
	 * Les cinq catégories de ticket étaient des cartes maison (`.cat-option`,
	 * grille à deux colonnes, bordure 2 px, padding double) — deux fois plus
	 * hautes que les pastilles du même site, pour la même question posée à
	 * l'utilisateur.
	 *
	 * 🔴 **Elles ne pouvaient PAS être converties jusqu'ici**, et `ux-patterns` le
	 * disait : *« un vrai `radiogroup` avec des `<input type="radio">` ne se
	 * convertit pas — `Pastille` rend un `<button>`, la navigation par flèches et
	 * l'annonce du lecteur d'écran y seraient perdues. L'uniformité ne se paie pas
	 * en accessibilité. »*
	 *
	 * L'argument reste juste. Ce qui change, c'est la réponse : **on enrichit
	 * l'objet au lieu de le contourner.** Avec `radio`, la pastille rend un
	 * `<label>` portant un `<input type="radio">` visuellement masqué — apparence
	 * de pastille, sémantique de radiogroup, flèches et lecteur d'écran intacts.
	 *
	 * ⚠️ Le `<input>` est masqué par `clip`, **jamais par `display:none`** : ce
	 * dernier le retire de l'ordre de tabulation et de l'arbre d'accessibilité,
	 * c'est-à-dire qu'il annule très exactement ce que ce mode existe pour
	 * préserver. C'est ce que faisait `.cat-option input[type='radio']`.
	 */
	export let radio: { nom: string; valeur: string } | null = null;
</script>

<!--  ⚠️ `$$slots.detail` et non une prop : c'est le SEUL moyen pour Svelte de
      savoir si l'appelant a fourni un sous-texte. Sans cette condition, la
      pastille passerait en deux lignes chez tout le monde — y compris là où il
      n'y a rien à mettre dessous. -->
{#if radio}
	<!--  Le mode radio : même apparence, sémantique de `radiogroup`. Le contenu
	      est écrit deux fois dans le balisage parce que Svelte n'a pas d'élément
	      « `<button>` ou `<label>` selon le cas » qui accepte un `<slot>` — mais
	      le STYLE, lui, n'existe qu'une fois, et c'est ce qui compte : c'est sa
	      duplication qui produit les divergences (v2.67.11). -->
	<label
		class="pastille"
		class:active
		class:petite
		class:privatif
		class:avec-detail={$$slots.detail}
	>
		<input
			type="radio"
			class="pastille-radio"
			name={radio.nom}
			value={radio.valeur}
			checked={active}
			on:change
		/>
		{#if icone}<Icon name={icone} size={15} />{/if}
		<span class="pastille-corps">
			<span class="pastille-libelle"><slot /></span>
			{#if $$slots.detail}<span class="pastille-detail"><slot name="detail" /></span>{/if}
		</span>
	</label>
{:else}
	<button
		type="button"
		class="pastille"
		class:active
		class:petite
		class:privatif
		class:avec-detail={$$slots.detail}
		on:click
	>
		{#if icone}<Icon name={icone} size={15} />{/if}
		<span class="pastille-corps">
			<span class="pastille-libelle"><slot /></span>
			{#if $$slots.detail}<span class="pastille-detail"><slot name="detail" /></span>{/if}
		</span>
		{#if chevron}<span class="pastille-chevron" aria-hidden="true">›</span>{/if}
	</button>
{/if}

<style>
	.pastille {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		padding: 0.35rem 0.7rem;
		border: 1px solid var(--color-border);
		border-radius: 999px;
		background: var(--color-surface);
		font-size: 0.82rem;
		cursor: pointer;
		color: var(--color-text-muted);
		transition: all 0.12s;
		white-space: nowrap;
	}
	/*  PRIVATIF : un contour discontinu, et rien d'autre. Pas de couleur — elle
	    est prise par l'état retenu — ni de symbole — l'icône du nœud l'occupe
	    déjà. Le trait suffit à dire « délimité, à quelqu'un », et il reste lisible
	    sur la pastille pleine comme sur la pastille retenue. */
	.pastille.privatif {
		border-style: dashed;
		border-width: 1.5px;
	}
	.pastille:hover {
		border-color: var(--color-primary);
		color: var(--color-text);
	}
	.active {
		background: var(--color-primary);
		color: #fff;
		border-color: var(--color-primary);
	}
	.petite {
		font-size: 0.78rem;
		padding: 0.28rem 0.6rem;
	}
	.pastille-chevron {
		margin-left: 0.3rem;
		opacity: 0.6;
	}

	/*  🔴 Le bouton radio est masqué à l'ŒIL, jamais à l'accessibilité.
	    `display: none` l'aurait retiré de l'ordre de tabulation et de l'arbre
	    d'accessibilité — donc annulé la navigation par flèches et l'annonce du
	    lecteur d'écran, c'est-à-dire tout ce que ce mode existe pour préserver.
	    C'est pourtant ce que faisait `.cat-option input[type='radio']`, qu'il
	    remplace. Le découpage à 1 px est le motif standard : l'élément reste
	    focusable et lu, il n'occupe simplement aucune surface. */
	.pastille-radio {
		position: absolute;
		width: 1px;
		height: 1px;
		margin: -1px;
		padding: 0;
		overflow: hidden;
		clip: rect(0 0 0 0);
		clip-path: inset(50%);
		white-space: nowrap;
		border: 0;
	}
	/*  Le focus clavier doit se VOIR : sans cela, un utilisateur au clavier
	    déplace une sélection invisible. Le contour est porté par la pastille,
	    puisque c'est elle qu'on regarde. */
	.pastille:has(.pastille-radio:focus-visible) {
		outline: 2px solid var(--color-primary);
		outline-offset: 2px;
	}

	/*  ── Le SOUS-TEXTE (29/08/2026, arbitré avec l'utilisateur) ──────────────
	    Deux listes portaient une description par option — type de prestataire,
	    catégorie de ticket — et étaient rendues en cartes maison pour cette
	    seule raison. La pastille les accueille désormais plutôt que d'être
	    contournée : c'est l'objet qui s'enrichit, pas un second motif qui naît.

	    ⚠️ Sans `detail`, RIEN ne change : `.pastille-corps` reste en ligne et la
	    pastille garde sa hauteur. Un enrichissement qui modifierait les appelants
	    existants ne serait pas un enrichissement. */
	/*  Le libellé porte le poids ; le sous-texte s'en distingue par la taille et
	    l'opacité, jamais par une couleur qui deviendrait illisible en actif. */
	.pastille-libelle {
		font-weight: inherit;
	}
	.pastille-corps {
		display: inline-flex;
		flex-direction: column;
		align-items: flex-start;
		line-height: 1.25;
	}
	.avec-detail {
		align-items: flex-start;
		padding: 0.45rem 0.8rem;
		border-radius: var(--radius);
		/*  Le sous-texte est une phrase : elle doit pouvoir se replier. */
		white-space: normal;
		text-align: left;
		/*  🔴 Une BORNE, pas une largeur — arbitré à l'écran le 30/08/2026 :
		    *« mets le libellé sur 2 lignes pour diminuer la largeur »*.

		    Sans elle, la pastille s'étire à la longueur de sa phrase la plus
		    longue : « Équipement défectueux, ascenseur, chauffage… » faisait à
		    elle seule le double des autres, et une rangée de cinq débordait de
		    l'écran. Bornée, chaque pastille se replie sur deux lignes et la
		    rangée redevient lisible d'un coup d'œil.

		    ⚠️ `max-width` et non `width` : une pastille au libellé court —
		    « Gestion / Syndic, gestion locative » — reste étroite. Une largeur
		    fixe alignerait au prix d'un vide à droite de chacune. */
		max-width: 13rem;
	}
	.pastille-detail {
		font-size: 0.72rem;
		opacity: 0.75;
		font-weight: 400;
	}
	/*  Sur fond plein, le sous-texte reste lisible : c'est l'opacité qui le
	    distingue, jamais une couleur fixe qui deviendrait illisible en actif. */
	.active .pastille-detail {
		opacity: 0.85;
	}

	/*  Sous 480 px, une pastille à sous-texte prend toute la largeur : côte à
	    côte, deux phrases de six mots débordent (socle 11 §10). */
	@media (max-width: 480px) {
		.avec-detail {
			width: 100%;
		}
	}
</style>
