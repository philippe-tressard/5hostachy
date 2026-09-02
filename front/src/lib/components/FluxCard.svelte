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

	import { isAdmin } from '$lib/stores/auth';
	import type { FluxItem } from '$lib/api';
	import { safeHtml } from '$lib/sanitize';
	import { fmtDatetimeShort } from '$lib/date';
	import FluxVignette from '$lib/components/FluxVignette.svelte';
	import PiecesJointes from '$lib/components/PiecesJointes.svelte';
	import {
		badgeClass,
		isNew,
		typeCouleur,
		typeFond,
		typeLibelle,
		typeLink,
		typeVoirLabel,
	} from '$lib/flux';

	export let item: FluxItem;
	export let expanded = false;

	/**  🗑️ Retirer la carte du FIL — admin seulement, et sur les cartes d'ANNUAIRE
	 *   seulement. La carte n'agit pas, elle prévient — comme pour `toggle`. */
	const dispatch = createEventDispatcher<{ toggle: string; masquer: string }>();

	/**  Une carte ne se retire du fil que si son objet n'a pas d'archivage : ce
	 *   qui s'archive se retire EN S'ARCHIVANT, et poser un 🗑️ à côté offrirait
	 *   un second chemin pour la même intention (#367). Seul l'annuaire n'a pas
	 *   d'archivage. Le raisonnement complet est dans l'endpoint. */
	$: retirable = item.type === 'annuaire';
	function basculer() {
		dispatch('toggle', item.id);
	}

	$: typeColor = typeCouleur(item.type);
	$: nouveau = isNew(item);
	$: lien = typeLink(item);
	/**
	 *  L'extrait à montrer sous le libellé quand la carte est PLIÉE.
	 *
	 *  `evol_contenu` d'abord — c'est ce qui vient d'être dit, donc ce qu'on
	 *  cherche en parcourant le fil. `description` en repli, pour les cartes qui
	 *  n'annoncent pas une évolution.
	 *
	 *  ⚠️ Rien n'est affiché si l'extrait répète déjà `detail` : sur une carte
	 *  d'actualité, `detail` EST l'extrait, et l'afficher deux fois serait pire
	 *  que de ne rien ajouter. C'est la donnée qui tranche, pas le type de carte
	 *  — énumérer les types est exactement ce qui a coûté l'affichage du
	 *  commentaire d'un événement (cf. `flux/evenements.py`).
	 */
	$: extraitReplie = (() => {
		const brut = (item.meta?.evol_contenu ?? item.meta?.description) as string | undefined;
		const extrait = (brut ?? '').trim();
		if (!extrait) return '';
		const libelle = (item.detail ?? '').trim();
		if (!libelle) return extrait;
		return libelle.includes(extrait) || extrait.includes(libelle) ? '' : extrait;
	})();

	$: photos = (item.meta?.photos_urls as string[] | undefined) ?? [];
	$: fichiers = (item.meta?.fichiers_urls as string[] | undefined) ?? [];

	$: perimetre = item.meta?.perimetre as string | undefined;
	//  « Copropriété entière » n'apprend rien : c'est le cas par défaut.
	//
	//  ⚠️ COMPARAISON DE LIBELLÉ EN DUR, et c'est une fragilité connue : `meta.perimetre`
	//  arrive du serveur déjà mis en forme, si bien qu'`estPerimetreParDefaut()` — qui
	//  travaille sur des CODES — ne s'applique pas ici. Renommer le nœud racine depuis
	//  l'administration ferait donc réapparaître « 🔹 Toute la copropriété » sur chaque
	//  ligne du fil. C'est la même famille de défaut que les tables de périmètres
	//  recopiées (#316) ; le remède est côté API — ne pas envoyer le périmètre quand il
	//  vaut le défaut —, pas ici.
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
				<span class="flux-type-chip" style="background:{typeFond(item.type)};color:{typeColor}"
					>{typeLibelle(item.type)}</span
				>
				{#if nouveau}<span class="new-badge">NEW</span>{/if}
			</div>
			<div class="flux-card-top-right">
				<span class="flux-heure">{fmtDatetimeShort(item.date)}</span>
				{#if $isAdmin && retirable}
					<!--  `stopPropagation` : la carte entière bascule au clic. Sans lui,
					      retirer une carte la déplierait au passage. -->
					<button
						class="btn-icon-danger"
						title="Retirer du fil (l'élément reste à son origine)"
						aria-label="Retirer cette carte du fil"
						on:click|stopPropagation={() => dispatch('masquer', item.id)}
						on:keydown|stopPropagation>🗑️</button
					>
				{/if}
				<span class="chevron" class:open={expanded}>›</span>
			</div>
		</div>
		<div class="flux-card-body">
			<span class="flux-icon">{item.icon}</span>
			<div class="flux-card-text">
				<span class="flux-titre">{item.titre}</span>
				{#if !expanded && (item.detail || extraitReplie)}
					<!--  🔴 Le LIBELLÉ et l'EXTRAIT, pas seulement le libellé (#531).
					      Signalé à l'écran, capture à l'appui : une carte « ticket mis à
					      jour » n'affichait que « Mise à jour » ou « Pris en charge » —
					      deux mots qui disent qu'il s'est passé quelque chose sans dire
					      quoi. À côté, une carte d'actualité remplissait deux lignes.

					      L'asymétrie ne venait pas des données : `evol_contenu` (300
					      caractères) était déjà transporté et déjà rendu par la carte
					      DÉPLIÉE. Seule la carte pliée l'ignorait. -->
					<p class="flux-detail clamp-3">
						{#if item.detail}<span class="flux-detail-libelle">{item.detail}</span
							>{/if}{#if item.detail && extraitReplie}&#8201;—&#8201;{/if}{extraitReplie}
					</p>
				{/if}
			</div>
			<!-- Plié : aperçu. Déplié : la galerie plus bas prend le relais,
			     inutile de montrer deux fois la même image. -->
			{#if !expanded}
				<FluxVignette
					{photos}
					{fichiers}
					nbPieces={(item.meta?.pj_compte as number | undefined) ?? 0}
				/>
			{/if}
		</div>
		{#if item.badges.length > 0 || perimetreAffiche || aVenir}
			<div class="flux-badges">
				<!-- La ligne est datée de l'annonce : sans ce repère, un événement
				     à venir se lirait comme s'il avait déjà eu lieu. -->
				{#if aVenir}
					<span class="badge badge-orange" style="font-size:.7rem"
						>🗓️ prévu le {fmtDatetimeShort(String(debut))}</span
					>
				{/if}
				<!--  🔴 `badge-gray`, comme sur les CARTES (18/08/2026). Le fil le rendait
				      en `badge-blue` : le même périmètre changeait donc de couleur selon
				      qu'on le lisait dans le fil ou dans la liste d'où il vient. Un objet
				      se rend toujours pareil (R3) — et le bleu, ici, servait à le
				      distinguer des badges d'état voisins, ce que le 🔹 fait déjà.
				      Le `font-size` en ligne part avec : il est dans `.flux-badges`. -->
				{#if perimetreAffiche}
					<span class="badge badge-gray">🔹 {perimetreAffiche}</span>
				{/if}
				{#each item.badges as b (b)}
					<span class="badge {badgeClass(item.type, b)}">{b}</span>
				{/each}
			</div>
		{/if}
		{#if expanded}
			<!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
			<div class="flux-body" on:click|stopPropagation>
				{#if item.meta?.lieu}<p class="flux-meta-line">📍 {item.meta.lieu}</p>{/if}
				<!--  ⚠️ Le périmètre n'est PAS répété ici : il est déjà en badge dans
				      l'en-tête de la carte, visible replié comme déplié. Il s'affichait
				      deux fois sur toute carte dépliée — le même défaut que celui corrigé
				      sur les tickets le même jour, dans l'autre sens. -->
				{#if item.meta?.prestataire}<p class="flux-meta-line">🔧 {item.meta.prestataire}</p>{/if}
				<!-- `fin` est facultatif : l'exiger masquait la date de tenue de
				     tout événement sans heure de fin — désormais l'information
				     essentielle, puisque la ligne du fil est datée de l'annonce. -->
				{#if debut}
					<p class="flux-meta-line">
						🕐 {fmtDatetimeShort(String(debut))}{#if item.meta?.fin}
							→ {fmtDatetimeShort(String(item.meta.fin))}{/if}
					</p>
				{/if}
				{#if item.meta?.auteur}<p class="flux-meta-line">✍️ {item.meta.auteur}</p>{/if}
				{#if item.meta?.statut}
					<p class="flux-meta-line">
						État :
						<span
							class="badge {item.meta.statut === 'résolu' || item.meta.statut === 'réalisé'
								? 'badge-green'
								: item.meta.statut === 'en_cours' || item.meta.statut === 'ouvert'
									? 'badge-orange'
									: 'badge-gray'}">{item.meta.statut}</span
						>
					</p>
				{/if}
				<!--  🔴 LA DERNIÈRE MISE À JOUR D'ABORD, le texte d'origine ensuite
				      (#531, demandé à l'écran le 20/08/2026 sur la carte dépliée).

				      Une carte du fil répond à « quoi de neuf ». Ce qui est neuf, c'est
				      le commentaire du jour ; la description d'origine est le CONTEXTE
				      qui permet de le comprendre. L'ordre inverse obligeait à lire un
				      texte parfois vieux de plusieurs semaines avant d'atteindre la
				      seule ligne qu'on venait chercher.

				      ⚠️ La condition ne teste PAS le type : `evol_contenu` n'est posé
				      que par une carte de mise à jour, et le vérifier deux fois ferait
				      de cette liste de types une seconde déclaration à tenir. Elle a
				      immédiatement divergé la première fois : le calendrier a eu son
				      Historique le 18/08/2026, le fil a su le fournir, et RIEN ne
				      s'affichait. La donnée décide, pas une énumération de types. -->
				{#if item.meta?.evol_contenu}
					<div class="flux-reaction">
						<span class="flux-reaction-icon">💬</span>
						<div class="flux-reaction-body">
							{#if item.meta?.evol_auteur}<span class="flux-reaction-auteur"
									>{item.meta.evol_auteur}</span
								>{/if}
							<p class="flux-reaction-text">{item.meta.evol_contenu}</p>
						</div>
					</div>
				{/if}
				<!--  Le texte d'origine, en dessous : il rappelle DE QUOI il s'agit. -->
				{#if item.meta?.full_html}
					<div class="flux-full-content rich-content">
						{@html safeHtml(String(item.meta.full_html))}
					</div>
				{:else if item.meta?.description}
					<p class="flux-full-content">{item.meta.description}</p>
				{:else if item.detail}
					<p class="flux-full-content">{item.detail}</p>
				{/if}
				{#if photos.length || fichiers.length}
					<!-- Les pièces jointes de devis sont des PDF : elles étaient
					     rendues en <img>, donc en image cassée. Le composant
					     distingue image et document, une fois pour toutes. -->
					<!-- Format « grand » : la carte est dépliée, l'utilisateur a
					     demandé à voir. Une vignette de 72 px lui imposerait un
					     clic de plus pour ce qu'il vient d'ouvrir. -->
					<div class="flux-photos">
						<PiecesJointes urls={[...photos, ...fichiers]} format="grand" />
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
		display: flex;
		align-items: flex-start;
		gap: 0.75rem;
		color: inherit;
		position: relative;
		margin-bottom: 0.5rem;
	}
	.flux-card {
		flex: 1;
		padding: 0.7rem 0.9rem;
		transition:
			box-shadow 0.15s,
			border-left-color 0.15s,
			background 0.12s;
		border-left: 4px solid var(--color-border);
		cursor: pointer;
	}
	.flux-card:focus-visible {
		outline: 2px solid var(--color-primary);
		outline-offset: 2px;
	}
	/*  Le fond change au survol, comme sur toutes les listes dépliables du site
	    (#362). La carte ne renforçait que son OMBRE — trop discret pour annoncer
	    « ceci s'ouvre », et l'utilisateur l'a signalé deux fois : une carte du fil
	    restait blanche là où une actualité se teintait. La même valeur que
	    `.pub-row:hover` et `.tk-row:hover`, pas une nuance de plus. */
	/*  🔴 Le survol colore le TITRE, pas le bloc — la règle du site depuis le
	    18/08/2026, et le fil est le dernier à l'avoir reçue alors qu'il en est
	    la référence : « quand tout l'article change de couleur c'est moche ».

	    Un aplat sur toute la carte fait bouger la page à chaque passage de souris
	    dans une liste longue. Le titre qui change de teinte dit la même chose —
	    « ceci répond » — sans repeindre l'écran.

	    ⚠️ Le titre change **où que soit la souris sur le bloc** : c'est bien le
	    survol de `.flux-item` qui déclenche, pas celui du titre. Toute la carte
	    reste la cible du clic.

	    ⚠️ Pas de soulignement : le titre n'est pas un lien, c'est une zone
	    cliquable — le souligner le ferait passer pour une navigation. */
	.flux-item:hover .flux-card {
		box-shadow: var(--shadow);
	}
	.flux-item:hover .flux-titre {
		color: var(--color-primary);
	}
	.flux-titre {
		transition: color 0.12s ease;
	}
	.flux-item.flux-urgent .flux-card {
		border-left-color: var(--color-danger) !important;
	}
	.flux-item.flux-expanded .flux-card {
		box-shadow: var(--shadow);
	}

	.flux-card-top {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 0.35rem;
	}
	.flux-card-top-left {
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}
	.flux-card-top-right {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.flux-heure {
		font-size: 0.72rem;
		color: var(--color-text-muted);
		white-space: nowrap;
	}
	.flux-card-body {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
	}
	.flux-icon {
		font-size: 1.05rem;
		flex-shrink: 0;
		line-height: 1;
		margin-top: 0.1rem;
	}
	.flux-card-text {
		flex: 1;
		min-width: 0;
	}
	.flux-titre {
		font-size: 0.88rem;
		font-weight: 500;
		line-height: 1.35;
		display: block;
	}
	.flux-detail {
		font-size: 0.8rem;
		color: var(--color-text-muted);
		margin: 0.15rem 0 0;
		line-height: 1.4;
	}
	/*  Le libellé garde le poids qu'il avait quand il était seul : c'est lui qui
	    dit la NATURE de la mise à jour, l'extrait n'en donne que la teneur. */
	.flux-detail-libelle {
		font-weight: 600;
	}
	.clamp-3 {
		display: -webkit-box;
		-webkit-line-clamp: 3;
		line-clamp: 3;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}
	.flux-badges {
		display: flex;
		gap: 0.3rem;
		flex-wrap: wrap;
		margin-top: 0.35rem;
	}

	/* ═══ NEW BADGE ═════════════════════════════════════════════════════ */
	@keyframes new-pulse {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0.7;
		}
	}
	.new-badge {
		font-size: 0.55rem;
		font-weight: 700;
		letter-spacing: 0.06em;
		background: #ef4444;
		color: #fff;
		padding: 0.1rem 0.35rem;
		border-radius: 0.2rem;
		animation: new-pulse 2s ease-in-out infinite;
		flex-shrink: 0;
		text-transform: uppercase;
	}

	/* ═══ CHEVRON ═══════════════════════════════════════════════════════ */
	/*  Écart assumé : chevron en gras, non sélectionnable, dans un flex. */
	.chevron {
		font-weight: 700;
		flex-shrink: 0;
		user-select: none;
	}

	/* ═══ CORPS DÉPLIÉ ══════════════════════════════════════════════════ */
	.flux-body {
		border-top: 1px solid var(--color-border);
		padding: 0.75rem 0.5rem 0.75rem 1.7rem;
		margin-top: 0.5rem;
	}
	.flux-meta-line {
		font-size: 0.82rem;
		color: var(--color-text-muted);
		margin: 0.15rem 0;
	}
	.flux-full-content {
		font-size: 0.85rem;
		line-height: 1.55;
		margin: 0.5rem 0;
	}
	.flux-link {
		font-size: 0.78rem;
		color: var(--color-primary);
		font-weight: 500;
		text-decoration: none;
		display: inline-block;
		margin-top: 0.5rem;
	}
	.flux-link:hover {
		text-decoration: underline;
	}

	/* Galerie dépliée — les styles étaient écrits en `style=` sur chaque balise,
	   donc quatre fois pour deux blocs.
	   La règle `.flux-photos img` qui bornait les images à 120×90 en `cover` a été
	   retirée : le format des photos appartient désormais à `PiecesJointes`, qui
	   les rend en grand une fois la carte dépliée. Deux endroits pour décider de
	   la même taille, c'est un endroit de trop — et celui-ci était devenu mort. */
	.flux-photos {
		margin: 0.5rem 0;
	}

	/* ═══ RÉACTION INLINE (ticket_mis_a_jour) ═══════════════════════════ */
	.flux-reaction {
		display: flex;
		gap: 0.5rem;
		align-items: flex-start;
		margin: 0.6rem 0 0.3rem;
		padding: 0.5rem 0.75rem;
		border-radius: 6px;
		background: #eef2f7;
		border-left: 3px solid var(--color-primary);
		font-size: 0.82rem;
	}
	.flux-reaction-icon {
		flex-shrink: 0;
		font-size: 0.85rem;
		margin-top: 0.1rem;
	}
	.flux-reaction-body {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		min-width: 0;
	}
	.flux-reaction-auteur {
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--color-primary);
	}
	.flux-reaction-text {
		margin: 0;
		color: var(--color-text);
		line-height: 1.45;
	}

	@media (max-width: 767px) {
		.flux-dot {
			left: -1.1rem;
			width: 8px;
			height: 8px;
		}
		.flux-new-dot {
			left: -1.4rem;
			width: 14px;
			height: 14px;
		}
	}
</style>
