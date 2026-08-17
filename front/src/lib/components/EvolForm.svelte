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

  ## LE GESTE EST DÉCIDÉ PAR L'APPELANT (#426, 18/08/2026)

  Ce formulaire commençait par une rangée de deux pastilles — « 💬 Commentaire »
  et « 🔄 Changement d'état » — au-dessus d'un formulaire ouvert par un bouton
  💬. L'utilisateur avait donc **déjà dit** ce qu'il voulait faire en cliquant, et
  la première pastille était un choix sans objet : déjà sélectionnée, et la
  sélectionner ne faisait rien.

  > « le bouton commentaire n'a pas lieu d'être — il est présent sur le fil
  >   principal pour ouvrir un *nouveau commentaire* » (17/08/2026)

  La rangée a disparu, et le geste arrive en prop : `evolType`. Chaque écran
  porte désormais **deux** points d'entrée — 💬 pour commenter, 🔄 pour changer
  l'état —, ce qui était la forme recommandée par #426. On ne pouvait pas retirer
  la pastille seule : « Changement d'état » n'avait aucun autre chemin depuis un
  fil, et la supprimer aurait supprimé la fonction.

  La section **Workflow** ne rend donc plus qu'un sélecteur d'état, et seulement
  quand c'est le geste demandé.

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
    evolType           – LE GESTE, décidé par l'appelant : 'commentaire' | 'etat'
    statutOptions      – liste des options de statut disponibles (geste 'etat')
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
	import CanauxNotification from '$lib/components/CanauxNotification.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import { ACCEPT_PHOTOS, estImage } from '$lib/fichiers';

	// ── Props ─────────────────────────────────────────────────────────────────
	/** Préfixe des `id` des champs. Plusieurs formulaires d'évolution coexistent à
	    l'écran — le formulaire d'ajout d'une carte et l'édition d'une évolution du
	    même fil —, et deux `<label for="…">` pointant le même id ne désignent plus
	    rien. Même contrat que `ChampsCommuns`. */
	export let idPrefixe = 'evol';
	/**  LE GESTE, décidé par l'appelant — c'est le bouton cliqué qui l'a dit
	     (#426). `commentaire` : on ajoute une réponse au fil. `etat` : on fait
	     avancer le workflow, et le sélecteur d'état apparaît. Il n'y a plus de
	     rangée de pastilles : redemander ce que le clic vient de déclarer est un
	     choix sans objet. */
	export let evolType: 'commentaire' | 'etat' = 'commentaire';
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
		};
		cancel: void;
	}>();

	// ── State ─────────────────────────────────────────────────────────────────
	let contenu = initialContenu;
	let nouveauStatut = '';
	let partagerWhatsapp = defaultPartagerWhatsapp;
	let envoyerSyndic = defaultEnvoyerSyndic;
	let envoyerCs = defaultEnvoyerCs;
	let emailExterne = '';

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
	$: sectionWorkflow = !editMode && evolType === 'etat' && statutOptions.length > 0;
	$: sectionDiffusion = showNotifs || showEmail || avecInterne;

	//  L'état actuel se lit en BADGE à droite de l'intitulé, pas en ligne de texte
	//  sous lui (`ux-patterns` §9 quater) — c'est la forme qu'a déjà la carte du
	//  ticket, deux centimètres plus haut.
	$: libelleStatutActuel = currentStatut ? (statutLabels[currentStatut] || currentStatut) : '';

	//  Le commentaire est REQUIS pour une évolution de type commentaire, facultatif
	//  quand il accompagne un changement d'état. Pas de mention « (optionnel) » :
	//  l'absence d'astérisque suffit (`ux-patterns` §9).
	$: titreContenu = editMode ? 'Contenu' : 'Commentaire';
	$: contenuRequis = !editMode && evolType === 'commentaire';

	$: canSubmit = !saving && (
		editMode
			? !(richEmpty(contenu) && allFichiersUrls.length === 0)
			: evolType === 'etat'
				? !!nouveauStatut
				: !(richEmpty(contenu) && (!showFiles || allFichiersUrls.length === 0))
	);

	// Le téléversement lui-même vit dans `FichiersUpload` : trois copies de la
	// même fonction (photo, document, fichier unifié) ne différaient que par la
	// liste alimentée.

	// ── Submit ────────────────────────────────────────────────────────────────
	function handleSubmit() {
		if (!canSubmit) return;
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
		});
	}
</script>

<!--  Même largeur de saisie que partout ailleurs (`ux-patterns` §9) : le
      formulaire s'étalait sur toute la carte, alors que le même geste sur une
      page dédiée s'arrête à 720 px. -->
