//  Le workflow d'un ticket — écrit UNE fois, pour les cinq écrans qui l'affichent.
//
//  Avant le 17/08/2026, chaque écran portait sa propre liste : quatre listes
//  d'options et trois tables de libellés, aucune dérivée de l'énumération du
//  serveur. Elles avaient divergé dans les deux sens (#415) — la fiche du ticket
//  proposait `fermé`, la liste et l'espace CS proposaient `annulé`, et le serveur
//  refusait précisément ce dernier. Chacune était cohérente avec elle-même ; c'est
//  ce qui les rendait invisibles à la relecture.
//
//  ⚠️ Ces quatre états sont la notion **Workflow** au sens de `ux-patterns`
//  §9 sexies — « où en est cet objet ? ». À ne pas confondre avec la Diffusion
//  (« qui le voit, et où ? »), ni avec les statuts d'une PUBLICATION, qui sont
//  une autre notion et vivent dans `$lib/publications.ts`.
//
//  La contrepartie serveur est `StatutTicket` (`api/app/models/core.py`), et
//  `api/tests/test_statuts_tickets.py` échoue si les deux divergent.

import type { CleOptionPublication } from '$lib/options-publication';
import type { Ticket } from '$lib/api';

export interface StatutTicket {
	/** Valeur envoyée à l'API — jamais traduite, jamais réécrite. */
	value: string;
	/** Libellé seul, pour un badge ou une phrase. */
	label: string;
	/** Pastille de couleur, pour une liste d'options. */
	emoji: string;
	/** Classe de badge (`app.css`). */
	badge: string;
}

//: Les quatre états, dans l'ordre du workflow : c'est celui dans lequel ils
//: s'affichent partout, boutons de la fiche comme listes déroulantes.
export const STATUTS_TICKET: readonly StatutTicket[] = [
	{ value: 'ouvert', label: 'Ouvert', emoji: '\u{1F535}', badge: 'badge-blue' },
	{ value: 'en_cours', label: 'En cours', emoji: '\u{1F7E1}', badge: 'badge-orange' },
	{ value: 'résolu', label: 'Résolu', emoji: '\u{1F7E2}', badge: 'badge-green' },
	{ value: 'annulé', label: 'Annulé', emoji: '⚫', badge: 'badge-gray' },
];

//: Options d'un `<select>` ou d'une rangée de boutons — pastille comprise.
export const STATUT_TICKET_OPTIONS = STATUTS_TICKET.map((s) => ({
	value: s.value,
	label: `${s.emoji} ${s.label}`,
}));

//: `fermé` n'est plus un état depuis le 17/08/2026 (migration 0149), mais le fil
//: d'évolutions d'un ticket ancien raconte encore « Ouvert → Fermé ». Il reste
//: donc **affichable**, et n'est jamais proposable : il n'apparaît ni dans
//: `STATUTS_TICKET`, ni dans les options, ni dans les états clos.
const STATUTS_TICKET_HISTORIQUES: Record<string, { label: string; badge: string }> = {
	fermé: { label: 'Fermé', badge: 'badge-gray' },
};

export const STATUT_TICKET_LABELS: Record<string, string> = {
	...Object.fromEntries(STATUTS_TICKET.map((s) => [s.value, s.label])),
	...Object.fromEntries(Object.entries(STATUTS_TICKET_HISTORIQUES).map(([v, h]) => [v, h.label])),
};

export const STATUT_TICKET_BADGE: Record<string, string> = {
	...Object.fromEntries(STATUTS_TICKET.map((s) => [s.value, s.badge])),
	...Object.fromEntries(Object.entries(STATUTS_TICKET_HISTORIQUES).map(([v, h]) => [v, h.badge])),
};

//: Un ticket dans l'un de ces états ne demande plus de suivi : il quitte la liste
//: active pour l'Historique, et sort des relances. `fermé` y figure parce que
//: l'affichage d'un ticket ancien ne doit pas dépendre du succès d'une migration.
export const STATUTS_TICKET_CLOS: readonly string[] = ['résolu', 'annulé', 'fermé'];

