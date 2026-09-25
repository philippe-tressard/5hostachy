/**
 * La pastille de lecture d'une AFFAIRE — `$lib/lecture` appliqué à l'objet.
 *
 * Séparé de `$lib/lecture` pour une seule raison : trancher « le périmètre
 * est-il restreint ? » demande l'ARBRE des périmètres, un état chargé à
 * l'exécution que le contrôle `lint:lecture` n'a pas. Le calcul reste pur
 * là-bas ; ici, on ne fait que lui fournir ses entrées.
 */
import { concerneTous } from '$lib/perimetres';
import { lectureDe, type Lecture } from '$lib/lecture';
import { estActualite } from '$lib/tickets';
import type { Ticket } from '$lib/api';

/** Ce que le FORMULAIRE sait de la nature — la pastille de sa section. */
export type NatureLue = { actualite: boolean; datee: boolean; enAg: boolean };

/**
 * Le périmètre vise-t-il MOINS que la copropriété ? Miroir de
 * `a_portee_globale` côté serveur — la même question que la case 🔒 pose
 * (`CaseReservePerimetre`). Vide = aucune restriction, comme au serveur.
 */
export function perimetreRestreint(perimetre: string[] | null | undefined): boolean {
	return !!perimetre && perimetre.length > 0 && !concerneTous(perimetre);
}

/** Qui lit cette affaire, telle qu'elle est enregistrée. */
export function lectureDuTicket(t: Ticket): Lecture {
	return lectureDe({
		actualite: estActualite(t),
		confidentiel: t.confidentiel === true,
		publicCible: t.public_cible,
		perimetreRestreint: perimetreRestreint(t.perimetre_cible),
		reservePerimetre: t.reserve_perimetre === true,
		datee: !!t.debut,
		enAg: t.statut === 'en_ag',
	});
}
