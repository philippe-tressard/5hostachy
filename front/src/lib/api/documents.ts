//  Documents, fichiers et téléversements : trois clients qui manipulent la
//  même notion et vivaient à 400 lignes d'écart.
import { api, ApiError, BASE } from './client';
import type { Document } from './types';

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
	uploadForPublication: async (titre: string, publicationId: number, file: File): Promise<any> => {
		const form = new FormData();
		form.append('titre', titre);
		form.append('publication_id', String(publicationId));
		form.append('file', file);
		const res = await fetch(`${BASE}/documents`, { method: 'POST', body: form, credentials: 'include' });
		if (!res.ok) {
			let detail = 'Erreur upload';
			try { const err = await res.json(); detail = err.detail ?? detail; } catch { /* ignore */ }
			throw new ApiError(res.status, detail);
		}
		return res.json();
	},
	listByPublication: (publicationId: number) => api.get<any[]>(`/documents?publication_id=${publicationId}`),
	downloadUrl: (docId: number) => `${BASE}/documents/${docId}/télécharger`,
	delete: (id: number) => api.delete(`/documents/${id}`),
};


export const fichiersApi = {
	/**
	 * Upload un fichier (photo ou document PDF/Word/Excel) destiné à être joint à
	 * un ticket, une affaire ou un commentaire. Ne demande aucun élément parent :
	 * l'URL est connue avant la création, ce qui permet de la passer dans le
	 * payload — et donc de la joindre à l'e-mail envoyé au syndic.
	 * Retourne { url, nom, type }
	 */
	upload: async (file: File): Promise<{ url: string; nom: string; type: string }> => {
		const fd = new FormData();
		fd.append('file', file);
		const res = await fetch(`${BASE}/uploads/fichier`, { method: 'POST', body: fd, credentials: 'include' });
		if (!res.ok) {
			let detail = 'Erreur upload fichier';
			try { const err = await res.json(); detail = err.detail ?? detail; } catch { /* ignore */ }
			throw new ApiError(res.status, detail);
		}
		return res.json();
	},
};

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

export async function uploadExcel<T = any>(path: string, file: File, remplacer = false): Promise<T> {
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


export const uploads = {
	avatar: (file: File) => uploadFile('/uploads/avatar', file),
	residence: (file: File) => uploadFile('/uploads/residence', file),
};
