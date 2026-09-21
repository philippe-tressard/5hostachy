/**
 * **Lire le pliage d'une section** — et rien d'autre (#1095).
 *
 * Une ligne, mais elle a sa place ici plutôt que dans un écran : le pliage se
 * LIT dans la déclaration, il ne se décide pas. Un second écran qui en aurait
 * besoin recopierait sinon le `?.pliee` et le repli à `false` — et c'est ainsi
 * qu'une règle se met à diverger.
 *
 * ⚠️ `pliable` ne suffit jamais seul : il va avec `ouvrirSiRenseignee`, la
 * moitié que la table ne peut pas porter puisqu'elle dépend de ce que l'objet
 * CONTIENT. Les séparer laisserait une section pliée cacher une valeur saisie.
 *
 * 🔴 Et cette seconde moitié se calcule contre le DÉFAUT, jamais contre le
 * vide : le périmètre porte toujours « Copropriété entière », les destinataires
 * « Tous les résidents ». Tester leur présence rouvrait la section à chaque
 * fois, et rien ne pliait — constaté à l'écran le 21/09/2026, « Visu sans
 * pliages ». `estPerimetreParDefaut` et `concerneTousLesResidents` savent, eux,
 * ce qu'est le défaut.
 */
import { section, type EntiteDeclaree, type IdSection } from '$lib/entites/types';

/** La section est-elle repliée par défaut ? `false` sans déclaration. */
export function pliageDe(entite: EntiteDeclaree | null, id: IdSection): boolean {
	return entite ? !!section(entite, id)?.pliee : false;
}