//: Le complément : un ticket qui demande encore du suivi. La question s'écrivait
//: `t.statut === 'ouvert' || t.statut === 'en_cours'`, deux fois dans le même
//: fichier — trouvée par le garde-fou, pas à la relecture.
//: Déclaré après `STATUTS_TICKET_CLOS`, dont il dépend à l'initialisation.
export const STATUTS_TICKET_ACTIFS: readonly string[] = STATUTS_TICKET.map((s) => s.value).filter(
	(v) => !STATUTS_TICKET_CLOS.includes(v),
);

//: 🔴 LE FILTRE SE DÉDUIT DE LA LISTE, il ne se choisit plus.
//:
//: Il proposait les seuls états ACTIFS, au motif que « les clos ont leur section
//: Historique ». C'était faux d'une semaine : un ticket clôturé reste **sept
//: jours** dans la liste principale (délai de grâce). Un ticket « Résolu » hier
//: s'affiche donc, et aucun bouton ne permettait de l'isoler — signalé à l'écran
//: le 01/09/2026 : *« le filtre ne comprend pas tous les états du workflow
//: pouvant être affichés sur la page (notamment résolu ?) »*.
//:
//: ⚠️ Le défaut n'était pas la liste, c'était sa SOURCE : elle décrivait ce
//: qu'on croyait afficher, pas ce qui s'affiche. Elle se calcule maintenant sur
//: les tickets réellement rendus — ce qui couvre aussi `fermé`, l'état
//: historique qu'aucune liste écrite à la main n'aurait pensé à inclure.
//:
//: L'ordre reste celui du workflow, jamais celui d'apparition : un filtre dont
//: les boutons bougent d'un chargement à l'autre n'est pas un filtre.
export function statutsPresents(
	tickets: readonly { statut: string }[],
): { value: string; label: string }[] {
	const presents = new Set(tickets.map((t) => t.statut));
	const connus = STATUT_TICKET_OPTIONS.filter((o) => presents.has(o.value));
	//: Les états historiques (`fermé`) n'ont pas d'emoji : ils portent leur
	//: libellé seul, ce qui les distingue sans les mettre en avant.
	const historiques = Object.keys(STATUTS_TICKET_HISTORIQUES)
		.filter((v) => presents.has(v))
		.map((v) => ({ value: v, label: STATUT_TICKET_LABELS[v] }));
	return [...connus, ...historiques];
}

//  ── Les catégories — même histoire que les statuts, un cran plus tard ────────
//
//  Elles vivaient en QUATRE endroits le 17/08/2026 : la grille de choix de
//  `FormulaireTicket` (valeur + libellé + description), la table `CATEGORIES` de
//  la fiche d'un ticket, la table `CAT_ICON` de la liste, et six boutons de
//  filtre écrits en dur dans le balisage de cette même liste. Aucune n'était
//  dérivée d'une autre — exactement le motif qui avait fait diverger les statuts
//  (#415), à ceci près qu'ici l'écart n'a pas encore eu le temps de se produire.
//
//  ⚠️ La catégorie **qualifie le titre** : elle appartient à la section 1 du
//  cadre (#430), pas à une section « Détails ».

export interface CategorieTicket {
	/** Valeur envoyée à l'API — jamais traduite. */
	value: string;
	/** Libellé seul. */
	label: string;
	/** Pastille de contexte. */
	emoji: string;
	/** Ce que la catégorie recouvre, pour aider à choisir à la création. */
	description: string;
}

/**
 *  Les huit catégories, **dans l'ordre de fréquence attendue** en copropriété.
 *
 *  🔴 L'ordre est une décision, pas le résidu de celui où on les a écrites : sur
 *  deux lignes de quatre, la première porte le quotidien — panne, nuisance,
 *  propreté, espaces verts — et la seconde les cas particuliers : le sinistre,
 *  le dossier suivi par le conseil, la question, le défaut du logiciel.
 *
 *  ⚠️ L'alphabétique a été écarté (07/09/2026, l'alternative proposée) : il
 *  mettrait « Bug » en tête et « Sinistre » en avant-dernier. Un ordre qui ne
 *  dit rien du métier oblige à lire les huit entrées à chaque fois ; celui-ci
 *  fait que la plupart des gens s'arrêtent aux deux premières.
 */
