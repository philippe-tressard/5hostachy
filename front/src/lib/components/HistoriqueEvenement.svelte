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
	import EvolForm from './EvolForm.svelte';
	import { calendrier as calApi, ApiError } from '$lib/api';
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
</script>

<div class="ev-fil">
	<RubriqueHistorique
		evolutions={evenement.evolutions ?? []}
		statutLabels={libelles}
		titre="&#x1F4CB; Historique"
		vide={peutAgir ? 'Aucune entrée pour le moment.' : ''}
	>
	</RubriqueHistorique>

	{#if ouvert}
		{#key ouvert}
			<EvolForm idPrefixe="ev-evol-{evenement.id}"
				statutOptions={options}
				statutLabels={libelles}
				currentStatut={evenement.statut_kanban ?? ''}
				showFiles={true}
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
