<!--
  Une petite annonce : bandeau replié, détails dépliés, réponses.

  Extrait de `routes/(app)/sondages/+page.svelte` le 14/08/2026. Cette page porte
  TROIS rubriques (sondages, boîte à idées, petites annonces) et dépassait les
  1 000 lignes — deux fois le plafond de modularité (rang 1 §4). La règle est « au
  fil de l'eau » : on découpe le fichier quand on y touche, et c'est le contrôle de
  CI qui a refusé qu'il grossisse encore, à l'occasion du correctif #338.

  Le composant ne connaît ni l'API ni les magasins : tout ce qui écrit passe par un
  callback, comme `Reponses.svelte` juste en dessous. C'est ce qui permet à la page
  de garder la main sur la liste (elle réassigne `annonces` après chaque écriture,
  ce qui rafraîchit la galerie sans rechargement).

  Le vocabulaire — types, catégories, statuts et leurs rendus — vit dans
  `$lib/annonces.ts` : la carte le rend, la page en fait ses filtres et son
  formulaire de dépôt. Le garder ici aurait obligé la page à le recopier.
-->
<script lang="ts">
	import FichiersUpload from './FichiersUpload.svelte';
	import PiecesJointes from './PiecesJointes.svelte';
	import Reponses from './Reponses.svelte';
	import Vignette from './Vignette.svelte';
	import { safeHtml } from '$lib/sanitize';
	import { fmtDateShort, isNouveau } from '$lib/date';
	import { fmtMontant, perimetreLabel, estPerimetreParDefaut } from '$lib/utils';
	import {
		MAX_PHOTOS_ANNONCE,
		STATUTS_ANNONCE,
		categorieAnnonceLabel,
		statutAnnonceClass,
		typeAnnonceClass,
		typeAnnonceLabel,
	} from '$lib/annonces';

	export let annonce: any;
	/** L'annonce est-elle dépliée ? */
	export let expanded = false;
	/** L'auteur a-t-il ouvert la zone de gestion des photos ? */
	export let gestionOuverte = false;
	export let estCS = false;
	export let estAdmin = false;
	export let currentUserId: number | undefined = undefined;

	export let onToggle: () => void;
	export let onToggleGestion: () => void;
	export let onUpload: (f: File) => Promise<string>;
	export let onRemove: (url: string) => Promise<string[] | void>;
	export let onStatut: (statut: string) => void;
	export let onModifier: () => void;
	export let onSupprimer: () => void;
	export let onRepondre: (contenu: string) => void;
	export let onSupprimerReponse: (id: number) => void;
	export let onSignalerAnnonce: () => void;
	export let onSignalerReponse: (id: number) => void;
</script>

