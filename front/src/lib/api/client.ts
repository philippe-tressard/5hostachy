//  Transport HTTP et erreurs — le noyau que tous les modules de ce paquet
//  utilisent. Extrait de `api.ts` le 12/08/2026 : ce fichier atteignait 914
//  lignes et le garde-fou de modularité (rang 1) refuse qu'il grossisse.
/**
 * Client API — wrappeur fetch vers le backend FastAPI.
 * En production, Caddy route /api/* → FastAPI.
 * En développement, vite proxy forward /api → localhost:8000.
 */

import { urlDeConnexion } from '$lib/redirection';

export const BASE = '/api';

/** ID du mandant si l'aidant agit en délégation (null = agit pour soi-même) */
let _actingAsId: number | null = null;
export function setActingAs(mandantId: number | null) {
	_actingAsId = mandantId;
}
export function getActingAs(): number | null {
	return _actingAsId;
}

export class ApiError extends Error {
	constructor(
		public status: number,
		message: string,
		/** Détail technique (jamais affiché à l'utilisateur, disponible en console) */
		public technicalDetail?: string,
		/**
		 * 🔴 Le chemin appelé — ce qui permet de savoir ce que veut dire un 401.
		 *
		 * Sur `/auth/login`, un 401 signifie « identifiants refusés » et le
		 * serveur l'explique ; partout ailleurs il signifie « cette session n'est
		 * plus valide ». Sans cette information, `messageErreur` répondait
		 * « votre session a expiré » à qui venait de se tromper de mot de passe —
		 * et c'est la raison pour laquelle trois écrans d'authentification
		 * n'avaient pas pu passer au message partagé.
		 *
		 * La distinction n'est pas réécrite : c'est `CHEMINS_SANS_RENOUVELLEMENT`
		 * qui la porte déjà, pour le renouvellement. Une seule liste, deux usages.
		 */
		public chemin?: string,
	) {
		super(message);
	}
}

/**
 * Chemins où un 401 est une RÉPONSE DÉFINITIVE, et non une session à renouveler.
 *
 * Le renouvellement silencieux était jusqu'ici désactivé par le PRÉFIXE `/auth/`.
 * Il attrapait donc `/auth/me` — l'appel qui charge l'utilisateur au démarrage de
 * l'application. Or l'access token vit 120 min et le refresh token 7 jours
 * (`api/app/config.py`) : il existe une fenêtre de sept jours pendant laquelle la
 * session est parfaitement renouvelable et où `me()` était pourtant refusé sans
 * qu'on ait seulement essayé. Les requêtes de la page, elles, se renouvelaient et
 * s'affichaient — d'où du contenu à l'écran, `$currentUser` resté nul, et un menu
 * vidé de ses quatorze entrées pour ne garder que la marque (#379).
 *
 * La liste est donc NOMINATIVE, jamais un préfixe. N'y figurent que les chemins
 * dont l'API renvoie 401 comme réponse métier :
 *   - `/auth/refresh` : c'est lui qui renouvelle — s'y rappeler serait une récursion ;
 *   - `/auth/login`   : 401 = identifiants refusés, à afficher tel quel ;
 *   - `/auth/logout`  : on quitte la session, la renouveler n'aurait aucun sens.
 *
 * Tout autre 401 signifie « cette session n'est plus valide » : on tente de la
 * renouveler, et on n'envoie vers la mire que si le renouvellement échoue.
 *
 * `npm run lint:session` vérifie qu'aucun préfixe ne revient, que `/auth/me` n'y
 * entre pas, et qu'une entrée devenue inutile fait échouer le contrôle.
 */
export const CHEMINS_SANS_RENOUVELLEMENT = ['/auth/refresh', '/auth/login', '/auth/logout'];

/** Chemin sans sa chaîne de requête — `/auth/verifier-email?token=…` porte la sienne. */
function cheminNu(path: string): string {
	return path.split('?')[0];
}

// Guard pour éviter deux refreshes simultanés
let _refreshing: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
	if (_refreshing) return _refreshing;
	_refreshing = fetch(`${BASE}/auth/refresh`, { method: 'POST', credentials: 'include' })
		.then((r) => r.ok)
		.catch(() => false)
		.finally(() => {
			_refreshing = null;
		});
	return _refreshing;
}

