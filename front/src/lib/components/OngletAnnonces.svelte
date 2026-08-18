<!--
  L'onglet **Petites annonces** de la Communauté — ses filtres, sa liste, son
  formulaire de dépôt et son Historique.

  Extrait de `sondages/+page.svelte` le 18/08/2026 (plafond de modularité). La
  page porte TROIS rubriques ; la règle est « au fil de l'eau », et c'est la
  rubrique touchée qui sort.

  ⚠️ **26 lignes de code MORT sont parties avec ce déménagement** : `creerAnnonce()`,
  `formAnnonce` et `submittingAnnonce` étaient restés dans la page après
  l'extraction de `FormulaireAnnonce` le 16/08 — un second chemin de création,
  complet et plausible, que plus rien n'appelait. C'est ce qu'un déménagement rend
  visible et qu'une relecture ne voit pas : le code mort ressemble au code vivant.

  ## Deux listes, un seul rendu

  Les annonces conclues depuis plus d'un mois basculent dans un **Historique
  replié** — demandé le 18/08/2026. Les deux listes passent par le MÊME
  `ListeAnnonces` : recopier le `{#each}` sous la section repliée aurait créé
  deux rendus libres de diverger, ce qui est arrivé six fois au fil des tickets
  (#431).

  🔴 `annonce.archivee` est **calculé par le serveur**. Refaire la règle ici
  (« vendu depuis plus de 30 jours ») en ferait une seconde, et les deux
  trancheraient différemment le jour où le délai changerait — c'est le bug du
  17/07/2026 sur les actualités, un élément visible dans une vue et pas dans
  l'autre.

  ## Ce que ce composant ne fait pas

  Il ne **charge** pas la liste : la page le fait, en même temps que les sondages
  et les idées (un seul `Promise.all`), et la lie ici. Il ne connaît pas non plus
  les signalements — `onSignaler` est un rappel, parce que la modération est
  commune aux trois rubriques et vit avec elles.
-->
<script lang="ts">
	import FormulaireAnnonce from '$lib/components/FormulaireAnnonce.svelte';
	import ListeAnnonces from '$lib/components/ListeAnnonces.svelte';
	import SectionRepliee from '$lib/components/SectionRepliee.svelte';
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

	//  La partition vient du serveur, pas d'un calcul local — voir l'en-tête.
	$: courantes = triees.filter((a) => !a.archivee);
	$: archivees = triees.filter((a) => a.archivee);

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
			//  🔴 La liste est RECHARGÉE, pas rapiécée localement : c'est le serveur qui
			//  décide de `archivee`, et lui seul sait si ce changement d'état vient de
			//  faire basculer l'annonce dans l'Historique. Poser `{...a, statut}` à la
			//  main laisserait une annonce annulée dans la liste courante jusqu'au
			//  prochain rechargement de page.
			annonces = await annoncesApi.list();
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

	const basculer = (a: any) => (expandedAnnonce = expandedAnnonce === a.id ? null : a.id);
	const basculerGestion = (a: any) => (gestionPhotos = gestionPhotos === a.id ? null : a.id);

	function modifier(a: any) {
		editAnnonce = editAnnonce?.id === a.id ? null : a;
		//  Le formulaire prend la place du CORPS : sans déplier, le clic sur ✏️
		//  n'aurait aucun effet visible.
		if (editAnnonce) expandedAnnonce = a.id;
	}

	function appliquerModification(maj: any) {
		//  Rechargée pour la même raison que le changement d'état : la correction
		//  peut porter le workflow, donc décider de l'archivage.
		annonces = annonces.map((a) => (a.id === maj.id ? maj : a));
		editAnnonce = null;
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

<div class="filters">
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
{:else if courantes.length === 0 && archivees.length === 0}
	<div class="empty-state">
		<h3>Aucune annonce</h3>
		<p>Déposez la première annonce en cliquant sur « Déposer une annonce ».</p>
	</div>
{:else}
	{#if courantes.length === 0}
		<div class="empty-state">
			<h3>Aucune annonce en cours</h3>
			<p>Les annonces conclues sont rangées dans l'Historique, ci-dessous.</p>
		</div>
	{/if}
	<ListeAnnonces
		liste={courantes}
		expandedId={expandedAnnonce}
		gestionPhotosId={gestionPhotos}
		{editAnnonce}
		{estCS}
		{estAdmin}
		{currentUserId}
		onToggle={basculer}
		onToggleGestion={basculerGestion}
		onModifier={modifier}
		onUpload={uploadPhoto}
		onRemove={supprimerPhoto}
		onStatut={changerStatut}
		onSupprimer={supprimer}
		onRepondre={repondre}
		onSupprimerReponse={supprimerReponse}
		{onSignaler}
		onModifiee={appliquerModification}
		onAnnulerEdition={() => (editAnnonce = null)}
	/>

	<!--  L'Historique : replié par défaut, même bandeau que celui des actualités
	      (`SectionRepliee`, extrait dans ce lot pour ne pas en écrire un second).
	      Les cartes y sont les MÊMES — `ListeAnnonces`, appelé une seconde fois —
	      simplement atténuées par `annonce.archivee`. -->
	{#if archivees.length}
		<SectionRepliee titre="&#x1F4C1; Historique" compte={archivees.length}>
			<ListeAnnonces
				liste={archivees}
				expandedId={expandedAnnonce}
				gestionPhotosId={gestionPhotos}
				{editAnnonce}
				{estCS}
				{estAdmin}
				{currentUserId}
				onToggle={basculer}
				onToggleGestion={basculerGestion}
				onModifier={modifier}
				onUpload={uploadPhoto}
				onRemove={supprimerPhoto}
				onStatut={changerStatut}
				onSupprimer={supprimer}
				onRepondre={repondre}
				onSupprimerReponse={supprimerReponse}
				{onSignaler}
				onModifiee={appliquerModification}
				onAnnulerEdition={() => (editAnnonce = null)}
			/>
		</SectionRepliee>
	{/if}
{/if}
