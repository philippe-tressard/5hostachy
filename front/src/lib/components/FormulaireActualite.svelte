<!--
  Le formulaire d'une actualité — celui qu'on remplit pour la CRÉER, et celui
  qu'on rouvre pour la MODIFIER. Un seul fichier pour les deux gestes.

  ## 🔴 Une actualité EST une affaire depuis le 23/09/2026 (#1091, lot 4)

  Ce formulaire écrit par `POST /tickets` et `PATCH /tickets/{id}`, catégorie
  « Actualité ». Il reste distinct de `FormulaireTicket` parce que ce qu'il
  PROPOSE diffère — à qui l'on parle, l'Accès 🔒, l'affiche de hall, pas de
  catégorie à choisir ni de suivi —, pas parce que l'objet diffère : ce qui
  varie est déclaré dans `$lib/entites/publication`, pas ici.

  | Actualité (avant) | Affaire « Actualité » |
  |---|---|
  | `contenu` | `description` |
  | `urgente` | `urgente` → `priorite` (serveur) |
  | 🛡️ `brouillon` | Destinataires = « Conseil syndical » seul (#1096) |
  | 🔒 `confidentiel` | `reserve_perimetre`, sous les pastilles du Périmètre |
  | documents = entités `Document`, attachées APRÈS | `fichiers_urls`, téléversés AVANT, comme une affaire |

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

  ## ✅ La danse « créer puis attacher » a disparu avec l'entité

  Les documents d'une publication étaient des entités `Document` rattachées à
  un `publication_id` qui n'existait pas encore : créer en brouillon, attacher,
  puis publier, pour que l'affiche de hall les voie. Une affaire porte ses
  documents en `fichiers_urls`, téléversés AVANT l'enregistrement — ils partent
  donc avec le courriel et l'affiche, sans détour. Les `Document` des anciennes
  publications restent lisibles sur la carte.
-->
<script lang="ts">
	import { pourChampLocal, depuisChampLocal } from '$lib/date';
	import { contexteAssistant, perimetreContexte } from '$lib/assistant';
	import { createEventDispatcher, onMount } from 'svelte';
	import CadreFormulaire from '$lib/components/CadreFormulaire.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import ChampsCommuns from '$lib/components/ChampsCommuns.svelte';
	import {
		chargerResidents,
		lotDepuisSaisie,
		nomCopie,
		saisieDepuis,
		type ResidentProposable,
	} from '$lib/saisi-pour';
	import { admin as adminApi, tickets as ticketsApi, type Ticket } from '$lib/api';
	import { messageErreur } from '$lib/erreurs';
	import DiffusionPublication from '$lib/components/DiffusionPublication.svelte';
	import { toast } from '$lib/components/Toast.svelte';
	import RepriseAnnonceHall from '$lib/components/RepriseAnnonceHall.svelte';
	import type { PrefillActualite } from '$lib/actualite-prefill';
	import { perimetreDefautListe } from '$lib/utils';
	import { richEmpty } from '$lib/publications';
	import type { Etat } from '$lib/entites/types';
	import { sectionPresente } from '$lib/entites/types';
	import { PUBLICATION } from '$lib/entites/publication';
	import { motifWhatsappInterdit } from '$lib/options-publication';
	import { reserveAuConseil } from '$lib/destinataires';
	import { ticketUrgent } from '$lib/tickets';
	import { isCS } from '$lib/stores/auth';
	import PiedFormulaire from '$lib/components/PiedFormulaire.svelte';
	import EtoileRequis from '$lib/components/EtoileRequis.svelte';

	/**  L'actualité à MODIFIER, avec ses valeurs déjà saisies. `null` (défaut)
	 *   = création. Le mode ne change pas pendant la vie du composant : l'appelant
	 *   la remonte à neuf (`{#key}`) quand il passe d'une actualité à l'autre.
	 *   Même contrat que `FormulaireTicket` (#425). */
	export let affaire: Ticket | null = null;
	/**  Ce qui RAMÈNE le formulaire à l'écran quand il est rendu loin du geste qui
	 *   l'ouvre — relayé jusqu'à `CadreFormulaire` (`check-geste-edition`, règle F). */
	export let cle: unknown = undefined;

	//  ── Saisi pour — le CS publie parfois POUR quelqu'un (`$lib/saisi-pour`).
	let saisiPour = saisieDepuis(affaire);
	let residentsSaisiPour: ResidentProposable[] = [];

	const modeEdition = affaire !== null;

	/**  L'état du cadre #430 que ce formulaire rend. C'est LUI qui décide des
	 *   sections — voir `$lib/entites/publication`, qui porte chaque divergence
	 *   avec son motif. */
	const etat: Etat = modeEdition ? 'edition' : 'creation';

	const dispatch = createEventDispatcher<{
		cree: Ticket;
		modifie: Ticket;
		annule: void;
	}>();

	//  ── Pré-remplissage depuis une annonce de hall (#832) ───────────────
	//  Le raccourci vit dans `RepriseAnnonceHall` : ce n'est pas une section du
	//  cadre #430, donc il n'a pas sa place dans un écran qui rend des sections.
	function appliquerReprise(p: PrefillActualite) {
		({ titre, description, photos } = p);
		perimetreCible = p.perimetreCible;
	}

	onMount(async () => {
		residentsSaisiPour = await chargerResidents(adminApi.utilisateurs);
	});

	let titre = affaire?.titre ?? '';

	//  ── Mise en avant : épinglage et urgence, et plus rien d'autre (#1096).
	let epingle = affaire?.epingle ?? false;
	//  Épinglage à l'ouverture : sans lui, l'avertissement de plafond compterait
	//  une seconde fois une actualité déjà épinglée.
	const epingleInitial = affaire?.epingle ?? false;
	let urgente = ticketUrgent(affaire);
	//  🔒 L'Accès — sous les pastilles du Périmètre (#1096).
	let reservePerimetre = affaire?.reserve_perimetre ?? false;

	//  Copie défensive du périmètre et du public : les tableaux viennent de
	//  l'actualité affichée dans la liste. Liés tels quels, une sélection
	//  abandonnée resterait visible sur la carte alors que rien n'a été enregistré.
	let perimetreCible: string[] = [...(affaire?.perimetre_cible ?? perimetreDefautListe())];
	let publicCible: string[] = [...(affaire?.public_cible ?? ['résidents'])];
	let description = affaire?.description ?? '';
	//  Section « Quand » (#1092) : une actualité datée paraît au calendrier.
	let debut = pourChampLocal(affaire?.debut);
	let fin = pourChampLocal(affaire?.fin);
	//  Vrai dès qu'une proposition de l'assistant IA a été appliquée (#985).
	let assisteIA = false;
	//  🛡️ Destinataires = « Conseil syndical » seul : rien ne sort (#1096).
	$: reserveeAuConseil = reserveAuConseil(publicCible);
	$: assistant = contexteAssistant('actualité', {
		Périmètre: perimetreContexte(perimetreCible),
		Urgente: urgente,
		Épinglée: epingle,
		'Réservée au conseil syndical': reserveeAuConseil,
		'Réservée au périmètre': reservePerimetre,
	});
	//  Photos et documents sont téléversés AVANT l'enregistrement, comme pour
	//  toute affaire : leurs URLs partent dans la charge utile, donc avec le
	//  courriel et l'affiche. Rechargés en édition : `PATCH` remplace la liste
	//  entière, et partir d'un tableau vide effacerait l'existant en silence.
	let photos: string[] = [...(affaire?.photos_urls ?? [])];
	let fichiersUrls: string[] = [...(affaire?.fichiers_urls ?? [])];

	//  ── Diffusion — les cases de syndic et de conseil reprennent les valeurs
	//  enregistrées ; seule la transition décoché → coché envoie, et c'est le
	//  serveur qui en décide.
	let partagerWhatsapp = false;
	let envoyerSyndic = affaire?.destinataire_syndic ?? false;
	let envoyerCs = affaire?.destinataire_cs ?? false;
	//  « Envoyer une copie à … » — la case vit dans `CanauxNotification`.
	let envoyerAuteur = false;
	let annonceHall = false;

	//  Réservée — au périmètre ou au conseil —, l'actualité n'a pas d'affiche :
	//  un hall se lit sans connexion. Confort d'écran ; le serveur décide
	//  (`visibility.hors_du_hall`).
	$: reservee = reservePerimetre || reserveeAuConseil;
	$: if (reservee && annonceHall) annonceHall = false;

	//  Les canaux, écrits UNE fois pour les charges utiles de cet écran. Le
	//  conseil seul les envoie : l'auteur d'une annonce d'arrivée corrige son
	//  texte, il ne diffuse pas — le serveur le refuserait en 403.
	$: canaux = $isCS
		? {
				partager_whatsapp: partagerWhatsapp,
				destinataire_syndic: envoyerSyndic,
				destinataire_cs: envoyerCs,
				envoyer_auteur: envoyerAuteur,
				annonce_hall: annonceHall,
			}
		: {};

	let saving = false;

	//  L'aperçu de ce qui partira, avant de confirmer (#498) — celui des
	//  affaires, qui compose une actualité avec SON gabarit.
	let refDiffusion: any = null;
	$: aUneDiffusion = envoyerSyndic || envoyerCs || partagerWhatsapp;

	const brouillonApercu = () =>
		ticketsApi.apercuDiffusion({
			ticket_id: affaire?.id,
			titre: titre.trim(),
			description,
			categorie: 'actualite',
			urgente,
			perimetre_cible: perimetreCible,
			public_cible: publicCible,
			photos_urls: photos,
			fichiers_urls: fichiersUrls,
			destinataire_syndic: envoyerSyndic,
			destinataire_cs: envoyerCs,
			partager_whatsapp: partagerWhatsapp,
			envoyer_auteur: envoyerAuteur,
		});

	//  Le vocabulaire d'écran vient de la DÉCLARATION (#1107).
	const titreBoite = modeEdition ? PUBLICATION.libelleModifier : PUBLICATION.libelleNouveau;

	/**  Aperçu d'abord si un canal est coché — même patron que `FormulaireTicket`.
	 *   `enregistrer` reste l'unique chemin d'écriture. */
	function soumettre() {
		if (!titre.trim() || richEmpty(description)) return;
		if (refDiffusion?.ouvrirSiDiffusion(aUneDiffusion)) return;
		void enregistrer();
	}

	async function enregistrer() {
		if (!titre.trim() || richEmpty(description)) return;
		refDiffusion?.fermerApercu();
		saving = true;
		const commun = {
			titre: titre.trim(),
			description,
			urgente,
			perimetre_cible: perimetreCible,
			debut: depuisChampLocal(debut),
			fin: depuisChampLocal(fin),
			photos_urls: photos,
			fichiers_urls: fichiersUrls,
			//  Le conseil seul décide qui lit — ignorés pour un autre par le serveur.
			...($isCS ? { epingle, public_cible: publicCible, reserve_perimetre: reservePerimetre } : {}),
			...canaux,
			...lotDepuisSaisie(saisiPour),
		};
		try {
			if (affaire) {
				const maj = await ticketsApi.update(affaire.id, {
					...commun,
					assiste_ia: assisteIA || undefined,
				});
				toast('success', `${PUBLICATION.libelle} mise à jour`);
				dispatch('modifie', maj);
				return;
			}
			const cree = await ticketsApi.create({
				...commun,
				categorie: 'actualite',
				assiste_ia: assisteIA,
			});
			toast('success', `${PUBLICATION.libelle} publiée`);
			dispatch('cree', cree);
		} catch (e: any) {
			toast('error', messageErreur(e));
		} finally {
			saving = false;
		}
	}
</script>

<!--
	Un seul montage du formulaire, deux cadres possibles — et le CHOIX du cadre
	n'est plus écrit ici. `CadreFormulaire` le porte pour les six formulaires qui
	en ont besoin : il s'y écrivait cinq fois, et les copies avaient commencé à
	diverger (02/09/2026).

	Ce qui reste ici : `edition`, qui déclare le GESTE. Ce n'est pas décoratif —
	`lint:formulaires` l'exige, et c'est lui qui distingue « créer » de
	« corriger », ce que rien dans le balisage ne permettrait de deviner.
-->
<CadreFormulaire
	edition={modeEdition}
	titre={titreBoite}
	{cle}
	on:fermer={() => dispatch('annule')}
>
	<!--  ⚠️ Plus de `class:modal-body` ici : `CadreFormulaire` enveloppe lui-même
	      le contenu sur la classe par défaut (02/09/2026). Le laisser en
	      poserait un SECOND, et le padding serait compté deux fois. -->
	<div>
		<form on:submit|preventDefault={soumettre}>
			<!--  L'EXCEPTION AU CADRE #430 : le pré-remplissage vient AVANT le
			      titre, comme dans `FormulaireAnnonceHall` — c'est un raccourci qui
			      REMPLIT le formulaire, pas une section de l'entité. -->
			<RepriseAnnonceHall {modeEdition} on:reprise={(e) => appliquerReprise(e.detail)} />

			<!--  1. Titre. -->
			<SectionFormulaire premiere>
				<div class="field champ-large">
					<label for="pub-titre-{affaire?.id ?? 'new'}">Titre<EtoileRequis vide={!titre} /></label>
					<input
						id="pub-titre-{affaire?.id ?? 'new'}"
						type="text"
						bind:value={titre}
						required
						maxlength="200"
					/>
				</div>
			</SectionFormulaire>

			<!--  3 à 10 : l'ordre, les intitulés et les séparations viennent du
		      composant partagé — voir `ChampsCommuns.svelte`. Aucune de ces
		      sections n'est gouvernée par `modeEdition` : elles le sont par la
		      DÉCLARATION, qui porte chaque divergence avec son motif.

		      ⚠️ Les OPTIONS y sont entrées le 12/09/2026. Elles étaient posées ici,
		      en section 2 — ce qui était juste pour une actualité, dont elles SONT
		      les champs spécifiques, et faux dès qu'un autre écran en a de vrais :
		      le rang de la section devenait alors une affaire d'écran. Il ne l'est
		      plus. -->
			<ChampsCommuns
				entite={PUBLICATION}
				avecSaisiPour
				{residentsSaisiPour}
				bind:saisiPour
				demanderApercu={brouillonApercu}
				bind:refDiffusion
				envoiEnCours={saving}
				on:envoyer={() => void enregistrer()}
				idPrefixe="pub-{affaire?.id ?? 'new'}"
				avecQuand={sectionPresente(PUBLICATION, etat, 'quand')}
				bind:debut
				bind:fin
				avecPerimetre={sectionPresente(PUBLICATION, etat, 'perimetre')}
				bind:perimetre={perimetreCible}
				avecReservePerimetre={$isCS}
				bind:reservePerimetre
				avecDestinataires={$isCS && sectionPresente(PUBLICATION, etat, 'destinataires')}
				bind:destinataires={publicCible}
				avecOptions={sectionPresente(PUBLICATION, etat, 'mise_en_avant')}
				optionsRendues={$isCS ? ['epingle', 'urgente'] : ['urgente']}
				dejaEpingle={epingleInitial}
				bind:epingle
				bind:urgente
				avecDescription={sectionPresente(PUBLICATION, etat, 'description')}
				descriptionRequise
				bind:description
				{assistant}
				bind:titreObjet={titre}
				bind:assisteIA
				descriptionPlaceholder="Contenu de l'actualité…"
				avecPhotos={sectionPresente(PUBLICATION, etat, 'pieces_jointes')}
				bind:photos
				avecDocuments={sectionPresente(PUBLICATION, etat, 'pieces_jointes')}
				bind:documents={fichiersUrls}
				avecDiffusion={$isCS && sectionPresente(PUBLICATION, etat, 'diffusion')}
				bind:whatsapp={partagerWhatsapp}
				bind:syndic={envoyerSyndic}
				bind:cs={envoyerCs}
				bind:auteur={envoyerAuteur}
				auteurNom={nomCopie(affaire)}
				whatsappInterdit={motifWhatsappInterdit(reserveeAuConseil, 'actualité')}
				aideWhatsapp={reservePerimetre
					? "Le groupe est commun à toute la copropriété : le message portera le titre et le périmètre, avec un lien vers l'application — jamais le contenu."
					: "Le message est publié sur le groupe WhatsApp ; l'image jointe part avec."}
			>
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
					<DiffusionPublication {reservee} bind:annonceHall />
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
			<PiedFormulaire enCours={saving} on:annule />
		</form>
	</div>
</CadreFormulaire>

<style>
</style>
