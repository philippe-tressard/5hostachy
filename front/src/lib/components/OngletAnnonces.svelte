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

  Les annonces conclues depuis plus d'un mois basculent dans des **Archives
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
	import ListeEtArchives from '$lib/components/ListeEtArchives.svelte';
	import EtatListe from '$lib/components/EtatListe.svelte';
	import ChoixPastilles from '$lib/components/ChoixPastilles.svelte';
	import { CATEGORIES_ANNONCE, TYPES_ANNONCE } from '$lib/annonces';
	import { annonces as annoncesApi, ApiError } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';

	/** La liste, tenue par la page — elle la charge avec les deux autres rubriques. */
	export let annonces: any[] = [];
	export let chargement = false;
	/**  Non vide = on n'a PAS pu charger. À afficher AVANT « aucune annonce » :
	 *   annoncer une absence qu'on n'a pas constatée, c'est ce qui a fait croire
	 *   à trois annonces perdues (#519). */
	export let erreur = '';
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

	//  La partition courants / Archives ne se fait plus ici : `ListeEtArchives`
	//  la porte pour les trois onglets de la Communauté, sur le `archivee` que le
	//  serveur calcule (voir son en-tête).

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

	//  🔴 La correction s'ouvre DANS la carte, à la place de son corps (#787,
	//  06/09/2026) — la fenêtre flottante posée le 02/09 (#640) a été écartée à
	//  l'écran : « pas de spécifique, comme le reste du site ». Conséquence
	//  directe : le clic sur ✏️ doit DÉPLIER la carte, sinon le formulaire n'a
	//  nulle part où apparaître. C'est ce que fait la fonction ci-dessous.
	function modifier(a: any) {
		editAnnonce = editAnnonce?.id === a.id ? null : a;
		//  🔴 DÉPLIER la carte, sinon le formulaire n'apparaît nulle part : il vit
		//  dans le corps, et le corps n'est rendu que déplié. Le bouton ✏️ aurait
		//  été muet — le défaut EXACT que ce lot corrige, sous une autre forme.
		//
		//  ⚠️ Une seule carte dépliée à la fois, comme les actualités : deux
		//  formulaires ouverts simultanément laisseraient l'utilisateur écrire dans
		//  celui qu'il ne regarde pas.
		expandedAnnonce = editAnnonce ? a.id : null;
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
	<!--  🔴 TROIS valeurs : sous le seuil des listes courtes, donc des PASTILLES —
	      la règle est écrite dans `ux-patterns` depuis le 29/08/2026 (#491) et
	      n'avait pas été appliquée ici. Confirmée par l'utilisateur le 06/09
	      (« ≤ 5 valeurs en pastilles ») : les deux seuils coïncident, aucune liste
	      du produit n'a cinq ou six valeurs.

	      ⚠️ La catégorie reste un `<select>` juste à côté, et c'est la règle qui
	      le veut : NEUF valeurs. Deux formes voisines sur une même barre n'est pas
	      une incohérence — c'est la cardinalité qui choisit, pas l'écran. Le
	      §« seuil des listes courtes » nomme d'ailleurs `CATEGORIES_ANNONCE` comme
	      le cas qui reste dehors. -->
	<ChoixPastilles
		options={TYPES_ANNONCE}
		bind:valeur={filtreType}
		tous="Tous types"
		libelle="Filtrer les annonces par type"
	/>
	<select bind:value={filtreCategorie} class="filter-select" aria-label="Filtrer par catégorie">
		<option value="">Toutes catégories</option>
		{#each CATEGORIES_ANNONCE as c (c.val)}<option value={c.val}>{c.label}</option>{/each}
	</select>
	<select bind:value={filtreTri} class="filter-select" aria-label="Trier les annonces">
		<option value="recent">Plus récentes</option>
		<option value="prix_asc">Prix croissant</option>
		<option value="prix_desc">Prix décroissant</option>
	</select>
</div>

<!--  🔴 Les trois états — chargement, erreur, vide — étaient écrits ICI, à la
      main, alors que `EtatListe` les porte (#796). Ils reproduisaient le
      composant à l'identique : même `Chargement…`, même `empty-state` avec titre
      et message, même priorité de l'erreur sur le vide.

      ⚠️ L'état ERREUR est celui qu'on oublie en recopiant, parce qu'on ne le voit
      jamais en développement. Ici il était présent — mais son titre et sa mise en
      forme ne suivaient plus le composant, et un ajustement de l'un aurait laissé
      l'autre en arrière. C'est la duplication de balisage, pas de logique : celle
      qui ne casse rien et qui dérive.

      La condition de vide porte sur la liste ENTIÈRE, archives comprises : une
      annonce archivée n'est pas rien, et annoncer « Aucune annonce » alors que
      les Archives en portent trois serait faux (#519). -->
<EtatListe
	{chargement}
	{erreur}
	vide={triees.length === 0}
	titreErreur="Impossible d'afficher les annonces"
	titreVide="Aucune annonce"
	messageVide="Déposez la première annonce en cliquant sur « Déposer une annonce »."
>
	<ListeEtArchives
		liste={triees}
		titreVideCourant="Aucune annonce en cours"
		messageVideCourant="Les annonces conclues sont rangées dans les Archives, ci-dessous."
	>
		<svelte:fragment let:items>
			<ListeAnnonces
				liste={items}
				expandedId={expandedAnnonce}
				gestionPhotosId={gestionPhotos}
				{estCS}
				{estAdmin}
				{currentUserId}
				onToggle={basculer}
				onToggleGestion={basculerGestion}
				onModifier={modifier}
				editId={editAnnonce?.id ?? null}
				onUpload={uploadPhoto}
				onRemove={supprimerPhoto}
				onStatut={changerStatut}
				onSupprimer={supprimer}
				onRepondre={repondre}
				onSupprimerReponse={supprimerReponse}
				{onSignaler}
			>
				<svelte:fragment slot="formulaire" let:annonce>
					<!--  `{#key}` remonte le composant d'une annonce à l'autre : ses champs
					      sont initialisés une seule fois, à la construction. -->
					{#key annonce.id}
						<FormulaireAnnonce
							{annonce}
							on:modifie={(e) => appliquerModification(e.detail)}
							on:annule={() => (editAnnonce = null)}
						/>
					{/key}
				</svelte:fragment>
			</ListeAnnonces>
		</svelte:fragment>
	</ListeEtArchives>
</EtatListe>

<!--  🔴 LE FORMULAIRE DE CORRECTION N'EST PLUS ICI (#787, 06/09/2026).
      Il était monté en bas, après les deux listes : « c'est tout en bas, et on
      ne voit pas ». Il vit maintenant DANS la carte de l'annonce, par le slot
      `formulaire` que `ListeAnnonces` relaie — le pattern de la carte
      d'actualité, qui existait déjà. -->
