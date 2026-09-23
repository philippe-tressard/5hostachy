/**
 * **Le formulaire unique d'une affaire** — ce qu'il envoie, et ce qu'il éteint.
 *
 * ## Pourquoi ce module (23/09/2026, arbitré à l'écran avec maquette)
 *
 * Demandé : *« un seul “+ Nouvelle affaire” comprenant toutes les sections
 * Affaires et Actualités, avec une nouvelle catégorie Actualité qui apparaît en
 * premier ; selon le choix de la catégorie, les sections peuvent changer —
 * grisées, pliées, inactives et sans données pour celles inappropriées »*.
 *
 * `FormulaireTicket` et `FormulaireActualite` n'en font plus qu'un. Ce que la
 * NATURE de l'affaire change — quelles sections sont actives, quels champs
 * partent — s'écrit ici, pur et sans écran, et non en `{#if}` dispersés dans
 * le composant : c'est la même question posée à l'affichage et à l'envoi, et
 * deux écritures divergeraient au premier changement.
 *
 * ## « Sans données »
 *
 * Une section inactive n'est pas seulement grisée : ce qu'elle portait NE PART
 * PAS. `chargeUtileAffaire` n'emporte que ce que la nature appelle, et efface
 * ce qu'elle n'appelle plus (le public visé d'une actualité devenue affaire
 * suivie, le 🛡️ d'une affaire devenue actualité) — sinon l'objet garderait en
 * base une valeur qu'aucun écran ne montre plus.
 */
import type { Ticket } from '$lib/api';
import type { ConditionInactive, Etat, IdSection, NatureAffaire } from '$lib/entites/types';
import { motifInactif } from '$lib/entites/types';
import { TICKET } from '$lib/entites/ticket';
import { concerneTousLesResidents } from '$lib/destinataires';
import { depuisChampLocal } from '$lib/date';
import { lotDepuisSaisie, type SaisieSaisiPour } from '$lib/saisi-pour';
import { CATEGORIES_TICKET, estActualite, optionsVersTicket } from '$lib/tickets';

/** La nature d'une catégorie : Actualité informe, toute autre se suit. */
export function natureDe(categorie: string): NatureAffaire {
	return estActualite({ categorie }) ? 'actualite' : 'suivie';
}

/** Les sections que la nature éteint — celles qui ont un motif déclaré. */
const SECTIONS_ETEIGNABLES: readonly IdSection[] = [
	'equipement',
	'suivi',
	'intervenant',
	'destinataires',
];

/** Une catégorie du bâti — celles du carnet, au liseré doré (`carnet`). */
export function estBati(categorie: string): boolean {
	return CATEGORIES_TICKET.some((c) => c.value === categorie && c.carnet);
}

/** La catégorie de la récurrence : un Entretien seul se répète (#1092). */
export const CATEGORIE_ENTRETIEN = 'entretien';

/** Le motif de chaque section inactive, pour cet état, cette catégorie et ce rôle. */
export function sectionsInactives(
	etat: Etat,
	categorie: string,
	estCS = true,
): Partial<Record<IdSection, string>> {
	//  Dans l'ordre : la nature, puis le rôle, puis la catégorie (`motifInactif`).
	const conditions: ConditionInactive[] = [natureDe(categorie)];
	if (!estCS) conditions.push('resident');
	if (categorie && !estBati(categorie)) conditions.push('horsBati');
	const inactives: Partial<Record<IdSection, string>> = {};
	for (const id of SECTIONS_ETEIGNABLES) {
		const motif = motifInactif(TICKET, etat, id, conditions);
		if (motif) inactives[id] = motif;
	}
	return inactives;
}

/** Tout ce que l'écran a saisi — la charge utile en est DÉRIVÉE, jamais recopiée. */
export interface SaisieAffaire {
	titre: string;
	description: string;
	assisteIA: boolean;
	categorie: string;
	statut: string;
	options: { epingle: boolean; urgente: boolean; brouillon: boolean; suiviKanban: boolean };
	perimetreCible: string[];
	publicCible: string[];
	reservePerimetre: boolean;
	debut: string;
	fin: string;
	photosUrls: string[];
	fichiersUrls: string[];
	destinataireSyndic: boolean;
	destinataireCs: boolean;
	partagerWhatsapp: boolean;
	envoyerAuteur: boolean;
	annonceHall: boolean;
	saisiPour: SaisieSaisiPour;
	prestataireId: number | null;
	frequenceType: string;
	frequenceValeur: number | string | null;
}