/**
 * 🔴 **La conduite à tenir sur un 401 — renouveler, ou envoyer vers la mire.**
 *
 * Elle était écrite dans `request()`, donc réservée aux appels d'API. Les
 * IMAGES protégées n'y avaient aucun accès : `/uploads/*` passe par le
 * `forward_auth` du Caddyfile, le navigateur les charge lui-même, et un 401
 * n'y produit qu'une icône cassée. C'est ce qu'a vu Philippe le 17/09/2026 —
 * des photos cassées sur un serveur parfaitement sain (#996).
 *
 * Exportée ici pour que l'occurrence non couverte suive la MÊME règle, plutôt
 * que d'en inventer une deuxième dans un écran :
 * `$lib/imagesProtegees.ts` l'appelle telle quelle.
 *
 * @returns `true` si la session a été renouvelée — le geste peut être rejoué.
 *          `false` après redirection vers la mire : la session est morte, et
 *          la page demandée est conservée dans l'URL de connexion.
 */
export async function renouvelerSession(): Promise<boolean> {
	if (await tryRefresh()) return true;
	//  Renouvellement impossible : rediriger vers la mire EN CONSERVANT la page
	//  courante. C'est le chemin réellement emprunté en production quand une
	//  session a expiré ou n'existe pas : la garde de `(app)/+layout` n'a pas le
	//  temps de s'exécuter, cette ligne part avant elle.
	if (typeof window !== 'undefined') {
		window.location.href = urlDeConnexion();
	}
	return false;
}

/**
 * **Envoyer, renouveler la session sur 401, rejouer une fois.**
 *
 * Écrit une fois : `request()` le faisait pour les appels JSON, et
 * `postFormData()` ne le faisait PAS — son en-tête le déclarait d'ailleurs
 * comme un écart à corriger un jour (« une session expirée pendant un envoi
 * échoue au lieu de se renouveler »). Un écart déclaré dans un commentaire
 * n'est pas un écart surveillé : il a vécu du 12/09 au 18/09/2026.
 *
 * @param envoyer  refabrique la requête à chaque tentative — un corps déjà
 *                 consommé ne se rejoue pas.
 */
async function envoyerAvecRenouvellement(
	envoyer: () => Promise<Response>,
	path: string,
): Promise<Response> {
	const res = await envoyer();
	if (res.status !== 401 || CHEMINS_SANS_RENOUVELLEMENT.includes(cheminNu(path))) return res;
	if (await renouvelerSession()) return envoyer();
	throw new ApiError(401, 'Session expirée, veuillez vous reconnecter.', undefined, cheminNu(path));
}

/**
 * **L'erreur à lever pour une réponse en échec** — masquage des 5xx compris.
 *
 * Écrit une fois, pour la même raison : les neuf copies de téléversement
 * n'avaient jamais reçu ni le masquage du détail technique sur 5xx, ni la
 * lecture du `detail` de validation. Elles l'ont en passant par ici.
 */
async function echecApi(
	res: Response,
	method: string,
	path: string,
	repli: string,
): Promise<ApiError> {
	let rawDetail = repli;
	try {
		const err = await res.json();
		if (typeof err.detail === 'string') {
			rawDetail = err.detail;
		} else if (err.detail) {
			rawDetail = JSON.stringify(err.detail);
		}
	} catch {
		/* le corps n'est pas du JSON : on garde le libellé par défaut */
	}

	if (res.status >= 500) {
		// Erreur serveur : ne pas exposer le détail technique à l'utilisateur
		console.error(`[API ${res.status}] ${method} ${path} — ${rawDetail}`);
		const userMsg =
			res.status === 503
				? 'Service momentanément indisponible. Veuillez réessayer dans quelques instants.'
				: 'Une erreur est survenue. Si le problème persiste, contactez l’administrateur.';
		return new ApiError(res.status, userMsg, rawDetail, cheminNu(path));
	}

	return new ApiError(res.status, rawDetail, undefined, cheminNu(path));
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
	const headers: Record<string, string> = {};
	if (body) headers['Content-Type'] = 'application/json';
	if (_actingAsId !== null) headers['X-Acting-As'] = String(_actingAsId);

	const opts: RequestInit = {
		method,
		headers,
		body: body ? JSON.stringify(body) : undefined,
		credentials: 'include',
	};

	const res = await envoyerAvecRenouvellement(() => fetch(`${BASE}${path}`, opts), path);
	if (!res.ok) throw await echecApi(res, method, path, 'Erreur serveur');

	if (res.status === 204) return undefined as T;
	return res.json() as Promise<T>;
}

