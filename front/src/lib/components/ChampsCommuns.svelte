<!--
  ChampsCommuns.svelte — les sections 3 à 10 de TOUT formulaire de création,
  écrites une fois, dans l'ordre, avec leurs intitulés.

  ## Pourquoi ce composant (16/08/2026)

  L'ordre des sections était posé (`ux-patterns` §9 sexies) et `SectionFormulaire`
  savait les séparer à l'écran — mais chaque formulaire recomposait la suite à la
  main. Le résultat était exactement celui que `standards/02` §2 décrit :

  > « Les objets ont l'air d'être dupliqués, pas instanciés, car ils diffèrent
  >   selon les pages où ils sont implémentés. Il ne devrait pas y avoir de
  >   différence sur les objets Périmètre, Destinataires, Description, Photos,
  >   Fichiers et Diffusion — mais chaque page a des différences ! »

  Relevé avant correction, sur six écrans :

  | Notion       | Ce qui divergeait |
  |--------------|-------------------|
  | Description  | « Description » / « Description * » / « Notes » ; hauteur 60, 80, 90, 100 ou 120 px |
  | Photos       | `FichiersUpload` ici, absent là |
  | Documents    | `FichiersUpload` sur les tickets et le calendrier, `<input type="file">` nu sur les actualités et les prestations |
  | Diffusion    | aucune section nommée sur 4 écrans sur 6 |
  | Ordre        | Périmètre au milieu de la grille des champs spécifiques (prestations) ; Kanban rangé dans la diffusion (calendrier) |

  Aucune de ces différences n'était voulue. Elles sont le produit mécanique de
  six recopies : la seule façon de ne pas les voir revenir est qu'il n'y ait plus
  qu'UN endroit qui les écrive.

  ## Ce que ce composant décide, et ce qu'il ne décide pas

  Il décide **l'ordre, les intitulés et les séparations** des sections 3 à 10. Il
  ne décide RIEN du contenu métier : les sections 1 et 2 (Titre, champs
  spécifiques) restent dans l'écran, qui seul sait ce qu'elles portent.

  ## 🔴 Les sections 3 et 4 l'ont rejoint le 12/09/2026, et voici pourquoi

  Signalé à l'écran : *« la section Options de publication n'est pas ordonnée de
  la même façon entre Actualité et Tickets »*, et *« dans le calendrier,
  “Épingler dans le fil” est dans Diffusion alors qu'ailleurs c'est dans Options
  de publication »*.

  Les deux écarts ont la même cause : **l'ordre était écrit dans une
  documentation et respecté à la main.** Chaque écran posait sa section Options
  et sa section Workflow où il voulait, et rien ne pouvait le contredire — c'est
  très exactement le défaut que ce composant existait pour supprimer sur les
  sections 4 à 9, laissé en place sur les deux précédentes.

  L'ordre arbitré (`ux-patterns` §9 sexies) :

  | # | Section | Écrite par |
  |---|---|---|
  | 1 | Titre | l'écran |
  | 2 | Champs spécifiques | l'écran |
  | 3 | **Options de publication** | **ici** |
  | 4 | **Workflow** | **ici** (contenu par `slot`) |
  | 5 à 10 | Périmètre · Destinataires · Description · Photos · Documents · Diffusion | ici |

  ⚠️ Le Workflow reste un `slot` : son CONTENU est propre à l'objet (les six
  colonnes du Kanban, les états d'un ticket). Ce composant en impose le rang, le
  titre et le filet — pas ce qu'il y a dedans.

  Une section n'apparaît que si l'écran la déclare (`avecPerimetre`, `avecPhotos`…).
  Un sondage n'a pas de pièces jointes, une annonce n'a pas de diffusion : le
  contrat n'est pas « tous les écrans ont tout », c'est « quand un écran a une de
  ces notions, elle est à la même place et a la même tête ».

  ## L'ordre — il ne se discute pas par écran

  4. Périmètre · 5. Destinataires · 6. Description · 7. Photos · 8. Documents
  · 9. Diffusion.

  Le périmètre dit *de quoi* il s'agit, les destinataires *à qui* on l'adresse :
  le premier cadre le second (§9 ter). La **diffusion** (*qui le voit, et où ?*)
  est distincte du **workflow** (*où en est cet objet ?*), qui reste en section 3,
  avant le périmètre — les confondre est l'erreur d'origine.
