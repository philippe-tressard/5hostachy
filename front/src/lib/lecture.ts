/**
 * **Qui LIT une affaire ou une actualité** — la pastille de lecture, calculée
 * une fois (lot 1, arbitré le 25/09/2026, maquette « Anneau de lecture »).
 *
 * ## Le besoin
 *
 * > « cet état est important pour connaître qui peut le voir (forcément le
 * >   lecteur, mais qui d'autre ?) »
 *
 * La réponse était éparpillée : la case 🔒 du Périmètre, les pastilles de
 * Destinataires, la case 🛡️ de Mise en avant — plus des règles du serveur que
 * rien n'affichait (une affaire n'est pas lue des locataires). La pastille les
 * RÉSUME en un seul objet : une ou des icônes, un libellé court (carte) ou long
 * (section), et le cadenas quand le périmètre est réservé.
 *
 * ## Trois restrictions, pas une de plus
 *
 * 1. **Confidentielle** — le conseil syndical seul. Elle passe outre tout le
 *    reste : une seule pastille « CS ».
 * 2. **Périmètre réservé** — oui ou non. LEQUEL, le 🔹 d'à côté le dit déjà.
 * 3. **Profils** — ceux que Destinataires vise (actualité), ou la règle des
 *    affaires : tous sauf les locataires.
 *
 * ⚠️ **Ce n'est qu'un résumé : c'est le serveur qui décide** (`ticket_visible`).
 * Les deux écritures sont tenues par UNE attente,
 * `api/tests/donnees/lecture_pastille.json` : `test_lecture_pastille.py`
 * l'exécute contre la règle, `npm run lint:lecture` contre ce fichier. Une
 * pastille qui annoncerait « Tous » là où les locataires ne lisent pas mentirait
 * à chaque lecteur, sans que rien casse — d'où le contrôle.
 *
 * 🔴 Ce module n'importe que `$lib/destinataires` : il doit s'exécuter HORS du
 * site, dans le contrôle. Le périmètre lui arrive donc déjà tranché
 * (`perimetreRestreint`) — l'arbre des périmètres est un état chargé à
 * l'exécution, que le contrôle n'a pas.
 */
import {
	TOUS_LES_RESIDENTS,
	codesDestinataires,
	concerneTousLesResidents,
	reserveAuConseil,
} from '$lib/destinataires';

/**
 * Les PROFILS de lecteurs, au pluriel — la nomenclature arbitrée le 25/09/2026
 * (`ux-patterns` §2 bis). L'ordre est celui de l'affichage.
 *
 * `statut` est celui du compte (`StatutUtilisateur`) : c'est par lui que le
 * contrôle confronte ce résumé à la règle du serveur. Les « Bailleurs » sont les
 * comptes mandataires — agence, gestionnaire — qui louent par délégation d'un
 * copropriétaire ; les aidants n'en sont pas, ils héritent du droit de celui
 * qu'ils aident.
 */
export const PROFILS = [
	{
		code: 'occupants',
		statut: 'copropriétaire_résident',
		court: 'Occupants',
		long: 'Copropriétaires occupants',
		icone: 'home',
	},
	{
		code: 'copro_bailleurs',
		statut: 'copropriétaire_bailleur',
		court: 'Copro-bailleurs',
		long: 'Copropriétaires bailleurs',
		icone: 'building-2',
	},
	{
		code: 'bailleurs',
		statut: 'mandataire',
		court: 'Bailleurs',
		long: 'Bailleurs (mandataires)',
		icone: 'heart-handshake',
	},
	{
		code: 'locataires',
		statut: 'locataire',
		court: 'Locataires',
		long: 'Locataires',
		icone: 'user',
	},
] as const;

export type Profil = (typeof PROFILS)[number]['code'];

const TOUS_PROFILS: Profil[] = PROFILS.map((p) => p.code);

/**
 * Ce que chaque code de Destinataires fait LIRE — miroir de
 * `public_cible_visible` côté serveur. Un code inconnu ne fait lire personne :
 * la règle refuse ce qu'elle ne reconnaît pas. `conseil_syndical` non plus —
 * le conseil lit TOUT, ce n'est pas un profil qu'on ajoute.
 */
