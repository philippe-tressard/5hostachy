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
	...Object.fromEntries(
		Object.entries(STATUTS_TICKET_HISTORIQUES).map(([v, h]) => [v, h.label]),
	),
};

export const STATUT_TICKET_BADGE: Record<string, string> = {
	...Object.fromEntries(STATUTS_TICKET.map((s) => [s.value, s.badge])),
	...Object.fromEntries(
		Object.entries(STATUTS_TICKET_HISTORIQUES).map(([v, h]) => [v, h.badge]),
	),
};

//: Un ticket dans l'un de ces états ne demande plus de suivi : il quitte la liste
//: active pour l'Historique, et sort des relances. `fermé` y figure parce que
//: l'affichage d'un ticket ancien ne doit pas dépendre du succès d'une migration.
export const STATUTS_TICKET_CLOS: readonly string[] = ['résolu', 'annulé', 'fermé'];

//: Le complément : un ticket qui demande encore du suivi. La question s'écrivait
//: `t.statut === 'ouvert' || t.statut === 'en_cours'`, deux fois dans le même
//: fichier — trouvée par le garde-fou, pas à la relecture.
//: Déclaré après `STATUTS_TICKET_CLOS`, dont il dépend à l'initialisation.
export const STATUTS_TICKET_ACTIFS: readonly string[] = STATUTS_TICKET.map(
	(s) => s.value,
).filter((v) => !STATUTS_TICKET_CLOS.includes(v));

//: Le filtre rapide des deux listes (Tickets, Espace CS) ne propose QUE les états
//: actifs : « Tous » couvre le reste, et les clos ont leur section Historique.
//: C'est un sous-ensemble volontaire — mais il tire sa pastille et son libellé
//: d'ici, sinon c'est une liste de plus qui se réécrit à la main.
export const STATUTS_TICKET_FILTRE = STATUT_TICKET_OPTIONS.filter((o) =>
	STATUTS_TICKET_ACTIFS.includes(o.value),
);

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

export const CATEGORIES_TICKET: readonly CategorieTicket[] = [
	{ value: 'panne', label: 'Panne', emoji: '\u{1F6E0}️', description: 'Équipement défectueux, ascenseur, chauffage…' },
	{ value: 'nuisance', label: 'Nuisance', emoji: '\u{1F4E2}', description: 'Bruit, odeur, parking…' },
	{ value: 'question', label: 'Question', emoji: '❓', description: 'Information, procédure…' },
	{ value: 'urgence', label: 'Urgence', emoji: '\u{1F6A8}', description: 'Inondation, panne majeure, danger immédiat' },
	{ value: 'bug', label: 'Bug', emoji: '\u{1F41B}', description: 'Problème technique sur le site ou l’application' },
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
export function ticketScope(t: { auteur_batiment_nom?: string | null; batiment_id?: number | null }): string {
	return t.auteur_batiment_nom ?? (t.batiment_id ? `Bât. ${t.batiment_id}` : 'Résidence');
}
