/**
 * Client API — wrappeur fetch vers le backend FastAPI.
 * En production, Caddy route /api/* → FastAPI.
 * En développement, vite proxy forward /api → localhost:8000.
 */

const BASE = '/api';

/** ID du mandant si l'aidant agit en délégation (null = agit pour soi-même) */
let _actingAsId: number | null = null;
export function setActingAs(mandantId: number | null) { _actingAsId = mandantId; }
export function getActingAs(): number | null { return _actingAsId; }

export class ApiError extends Error {
	constructor(
		public status: number,
		message: string,
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
			// Refresh impossible : rediriger vers login
			if (typeof window !== 'undefined') {
				window.location.href = '/auth/connexion';
			}
			throw new ApiError(401, 'Session expirée, veuillez vous reconnecter.');
		}
	}

	if (!res.ok) {
		let detail = 'Erreur serveur';
		try {
			const err = await res.json();
			if (typeof err.detail === 'string') {
				detail = err.detail;
			} else if (Array.isArray(err.detail)) {
				// Erreurs de validation Pydantic : [{loc, msg, type}]
				detail = err.detail.map((e: any) => e.msg ?? JSON.stringify(e)).join(', ');
			} else if (err.detail) {
				detail = JSON.stringify(err.detail);
			}
		} catch {
			/* ignore */
		}
		throw new ApiError(res.status, detail);
	}

	if (res.status === 204) return undefined as T;
	return res.json() as Promise<T>;
}

