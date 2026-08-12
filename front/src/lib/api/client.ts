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
export function setActingAs(mandantId: number | null) { _actingAsId = mandantId; }
export function getActingAs(): number | null { return _actingAsId; }

export class ApiError extends Error {
	constructor(
		public status: number,
		message: string,
		/** Détail technique (jamais affiché à l'utilisateur, disponible en console) */
		public technicalDetail?: string,
	) {
		super(message);
	}
}

// Guard pour éviter deux refreshes simultanés
let _refreshing: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
	if (_refreshing) return _refreshing;
	_refreshing = fetch(`${BASE}/auth/refresh`, { method: 'POST', credentials: 'include' })
		.then(r => r.ok)
		.catch(() => false)
		.finally(() => { _refreshing = null; });
	return _refreshing;
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

	let res = await fetch(`${BASE}${path}`, opts);

	// Refresh silencieux sur 401 (sauf sur les routes d'auth elles-mêmes)
	if (res.status === 401 && !path.startsWith('/auth/')) {
		const ok = await tryRefresh();
		if (ok) {
			res = await fetch(`${BASE}${path}`, opts);
		} else {
			// Refresh impossible : rediriger vers login EN CONSERVANT la page
			// courante. C'est le chemin réellement emprunté en production quand
			// une session a expiré ou n'existe pas : la garde de `(app)/+layout`
			// n'a pas le temps de s'exécuter, cette ligne part avant elle.
			if (typeof window !== 'undefined') {
				window.location.href = urlDeConnexion();
			}
			throw new ApiError(401, 'Session expirée, veuillez vous reconnecter.');
		}
	}

	if (!res.ok) {
		let rawDetail = 'Erreur serveur';
		try {
			const err = await res.json();
			if (typeof err.detail === 'string') {
				rawDetail = err.detail;
			} else if (Array.isArray(err.detail)) {
				// Erreurs de validation Pydantic : [{loc, msg, type}]
				rawDetail = err.detail.map((e: any) => e.msg ?? JSON.stringify(e)).join(', ');
			} else if (err.detail) {
				rawDetail = JSON.stringify(err.detail);
			}
		} catch {
			/* ignore */
		}

		if (res.status >= 500) {
			// Erreur serveur : ne pas exposer le détail technique à l'utilisateur
			console.error(`[API ${res.status}] ${method} ${path} — ${rawDetail}`);
			const userMsg = res.status === 503
				? 'Service momentanément indisponible. Veuillez réessayer dans quelques instants.'
				: 'Une erreur est survenue. Si le problème persiste, contactez l’administrateur.';
			throw new ApiError(res.status, userMsg, rawDetail);
		}

		throw new ApiError(res.status, rawDetail);
	}

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

export const api = {
	get: <T>(path: string) => request<T>('GET', path),
	post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
	// `body` optionnel : `request` le traite déjà ainsi, et un PATCH d'action
	// (marquer une notification lue) n'a pas de corps à envoyer.
	patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, body),
	put: <T>(path: string, body: unknown) => request<T>('PUT', path, body),
	delete: <T>(path: string) => request<T>('DELETE', path),
};
