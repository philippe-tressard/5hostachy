<!--
  Une carte du fil d'activité du tableau de bord.

  Ce composant existe parce que le fil rendait la MÊME carte à deux endroits —
  le bloc « récent » et l'accordéon « plus ancien » — dans deux blocs de balisage
  copiés puis modifiés séparément. Les deux avaient divergé : le bloc ancien
  avait perdu la date de tenue, l'auteur, l'état, la réaction du CS, les badges
  et le libellé de lien adapté au type. Toute évolution du fil devait par ailleurs
  être écrite deux fois (la vignette d'aperçu l'a été, le 01/08/2026).

  La fusion retient, pour chaque partie, la version la plus complète des deux —
  pas la première rencontrée. Le bloc « ancien » conserve sa seule distinction
  volontaire, l'atténuation (`.older-timeline { opacity }`), qui est du ressort
  du conteneur.

  Sert les trois registres du fil : urgences (via le bandeau dédié de la page),
  épinglé et chronologie. Une carte se rend de la même façon partout.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import type { FluxItem } from '$lib/api';
	import { safeHtml } from '$lib/sanitize';
	import { fmtDatetimeShort } from '$lib/date';
	import FluxVignette from '$lib/components/FluxVignette.svelte';
	import PiecesJointes from '$lib/components/PiecesJointes.svelte';
	import {
		badgeClass, isNew, typeCouleur, typeFond, typeLibelle, typeLink, typeVoirLabel,
	} from '$lib/flux';

	export let item: FluxItem;
	export let expanded = false;

	const dispatch = createEventDispatcher<{ toggle: string }>();
	function basculer() { dispatch('toggle', item.id); }

	$: typeColor = typeCouleur(item.type);
	$: nouveau = isNew(item);
	$: lien = typeLink(item);
	$: photos = (item.meta?.photos_urls as string[] | undefined) ?? [];
	$: fichiers = (item.meta?.fichiers_urls as string[] | undefined) ?? [];
	$: image = (item.meta?.image_url as string | undefined) ?? null;
	$: perimetre = item.meta?.perimetre as string | undefined;
	// « Copropriété entière » n'apprend rien : c'est le cas par défaut.
	$: perimetreAffiche = perimetre && perimetre !== 'Copropriété entière' ? perimetre : null;
	$: debut = item.meta?.debut as string | undefined;
	$: aVenir = item.type === 'evenement' && debut ? new Date(debut) > new Date() : false;
</script>

<div
	class="flux-item"
	class:flux-urgent={item.type === 'ticket_ouvert' && item.badges?.includes('urgence')}
	class:flux-expanded={expanded}
