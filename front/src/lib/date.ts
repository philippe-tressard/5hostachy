/**
 * Détermine si un item est "Nouveau" (créé il y a moins de 48h et jamais mis à jour)
 * @param cree_le - date de création (ISO string)
 * @param mis_a_jour_le - date de mise à jour (ISO string ou null)
 * @returns true si l'item est considéré comme nouveau
 */
/**
 * Un item est "Nouveau" si :
 * - il a été créé il y a moins de 48h
 * - il n'a pas été mis à jour (mis_a_jour_le absent ou identique à cree_le)
 */
export function isNouveau(cree_le: string, mis_a_jour_le?: string | null): boolean {
	if (!cree_le) return false;
	const now = Date.now();
	const created = new Date(cree_le).getTime();
	const FORTY_EIGHT_HOURS = 48 * 60 * 60 * 1000;
	const notUpdated = !mis_a_jour_le || mis_a_jour_le === cree_le;
	return notUpdated && (now - created < FORTY_EIGHT_HOURS);
}
/**
 * Utilitaires de formatage de dates — Europe/Paris
 *
 * Toutes les fonctions forcent le fuseau Europe/Paris pour garantir
 * un affichage cohérent que le code tourne côté serveur (SSR, Docker UTC)
 * ou côté client (navigateur).
 */

const TZ = 'Europe/Paris';
const LOCALE = 'fr-FR';

/** "2 avr. 2026" */
export function fmtDate(d: string | null | undefined): string {
	if (!d) return '—';
	return new Date(d).toLocaleDateString(LOCALE, { day: 'numeric', month: 'short', year: 'numeric', timeZone: TZ });
}

/** "2 avril 2026" */
export function fmtDateLong(d: string | null | undefined): string {
	if (!d) return '—';
	return new Date(d).toLocaleDateString(LOCALE, { day: 'numeric', month: 'long', year: 'numeric', timeZone: TZ });
}

/** "02 avr. 2026" */
export function fmtDate2d(d: string | null | undefined): string {
	if (!d) return '—';
	return new Date(d).toLocaleDateString(LOCALE, { day: '2-digit', month: 'short', year: 'numeric', timeZone: TZ });
}

/** "10/04/2026" */
export function fmtDateShort(d: string | null | undefined): string {
	if (!d) return '—';
	return new Date(d).toLocaleDateString(LOCALE, { dateStyle: 'short', timeZone: TZ });
}

/** "2 avr. 2026, 14:30" */
export function fmtDatetime(d: string | null | undefined): string {
	if (!d) return '—';
	return new Date(d).toLocaleString(LOCALE, { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: TZ });
}

/** "02 avr. 2026, 14:30" */
export function fmtDatetime2d(d: string | null | undefined): string {
	if (!d) return '—';
	return new Date(d).toLocaleString(LOCALE, { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: TZ });
}

/** "10/04/2026 14:30" */
export function fmtDatetimeShort(d: string | null | undefined): string {
	if (!d) return '—';
	return new Date(d).toLocaleString(LOCALE, { dateStyle: 'short', timeStyle: 'short', timeZone: TZ });
}

/** "14:30" */
export function fmtTime(d: string | null | undefined): string {
	if (!d) return '—';
	return new Date(d).toLocaleTimeString(LOCALE, { hour: '2-digit', minute: '2-digit', timeZone: TZ });
}

/** "avril 2026" */
export function fmtMonthYear(d: string | Date | null | undefined): string {
	if (!d) return '—';
	const dt = typeof d === 'string' ? new Date(d) : d;
	return dt.toLocaleDateString(LOCALE, { month: 'long', year: 'numeric', timeZone: TZ });
}

/** "2 avril" (jour + mois long, sans année) */
export function fmtDayMonth(d: string | null | undefined): string {
	if (!d) return '—';
	return new Date(d).toLocaleDateString(LOCALE, { day: 'numeric', month: 'long', timeZone: TZ });
}
