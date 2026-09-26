/**
 * La pastille de lecture d'une AFFAIRE — `$lib/lecture` appliqué à l'objet.
 *
 * Séparé de `$lib/lecture` pour une seule raison : trancher « le périmètre
 * est-il restreint ? » demande l'ARBRE des périmètres, un état chargé à
 * l'exécution que le contrôle `lint:lecture` n'a pas. Le calcul reste pur
 * là-bas ; ici, on ne fait que lui fournir ses entrées.
 */
import { batimentsCibles, concerneTous } from '$lib/perimetres';
import { destinatairesParDefaut, lectureDe, type Lecture } from '$lib/lecture';
import { estActualite } from '$lib/tickets';
import type { Ticket } from '$lib/api';

/** Ce que le FORMULAIRE sait de la nature — la pastille de sa section. */
export type NatureLue = {
	actualite: boolean;
	datee: boolean;
	enAg: boolean;
	categorie?: string;
	dansBatiments?: boolean;
};

/**  Chaque code du périmètre descend-il d'un bâtiment ? Miroir du test de
 *   `destinataires_par_defaut` au serveur (#1343). Vide : non. */
export function dansDesBatiments(perimetre: string[] | null | undefined): boolean {
	return !!perimetre?.length && perimetre.every((c) => batimentsCibles([c]).length > 0);
}

/**
 * Le périmètre vise-t-il MOINS que la copropriété ? Miroir de
 * `a_portee_globale` côté serveur — la même question que la case 🔒 pose
 * (`CaseReservePerimetre`). Vide = aucune restriction, comme au serveur.
 */
export function perimetreRestreint(perimetre: string[] | null | undefined): boolean {
	return !!perimetre && perimetre.length > 0 && !concerneTous(perimetre);
}

/** Qui lit cette affaire, telle qu'elle est enregistrée. */
/**  Ce qui décide de la lecture d'une affaire, hors de ses choix — d'un objet
 *   enregistré comme d'une saisie en cours (`FormulaireTicket`). */
export function natureLue(s: {
	categorie?: string | null;
	debut?: string | null;
	statut?: string | null;
	perimetre?: string[] | null;
}): NatureLue {
	return {
		actualite: estActualite(s),
		datee: !!s.debut,
		enAg: s.statut === 'en_ag',
		categorie: s.categorie ?? undefined,
		dansBatiments: dansDesBatiments(s.perimetre),
	};
}

export function natureDuTicket(t: Ticket): NatureLue {
	return natureLue({ ...t, perimetre: t.perimetre_cible });
}

/**  Les Destinataires qu'une Suite présélectionne sur une AFFAIRE sans choix
 *   du conseil (#1343) — `null` pour une actualité, qui a les siens. */
export function destinatairesParDefautDuTicket(t: Ticket): string[] | null {
	return estActualite(t) ? null : destinatairesParDefaut(natureDuTicket(t));
}

export function lectureDuTicket(t: Ticket): Lecture {
	return lectureDe({
		...natureDuTicket(t),
		confidentiel: t.confidentiel === true,
		publicCible: t.public_cible,
		perimetreRestreint: perimetreRestreint(t.perimetre_cible),
		reservePerimetre: t.reserve_perimetre === true,
	});
}