export const CATEGORIES_TICKET: readonly CategorieTicket[] = [
	{
		value: 'panne',
		label: 'Panne',
		emoji: '\u{1F6E0}️',
		//  🔴 « éclairage » et « fuite » sont NOMMÉS, et « à réparer » conclut.
		//  Questionné le 07/09/2026 : *« une fuite goutte-à-goutte dans les communs,
		//  Panne ou Sinistre ? Idem pour une ampoule grillée. »* Les deux sont des
		//  pannes — mais la description ne le disait pas, et c'est ce qui rendait la
		//  question nécessaire. Quelqu'un qui cherche « Électricité » ne trouvait
		//  rien.
		description: 'Ascenseur, chauffage, éclairage, fuite, porte — à réparer',
	},
	/*  🔴 UNE SEULE CATÉGORIE, après avoir essayé d'en faire deux (07/09/2026).

	    J'avais séparé « Nuisance » et « Propreté » sur l'argument « deux
	    prestataires différents ». Signalé le soir même : *« très sincèrement,
	    Propreté je la regrouperais dans Nuisance en complétant le libellé »*.
	    C'est juste, et l'erreur était la mienne — trois signes le disaient déjà :

	    • dans les faits le GESTE est le même : le conseil relaie au syndic ou au
	      prestataire, il ne fait pas deux choses différentes ;
	    • le recouvrement, je l'avais ADMIS en écrivant qu'« un encombrant
	      abandonné dans le hall est les deux à la fois » ;
	    • et j'avais dû EXPLIQUER LA FRONTIÈRE dans le manuel. Une frontière qu'il
	      faut expliquer est une frontière qui n'existe pas.

	    Le critère du projet — « une catégorie ne se justifie que si elle change ce
	    qu'on FAIT du ticket » — était le bon ; c'est mon application qui était
	    fausse, en prenant « qui exécute in fine » pour « qui traite ». */
	{
		value: 'nuisance',
		label: 'Nuisance & propreté',
		emoji: '\u{1F4E2}',
		description: 'Bruit, odeurs, stationnement, parties communes, encombrants',
	},
	{
		value: 'espaces_verts',
		label: 'Espaces verts',
		emoji: '\u{1F333}',
		description: 'Élagage, haies, arrosage, allées…',
	},
	{
		value: 'sinistre',
		label: 'Sinistre',
		//  ⚠️ La description porte les mots du RÉSIDENT — « dégât des eaux »,
		//  « fuite » — là où le libellé porte celui de l'assureur. Le sinistre est
		//  ce qui déclenche une déclaration sous cinq jours ouvrés ; c'est la
		//  procédure qui fait la catégorie, pas la cause.
		emoji: '\u{1F4A7}',
		//  🔴 « Dégât CONSTATÉ » ouvre la description, et ce mot fait tout le
		//  travail. La frontière avec « Panne » n'est pas l'eau, c'est le DOMMAGE :
		//  une fuite qu'on répare est une panne ; de l'eau chez le voisin, un
		//  plafond taché, un parquet gondolé — il y a un tiers lésé et un délai
		//  d'assurance, c'est un sinistre.
		description: 'Dégât constaté : eau, incendie, vandalisme — déclaration à l’assurance',
	},
	{
		value: 'etude_travaux',
		label: 'Étude & travaux',
		emoji: '\u{1F3D7}️',
		description: 'Diagnostic, sondage, devis, chantier suivi par le conseil',
	},
	{
		value: 'acces_accueil',
		label: 'Accès & accueil',
		//  ⚠️ Le badge et la télécommande N'Y SONT PAS, et c'est délibéré :
		//  `CommandeAcces` porte déjà le lot, la quantité, le motif et son propre
		//  workflow (écran « Accès & sécurité »). Un ticket y perdrait tout. Cette
		//  catégorie est pour ce qui n'a AUCUN circuit dédié — l'interphone, la
		//  boîte aux lettres, et le suivi d'un emménagement.
		emoji: '\u{1F511}',
		description: 'Interphone, boîte aux lettres, emménagement',
	},
	{ value: 'question', label: 'Question', emoji: '❓', description: 'Information, procédure…' },
	{
		value: 'bug',
		label: 'Bug',
		emoji: '\u{1F41B}',
		//  Arbitré à l'écran le 30/08/2026. « le site ou l'application » décrivait
		//  le support ; le résident, lui, cherche le NOM de ce qu'il utilise —
		//  et il n'a pas à savoir si sa gêne vient du site ou de la PWA.
		description: 'Pb technique sur 5Hostachy',
	},
];