const PROFILS_DU_CODE: Record<string, Profil[]> = {
	résidents: TOUS_PROFILS,
	copropriétaires: ['occupants', 'copro_bailleurs'],
	copropriétaires_occupants: ['occupants'],
	bailleurs: ['copro_bailleurs'],
	mandataires: ['bailleurs'],
	locataires: ['locataires'],
};

/**
 * Une affaire suivie : les COPROPRIÉTAIRES seuls, occupants et bailleurs
 * (`ticket_visible`) — ni locataires, ni mandataires depuis #1311 (25/09/2026) —,
 * sauf une affaire DATÉE (au calendrier), que tous ceux de son périmètre
 * lisent, hors « En AG » (#1269).
 */
const PROFILS_AFFAIRE: Profil[] = ['occupants', 'copro_bailleurs'];

type Vocable = { cle: string; icones: string[]; court: string; long: string; qui?: string };

/** Les combinaisons qui ont un NOM ; les autres se composent. */
const NOMMEES: (Vocable & { profils: Profil[] })[] = [
	{ cle: 'tous', profils: TOUS_PROFILS, icones: ['users-round'], court: 'Tous', long: 'Tous' },
	{
		cle: 'residents',
		profils: ['occupants', 'locataires'],
		icones: ['home', 'user'],
		court: 'Résidents',
		long: 'Résidents (occupants et locataires)',
	},
	//  🔴 UN ensemble, UN nom (#1311, 25/09/2026) : c'est désormais aussi celui
	//  d'une affaire suivie, qui disait « Tous sauf locataires » tant que les
	//  mandataires la lisaient. « Propriétaires » (actualités) et « Copropriétaires
	//  seuls » (demandé pour les affaires) auraient nommé deux fois les mêmes
	//  lecteurs ; arbitré : « Copropriétaires ».
	{
		cle: 'coproprietaires',
		profils: PROFILS_AFFAIRE,
		icones: ['key-round'],
		court: 'Copropriétaires',
		long: 'Copropriétaires (occupants et bailleurs)',
	},
];

const CS: Vocable = {
	cle: 'cs',
	icones: ['shield-check'],
	court: 'CS',
	long: 'Conseil syndical seul',
};

const minuscule = (t: string) => t.charAt(0).toLocaleLowerCase('fr') + t.slice(1);

function vocableDe(profils: Profil[]): Vocable {
	const cle = [...profils].sort().join();
	const nommee = NOMMEES.find((n) => [...n.profils].sort().join() === cle);
	if (nommee) return nommee;
	const ps = PROFILS.filter((p) => profils.includes(p.code));
	return {
		cle: ps.map((p) => p.code).join('+'),
		icones: ps.map((p) => p.icone),
		court: ps.map((p) => p.court).join(' + '),
		long: ps.map((p, i) => (i ? minuscule(p.long) : p.long)).join(' et '),
		qui: 'les ' + ps.map((p) => minuscule(p.long)).join(' et les '),
	};
}

/** Ce que l'objet dit de ses lecteurs. */
export interface EntreeLecture {
	/** Une actualité (vrai) ou une affaire suivie. */
	actualite: boolean;
	/** 🛡️ Le conseil syndical seul (`ticket.confidentiel`). */
	confidentiel: boolean;
	/** Destinataires — une affaire ne les lit que s'ils ont été choisis (#1343). */
	publicCible: string[] | string | null | undefined;
	/** Le périmètre vise-t-il MOINS que la copropriété ? Tranché par l'appelant. */
	perimetreRestreint: boolean;
	/** 🔒 « Réservé au périmètre sélectionné » — le choix d'une actualité. */
	reservePerimetre: boolean;
	/** Une date de début : l'affaire paraît au calendrier (`natures`). */
	datee?: boolean;
	/** Le suivi est « En AG » — ce qui la retire aux locataires. */
	enAg?: boolean;
	/** La catégorie d'une affaire, et son périmètre dans des bâtiments (#1343). */
	categorie?: string;
	dansBatiments?: boolean;
}

export interface Lecture extends Vocable {
	/** Les profils qui lisent, dans l'ordre de `PROFILS`. Vide : le conseil seul. */
	profils: Profil[];
	/** Le cadenas : seuls ceux du périmètre lisent. */
	perimetreReserve: boolean;
	/** La phrase de l'infobulle : « Lue par… ». */
	phrase: string;
	/** Ceux qui ne lisent pas : « Pas les locataires, ni… ». */
	exclus: string;
	/** Personne n'est exclu : rien sur la carte, « Tous » dans la section. */
	parDefaut: boolean;
	/** Le piège d'une actualité : un périmètre choisi mais non réservé. */
	avertissement: string;
}

