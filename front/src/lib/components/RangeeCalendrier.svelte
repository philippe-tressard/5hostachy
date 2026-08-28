<!--
  RangeeCalendrier.svelte — LA rangée compacte du calendrier, écrite une fois.

  ## Pourquoi ce composant (#432, 18/08/2026)

  `calendrier/+page.svelte` rendait **quatre** rangées à la main — une publication
  archivée, une prestation archivée, un événement archivé, une maintenance
  récurrente — avec la même structure *type · corps · date · actions* recopiée
  quatre fois, et un seul jeu de règles `.event-*` dans le `<style>` de la page
  pour les servir toutes.

  🔴 **C'est ce partage qui empêchait de découper**, et le fichier le disait
  lui-même : *« `.event-meta` et `.event-actions` existent AUSSI dans
  `CarteEvenement.svelte` […] les unifier suppose de reprendre ces deux blocs —
  c'est le travail de #432 »*. Svelte scope le style au composant qui **rend** le
  balisage : n'extraire qu'un des deux blocs aurait emporté les règles et laissé
  l'autre nu — c'est la panne des pastilles de la v2.67.11. Il fallait donc les
  reprendre **ensemble**, et c'est ce que fait ce composant.

  ## Pourquoi des props et non des slots

  Un slot est écrit par l'appelant, donc **stylé par l'appelant** : passer le
  titre ou la description en slot aurait laissé `.event-titre` et `.event-desc`
  dans la page, c'est-à-dire exactement le problème qu'on vient de résoudre. Tout
  ce qui porte une classe locale arrive donc en **prop**.

  Seules les **actions** sont un slot, et c'est sûr : elles ne portent que des
  classes globales (`btn-icon`, `btn-icon-danger`), qu'`app.css` atteint partout.

  ## Un écart entérinné aurait suffi à rendre ce composant inutile

  Le badge de périmètre était rendu **dans le corps** sur la publication archivée
  (`badge-gray`, `.7rem`) et **dans la colonne de date** sur les deux autres
  (`badge-blue`). Trois rangées voisines du même écran, deux placements. Ajouter
  une prop pour accueillir cet écart ne l'aurait pas factorisé, ça l'aurait
  entériné : le placement de la majorité gagne — colonne de date, `badge-blue` —
  et il n'y a plus qu'une façon de lire un périmètre dans cette liste.
-->
<script lang="ts">
	import { safeHtml } from '$lib/sanitize';
	import { estPerimetreParDefaut, perimetreLabel } from '$lib/utils';

	/** Variante **archive** : disposition en grille et badge de nature. */
	export let archive = false;
	/** Couleur du liseré gauche — la nature de l'élément archivé. */
	export let bordure: string | null = null;
	/** Bord rouge : la seule marque d'urgence, jamais un badge texte. */
	export let urgent = false;

	//  ── Zone « type » ────────────────────────────────────────────────────────
	export let typeTexte = '';
	/** Badge de nature, en archives seulement : Actualité · Prestation · Événement. */
	export let badgeType: { texte: string; couleur: string } | null = null;

	//  ── Zone « corps » ───────────────────────────────────────────────────────
	export let titre = '';
	/** Métadonnées déjà formées — « 🎯 Untel », « 📍 Hall B ». */
	export let metas: string[] = [];
	/** Assainie ici : aucun appelant ne pose `{@html}` sur une rangée. */
	export let description: string | null = null;

	//  ── Zone « date » ────────────────────────────────────────────────────────
	/** Les lignes de la colonne de droite, dans l'ordre. `attenue` = gris, plus petit. */
	export let dates: { texte: string; attenue?: boolean }[] = [];
	/** 🔹 = périmètre logique, jamais 📍, et jamais affiché s'il vaut le défaut. */
	export let perimetre: string | string[] | null = null;
	/** Où en est l'objet — la colonne du Kanban, avec sa couleur. */
	export let badgeKanban: { texte: string; couleur: string } | null = null;
	/** Dernière ligne, en petit : « Mise à jour le … · Untel ». */
	export let pied: string | null = null;

	/**  La rangée porte-t-elle des actions ? C'est une PROP et non `$$slots` :
	 *   un fragment déclaré compte comme présent même quand son `{#if}` intérieur
	 *   ne rend rien, et la zone vide décalerait la rangée d'un `gap`. Le droit
	 *   d'agir se lit donc au même endroit que le bouton qu'il gouverne. */
	export let avecActions = false;

	$: perimetreVisible = !!perimetre && !estPerimetreParDefaut(perimetre);