//: Emoji seul — la pastille de contexte d'une carte. Repli sur 📋 : une catégorie
//: retirée du référentiel ne doit pas laisser une carte sans repère.
export const CATEGORIE_TICKET_EMOJI: Record<string, string> = Object.fromEntries(
	CATEGORIES_TICKET.map((c) => [c.value, c.emoji]),
);

//: « 🛠️ Panne » — la forme complète, celle des filtres, des badges et des choix.
export const CATEGORIE_TICKET_LABELS: Record<string, string> = Object.fromEntries(
	CATEGORIES_TICKET.map((c) => [c.value, `${c.emoji} ${c.label}`]),
);

/** Emoji d'une catégorie, jamais vide. */
export function categorieTicketEmoji(categorie: string | undefined | null): string {
	return CATEGORIE_TICKET_EMOJI[categorie ?? ''] ?? '\u{1F4CB}';
}

/** « 🛠️ Panne », valeur brute à défaut (jamais vide). */
export function categorieTicketLabel(categorie: string | undefined | null): string {
	return CATEGORIE_TICKET_LABELS[categorie ?? ''] ?? categorie ?? '';
}

/** Ce ticket demande-t-il encore du suivi ? */
export function estTicketActif(statut: string | undefined | null): boolean {
	return STATUTS_TICKET_ACTIFS.includes(statut ?? '');
}

/** Ce ticket est-il clos ? — la seule écriture de cette question côté front. */
export function estTicketClos(statut: string | undefined | null): boolean {
	return STATUTS_TICKET_CLOS.includes(statut ?? '');
}

/** Libellé affichable d'un statut, valeur brute à défaut (jamais vide). */
export function statutTicketLabel(statut: string | undefined | null): string {
	return STATUT_TICKET_LABELS[statut ?? ''] ?? statut ?? '';
}

/**
 * Le périmètre d'un ticket tel qu'on l'affiche : le bâtiment de son auteur, à
 * défaut le bâtiment ciblé, à défaut la résidence entière.
 *
 * L'ordre compte — un ticket saisi par un résident du bâtiment 2 concerne le
 * bâtiment 2, même quand il ne cible aucun bâtiment en particulier.
 */
export function ticketScope(t: {
	auteur_batiment_nom?: string | null;
	batiment_id?: number | null;
}): string {
	return t.auteur_batiment_nom ?? (t.batiment_id ? `Bât. ${t.batiment_id}` : 'Résidence');
}

/**
 * Au nom de qui le conseil syndical ouvre un ticket.
 *
 * Le type vivait dans `FormulaireTicket.svelte`, d'où il n'était pas importable :
 * un `export type` dans le `<script>` d'instance d'un composant n'est pas exporté.
 * Il appartient de toute façon au vocabulaire du ticket, pas à l'écran qui le
 * saisit — comme les statuts et les catégories juste au-dessus.
 */
export type ModeSaisiPour = 'moi' | 'resident' | 'exterieur';

// ── Options de publication ───────────────────────────────────────────────────

/**
 * 🔴 LES OPTIONS DE PUBLICATION D'UN TICKET — le pont écran ⇄ objet, écrit ICI.
 *
 * Demandé à l'écran le 05/09/2026 :
 *
 * > « tous les autres options de publication doivent être aussi conservé dans
 * >   l'objet pour les tickets en édition et commentaire »
 * > « pas que Visibilité du ticket »
 *
 * ## Les clés de l'écran ne sont pas les champs du ticket
 *
 * | Option (table `$lib/options-publication`) | Champ du ticket |
 * |---|---|
 * | `epingle` | `epingle` |
 * | `urgente` | `priorite === 'haute'` — ce que la catégorie « Urgence » pose déjà |
 * | `brouillon` (🛡️ « au seul conseil syndical ») | `confidentiel` |
 *
 * `confidentiel` de la table (🔒 « visible du seul périmètre ») **n'est pas
 * proposé** : un ticket l'est déjà. Sa lecture passe par `perimetre_visible`
 * sans `ouvert_a_la_copropriete`, là où une actualité le passe (#339) — la case
 * n'aurait rien restreint, et une case sans effet est une promesse vide.
 *
 * ⚠️ Deux noms se croisent, et c'est le piège de ce fichier : la clé d'écran
 * `brouillon` écrit la colonne `confidentiel`, tandis que la clé d'écran
 * `confidentiel` ne s'applique pas ici. Les deux sens du pont vivent donc côte
 * à côte, pour qu'aucun ne puisse être corrigé sans l'autre.
 */
