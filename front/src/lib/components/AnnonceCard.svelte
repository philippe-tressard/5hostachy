<!--
  Une petite annonce : bandeau replié, détails dépliés, réponses.

  ## Réécrite sur la norme du site le 18/08/2026

  Signalé à l'écran, capture à l'appui : *« Petites annonces ne respecte pas le
  visuel de l'UX standard de la liste »*. Quatre écarts, une seule cause — cette
  carte **précède** la norme et recomposait donc son propre en-tête :

  | Écart | Correction |
  |---|---|
  | pastilles AVANT le titre | `EnteteCarte` : titre sur sa ligne, tags en dessous |
  | rien à modifier depuis la liste | ✏️ dans le slot `actions`, comme partout |
  | replié = le titre seul | `ApercuCarte` : quatre lignes, et le dégradé s'il est coupé |
  | vignette à GAUCHE | `ApercuCarte` la met à droite — la gauche porte le bord coloré |
  | on ne déplie qu'en visant ▼ | le **titre** plie, avec un survol qui le dit — `EnteteCarte` |

  ⚠️ **Aucun de ces cinq points n'a été corrigé ici** : ils viennent de composants
  qui les portaient déjà pour les actualités, les tickets et le calendrier. Une
  carte qui recompose son en-tête a sa propre façon de mal se replier — c'est
  très exactement ce que #430 R1 dit, et cette carte en était la dernière preuve.

  ## Ce qui reste propre à l'annonce

  Le prix, la gestion des photos (l'endpoint exige l'identifiant, cf. la dette
  `api` déclarée dans `$lib/entites/annonce`), et le raccourci de workflow.

  Le composant ne connaît ni l'API ni les magasins : tout ce qui écrit passe par
  un callback. C'est ce qui permet à l'onglet de garder la main sur la liste.

  Le vocabulaire — types, catégories, états et leurs rendus — vit dans
  `$lib/annonces.ts` : la carte le rend, l'onglet en fait ses filtres.