-->
<script lang="ts">
	import SectionDescription from '$lib/components/SectionDescription.svelte';
	import SectionsPiecesJointes from '$lib/components/SectionsPiecesJointes.svelte';
	import SectionFormulaire from './SectionFormulaire.svelte';
	import PerimetrePicker from './PerimetrePicker.svelte';
	import DestinatairePicker from './DestinatairePicker.svelte';
	import SectionDiffusion from './SectionDiffusion.svelte';
	import SectionOptionsPublication from './SectionOptionsPublication.svelte';
	import type { CleOptionPublication } from '$lib/options-publication';
	import { estPerimetreParDefaut, perimetreLabelUn, perimetreParDefaut } from '$lib/perimetres';
	import { concerneTousLesResidents } from '$lib/destinataires';

	/** Préfixe des `id` des champs — deux formulaires peuvent coexister à l'écran,
	    et deux `<label for="…">` pointant le même id ne désignent plus rien. */
	export let idPrefixe: string;

	//  ── 3. Options de publication ─────────────────────────────────────────────
	//  🔴 Le rang de cette section ne se négocie plus par écran (12/09/2026) :
	//  elle était posée par l'actualité, par le ticket et par l'événement, chacun
	//  à sa place. Le CONTENU, lui, reste déclaré — un ticket n'en rend pas les
	//  mêmes qu'une actualité.
	export let avecOptions = false;
	/** Les options rendues, dans l'ordre de la table `$lib/options-publication`. */
	export let optionsRendues: CleOptionPublication[] = [
		'epingle',
		'urgente',
		'brouillon',
		'confidentiel',
	];
	/** Le nom de l'objet décrit — il entre dans les libellés qui le nomment. */
	export let objet = 'publication';
	export let epingle = false;
	export let urgente = false;
	export let brouillon = false;
	export let confidentiel = false;
	/** L'objet édité était-il DÉJÀ épinglé ? (évite un double comptage) */
	export let dejaEpingle = false;
	/** 🔒 Motif pour lequel l'objet est TOUJOURS restreint — relayé tel quel. */
	export let confidentielAcquis = '';
	/** 🔒 Motif pour lequel l'épinglage est impossible — relayé tel quel. */
	export let epingleInterdit = '';

	//  ── 4. Workflow ───────────────────────────────────────────────────────────
	//  ⚠️ Le CONTENU vient du `slot` : ce composant impose le rang, le titre et le
	//  filet, pas les états. `idTitre` est relayé pour que le groupe de pastilles
	//  s'y rattache (`aria-labelledby`).
	export let avecWorkflow = false;

	//  ── 5. Périmètre ──────────────────────────────────────────────────────────
	export let avecPerimetre = false;
	export let perimetre: string[] = [];
	/**  `single` : un seul code retenu. Le rendu est le MÊME (des pastilles) —
	     seule la sélection change. Utilisé par les prestations, dont la colonne
	     `perimetre` ne porte qu'un code ; les passer au tableau demande une
	     migration, suivie à part. */
	export let perimetreMode: 'multi' | 'single' = 'multi';
	/**  Le périmètre est-il OBLIGATOIRE ? Vrai partout sauf sur une évolution, où
	 *   il sert à **préciser** le périmètre de l'objet porteur : ne rien y toucher
	 *   ne change rien (#497). */
	export let perimetreRequis = true;
	/**  Le badge de la section. `null` = calculé (le périmètre par défaut, quand
	 *   c'est lui). Une évolution y met le périmètre COURANT de l'objet porteur —
	 *   on voit d'où l'on part, ce qu'aucun calcul local ne peut deviner. */
	export let perimetreBadge: string | null = null;

	//  ── 6. Destinataires ──────────────────────────────────────────────────────
	export let avecDestinataires = false;
	/**  Ce bloc ouvre-t-il le formulaire ? Une section n'affiche son filet que si
	 *   quelque chose la précède — sinon il double celui du cadre, et c'est le
	 *   « double trait » signalé à l'écran le 05/09/2026. */
	export let premiere = false;
	export let destinataires: string[] = ['résidents'];

	//  ── 7. Description ────────────────────────────────────────────────────────
	export let avecDescription = false;
	export let description = '';
	/**  L'intitulé de la section — « Description » par défaut.
	 *
	 *   🔴 Il était FIGÉ, et c'est ce qui empêchait `EvolForm` d'hériter de ce
	 *   composant : une évolution parle de « Commentaire », pas de « Description »
	 *   (#463). Le formulaire recopiait donc l'ordre ET les intitulés des sections
	 *   4 à 9 — deux endroits qui doivent rester d'accord, sans contrôle pour le
	 *   vérifier, ce que le cadre #430 supprime partout ailleurs.
	 *
	 *   ⚠️ Ce n'est pas une porte ouverte à un libellé par écran : **R3** demande
	 *   le même mot d'un formulaire à l'autre pour la même notion. Le paramètre
	 *   existe pour les objets dont la section n'est PAS une description — et
	 *   aujourd'hui il n'y en a qu'un. */
	export let descriptionTitre = 'Description';
	export let descriptionRequise = false;
	export let descriptionPlaceholder = '';
	/**  Hauteur minimale de l'éditeur. Elle valait 60, 80, 90, 100 ou 120 px selon
	     l'écran, sans qu'aucune de ces valeurs ait de raison : 120 px est retenu
	     comme défaut — c'est celui des deux écrans les plus utilisés (actualités,
	     tickets). Ne la surcharger que pour une vraie contrainte de place. */
	export let descriptionHauteur = '120px';

	//  ── 8. Photos ─────────────────────────────────────────────────────────────
	export let avecPhotos = false;
	export let photos: string[] = [];

	//  ── 9. Documents ──────────────────────────────────────────────────────────
	export let avecDocuments = false;
	export let documents: string[] = [];
	/**  Mode différé : les documents d'une actualité deviennent des entités
	     `Document` rattachées à la publication, qui n'existe pas encore. Le
	     composant retient les `File`, l'écran les téléverse après création.
	     Voir l'en-tête de `FichiersUpload.svelte`. */
	export let documentsDifferes = false;
	export let documentsFichiers: File[] = [];
	/**  Qui rend le CONTRÔLE des documents. `interne` (défaut) : `FichiersUpload`,
	     comme partout. `slot` : l'écran fournit le sien — les documents d'une
	     publication sont des entités `Document` avec un identifiant, qu'on ajoute
	     et retire à l'unité. **La SECTION reste ici** dans les deux cas : son rang,
	     son intitulé et sa séparation ne se négocient pas, seul le contrôle change.
	     C'est le même contrat que la Diffusion, dont les actualités rendent déjà
	     les canaux elles-mêmes. */
	export let documentsControle: 'interne' | 'slot' = 'interne';

	//  ── 10. Diffusion ─────────────────────────────────────────────────────────
	export let avecDiffusion = false;
	/**  Les trois canaux (WhatsApp, syndic, CS). Un écran peut avoir une section
	     Diffusion SANS canaux — les actualités les rendent elles-mêmes, à travers
	     `OptionsPublication`, qui porte en plus le confidentiel et l'affiche de hall. */
	export let avecCanaux = true;
	export let whatsapp = false;
	export let syndic = false;
	export let cs = false;
	/** « M'envoyer une copie » — relayée telle quelle (voir `CanauxNotification`). */
	export let auteur = false;
	/**  Le nom de l'auteur de l'objet, relayé jusqu'à la case « Envoyer une copie
	 *   à … ». Relais pur : ce composant ne sait pas non plus qui a écrit
	 *   l'objet — seul l'écran tient l'objet. */
	export let auteurNom = '';
	export let aideWhatsapp = '';
	/** Motif interdisant le groupe WhatsApp — relayé jusqu'à `CanauxNotification`. */
	export let whatsappInterdit = '';
	/**  La fonction d'aperçu de l'écran — transmise TELLE QUELLE à l'objet
	 *   Diffusion, qui porte l'état et la modale (#498). Absente = pas d'aperçu,
	 *   ce qui est le cas des écrans sans endpoint. */
	export let demanderApercu: (() => Promise<any>) | null = null;
	//  Exposé au parent : c'est LUI qui déclenche l'aperçu au moment de soumettre.
	export let refDiffusion: any = null;
	export let envoiEnCours = false;

	//  ── Les badges d'état, portés par le TITRE de section ────────────────────
	//  Ils vivaient dans les sélecteurs, avec leur intitulé. Depuis que le titre
	//  de section porte le libellé, il porte aussi le badge — sinon on lirait
	//  « PÉRIMÈTRE » puis « Périmètre * [Copropriété entière] », c'est-à-dire le
	//  nom deux fois (signalé à l'écran le 16/08/2026, dès la mise en production).
	//  Rien n'est recalculé : `estPerimetreParDefaut` et `concerneTousLesResidents`
	//  sont les fonctions qu'utilisent déjà les sélecteurs eux-mêmes.
	$: badgePerimetre = estPerimetreParDefaut(perimetre)
		? perimetreLabelUn(perimetreParDefaut() ?? '')
		: '';
	$: badgeDestinataires = concerneTousLesResidents(destinataires) ? 'Tous les résidents' : '';

	//  Le filet du haut n'appartient pas au Périmètre : il appartient à la
	//  PREMIÈRE section rendue, quelle qu'elle soit. Sans ce calcul, ouvrir un
	//  formulaire par les options doublait le trait du cadre — le « double trait »
	//  signalé à l'écran le 05/09/2026, une section plus haut.
	$: premiereWorkflow = premiere && !avecOptions;
	$: premierePerimetre = premiere && !avecOptions && !avecWorkflow;