>
	<div class="flux-dot" style="background:{typeColor}"></div>
	{#if nouveau}<div class="flux-new-dot"></div>{/if}
	<div
		class="flux-card card"
		style="border-left-color:{typeColor}"
		role="button"
		tabindex="0"
		on:click={basculer}
		on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && basculer()}
	>
		<div class="flux-card-top">
			<div class="flux-card-top-left">
				<span class="flux-type-chip" style="background:{typeFond(item.type)};color:{typeColor}">{typeLibelle(item.type)}</span>
				{#if nouveau}<span class="new-badge">NEW</span>{/if}
			</div>
			<div class="flux-card-top-right">
				<span class="flux-heure">{fmtDatetimeShort(item.date)}</span>
				<span class="chevron" class:open={expanded}>›</span>
			</div>
		</div>
		<div class="flux-card-body">
			<span class="flux-icon">{item.icon}</span>
			<div class="flux-card-text">
				<span class="flux-titre">{item.titre}</span>
				{#if !expanded && item.detail}
					<p class="flux-detail clamp-3">{item.detail}</p>
				{/if}
			</div>
			<!-- Plié : aperçu. Déplié : la galerie plus bas prend le relais,
			     inutile de montrer deux fois la même image. -->
			{#if !expanded}
				<FluxVignette {photos} {image} />
			{/if}
		</div>
		{#if item.badges.length > 0 || perimetreAffiche || aVenir}
			<div class="flux-badges">
				<!-- La ligne est datée de l'annonce : sans ce repère, un événement
				     à venir se lirait comme s'il avait déjà eu lieu. -->
				{#if aVenir}
					<span class="badge badge-orange" style="font-size:.7rem">🗓️ prévu le {fmtDatetimeShort(String(debut))}</span>
				{/if}
				{#if perimetreAffiche}
					<span class="badge badge-blue" style="font-size:.7rem">🔹 {perimetreAffiche}</span>
				{/if}
				{#each item.badges as b}
					<span class="badge {badgeClass(item.type, b)}">{b}</span>
				{/each}
			</div>
		{/if}
		{#if expanded}
			<!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
			<div class="flux-body" on:click|stopPropagation>
				{#if item.meta?.lieu}<p class="flux-meta-line">📍 {item.meta.lieu}</p>{/if}
				{#if perimetreAffiche}<p class="flux-meta-line">🔹 {perimetreAffiche}</p>{/if}
				{#if item.meta?.prestataire}<p class="flux-meta-line">🔧 {item.meta.prestataire}</p>{/if}
				<!-- `fin` est facultatif : l'exiger masquait la date de tenue de
				     tout événement sans heure de fin — désormais l'information
				     essentielle, puisque la ligne du fil est datée de l'annonce. -->
				{#if debut}
					<p class="flux-meta-line">🕐 {fmtDatetimeShort(String(debut))}{#if item.meta?.fin} → {fmtDatetimeShort(String(item.meta.fin))}{/if}</p>
				{/if}
				{#if item.meta?.auteur}<p class="flux-meta-line">✍️ {item.meta.auteur}</p>{/if}
				{#if item.meta?.statut}
					<p class="flux-meta-line">
						État :
						<span class="badge {item.meta.statut === 'résolu' || item.meta.statut === 'réalisé' ? 'badge-green' : item.meta.statut === 'en_cours' || item.meta.statut === 'ouvert' ? 'badge-orange' : 'badge-gray'}">{item.meta.statut}</span>
					</p>
				{/if}
				{#if item.meta?.full_html}
					<div class="flux-full-content rich-content">{@html safeHtml(String(item.meta.full_html))}</div>
				{:else if item.meta?.description}
					<p class="flux-full-content">{item.meta.description}</p>
				{:else if item.detail}
					<p class="flux-full-content">{item.detail}</p>
				{/if}
				{#if item.type === 'ticket_mis_a_jour' && item.meta?.evol_contenu}
					<div class="flux-reaction">
						<span class="flux-reaction-icon">💬</span>
						<div class="flux-reaction-body">
							{#if item.meta?.evol_auteur}<span class="flux-reaction-auteur">{item.meta.evol_auteur}</span>{/if}
							<p class="flux-reaction-text">{item.meta.evol_contenu}</p>
						</div>
					</div>
				{/if}
				{#if image}
					<img src={image} alt="" class="flux-image" loading="lazy" />
				{/if}
				{#if photos.length || fichiers.length}
					<!-- Les pièces jointes de devis sont des PDF : elles étaient
					     rendues en <img>, donc en image cassée. Le composant
					     distingue image et document, une fois pour toutes. -->
					<div class="flux-photos">
						<PiecesJointes urls={[...photos, ...fichiers]} size={72} />
					</div>
				{/if}
				{#if lien}
					<a href={lien} class="flux-link">{typeVoirLabel(item)}</a>
				{/if}
			</div>
		{/if}
	</div>
</div>

<style>
	.flux-item {
		display: flex; align-items: flex-start; gap: .75rem;
		color: inherit; position: relative; margin-bottom: .5rem;
	}
	.flux-dot {
		width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; margin-top: .85rem;
		position: absolute; left: -1.35rem;
		border: 2px solid var(--color-surface); box-shadow: 0 0 0 2px var(--color-border); z-index: 1;
	}
	.flux-new-dot {
		position: absolute; left: -1.7rem; top: .55rem;
		width: 18px; height: 18px; border-radius: 50%;
		background: rgba(239, 68, 68, .15);
		animation: new-dot-pulse 2s ease-in-out infinite; z-index: 0;
	}
	@keyframes new-dot-pulse {
		0%, 100% { transform: scale(1); opacity: .6; }
		50% { transform: scale(1.6); opacity: 0; }
	}
	.flux-card {
		flex: 1; padding: .7rem .9rem;
		transition: box-shadow .15s, border-left-color .15s;
		border-left: 4px solid var(--color-border);
		cursor: pointer;
	}
	.flux-card:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px; }
	.flux-item:hover .flux-card { box-shadow: var(--shadow); }
	.flux-item.flux-urgent .flux-card { border-left-color: var(--color-danger) !important; }
	.flux-item.flux-expanded .flux-card { box-shadow: var(--shadow); }

	.flux-card-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: .35rem; }
	.flux-card-top-left { display: flex; align-items: center; gap: .4rem; }
	.flux-card-top-right { display: flex; align-items: center; gap: .5rem; }
	.flux-heure { font-size: .72rem; color: var(--color-text-muted); white-space: nowrap; }
	.flux-card-body { display: flex; align-items: flex-start; gap: .5rem; }
	.flux-icon { font-size: 1.05rem; flex-shrink: 0; line-height: 1; margin-top: .1rem; }
	.flux-card-text { flex: 1; min-width: 0; }
	.flux-titre { font-size: .88rem; font-weight: 500; line-height: 1.35; display: block; }
	.flux-detail { font-size: .8rem; color: var(--color-text-muted); margin: .15rem 0 0; line-height: 1.4; }
	.clamp-3 { display: -webkit-box; -webkit-line-clamp: 3; line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
	.flux-badges { display: flex; gap: .3rem; flex-wrap: wrap; margin-top: .35rem; }

	/* ═══ NEW BADGE ═════════════════════════════════════════════════════ */
	@keyframes new-pulse {
		0%, 100% { opacity: 1; }
		50% { opacity: .7; }
	}
	.new-badge {
		font-size: .55rem; font-weight: 700; letter-spacing: .06em;
		background: #EF4444; color: #fff;
		padding: .1rem .35rem; border-radius: .2rem;
		animation: new-pulse 2s ease-in-out infinite;
		flex-shrink: 0; text-transform: uppercase;
	}

	/* ═══ CHEVRON ═══════════════════════════════════════════════════════ */
	.chevron {
		font-size: 1.1rem; font-weight: 700; color: var(--color-text-muted);
		transition: transform .2s ease; display: inline-block; flex-shrink: 0;
		line-height: 1; user-select: none;
	}
	.chevron.open { transform: rotate(90deg); }

	/* ═══ CORPS DÉPLIÉ ══════════════════════════════════════════════════ */
	.flux-body {
		border-top: 1px solid var(--color-border);
		padding: .75rem .5rem .75rem 1.7rem;
		margin-top: .5rem;
	}
	.flux-meta-line { font-size: .82rem; color: var(--color-text-muted); margin: .15rem 0; }
	.flux-full-content { font-size: .85rem; line-height: 1.55; margin: .5rem 0; }
	.flux-image { max-width: 100%; max-height: 200px; border-radius: var(--radius); margin-top: .5rem; object-fit: cover; }
	.flux-link { font-size: .78rem; color: var(--color-primary); font-weight: 500; text-decoration: none; display: inline-block; margin-top: .5rem; }
	.flux-link:hover { text-decoration: underline; }

	/* Galerie dépliée — les styles étaient écrits en `style=` sur chaque balise,
	   donc quatre fois pour deux blocs. */
	.flux-photos { margin: .5rem 0; display: flex; gap: .5rem; flex-wrap: wrap; }
	.flux-photos img {
		max-width: 120px; max-height: 90px;
		border-radius: 6px; object-fit: cover;
		border: 1px solid var(--color-border);
	}

	/* ═══ RÉACTION INLINE (ticket_mis_a_jour) ═══════════════════════════ */
	.flux-reaction {
		display: flex; gap: .5rem; align-items: flex-start;
		margin: .6rem 0 .3rem;
		padding: .5rem .75rem; border-radius: 6px;
		background: #EEF2F7; border-left: 3px solid var(--color-primary);
		font-size: .82rem;
	}
	.flux-reaction-icon { flex-shrink: 0; font-size: .85rem; margin-top: .1rem; }
	.flux-reaction-body { display: flex; flex-direction: column; gap: .15rem; min-width: 0; }
	.flux-reaction-auteur { font-size: .75rem; font-weight: 600; color: var(--color-primary); }
	.flux-reaction-text { margin: 0; color: var(--color-text); line-height: 1.45; }

	@media (max-width: 767px) {
		.flux-dot { left: -1.1rem; width: 8px; height: 8px; }
		.flux-new-dot { left: -1.4rem; width: 14px; height: 14px; }
	}
</style>
