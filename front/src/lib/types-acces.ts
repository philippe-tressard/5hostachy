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