/**
 * Ce que le formulaire envoie — à la création (`POST`) comme à la correction
 * (`PATCH`).
 *
 * ⚠️ Les droits ne se décident pas ici : le serveur refuse ou ignore ce qu'un
 * résident n'a pas le droit de poser. Ce module évite seulement d'envoyer ce
 * qui ferait échouer une correction légitime (un 403 sur `confidentiel`).
 *
 * 🔴 L'URGENCE part pour TOUT LE MONDE. Elle ne partait que pour le conseil à
 * la création : un résident cochait 🚨, l'avertissement « 15 · 17 · 18 »
 * s'affichait, et l'affaire arrivait en priorité normale — alors que le
 * serveur l'accepte de lui depuis #820. Trouvé en écrivant ce module.
 */
export function chargeUtileAffaire(
	s: SaisieAffaire,
	contexte: { creation: boolean; estCS: boolean },
): Record<string, unknown> {
	const actualite = natureDe(s.categorie) === 'actualite';
	const charge: Record<string, unknown> = {
		titre: s.titre.trim(),
		description: s.description,
		categorie: s.categorie,
		perimetre_cible: s.perimetreCible,
		debut: depuisChampLocal(s.debut),
		fin: depuisChampLocal(s.fin),
		photos_urls: s.photosUrls,
		fichiers_urls: s.fichiersUrls,
		urgente: s.options.urgente,
		//  « Je n'en dis rien » en correction : la marque ne s'efface pas.
		assiste_ia: contexte.creation ? s.assisteIA : s.assisteIA || undefined,
	};
	//  La diffusion part à la création pour tous (le serveur trie), et en
	//  correction pour le conseil seul — il est le seul à la voir rouverte.
	if (contexte.creation || contexte.estCS) {
		Object.assign(charge, {
			destinataire_syndic: s.destinataireSyndic,
			destinataire_cs: s.destinataireCs,
			partager_whatsapp: s.partagerWhatsapp,
		});
	}
	if (contexte.creation) charge.envoyer_auteur = s.envoyerAuteur;
	if (!contexte.estCS) return charge;

	Object.assign(charge, lotDepuisSaisie(s.saisiPour));
	//  Intervenant et récurrence : envoyés à vide hors de leur catégorie — le
	//  serveur les efface de toute façon (`utils/intervenant`), l'écran le dit.
	const entretien = s.categorie === CATEGORIE_ENTRETIEN;
	Object.assign(charge, {
		prestataire_id: estBati(s.categorie) ? s.prestataireId : null,
		frequence_type: entretien && s.frequenceType ? s.frequenceType : null,
		frequence_valeur: entretien && s.frequenceType ? Number(s.frequenceValeur) || null : null,
	});
	if (actualite) {
		//  Pas de suivi : ni état, ni 🛡️, ni kanban — effacés s'ils venaient
		//  d'une affaire suivie. À qui l'on parle, l'Accès et l'affiche, oui.
		Object.assign(charge, {
			epingle: s.options.epingle,
			confidentiel: false,
			suivi_kanban: false,
			public_cible: concerneTousLesResidents(s.publicCible) ? [] : s.publicCible,
			reserve_perimetre: s.reservePerimetre,
			annonce_hall: s.annonceHall,
		});
	} else {
		//  Une affaire suivie : son état et ses options ; le public visé et
		//  l'Accès d'une actualité sont effacés s'ils en venaient.
		//  ⚠️ Une actualité repassée en suivi porte encore `publie`, que le
		//  serveur refuse à une affaire suivie (422) : elle repart « Ouvert ».
		Object.assign(charge, optionsVersTicket(s.options), {
			statut: s.statut === 'publie' ? 'ouvert' : s.statut,
			public_cible: [],
			reserve_perimetre: false,
		});
	}
	return charge;
}

/**
 * Ce qu'une correction EFFACE en changeant la nature de l'affaire — à dire
 * avant d'enregistrer (arbitré le 23/09/2026 : catégorie modifiable, données
 * des sections devenues inappropriées effacées après confirmation).
 *
 * Vide quand la nature ne change pas, ou quand il n'y avait rien à perdre.
 */
export function pertesAuChangement(avant: Ticket, apres: SaisieAffaire): string[] {
	const pertes: string[] = [];
	if (avant.prestataire_id && !estBati(apres.categorie)) pertes.push('l’intervenant');
	if (avant.frequence_type && apres.categorie !== CATEGORIE_ENTRETIEN) pertes.push('la récurrence');
	const etait = natureDe(avant.categorie);
	if (etait === natureDe(apres.categorie)) return pertes;
	if (etait === 'actualite') {
		if (!concerneTousLesResidents(avant.public_cible ?? [])) pertes.push('le public visé');
		if (avant.reserve_perimetre) pertes.push('la réserve au périmètre (🔒)');
	} else {
		pertes.push('l’état de suivi');
		if (avant.confidentiel) pertes.push('la réserve au conseil syndical (🛡️)');
		if (avant.suivi_kanban) pertes.push('l’inscription au kanban');
	}
	return pertes;
}