</script>

<div
	class="event-row card"
	class:archive-row={archive}
	class:archive-attenuee={archive}
	class:event-urgent={urgent}
	style={bordure ? `border-left:3px solid ${bordure}` : ''}
>
	<div class="event-type" class:archive-type={archive}>
		{typeTexte}
		{#if badgeType}
			<span class="badge rangee-badge" style="background:{badgeType.couleur}">{badgeType.texte}</span>
		{/if}
	</div>

	<div class="event-body">
		<strong class="event-titre">{titre}</strong>
		{#each metas as meta}<span class="event-meta">{meta}</span>{/each}
		{#if description}
			<div class="event-desc rich-content clamp-5">{@html safeHtml(description)}</div>
		{/if}
	</div>

	<div class="event-date">
		{#each dates as ligne}
			<div class:date-attenuee={ligne.attenue}>{ligne.texte}</div>
		{/each}
		{#if perimetreVisible}
			<span class="badge badge-blue rangee-perimetre">&#x1F539; {perimetreLabel(perimetre ?? [])}</span>
		{/if}
		{#if badgeKanban}
			<span class="badge rangee-badge rangee-kanban" style="background:{badgeKanban.couleur}">{badgeKanban.texte}</span>
		{/if}
		{#if pied}<small class="ev-updated">{pied}</small>{/if}
	</div>

	{#if avecActions}
		<div class="event-actions"><slot name="actions" /></div>
	{/if}
</div>

<style>
	/*  Ces règles vivaient dans le `<style>` de `calendrier/+page.svelte` et
	    servaient QUATRE rangées écrites à la main. Elles partent avec le balisage
	    qui les porte — c'est la seule façon qu'elles s'appliquent : un style de
	    page n'atteint pas le balisage d'un composant enfant (v2.67.11). */
	/*  `flex-wrap` : le corps déplié portait `grid-column`, sans effet en flex. */
	.event-row { display: flex; flex-wrap: wrap; gap: 1rem; align-items: flex-start; padding: .85rem 1rem; margin-bottom: .4rem; transition: background .12s; }
	.event-type { min-width: 7rem; font-size: .8rem; font-weight: 600; padding-top: .1rem; }
	.event-body { flex: 1; }
	.event-titre { font-size: .95rem; }
	.event-meta { font-size: .8rem; color: var(--color-text-muted); margin-left: .5rem; }
	.event-desc { font-size: .85rem; color: var(--color-text-muted); margin: .2rem 0 0; }
	.event-date { text-align: right; font-size: .85rem; min-width: 110px; }
	.event-actions { display: flex; gap: .3rem; }
	.ev-updated { display: block; font-size: .75rem; color: var(--color-text-muted); margin-top: .3rem; }

	/*  L'atténuation des archives était posée en `style="opacity:.85"` sur les
	    trois rangées — une valeur recopiée trois fois, qu'une quatrième aurait
	    fait diverger. Elle est ici, avec sa variante. */
	.archive-attenuee { opacity: .85; }
	.date-attenuee { color: var(--color-text-muted); font-size: .8rem; }
	.rangee-badge { color: #fff; font-size: .65rem; white-space: nowrap; }
	.rangee-kanban { font-size: .73rem; }
	.rangee-perimetre, .rangee-kanban { margin-top: .3rem; }

	.archive-row {
		display: grid;
		grid-template-columns: 7.75rem minmax(0, 1fr) 8.5rem auto;
		column-gap: 1rem;
		align-items: start;
	}
	.archive-row .event-body { min-width: 0; }
	.archive-type {
		min-width: 0;
		width: 7.75rem;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: .35rem;
		text-align: center;
		padding: .15rem .35rem;
	}
	.archive-type .rangee-badge {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-width: 6.5rem;
	}
	@media (max-width: 760px) {
		.archive-row {
			grid-template-columns: 1fr;
			row-gap: .6rem;
		}
		.archive-type {
			width: auto;
			align-items: flex-start;
			text-align: left;
			padding: 0;
		}
		.archive-row .event-date {
			text-align: left;
			min-width: 0;
		}
		.archive-row .event-actions {
			justify-content: flex-start;
		}
	}
</style>
