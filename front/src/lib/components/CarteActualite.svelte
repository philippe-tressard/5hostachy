<!--
  Une publication dans une liste : le conteneur dépliable, sa ligne d'en-tête,
  son aperçu replié et son corps déplié.

  Pourquoi ce composant (#356) : la page Actualités rendait la MÊME carte à deux
  endroits — le fil principal et l'Historique. Le lot #351 a dû y appliquer
  quatre modifications au lieu de deux (ordre photos/texte, puis vignette, deux
  fois chacune), et c'est le genre d'écart qui finit par diverger le jour où l'on
  ne pense qu'à l'un des deux.

  ⚠️ Le balisage part AVEC ses règles CSS (`.pub-row*`, `.pub-body`,
  `.pin-badge`…). Svelte scope les styles au composant : les laisser derrière
  reproduirait la régression du 14/08/2026 (#344), où le balisage était parti
  dans un composant et les règles étaient restées dans la page.

  Ce que la page garde chez elle : ses formulaires et son fil d'évolutions,
  passés en slots — ils sont écrits dans la page, donc leurs styles y restent.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import ApercuCarte from '$lib/components/ApercuCarte.svelte';
	import EnteteCarte from '$lib/components/EnteteCarte.svelte';
	import PiecesJointes from '$lib/components/PiecesJointes.svelte';
	import { documents as docsApi, type Publication } from '$lib/api';
	import { safeHtml } from '$lib/sanitize';
	import { perimetreLabel, estPerimetreParDefaut } from '$lib/utils';
	import { STATUT_LABELS, STATUT_BADGE } from '$lib/publications';
	import { fmtDate2d as fmtDate, fmtDateLong, isNouveau } from '$lib/date';

	export let pub: Publication;
	export let expanded = false;
	/**  `fil` : la liste principale. `historique` : les archives — atténuées, et
	 *   sans épingle ni « New », qui n'ont plus de sens sur une publication rangée. */
	export let variante: 'fil' | 'historique' = 'fil';
	/** Aperçu replié — la page le masque quand la liste devient longue. */
	export let apercu = true;
	/** Documents joints, chargés par la page au premier dépliage. */
	export let documents: any[] = [];
	/**  Vrai quand la page affiche un formulaire à la place du contenu (édition,
	 *   ajout d'évolution). Explicite, et non déduit de `$$slots` : un slot
	 *   fourni mais vide masquerait le corps en permanence. */
	export let formulaireOuvert = false;

	const dispatch = createEventDispatcher<{ toggle: void }>();
	const basculer = () => dispatch('toggle');

	$: estFil = variante === 'fil';

	//  L'ancre `#pub-<id>` est la MÊME dans les deux variantes, et c'est sans
	//  risque de collision : le fil ne liste que les publications actives,
	//  l'historique que les archivées — les deux ensembles sont disjoints. Elle
	//  était préfixée `hist-pub-` dans l'historique, ce que rien ne ciblait.
	//
	//  Elle doit rester écrite en toutes lettres (`id="pub-…"`) : le garde-fou
	//  `api/tests/test_liens_front.py` cherche cette chaîne pour vérifier qu'un
	//  lien `/actualites#pub-42` tombe bien sur un élément existant. Un préfixe
	//  calculé la rendrait invisible à l'analyse, et le contrôle échouerait sans
	//  qu'aucun lien ne soit cassé.
</script>

<div class="carte-liste pub-expand" class:expanded class:urgent={pub.urgente}
	class:brouillon={pub.brouillon} class:epingle={pub.epingle} class:attenue={!estFil}
	id="pub-{pub.id}">

	{#if estFil && pub.epingle}<span class="pin-badge">&#x1F4CC;</span>{/if}

	<!--  Titre sur sa propre ligne, puis tags à gauche / date + actions à droite :
	      la norme de toutes les cartes du site depuis le 18/08/2026. Elle vit dans
	      `EnteteCarte`, pas ici — chaque carte qui recomposait son en-tête avait sa
	      propre façon de mal se replier, et sur téléphone le titre disparaissait. -->
	<!--  Le geste de dépliage vit dans `EnteteCarte` : le TITRE plie, avec un
	      survol qui le dit (18/08/2026). Le conteneur ne porte plus
	      `role="button"` — il interceptait la sélection de texte, et obligeait
	      chaque bouton d'action à un `stopPropagation` pour qu'un clic sur ✏️ ne
	      déplie pas la carte au même instant. -->
	<EnteteCarte titre={pub.titre} date={fmtDate(pub.mis_a_jour_le ?? pub.cree_le)}
		basculable on:toggle={basculer}>
		<svelte:fragment slot="titre-suffixe">
			{#if estFil && isNouveau(pub.cree_le, pub.mis_a_jour_le)}<span class="badge badge-gray pub-neuf">New</span>{/if}
		</svelte:fragment>
		<svelte:fragment slot="tags">
			{#if pub.brouillon}<span class="badge badge-gray">✏️ Brouillon</span>{/if}
			{#if pub.statut && pub.statut !== 'publie'}<span class="badge {STATUT_BADGE[pub.statut] ?? 'badge-gray'}">{STATUT_LABELS[pub.statut] ?? pub.statut}</span>{/if}
			{#if !estPerimetreParDefaut(pub.perimetre_cible)}<span class="badge badge-gray">&#x1F539; {perimetreLabel(pub.perimetre_cible)}</span>{/if}
			{#if pub.confidentiel}<span class="badge badge-gray" title="Visible du seul périmètre sélectionné">&#x1F512; Confidentiel</span>{/if}
			{#if pub.auteur_nom}<span class="pub-auteur">{pub.auteur_nom}</span>{/if}
		</svelte:fragment>
		<svelte:fragment slot="actions"><slot name="actions" /></svelte:fragment>
		<svelte:fragment slot="chevron"><span class="chevron" class:open={expanded}>›</span></svelte:fragment>
	</EnteteCarte>

	{#if !expanded && apercu}
		<ApercuCarte contenu={pub.contenu} photos={pub.photos_urls ?? []} />
	{/if}

	{#if expanded}
		<!--  Le corps ne referme pas la carte : on referme par l'en-tête. Sans cela,
		      impossible de sélectionner du texte, et un clic sur une photo ou un
		      formulaire referme ce qu'on lisait (ux-patterns §3). -->
		<div class="pub-body" role="presentation" on:click|stopPropagation on:keydown|stopPropagation>
			{#if formulaireOuvert}
				<slot name="formulaire" />
			{:else}
				<!--  Texte AVANT les photos : une image en tête poussait le premier mot sous la ligne de flottaison. -->
				<div class="rich-content" style="font-size:.875rem;line-height:1.6;margin-bottom:.5rem">{@html safeHtml(pub.contenu)}</div>
				{#if pub.photos_urls?.length}
					<PiecesJointes urls={pub.photos_urls} format="grand" />
				{/if}
				{#if documents.length > 0}
					<div class="pub-attachments">
						{#each documents as doc}
							<a href={docsApi.downloadUrl(doc.id)} target="_blank" class="pub-attachment-link">
								📎 {doc.titre || doc.fichier_nom}
							</a>
						{/each}
					</div>
				{/if}
				<small style="color:var(--color-text-muted);font-size:.78rem">
				{#if pub.mis_a_jour_le}Mise à jour le {fmtDateLong(pub.mis_a_jour_le)}{:else}Publié le {fmtDateLong(pub.cree_le)}{/if}{#if pub.auteur_nom} · {pub.auteur_nom}{/if}
				</small>
				<slot name="apres-corps" />
			{/if}
		</div>
	{/if}
</div>

<style>
	/*  Conteneur, survol, urgence et espacement : `.carte-liste` (app.css). Ne
	    reste ici que ce qui est propre à la publication. */
	.pin-badge { position: absolute; top: -9px; left: 8px; display: inline-flex; align-items: center; background: var(--color-primary); color: #fff; font-size: .65rem; padding: .1rem .35rem; border-radius: 8px; line-height: 1.6; z-index: 1; pointer-events: none; }

	/*  L'en-tête vit dans `EnteteCarte` — titre, tags, date, actions et leur repli.
	    Ne reste ici que ce qui est propre à une publication. */
	.pub-neuf { margin-left: .4em; font-size: .82em; font-weight: 500; vertical-align: middle; }
	.pub-auteur { font-size: .78rem; color: var(--color-text-muted); }

	.pub-body { padding: .75rem 1rem 1rem; border-top: 1px solid var(--color-border); }
	.pub-attachments { display: flex; flex-wrap: wrap; gap: .4rem; margin: .5rem 0 .25rem; }
	.pub-attachment-link { display: inline-flex; align-items: center; gap: .3rem; font-size: .82rem; padding: .25rem .55rem; background: var(--color-bg); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-primary); text-decoration: none; }
	.pub-attachment-link:hover { background: var(--color-border); }

	/*  Archives : la carte s'efface tant qu'on ne la vise pas. */
	.attenue { opacity: .8; transition: opacity .15s; margin-bottom: .3rem; }
	.attenue:hover, .attenue.expanded { opacity: 1; }
</style>