/** Le titre de la pastille longue : son libellé, et le cadenas en toutes lettres. */
export function titreLecture(l: Lecture): string {
	return l.long + (l.perimetreReserve ? ' · du périmètre seulement' : '');
}

/**
 * Les Destinataires qu'une affaire a SANS choix du conseil (#1343) — ce que
 * sa nature décide, et que les pastilles présélectionnent : les
 * copropriétaires (occupants et bailleurs) ; « Tous » pour une affaire datée
 * hors AG, que le calendrier montre aux locataires. Une actualité : « Tous ».
 *
 * La règle vit au serveur (`ticket_visible`) ; `lecture_pastille.json` tient
 * les deux écritures d'accord.
 */
export function destinatairesParDefaut(n: {
	actualite?: boolean;
	datee?: boolean;
	enAg?: boolean;
	/** La catégorie d'une affaire — une Panne a sa propre règle. */
	categorie?: string;
	/** Chaque code du périmètre descend-il d'un bâtiment ? Tranché par l'appelant. */
	dansBatiments?: boolean;
}): string[] {
	if (n.actualite) return [TOUS_LES_RESIDENTS];
	//  Arbitré à l'écran le 26/09/2026 : une Panne concerne ceux qui VIVENT
	//  dans le bâtiment — occupants et locataires, pas les bailleurs ; hors
	//  bâtiment (parking, espaces verts…), tout le monde. Miroir de
	//  `destinataires_par_defaut` (`utils/visibility/objets.py`).
	if (n.categorie === 'panne')
		return n.dansBatiments ? ['copropriétaires_occupants', 'locataires'] : [TOUS_LES_RESIDENTS];
	return n.datee && !n.enAg ? [TOUS_LES_RESIDENTS] : ['copropriétaires_occupants', 'bailleurs'];
}

export function lectureDe(e: EntreeLecture): Lecture {
	//  Une affaire lit ses Destinataires quand le conseil en a CHOISI (#1343) ;
	//  vides, ceux de sa nature — comme `ticket_visible`.
	const explicites = codesDestinataires(e.publicCible);
	const codes = e.actualite || explicites.length ? explicites : destinatairesParDefaut(e);
	const csSeul = e.confidentiel || reserveAuConseil(codes);
	let profils: Profil[] = [];
	if (!csSeul) {
		if (concerneTousLesResidents(codes)) profils = TOUS_PROFILS;
		else {
			const vises = new Set(codes.flatMap((c) => PROFILS_DU_CODE[c] ?? []));
			profils = TOUS_PROFILS.filter((p) => vises.has(p));
		}
	}
	//  Une actualité s'ouvre à la copropriété sauf réserve ; une affaire, jamais.
	const perimetreReserve =
		profils.length > 0 && e.perimetreRestreint && (e.actualite ? e.reservePerimetre : true);
	const v = profils.length ? vocableDe(profils) : CS;
	const tous = v.cle === 'tous';

	let phrase: string;
	const pas: string[] = [];
	if (!profils.length) {
		phrase = 'Personne d’autre que le conseil syndical ne la lit, à part son auteur.';
	} else {
		const ou = perimetreReserve ? ', dans le périmètre seulement.' : '.';
		phrase = tous
			? `Lue par tous${ou}`
			: `Lue par ${v.qui ?? 'les ' + minuscule(v.long)}${perimetreReserve ? ou : ', dans toute la copropriété.'}`;
		for (const p of PROFILS) if (!profils.includes(p.code)) pas.push('les ' + minuscule(p.long));
		if (perimetreReserve) pas.push('les personnes hors du périmètre');
	}
	return {
		...v,
		profils,
		perimetreReserve,
		phrase,
		exclus: pas.length ? `Pas ${pas.join(', ni ')}.` : '',
		parDefaut: tous && !perimetreReserve,
		avertissement:
			e.actualite && profils.length && e.perimetreRestreint && !e.reservePerimetre
				? 'Le périmètre est choisi mais pas réservé : toute la copropriété la lira.'
				: '',
	};
}