<div class="largeur-saisie">

	<!-- ── 3. Workflow ───────────────────────────────────────────────────────
	     Plus de rangée de pastilles : le geste a été déclaré par le bouton qui a
	     ouvert ce formulaire (#426). Ne reste que ce qu'il faut encore préciser —
	     vers quel état. Le libellé porte l'état ACTUEL en badge, à droite
	     (`ux-patterns` §9 quater). -->
	{#if sectionWorkflow}
		<!--  Section à UN champ : le titre EST le libellé, et le sélecteur ne
		      réécrit rien (`ux-patterns` §9 septies). Même forme que la section
		      Workflow de `FormulaireTicket`, au mot près. -->
		<SectionFormulaire premiere titre="Workflow" requis badge={libelleStatutActuel}
			pour="{idPrefixe}-statut">
			<div class="field champ-large">
				<select id="{idPrefixe}-statut" bind:value={nouveauStatut}>
					<option value="">— Choisir le nouvel état —</option>
					{#each statutOptions as opt (opt.value)}
						<option value={opt.value}>{opt.label}</option>
					{/each}
				</select>
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
	     ⚠️ `evolType === 'commentaire'` ferme les pièces jointes sur un
	     CHANGEMENT D'ÉTAT. Cette condition est héritée du code d'avant
	     l'extraction du composant (elle existait telle quelle dans
	     `tickets/[id]` avant le 22b3828) : aucun commit ni aucune issue n'en
	     porte la raison. Une photo justifie pourtant souvent un passage à
	     « Résolu ». Laissée EN L'ÉTAT tant qu'elle n'est pas arbitrée — la
	     question est posée dans #416. -->
	{#if showFiles && (editMode || evolType === 'commentaire')}
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

	<!-- ── 9. Diffusion — EN DERNIER, après les pièces jointes ──────────────
	     L'avertissement sur les fichiers est rendu au CONTACT de la case
	     WhatsApp qu'il commente : sous le sélecteur de fichiers, il en était
	     séparé par toute la rubrique (#416). -->
	{#if sectionDiffusion}
		<SectionFormulaire titre="Diffusion">
			{#if avecInterne}
				<label class="case-interne">
					<input type="checkbox" bind:checked={interne} />
					<span>Message interne (visible par le conseil syndical uniquement)</span>
				</label>
			{/if}
			{#if showNotifs}
				<CanauxNotification
					bind:whatsapp={partagerWhatsapp}
					bind:syndic={envoyerSyndic}
					bind:cs={envoyerCs}
					compact
				/>
				{#if partagerWhatsapp && allFichiersUrls.length > 0}
					<p class="aide-case">
						⚠️ Les fichiers ne sont pas envoyés via WhatsApp, uniquement le texte.
					</p>
				{/if}
			{/if}

			{#if showEmail}
				<div class="field champ-large">
					<label for="{idPrefixe}-email-ext">&#x1F4E7; Notifier une adresse email externe</label>
					<input id="{idPrefixe}-email-ext" type="email" bind:value={emailExterne}
						placeholder="contact@exemple.fr" />
				</div>
			{/if}
		</SectionFormulaire>
	{/if}

	<!-- ── Actions ──────────────────────────────────────────────────────────
	     `.form-actions` vient d'app.css : la disposition était recomposée ici en
	     ligne, aux mêmes valeurs, donc libre de diverger (`ux-patterns` §9
	     quinquies). Le verbe est GÉNÉRIQUE dans les deux modes — « Valider » /
	     « Envoi… » en création contre « Enregistrer » / « Enregistrement… » en
	     édition, c'était le même geste sous deux libellés (§9 quinquies bis). -->
	<div class="form-actions">
		<button type="button" class="btn btn-outline btn-sm" on:click={() => dispatch('cancel')}>Annuler</button>
		<button type="button" class="btn btn-primary btn-sm" disabled={!canSubmit} on:click={handleSubmit}>
			{saving ? 'Enregistrement…' : 'Enregistrer'}
		</button>
	</div>
</div>

<style>
	/*  `.evol-nature` a disparu avec la rangée de pastilles qu'elle habillait
	    (#426) : le geste est décidé par le bouton qui ouvre ce formulaire. */

	/*  Définie ICI, avec le balisage qu'elle habille : `.checkbox-field` n'est pas
	    une classe d'`app.css` — chaque composant qui l'emploie la style lui-même,
	    et une classe seulement utilisée arrive nue à l'écran (v2.67.11). */
	.case-interne {
		display: flex;
		align-items: center;
		gap: .4rem;
		cursor: pointer;
		font-size: .85rem;
		margin: 0 0 .6rem;
	}
	.case-interne input[type='checkbox'] { width: auto; margin: 0; flex-shrink: 0; }
	/*  Sous 480 px, la cible tactile d'une case ne faisait que 16 à 18 px de haut
	    (socle 11 §10). */
	@media (max-width: 480px) {
		.case-interne { min-height: 44px; }
	}
</style>
