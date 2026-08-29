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

	/** Icône Lucide facultative, affichée avant le libellé. */
	export let icone = '';

	/** Chevron « › » : annonce qu'un second niveau existe derrière cette pastille.
	    Sans lui, rien n'indiquait qu'un bâtiment cachait neuf espaces, et personne
	    ne cliquait (signalé le 12/08/2026). */
	export let chevron = false;
</script>

<!--  ⚠️ `$$slots.detail` et non une prop : c'est le SEUL moyen pour Svelte de
      savoir si l'appelant a fourni un sous-texte. Sans cette condition, la
      pastille passerait en deux lignes chez tout le monde — y compris là où il
      n'y a rien à mettre dessous. -->
<button
	type="button"
	class="pastille"
	class:active
	class:petite
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
