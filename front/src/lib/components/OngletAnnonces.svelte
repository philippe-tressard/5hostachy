<!--
  L'onglet **Petites annonces** de la Communauté — ses filtres, sa liste, son
  formulaire de dépôt et son formulaire de correction.

  Extrait de `sondages/+page.svelte` le 18/08/2026. La page porte TROIS rubriques
  (sondages, boîte à idées, petites annonces) et repassait au-dessus du plafond
  de modularité (rang 1, `standards/02` §6) en ajoutant le mode édition. La règle
  est « au fil de l'eau » : on découpe le fichier **quand on y touche**, et c'est
  la rubrique touchée qui sort — pas un découpage de confort décidé ailleurs.

  ⚠️ **26 lignes de code MORT sont parties avec ce déménagement** : `creerAnnonce()`,
  `formAnnonce` et `submittingAnnonce` étaient restés dans la page après
  l'extraction de `FormulaireAnnonce` le 16/08 — un second chemin de création,
  complet et plausible, que plus rien n'appelait. C'est ce qu'un déménagement
  rend visible et qu'une relecture ne voit pas : le code mort ressemble au code
  vivant.

  ## Ce que ce composant ne fait pas

  Il ne **charge** pas la liste : la page le fait, en même temps que les sondages
  et les idées (un seul `Promise.all`), et la lie ici. Il ne connaît pas non plus
  les signalements — `onSignaler` est un rappel, parce que la modération est
  commune aux trois rubriques et vit avec elles.
