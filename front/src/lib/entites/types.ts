/**
 * Le CADRE d'interface, en types : une entité, quatre rendus.
 *
 * Décidé par l'utilisateur le 17/08/2026 (#430), après le relevé des 42 couples
 * menu/entité. Ce fichier ne décrit AUCUNE entité — il décrit la forme que prend
 * la description d'une entité. Les entités elles-mêmes vivent à côté
 * (`ticket.ts`, puis `actualite.ts`, `evenement.ts`…).
 *
 * ## Ce qu'on a mesuré, et qui a fait naître ce fichier
 *
 * Ce que les quatre états ont en commun n'est pas « le formulaire », c'est **la
 * description de l'entité** : la liste de ses sections, leur ordre, ce qu'elles
 * portent, leur caractère requis. Ce qui diffère est le **rendu** (lecture /
 * saisie), la **valeur** (défaut / existante / héritée) et le **geste**
 * (POST / PATCH / évolution tracée).
 *
 * Sans déclaration, chaque état réinvente ce que l'autre portait déjà : **13
 * éditions sur 23 le faisaient**, et **5 seulement** portaient une raison écrite.
 * C'est exactement ce que `lib/pages.ts` a réglé pour l'identité des pages
 * (#401, #420) — une table unique, et un contrôle qui refuse qu'on la recopie.
 *
 * ## R4 est la clé de voûte : une divergence SANS MOTIF est refusée
 *
 * Trois motifs, trois seulement :
 *
 *   • `geste`  — la section est un ACTE qui n'a pas lieu dans cet état. La
 *                Diffusion en édition : une correction n'est pas une nouvelle,
 *                et rejouer les canaux renverrait un message à chaque faute de
 *                frappe rattrapée (incident du triple envoi WhatsApp, 14/08/2026).
 *   • `hérité` — la valeur vient de l'objet porteur. Le titre d'un ticket dans
 *                une évolution : l'entrée se rattache au ticket, elle ne le
 *                renomme pas.
 *   • `api`    — ⚠️ **motif de DETTE, jamais de conception.** Il DOIT citer un
 *                ticket. Une contrainte serveur qu'on subit se note pour être
 *                corrigée, pas pour être entérinée.
 *
 * `npm run lint:etats` refuse une divergence sans motif, un motif `api` sans
 * ticket, une section rendue hors déclaration et un ordre qui s'écarte des neuf.
 *
 * ## Ce fichier ne se recopie pas
 *
 * Ni l'ordre des sections, ni leurs libellés, ni la liste des états ne
 * s'écrivent ailleurs. Une seconde table diverge de la première au premier lot
 * suivant — c'est déjà arrivé aux périmètres (#316), aux canaux de notification,
 * aux statuts de ticket (#415) et aux pages (#401).
 */

/** Les neuf sections. L'identifiant est technique ; le libellé est à l'écran. */
export type IdSection =
	| 'titre'
	| 'specifiques'
	| 'workflow'
	| 'perimetre'
	| 'destinataires'
	| 'description'
	| 'photos'
	| 'documents'
	| 'diffusion';

/**
 * 🔴 **L'ordre des neuf sections — il ne se discute plus, et il vaut aussi pour
 * l'AFFICHAGE** (mesuré : l'affichage n'empruntait le motif d'aucun formulaire,
 * 0 cas sur 42).
 *
 * 🔴 Une section ne se fusionne JAMAIS avec une autre, dans aucun rendu. Neuf
 * déclarées, neuf rendues — même voisines, même courtes, même héritées de la
 * même valeur. Fusionner « Photos · Documents » parce qu'elles tiennent sur une
 * ligne, c'est créer une dixième section que rien ne déclare.
 */
export const SECTIONS_ORDRE: readonly IdSection[] = [
	'titre',
	'specifiques',
	'workflow',
	'perimetre',
	'destinataires',
	'description',
	'photos',
	'documents',
	'diffusion',
];

/**
 * Le libellé de chaque section, écrit UNE fois.
 *
 * ⚠️ *Destinataires* (5) et *Diffusion* (9) parlent tous deux de « à qui »,
 * séparés par quatre sections : les intitulés doivent lever l'ambiguïté —
 * Destinataires = qui est concerné **dans l'application** ; Diffusion = par
 * quels canaux on prévient **à l'extérieur**.
 */
