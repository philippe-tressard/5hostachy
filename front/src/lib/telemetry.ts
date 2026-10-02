/**
 * Télémétrie — collecte transparente des pages visitées.
 *
 * Utilise `navigator.sendBeacon` pour un envoi non-bloquant (fire-and-forget).
 * Les événements sont accumulés en mémoire et envoyés en batch toutes les 30 s
 * ou au moment du déchargement de la page (beforeunload / visibilitychange).
 *
 * Aucun impact sur la latence utilisateur.
 *
 * 🔴 ANONYME (#1545, 02/10/2026) : le serveur n'enregistre aucun identifiant et
 * ne lit pas la session (`routers/telemetry_collecte.py`). Le refus du profil
 * s'applique donc ICI — qui refuse n'envoie plus rien.
 */

const FLUSH_INTERVAL = 30_000; // 30 secondes
const ENDPOINT = '/api/telemetry/collect';
/** Au-delà, le serveur refuse le lot (`EVENEMENTS_PAR_LOT` de
 *  `telemetry_collecte.py`, #1597) : la file part dès qu'elle l'atteint. ⚠️ Les
 *  deux valeurs se tiennent à la main — le front et l'API ne partagent aucun
 *  fichier. */
const EVENEMENTS_PAR_LOT = 20;

const buffer: { page: string; action: string; detail?: string }[] = [];
let timer: ReturnType<typeof setInterval> | null = null;
let disabled = false;

/** Refus de la mesure d'audience — appliqué ici, seul endroit qui le peut. */
export function setTelemetryOptOut(optOut: boolean) {
	disabled = optOut;
	if (optOut) buffer.length = 0;
}

/** Enregistre un événement de télémétrie (non-bloquant). */
export function trackEvent(page: string, action = 'view', detail?: string) {
	if (disabled) return;
	buffer.push({ page, action, ...(detail ? { detail } : {}) });
	if (buffer.length >= EVENEMENTS_PAR_LOT) flush();
}

/** Enregistre une vue de page. */
export function trackPageView(path: string) {
	trackEvent(path, 'view');
}

/** Enregistre une vue d'onglet (page#tab). */
export function trackTabView(tab: string) {
	if (typeof window === 'undefined') return;
	trackEvent(`${window.location.pathname}#${tab}`, 'view');
}

function flush() {
	if (buffer.length === 0) return;
	const events = buffer.splice(0);
	const payload = JSON.stringify({ events });
	try {
		if (typeof navigator !== 'undefined' && navigator.sendBeacon) {
			navigator.sendBeacon(ENDPOINT, new Blob([payload], { type: 'application/json' }));
		} else {
			// Fallback pour les navigateurs sans sendBeacon
			fetch(ENDPOINT, {
				method: 'POST',
				body: payload,
				headers: { 'Content-Type': 'application/json' },
				credentials: 'include',
				keepalive: true,
			}).catch(() => {});
		}
	} catch {
		// Silencieux — ne jamais impacter l'UX
	}
}

/** Initialise la télémétrie (appeler une seule fois dans le layout). */
export function initTelemetry() {
	if (typeof window === 'undefined') return;
	if (timer) return; // Déjà initialisé

	timer = setInterval(flush, FLUSH_INTERVAL);

	// Flush au déchargement de la page
	window.addEventListener('visibilitychange', () => {
		if (document.visibilityState === 'hidden') flush();
	});
	window.addEventListener('beforeunload', flush);
}