/** Construit une query string depuis un objet en filtrant les undefined/null/vide. */
function buildQuery(params: Record<string, string | undefined | null>): string {
	const q = Object.entries(params)
		.filter(([, v]) => v !== undefined && v !== null && v !== '')
		.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v!)}`)
		.join('&');
	return q ? `?${q}` : '';
}

export const api = {
	get: <T>(path: string) => request<T>('GET', path),
	post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
	patch: <T>(path: string, body: unknown) => request<T>('PATCH', path, body),
	put: <T>(path: string, body: unknown) => request<T>('PUT', path, body),
	delete: <T>(path: string) => request<T>('DELETE', path),
};

// ── Helpers métier ──────────────────────────────────────────────────────────

export interface User {
	id: number;
	nom: string;
	prenom: string;
	email: string;
	telephone?: string | null;
	societe?: string | null;	fonction?: string | null;	statut: string;
	role: string;
	roles: string[];  // multi-rôles cumulables
	actif: boolean;
	onboarding_complete: boolean;
	onboarding_etape: number;
	photo_url?: string;
	preferences_notifications: string;
	batiment_id?: number | null;
	batiment_nom?: string | null;  // "Bât. A"
	last_seen_actualites?: string | null;
	delegations_aidant?: { delegation_id: number; mandant_id: number; mandant_nom: string }[];
	cree_le: string;
	derniere_connexion?: string | null;
}

export interface Ticket {
	id: number;
	numero: string;
	titre: string;
	description: string;
	categorie: string;
	statut: string;
	priorite: string;
	auteur_id: number;
	auteur_nom?: string | null;
	auteur_batiment_nom?: string | null;
	lot_id?: number;
	batiment_id?: number;
	perimetre_cible?: string[];
	cree_le: string;
	mis_a_jour_le: string;
}

export interface TicketEvolution {
	id: number;
	ticket_id: number;
	type: 'commentaire' | 'etat' | 'reponse';
	contenu?: string;
	ancien_statut?: string;
	nouveau_statut?: string;
	auteur_id: number;
	auteur_nom?: string;
	cree_le: string;
}

export interface PublicationEvolution {
	id: number;
	publication_id: number;
	type: 'commentaire' | 'etat' | 'correction';
	contenu?: string;
	ancien_statut?: string;
	nouveau_statut?: string;
	auteur_id: number;
	auteur_nom?: string;
	cree_le: string;
}

export interface Publication {
	id: number;
	titre: string;
	contenu: string;
	perimetre: string;
	batiment_id?: number;
	epingle: boolean;
	urgente: boolean;
	auteur_id: number;
	auteur_nom?: string;
	image_url?: string;
	cree_le: string;
	mis_a_jour_le?: string;
	perimetre_cible: string[];
	public_cible: string[];
	statut?: 'en_cours' | 'resolu' | 'annule' | null;
	statut_change_le?: string | null;
	brouillon: boolean;
	partager_whatsapp?: boolean;
	evolutions: PublicationEvolution[];
}

export interface Document {
	id: number;
	titre: string;
	fichier_nom: string;
	taille_octets?: number;
	mime_type: string;
	categorie_id: number;
	perimetre: string;
	publie_le: string;
}

export interface Notification {
	id: number;
	type: string;
	titre: string;
	corps: string;
	lien?: string;
	lue: boolean;
	urgente: boolean;
	cree_le: string;
}

export const auth = {
	me: () => api.get<User>('/auth/me'),
	login: (email: string, password: string) => api.post<User>('/auth/login', { email, password }),
	register: (data: unknown) => api.post<User>('/auth/register', data),
	logout: () => api.post('/auth/logout'),
	refresh: () => api.post('/auth/refresh'),
	updateMe: (data: unknown) => api.patch<User>('/auth/me', data),
	changePassword: (data: unknown) => api.post('/auth/change-password', data),
	requestPasswordReset: (data: unknown) => api.post('/auth/mot-de-passe-oublie', data),
	batiments: () => api.get<{ id: number; numero: string }[]>('/auth/batiments'),
	mesDemandes: () => api.get<any[]>('/auth/me/demandes-modification'),
	demanderModification: (data: unknown) => api.post<any>('/auth/me/demande-modification', data),
	declarerNouvelArrivant: (data: { batiment?: string | null; ancien_resident?: string | null; ancien_resident_inconnu?: boolean }) =>
		api.post<any>('/admin/me/accueil-arrivant', data),
};

export const tickets = {
	list: () => api.get<Ticket[]>('/tickets'),
	get: (id: number) => api.get<Ticket>(`/tickets/${id}`),
	create: (data: unknown) => api.post<Ticket>('/tickets', data),
	update: (id: number, data: unknown) => api.patch<Ticket>(`/tickets/${id}`, data),
	delete: (id: number) => api.delete(`/tickets/${id}`),
	messages: (id: number) => api.get(`/tickets/${id}/messages`),
	addMessage: (id: number, data: unknown) => api.post(`/tickets/${id}/messages`, data),
	evolutions: (id: number) => api.get<TicketEvolution[]>(`/tickets/${id}/evolutions`),
	addEvolution: (id: number, data: { type: string; contenu?: string; nouveau_statut?: string }) =>
		api.post<TicketEvolution>(`/tickets/${id}/evolutions`, data),
};

export const publications = {
	list: (archived = false) => api.get<Publication[]>(`/publications${archived ? '?archived=true' : ''}`),
	create: (data: unknown) => api.post<Publication>('/publications', data),
	update: (id: number, data: unknown) => api.patch<Publication>(`/publications/${id}`, data),
	archive: (id: number) => api.patch<Publication>(`/publications/${id}`, { archivee: true }),
	delete: (id: number) => api.delete(`/publications/${id}`),
	addEvolution: (pubId: number, data: { type: string; contenu?: string; nouveau_statut?: string }) =>
		api.post<PublicationEvolution>(`/publications/${pubId}/evolutions`, data),
};

export const documents = {
	list: (categorieId?: number, contratId?: number) => {
		const params = new URLSearchParams();
		if (categorieId) params.set('categorie_id', String(categorieId));
		if (contratId) params.set('contrat_id', String(contratId));
		const qs = params.toString();
		return api.get<Document[]>(`/documents${qs ? `?${qs}` : ''}`);
	},
	listCategories: () =>
		api.get<{ id: number; code: string; libelle: string }[]>('/documents/categories'),
	update: (id: number, data: { titre?: string; annee?: number | null; date_ag?: string | null }) =>
		api.patch<Document>(`/documents/${id}`, data),
	upload: async (
		titre: string,
		categorieId: number,
		file: File,
		perimetre = 'résidence',
		batimentId?: number,
		annee?: number,
		dateAg?: string,
		batimentsIdsJson?: string,
	): Promise<Document> => {
		const form = new FormData();
		form.append('titre', titre);
		form.append('categorie_id', String(categorieId));
		form.append('perimetre', perimetre);
		if (batimentId) form.append('batiment_id', String(batimentId));
		if (annee) form.append('annee', String(annee));
		if (dateAg) form.append('date_ag', dateAg);
		if (batimentsIdsJson) form.append('batiments_ids_json', batimentsIdsJson);
		form.append('file', file);
		const res = await fetch(`${BASE}/documents`, { method: 'POST', body: form, credentials: 'include' });
		if (!res.ok) {
			let detail = 'Erreur upload';
			try { const err = await res.json(); detail = err.detail ?? detail; } catch { /* ignore */ }
			throw new ApiError(res.status, detail);
		}
		return res.json();
	},
	uploadForContrat: async (titre: string, contratId: number, file: File): Promise<any> => {
		const form = new FormData();
		form.append('titre', titre);
		form.append('contrat_id', String(contratId));
		form.append('file', file);
		const res = await fetch(`${BASE}/documents`, { method: 'POST', body: form, credentials: 'include' });
		if (!res.ok) {
			let detail = 'Erreur upload';
			try { const err = await res.json(); detail = err.detail ?? detail; } catch { /* ignore */ }
			throw new ApiError(res.status, detail);
		}
		return res.json();
	},
	downloadUrl: (docId: number) => `${BASE}/documents/${docId}/télécharger`,
	delete: (id: number) => api.delete(`/documents/${id}`),
};

export const lots = {
	mesList: () => api.get<any[]>('/lots/mes-lots'),
	get: (id: number) => api.get<any>(`/lots/${id}`),
	mesCommandes: () => api.get<any[]>('/lots/commandes-acces/mes-commandes'),
	creerCommande: (data: unknown) => api.post<any>('/lots/commandes-acces', data),
	// Admin — tous les lots
	tous: () => api.get<any[]>('/lots/admin/tous'),
	// Admin — import staging
	uploadImport: (file: File, remplacer = false) => uploadExcel('/lots/admin/imports/upload', file, remplacer),
	listImports: (statut?: string, tri?: string) =>
		api.get<any[]>(`/lots/admin/imports${buildQuery({ statut, tri })}`),
	statsImports: () => api.get<any>('/lots/admin/imports/stats'),
	autoMatchImports: () => api.post<any>('/lots/admin/imports/auto-match', {}),
	autoResoudreImports: () => api.post<any>('/lots/admin/imports/auto-resoudre', {}),
	patchImport: (id: number, data: { lot_id?: number | null; utilisateurs?: {user_id: number; type_lien: string}[]; notes_admin?: string | null }) => api.patch<any>(`/lots/admin/imports/${id}`, data),
	resoudreImport: (id: number) => api.post<any>(`/lots/admin/imports/${id}/resoudre`, {}),
	ignorerimport: (id: number) => api.post<any>(`/lots/admin/imports/${id}/ignorer`, {}),
};

export const notifications = {
	list: () => api.get<Notification[]>('/notifications'),
	markRead: (id: number) => api.patch<Notification>(`/notifications/${id}/lue`),
	markAllRead: () => api.post('/notifications/tout-marquer-lu'),
	delete: (id: number) => api.delete(`/notifications/${id}`),
};

export const acces = {
	mesVigiks: () => api.get<any[]>('/acces/mes-vigiks'),
	mesTelecommandes: () => api.get<any[]>('/acces/mes-telecommandes'),
	mesCommandes: () => api.get<any[]>('/acces/mes-commandes'),
	creerCommande: (data: unknown) => api.post<any>('/acces/commandes', data),
	signalerVigiKPerdu: (id: number) => api.patch(`/acces/vigiks/${id}/perdu`, {}),
	signalerTcPerdu: (id: number) => api.patch(`/acces/telecommandes/${id}/perdu`, {}),
	supprimerVigik: (id: number) => api.delete(`/acces/vigiks/${id}`),
	supprimerTc: (id: number) => api.delete(`/acces/telecommandes/${id}`),
	declarerBadge: (data: { type: string; code: string }) => api.post<any>('/acces/declarer-badge', data),
	// CS/Admin — badges individuels
	listVigiks: () => api.get<any[]>('/acces/admin/vigiks'),
	listTelecommandes: () => api.get<any[]>('/acces/admin/telecommandes'),
	updateVigik: (id: number, data: unknown) => api.patch(`/acces/admin/vigiks/${id}`, data),
	creerVigik: (data: unknown) => api.post('/acces/admin/vigiks', data),
	creerTelecommande: (data: unknown) => api.post('/acces/admin/telecommandes', data),
	// CS/Admin — import vigik
	uploadImportVigik: (file: File, remplacer = false) => uploadExcel('/acces/admin/imports-vigik/upload', file, remplacer),
	listImportsVigik: (statut?: string) => api.get<any[]>(`/acces/admin/imports-vigik${statut ? `?statut=${statut}` : ''}`),
	statsImportsVigik: () => api.get<any>('/acces/admin/imports-vigik/stats'),
	autoMatchImportsVigik: () => api.post<any>('/acces/admin/imports-vigik/auto-match', {}),
	patchImportVigik: (id: number, data: unknown) => api.patch<any>(`/acces/admin/imports-vigik/${id}`, data),
	resoudreImportVigik: (id: number) => api.post<any>(`/acces/admin/imports-vigik/${id}/resoudre`, {}),
	ignorerImportVigik: (id: number) => api.post<any>(`/acces/admin/imports-vigik/${id}/ignorer`, {}),
	// CS/Admin — import télécommandes
	uploadImportTC: (file: File, remplacer = false) => uploadExcel('/acces/admin/imports/upload', file, remplacer),
	listImportsTC: (statut?: string) => api.get<any[]>(`/acces/admin/imports${statut ? `?statut=${statut}` : ''}`),
	statsImportsTC: () => api.get<any>('/acces/admin/imports/stats'),
	autoMatchImportsTC: () => api.post<any>('/acces/admin/imports/auto-match', {}),
	patchImportTC: (id: number, data: unknown) => api.patch<any>(`/acces/admin/imports/${id}`, data),
	resoudreImportTC: (id: number) => api.post<any>(`/acces/admin/imports/${id}/resoudre`, {}),
	ignorerImportTC: (id: number) => api.post<any>(`/acces/admin/imports/${id}/ignorer`, {}),
	remettreEnAttenteImportTC: (id: number) => api.post<any>(`/acces/admin/imports/${id}/remettre-en-attente`, {}),
};

export const calendrier = {
	list: () => api.get<any[]>('/calendrier'),
	get: (id: number) => api.get<any>(`/calendrier/${id}`),
	create: (data: unknown) => api.post<any>('/calendrier', data),
	update: (id: number, data: unknown) => api.patch<any>(`/calendrier/${id}`, data),
	archive: (id: number) => api.patch<any>(`/calendrier/${id}`, { archivee: true }),
	delete: (id: number) => api.delete(`/calendrier/${id}`),
};

export const prestataires = {
	list: () => api.get<any[]>('/prestataires'),
	create: (data: unknown) => api.post<any>('/prestataires', data),
	update: (id: number, data: unknown) => api.patch<any>(`/prestataires/${id}`, data),
	delete: (id: number) => api.delete(`/prestataires/${id}`),
	contrats: () => api.get<any[]>('/prestataires/contrats'),
	createContrat: (data: unknown) => api.post<any>('/prestataires/contrats', data),
	updateContrat: (id: number, data: unknown) => api.patch<any>(`/prestataires/contrats/${id}`, data),
	deleteContrat: (id: number) => api.delete(`/prestataires/contrats/${id}`),
	devis: () => api.get<any[]>('/prestataires/devis'),
	createDevis: (data: unknown) => api.post<any>('/prestataires/devis', data),
	updateDevis: (id: number, data: unknown) => api.patch<any>(`/prestataires/devis/${id}`, data),
	deleteDevis: (id: number) => api.delete(`/prestataires/devis/${id}`),
	uploadDevisFichier: async (id: number, file: File) => {
		const fd = new FormData();
		fd.append('file', file);
		const res = await fetch(`${BASE}/prestataires/devis/${id}/fichier`, { method: 'POST', body: fd, credentials: 'include' });
		if (!res.ok) {
			let detail = 'Erreur upload fichier';
			try { const err = await res.json(); detail = err.detail ?? detail; } catch { /* ignore */ }
			throw new ApiError(res.status, detail);
		}
		return res.json();
	},
	deleteDevisFichier: async (id: number, url: string) => {
		const res = await fetch(`${BASE}/prestataires/devis/${id}/fichier?url=${encodeURIComponent(url)}`, { method: 'DELETE', credentials: 'include' });
		if (!res.ok) {
			let detail = 'Erreur suppression fichier';
			try { const err = await res.json(); detail = err.detail ?? detail; } catch { /* ignore */ }
			throw new ApiError(res.status, detail);
		}
		return res.json();
	},
	uploadDevisOs: async (id: number, file: File) => {
		const fd = new FormData();
		fd.append('file', file);
		const res = await fetch(`${BASE}/prestataires/devis/${id}/os`, { method: 'POST', body: fd, credentials: 'include' });
		if (!res.ok) {
			let detail = 'Erreur upload OS';
			try { const err = await res.json(); detail = err.detail ?? detail; } catch { /* ignore */ }
			throw new ApiError(res.status, detail);
		}
		return res.json();
	},
	releves: (type_compteur?: string) => api.get<any[]>(`/prestataires/releves${type_compteur ? '?type_compteur=' + encodeURIComponent(type_compteur) : ''}`),
	createReleve: (data: unknown) => api.post<any>('/prestataires/releves', data),
	updateReleve: (id: number, data: unknown) => api.patch<any>(`/prestataires/releves/${id}`, data),
	deleteReleve: (id: number) => api.delete(`/prestataires/releves/${id}`),
	uploadRelevePhoto: async (id: number, file: File) => {
		const fd = new FormData();
		fd.append('file', file);
		const res = await fetch(`${BASE}/prestataires/releves/${id}/photo`, { method: 'POST', body: fd, credentials: 'include' });
		if (!res.ok) {
			let detail = 'Erreur upload photo';
			try { const err = await res.json(); detail = err.detail ?? detail; } catch { /* ignore */ }
			throw new ApiError(res.status, detail);
		}
		return res.json();
	},
	compteurConfigs: () => api.get<any[]>('/prestataires/compteurs-config'),
	createCompteurConfig: (data: unknown) => api.post<any>('/prestataires/compteurs-config', data),
	updateCompteurConfig: (id: number, data: unknown) => api.patch<any>(`/prestataires/compteurs-config/${id}`, data),
	deleteCompteurConfig: (id: number) => api.delete(`/prestataires/compteurs-config/${id}`),
};

export const sondages = {
	list: () => api.get<any[]>('/sondages'),
	get: (id: number) => api.get<any>(`/sondages/${id}`),
	create: (data: unknown) => api.post<any>('/sondages', data),
	modifier: (id: number, data: unknown) => api.patch<any>(`/sondages/${id}`, data),
	supprimer: (id: number) => api.delete(`/sondages/${id}`),
	cloturer: (id: number) => api.patch<any>(`/sondages/${id}/cloturer`, {}),
	voter: (id: number, option_id: number, commentaire?: string, reponse_libre?: string) =>
		api.post(`/sondages/${id}/voter`, { option_id, commentaire: commentaire || null, reponse_libre: reponse_libre || null }),
	commenter: (id: number, contenu: string) =>
		api.post<any>(`/sondages/${id}/commenter`, { contenu }),
	supprimerCommentaire: (sondageId: number, commentaireId: number) =>
		api.delete(`/sondages/${sondageId}/commentaires/${commentaireId}`),
};

// ── Upload fichiers ─────────────────────────────────────────────────────────

async function uploadFile(path: string, file: File): Promise<{ url: string }> {
	const form = new FormData();
	form.append('file', file);
	const res = await fetch(`${BASE}${path}`, {
		method: 'POST',
		body: form,
		credentials: 'include',
	});
	if (!res.ok) {
		let detail = 'Erreur upload';
		try { const err = await res.json(); detail = err.detail ?? detail; } catch { /* ignore */ }
		throw new ApiError(res.status, detail);
	}
	return res.json();
}

async function uploadExcel<T = any>(path: string, file: File, remplacer = false): Promise<T> {
	const form = new FormData();
	form.append('file', file);
	const url = `${BASE}${path}${remplacer ? '?remplacer=true' : ''}`;
	const res = await fetch(url, { method: 'POST', body: form, credentials: 'include' });
	if (!res.ok) {
		let detail = 'Erreur import';
		try { const err = await res.json(); detail = err.detail ?? detail; } catch { /* ignore */ }
		throw new ApiError(res.status, detail);
	}
	return res.json();
}

export const faq = {
	list: () => api.get<any[]>('/faq'),
	listAll: () => api.get<any[]>('/faq/all'),
	create: (data: unknown) => api.post<any>('/faq', data),
	update: (id: number, data: unknown) => api.patch<any>(`/faq/${id}`, data),
	delete: (id: number) => api.delete(`/faq/${id}`),
};

export const diagnostics = {
	listTypes: () => api.get<any[]>('/diagnostics/types'),
	uploadRapport: async (typeId: number, titre: string, dateRapport: string | undefined, file: File): Promise<any> => {
		const form = new FormData();
		form.append('titre', titre);
		if (dateRapport) form.append('date_rapport', dateRapport);
		form.append('file', file);
		const res = await fetch(`${BASE}/diagnostics/types/${typeId}/rapports`, {
			method: 'POST',
			body: form,
			credentials: 'include',
		});
		if (!res.ok) {
			let detail = 'Erreur upload';
			try { const err = await res.json(); detail = err.detail ?? detail; } catch { /* ignore */ }
			throw new ApiError(res.status, detail);
		}
		return res.json();
	},
	updateRapport: (id: number, data: { titre?: string; date_rapport?: string | null }) =>
		api.patch<any>(`/diagnostics/rapports/${id}`, data),
	deleteRapport: (id: number) => api.delete(`/diagnostics/rapports/${id}`),
	downloadUrl: (id: number) => `${BASE}/diagnostics/rapports/${id}/télécharger`,
	toggleNonApplicable: (typeId: number, nonApplicable: boolean) =>
		api.patch<any>(`/diagnostics/types/${typeId}/non-applicable`, { non_applicable: nonApplicable }),
};

export const annuaire = {
	get: () => api.get<{ cs: { ag_annee: number | null; ag_date: string | null; membres: any[] }; syndic: { nom_syndic: string; adresse: string; membres: any[] } }>('/admin/annuaire'),
};

export const annuaireAdmin = {
	getCS:     () => api.get<any>('/admin/annuaire/cs'),
	putCS:     (data: unknown) => api.put<any>('/admin/annuaire/cs', data),
	getSyndic: () => api.get<any>('/admin/annuaire/syndic'),
	putSyndic: (data: unknown) => api.put<any>('/admin/annuaire/syndic', data),
};

export const uploads = {
	avatar: (file: File) => uploadFile('/uploads/avatar', file),
	residence: (file: File) => uploadFile('/uploads/residence', file),
	publication: (id: number, file: File) => uploadFile(`/uploads/publication/${id}`, file),
};

export const idees = {
	list: () => api.get<any[]>('/idees'),
	create: (data: unknown) => api.post<any>('/idees', data),
	voter: (id: number) => api.post(`/idees/${id}/voter`),
	updateStatut: (id: number, statut: string) => api.patch(`/idees/${id}/statut`, { statut }),
	delete: (id: number) => api.delete(`/idees/${id}`),
};

export const annonces = {
	list: () => api.get<any[]>('/annonces'),
	create: (data: unknown) => api.post<any>('/annonces', data),
	updateStatut: (id: number, statut: string) => api.patch(`/annonces/${id}/statut`, { statut }),
	supprimer: (id: number) => api.delete(`/annonces/${id}`),
	uploadPhoto: async (id: number, file: File): Promise<{ url: string; photos: string[] }> => {
		const form = new FormData();
		form.append('file', file);
		const res = await fetch(`${BASE}/annonces/${id}/photo`, { method: 'POST', body: form, credentials: 'include' });
		if (!res.ok) {
			let detail = 'Erreur upload';
			try { const err = await res.json(); detail = err.detail ?? detail; } catch { /* ignore */ }
			throw new ApiError(res.status, detail);
		}
		return res.json();
	},
	deletePhoto: (id: number, url: string) => api.delete(`/annonces/${id}/photo?url=${encodeURIComponent(url)}`),
};

export const copropriete = {
	get: () => api.get<any>('/copropriete'),
	update: (data: unknown) => api.patch<any>('/copropriete', data),
	batiments: () => api.get<any[]>('/copropriete/batiments'),
	lots: (batiment_id?: number) =>
		api.get<any[]>(`/copropriete/lots${batiment_id ? `?batiment_id=${batiment_id}` : ''}`),
};

export const reglesResidence = {
	list: () => api.get<any[]>('/regles-residence'),
	create: (data: { titre: string; contenu?: string }) => api.post<any>('/regles-residence', data),
	update: (id: number, data: { titre?: string; contenu?: string; ordre?: number }) =>
		api.patch<any>(`/regles-residence/${id}`, data),
	remove: (id: number) => api.delete(`/regles-residence/${id}`),
};

export const delegations = {
	list: () => api.get<any[]>('/delegations'),
	create: (data: { mandant_id: number; aidant_id: number; motif?: string; date_fin?: string }) =>
		api.post<any>('/delegations', data),
	update: (id: number, data: { motif?: string; date_fin?: string }) =>
		api.patch<any>(`/delegations/${id}`, data),
	accepter: (id: number) => api.post<any>(`/delegations/${id}/accepter`),
	revoquer: (id: number) => api.post<any>(`/delegations/${id}/revoquer`),
	mesMandants: () => api.get<any[]>('/delegations/mes-mandants'),
};

export const bailleur = {
	mesBaux: () => api.get<any[]>('/bailleur/mes-baux'),
	creerBail: (lot_id: number, data: unknown) => api.post<any>(`/bailleur/lots/${lot_id}/bail`, data),
	creerBailMulti: (data: unknown) => api.post<any[]>('/bailleur/baux/creer-multi', data),
	getBail: (id: number) => api.get<any>(`/bailleur/baux/${id}`),
	updateBail: (id: number, data: unknown) => api.patch<any>(`/bailleur/baux/${id}`, data),
	terminerBail: (id: number, data: unknown) => api.post<any>(`/bailleur/baux/${id}/terminer`, data),
	ajouterObjet: (bail_id: number, data: unknown) => api.post<any>(`/bailleur/baux/${bail_id}/objets`, data),
	updateObjet: (bail_id: number, obj_id: number, data: unknown) =>
		api.patch<any>(`/bailleur/baux/${bail_id}/objets/${obj_id}`, data),
	retourObjet: (bail_id: number, obj_id: number, data: unknown) =>
		api.post<any>(`/bailleur/baux/${bail_id}/objets/${obj_id}/retour`, data),
	supprimerObjet: (bail_id: number, obj_id: number) =>
		api.delete(`/bailleur/baux/${bail_id}/objets/${obj_id}`),
	supprimerBail: (bail_id: number) =>
		api.delete(`/bailleur/baux/${bail_id}`),
	tousBaux: () => api.get<any[]>('/bailleur/tous-les-baux'),
	// Recherche locataire & gestion accès
	searchLocataire: (q: string) =>
		api.get<any[]>(`/bailleur/search-locataire?q=${encodeURIComponent(q)}`),
	locatairesSuggeres: () => api.get<any[]>('/bailleur/locataires-suggeres'),
	accesBail: (bail_id: number) =>
		api.get<any[]>(`/bailleur/baux/${bail_id}/acces`),
	transfererAcces: (bail_id: number, data: { vigik_ids: number[]; tc_ids: number[] }) => 
		api.post<any[]>(`/bailleur/baux/${bail_id}/transferer-acces`, data),
	recupererAcces: (bail_id: number, data?: { vigik_ids: number[]; tc_ids: number[] }) =>
		api.post<any[]>(`/bailleur/baux/${bail_id}/recuperer-acces`, data ?? {}),
	mesAccesRecus: () => api.get<any[]>('/bailleur/mes-acces-recus'),
	monBail: () => api.get<any>('/bailleur/mon-bail'),
};

export const admin = {
	// Comptes
	comptesEnAttente: () => api.get<any[]>('/admin/comptes-en-attente'),
	pendingAccounts: () => api.get<any[]>('/admin/comptes-en-attente'),
	traiterCompte: (id: number, data: { action: string; motif?: string }) =>
		api.post(`/admin/comptes/${id}/traiter`, data),
	// Commandes accès
	commandesAccesEnAttente: () => api.get<any[]>('/admin/commandes-acces'),
	traiterCommandeAcces: (id: number, data: { action: string; motif_refus?: string }) =>
		api.post(`/admin/commandes-acces/${id}/traiter`, data),
	// Sauvegardes
	backupConfig: () => api.get<any>('/admin/sauvegardes/config'),
	updateBackupConfig: (data: unknown) => api.put<any>('/admin/sauvegardes/config', data),
	triggerBackup: () => api.post('/admin/sauvegardes/maintenant'),
	backupHistory: () => api.get<any[]>('/admin/sauvegardes/historique'),
	// Modèles e-mail
	emailTemplates: () => api.get<any[]>('/admin/modeles-email'),
	updateEmailTemplate: (id: number, data: unknown) => api.patch(`/admin/modeles-email/${id}`, data),
	// Utilisateurs & rôles
	utilisateurs: () => api.get<any[]>('/admin/utilisateurs'),
	changerRole: (id: number, role: string) => api.post(`/admin/utilisateurs/${id}/changer-role`, { role }),
	ajouterRole: (id: number, role: string) => api.post(`/admin/utilisateurs/${id}/ajouter-role`, { role }),
	retirerRole: (id: number, role: string) => api.post(`/admin/utilisateurs/${id}/retirer-role`, { role }),
	// Demandes de modification de profil
	demandesProfil: () => api.get<any[]>('/admin/demandes-profil'),
	traiterDemandeProfil: (id: number, data: { action: string; motif_refus?: string }) =>
		api.post(`/admin/demandes-profil/${id}/traiter`, data),
	// Baux locatifs
	baux: () => api.get<any[]>('/admin/baux'),
	lierLocataire: (bail_id: number, user_id: number) =>
		api.post(`/admin/baux/${bail_id}/lier-locataire/${user_id}`, {}),
	// Audit associations user-lot
	auditUserLots: () => api.get<any[]>('/admin/audit/user-lots'),
	supprimerUserLot: (id: number) => api.delete(`/admin/user-lots/${id}`),
};

export const config = {
        get: (): Promise<Record<string, string>> => api.get<Record<string, string>>('/config'),
        save: (data: Record<string, string>): Promise<void> => api.put('/config', data),
};