</script>

{#if avecOptions}
	<!--  3. Les options qui DÉCRIVENT l'objet — épinglage, urgence, brouillon,
	      confidentialité. Toujours ici, jamais dans la Diffusion : elles se
	      corrigent, elles ne s'envoient pas. -->
	<SectionOptionsPublication
		{objet}
		{premiere}
		options={optionsRendues}
		perimetreCible={perimetre}
		{dejaEpingle}
		{confidentielAcquis}
		{epingleInterdit}
		bind:epingle
		bind:urgente
		bind:brouillon
		bind:confidentiel
	/>
{/if}

{#if avecWorkflow}
	<!--  4. Workflow — OÙ EN EST l'objet. À distinguer de la Diffusion, qui dit
	      qui le voit et où (section 10). Le contenu vient de l'écran. -->
	<SectionFormulaire titre="Workflow" premiere={premiereWorkflow} idTitre="{idPrefixe}-workflow">
		<slot name="workflow" />
	</SectionFormulaire>
{/if}

{#if avecPerimetre}
	<!--  Le sélecteur se tait (`titre=""`) : la section le nomme. Les pastilles ne
	      sont pas un contrôle labelable — `for` n'y associerait rien —, d'où le
	      couple `id` sur le titre / `aria-labelledby` sur le groupe. -->
	<SectionFormulaire
		premiere={premierePerimetre}
		titre="Périmètre"
		requis={perimetreRequis}
		badge={perimetreBadge ?? badgePerimetre}
		idTitre="{idPrefixe}-perimetre-titre"
	>
		<div class="field champ-large" role="group" aria-labelledby="{idPrefixe}-perimetre-titre">
			<PerimetrePicker bind:value={perimetre} mode={perimetreMode} titre="" />
			<!--  🔴 Un SLOT et non une prop de texte : l'aide porte du balisage (un
			      `<strong>`), et une prop obligerait à un `{@html}` — donc à un
			      assainisseur, pour du contenu qui n'est pas de la donnée mais du
			      gabarit. Le slot laisse le balisage chez l'appelant : rien à
			      assainir, rien à faire confiance.

			      Vide par défaut : l'aide n'existe que là où le geste n'est pas
			      évident. Sur une évolution, « laissé vide, le périmètre du ticket ne
			      bouge pas » ne se déduit pas du champ. -->
			<slot name="aidePerimetre" />
		</div>
	</SectionFormulaire>
{/if}

{#if avecDestinataires}
	<SectionFormulaire
		premiere={premiere && !avecPerimetre}
		titre="Destinataires"
		requis
		badge={badgeDestinataires}
		idTitre="{idPrefixe}-destinataires-titre"
	>
		<div class="field champ-large" role="group" aria-labelledby="{idPrefixe}-destinataires-titre">
			<DestinatairePicker bind:value={destinataires} titre="" />
		</div>
	</SectionFormulaire>
{/if}

{#if avecDescription}
	<SectionDescription
		{idPrefixe}
		titre={descriptionTitre}
		requis={descriptionRequise}
		placeholder={descriptionPlaceholder}
		hauteur={descriptionHauteur}
		bind:valeur={description}
	/>
{/if}

<!--  7. Photos · 8. Documents — DEUX sections, écrites une seule fois pour ce
      composant ET `EvolForm`, qui les portait à l'identique (01/09/2026). -->
<SectionsPiecesJointes
	{idPrefixe}
	{avecPhotos}
	bind:photos
	{avecDocuments}
	{documentsControle}
	{documentsDifferes}
	bind:documents
	bind:documentsFichiers
>
	<svelte:fragment slot="documents"><slot name="documents" /></svelte:fragment>
</SectionsPiecesJointes>

<!--  🔴 La section 9 vient de `SectionDiffusion`, elle n'est plus réécrite ici
      (#498, 20/08/2026).

      L'objet Diffusion existait en DOUBLE : `SectionDiffusion.svelte` d'un côté,
      ces onze lignes de l'autre — et c'est la seconde que servaient les six
      formulaires de création. D'où la question posée à l'écran : « je ne
      comprends pas qu'une fonction dans un objet ne soit pas accessible sur
      toutes ses implémentations ». Réponse : il y avait deux objets, et l'aperçu
      n'avait été ajouté qu'à l'un des deux.

      ⚠️ `demanderApercu` n'est PAS transmis ici : aucun de ces six écrans n'a
      encore d'endpoint d'aperçu (seuls les tickets en ont un). L'objet le porte
      désormais — le jour où un écran fournit sa fonction, il obtient l'aperçu
      sans une ligne de plus. -->
{#if avecDiffusion}
	<SectionDiffusion
		{avecCanaux}
		bind:whatsapp
		bind:syndic
		bind:cs
		bind:auteur
		{auteurNom}
		{aideWhatsapp}
		{whatsappInterdit}
		bind:this={refDiffusion}
		{demanderApercu}
		{envoiEnCours}
		on:envoyer
	>
		<svelte:fragment slot="options"><slot name="diffusion" /></svelte:fragment>
	</SectionDiffusion>
{/if}
