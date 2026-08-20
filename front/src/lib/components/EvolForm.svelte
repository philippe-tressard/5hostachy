<!--
  EvolForm.svelte — Formulaire partagé d'ajout/édition d'évolution
  Utilisé par : tickets/[id], tickets (liste), actualites, espace-cs

  ## Il suit l'ORDRE et les SECTIONS communes (`ux-patterns` §9 sexies et septies)

  Ce composant est antérieur aux règles posées les 15-17/08/2026, et n'avait été
  repris par aucun des lots qui les ont établies (#416) : la **Diffusion** était
  rendue AVANT les pièces jointes, aucune section n'était nommée, et le bouton de
  soumission disait « Valider » en création contre « Enregistrer » en édition —
  le même geste, deux libellés, dans la même ligne de code.

  L'ordre est désormais celui de tout le site :

    3. Workflow    →  cette entrée change-t-elle l'état, et vers quoi ?
    6. Description →  le commentaire
    7-8. Photos / Documents (ou Pièces jointes en mode unifié)
    9. Diffusion   →  message interne, canaux, adresse externe — EN DERNIER

  ## UN SEUL POINT D'ENTRÉE, ET LE GESTE SE LIT DANS LES PASTILLES (#426)

  Ce formulaire commençait par une rangée de deux pastilles — « 💬 Commentaire »
  et « 🔄 Changement d'état » — au-dessus d'un formulaire ouvert par un bouton
  💬 : l'utilisateur avait **déjà dit** ce qu'il voulait faire en cliquant, et la
  première pastille était un choix sans objet.

  > « le bouton commentaire n'a pas lieu d'être — il est présent sur le fil
  >   principal pour ouvrir un *nouveau commentaire* » (17/08/2026)

  Première tentative (18/08, matin) : deux boutons sur la carte, 💬 et 🔄, et le
  geste figé par l'appelant. **Refusée à l'écran le 18/08** — *« l'icône commenter
  est à retirer, devenue obsolète ; il manque le principal, la section Workflow
  avec les différentes pastilles »*.

  La forme retenue est plus simple, et c'est **UN** point d'entrée : le bouton 🔄
  ouvre le formulaire, dont la **section Workflow** porte les états en pastilles,
  **celle de l'état courant active**. Laisser la pastille telle quelle ne change
  rien : l'entrée est alors un commentaire. En choisir une autre fait avancer le
  suivi. Le même formulaire sert les deux gestes sans jamais les redemander, parce
  que **la réponse est déjà visible à l'écran**.

  C'est aussi ce qui supprime la question « et si je veux commenter ET changer
  l'état ? » : c'était déjà possible, mais il fallait le deviner.

  ## Les pièces jointes sont DEUX sections, jamais une (#433)

  Le mode « pièces jointes unifiées » (`separatePhotosAndDocs = false`) fusionnait
  les sections 7 et 8, ce que le cadre #430 interdit dans tous les rendus. Il a
  disparu le 18/08/2026, quand son dernier appelant l'a quitté : *une variante
  ajoutée pour accueillir un écart existant ne factorise pas, elle entérine*.

  ⚠️ **Ce composant n'est toujours pas gouverné par la déclaration d'entité**
  (`$lib/entites/`) : il sert quatre écrans, et l'état `evolution` est déclaré
  sans être encore confronté à son rendu. Un écart connu subsiste — l'intitulé de
  la description bascule « Commentaire » / « Contenu » selon le mode, là où R3
  demande le MÊME libellé d'un formulaire à l'autre.

  ⚠️ **Pourquoi `SectionFormulaire` et non `ChampsCommuns`.** `ChampsCommuns` est
  le point d'héritage des sections 4 à 9, et c'est lui qu'il faudrait utiliser —
  son intitulé de description est figé à « Description » là où l'évolution parle
  de « Commentaire ». Les sections sont donc composées ici avec
  `SectionFormulaire`, dans le MÊME ordre et avec les MÊMES intitulés que
  `ChampsCommuns` — toute évolution de l'un doit suivre dans l'autre.

  Props clés :
    statutOptions      – états proposables, rendus en pastilles (section Workflow)
    statutLabels       – map value→label pour afficher le statut actuel
    currentStatut      – statut actuel de l'item parent (badge du libellé)
    showNotifs         – afficher les cases WhatsApp/syndic/CS
    showEmail          – afficher le champ email externe
    showFiles          – afficher l'upload de fichiers
    editMode           – masque le statut, pré-remplit contenu+fichiers
    initialContenu     – contenu initial (mode édition)
    initialFichiers    – fichiers initiaux (mode édition)
    saving             – contrôlé par le parent (en cours de sauvegarde API)

  Événements :
    submit(data)  – {type, contenu, nouveau_statut?, fichiers_urls, partager_whatsapp?, envoyer_syndic?, envoyer_cs?, email_externe?}
    cancel        – fermer le formulaire sans sauvegarder
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import RichEditor from '$lib/components/RichEditor.svelte';
	import FichiersUpload from '$lib/components/FichiersUpload.svelte';
	import SectionDiffusion from '$lib/components/SectionDiffusion.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import FormulaireCreation from '$lib/components/FormulaireCreation.svelte';
	import Pastille from '$lib/components/Pastille.svelte';
	import PerimetrePicker from '$lib/components/PerimetrePicker.svelte';
	import type { ApercuDiffusion } from '$lib/api';
	import { ACCEPT_PHOTOS, estImage } from '$lib/fichiers';
	import { perimetreLabel, perimetreLabelUn, perimetreParDefaut } from '$lib/perimetres';

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
	export let showNotifs = false;
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
	/** Afficher l'upload de fichiers */
	export let showFiles = false;
	/** Mode édition : masque le statut, pré-remplit contenu+fichiers */
	export let editMode = false;
	/** Contenu initial (mode édition) */
	export let initialContenu = '';
	/** Fichiers initiaux (mode édition) */
	export let initialFichiers: { url: string; nom: string; type?: string }[] = [];
	/**  Proposer de PRÉCISER LE PÉRIMÈTRE dans cette entrée (#497).
	 *
	 *   Un ticket se signale avec ce qu'on sait au moment où on le signale — donc
	 *   souvent le périmètre le plus large, parce qu'on ignore encore d'où ça
	 *   vient. Puis on cherche : « bâtiment 2 » devient « bât. 2, 3ᵉ étage, cage B ».
	 *   Jusqu'ici cette précision se perdait, ou se racontait en texte libre.
	 *
	 *   ⚠️ Facultatif, et **vide par défaut** : ne rien toucher ne change rien.
	 *   Une entrée qui ne parle pas du périmètre n'en déclare aucun, elle ne
	 *   l'élargit surtout pas à la résidence entière. */
	export let avecPerimetre = false;
	/** Périmètre courant de l'objet — affiché en badge, comme l'état courant. */
	export let perimetreCourant: string[] = [];
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
	let emailExterne = '';
	//  Vide tant que personne n'y touche : c'est ce vide qui veut dire « cette
	//  entrée ne dit rien du périmètre ». Le pré-remplir avec le périmètre courant
	//  ferait déclarer un périmètre à chaque commentaire — donc écrire dans
	//  l'historique un resserrement qui n'a pas eu lieu.
	let perimetre: string[] = [];

	//  7. Photos · 8. Documents — DEUX sections, jamais une seule (cadre #430).
	//  Le tri se fait à l'ouverture, sur ce que l'entrée portait déjà : les
	//  évolutions ne stockent qu'une liste (`fichiers_urls`), et c'est `estImage`
	//  qui décide de quel côté chaque pièce revient — la même règle que partout
	//  ailleurs (`$lib/fichiers`), jamais réimplémentée dans un écran.
	let photos: string[] = editMode
		? initialFichiers.filter(f => estImage(f.url)).map(f => f.url)
		: [];
	let docs: string[] = editMode
		? initialFichiers.filter(f => !estImage(f.url)).map(f => f.url)
		: [];

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
	//  Préciser le périmètre est un geste de SUIVI : il n'a pas de sens en
	//  réécrivant une entrée passée, où il raturerait un fait daté (le serveur
	//  refuse d'ailleurs `perimetre_cible` sur un PATCH).
	$: sectionPerimetre = avecPerimetre && !editMode;

	//  L'état actuel se lit en BADGE à droite de l'intitulé, pas en ligne de texte
	//  sous lui (`ux-patterns` §9 quater) — c'est la forme qu'a déjà la carte du
	//  ticket, deux centimètres plus haut.
	$: libelleStatutActuel = currentStatut ? (statutLabels[currentStatut] || currentStatut) : '';

	//  Le périmètre COURANT en badge, même forme que l'état courant deux lignes
	//  plus haut : on voit d'où l'on part avant de préciser. `ChampsCommuns`
	//  n'affiche le badge que sur le périmètre par défaut, parce que le sélecteur
	//  montre déjà la sélection ; ici le sélecteur part vide, donc le badge est le
	//  SEUL endroit où l'on lit le périmètre actuel — il est toujours affiché.
	$: libellePerimetreActuel = perimetreCourant.length
		? perimetreLabel(perimetreCourant)
		: perimetreLabelUn(perimetreParDefaut() ?? '');

	//  Le commentaire est REQUIS pour une évolution de type commentaire, facultatif
	//  quand il accompagne un changement d'état. Pas de mention « (optionnel) » :
	//  l'absence d'astérisque suffit (`ux-patterns` §9).
	$: titreContenu = editMode ? 'Contenu' : 'Commentaire';
	//  🔴 LE GESTE EST DÉDUIT, il ne se déclare plus. Une pastille laissée sur
	//  l'état courant ne change rien : l'entrée est un commentaire. En choisir une
	//  autre en fait un changement d'état. C'est ce qui permet UN seul point
	//  d'entrée — la question « lequel des deux ? » a déjà sa réponse à l'écran.
	$: evolType = (!editMode && nouveauStatut && nouveauStatut !== currentStatut)
		? 'etat'
		: 'commentaire';
	//  Le commentaire est REQUIS quand l'entrée n'apporte que lui : sans texte ni
	//  changement d'état, l'entrée ne dirait rien.
	$: contenuRequis = !editMode && evolType === 'commentaire';

	//  Une entrée vaut si elle apporte quelque chose : un changement d'état, un
	//  texte, ou une pièce jointe. Rien des trois → rien à enregistrer.
	$: canSubmit = !saving && (
		evolType === 'etat' || !(richEmpty(contenu) && allFichiersUrls.length === 0)
	);

	// Le téléversement lui-même vit dans `FichiersUpload` : trois copies de la
	// même fonction (photo, document, fichier unifié) ne différaient que par la
	// liste alimentée.

	// ── Aperçu avant diffusion (#498) ─────────────────────────────────────────
	//  Il ne s'interpose QUE si l'appelant sait le composer ET qu'un canal est
	//  coché : sans canal il n'y a rien à montrer, et une modale de plus serait
	//  une étape gratuite entre l'utilisateur et son commentaire.
	$: aUneDiffusion = showNotifs && (partagerWhatsapp || envoyerSyndic || envoyerCs);
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
			nouveau_statut: (!editMode && evolType === 'etat') ? nouveauStatut : undefined,
			fichiers_urls: allFichiersUrls,
			partager_whatsapp: showNotifs ? partagerWhatsapp : undefined,
			envoyer_syndic: showNotifs ? envoyerSyndic : undefined,
			envoyer_cs: showNotifs ? envoyerCs : undefined,
			email_externe: showEmail ? (emailExterne.trim() || undefined) : undefined,
			interne: avecInterne ? interne : undefined,
			//  `undefined` et non `[]` : le serveur distingue « n'en parle pas » de
			//  « plus aucun périmètre », et seul le premier laisse le ticket tranquille.
			perimetre_cible: (sectionPerimetre && perimetre.length) ? perimetre : undefined,
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
		<SectionFormulaire premiere titre="Workflow" requis badge={libelleStatutActuel}
			idTitre="{idPrefixe}-workflow-titre">
			<div class="field champ-large" role="group" aria-labelledby="{idPrefixe}-workflow-titre">
				<div class="evol-pastilles">
					{#each statutOptions as opt (opt.value)}
						<Pastille active={(nouveauStatut || currentStatut) === opt.value}
							on:click={() => (nouveauStatut = opt.value)}>{opt.label}</Pastille>
					{/each}
				</div>
			</div>
		</SectionFormulaire>
	{/if}

	<!-- ── 4. Périmètre ─────────────────────────────────────────────────────
	     Le périmètre d'un ticket n'est pas acquis à l'ouverture : il se précise à
	     mesure qu'on cherche (#497). Cette section le laisse dire, sans jamais
	     l'imposer — le sélecteur part VIDE, et ne rien y toucher ne change rien.
	     Le badge porte le périmètre COURANT : on voit d'où l'on part.
	     Section à UN champ : le titre EST le libellé, le sélecteur se tait
	     (`ux-patterns` §9 septies). Les pastilles ne sont pas labelables, d'où le
	     couple `idTitre` / `aria-labelledby`, comme dans `ChampsCommuns`. -->
	{#if sectionPerimetre}
		<SectionFormulaire titre="Périmètre" badge={libellePerimetreActuel}
			idTitre="{idPrefixe}-perimetre-titre">
			<div class="field champ-large" role="group" aria-labelledby="{idPrefixe}-perimetre-titre">
				<PerimetrePicker bind:value={perimetre} titre="" />
				<p class="evol-aide">
					À renseigner seulement pour <strong>préciser</strong> le périmètre — par
					exemple quand on a trouvé d'où vient la fuite. Laissé vide, le périmètre
					du ticket ne bouge pas.
				</p>
			</div>
		</SectionFormulaire>
	{/if}

	<!-- ── 6. Description ───────────────────────────────────────────────────
	     Section à UN champ : le titre EST le libellé, et l'éditeur ne réécrit
	     rien (`ux-patterns` §9 septies). L'éditeur riche est un `contenteditable`,
	     donc PAS labelable : le titre reste un `<h4>` et l'éditeur s'y relie par
	     `aria-labelledby` — un `for` n'aurait rien associé, et en silence. -->
	<SectionFormulaire premiere={!sectionWorkflow} titre={titreContenu} requis={contenuRequis}
		idTitre="{idPrefixe}-contenu-titre">
		<div class="field champ-large">
			<RichEditor id="{idPrefixe}-contenu" bind:value={contenu}
				ariaLabelledby="{idPrefixe}-contenu-titre"
				placeholder={editMode
					? 'Modifier le commentaire…'
					: evolType === 'etat'
						? 'Précisions sur ce changement…'
						: 'Ajoutez un commentaire de suivi…'}
				minHeight="90px" />
		</div>
	</SectionFormulaire>

	<!-- ── 7-8. Photos et Documents ─────────────────────────────────────────
	     ✅ Les pièces jointes ne dépendent PLUS du geste (18/08/2026). Une
	     condition héritée les fermait sur un changement d'état — sans qu'aucun
	     commit ni aucune issue n'en porte la raison, alors qu'une photo justifie
	     souvent un passage à « Résolu ». Elle ne pouvait de toute façon pas
	     survivre au point d'entrée unique : le geste n'est plus connu à
	     l'ouverture du formulaire, il se déduit de ce qu'on y fait. -->
	{#if showFiles}
		<SectionFormulaire titre="Photos" pour="{idPrefixe}-photos">
			<div class="field champ-large">
				<FichiersUpload id="{idPrefixe}-photos" bind:urls={photos} titre=""
					label="Ajouter une photo" accept={ACCEPT_PHOTOS} size={80} />
			</div>
		</SectionFormulaire>
		<SectionFormulaire titre="Documents" pour="{idPrefixe}-docs">
			<div class="field champ-large">
				<FichiersUpload id="{idPrefixe}-docs" mode="documents" titre="" bind:urls={docs} />
			</div>
		</SectionFormulaire>
	{/if}

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
		avecCanaux={showNotifs}
		bind:whatsapp={partagerWhatsapp}
		bind:syndic={envoyerSyndic}
		bind:cs={envoyerCs}
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
		<button type="button" class="btn btn-outline btn-sm" on:click={() => dispatch('cancel')}>Annuler</button>
		<button type="button" class="btn btn-primary btn-sm" disabled={!canSubmit} on:click={soumettre}>
			{saving ? 'Enregistrement…' : 'Enregistrer'}
		</button>
	</div>
</FormulaireCreation>

<style>
	/*  La rangée de pastilles du workflow. Les pastilles portent leur propre style
	    (`Pastille.svelte`, v2.67.11) : ne vit ici que leur disposition. */
	.evol-pastilles { display: flex; gap: .5rem; flex-wrap: wrap; }

	/*  Le texte d'aide sous le sélecteur de périmètre. Défini ICI, avec le
	    balisage qu'il habille : un style de page n'atteint pas un composant, et
	    une classe seulement employée arrive nue à l'écran (v2.67.11).
	    ⚠️ C'est la TROISIÈME écriture de la même notion dans le dépôt —
	    `.ah-aide` (FormulaireAnnonceHall) et `.perimetre-aide` (PerimetrePicker)
	    disent la même chose aux mêmes valeurs. Suivi à part : les fusionner
	    demande de reprendre les trois appelants, pas d'en ajouter une quatrième
	    en douce ici. */
	.evol-aide { font-size: .8rem; color: var(--color-text-muted); line-height: 1.5; margin: .6rem 0 0; }

	/*  `.case-interne` est partie avec son balisage dans `SectionDiffusion.svelte`
	    (#498), cible tactile de 44 px comprise : la garder ici en ferait une règle
	    orpheline, c'est-à-dire la moitié du défaut que `lint:classes-nues`
	    surveille par l'autre bout. */
</style>
