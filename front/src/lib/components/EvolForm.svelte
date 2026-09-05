<!--
  EvolForm.svelte — Formulaire partagé d'ajout/édition d'évolution
  Utilisé par : tickets/[id], tickets (liste), actualites, espace-cs

  ## Il suit l'ORDRE et les SECTIONS communes (`ux-patterns` §9 sexies et septies)

  Ce composant est antérieur aux règles posées les 15-17/08/2026, et n'avait été
  repris par aucun des lots qui les ont établies (#416) : la **Diffusion** était
  rendue AVANT les pièces jointes, aucune section n'était nommée, et le bouton de
  soumission disait « Valider » en création contre « Enregistrer » en édition —
  le même geste, deux libellés, dans la même ligne de code.

  L'ordre est désormais celui de tout le site — Workflow, Description, Photos,
  Documents, Diffusion en dernier. La liste n’est pas recopiée ici : elle vit
  dans `ux-patterns` §9 sexies, et deux versions divergeraient au premier lot.

  ## UN SEUL POINT D'ENTRÉE, ET LE GESTE SE LIT DANS LES PASTILLES (#426)

  Ce formulaire commençait par une rangée de deux pastilles — « 💬 Commentaire »
  et « 🔄 Changement d'état » — au-dessus d'un formulaire ouvert par un bouton
  💬 : l'utilisateur avait **déjà dit** ce qu'il voulait faire en cliquant, et la
  première pastille était un choix sans objet.

  > « le bouton commentaire n'a pas lieu d'être — il est présent sur le fil
  >   principal pour ouvrir un *nouveau commentaire* » (17/08/2026)

  Première tentative (18/08, matin) : deux boutons sur la carte, le geste figé
  par l'appelant. **Refusée à l'écran** — *« il manque le principal, la section
  Workflow avec les différentes pastilles »*.

  La forme retenue est plus simple, et c'est **UN** point d'entrée : le bouton 🔄
  ouvre le formulaire, dont la **section Workflow** porte les états en pastilles,
  **celle de l'état courant active**. Laisser la pastille telle quelle ne change
  rien : l'entrée est alors un commentaire. En choisir une autre fait avancer le
  suivi. Le même formulaire sert les deux gestes sans jamais les redemander, parce
  que **la réponse est déjà visible à l'écran**.

  C'est aussi ce qui supprime la question « et si je veux commenter ET changer
  l'état ? » : c'était déjà possible, mais il fallait le deviner.

  Les pièces jointes sont DEUX sections, jamais une (#433) : le mode unifié
  (`separatePhotosAndDocs`) a disparu le 18/08/2026 avec son dernier appelant.

  ✅ **Gouverné par la déclaration d'entité** (02/09/2026, #463) : il REÇOIT
  l'entité et lit `sectionPresente(…, 'evolution', …)` lui-même. Les cinq écrans
  ne décident plus des sections — seulement des DROITS de leur lecteur.

  ✅ **L'écart d'intitulé est levé (02/09/2026)** — arbitré : *« oui, unifier à
  commentaire »*. La description basculait « Commentaire » / « Contenu » selon le
  mode, là où R3 demande le MÊME libellé d'un formulaire à l'autre.

  ✅ **`SectionFormulaire` n'est plus employé ici** (02/09/2026, #463) : les
  sections 4, 6, 7-8 et 9 passent par les composants du cadre. L'ordre et les
  intitulés ne sont plus tenus par recopie. La raison invoquée jusqu'ici —
  « l'intitulé de `ChampsCommuns` est figé à Description » — était tombée le
  matin même.

  Les props sont documentées UNE fois, chacune à sa déclaration : cette liste-ci
  les recopiait, et deux listes divergent au premier ajout.

  Événements :
    submit(data)  – {type, contenu, nouveau_statut?, fichiers_urls, partager_whatsapp?, envoyer_syndic?, envoyer_cs?, email_externe?}
    cancel        – fermer le formulaire sans sauvegarder
-->
<script lang="ts">
	import SectionWorkflow from '$lib/components/SectionWorkflow.svelte';
	import SectionDescription from '$lib/components/SectionDescription.svelte';
	import { createEventDispatcher } from 'svelte';
	import SectionDiffusion from '$lib/components/SectionDiffusion.svelte';
	import SectionsPiecesJointes from '$lib/components/SectionsPiecesJointes.svelte';
	import FormulaireCreation from '$lib/components/FormulaireCreation.svelte';
	import SectionsCiblageEvolution from '$lib/components/SectionsCiblageEvolution.svelte';
	import { sectionPresente, type EntiteDeclaree } from '$lib/entites/types';
	import type { ApercuDiffusion } from '$lib/api';
	import { separerFichiers } from '$lib/fichiers';
	import { perimetreEntree, perimetreHerite } from '$lib/perimetres';

	// ── Props ─────────────────────────────────────────────────────────────────
	/** Préfixe des `id` des champs. Plusieurs formulaires d'évolution coexistent à
	    l'écran — le formulaire d'ajout d'une carte et l'édition d'une évolution du
	    même fil —, et deux `<label for="…">` pointant le même id ne désignent plus
	    rien. Même contrat que `ChampsCommuns`. */
	export let idPrefixe = 'evol';
	/**  CE QUE L'ON EST EN TRAIN DE FAIRE, écrit en toutes lettres (18/08/2026).
	 *
	 *   Ce formulaire était le SEUL du site sans en-tête : `FormulaireTicket` et
	 *   `FormulaireActualite` passent par `FormulaireCreation`, qui leur donne un
	 *   titre. Ici, le mode devait se deviner à partir de l'icône cliquée trois
	 *   secondes plus tôt — signalé à l'écran : *« on ne sait pas si on est en
	 *   mode édition, en mode suivi »*. R1 dit que le squelette porte
	 *   *en-tête · corps · pied* : un formulaire sans nom viole le cadre. */
	export let titre = 'Commenter';
	/** Options affichées dans le select "Nouvel état" */
	export let statutOptions: { value: string; label: string }[] = [];
	/** Map value→label pour afficher le statut actuel */
	export let statutLabels: Record<string, string> = {};
	/** Statut actuel de l'objet parent (badge à droite de l'intitulé) */
	export let currentStatut = '';
	/** Afficher les cases de partage (WhatsApp / syndic / CS) */
	/**  🔴 L'ENTITÉ dont ce fil est le quatrième état (#463) : c'est ELLE qui dit
	 *   quelles sections existent, plus les cinq écrans chacun de son côté (trois
	 *   recopiaient `sectionPresente(TICKET, 'evolution', …)`, deux passaient `true`
	 *   en dur — les valeurs coïncidaient, d'où l'invisibilité de la divergence).
	 *
	 *   ⚠️ La déclaration dit ce qui EXISTE, jamais ce que CET utilisateur a le
	 *   droit de faire : les trois props ci-dessous portent cela et restent chez
	 *   l'appelant, seul à connaître le lecteur. Les mêler aurait fait décider d'un
	 *   droit par une déclaration de forme. */
	export let entite: EntiteDeclaree;
	/**  Un DROIT, pas une section : `$isCS` sur la fiche, l'auteur sur sa carte. */
	export let peutDiffuser = true;
	/**  Même nature : préciser le périmètre change qui verra l'objet. */
	export let peutPreciserPerimetre = true;
	/**  Une variante du GESTE, pas de la section — R4 ne sait pas la déclarer
	 *   (#436) : faux sur une note interne, ligne de suivi et non signalement. */
	export let avecPiecesJointes = true;
	/** Valeurs par défaut des notifications */
	export let defaultPartagerWhatsapp = false;
	export let defaultEnvoyerSyndic = false;
	export let defaultEnvoyerCs = false;
	/** Afficher le champ email externe */
	export let showEmail = false;
	/**  Proposer « Message interne ». C'est une décision de DIFFUSION — qui voit
	     cette entrée —, donc elle est rendue en section 9, avec les canaux, et
	     non au milieu du commentaire comme le faisait le formulaire de réponse
	     écrit à la main de la fiche d'un ticket (#431). */
	export let avecInterne = false;
	/** Lié par le parent : lui seul sait ce qu'une entrée interne change chez lui. */
	export let interne = false;
	/**
	 * Section 7 — Photos. Séparée de la 8 le 28/08/2026 (#463) : une prop
	 * unique ouvrait les DEUX sections d'un coup, ce que le cadre interdit
	 * (« une section ne se fusionne JAMAIS avec une autre »). Un écran ne
	 * pouvait donc pas déclarer les Photos présentes et les Documents absents.
	 */
	/** Mode édition : masque le statut, pré-remplit contenu+fichiers */
	export let editMode = false;
	/** Contenu initial (mode édition) */
	export let initialContenu = '';
	/** Fichiers initiaux (mode édition) */
	export let initialFichiers: { url: string; nom: string; type?: string }[] = [];

	/**  Le périmètre que l'entrée AVAIT déclaré, en correction. Vide si elle n'en
	 *   déclarait aucun — le sélecteur part alors de l'hérité, comme en saisie. */
	export let initialPerimetre: string[] = [];
	/** Le ciblage en vigueur et son aide — voir `SectionsCiblageEvolution`. */
	export let initialDestinataires: string[] = [];
	export let aidePerimetre = '';
	/**  Le périmètre de l’objet, et l’historique déjà écrit : ensemble ils donnent
	 *   celui dont cette entrée HÉRITE (`perimetreHerite`) — badge et point de
	 *   départ du sélecteur, calculés une seule fois pour ne pas en montrer deux. */
	export let perimetreCourant: string[] = [];
	export let entrees: { perimetre_cible?: string[] | null }[] = [];
	/**  Comment demander l'aperçu de ce qui partira — `null` = pas d'aperçu ici.
	 *
	 *   🔴 Fournie par l'APPELANT, jamais codée ici : ce formulaire sert quatre
	 *   écrans (ticket, actualité, calendrier, espace CS), et chacun compose son
	 *   message avec ses propres modèles. Un aperçu écrit ici ne pourrait montrer
	 *   qu'un seul des quatre — donc mentir sur les trois autres.
	 *
	 *   ⚠️ AJOUTÉ le 19/08/2026 après un signalement : l'aperçu n'existait qu'à la
	 *   création d'un ticket, et l'utilisateur l'a découvert en COMMENTANT — case
	 *   « envoyer au syndic » cochée, rien ne s'est ouvert. Une fonctionnalité
	 *   livrée à moitié ne se lit pas « la suite arrive », elle se lit « cassée »,
	 *   et c'est la lecture juste du côté de l'écran. */
	export let demanderApercu:
		| ((saisie: {
				contenu: string;
				fichiers_urls: string[];
				whatsapp: boolean;
				syndic: boolean;
				cs: boolean;
		  }) => Promise<ApercuDiffusion>)
		| null = null;
	/** Contrôlé par le parent : est-ce que la sauvegarde API est en cours */
	/**  Le nom de l'auteur de l'OBJET commenté, jamais celui du commentaire —
	 *   la règle vit dans `CanauxNotification.svelte`. */
	export let auteurNom = '';

	export let saving = false;

	// ── Events ────────────────────────────────────────────────────────────────
	const dispatch = createEventDispatcher<{
		submit: {
			type: 'commentaire' | 'etat';
			contenu: string;
			nouveau_statut?: string;
			fichiers_urls: string[];
			partager_whatsapp?: boolean;
			envoyer_syndic?: boolean;
			envoyer_cs?: boolean;
			envoyer_auteur?: boolean;
			email_externe?: string;
			interne?: boolean;
			perimetre_cible?: string[];
		};
		cancel: void;
	}>();

	// ── State ─────────────────────────────────────────────────────────────────
	let contenu = initialContenu;
	let nouveauStatut = '';
	let evolType: 'commentaire' | 'etat' = 'commentaire';
	let partagerWhatsapp = defaultPartagerWhatsapp;
	let envoyerSyndic = defaultEnvoyerSyndic;
	let envoyerCs = defaultEnvoyerCs;
	let envoyerAuteur = false;
	let emailExterne = '';
	//  Pré-rempli avec l’hérité (31/08/2026) — voir `perimetreHerite`.
	let perimetre: string[] =
		editMode && initialPerimetre.length
			? [...initialPerimetre]
			: perimetreHerite(perimetreCourant, entrees);
	//  Repli sur le défaut du site : une liste vide serait un effacement.
	let destinataires: string[] = initialDestinataires.length
		? [...initialDestinataires]
		: ['résidents'];

	//  7. Photos · 8. Documents — DEUX sections, jamais une seule (cadre #430).
	//  Le tri vient de `$lib/fichiers` : c'est une règle de FICHIERS, pas de
	//  formulaire — et elle y était déjà, sous le nom `separerFichiers`.
	const heritees = separerFichiers(editMode ? initialFichiers.map((f) => f.url) : []);
	let photos: string[] = heritees.photos;
	let docs: string[] = heritees.documents;

	// ── Helpers ───────────────────────────────────────────────────────────────

	const richEmpty = (html: string) => !html || html.replace(/<[^>]+>/g, '').trim() === '';

	$: allFichiersUrls = [...photos, ...docs];

	//  Sections visibles. La PREMIÈRE section rendue ne porte pas de filet
	//  au-dessus : un trait avant le premier groupe le séparerait du titre du
	//  formulaire, qui joue déjà ce rôle (`SectionFormulaire`).
	//  La section Workflow n'existe que pour le geste qui la concerne, et
	//  seulement s'il y a un état à proposer : un choix à un seul choix n'est pas
	//  un choix. Elle ne porte plus la NATURE de l'entrée — c'est l'appelant qui
	//  la décide (#426).
	$: sectionWorkflow = !editMode && statutOptions.length > 0;
	//  🔴 LE PÉRIMÈTRE SE CORRIGE AUSSI (01/09/2026, à l'écran) :
	//
	//  > *« L'édition peut modifier le périmètre (correction d'erreur
	//  > d'affectation d'un périmètre) »*
	//
	//  Cette ligne valait `avecPerimetre && !editMode`, au motif que « préciser
	//  est un geste de SUIVI, qui raturerait un fait daté en réécrivant une
	//  entrée passée » — et le serveur refusait le champ en PATCH, ce qui
	//  fermait la question.
	//
	//  Le motif vaut pour un RESSERREMENT, pas pour une faute de clic. Et la
	//  faute coûte cher : le périmètre d'une entrée écrase celui du ticket,
	//  donc une erreur d'affectation reclasse tout le ticket.
	//
	//  ⚠️ Côté serveur, la correction ne se propage à l'objet que si l'entrée
	//  corrigée est la dernière à avoir précisé quelque chose
	//  (`app/utils/perimetre_fil.py`) : corriger une vieille entrée ne défait
	//  pas une précision récente.
	//  🔴 Chaque ligne combine ce qui EXISTE (la déclaration) et ce que cet
	//  utilisateur-ci PEUT (le droit) — jamais l'un à la place de l'autre (#463).
	$: sectionPerimetre = peutPreciserPerimetre && sectionPresente(entite, 'evolution', 'perimetre');
	//  Ouvertes par la DÉCLARATION de l'entité — voir `SectionsCiblageEvolution`.
	$: sectionDestinataires = sectionPresente(entite, 'evolution', 'destinataires');
	$: sectionSpecifiques = sectionPresente(entite, 'evolution', 'specifiques');
	$: sectionPhotos = avecPiecesJointes && sectionPresente(entite, 'evolution', 'photos');
	$: sectionDocuments = avecPiecesJointes && sectionPresente(entite, 'evolution', 'documents');
	$: sectionDiffusion = peutDiffuser && sectionPresente(entite, 'evolution', 'diffusion');

	//  L'état actuel se lit en BADGE à droite de l'intitulé, pas en ligne de texte
	//  sous lui (`ux-patterns` §9 quater) — c'est la forme qu'a déjà la carte du
	//  ticket, deux centimètres plus haut.
	$: libelleStatutActuel = currentStatut ? statutLabels[currentStatut] || currentStatut : '';

	//  Le périmètre COURANT en badge, même forme que l'état courant deux lignes
	//  plus haut : on voit d'où l'on part avant de préciser. `ChampsCommuns`
	//  n'affiche le badge que sur le périmètre par défaut, parce que le sélecteur
	//  montre déjà la sélection ; ici le sélecteur part vide, donc le badge est le
	//  SEUL endroit où l'on lit le périmètre actuel — il est toujours affiché.
	//
	//  Le calcul lui-même vit dans `$lib/perimetres` : il parle de périmètre, pas
	//  de formulaire (extrait le 31/08/2026, sur refus de modularité).
	//  ⚠️ Des affectations plutôt qu'une déstructuration réactive : ESLint 10
	//  plante sur `$: ({a, b} = f())` (@typescript-eslint/no-unused-vars). Le
	//  contournement est ici, pas dans une règle désactivée.
	$: entreePerimetre = perimetreEntree(perimetreCourant, entrees, perimetre, sectionPerimetre);
	$: perimetreDeclare = entreePerimetre.declare;
	$: libellePerimetreActuel = entreePerimetre.libelleActuel;

	//  Le commentaire est REQUIS pour une évolution de type commentaire, facultatif
	//  quand il accompagne un changement d'état. Pas de mention « (optionnel) » :
	//  l'absence d'astérisque suffit (`ux-patterns` §9).
	//  🔴 L'INTITULÉ NE BASCULE PLUS (voir l'en-tête). « Commentaire » et non
	//  « Description » : c'est le mot d'un auteur sur un fil, pas le corps d'un objet.
	const titreContenu = 'Commentaire';
	//  🔴 LE GESTE EST DÉDUIT, il ne se déclare plus. Une pastille laissée sur
	//  l'état courant ne change rien : l'entrée est un commentaire. En choisir une
	//  autre en fait un changement d'état. C'est ce qui permet UN seul point
	//  d'entrée — la question « lequel des deux ? » a déjà sa réponse à l'écran.
	$: evolType =
		!editMode && nouveauStatut && nouveauStatut !== currentStatut ? 'etat' : 'commentaire';
	//  Le commentaire est REQUIS quand l'entrée n'apporte que lui : sans texte ni
	//  changement d'état, l'entrée ne dirait rien.
	$: contenuRequis = !editMode && evolType === 'commentaire';

	//  Une entrée vaut si elle apporte quelque chose : un changement d'état, un
	//  texte, ou une pièce jointe. Rien des trois → rien à enregistrer.
	$: canSubmit =
		!saving && (evolType === 'etat' || !(richEmpty(contenu) && allFichiersUrls.length === 0));

	// Le téléversement lui-même vit dans `FichiersUpload` : trois copies de la
	// même fonction (photo, document, fichier unifié) ne différaient que par la
	// liste alimentée.

	// ── Aperçu avant diffusion (#498) ─────────────────────────────────────────
	//  Il ne s'interpose QUE si l'appelant sait le composer ET qu'un canal est
	//  coché : sans canal il n'y a rien à montrer, et une modale de plus serait
	//  une étape gratuite entre l'utilisateur et son commentaire.
	$: aUneDiffusion = sectionDiffusion && (partagerWhatsapp || envoyerSyndic || envoyerCs);
	//  🔴 La saisie est PASSÉE à l'appelant, elle n'est pas lue depuis l'extérieur.
	//  Ce formulaire tient son état ; une fermeture posée chez l'appelant lirait
	//  des valeurs vides — première tentative, corrigée avant d'être livrée.
	//  L'état et la modale vivent dans `SectionDiffusion` depuis le 20/08/2026 :
	//  l'aperçu appartient à l'objet Diffusion, pas à ses appelants (#498). Ne
	//  reste ici que la SAISIE à transmettre — ce formulaire seul la connaît.
	let refDiffusion: SectionDiffusion;
	const brouillonApercu = () => {
		if (!demanderApercu) throw new Error('Aperçu non disponible sur cet écran.');
		return demanderApercu({
			contenu,
			fichiers_urls: allFichiersUrls,
			whatsapp: partagerWhatsapp,
			syndic: envoyerSyndic,
			cs: envoyerCs,
		});
	};

	// ── Submit ────────────────────────────────────────────────────────────────
	function soumettre() {
		if (!canSubmit) return;
		if (refDiffusion?.ouvrirSiDiffusion(aUneDiffusion)) return;
		handleSubmit();
	}

	function handleSubmit() {
		if (!canSubmit) return;
		refDiffusion?.fermerApercu();
		dispatch('submit', {
			type: editMode ? 'commentaire' : evolType,
			contenu,
			nouveau_statut: !editMode && evolType === 'etat' ? nouveauStatut : undefined,
			fichiers_urls: allFichiersUrls,
			partager_whatsapp: sectionDiffusion ? partagerWhatsapp : undefined,
			envoyer_syndic: sectionDiffusion ? envoyerSyndic : undefined,
			envoyer_cs: sectionDiffusion ? envoyerCs : undefined,
			envoyer_auteur: sectionDiffusion ? envoyerAuteur : undefined,
			email_externe: showEmail ? emailExterne.trim() || undefined : undefined,
			interne: avecInterne ? interne : undefined,
			perimetre_cible: perimetreDeclare,
		});
	}
</script>

<!--  Même largeur de saisie que partout ailleurs (`ux-patterns` §9) : le
      formulaire s'étalait sur toute la carte, alors que le même geste sur une
      page dédiée s'arrête à 720 px. -->
<!--  Pas de cadre : ce formulaire s'ouvre DÉJÀ dans une carte, et deux bordures
      imbriquées pour un seul objet est le défaut signalé sur #425. Le titre,
      lui, reste — c'est lui qui dit ce qu'on fait. -->
<FormulaireCreation {titre} encadre={false}>
	<!-- ── 3. Workflow ───────────────────────────────────────────────────────
	     Plus de rangée de pastilles : le geste a été déclaré par le bouton qui a
	     ouvert ce formulaire (#426). Ne reste que ce qu'il faut encore préciser —
	     vers quel état. Le libellé porte l'état ACTUEL en badge, à droite
	     (`ux-patterns` §9 quater). -->
	{#if sectionWorkflow}
		<!--  Section à UN champ : le titre EST le libellé, et le sélecteur ne
		      réécrit rien (`ux-patterns` §9 septies). Même forme que la section
		      Workflow de `FormulaireTicket`, au mot près. -->
		<!--  🔴 PASTILLES, jamais un `<select>` nu (R3, #423). L'état COURANT est
		      actif à l'ouverture : on voit où en est l'objet, et en changer est un
		      clic. Laisser la pastille active telle quelle ne change rien — l'entrée
		      est alors un simple commentaire, et c'est ce qui permet de n'avoir
		      qu'UN point d'entrée sur la carte.
		      Section à un champ : le titre EST le libellé, et il porte l'état actuel
		      en badge (`ux-patterns` §9 septies et §9 quater). -->
		<SectionWorkflow
			premiere
			idTitre="{idPrefixe}-workflow-titre"
			options={statutOptions}
			valeur={nouveauStatut || currentStatut}
			badge={libelleStatutActuel}
			on:choisir={(e) => (nouveauStatut = e.detail)}
		/>
	{/if}

	<!--  2. Champs spécifiques — AVANT le ciblage : même ordre dans les quatre
	      états (cadre #430, R2). Le commentaire l'inversait (05/09/2026). -->
	{#if sectionSpecifiques}
		<slot name="specifiques" premiere={!sectionWorkflow} />
	{/if}

	<!--  4. Périmètre · 5. Destinataires — dans `SectionsCiblageEvolution`. -->
	<SectionsCiblageEvolution
		{idPrefixe}
		premiere={!sectionWorkflow && !sectionSpecifiques}
		avecPerimetre={sectionPerimetre}
		bind:perimetre
		perimetreBadge={libellePerimetreActuel}
		{aidePerimetre}
		avecDestinataires={sectionDestinataires}
		bind:destinataires
	/>

	<!-- ── 6. Description ───────────────────────────────────────────────────
	     Section à UN champ : le titre EST le libellé. Le rendu vient de
	     `SectionDescription`, écrit une fois pour ce composant et
	     `ChampsCommuns` (01/09/2026). -->
	<SectionDescription
		{idPrefixe}
		idChamp="contenu"
		premiere={!sectionWorkflow && !sectionSpecifiques && !sectionPerimetre && !sectionDestinataires}
		titre={titreContenu}
		requis={contenuRequis}
		hauteur="90px"
		placeholder={editMode
			? 'Modifier le commentaire…'
			: evolType === 'etat'
				? 'Précisions sur ce changement…'
				: 'Ajoutez un commentaire de suivi…'}
		bind:valeur={contenu}
	/>

	<!-- ── 7-8. Photos et Documents ─────────────────────────────────────────
	     ✅ Les pièces jointes ne dépendent PLUS du geste (18/08/2026). Une
	     condition héritée les fermait sur un changement d'état — sans qu'aucun
	     commit ni aucune issue n'en porte la raison, alors qu'une photo justifie
	     souvent un passage à « Résolu ».

	     Les deux sections viennent de `SectionsPiecesJointes` : elles étaient
	     écrites à l'identique ici et dans `ChampsCommuns` (01/09/2026). -->
	<SectionsPiecesJointes
		{idPrefixe}
		avecPhotos={sectionPhotos}
		bind:photos
		avecDocuments={sectionDocuments}
		bind:documents={docs}
		idDocuments="docs"
	/>

	<!-- ── 9. Diffusion — un OBJET du site, rendu partout pareil (#498) ─────
	     Arbitré à l'écran le 19/08/2026 : *« C'est une évolution sur l'objet
	     Diffusion, qu'il soit positionné sur n'importe quel formulaire. »* Le
	     bloc était écrit ici ET dans `ChampsCommuns` — deux écritures d'une même
	     notion, donc deux valeurs libres de diverger. -->
	<SectionDiffusion
		bind:this={refDiffusion}
		demanderApercu={demanderApercu ? brouillonApercu : null}
		envoiEnCours={saving}
		on:envoyer={handleSubmit}
		{idPrefixe}
		avecCanaux={sectionDiffusion}
		bind:whatsapp={partagerWhatsapp}
		bind:syndic={envoyerSyndic}
		bind:cs={envoyerCs}
		bind:auteur={envoyerAuteur}
		{auteurNom}
		avecEmailExterne={showEmail}
		bind:emailExterne
		{avecInterne}
		bind:interne
		fichiers={allFichiersUrls}
		compact
	/>

	<!-- ── Actions ──────────────────────────────────────────────────────────
	     `.form-actions` vient d'app.css : la disposition était recomposée ici en
	     ligne, aux mêmes valeurs, donc libre de diverger (`ux-patterns` §9
	     quinquies). Le verbe est GÉNÉRIQUE dans les deux modes — « Valider » /
	     « Envoi… » en création contre « Enregistrer » / « Enregistrement… » en
	     édition, c'était le même geste sous deux libellés (§9 quinquies bis). -->
	<div class="form-actions">
		<button type="button" class="btn btn-outline btn-sm" on:click={() => dispatch('cancel')}
			>Annuler</button
		>
		<button type="button" class="btn btn-primary btn-sm" disabled={!canSubmit} on:click={soumettre}>
			{saving ? 'Enregistrement…' : 'Enregistrer'}
		</button>
	</div>
</FormulaireCreation>

<!--  Aucun `<style>` : tout le rendu vient des composants montés ci-dessus, et
      chaque règle voyage avec le balisage qu'elle habille (v2.67.11). Les notes
      qui expliquaient l'absence de `.aide-bloc`, `.case-interne` et de la rangée
      de pastilles sont désormais dans les trois composants qui les portent. -->
