<!--
  Le formulaire d'une publication — celui qu'on remplit pour la CRÉER, et celui
  qu'on rouvre pour la MODIFIER. Un seul fichier pour les deux gestes.

  Extrait de `actualites/+page.svelte` (#356) parce que la page dépassait le
  plafond de 500 lignes ; rendu **paramétrable** le 18/08/2026 (#433).

  ## Pourquoi il sert aussi l'édition (#433)

  Le crayon ✏️ d'une carte ouvrait un SECOND formulaire, écrit à la main dans la
  page — 31 lignes. Il **perdait** cinq notions que celui-ci propose (périmètre,
  destinataires, photos, documents, canaux) et **gagnait** un `<select>` « État »
  que la création n'avait pas : une publication naissait donc sans état visible
  et n'en acquérait un qu'à la modification.

  Rien de tout cela n'était une contrainte serveur. `PublicationUpdate` accepte
  **quinze** champs ; le formulaire d'édition en proposait **sept**. Sous le cadre
  #430, un écart pareil ne peut plus exister sans motif — et les motifs, quand
  ils existent, vivent dans `$lib/entites/publication`, pas ici.

  L'en-tête de ce fichier disait :

  > « Les fusionner supposerait de trancher ce que “modifier une publication”
  >   doit permettre — c'est une question de produit, pas de refactorisation. »

  Le cadre l'a tranchée : **l'édition corrige**, donc elle propose les sections 1
  à 8 comme la création, et **seule la Diffusion tombe** (motif `geste`).

  ## Ce qui n'est PAS gouverné par `modeEdition`

  Aucune section. `avecPerimetre`, `avecPhotos`… passent tous par
  `sectionPresente(PUBLICATION, etat, …)`, et `npm run lint:etats` refuse qu'on
  remette une condition en dur. La seule chose que le mode décide encore ici est
  le **geste** : `POST` ou `PATCH`, et le bouton « Annuler ».

  ## ⚠️ La danse « créer puis attacher » n'a lieu QU'À LA CRÉATION

  Les documents d'une actualité deviennent des entités `Document` rattachées à un
  `publication_id` qui n'existe pas encore : ils sont retenus, la publication est
  créée en brouillon, ils sont téléversés, puis la publication est publiée — pour
  que l'affiche de hall les voie. Ce contournement **n'a aucun sens en édition**
  (la publication existe), et la déclaration l'empêche plutôt que de le rejouer :
  la section Documents y est absente, motif `api` citant #390.

  ⚠️ **Le moment du téléversement porte une fonctionnalité, pas une ergonomie**, et
  **ça ne se voit pas à l'écran** : quand les photos étaient téléversées après, le
  courriel était déjà construit et partait sans elles, sans que rien ne le
  signale. Toute retouche ici se vérifie sur un envoi réel.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { attacherAPublication } from '$lib/fichiers';
	import FormulaireCreation from '$lib/components/FormulaireCreation.svelte';
	import Modale from '$lib/components/Modale.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import ChampsCommuns from '$lib/components/ChampsCommuns.svelte';
	import DocumentsPublication from '$lib/components/DocumentsPublication.svelte';
	import OptionsPublication from '$lib/components/OptionsPublication.svelte';
	import DiffusionPublication from '$lib/components/DiffusionPublication.svelte';
	import { toast } from '$lib/components/Toast.svelte';
	import { publications as pubsApi, ApiError, type Publication } from '$lib/api';
	import { perimetreDefautListe } from '$lib/utils';
	import { richEmpty } from '$lib/publications';
	import type { Etat } from '$lib/entites/types';
	import { sectionPresente } from '$lib/entites/types';
	import { PUBLICATION } from '$lib/entites/publication';

	/**  La publication à MODIFIER, avec ses valeurs déjà saisies. `null` (défaut)
	 *   = création. Le mode ne change pas pendant la vie du composant : l'appelant
	 *   la remonte à neuf (`{#key}`) quand il passe d'une publication à l'autre,
	 *   exactement comme il le fait pour `EvolForm`. Même contrat que
	 *   `FormulaireTicket` (#425). */
	export let publication: Publication | null = null;

	const modeEdition = publication !== null;

	/**  L'état du cadre #430 que ce formulaire rend. C'est LUI qui décide des
	 *   sections — voir `$lib/entites/publication`, qui porte chaque divergence
	 *   avec son motif. */
	const etat: Etat = modeEdition ? 'edition' : 'creation';

	const dispatch = createEventDispatcher<{
		cree: Publication;
		modifie: Publication;
		annule: void;
	}>();

	//  ── 1. Titre ────────────────────────────────────────────────────────────
	let titre = publication?.titre ?? '';

	//  ── 2. Champs spécifiques : ce qui DÉCRIT la publication ────────────────
	let epingle = publication?.epingle ?? false;
	//  Épinglage à l'ouverture : sans lui, l'avertissement de plafond compterait
	//  une seconde fois une publication déjà épinglée.
	const epingleInitial = publication?.epingle ?? false;
	let urgente = publication?.urgente ?? false;
	let brouillon = publication?.brouillon ?? false;
	let confidentiel = publication?.confidentiel ?? false;

	//  ⚠️ PLUS DE WORKFLOW — arbitré le 18/08/2026. Une actualité n'a pas d'étapes
	//  de vie : elle est publiée, puis bascule dans l'Historique au bout de son
	//  délai. Le `statut` n'est donc plus envoyé du tout — ni à la création, ni à
	//  la correction —, et la colonne garde sa valeur d'origine pour les anciennes
	//  publications (la carte l'affiche encore, en lecture).

	//  ── 4 à 8 ───────────────────────────────────────────────────────────────
	//  Copie défensive du périmètre et du public : les tableaux viennent de la
	//  publication affichée dans la liste. Liés tels quels, une sélection
	//  abandonnée resterait visible sur la carte alors que rien n'a été enregistré.
	let perimetreCible: string[] = [...(publication?.perimetre_cible ?? perimetreDefautListe())];
	let publicCible: string[] = [...(publication?.public_cible ?? ['résidents'])];
	let contenu = publication?.contenu ?? '';
	//  Les photos sont téléversées AVANT l'enregistrement (endpoint générique),
	//  comme pour les tickets et les événements : leurs URLs partent dans la
	//  charge utile. C'est ce qui permet au courriel de partir AVEC elles.
	//  Rechargées en édition : `PATCH` remplace la liste entière — partir d'un
	//  tableau vide effacerait les photos existantes au premier enregistrement,
	//  silencieusement, et sans qu'on ait touché à la section.
	let photos: string[] = [...(publication?.photos_urls ?? [])];
	//  Les DOCUMENTS restent différés à la CRÉATION : ils deviennent des entités
	//  `Document` rattachées à `publication_id`, qui n'existe pas encore.
	let pendingFiles: File[] = [];

	//  ✅ EN CORRECTION, la publication existe : on ajoute et on retire à l'unité,
	//  tout de suite. C'est ce qui a permis de rouvrir la section sans attendre
	//  #390 — il n'a jamais été nécessaire de « remplacer la liste ».

	//  ── 9. Diffusion ────────────────────────────────────────────────────────
	//  ✅ Rouverte à l'édition (18/08/2026). Les cases reprennent les valeurs
	//  enregistrées — « telle qu'à la création ». Ce qui rend la réouverture sûre
	//  vit côté serveur : seule la transition décoché → coché envoie.
	let partagerWhatsapp = publication?.partager_whatsapp ?? false;
	let envoyerSyndic = publication?.envoyer_syndic ?? false;
	let envoyerCs = publication?.envoyer_cs ?? false;
	//  « Envoyer une copie à … » — la case vit dans `CanauxNotification`, qui
	//  porte la règle et son pourquoi. Elle s'affichait ici sans être lue (31/08).
	let envoyerAuteur = false;

	//  Les quatre canaux, écrits UNE fois pour les trois charges utiles de cet
	//  écran — la règle et son pourquoi : `SectionDiffusion.svelte`.
	$: canaux = {
		partager_whatsapp: partagerWhatsapp,
		envoyer_syndic: envoyerSyndic,
		envoyer_cs: envoyerCs,
		envoyer_auteur: envoyerAuteur,
	};

	let annonceHall = publication?.annonce_hall ?? false;

	//  ⚠️ La règle « Confidentiel interdit l'affiche de hall » enjambe les sections
	//  2 et 9 : elle vit donc ici, seul endroit où les deux valeurs se rencontrent.
	//  Elle est **aussi** tenue côté serveur (`appliquer_confidentialite`), qui
	//  seul décide — celle-ci n'est qu'un confort d'écran.
	$: if (confidentiel && annonceHall) annonceHall = false;

	let saving = false;

	//  L'aperçu de ce qui partira, avant de confirmer (#498). Il compose par les
	//  MÊMES fonctions que l'envoi — voir `publications/apercu.py`.
	//
	//  🔴 Cet écran n'en avait pas. Le 31/08/2026, une actualité est partie au
	//  conseil syndical sans que son auteur ait rien pu voir ni annuler. Le point
	//  d'accroche existait pourtant depuis le 29/08 : ce qui manquait était
	//  l'endpoint, et le contexte du gabarit que l'envoi construisait chez lui.
	//  🔴 Sans ces deux-là, `demanderApercu` ne sert À RIEN : la modale sait
	//  s'ouvrir, et personne ne l'ouvre. C'est l'erreur du 31/08/2026 — le
	//  pourquoi est dans `scripts/check-apercu-branche.mjs`, qui la refuse.
	let refDiffusion: any = null;
	$: aUneDiffusion = envoyerSyndic || envoyerCs || partagerWhatsapp;

	const brouillonApercu = () =>
		pubsApi.apercuDiffusion({
			publication_id: publication?.id,
			titre: titre.trim(),
			contenu,
			urgente,
			perimetre_cible: perimetreCible,
			photos_urls: photos,
			...canaux,
		});

	const titreBoite = modeEdition ? 'Modifier la publication' : 'Nouvelle publication';

	//  LE CADRE dépend du geste — `ux-patterns` §14 bis, qui porte la règle et
	//  son pourquoi : boîte pour créer, modale pour corriger, et le cadre se pose
	//  là où le geste est connu. Ici, c'est `modeEdition`.
	//
	//  ⚠️ En édition, ce composant ne vit plus dans la carte : elle ne le rendait
	//  que dépliée, et replier pendant la saisie aurait effacé la fenêtre AVEC la
	//  saisie. `encadre` est parti avec le problème qu'il corrigeait (#425).

	function reinitialiser() {
		titre = '';
		contenu = '';
		urgente = false;
		epingle = false;
		brouillon = false;
		partagerWhatsapp = false;
		envoyerSyndic = false;
		envoyerCs = false;
		annonceHall = false;
		confidentiel = false;
		perimetreCible = perimetreDefautListe();
		publicCible = ['résidents'];
		photos = [];
		pendingFiles = [];
	}

	/**  Aperçu d'abord si un canal est coché — même patron que `FormulaireTicket`,
	 *   qui en porte le pourquoi. `enregistrer` reste l'unique chemin d'écriture. */
	function soumettre() {
		if (!titre.trim() || richEmpty(contenu)) return;
		if (refDiffusion?.ouvrirSiDiffusion(aUneDiffusion)) return;
		void enregistrer();
	}

	async function enregistrer() {
		if (!titre.trim() || richEmpty(contenu)) return;
		refDiffusion?.fermerApercu();
		saving = true;
		try {
			if (publication) {
				//  Tout ce que la déclaration rend en édition, et rien d'autre : les
				//  canaux ne sont pas renvoyés (section 9 absente, motif `geste`), les
				//  documents pas non plus (motif `api`, #390).
				const maj = await pubsApi.update(publication.id, {
					titre: titre.trim(),
					contenu,
					epingle,
					urgente,
					brouillon,
					confidentiel,
					perimetre_cible: perimetreCible,
					public_cible: publicCible,
					photos_urls: photos,
					...canaux,
					annonce_hall: annonceHall,
				});
				toast('success', 'Publication mise à jour');
				dispatch('modifie', maj);
				return;
			}

			//  Restent les DOCUMENTS, encore persistés en entités `Document` propres
			//  aux publications (les tickets et les événements utilisent
			//  `fichiers_urls`) — eux seuls imposent de publier après coup, pour que
			//  l'affiche de hall les voie. Divergence connue, suivie en #390.
			const publierApresDocuments = !brouillon && annonceHall && pendingFiles.length > 0;
			let pub = await pubsApi.create({
				titre: titre.trim(),
				contenu,
				urgente,
				epingle,
				perimetre_cible: perimetreCible,
				public_cible: publicCible,
				brouillon: publierApresDocuments ? true : brouillon,
				photos_urls: photos,
				...canaux,
				annonce_hall: annonceHall,
				confidentiel,
			});
			//  Un échec ici ne doit pas perdre la publication déjà créée.
			try {
				await attacherAPublication(pub.id, pendingFiles);
			} catch {
				/* la publication existe : le document se rattrape depuis l'écran */
			}
			if (publierApresDocuments) {
				pub = await pubsApi.update(pub.id, { brouillon: false });
			}
			toast('success', pub.brouillon ? 'Brouillon enregistré' : 'Publication créée');
			reinitialiser();
			dispatch('cree', pub);
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			saving = false;
		}
	}
</script>

<!--
	Un seul montage du formulaire, deux cadres possibles. `svelte:component` est
	ce qui permet d'écrire le corps UNE fois — deux branches `{#if}` en feraient
	deux copies de deux cents lignes, qui divergeraient au premier champ ajouté.

	🔒 `Modale` est nommée DANS le `this={…}` : c'est ce que `lint:formulaires`
	lit. Un cadre choisi dans une variable compile aussi bien et sort la modale du
	champ du contrôle.
-->
<svelte:component
	this={modeEdition ? Modale : FormulaireCreation}
	titre={titreBoite}
	{...modeEdition ? { edition: true } : {}}
	on:fermer={() => dispatch('annule')}
>
	<div class:modal-body={modeEdition}>
		<form on:submit|preventDefault={soumettre}>
			<!--  1. Titre. -->
			<SectionFormulaire premiere>
				<div class="field champ-large">
					<label for="pub-titre-{publication?.id ?? 'new'}">Titre *</label>
					<input
						id="pub-titre-{publication?.id ?? 'new'}"
						type="text"
						bind:value={titre}
						required
						maxlength="200"
					/>
				</div>
			</SectionFormulaire>

			<!--  2. Champs spécifiques — ce qui DÉCRIT la publication. Ces quatre
		      options vivaient dans la Diffusion : les y laisser les aurait fait
		      disparaître de l'édition, et publier un brouillon serait devenu
		      impossible (le crayon ✏️ est le seul chemin qui le permette). Aucune
		      n'est un acte — voir `$lib/entites/publication`. -->
			{#if sectionPresente(PUBLICATION, etat, 'specifiques')}
				<SectionFormulaire titre="Options de publication">
					<OptionsPublication
						{perimetreCible}
						dejaEpingle={epingleInitial}
						bind:epingle
						bind:urgente
						bind:brouillon
						bind:confidentiel
					/>
				</SectionFormulaire>
			{/if}

			<!--  4 à 9 : l'ordre, les intitulés et les séparations viennent du
		      composant partagé — voir `ChampsCommuns.svelte`. Aucune de ces
		      sections n'est gouvernée par `modeEdition` : elles le sont par la
		      DÉCLARATION, qui porte chaque divergence avec son motif. -->
			<ChampsCommuns
				demanderApercu={brouillonApercu}
				bind:refDiffusion
				envoiEnCours={saving}
				on:envoyer={() => void enregistrer()}
				idPrefixe="pub-{publication?.id ?? 'new'}"
				avecPerimetre={sectionPresente(PUBLICATION, etat, 'perimetre')}
				bind:perimetre={perimetreCible}
				avecDestinataires={sectionPresente(PUBLICATION, etat, 'destinataires')}
				bind:destinataires={publicCible}
				avecDescription={sectionPresente(PUBLICATION, etat, 'description')}
				descriptionRequise
				bind:description={contenu}
				descriptionPlaceholder="Contenu de l'actualité…"
				avecPhotos={sectionPresente(PUBLICATION, etat, 'photos')}
				bind:photos
				avecDocuments={sectionPresente(PUBLICATION, etat, 'documents')}
				documentsDifferes
				documentsControle={modeEdition ? 'slot' : 'interne'}
				bind:documentsFichiers={pendingFiles}
				avecDiffusion={sectionPresente(PUBLICATION, etat, 'diffusion')}
				bind:whatsapp={partagerWhatsapp}
				bind:syndic={envoyerSyndic}
				bind:cs={envoyerCs}
				bind:auteur={envoyerAuteur}
				auteurNom={publication?.auteur_nom ?? ''}
				aideWhatsapp={confidentiel
					? "Le groupe est commun à toute la copropriété : le message ne portera ni le titre ni le contenu, seulement le périmètre concerné et un lien vers l'application."
					: "Le message est publié sur le groupe WhatsApp ; l'image jointe part avec."}
			>
				<!--  ✅ EN CORRECTION, les documents s'ajoutent et se retirent à l'unité :
			      la publication existe, il n'y a rien à différer. Le contrôle vient
			      d'ici parce que ce sont des entités `Document` avec un identifiant ;
			      la SECTION, elle — son rang, son intitulé, sa séparation — reste
			      celle de `ChampsCommuns`. -->
				<svelte:fragment slot="documents">
					{#if publication}
						<DocumentsPublication publicationId={publication.id} />
					{/if}
				</svelte:fragment>

				<!--  🔴 Les canaux appartiennent à l'OBJET, plus à cet écran (#498).
			      Ce commentaire disait « les actualités rendent leurs canaux
			      elles-mêmes : l'affiche de hall n'est pas un canal, et
			      `CanauxNotification` ne saurait pas la porter ». La prémisse est
			      juste — l'affiche n'est pas un canal —, la conclusion ne l'était
			      pas : sa place est le créneau `options` de `SectionDiffusion`,
			      qui existe pour ça. Rendre les canaux ici obligeait à passer
			      `avecCanaux={false}`, et les actualités se retrouvaient DANS
			      l'objet avec des canaux qui le contournaient. -->
				<svelte:fragment slot="diffusion">
					<DiffusionPublication {confidentiel} bind:annonceHall />
				</svelte:fragment>
			</ChampsCommuns>

			<!--  Le bouton « Annuler » n'existe qu'en ÉDITION : en création, la commande
		      vit dans l'en-tête de page, où le bouton d'ouverture bascule en
		      « ✕ Annuler » — deux commandes pour un formulaire est le défaut relevé
		      sur la modale du calendrier (#367). Même contrat que `FormulaireTicket`. -->
			<!--  « Annuler » est À CÔTÉ d'« Enregistrer », dans les deux gestes — norme
		      posée sur Tickets le 18/08/2026, constatée, puis étendue ici.
		      ⚠️ Corollaire : l'en-tête de page ne porte plus « ✕ Annuler » quand le
		      formulaire est ouvert (#367 — deux commandes pour un seul formulaire). -->
			<div class="form-actions">
				<button type="button" class="btn btn-outline" on:click={() => dispatch('annule')}
					>Annuler</button
				>
				<button type="submit" class="btn btn-primary" disabled={saving}>
					{saving ? 'Enregistrement…' : 'Enregistrer'}
				</button>
			</div>
		</form>
	</div>
</svelte:component>

<style>
</style>