/** Construit une query string depuis un objet en filtrant les undefined/null/vide. */
export function buildQuery(params: Record<string, string | undefined | null>): string {
	const q = Object.entries(params)
		.filter(([, v]) => v !== undefined && v !== null && v !== '')
		.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v!)}`)
		.join('&');
	return q ? `?${q}` : '';
}

/**
 * Envoi MULTIPART — le seul chemin du site pour poster un fichier.
 *
 * ## Pourquoi cette fonction existe (27/08/2026, #453)
 *
 * `request()` sérialise en JSON : un `FormData` ne peut pas passer par lui. Chaque
 * appelant avait donc réécrit son propre `fetch`, et ils étaient **NEUF**, répartis
 * dans trois fichiers — `api/index.ts` (devis, OS, photo de relevé, rapport de
 * diagnostic), `api/documents.ts` (catégorie, contrat, publication, `uploadFile`,
 * `uploadExcel`) et `api/communaute.ts` (photo d'annonce).
 *
 * Neuf copies du même bloc de six lignes :
 *
 *     if (!res.ok) {
 *       let detail = 'Erreur upload';
 *       try { const err = await res.json(); detail = err.detail ?? detail; } catch {}
 *       throw new ApiError(res.status, detail);
 *     }
 *
 * Et elles avaient déjà divergé — sur le LIBELLÉ, seul point où c'était visible :
 * « Erreur upload », « Erreur upload fichier », « Erreur upload OS », « Erreur
 * upload photo », « Erreur import ». Cinq façons de dire la même chose à
 * l'utilisateur selon le bouton sur lequel il a cliqué.
 *
 * ⚠️ Ce qu'une copie coûtait VRAIMENT ici : `request()` avait reçu le
 * renouvellement silencieux de session (#379), le masquage des détails
 * techniques sur les 5xx et la lecture des erreurs de validation Pydantic —
 * **aucune des neuf copies n'en avait rien reçu**. Un 500 sur un téléversement
 * exposait son détail technique, et une session expirée pendant un envoi
 * échouait au lieu de se renouveler.
 *
 * 🔴 **Les deux écarts sont refermés depuis le 18/09/2026** : cette fonction
 * passe par `envoyerAvecRenouvellement()` et `echecApi()`, comme `request()`.
 * C'était l'objet de l'endroit unique — et il a fallu six jours, pendant
 * lesquels l'écart n'était écrit que dans ce commentaire. Un écart déclaré
 * n'est pas un écart surveillé (`standards/04` §28).
 *
 * @param champs  les champs du formulaire ; `undefined` et `null` sont écartés,
 *                pour que l'appelant n'ait pas à écrire `if (x) form.append(…)`.
 */
export async function postFormData<T = any>(
	path: string,
	champs: Record<string, string | Blob | undefined | null>,
	options: { libelleErreur?: string } = {},
): Promise<T> {
	const form = new FormData();
	for (const [cle, valeur] of Object.entries(champs)) {
		if (valeur === undefined || valeur === null) continue;
		form.append(cle, valeur);
	}
	const res = await envoyerAvecRenouvellement(
		() => fetch(`${BASE}${path}`, { method: 'POST', body: form, credentials: 'include' }),
		path,
	);
	if (!res.ok) {
		throw await echecApi(
			res,
			'POST',
			path,
			options.libelleErreur ?? 'Erreur lors de l’envoi du fichier',
		);
	}
	return res.json() as Promise<T>;
}

export const api = {
	get: <T>(path: string) => request<T>('GET', path),
	post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
	// `body` optionnel : `request` le traite déjà ainsi, et un PATCH d'action
	// (marquer une notification lue) n'a pas de corps à envoyer.
	patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, body),
	put: <T>(path: string, body: unknown) => request<T>('PUT', path, body),
	delete: <T>(path: string) => request<T>('DELETE', path),
};
