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
import { parAttribut } from '$lib/table-statuts';

//  Les catégories vivent dans leur propre module depuis le 21/09/2026 (500
//  lignes). `$lib/tickets` reste la porte du domaine : tout écran qui importait
//  `CATEGORIES_TICKET` d'ici continue de le faire.
export * from '$lib/tickets-categories';

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

//: Les six états, dans l'ordre du workflow : c'est celui dans lequel ils
//: s'affichent partout, boutons de la fiche comme listes déroulantes.
//: « À l'AG » et « Chez le prestataire » sont nés le 23/09/2026 (#1092, lot 5) :
//: les colonnes du kanban des événements, qu'aucun état d'affaire ne disait. Leur
//: pastille reprend la couleur de leur colonne (`KANBAN_COLS`).
export const STATUTS_TICKET: readonly StatutTicket[] = [
	{ value: 'ouvert', label: 'Ouvert', emoji: '\u{1F535}', badge: 'badge-blue' },
	{ value: 'en_ag', label: 'À l’AG', emoji: '\u{1F7E3}', badge: 'badge-purple' },
	{ value: 'en_cours', label: 'En cours', emoji: '\u{1F7E1}', badge: 'badge-orange' },
	{
		value: 'chez_prestataire',
		label: 'Chez le prestataire',
		emoji: '\u{1F7E0}',
		badge: 'badge-yellow',
	},
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

//: L'état SANS CYCLE d'une affaire de catégorie « Actualité » (#1091) : affichable,
//: jamais proposé — seule la catégorie y mène. Pendant de `STATUTS_TICKET_SANS_CYCLE`
//: côté serveur ; `test_statuts_tickets.py` tient la concordance.
const STATUTS_TICKET_SANS_CYCLE: Record<string, { label: string; badge: string }> = {
	publie: { label: 'Publiée', badge: 'badge-blue' },
};

export const STATUT_TICKET_LABELS: Record<string, string> = {
	...Object.fromEntries(STATUTS_TICKET.map((s) => [s.value, s.label])),
	...Object.fromEntries(Object.entries(STATUTS_TICKET_HISTORIQUES).map(([v, h]) => [v, h.label])),
	...Object.fromEntries(Object.entries(STATUTS_TICKET_SANS_CYCLE).map(([v, h]) => [v, h.label])),
};

export const STATUT_TICKET_BADGE: Record<string, string> = {
	...Object.fromEntries(STATUTS_TICKET.map((s) => [s.value, s.badge])),
	...Object.fromEntries(Object.entries(STATUTS_TICKET_HISTORIQUES).map(([v, h]) => [v, h.badge])),
	...Object.fromEntries(Object.entries(STATUTS_TICKET_SANS_CYCLE).map(([v, h]) => [v, h.badge])),
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
//  🔴 La notion a QUITTÉ ce fichier le 15/09/2026 : elle sert désormais aux
//  actualités et aux événements autant qu'aux tickets, et la laisser ici
//  aurait fait de « tickets » le domicile d'une règle partagée.
//  Réexporté pour que rien n'ait à changer chez les appelants.
export type { ModeSaisiPour } from '$lib/saisi-pour';

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
/**
 * **Tout ce que la page fait quand une liste de tickets bouge** — un seul objet.
 *
 * 🔴 `ListeTickets` relayait TREIZE événements, et `tickets/+page.svelte` les
 * câblait **deux fois** : une fois pour les tickets actifs, une fois pour les
 * archives. Le fichier le disait lui-même — *« c'est le prix de ce relais ; il se
 * paie à chaque nouvel événement »* — et il s'est payé le 12/09/2026, quand le
 * panneau d'options rapides en a demandé deux de plus.
 *
 * Les événements Svelte ne se transmettent pas en bloc (`{...props}` ne porte que
 * des props) : tant qu'ils sont des `on:`, chaque liste doit les réécrire. En
 * objet, les deux listes passent le même `{gestes}`, et ne peuvent plus diverger.
 *
 * ⚠️ C'est la forme qu'`ActionsActualite` employait déjà (`onCommenter`,
 * `onModifier`, `onOptions`) : l'alignement sur le voisin, pas une exception.
 */
export interface GestesTicket {
	basculer: (t: Ticket) => void;
	evoluerOuvrir: (t: Ticket) => void;
	modifier: (t: Ticket) => void;
	optionsOuvrir: (t: Ticket) => void;
	optionsEnregistrer: (t: Ticket, data: unknown) => void;
	supprimer: (t: Ticket) => void;
	evoluer: (t: Ticket, data: unknown) => void;
	evolModifier: (evolId: number) => void;
	evolCorriger: (t: Ticket, data: unknown) => void;
	evolSupprimer: (e: { ticket: Ticket; evolId: number }) => void;
	evolAnnuler: () => void;
	modifie: (maj: Ticket) => void;
	annuler: () => void;
}

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
	suiviKanban: boolean;
} {
	return {
		epingle: ticket?.epingle ?? false,
		urgente: ticket?.priorite === 'haute',
		brouillon: ticket?.confidentiel ?? false,
		//  ⚠️ `suivi_kanban` n'est PAS une option de publication : elle ne dit pas
		//  qui voit le ticket, mais s'il paraît au tableau de suivi. Elle voyage
		//  pourtant par ce pont, parce que c'est lui que le formulaire emprunte —
		//  et qu'une seconde charge utile serait une seconde occasion d'oublier
		//  un champ (#833, et le défaut du 31/08 sur cinq écrans).
		suiviKanban: ticket?.suivi_kanban ?? false,
	};
}

/** Ce qu'on ENVOIE — l'autre sens du même pont. */
export function optionsVersTicket(options: {
	epingle: boolean;
	urgente: boolean;
	brouillon: boolean;
	suiviKanban: boolean;
}): { epingle: boolean; urgente: boolean; confidentiel: boolean; suivi_kanban: boolean } {
	return {
		epingle: options.epingle,
		urgente: options.urgente,
		confidentiel: options.brouillon,
		suivi_kanban: options.suiviKanban,
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

/*  ── La PRIORITÉ, et ses deux longueurs ─────────────────────────────────────
    🔴 Son vocabulaire vivait dans un ÉCRAN (`tickets/[id]`), en table locale —
    du spécifique, alors que tous les autres états du produit vivent ici. Et la
    carte du ticket en donnait un SECOND rendu, écrit à la main : « ⚡ Urgente »
    là où la fiche dit « Priorité haute ». Deux rendus du même état, aucun qui
    se voie depuis l'autre.

    Ils ne sont PAS fondus en un seul : une carte est dense et ne montre que ce
    qui presse, une fiche décrit. C'est la même distinction que `LIBELLES_STATUT`
    / `LIBELLES_STATUT_ABREGE` dans `$lib/roles` — et elle se DÉCLARE ici, au
    lieu de se découvrir en comparant deux écrans.

    ⚠️ `normale` ne s'affiche NULLE PART : les deux écrans la taisent, chacun à
    sa façon (`!== 'normale'` sur la fiche, `=== 'haute'` sur la carte). Son
    libellé existe quand même, pour que la table couvre l'énumération du
    serveur — `PrioriteTicket` (`api/app/models/tickets.py`).                  */
const PRIORITE = parAttribut({
	basse: { libelle: 'Priorité basse', bref: '', badge: 'badge-gray' },
	normale: { libelle: 'Priorité normale', bref: '', badge: 'badge-gray' },
	haute: { libelle: 'Priorité haute', bref: '⚡ Urgente', badge: 'badge-orange' },
});

/** « Priorité haute » — la forme longue, pour une fiche. */
export const LIBELLE_PRIORITE: Record<string, string> = PRIORITE.libelle;

/** « ⚡ Urgente » — la forme brève, pour une carte. **Vide** quand il n'y a rien
 *  à signaler : c'est ce qui permet à la carte de ne rien afficher sans reposer
 *  la question de son côté. */
export const PRIORITE_BREVE: Record<string, string> = PRIORITE.bref;

/** La teinte de la priorité. */
export const BADGE_PRIORITE: Record<string, string> = PRIORITE.badge;

/** Un ticket presse-t-il ? La priorité le dit, et elle seule.
 *
 *  ⚠️ `CarteTicket` écrivait `ticket.priorite === 'haute'` en toutes lettres —
 *  dans le composant le plus vu du produit, et sous une fonction qui se déclare
 *  le seul endroit où la question se pose. Une règle qui s'annonce unique et
 *  qu'un appelant contourne n'est pas unique : elle est ignorée. */
export function ticketUrgent(ticket: { priorite?: string | null } | null | undefined): boolean {
	return ticket?.priorite === 'haute';
}

/**
 * L'adresse de la FICHE d'une affaire — actualités comprises (#1091).
 *
 * Miroir de `utils/liens.lien_ticket` côté serveur : c'est l'adresse que les
 * courriels et le groupe WhatsApp portent, et celle que « Copier le lien »
 * doit rendre. Écrite une fois ici, jamais recomposée dans un écran.
 */
export function lienTicket(id: number): string {
	return `/tickets/${id}`;
}

/** La catégorie qui fait d'une affaire une actualité (#1091). */
export const CATEGORIE_ACTUALITE = 'actualite';

/**
 * Cette affaire est-elle une actualité ? Miroir de `nature_affaire.est_actualite`
 * côté serveur — la question ne se pose qu'ici, jamais par un `=== 'actualite'`
 * recopié dans un écran.
 */
export function estActualite(t: { categorie?: string | null } | null | undefined): boolean {
	return t?.categorie === CATEGORIE_ACTUALITE;
}
