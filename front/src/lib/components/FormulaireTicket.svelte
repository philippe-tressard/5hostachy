<!--
  Le formulaire d'une AFFAIRE — actualités comprises —, celui qu'on remplit pour
  la CRÉER et celui qu'on rouvre pour la MODIFIER. Un seul fichier, deux gestes.

  ## 🔴 UN SEUL FORMULAIRE depuis le 23/09/2026 (arbitré à l'écran, maquette à l'appui)

  > « Sur la page, il y a deux nouveaux boutons : Affaires et Actualités. J'en veux
  >   qu'un seul “+ Nouvelle affaire” comprenant toutes les sections Affaires et
  >   Actualités, avec une nouvelle catégorie Actualité qui apparaît en premier.
  >   Selon le choix de la catégorie, les sections peuvent changer. Prévoir toutes
  >   les sections, grisées, pliées et inactives pour celles inappropriées. »

  `FormulaireActualite` a disparu dans celui-ci. « Actualité » est la première
  pastille de la catégorie (pleine ligne, puis un filet — variante A). La NATURE
  qu'elle décide — informer ou faire traiter — éteint des sections : Suivi,
  Équipement et Intervenant pour une actualité, Destinataires pour une affaire
  suivie. Elles restent à leur rang, grisées, avec leur motif, et ce qu'elles
  portaient ne part pas. La règle vit dans `$lib/formulaire-affaire` (et le motif
  dans la déclaration `TICKET`), pas en `{#if}` ici : la même question se pose à
  l'affichage et à l'envoi.

  ## Pourquoi il sert aussi l'édition (17/08/2026, #425)

  > « je préfère que tu rendes paramétrable avec les valeurs déjà saisies le
  >   formulaire d'édition plutôt que de le dupliquer »

  D'où la prop `ticket` : `null` = création, une affaire = correction. La
  catégorie s'y corrige aussi — c'est ainsi qu'une affaire devient une actualité
  ou l'inverse —, et ce qui s'efface alors est annoncé avant d'enregistrer.

  ⚠️ « Annuler » est À CÔTÉ d'« Enregistrer », dans les deux gestes : la page ne
  porte plus de « ✕ Annuler » quand le formulaire est ouvert (#367).
-->
<script lang="ts">
	import { pourChampLocal } from '$lib/date';
	import { contexteAssistant, perimetreContexte } from '$lib/assistant';
	import { createEventDispatcher, onMount } from 'svelte';
	import { perimetreDefautListe } from '$lib/perimetres';
	import {
		tickets as ticketsApi,
		admin as adminApi,
		prestataires as prestatairesApi,
		ApiError,
		type Ticket,
	} from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import FormulaireCreation from '$lib/components/FormulaireCreation.svelte';
	import SectionTitre from '$lib/components/SectionTitre.svelte';
	import SectionsSpecifiquesTicket from '$lib/components/SectionsSpecifiquesTicket.svelte';
	import ChampsCommuns from '$lib/components/ChampsCommuns.svelte';
	import DiffusionPublication from '$lib/components/DiffusionPublication.svelte';
	import RepriseAnnonceHall from '$lib/components/RepriseAnnonceHall.svelte';
	import SectionIntervenant from '$lib/components/SectionIntervenant.svelte';
	import ChampFrequence from '$lib/components/ChampFrequence.svelte';
	import { essayer } from '$lib/chargement';
	import { pliageDe } from '$lib/pliage';
	import type { PrefillActualite } from '$lib/actualite-prefill';
	import { isCS } from '$lib/stores/auth';
	import {
		CATEGORIE_ACTUALITE,
		OPTIONS_CATEGORIE,
		optionsCategorie,
		OPTIONS_TICKET,
		STATUT_TICKET_LABELS,
		TICKET_CONFIDENTIEL_ACQUIS,
		optionsDuTicket,
	} from '$lib/tickets';
	import type { Etat } from '$lib/entites/types';
	import { sectionPresente } from '$lib/entites/types';
	import { TICKET } from '$lib/entites/ticket';
	import { PUBLICATION } from '$lib/entites/publication';
	import { motifWhatsappInterdit } from '$lib/options-publication';
	import { reserveAuConseil } from '$lib/destinataires';
	import { confirmer } from '$lib/confirmation';
	import {
		CATEGORIE_ENTRETIEN,
		chargeUtileAffaire,
		intervenantPropose,
		natureDe,
		pertesAuChangement,
		sectionsInactives,
		type SaisieAffaire,
	} from '$lib/formulaire-affaire';
	import PiedFormulaire from '$lib/components/PiedFormulaire.svelte';
	import { comparerParNom } from '$lib/noms';
	import { nomCopie, saisieDepuis } from '$lib/saisi-pour';

	/**  L'affaire à MODIFIER, avec ses valeurs déjà saisies. `null` (défaut) =
	 *   création. Le mode ne change pas pendant la vie du composant : l'appelant le
	 *   remonte à neuf (`{#key}`) quand il passe d'une affaire à l'autre. */
	export let ticket: Ticket | null = null;

	/**  Ce qui RAMÈNE le formulaire à l'écran quand il est rendu loin du geste
	 *   qui l'ouvre — relayé jusqu'à `FormulaireCreation` (`check-geste-edition`,
	 *   règle F, 13/09/2026). */
	export let cle: unknown = undefined;

	const modeEdition = ticket !== null;

	/**  L'état du cadre #430 que ce formulaire rend : c'est LUI qui décide des
	 *   sections, via `sectionPresente(TICKET, etat, …)` — `lint:etats` refuse
	 *   qu'une condition en dur les gouverne. */
	const etat: Etat = modeEdition ? 'edition' : 'creation';

	const dispatch = createEventDispatcher<{ cree: Ticket; modifie: Ticket; annule: void }>();

	let titre = ticket?.titre ?? '';
	let description = ticket?.description ?? '';
	//  Section « Quand » (#1092) : une date fait paraître l'affaire au calendrier.
	let debut = pourChampLocal(ticket?.debut);
	let fin = pourChampLocal(ticket?.fin);
	//  Vrai dès qu'une proposition de l'assistant IA a été appliquée (#985).
	let assisteIA = false;
	//  🔴 AUCUNE catégorie présélectionnée (21/09/2026) : un défaut qui engage
	//  quelqu'un d'autre n'est pas un défaut, c'est une réponse qu'on n'a pas donnée.
	let categorie = ticket?.categorie ?? '';
	let statut = ticket?.statut ?? 'ouvert';
	//  Les options, reprises de l'affaire : le pont écran ⇄ objet vit dans
	//  `$lib/tickets` (`brouillon` écrit `confidentiel`, `urgente` la priorité).
	let options = optionsDuTicket(ticket);
	//  Copies défensives : les tableaux viennent de la carte affichée, et une
	//  sélection abandonnée y resterait visible sans avoir été enregistrée.
	let perimetreCible: string[] = [...(ticket?.perimetre_cible ?? perimetreDefautListe())];
	//  Ce qu'une ACTUALITÉ ajoute (#1091, #1096) : à qui l'on parle, l'Accès 🔒
	//  sous le Périmètre, l'affiche de hall.
	let publicCible: string[] = [...(ticket?.public_cible ?? ['résidents'])];
	let reservePerimetre = ticket?.reserve_perimetre ?? false;
	let annonceHall = false;
	//  La DIFFUSION reprend les valeurs enregistrées ; seule la transition
	//  décoché → coché envoie, et c'est le serveur qui le décide (14/08/2026).
	let destinataireSyndic = ticket?.destinataire_syndic ?? false;
	let destinataireCs = ticket?.destinataire_cs ?? false;
	let envoyerAuteur = false;
	//  Un ACTE, pas une colonne : la case repart décochée à chaque ouverture.
	let partagerWhatsapp = false;
	//  Téléversés dès leur sélection, avant l'enregistrement : c'est ce qui permet
	//  au courriel et à l'affiche de partir AVEC eux. Rechargés en correction :
	//  `PATCH` remplace la liste entière.
	let photosUrls: string[] = [...(ticket?.photos_urls ?? [])];
	let fichiersUrls: string[] = [...(ticket?.fichiers_urls ?? [])];
	let error = '';
	let loading = false;
	//  « Au nom de » (CS/admin) — la saisie vit dans `ChampSaisiPour`.
	let saisiPour = saisieDepuis(ticket);
	let usersActifs: { id: number; prenom: string; nom: string; email: string }[] = [];
	//  Section « Intervenant » et récurrence d'un Entretien (#1092, lot 5).
	let prestataireId: number | null = ticket?.prestataire_id ?? null;
	let equipement = ticket?.equipement ?? '';
	let contrats: {
		actif?: boolean;
		type_equipement?: string | null;
		prestataire_id?: number | null;
	}[] = [];
	let frequenceType = ticket?.frequence_type ?? '';
	let frequenceValeur: number | string | null = ticket?.frequence_valeur ?? null;
	let prestataires: { id: number; nom: string; actif?: boolean }[] = [];
	let erreurPrestataires = '';

	//  ── Ce que la NATURE décide (formulaire unique, 23/09/2026) ─────────────
	$: nature = natureDe(categorie);
	$: actualite = nature === 'actualite';
	$: inactives = sectionsInactives(etat, categorie, $isCS);
	$: reserveeAuConseil = actualite && reserveAuConseil(publicCible);
	//  Une actualité réservée — au périmètre ou au conseil — n'a pas d'affiche.
	$: if ((reservePerimetre || reserveeAuConseil) && annonceHall) annonceHall = false;
	$: assistant = contexteAssistant(actualite ? 'actualité' : 'ticket', {
		Catégorie: OPTIONS_CATEGORIE.find((o) => o.val === categorie)?.label ?? categorie,
		Périmètre: perimetreContexte(perimetreCible),
		...(actualite ? {} : { État: STATUT_TICKET_LABELS[statut] ?? statut }),
	});

	//  L'équipement PROPOSE l'intervenant sous contrat (#1097) — seulement quand
	//  il vient de changer et qu'aucun n'est désigné : une proposition, jamais
	//  un remplacement.
	let equipementVu = equipement;
	$: if (equipement !== equipementVu) {
		equipementVu = equipement;
		if (prestataireId === null)
			prestataireId = intervenantPropose(equipement, contrats, prestataires);
	}

	onMount(async () => {
		if ($isCS && sectionPresente(TICKET, etat, 'intervenant')) {
			[prestataires, erreurPrestataires] = await essayer(prestatairesApi.list(), []);
			//  Pour PROPOSER l'intervenant sous contrat (#1097) — sans eux, rien n'est proposé.
			[contrats] = await essayer(prestatairesApi.contrats(), []);
		}
		if ($isCS && sectionPresente(TICKET, etat, 'au_nom_de')) {
			try {
				const all = await adminApi.utilisateurs();
				usersActifs = all.filter((u: any) => u.actif).sort(comparerParNom);
			} catch {
				/* ignore */
			}
		}
	});

	//  Le pré-remplissage depuis une affiche de hall (#832) produit une actualité.
	//  Ce n'est pas une présélection (`lint:choix-requis`) : c'est la réponse au
	//  geste « reprendre cette affiche », que le conseil vient de faire.
	function appliquerReprise(p: PrefillActualite) {
		({ titre, description } = p);
		photosUrls = p.photos;
		perimetreCible = p.perimetreCible;
		categorie = CATEGORIE_ACTUALITE;
	}

	const richEmpty = (html: string) => !html || html.replace(/<[^>]+>/g, '').trim() === '';

	/** Tout ce qui a été saisi — la charge utile en est dérivée (`$lib/formulaire-affaire`). */
	$: saisie = {
		titre,
		description,
		assisteIA,
		categorie,
		statut,
		options,
		perimetreCible,
		publicCible,
		reservePerimetre,
		debut,
		fin,
		photosUrls,
		fichiersUrls,
		destinataireSyndic,
		destinataireCs,
		partagerWhatsapp,
		envoyerAuteur,
		annonceHall,
		saisiPour,
		prestataireId,
		equipement,
		frequenceType,
		frequenceValeur,
	} satisfies SaisieAffaire;

	//  ── L'aperçu avant diffusion (#498) — il compose avec le gabarit de la
	//  NATURE (le serveur choisit `publication_syndic` pour une actualité).
	$: aUneDiffusion = destinataireSyndic || destinataireCs || partagerWhatsapp;
	let refDiffusion: any = null;
	const brouillonApercu = () =>
		ticketsApi.apercuDiffusion({
			ticket_id: ticket?.id,
			titre: titre.trim(),
			description,
			categorie,
			urgente: options.urgente,
			public_cible: actualite ? publicCible : undefined,
			perimetre_cible: perimetreCible,
			photos_urls: photosUrls,
			fichiers_urls: fichiersUrls,
			destinataire_syndic: destinataireSyndic,
			destinataire_cs: destinataireCs,
			partager_whatsapp: partagerWhatsapp,
			envoyer_auteur: envoyerAuteur,
		});

	//  Le vocabulaire vient des DÉCLARATIONS (#1107). Une actualité n'affiche pas
	//  de numéro ; une affaire suivie le garde, c'est ce qui la distingue.
	$: titreBoite = !modeEdition
		? actualite
			? PUBLICATION.libelleNouveau
			: TICKET.libelleNouveau
		: estActualiteAvant
			? PUBLICATION.libelleModifier
			: `${TICKET.libelleModifier} #${ticket?.numero ?? ''}`;
	const estActualiteAvant = natureDe(ticket?.categorie ?? '') === 'actualite';
	//  « Actualité » est réservée au conseil. Son AUTEUR peut la corriger
	//  (`peut_editer`), mais pas la convertir : c'est un geste de modération, et
	//  une affaire suivie ouverte par lui repartirait sans état. Il ne voit donc
	//  que la sienne — la taire laisserait une catégorie cochée invisible.
	const optionsCat =
		!$isCS && estActualiteAvant
			? OPTIONS_CATEGORIE.filter((o) => o.val === 'actualite')
			: optionsCategorie($isCS);

	/** Contrôles de saisie — communs à la soumission directe et à l'aperçu. */
	function saisieValide(): boolean {
		if (!titre.trim() || richEmpty(description)) {
			error = 'Titre et description sont obligatoires.';
			return false;
		}
		//  Déclarée `requis` : l'exiger à l'écran et laisser le serveur en poser
		//  une à notre place serait le plus trompeur des deux.
		if (!categorie) {
			error = 'Choisissez une catégorie : c’est elle qui décide de qui traite.';
			return false;
		}
		if ($isCS && saisiPour.mode === 'exterieur' && !saisiPour.nom.trim()) {
			error = 'Veuillez saisir le nom de la personne.';
			return false;
		}
		error = '';
		return true;
	}

	/**  Le geste de soumission : aperçu d'abord si un canal est coché. `submit`
	 *   reste l'unique chemin d'enregistrement. */
	function soumettre() {
		if (!saisieValide()) return;
		if (!modeEdition && refDiffusion?.ouvrirSiDiffusion(aUneDiffusion)) return;
		void submit();
	}

	async function submit() {
		if (!saisieValide()) return;
		refDiffusion?.fermerApercu();
		const contexte = { creation: !modeEdition, estCS: $isCS };
		if (ticket) {
			//  🔴 Changer de nature EFFACE ce que les sections éteintes portaient :
			//  on le dit avant, et rien ne part sans accord (arbitré le 23/09/2026).
			const pertes = pertesAuChangement(ticket, saisie);
			if (
				pertes.length &&
				!(await confirmer({
					titre: actualite ? 'En faire une actualité' : 'En faire une affaire suivie',
					message: `Ce changement de catégorie efface ${pertes.join(', ')}.`,
					libelleConfirmer: 'Enregistrer',
				}))
			)
				return;
		}
		loading = true;
		try {
			const charge = chargeUtileAffaire(saisie, contexte);
			if (ticket) {
				const maj = await ticketsApi.update(ticket.id, charge);
				toast('success', `${actualite ? PUBLICATION.libelle : TICKET.libelle} modifiée`);
				dispatch('modifie', maj);
				return;
			}
			const t = await ticketsApi.create(charge);
			toast(
				'success',
				actualite ? `${PUBLICATION.libelle} publiée` : `${TICKET.libelle} ${t.numero} créée`,
			);
			dispatch('cree', t);
		} catch (e) {
			error =
				e instanceof ApiError
					? e.message
					: modeEdition
						? 'Erreur lors de l’enregistrement'
						: 'Erreur lors de la création';
		} finally {
			loading = false;
		}
	}
</script>

<!--  L'avertissement n'est rendu qu'en CRÉATION d'une affaire suivie : c'est
      l'envoi qui notifie. Il suit la case « Urgent » (#820), qui pose
      `priorite = haute` — pour le résident aussi, désormais. -->
{#if !modeEdition && !actualite && options.urgente}
	<div class="alert alert-error largeur-saisie" style="margin-bottom:1rem">
		&#x1F6A8; <strong>Urgent</strong> — Le conseil syndical et le syndic seront notifiés
		immédiatement. En cas de danger immédiat, composez le
		<strong>15 (SAMU), 17 (Police) ou 18 (Pompiers)</strong>.
	</div>
{/if}

{#if error}
	<div class="alert alert-error largeur-saisie">{error}</div>
{/if}

<FormulaireCreation titre={titreBoite} encadre={!modeEdition} {cle}>
	<form on:submit|preventDefault={soumettre}>
		<!--  Le pré-remplissage depuis une affiche vient AVANT le titre : c'est un
		      raccourci qui REMPLIT le formulaire, pas une section de l'entité. Il
		      produit une actualité — le conseil seul la publie. -->
		{#if $isCS}
			<RepriseAnnonceHall {modeEdition} on:reprise={(e) => appliquerReprise(e.detail)} />
		{/if}

		<SectionTitre
			id="titre"
			bind:valeur={titre}
			placeholder="Ex : Ascenseur bâtiment A en panne"
			maxlength={200}
		/>

		<!--  2 et 3 — Catégorie (« Actualité » en tête), Équipement, Suivi : ce
		      que l'affaire a de PROPRE. Les sections éteintes par la nature y sont
		      rendues grisées, à leur rang. -->
		<SectionsSpecifiquesTicket
			{etat}
			OPTIONS_CATEGORIE={optionsCat}
			{modeEdition}
			{inactives}
			bind:categorie
			bind:statut
			bind:options
			bind:equipement
		/>

		<!--  4 à 13 : ordre, intitulés et séparations hérités de `ChampsCommuns`,
		      gouvernés par la DÉCLARATION (`lint:etats`). Ce qui change avec la
		      nature — les options rendues, la case 🔒, les Destinataires, l'affiche
		      — se lit sur `actualite`, dérivée de la catégorie. -->
		<ChampsCommuns
			entite={TICKET}
			{inactives}
			bind:refDiffusion
			demanderApercu={brouillonApercu}
			envoiEnCours={loading}
			on:envoyer={() => void submit()}
			idPrefixe="ticket"
			avecSaisiPour={$isCS && sectionPresente(TICKET, etat, 'au_nom_de')}
			residentsSaisiPour={usersActifs}
			bind:saisiPour
			avecOptions={sectionPresente(TICKET, etat, 'mise_en_avant')}
			objet={actualite ? 'actualité' : 'ticket'}
			optionsRendues={!$isCS ? ['urgente'] : actualite ? ['epingle', 'urgente'] : OPTIONS_TICKET}
			confidentielAcquis={TICKET_CONFIDENTIEL_ACQUIS}
			dejaEpingle={ticket?.epingle ?? false}
			bind:epingle={options.epingle}
			bind:urgente={options.urgente}
			bind:brouillon={options.brouillon}
			avecQuand={sectionPresente(TICKET, etat, 'quand')}
			bind:debut
			bind:fin
			quandAutreValeur={!!frequenceType}
			avecPerimetre={sectionPresente(TICKET, etat, 'perimetre')}
			bind:perimetre={perimetreCible}
			avecReservePerimetre={$isCS && actualite}
			bind:reservePerimetre
			avecDestinataires={$isCS && sectionPresente(TICKET, etat, 'destinataires')}
			bind:destinataires={publicCible}
			avecDescription={sectionPresente(TICKET, etat, 'description')}
			avecNotificationCs
			descriptionRequise
			bind:description
			{assistant}
			bind:titreObjet={titre}
			bind:assisteIA
			descriptionPlaceholder={actualite
				? 'Contenu de l’actualité…'
				: 'Décrivez le problème avec le maximum de détails (localisation, depuis quand, fréquence…)'}
			avecPhotos={sectionPresente(TICKET, etat, 'pieces_jointes')}
			bind:photos={photosUrls}
			avecDocuments={sectionPresente(TICKET, etat, 'pieces_jointes')}
			bind:documents={fichiersUrls}
			avecDiffusion={$isCS && sectionPresente(TICKET, etat, 'diffusion')}
			bind:whatsapp={partagerWhatsapp}
			bind:syndic={destinataireSyndic}
			bind:cs={destinataireCs}
			bind:auteur={envoyerAuteur}
			auteurNom={nomCopie(ticket)}
			aideWhatsapp={actualite && reservePerimetre
				? 'Le groupe est commun à toute la copropriété : le message portera le titre et le périmètre, avec un lien vers l’application — jamais le contenu.'
				: 'Le message est publié sur le groupe WhatsApp ; les photos jointes partent avec.'}
			whatsappInterdit={motifWhatsappInterdit(
				actualite ? reserveeAuConseil : options.brouillon,
				actualite ? 'actualité' : 'ticket',
			)}
		>
			<!--  L'affiche de hall n'est pas un canal : c'est l'option d'une ACTUALITÉ,
			      rendue dans le créneau de la Diffusion (#498). -->
			<!--  6. Intervenant, et la récurrence d'un Entretien dans « Quand » :
			      rendus à LEUR rang par `ChampsCommuns`, qui les grise quand la
			      déclaration les éteint (hors bâti, résident, actualité). -->
			<svelte:fragment slot="intervenant">
				{#if sectionPresente(TICKET, etat, 'intervenant')}
					<SectionIntervenant
						idPrefixe="ticket"
						bind:prestataires
						{equipement}
						erreur={erreurPrestataires}
						pliable={pliageDe(TICKET, 'intervenant')}
						bind:prestataireId
					/>
				{/if}
			</svelte:fragment>
			<svelte:fragment slot="quand">
				{#if $isCS && categorie === CATEGORIE_ENTRETIEN}
					<ChampFrequence idPrefixe="ticket-frequence" bind:frequenceType bind:frequenceValeur />
				{/if}
			</svelte:fragment>
			<svelte:fragment slot="diffusion">
				{#if actualite}
					<DiffusionPublication reservee={reservePerimetre || reserveeAuConseil} bind:annonceHall />
				{/if}
			</svelte:fragment>
		</ChampsCommuns>

		<PiedFormulaire enCours={loading} on:annule />
	</form>
</FormulaireCreation>
