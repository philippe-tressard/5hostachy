/**
 * Les TYPES d'accès — badge Vigik, télécommande de parking —, écrits une fois.
 *
 * 🔴 Ils l'étaient trois fois, en trois libellés (#1329) : « 🏷️ Vigik » dans le
 * filtre des badges, « Badge Vigik » dans les deux formulaires de demande,
 * « 🏷️ Vigik » en dur dans les accès connexes. Même objet, même mot partout.
 *
 * Les valeurs sont celles du modèle (`TypeAcces` côté serveur).
 */
export const TYPES_ACCES = [
	{ val: 'vigik', label: '\u{1F3F7}\u{FE0F} Badge Vigik' },
	{ val: 'telecommande', label: '\u{1F4E1} Télécommande parking' },
] as const;

/** Le libellé d'un type d'accès ; la valeur brute si elle est inconnue (elle se voit). */
export function typeAccesLabel(val: string | null | undefined): string {
	return TYPES_ACCES.find((t) => t.val === val)?.label ?? val ?? '—';
}

/**
 * Les STATUTS d'un accès — libellé et badge, écrits une fois (#1345, 26/09/2026).
 *
 * 🔴 Deux tables de badges coexistaient, et elles avaient divergé : l'onglet
 * Accès connaissait « suspendu » (orange), le parc de la copropriété ne le
 * connaissait pas et prévoyait un « desactive » que le modèle n'a jamais eu.
 * Et le statut s'affichait BRUT (« actif ») dans cinq écrans. Les valeurs sont
 * celles de `StatutAcces` côté serveur.
 *
 * 🔴 Une troisième table vivait encore dans `FormulaireAcces` (#1575, 02/10/2026)
 * — les pastilles du choix d'état —, avec son propre libellé (« ✅ Actif ») : le
 * même statut se disait de deux façons selon qu'on le lisait ou qu'on le
 * choisissait. Le pictogramme rejoint donc l'entrée (`emoji`), et le choix se
 * dérive d'ici (`STATUT_ACCES_OPTIONS`). 🔒 `npm run lint:statuts-acces`.
 */
export const STATUTS_ACCES = [
	{ val: 'actif', label: 'Actif', emoji: '✅', badge: 'badge-green' },
	{ val: 'suspendu', label: 'Suspendu', emoji: '⏸️', badge: 'badge-orange' },
	{ val: 'perdu', label: 'Perdu', emoji: '\u{1F50E}', badge: 'badge-red' },
] as const;

/** Les pastilles d'un choix d'état — pictogramme compris, comme `STATUT_TICKET_OPTIONS`. */
export const STATUT_ACCES_OPTIONS = STATUTS_ACCES.map((s) => ({
	val: s.val,
	label: `${s.emoji} ${s.label}`,
}));

/** Le libellé d'un statut d'accès ; la valeur brute si elle est inconnue (elle se voit). */
export function statutAccesLabel(val: string | null | undefined): string {
	return STATUTS_ACCES.find((s) => s.val === val)?.label ?? val ?? '—';
}

/** La classe de badge d'un statut d'accès ; gris s'il est inconnu. */
export function statutAccesBadge(val: string | null | undefined): string {
	return STATUTS_ACCES.find((s) => s.val === val)?.badge ?? 'badge-gray';
}
