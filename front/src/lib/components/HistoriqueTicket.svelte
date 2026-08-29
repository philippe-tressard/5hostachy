<!--
  HistoriqueTicket.svelte — le fil d'un ticket, et les gestes qui l'alimentent.

  ## Pourquoi ce composant (18/08/2026)

  Le fil d'un ticket était rendu à **deux endroits** : `CarteTicket` (la liste) et
  la fiche `/tickets/[id]`, chacun avec son propre câblage. Deux rendus de la même
  entité, donc deux jeux de branchements à tenir d'accord — et ils ne l'ont pas
  été, **deux fois, dans les deux sens** :

    • le CRAYON servait la fiche et manquait à la liste (#431) ;
    • la CORBEILLE, ajoutée à la liste, manquait à la fiche le jour même.

  Le second écart est celui qui a fait naître ce fichier : le garde-fou de
  modularité a refusé que la fiche grossisse pour recevoir le handler manquant, et
  il avait raison — ce n'était pas un problème de taille mais de **placement**. Un
  fil de ticket, avec son formulaire de commentaire, sa correction d'entrée et sa
  suppression, est une notion : elle s'écrit une fois.

  ⚠️ Ce composant ne remplace pas `RubriqueHistorique`, il l'**habille** : la
  rubrique reste le fil générique — actualités, événements, espace CS l'utilisent
  aussi — et celui-ci y ajoute ce qui est propre au TICKET.

  ## Ce qu'il décide, et ce qu'il ne décide pas

  Il porte les gestes et leurs appels d'API. La page garde ce qu'elle seule sait :
  quel ticket, et quoi faire après (recharger sa liste). D'où `on:change`, émis
  après chaque écriture — c'est le seul contrat.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import RubriqueHistorique from './RubriqueHistorique.svelte';
	import { TITRE_HISTORIQUE } from '$lib/archives';
	import EvolForm from './EvolForm.svelte';
	import { tickets as ticketsApi, ApiError, type TicketEvolution } from '$lib/api';
	import { toast } from './Toast.svelte';
	import { currentUser, isAdmin, isCS } from '$lib/stores/auth';
	import { fichiersDepuisUrls } from '$lib/fichiers';
	import { STATUT_TICKET_LABELS } from '$lib/tickets';
	import { evolutionIcone } from '$lib/evolutions';
	import { TICKET } from '$lib/entites/ticket';
	import { sectionPresente } from '$lib/entites/types';

	export let ticketId: number;
	export let statutCourant = '';
	/**  Périmètre courant du ticket — affiché en badge dans le formulaire, pour
	     qu'on voie d'où l'on part avant de le préciser (#497). */
	export let perimetreCourant: string[] = [];
	export let evolutions: TicketEvolution[] = [];

	/** Émis après toute écriture — la page recharge ce qu'elle affiche. */
	const dispatch = createEventDispatcher<{ change: void }>();

	let ouvert = false;
	let enEdition: number | null = null;
	let enregistre = false;
	let corrige = false;

	//  L'aperçu d'un commentaire : le message part avec l'HISTORIQUE du ticket
	//  derrière lui, et c'est justement ce que personne ne relit avant d'envoyer
	//  (#498). Le brouillon est composé par le serveur, avec les fonctions de
	//  l'envoi — l'écran n'en fabrique aucune partie.
	//
	//  La saisie vient du formulaire lui-même : lui seul la tient, et une lecture
	//  depuis ici rendrait des valeurs vides.
	function apercuDuCommentaire(saisie: {
		contenu: string;
		fichiers_urls: string[];
		whatsapp: boolean;
		syndic: boolean;
		cs: boolean;
	}) {
		return ticketsApi.apercuDiffusion({
			ticket_id: ticketId,
			commentaire: saisie.contenu,
			fichiers_urls: saisie.fichiers_urls,
			destinataire_syndic: saisie.syndic,
			destinataire_cs: saisie.cs,
			partager_whatsapp: saisie.whatsapp,
		});
	}

	async function ajouter(e: CustomEvent) {
		enregistre = true;
		try {
			await ticketsApi.addEvolution(ticketId, e.detail);
			ouvert = false;
			dispatch('change');
			toast('success', e.detail?.nouveau_statut ? 'Statut mis à jour' : 'Commentaire ajouté');
		} catch (err) {
			toast('error', err instanceof ApiError ? err.message : 'Erreur');
		} finally {
			enregistre = false;
		}
	}

	//  🔴 Ni `type` ni `nouveau_statut` : une CORRECTION n'est pas une transition.
	//  Les envoyer ferait apparaître dans le fil une étape que le ticket n'a jamais
	//  franchie (`test_correction_pas_transition.py`).
	async function corriger(e: CustomEvent) {
		if (enEdition === null) return;
		corrige = true;
		try {
			await ticketsApi.updateEvolution(ticketId, enEdition, {
				contenu: e.detail?.contenu ?? '',
				fichiers_urls: e.detail?.fichiers_urls,
			});
			enEdition = null;
			dispatch('change');
			toast('success', 'Entrée corrigée');
		} catch (err) {
			toast('error', err instanceof ApiError ? err.message : 'Erreur');
		} finally {
			corrige = false;
		}
	}

	//  Effacer — ADMIN seulement, et le serveur le revérifie (`require_admin`). Une
	//  transition d'état est refusée côté serveur (422) et n'affiche pas de
	//  corbeille côté écran : l'écran dit la même chose que le serveur.
	async function supprimer(e: CustomEvent<number>) {
		try {
			await ticketsApi.deleteEvolution(ticketId, e.detail);
			dispatch('change');
			toast('success', 'Entrée supprimée');
		} catch (err) {
			toast('error', err instanceof ApiError ? err.message : 'Erreur');
		}
	}
</script>

<div class="bloc-historique">
	<RubriqueHistorique
		{evolutions}
		statutLabels={STATUT_TICKET_LABELS}
		titre={TITRE_HISTORIQUE}
		vide="Aucune évolution enregistrée."
		peutModifier={$isCS}
		currentUserId={$currentUser?.id}
		estAdmin={$isAdmin}
		avecSuppression
		{enEdition}
		on:modifier={(e) => (enEdition = e.detail)}
		on:supprimer={supprimer}
	>
		<svelte:fragment slot="action">
			{#if $isCS}
				<button class="btn btn-outline btn-sm" on:click={() => (ouvert = !ouvert)}>
					<!--  Le bouton et l'entrée qu'il produit lisent la MÊME table : c'est ce
					      qui les empêche de diverger, et c'est précisément par là que
					      l'écart est arrivé (19/08/2026). -->
					{ouvert ? '✕ Annuler' : `${evolutionIcone('commentaire')} Commenter`}
				</button>
			{/if}
		</svelte:fragment>

		<svelte:fragment slot="edition" let:evol>
			{#key enEdition}
				<EvolForm
					idPrefixe="tk-evol-edit-{evol.id}"
					titre="Modifier le commentaire"
					editMode={true}
					initialContenu={evol.contenu || ''}
					initialFichiers={fichiersDepuisUrls(evol.fichiers_urls)}
					showPhotos={sectionPresente(TICKET, 'evolution', 'photos')}
					showDocuments={sectionPresente(TICKET, 'evolution', 'documents')}
					saving={corrige}
					on:submit={corriger}
					on:cancel={() => (enEdition = null)}
				/>
			{/key}
		</svelte:fragment>
	</RubriqueHistorique>

	{#if ouvert}
		<div class="evol-form card">
			{#key ouvert}
				<EvolForm
					idPrefixe="tk-evol"
					titre="Commenter"
					demanderApercu={apercuDuCommentaire}
					statutLabels={STATUT_TICKET_LABELS}
					currentStatut={statutCourant}
					avecPerimetre={$isCS && sectionPresente(TICKET, 'evolution', 'perimetre')}
					{perimetreCourant}
					showNotifs={$isCS && sectionPresente(TICKET, 'evolution', 'diffusion')}
					showEmail={$isCS}
					showPhotos={sectionPresente(TICKET, 'evolution', 'photos')}
					showDocuments={sectionPresente(TICKET, 'evolution', 'documents')}
					saving={enregistre}
					on:submit={ajouter}
					on:cancel={() => (ouvert = false)}
				/>
			{/key}
		</div>
	{/if}
</div>

<style>
	/*  Le balisage part avec ses styles : une classe posée ici et définie dans la
	    page ne serait pas atteinte (panne des pastilles nues, v2.67.11). */
	.bloc-historique {
		margin-top: 1.5rem;
		max-width: 720px;
	}
	.evol-form {
		margin-top: 1rem;
	}
</style>