export const OPTIONS_TICKET: CleOptionPublication[] = [
	'epingle',
	'urgente',
	'brouillon',
	'confidentiel',
];

/**
 * 🔒 Pourquoi « Confidentiel » est MONTRÉ mais VERROUILLÉ sur un ticket.
 *
 * Demandé à l'écran le 05/09/2026 : *« il manque l'option confidentiel sur
 * l'objet Options de publication »*. Elle manquait en effet — et elle n'aurait
 * rien pu restreindre : `ticket_visible` appelle `perimetre_visible` **sans**
 * `ouvert_a_la_copropriete`, là où une actualité le passe (#339). Un ticket se
 * comporte donc déjà comme une actualité confidentielle, toujours.
 *
 * Trois issues étaient possibles, deux sont mauvaises : l'omettre laissait un
 * trou dans une liste de quatre ; la rendre cochable aurait promis une
 * protection que rien n'applique, et le premier qui s'y fie se croit couvert.
 * Elle est donc **cochée et verrouillée**, avec ce motif écrit sous elle — ce
 * n'est pas une case morte, c'est un état de l'objet, et il mérite d'être lu.
 */
export const TICKET_CONFIDENTIEL_ACQUIS =
	'🔒 Un ticket est toujours visible des seuls résidents du périmètre sélectionné : ' +
	'contrairement à une actualité, son ciblage restreint la lecture. Rien à cocher.';

/** L'état COURANT des options — ce que le formulaire reprend à l'ouverture. */
export function optionsDuTicket(ticket: Ticket | null | undefined): {
	epingle: boolean;
	urgente: boolean;
	brouillon: boolean;
} {
	return {
		epingle: ticket?.epingle ?? false,
		urgente: ticket?.priorite === 'haute',
		brouillon: ticket?.confidentiel ?? false,
	};
}

/** Ce qu'on ENVOIE — l'autre sens du même pont. */
export function optionsVersTicket(options: {
	epingle: boolean;
	urgente: boolean;
	brouillon: boolean;
}): { epingle: boolean; urgente: boolean; confidentiel: boolean } {
	return {
		epingle: options.epingle,
		urgente: options.urgente,
		confidentiel: options.brouillon,
	};
}

/*  ══════════════════════════════════════════════════════════════════════════
    L'URGENCE D'UN TICKET — une seule écriture (#820)

    🔴 « Ce ticket est urgent » s'écrivait HUIT fois : cinq ici (`CarteTicket`,
    `FormulaireTicket`, `VueTickets`, `FluxCard`, `flux.ts`) et trois côté API.
    Toutes testaient la catégorie `'urgence'`.

    Or ce fichier écrivait DÉJÀ la vérité contraire, quelques lignes plus haut :
    « `urgente` → `priorite === 'haute'` — ce que la catégorie Urgence pose
    déjà ». Le produit avait deux façons de dire qu'un ticket presse, et huit
    endroits n'en connaissaient qu'une.

    La catégorie a été retirée (migration 0177) : elle répondait à la question du
    DÉLAI dans la liste qui pose celle de la NATURE. Une panne peut être urgente,
    une nuisance aussi — et le résident dont l'ascenseur est bloqué avec
    quelqu'un dedans n'avait aucun moyen de dire les deux.
    ══════════════════════════════════════════════════════════════════════════ */

/** Un ticket presse-t-il ? La priorité le dit, et elle seule. */
export function ticketUrgent(ticket: { priorite?: string | null } | null | undefined): boolean {
	return ticket?.priorite === 'haute';
}