<div class="annonce-card card" id="annonce-{annonce.id}">
	<div class="annonce-top">
		<Vignette
			src={annonce.photos?.length ? annonce.photos[0] : null}
			alt={annonce.titre}
			placeholder={categorieAnnonceLabel(annonce.categorie).split(' ')[0]}
			count={Math.max(0, (annonce.photos?.length ?? 0) - 1)}
		/>

		<div class="annonce-body">
			<div class="annonce-header">
				<span class="badge {typeAnnonceClass(annonce.type_annonce)}" style="font-size:.72rem">{typeAnnonceLabel(annonce.type_annonce)}</span>
				<span class="badge {statutAnnonceClass(annonce.statut)}" style="font-size:.72rem">{annonce.statut}</span>
				<!--  🔹 = périmètre LOGIQUE, et jamais affiché quand il vaut « résidence » :
				      c'est la règle du produit, la même que sur les actualités et le
				      calendrier. 📍 resterait réservé à un lieu physique. -->
				{#if !estPerimetreParDefaut(annonce.perimetre_cible)}<span class="badge badge-gray" style="font-size:.72rem">&#x1F539; {perimetreLabel(annonce.perimetre_cible)}</span>{/if}
			</div>
			<strong class="annonce-titre">{annonce.titre}
				{#if isNouveau(annonce.cree_le, annonce.mis_a_jour_le)}<span class="badge badge-gray" style="margin-left:.5em;font-size:.82em;font-weight:500;vertical-align:middle">New</span>{/if}
			</strong>
			<small style="color:var(--color-text-muted)">{categorieAnnonceLabel(annonce.categorie)} · {fmtDateShort(annonce.cree_le)}</small>
			{#if annonce.prix !== null && annonce.prix !== undefined}
				<div class="annonce-prix">{fmtMontant(annonce.prix)}{#if annonce.negotiable}&nbsp;<span class="badge badge-gray" style="font-size:.68rem">Négociable</span>{/if}</div>
			{:else if annonce.type_annonce === 'don'}
				<div class="annonce-prix" style="color:var(--color-success,#16a34a)">Gratuit</div>
			{/if}
		</div>

		<div class="annonce-toggle-col">
			<button class="btn btn-sm btn-outline" aria-expanded={expanded} on:click={onToggle}>
				{expanded ? '▲' : '▼'}
			</button>
		</div>
	</div>

	{#if expanded}
		<div class="annonce-details">
			<div class="rich-content" style="font-size:.88rem;margin-bottom:.75rem">{@html safeHtml(annonce.description)}</div>

			<!-- Les photos en grand, pour TOUT LE MONDE — auteur compris. Elles lui
			     étaient refusées (`&& !annonce.est_auteur`) : il n'avait que la grille
			     d'édition ci-dessous, des vignettes faites pour ajouter et retirer, pas
			     pour regarder. Les annonces étaient le seul contenu du produit où
			     déplier ne donnait pas la galerie (#338) — et l'auteur est précisément
			     celui qui a besoin de voir ce que les autres verront.
			     Deuxième fois que ce bloc privait quelqu'un de ses photos : la condition
			     précédente (`> 1 || est_auteur`) privait le LECTEUR d'une annonce à une
			     seule photo. Le défaut avait changé de victime, pas disparu.
			     `npm run lint:fichiers` échoue désormais sur une galerie conditionnée à
			     l'identité. -->
			{#if annonce.photos?.length}
				<PiecesJointes urls={annonce.photos} format="grand" />
			{/if}

			<!-- L'édition, sur geste explicite : c'est le pattern du produit. Partout
			     ailleurs — actualité, événement, ticket — `FichiersUpload` vit dans un
			     contexte d'ÉDITION et jamais dans la vue de lecture ; l'annonce était
			     l'exception, les deux rôles empilés dans la même carte. -->
			{#if annonce.est_auteur}
				<button
					class="btn btn-sm btn-outline"
					style="margin:.25rem 0 .5rem"
					aria-expanded={gestionOuverte}
					on:click={onToggleGestion}
				>
					{gestionOuverte ? '▲' : '▼'} Gérer les photos{annonce.photos?.length ? ` (${annonce.photos.length})` : ''}
				</button>
				{#if gestionOuverte}
					<FichiersUpload
						urls={annonce.photos ?? []}
						max={MAX_PHOTOS_ANNONCE}
						mode="photos"
						upload={onUpload}
						remove={onRemove}
					/>
				{/if}
			{/if}

			<div class="annonce-contact">
				{#if annonce.auteur_email}
					<small>&#x1F4EC; <a href="mailto:{annonce.auteur_email}">{annonce.auteur_prenom} {annonce.auteur_nom}</a></small>
				{:else}
					<small>&#x1F464; {annonce.auteur_prenom} {annonce.auteur_nom}</small>
				{/if}
			</div>

			{#if annonce.est_auteur}
				<div class="annonce-actions">
					<select value={annonce.statut} aria-label="Statut de l'annonce" on:change={(e) => onStatut((e.target as HTMLSelectElement).value)}>
						{#each STATUTS_ANNONCE as s}<option value={s.val}>{s.label}</option>{/each}
					</select>
					<!--  ✏️ AVANT 🗑️ — l'ordre des icônes d'action est celui des tickets,
					      qui sert de référence depuis le 18/08/2026. Le sélecteur de statut
					      le précède : il n'est pas une action mais l'état de l'objet.
					      🔄 (le suivi) n'existe pas ici — une annonce n'a pas de workflow,
					      c'est déclaré dans `$lib/entites/annonce`. -->
					<button class="btn-icon" title="Modifier" aria-label="Modifier l'annonce" on:click={onModifier}>&#x270F;&#xFE0F;</button>
					<button class="btn-icon-danger" title="Supprimer" aria-label="Supprimer l'annonce" on:click={onSupprimer}>&#x1F5D1;&#xFE0F;</button>
				</div>
			{:else if estCS || estAdmin}
				<div class="annonce-actions">
					<button class="btn btn-sm btn-outline" style="color:var(--color-danger)" on:click={onSupprimer}>&#x1F5D1;&#xFE0F; Supprimer</button>
				</div>
			{/if}

			{#if !annonce.est_auteur}
				<div style="margin-top:.4rem">
					<button class="signaler-inline" title="Signaler cette annonce au conseil syndical" aria-label="Signaler cette annonce" on:click={onSignalerAnnonce}>&#x1F6A9; Signaler l'annonce</button>
				</div>
			{/if}

			<Reponses
				reponses={annonce.reponses ?? []}
				{currentUserId}
				isCS={estCS}
				placeholder="Une question sur cette annonce ?"
				onSubmit={onRepondre}
				onDelete={onSupprimerReponse}
				onReport={onSignalerReponse}
			/>
		</div>
	{/if}
</div>

<style>
	.annonce-card { padding: .85rem 1.1rem; margin-bottom: .5rem; }
	.annonce-top { display: flex; gap: .85rem; align-items: flex-start; }
	.annonce-body { flex: 1; min-width: 0; }
	.annonce-header { display: flex; gap: .3rem; flex-wrap: wrap; margin-bottom: .25rem; }
	.annonce-titre { font-size: .95rem; font-weight: 600; display: block; margin-bottom: .15rem; }
	.annonce-prix { font-size: .95rem; font-weight: 700; color: var(--color-primary); margin-top: .2rem; display: flex; align-items: center; gap: .3rem; }
	.annonce-toggle-col { display: flex; align-items: flex-start; padding-top: .1rem; }
	.annonce-details { border-top: 1px solid var(--color-border); margin-top: .75rem; padding-top: .75rem; }
	.annonce-contact { margin-bottom: .6rem; }
	.annonce-contact a { color: var(--color-primary); }
	.annonce-actions { display: flex; gap: .5rem; align-items: center; flex-wrap: wrap; }
	.annonce-actions select { padding: .35rem .5rem; border: 1px solid var(--color-border); border-radius: var(--radius); font-size: .8rem; background: var(--color-bg); }
</style>
