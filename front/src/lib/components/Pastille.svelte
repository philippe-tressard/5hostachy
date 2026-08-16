<!--
  LA pastille de sélection — le bouton arrondi qu'on trouve sur Périmètre,
  Destinataires, les filtres et les profils. Un seul objet, qui porte son
  balisage ET son style.

  POURQUOI CE COMPOSANT EXISTE (16/08/2026, régression livrée en v2.67.11).
  Ces règles ne vivaient que dans `PerimetrePicker.svelte`, donc scopées à lui
  par Svelte. Le jour où un second composant a repris le même balisage
  (`SelecteurCiblage`, pour le ciblage des sondages), il a hérité de la structure
  SANS le style : les pastilles sont parties en production nues, sous forme de
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

<button type="button" class="pastille" class:active class:petite on:click>
	{#if icone}<Icon name={icone} size={15} />{/if}<slot />{#if chevron}<span class="pastille-chevron" aria-hidden="true">›</span>{/if}
</button>

<style>
	.pastille {
		display: inline-flex;
		align-items: center;
		gap: .35rem;
		padding: .35rem .7rem;
		border: 1px solid var(--color-border);
		border-radius: 999px;
		background: var(--color-surface);
		font-size: .82rem;
		cursor: pointer;
		color: var(--color-text-muted);
		transition: all .12s;
		white-space: nowrap;
	}
	.pastille:hover { border-color: var(--color-primary); color: var(--color-text); }
	.active { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
	.petite { font-size: .78rem; padding: .28rem .6rem; }
	.pastille-chevron { margin-left: .3rem; opacity: .6; }
</style>
