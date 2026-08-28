<!--
  HistoriqueEvenement.svelte — le fil d'un événement de calendrier, et le geste
  qui l'alimente.

  ## Pourquoi ce composant (18/08/2026)

  Demandé ainsi : *« pour Calendrier il doit y avoir un historique et
  workflow »*. Le workflow existait déjà sous un autre nom — **les colonnes du
  Kanban répondent exactement à la question de la section 3 du cadre #430**,
  *« où en est cet objet ? »*. C'est ce que l'arbitrage a confirmé :

  > « peut-être que le kanban tu le glisses dans Workflow ? »

  Ce qui manquait était la **trace** : une colonne changeait sans que rien ne
  dise quand, par qui, ni pourquoi. Le calendrier était le dernier écran du site
  à faire avancer un suivi en silence.

  ⚠️ **Aucun second champ d'état n'a été créé.** Deux notions de suivi sur le
  même objet se contredisent au premier écart, et rien ne dirait laquelle fait
  foi. Le Kanban EST le workflow ; ce fil en enregistre les mouvements.

  ## Ce qu'il n'invente pas

  Ni le fil — `RubriqueHistorique`, la rubrique du site, qui sert déjà les
  tickets, les actualités et l'Espace CS —, ni le formulaire — `EvolForm`, avec
  ses états en pastilles. Ce composant ne fait que les relier à un événement et
  porter l'appel.

  Il est extrait de `calendrier/+page.svelte` : la page faisait 1 175 lignes et
  le garde-fou de modularité a refusé qu'elle grossisse (rang 1). La carte, elle,
  n'a **pas** pu être extraite — son `.event-row` est partagé avec les blocs
  Archives et Maintenances récurrentes, et déplacer ces règles les aurait laissés
  nus (la panne des pastilles, v2.67.11). Ce découpage-là attend #432.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import RubriqueHistorique from './RubriqueHistorique.svelte';
	import { TITRE_HISTORIQUE } from '$lib/archives';
	import EvolForm from './EvolForm.svelte';
	import { calendrier as calApi, ApiError } from '$lib/api';
	import { currentUser, isAdmin } from '$lib/stores/auth';
	import { fichiersDepuisUrls } from '$lib/fichiers';
	import { toast } from './Toast.svelte';

	export let evenement: any;
	/** Les colonnes du Kanban — la source unique reste la page. */
	export let colonnes: { id: string; label: string }[] = [];
	/** Le lecteur peut-il commenter ou faire avancer le suivi ? (CS/admin) */
	export let peutAgir = false;
	/**  Le formulaire est-il ouvert ? PORTÉ PAR LA PAGE (18/08/2026) : le geste se
	     déclare depuis l'icône 🔄 de l'en-tête de carte, comme sur les tickets et
	     les actualités. Un bouton ici, un autre là-haut, cela ferait deux commandes
	     pour un seul geste — le défaut de #367, et #426 pour la redite. */
	export let ouvert = false;

	const dispatch = createEventDispatcher<{ evolue: void; fermer: void }>();

	let enCours = false;
	//  L'entrée en cours de CORRECTION. `null` = aucune. Le fil n'en ouvre
	//  qu'une à la fois — deux formulaires ouverts sur le même fil ne diraient
	//  pas lequel enregistre quoi.
	let enEdition: number | null = null;
	let correctionEnCours = false;

	//  DÉRIVÉES des colonnes, jamais réécrites : une seconde table divergerait à
	//  la première colonne ajoutée. Le pendant serveur est `KANBAN_LABELS`
	//  (`calendrier_historique.py`) — les contextes de build sont `./api` et
	//  `./front`, le partage d'un fichier est impossible, seule la copie l'est.
	$: libelles = Object.fromEntries(colonnes.map((c) => [c.id, c.label]));
	$: options = colonnes.map((c) => ({ value: c.id, label: c.label }));

	async function enregistrer(e: CustomEvent) {
		const data = e.detail;
		enCours = true;
		try {
			await calApi.addEvolution(evenement.id, {
				type: data.type,
				contenu: data.contenu || undefined,
				nouveau_statut: data.nouveau_statut,
				fichiers_urls: data.fichiers_urls,
				//  La DIFFUSION est un ACTE, rejouable à chaque entrée : chacune est
				//  une nouvelle, à la différence d'une correction. Le serveur envoie
				//  avec un modèle propre au SUIVI — réutiliser « Nouvel événement »
				//  aurait annoncé une création à chaque commentaire.
				partager_whatsapp: data.partager_whatsapp ?? false,
				envoyer_syndic: data.envoyer_syndic ?? false,
				envoyer_cs: data.envoyer_cs ?? false,
			});
			dispatch('fermer');
			//  La page relit : le serveur a pu ajouter une ligne de correction, et
			//  la colonne a pu bouger. Recomposer le fil ici ferait diverger ce que
			//  l'écran montre de ce que la base porte.
			dispatch('evolue');
			toast('success', data.type === 'etat' ? 'Suivi mis à jour' : 'Commentaire ajouté');
		} catch (err: any) {
			toast('error', err instanceof ApiError ? err.message : 'Erreur');
		} finally { enCours = false; }
	}
	//  🔴 Une CORRECTION n'est pas une transition : elle ne porte pas de
	//  `nouveau_statut`, et le serveur inscrit « Correction : … » plutôt qu'une
	//  étape franchie. Sans cette distinction, corriger une faute de frappe
	//  ferait apparaître dans l'Historique un mouvement qui n'a jamais eu lieu
	//  (`test_correction_pas_transition.py`).
	async function corriger(e: CustomEvent) {
		if (enEdition === null) return;
		const data = e.detail;
		correctionEnCours = true;
		try {
			await calApi.updateEvolution(evenement.id, enEdition, {
				contenu: data.contenu ?? '',
				fichiers_urls: data.fichiers_urls,
			});
			enEdition = null;
			dispatch('evolue');
			toast('success', 'Entrée corrigée');
		} catch (err: any) {
			toast('error', err instanceof ApiError ? err.message : 'Erreur');
		} finally { correctionEnCours = false; }
	}

	//  Effacer — ADMIN seulement, et le serveur le revérifie (`require_admin`).
	//  Le bouton s'affichait ici sans route derrière : on cliquait, rien ne se
	//  passait (#505). La route existe depuis #512, le geste peut revenir.
	async function supprimer(e: CustomEvent<number>) {
		try {
			await calApi.deleteEvolution(evenement.id, e.detail);
			dispatch('evolue');
			toast('success', 'Entrée supprimée');
		} catch (err: any) {
			toast('error', err instanceof ApiError ? err.message : 'Erreur');
		}
	}
