/**
 * Télémétrie — collecte des pages visitées et des erreurs vues à l'écran.
 *
 * Utilise `navigator.sendBeacon` pour un envoi non-bloquant (fire-and-forget).
 * Les événements sont accumulés en mémoire et envoyés en batch toutes les 30 s
 * ou au moment du déchargement de la page (beforeunload / visibilitychange).
 *
 * Aucun impact sur la latence utilisateur.
 *
 * Ce que le serveur fait de ces lots — rattachés au compte s'il y en a un, refus
 * du profil honoré une seconde fois — se lit dans `api/app/routers/telemetry_collecte.py`,
 * pas ici. 🔴 Cet en-tête l'a décrit « anonyme » après la migration 0247, qui
 * rattachait de nouveau la mesure au compte (#1635) : un commentaire qui
 * raconte un autre fichier diverge sans bruit. Ce qui est vrai ICI : le refus
 * du profil s'applique aussi dans le navigateur — qui refuse n'envoie plus rien.
 */

const FLUSH_INTERVAL = 30_000; // 30 secondes
const ENDPOINT = '/api/telemetry/collect';
/** Au-delà, le serveur refuse le lot (`EVENEMENTS_PAR_LOT` de
 *  `telemetry_collecte.py`, #1597) : la file part dès qu'elle l'atteint. ⚠️ Les
 *  deux valeurs se tiennent à la main — le front et l'API ne partagent aucun
 *  fichier. */
const EVENEMENTS_PAR_LOT = 20;
/** L'action d'un signalement d'erreur (#1631). ⚠️ Tenue à la main avec
 *  `ACTION_ERREUR` de `api/app/utils/erreurs_navigateur.py`. */
const ACTION_ERREUR = 'erreur';
/** Au plus tant de signalements par onglet ouvert : une boucle d'erreurs ne doit
 *  ni épuiser la limite de collecte du serveur ni noyer les vues du même lot. */
const SIGNALEMENTS_PAR_ONGLET = 10;
/** Le `max_length` du `detail` côté serveur (`EvenementAudience`) : au-delà, le
 *  lot entier serait refusé, vues comprises. */
const LONGUEUR_DETAIL = 100;

const buffer: { page: string; action: string; detail?: string }[] = [];
let timer: ReturnType<typeof setInterval> | null = null;
let disabled = false;
/** Les couples (page, code) déjà signalés par cet onglet. */
const signales = new Set<string>();

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

/**
 * **Le CODE d'une erreur — ce qu'on en garde, jamais son message brut** (#1631).
 *
 * Un message peut porter une saisie de l'utilisateur ; une pile d'appels, des
 * chemins de fichiers. On garde donc, dans cet ordre :
 * - le code d'une erreur Svelte (`svelte:each_key_duplicate`), lu dans le lien
 *   que Svelte 5 met dans chaque message ;
 * - le statut et le chemin d'une réponse en échec (`ApiError`, reconnue à ses
 *   champs : l'importer ferait boucler ce module et le client d'API) ;
 * - sinon le nom de l'erreur et la PREMIÈRE ligne du message, sans ce qui est
 *   entre guillemets ou chevrons et sans les nombres.
 */
export function codeErreur(e: unknown): string {
	const brut = e instanceof Error ? e.message : String(e ?? '');
	const svelte = /svelte\.dev\/e\/(\w+)/.exec(brut);
	if (svelte) return `svelte:${svelte[1]}`;
	const reponse = e as { status?: unknown; chemin?: unknown } | null;
	if (typeof reponse?.status === 'number') {
		return codeHttp(reponse.status, typeof reponse.chemin === 'string' ? reponse.chemin : '?');
	}
	const nom = e instanceof Error ? e.name : typeof e;
	const signature = (brut.split('\n')[0] ?? '')
		.replace(/(["'`])[^"'`]*\1|«[^»]*»/g, '…')
		.replace(/\d+/g, '#')
		.replace(/\s+/g, ' ')
		.trim();
	return (signature ? `${nom}: ${signature}` : nom).slice(0, LONGUEUR_DETAIL);
}

/** Le code d'une réponse en échec : statut et chemin, identifiants masqués
 *  (`HTTP 502 /tickets/#`) — mille affaires ne font pas mille lignes. */
export function codeHttp(status: number, chemin: string): string {
	return `HTTP ${status} ${chemin.split('?')[0].replace(/\d+/g, '#')}`.slice(0, LONGUEUR_DETAIL);
}

/** Signale une erreur vue à l'écran — une fois par page et par code, pour cet onglet. */
export function signalerErreur(code: string) {
	if (typeof window === 'undefined') return;
	const page = window.location.pathname;
	const cle = `${page}|${code}`;
	if (signales.has(cle) || signales.size >= SIGNALEMENTS_PAR_ONGLET) return;
	signales.add(cle);
	trackEvent(page, ACTION_ERREUR, code);
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

	//  Ce que rien n'a rattrapé (#1631). Les erreurs d'un chargement ou d'une
	//  navigation n'arrivent pas jusqu'ici : `hooks.client.ts` les prend.
	window.addEventListener('error', (ev) => signalerErreur(codeErreur(ev.error ?? ev.message)));
	window.addEventListener('unhandledrejection', (ev) => signalerErreur(codeErreur(ev.reason)));
}
