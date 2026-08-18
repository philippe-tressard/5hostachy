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
	import { createEventDispatcher, onMount } from 'svelte';
	import FormulaireCreation from '$lib/components/FormulaireCreation.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import ChampsCommuns from '$lib/components/ChampsCommuns.svelte';
	import OptionsPublication from '$lib/components/OptionsPublication.svelte';
	import DiffusionPublication from '$lib/components/DiffusionPublication.svelte';
	import { toast } from '$lib/components/Toast.svelte';
	import { publications as pubsApi, documents as docsApi, ApiError, type Publication } from '$lib/api';
	import { perimetreDefautListe } from '$lib/utils';
	import { richEmpty } from '$lib/publications';
	import { ACCEPT_DOCUMENTS, nomFichier } from '$lib/fichiers';
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

	const dispatch = createEventDispatcher<{ cree: Publication; modifie: Publication; annule: void }>();

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
	let docsExistants: { id: number; titre?: string; fichier_nom?: string }[] = [];
	let docsEnCours = false;

	onMount(async () => {
		if (!publication) return;
		try { docsExistants = await docsApi.listByPublication(publication.id); }
		catch { /* la section reste vide plutôt que de bloquer la correction */ }
	});

	async function ajouterDocuments(e: Event) {
		const input = e.target as HTMLInputElement;
		if (!publication || !input.files?.length) return;
		docsEnCours = true;
		try {
			for (const f of Array.from(input.files)) {
				const doc = await docsApi.uploadForPublication(f.name, publication.id, f);
				docsExistants = [...docsExistants, doc];
			}
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Téléversement impossible');
		} finally { docsEnCours = false; input.value = ''; }
	}

	async function retirerDocument(id: number) {
		if (!confirm('Retirer ce document de la publication ?')) return;
		try {
			await docsApi.delete(id);
			docsExistants = docsExistants.filter((d) => d.id !== id);
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Suppression impossible');
		}
	}

	//  ── 9. Diffusion ────────────────────────────────────────────────────────
	//  ✅ Rouverte à l'édition (18/08/2026). Les cases reprennent les valeurs
	//  enregistrées — « telle qu'à la création ». Ce qui rend la réouverture sûre
	//  vit côté serveur : seule la transition décoché → coché envoie.
	let partagerWhatsapp = publication?.partager_whatsapp ?? false;
	let envoyerSyndic = publication?.envoyer_syndic ?? false;
	let envoyerCs = publication?.envoyer_cs ?? false;
	let annonceHall = publication?.annonce_hall ?? false;

	//  ⚠️ La règle « Confidentiel interdit l'affiche de hall » enjambe les sections
	//  2 et 9 : elle vit donc ici, seul endroit où les deux valeurs se rencontrent.
	//  Elle est **aussi** tenue côté serveur (`appliquer_confidentialite`), qui
	//  seul décide — celle-ci n'est qu'un confort d'écran.
	$: if (confidentiel && annonceHall) annonceHall = false;

	let saving = false;

	$: titreBoite = modeEdition ? 'Modifier la publication' : 'Nouvelle publication';

	function reinitialiser() {
		titre = ''; contenu = ''; urgente = false; epingle = false;
		brouillon = false; partagerWhatsapp = false; envoyerSyndic = false;
		envoyerCs = false; annonceHall = false; confidentiel = false;
		perimetreCible = perimetreDefautListe();
		publicCible = ['résidents'];
		photos = [];
		pendingFiles = [];
	}

	async function enregistrer() {
		if (!titre.trim() || richEmpty(contenu)) return;
		saving = true;
		try {
			if (publication) {
				//  Tout ce que la déclaration rend en édition, et rien d'autre : les
				//  canaux ne sont pas renvoyés (section 9 absente, motif `geste`), les
				//  documents pas non plus (motif `api`, #390).
				const maj = await pubsApi.update(publication.id, {
					titre: titre.trim(), contenu,
					epingle, urgente, brouillon, confidentiel,
					perimetre_cible: perimetreCible,
					public_cible: publicCible,
					photos_urls: photos,
					//  Les canaux partent aussi : le serveur n'envoie que sur la
					//  TRANSITION décoché → coché, donc réenregistrer sans y toucher
					//  ne rejoue rien.
					partager_whatsapp: partagerWhatsapp,
					envoyer_syndic: envoyerSyndic,
					envoyer_cs: envoyerCs,
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
				titre: titre.trim(), contenu, urgente, epingle,
				perimetre_cible: perimetreCible, public_cible: publicCible,
				brouillon: publierApresDocuments ? true : brouillon,
				photos_urls: photos,
				partager_whatsapp: partagerWhatsapp,
				envoyer_syndic: envoyerSyndic,
				envoyer_cs: envoyerCs,
				annonce_hall: annonceHall,
				confidentiel,
			});
			if (pendingFiles.length > 0) {
				for (const f of pendingFiles) {
					try { await docsApi.uploadForPublication(f.name, pub.id, f); } catch { /* ignoré */ }
				}
			}
			if (publierApresDocuments) {
				pub = await pubsApi.update(pub.id, { brouillon: false });
			}
			toast('success', pub.brouillon ? 'Brouillon enregistré' : 'Publication créée');
			reinitialiser();
			dispatch('cree', pub);
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally { saving = false; }
	}
</script>

<FormulaireCreation titre={titreBoite} encadre={!modeEdition}>
	<form on:submit|preventDefault={enregistrer}>
		<!--  1. Titre. -->
		<SectionFormulaire premiere>
			<div class="field champ-large">
				<label for="pub-titre-{publication?.id ?? 'new'}">Titre *</label>
				<input id="pub-titre-{publication?.id ?? 'new'}" type="text"
					bind:value={titre} required maxlength="200" />
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
			idPrefixe="pub-{publication?.id ?? 'new'}"
			avecPerimetre={sectionPresente(PUBLICATION, etat, 'perimetre')} bind:perimetre={perimetreCible}
			avecDestinataires={sectionPresente(PUBLICATION, etat, 'destinataires')} bind:destinataires={publicCible}
			avecDescription={sectionPresente(PUBLICATION, etat, 'description')} descriptionRequise bind:description={contenu}
			descriptionPlaceholder="Contenu de l'actualité…"
			avecPhotos={sectionPresente(PUBLICATION, etat, 'photos')} bind:photos
			avecDocuments={sectionPresente(PUBLICATION, etat, 'documents')} documentsDifferes
			documentsControle={modeEdition ? 'slot' : 'interne'} bind:documentsFichiers={pendingFiles}
			avecDiffusion={sectionPresente(PUBLICATION, etat, 'diffusion')}
			avecCanaux={false}
		>
			<!--  ✅ EN CORRECTION, les documents s'ajoutent et se retirent à l'unité :
			      la publication existe, il n'y a rien à différer. Le contrôle vient
			      d'ici parce que ce sont des entités `Document` avec un identifiant ;
			      la SECTION, elle — son rang, son intitulé, sa séparation — reste
			      celle de `ChampsCommuns`. -->
			<svelte:fragment slot="documents">
					{#if docsExistants.length}
						<ul class="docs-liste">
							{#each docsExistants as doc (doc.id)}
								<li>
									<span class="docs-nom">📎 {doc.titre || nomFichier(doc.fichier_nom ?? '')}</span>
									<button type="button" class="btn-icon-danger" aria-label="Retirer ce document"
										title="Retirer ce document" on:click={() => retirerDocument(doc.id)}>🗑️</button>
								</li>
							{/each}
						</ul>
					{/if}
				<label class="btn btn-outline btn-sm docs-ajout">
					{docsEnCours ? 'Téléversement…' : '+ Ajouter un document'}
					<input type="file" multiple accept={ACCEPT_DOCUMENTS} disabled={docsEnCours}
						on:change={ajouterDocuments} />
				</label>
			</svelte:fragment>

			<!--  Les actualités rendent leurs canaux elles-mêmes : l'affiche de hall
			      n'est pas un canal de notification, et `CanauxNotification` ne
			      saurait pas la porter. -->
			<svelte:fragment slot="diffusion">
				<DiffusionPublication
					{confidentiel}
					bind:whatsapp={partagerWhatsapp}
					bind:syndic={envoyerSyndic}
					bind:cs={envoyerCs}
					bind:annonceHall
				/>
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
			<button type="button" class="btn btn-outline" on:click={() => dispatch('annule')}>Annuler</button>
			<button type="submit" class="btn btn-primary" disabled={saving}>
				{saving ? 'Enregistrement…' : 'Enregistrer'}
			</button>
		</div>
	</form>
</FormulaireCreation>

<style>
	/*  La liste des documents déjà joints, en correction. Elle porte son style ici,
	    avec le balisage qui l'utilise — un style laissé chez le parent n'atteint pas
	    le balisage d'un enfant (v2.67.11). */
	.docs-liste { list-style: none; margin: 0 0 .6rem; padding: 0; display: flex; flex-direction: column; gap: .3rem; }
	.docs-liste li { display: flex; align-items: center; gap: .4rem; font-size: .85rem; }
	.docs-nom { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
	.docs-ajout { display: inline-flex; cursor: pointer; }
	.docs-ajout input[type='file'] { display: none; }
</style>