-->
<script lang="ts">
	import EnteteCarte from './EnteteCarte.svelte';
	import ApercuCarte from './ApercuCarte.svelte';
	import FichiersUpload from './FichiersUpload.svelte';
	import PiecesJointes from './PiecesJointes.svelte';
	import Reponses from './Reponses.svelte';
	import WorkflowPastilles from './WorkflowPastilles.svelte';
	import { safeHtml } from '$lib/sanitize';
	import { fmtDate2d as fmtDate, isNouveau } from '$lib/date';
	import { fmtMontant, perimetreLabel, estPerimetreParDefaut } from '$lib/utils';
	import {
		MAX_PHOTOS_ANNONCE,
		OPTIONS_STATUT_ANNONCE,
		categorieAnnonceLabel,
		statutAnnonceClass,
		statutAnnonceLabel,
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
	/**  Vrai quand l'onglet affiche un formulaire à la place du corps. Explicite,
	 *   et non déduit de `$$slots` : un slot fourni mais vide masquerait le corps
	 *   en permanence — même contrat que `CarteActualite`. */
	export let formulaireOuvert = false;

	export let onToggle: () => void;
	export let onToggleGestion: () => void;
	export let onUpload: (f: File) => Promise<string>;
	export let onRemove: (url: string) => Promise<string[] | void>;
	export let onStatut: (statut: string) => void;
	export let onSupprimer: () => void;
	export let onModifier: () => void;
	export let onRepondre: (contenu: string) => void;
	export let onSupprimerReponse: (id: number) => void;
	export let onSignalerAnnonce: () => void;
	export let onSignalerReponse: (id: number) => void;

	//  ⚠️ Le serveur refait ce contrôle (`_can_manage`) : ce qui suit n'est qu'un
	//  confort d'écran. Une interface qui cache un bouton n'a jamais protégé quoi
	//  que ce soit (`standards/03` §1).
	$: peutModifier = annonce.est_auteur;
	$: peutSupprimer = annonce.est_auteur || estCS || estAdmin;
</script>

<div class="carte-liste annonce-expand" class:expanded class:attenue={annonce.archivee}
	id="annonce-{annonce.id}">

	<!--  Titre sur sa propre ligne, puis tags à gauche / date + actions à droite :
	      la norme de toutes les cartes du site. Elle vit dans `EnteteCarte`. -->
	<EnteteCarte titre={annonce.titre} date={fmtDate(annonce.cree_le)}
		basculable on:toggle={onToggle}>
		<svelte:fragment slot="titre-suffixe">
			{#if !annonce.archivee && isNouveau(annonce.cree_le, annonce.mis_a_jour_le)}<span class="badge badge-gray annonce-neuf">New</span>{/if}
		</svelte:fragment>

		<svelte:fragment slot="tags">
			<span class="badge {typeAnnonceClass(annonce.type_annonce)}">{typeAnnonceLabel(annonce.type_annonce)}</span>
			<span class="badge {statutAnnonceClass(annonce.statut)}">{statutAnnonceLabel(annonce.statut)}</span>
			<span class="badge badge-gray">{categorieAnnonceLabel(annonce.categorie)}</span>
			<!--  🔹 = périmètre LOGIQUE, jamais affiché quand il vaut « résidence ».
			      📍 resterait réservé à un lieu physique. -->
			{#if !estPerimetreParDefaut(annonce.perimetre_cible)}<span class="badge badge-gray">&#x1F539; {perimetreLabel(annonce.perimetre_cible)}</span>{/if}
			{#if annonce.prix !== null && annonce.prix !== undefined}
				<span class="annonce-prix">{fmtMontant(annonce.prix)}{#if annonce.negotiable}&nbsp;<span class="badge badge-gray annonce-nego">Négociable</span>{/if}</span>
			{:else if annonce.type_annonce === 'don'}
				<span class="annonce-prix annonce-gratuit">Gratuit</span>
			{/if}
		</svelte:fragment>

		<!--  ✏️ AVANT 🗑️ — l'ordre des icônes est celui des tickets, qui sert de
		      référence au site. Elles vivent dans l'EN-TÊTE et non dans le corps :
		      une action qu'il faut déplier pour trouver n'existe pas (signalé à
		      l'écran le 18/08/2026, alors que l'édition venait d'être livrée).
		      `stopPropagation` est conservé par prudence : il ne sert plus depuis que
		      le geste est le titre, mais il ne coûte rien et protégerait d'un futur
		      conteneur redevenu cliquable. -->
		<svelte:fragment slot="actions">
			{#if peutModifier}
				<button class="btn-icon" aria-pressed={formulaireOuvert} title="Modifier" aria-label="Modifier l'annonce"
					on:click|stopPropagation={onModifier}>&#x270F;&#xFE0F;</button>
			{/if}
			{#if peutSupprimer}
				<button class="btn-icon-danger" title="Supprimer" aria-label="Supprimer l'annonce"
					on:click|stopPropagation={onSupprimer}>&#x1F5D1;&#xFE0F;</button>
			{/if}
		</svelte:fragment>

		<svelte:fragment slot="chevron"><span class="chevron" class:open={expanded}>›</span></svelte:fragment>
	</EnteteCarte>

	{#if !expanded}
		<!--  Quatre lignes d'aperçu et la vignette à DROITE — le composant partagé
		      des actualités et des tickets. La carte n'affichait que son titre. -->
		<ApercuCarte contenu={annonce.description} photos={annonce.photos ?? []} />
	{/if}

	{#if expanded}
		<!--  Le corps ne referme pas la carte : on referme par l'en-tête. Sans cela,
		      impossible de sélectionner du texte, et un clic sur une photo ou un
		      formulaire referme ce qu'on lisait (ux-patterns §3). -->
		<div class="annonce-body" role="presentation" on:click|stopPropagation on:keydown|stopPropagation>
			{#if formulaireOuvert}
				<slot name="formulaire" />
			{:else}
				<div class="rich-content annonce-texte">{@html safeHtml(annonce.description)}</div>

				<!-- Les photos en grand, pour TOUT LE MONDE — auteur compris. Elles lui
				     étaient refusées (`&& !annonce.est_auteur`) : il n'avait que la grille
				     d'édition ci-dessous, des vignettes faites pour ajouter et retirer, pas
				     pour regarder. Deuxième fois que ce bloc privait quelqu'un de ses
				     photos : la condition précédente (`> 1 || est_auteur`) privait le
				     LECTEUR d'une annonce à une seule photo. Le défaut avait changé de
				     victime, pas disparu. `npm run lint:fichiers` échoue désormais sur une
				     galerie conditionnée à l'identité. -->
				{#if annonce.photos?.length}
					<PiecesJointes urls={annonce.photos} format="grand" />
				{/if}

				<!-- L'édition des photos, sur geste explicite : c'est le pattern du
				     produit. Elle reste ICI et non dans le formulaire — l'endpoint exige
				     l'identifiant de l'annonce, dette `api` déclarée et suivie (#441).
				     La rouvrir dans le formulaire donnerait deux chemins concurrents. -->
				{#if annonce.est_auteur}
					<button class="btn btn-sm btn-outline annonce-gerer"
						aria-expanded={gestionOuverte} on:click={onToggleGestion}>
						{gestionOuverte ? '▲' : '▼'} Gérer les photos{annonce.photos?.length ? ` (${annonce.photos.length})` : ''}
					</button>
					{#if gestionOuverte}
						<FichiersUpload urls={annonce.photos ?? []} max={MAX_PHOTOS_ANNONCE}
							mode="photos" upload={onUpload} remove={onRemove} />
					{/if}
				{/if}

				<div class="annonce-contact">
					{#if annonce.auteur_email}
						<small>&#x1F4EC; <a href="mailto:{annonce.auteur_email}">{annonce.auteur_prenom} {annonce.auteur_nom}</a></small>
					{:else}
						<small>&#x1F464; {annonce.auteur_prenom} {annonce.auteur_nom}</small>
					{/if}
				</div>

				<!--  Le raccourci de workflow : des PASTILLES, jamais un `<select>` nu
				      (R3 / #423). Le `<select>` d'origine était le dernier du site.
				      Il double le formulaire de correction, et c'est assumé : changer
				      l'état est le geste le plus fréquent sur une annonce, il ne doit
				      pas coûter l'ouverture d'un formulaire. Les deux chemins écrivent
				      le MÊME fait, et le serveur l'horodate d'une seule façon. -->
				{#if annonce.est_auteur}
					<div class="annonce-workflow">
						<span class="annonce-workflow-titre" id="wf-annonce-{annonce.id}">Où en est cette annonce ?</span>
						<WorkflowPastilles options={OPTIONS_STATUT_ANNONCE} valeur={annonce.statut}
							idTitre="wf-annonce-{annonce.id}" on:choisir={(e) => onStatut(e.detail)} />
					</div>
				{/if}

				{#if !annonce.est_auteur}
					<div class="annonce-signaler">
						<button class="signaler-inline" title="Signaler cette annonce au conseil syndical"
							aria-label="Signaler cette annonce" on:click={onSignalerAnnonce}>&#x1F6A9; Signaler l'annonce</button>
					</div>
				{/if}

				<Reponses reponses={annonce.reponses ?? []} {currentUserId} isCS={estCS}
					placeholder="Une question sur cette annonce ?"
					onSubmit={onRepondre} onDelete={onSupprimerReponse} onReport={onSignalerReponse} />
			{/if}
		</div>
	{/if}
</div>

<style>
	/*  Conteneur, survol et espacement : `.carte-liste` (app.css). L'en-tête, ses
	    tags et leur repli : `EnteteCarte`. L'aperçu et sa vignette : `ApercuCarte`.
	    Ne reste ici que ce qui est propre à une annonce. */
	.annonce-neuf { margin-left: .4em; font-size: .82em; font-weight: 500; vertical-align: middle; }
	.annonce-prix { font-size: .85rem; font-weight: 700; color: var(--color-primary); white-space: nowrap; }
	.annonce-gratuit { color: var(--color-success, #16a34a); }
	.annonce-nego { font-size: .68rem; font-weight: 500; }

	.annonce-body { padding: .75rem 1rem 1rem; border-top: 1px solid var(--color-border); }
	.annonce-texte { font-size: .875rem; line-height: 1.6; margin-bottom: .5rem; }
	.annonce-gerer { margin: .25rem 0 .5rem; }
	.annonce-contact { margin: .6rem 0; }
	.annonce-contact a { color: var(--color-primary); }

	.annonce-workflow { margin-top: .75rem; }
	.annonce-workflow-titre { display: block; font-size: .8rem; font-weight: 600; color: var(--color-text-muted); margin-bottom: .35rem; }

	.annonce-signaler { margin-top: .4rem; }

	/*  Archives : la carte s'efface tant qu'on ne la vise pas — même traitement
	    que l'historique des actualités, pour que les deux listes se lisent pareil. */
	.attenue { opacity: .8; transition: opacity .15s; margin-bottom: .3rem; }
	.attenue:hover { opacity: 1; }
</style>