-->
<script lang="ts">
	import AnnonceCard from '$lib/components/AnnonceCard.svelte';
	import FormulaireAnnonce from '$lib/components/FormulaireAnnonce.svelte';
	import { CATEGORIES_ANNONCE, TYPES_ANNONCE } from '$lib/annonces';
	import { annonces as annoncesApi, ApiError } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';

	/** La liste, tenue par la page — elle la charge avec les deux autres rubriques. */
	export let annonces: any[] = [];
	export let chargement = false;
	/** Le formulaire de dépôt est ouvert ? Lié : le bouton vit dans l'en-tête de page. */
	export let showForm = false;
	/** L'annonce dépliée — liée aussi : un lien profond (`#annonce-12`) la désigne. */
	export let expandedAnnonce: number | null = null;
	export let estCS = false;
	export let estAdmin = false;
	export let currentUserId: number | undefined = undefined;
	export let onSignaler: (cibleType: string, cibleId: number) => void;

	let filtreType = '';
	let filtreCategorie = '';
	let filtreTri = 'recent';
	/** Annonce dont l'auteur a demandé à GÉRER les photos — voir `AnnonceCard`. */
	let gestionPhotos: number | null = null;
	//  L'annonce en cours de CORRECTION. Un seul formulaire ouvert à la fois : le
	//  `{#key}` du rendu remonte le composant à neuf quand on passe d'une annonce à
	//  l'autre, sinon les champs garderaient les valeurs de la précédente.
	let editAnnonce: any = null;

	$: filtrees = annonces
		.filter((a) => !filtreType || a.type_annonce === filtreType)
		.filter((a) => !filtreCategorie || a.categorie === filtreCategorie);
	$: triees = [...filtrees].sort((a, b) => {
		if (filtreTri === 'prix_asc') return (a.prix ?? 999999) - (b.prix ?? 999999);
		if (filtreTri === 'prix_desc') return (b.prix ?? 0) - (a.prix ?? 0);
		return new Date(b.cree_le).getTime() - new Date(a.cree_le).getTime();
	});

	/** Téléverse une photo et retourne son URL (contrat attendu par `FichiersUpload`). */
	async function uploadPhoto(id: number, file: File): Promise<string> {
		const res: any = await annoncesApi.uploadPhoto(id, file);
		annonces = annonces.map((a) => (a.id === id ? { ...a, photos: res.photos } : a));
		return res.url;
	}

	/** Supprime une photo et retourne la liste à jour (même contrat). */
	async function supprimerPhoto(id: number, url: string): Promise<string[]> {
		const res: any = await annoncesApi.deletePhoto(id, url);
		annonces = annonces.map((a) => (a.id === id ? { ...a, photos: res.photos } : a));
		return res.photos;
	}

	async function changerStatut(id: number, statut: string) {
		try {
			await annoncesApi.updateStatut(id, statut);
			//  « Archivé » sort l'annonce de la liste : le serveur l'exclut déjà du
			//  `GET`, la garder à l'écran ferait croire qu'elle est encore visible des
			//  voisins.
			if (statut === 'archive') annonces = annonces.filter((a) => a.id !== id);
			else annonces = annonces.map((a) => (a.id === id ? { ...a, statut } : a));
			toast('success', 'Statut mis à jour');
		} catch {
			toast('error', 'Erreur');
		}
	}

	async function supprimer(id: number) {
		if (!confirm('Supprimer définitivement cette annonce ?')) return;
		try {
			await annoncesApi.supprimer(id);
			annonces = annonces.filter((a) => a.id !== id);
			toast('success', 'Annonce supprimée');
		} catch {
			toast('error', 'Erreur');
		}
	}

	async function repondre(id: number, contenu: string) {
		try {
			await annoncesApi.repondre(id, contenu);
			annonces = await annoncesApi.list();
			toast('success', 'Réponse publiée');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
			throw e;
		}
	}

	async function supprimerReponse(annonceId: number, repId: number) {
		try {
			await annoncesApi.supprimerReponse(annonceId, repId);
			annonces = await annoncesApi.list();
			toast('success', 'Réponse supprimée');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}
</script>

{#if showForm}
	<FormulaireAnnonce
		on:cree={(e) => {
			annonces = [e.detail, ...annonces];
			showForm = false;
			expandedAnnonce = e.detail.id;
		}}
		on:annule={() => (showForm = false)}
	/>
{/if}

<div class="filters" style="margin-bottom:1.25rem">
	<select bind:value={filtreType} class="filter-select" aria-label="Filtrer par type">
		<option value="">Tous types</option>
		{#each TYPES_ANNONCE as t}<option value={t.val}>{t.label}</option>{/each}
	</select>
	<select bind:value={filtreCategorie} class="filter-select" aria-label="Filtrer par catégorie">
		<option value="">Toutes catégories</option>
		{#each CATEGORIES_ANNONCE as c}<option value={c.val}>{c.label}</option>{/each}
	</select>
	<select bind:value={filtreTri} class="filter-select" aria-label="Trier les annonces">
		<option value="recent">Plus récentes</option>
		<option value="prix_asc">Prix croissant</option>
		<option value="prix_desc">Prix décroissant</option>
	</select>
</div>

{#if chargement}
	<p style="color:var(--color-text-muted)">Chargement…</p>
{:else if triees.length === 0}
	<div class="empty-state">
		<h3>Aucune annonce</h3>
		<p>Déposez la première annonce en cliquant sur « Déposer une annonce ».</p>
	</div>
{:else}
	{#each triees as annonce (annonce.id)}
		<AnnonceCard
			{annonce}
			expanded={expandedAnnonce === annonce.id}
			gestionOuverte={gestionPhotos === annonce.id}
			{estCS}
			{estAdmin}
			{currentUserId}
			onToggle={() => (expandedAnnonce = expandedAnnonce === annonce.id ? null : annonce.id)}
			onToggleGestion={() => (gestionPhotos = gestionPhotos === annonce.id ? null : annonce.id)}
			onUpload={(f) => uploadPhoto(annonce.id, f)}
			onRemove={(url) => supprimerPhoto(annonce.id, url)}
			onStatut={(statut) => changerStatut(annonce.id, statut)}
			onSupprimer={() => supprimer(annonce.id)}
			onModifier={() => {
				editAnnonce = editAnnonce?.id === annonce.id ? null : annonce;
				expandedAnnonce = annonce.id;
			}}
			onRepondre={(c) => repondre(annonce.id, c)}
			onSupprimerReponse={(rid) => supprimerReponse(annonce.id, rid)}
			onSignalerAnnonce={() => onSignaler('annonce', annonce.id)}
			onSignalerReponse={(rid) => onSignaler('reponse', rid)}
		/>
		{#if editAnnonce?.id === annonce.id}
			<!--  Le formulaire de CORRECTION s'ouvre sous la carte qu'il corrige — même
			      geste que sur Tickets et Actualités. `{#key}` remonte le composant à
			      neuf d'une annonce à l'autre : ses champs sont initialisés une fois, à
			      la construction. -->
			{#key editAnnonce.id}
				<FormulaireAnnonce
					annonce={editAnnonce}
					on:modifie={(e) => {
						annonces = annonces.map((a) => (a.id === e.detail.id ? e.detail : a));
						editAnnonce = null;
					}}
					on:annule={() => (editAnnonce = null)}
				/>
			{/key}
		{/if}
	{/each}
{/if}