</script>

<div class="ev-fil">
	<RubriqueHistorique
		evolutions={evenement.evolutions ?? []}
		statutLabels={libelles}
		titre={TITRE_HISTORIQUE}
		vide={peutAgir ? 'Aucune entrée pour le moment.' : ''}
		peutModifier={peutAgir}
		currentUserId={$currentUser?.id}
		estAdmin={$isAdmin} avecSuppression
		{enEdition}
		on:modifier={(e) => (enEdition = e.detail)}
		on:supprimer={supprimer}
	>
		<!--  Le formulaire de correction prend la place de l'entrée qu'il corrige.
		      Il ne propose PAS d'état : corriger le texte d'une entrée ne rejoue
		      pas le mouvement de colonne qu'elle a enregistré. -->
		<svelte:fragment slot="edition" let:evol>
			{#key enEdition}
				<EvolForm idPrefixe="ev-evol-edit-{evol.id}" titre="Modifier le commentaire"
					editMode={true}
					initialContenu={evol.contenu || ''}
					initialFichiers={fichiersDepuisUrls(evol.fichiers_urls)}
					showPhotos={true}
					showDocuments={true}
					saving={correctionEnCours}
					on:submit={corriger}
					on:cancel={() => (enEdition = null)}
				/>
			{/key}
		</svelte:fragment>
	</RubriqueHistorique>

	{#if ouvert}
		{#key ouvert}
			<EvolForm idPrefixe="ev-evol-{evenement.id}" titre="Commenter ou changer l’état"
				statutOptions={options}
				statutLabels={libelles}
				currentStatut={evenement.statut_kanban ?? ''}
				showPhotos={true}
				showDocuments={true}
				showNotifs={true}
				saving={enCours}
				on:submit={enregistrer}
				on:cancel={() => dispatch('fermer')}
			/>
		{/key}
	{/if}
</div>

<style>
	/*  La marge qui sépare le fil de ce qu'il suit. Le reste de son allure vit
	    dans `RubriqueHistorique`, avec le balisage qui la porte. */
	.ev-fil { margin-top: .9rem; }
</style>
