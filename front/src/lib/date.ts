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