export const SECTIONS_LIBELLE: Readonly<Record<IdSection, string>> = {
	titre: 'Titre',
	specifiques: 'Champs spécifiques',
	workflow: 'Workflow',
	perimetre: 'Périmètre',
	destinataires: 'Destinataires',
	description: 'Description',
	photos: 'Photos',
	documents: 'Documents',
	diffusion: 'Diffusion',
};

/** Les quatre rendus d'une même entité. */
export type Etat = 'affichage' | 'creation' | 'edition' | 'evolution';

export const ETATS: readonly Etat[] = ['affichage', 'creation', 'edition', 'evolution'];

/** Les trois motifs de divergence, et il n'y en a pas d'autre (R4). */
export type Motif = 'geste' | 'hérité' | 'api';

export interface Divergence {
	motif: Motif;
	/** Pourquoi, en une phrase — lisible en revue comme en lot suivant. */
	explication: string;
	/** Forme « #431 ». **Obligatoire** quand `motif === 'api'` : une dette a un ticket. */
	ticket?: string;
}

export interface SectionDeclaree {
	id: IdSection;
	/** Ce que la section porte à l'écran. Vide seulement si `sansObjet`. */
	objet?: string;
	/** Marqué par `*` et rien d'autre — jamais « (optionnel) » (R3). */
	requis?: boolean;
	/**
	 * L'intitulé réellement affiché, quand il diffère du nom de la section.
	 *
	 * Une section qui ne contient qu'UN champ ne répète pas son nom : le titre de
	 * section DEVIENT le libellé du champ (`SectionFormulaire`). « Champs
	 * spécifiques » ne s'écrit jamais à l'écran — c'est « Saisi pour » qui s'y
	 * lit. R3 demande que ce libellé soit le même d'un formulaire à l'autre :
	 * il se déclare donc ici, et `lint:etats` refuse tout autre intitulé.
	 */
	titreEcran?: string;
	/**
	 * Les états où la section est ABSENTE, chacun avec son motif.
	 * Une absence non déclarée ici est un écart : `lint:etats` la refuse.
	 */
	absente?: Partial<Record<Etat, Divergence>>;
	/**
	 * L'entité ne porte PAS cette notion, dans aucun état — et voici pourquoi.
	 *
	 * À distinguer d'une divergence : « un sondage n'a pas de pièces jointes »
	 * n'est pas un écart entre deux états, c'est une absence de notion. Le
	 * contrat n'est pas « toutes les entités ont tout », c'est « quand une
	 * entité a une de ces notions, elle est à la même place et a la même tête ».
	 */
	sansObjet?: string;
}

export interface EntiteDeclaree {
	/** Identifiant technique — `ticket`, `actualite`… */
	id: string;
	/** Nom de l'entité à l'écran. */
	libelle: string;
	/** Les neuf sections, dans l'ordre de `SECTIONS_ORDRE`. */
	sections: readonly SectionDeclaree[];
}

/** La déclaration d'une section, ou `undefined` si l'entité est incomplète. */
export function section(
	entite: EntiteDeclaree,
	id: IdSection,
): SectionDeclaree | undefined {
	return entite.sections.find((s) => s.id === id);
}

/**
 * Cette section est-elle rendue dans cet état ?
 *
 * ⚠️ **C'est le SEUL portail.** Un écran qui décide lui-même (`{#if !modeEdition}`)
 * rouvre la divergence silencieuse que le cadre supprime — `lint:etats` refuse
 * qu'une section soit gouvernée par autre chose que cet appel.
 */
export function sectionPresente(
	entite: EntiteDeclaree,
	etat: Etat,
	id: IdSection,
): boolean {
	const s = section(entite, id);
	if (!s || s.sansObjet) return false;
	return !s.absente?.[etat];
}

/** Les sections rendues dans cet état, **dans l'ordre déclaré**. */
export function sectionsDe(entite: EntiteDeclaree, etat: Etat): SectionDeclaree[] {
	return entite.sections.filter((s) => sectionPresente(entite, etat, s.id));
}

/** La divergence déclarée pour cette section dans cet état, s'il y en a une. */
export function divergence(
	entite: EntiteDeclaree,
	etat: Etat,
	id: IdSection,
): Divergence | null {
	return section(entite, id)?.absente?.[etat] ?? null;
}
