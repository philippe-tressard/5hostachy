//  Les PRESTATAIRES : fiches, contrats d'entretien, devis, interventions,
//  relevés de compteurs et notations.
//
//  ⚠️ Fragment de `lib/api/` — extrait de `index.ts` le 27/08/2026 (#453). Ce
//  fichier portait VINGT ET UN domaines et 437 lignes ; `client.ts`, `types.ts`,
//  `documents.ts` et `communaute.ts` en étaient déjà sortis en leur temps, la
//  coupe suit donc une couture existante et non le compteur de lignes.
//
//  ⚠️ La surface publique NE BOUGE PAS : `index.ts` réexporte tout, et les
//  quarante et un `from '$lib/api'` du front ne changent pas d'une ligne.
import { api, postFormData, ApiError, BASE } from './client';

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
	uploadDevisFichier: (id: number, file: File) =>
		postFormData(`/prestataires/devis/${id}/fichier`, { file }),
	deleteDevisFichier: async (id: number, url: string) => {
		const res = await fetch(`${BASE}/prestataires/devis/${id}/fichier?url=${encodeURIComponent(url)}`, { method: 'DELETE', credentials: 'include' });
		if (!res.ok) {
			let detail = 'Erreur suppression fichier';
			try { const err = await res.json(); detail = err.detail ?? detail; } catch { /* ignore */ }
			throw new ApiError(res.status, detail);
		}
		return res.json();
	},
	uploadDevisOs: (id: number, file: File) => postFormData(`/prestataires/devis/${id}/os`, { file }),
	releves: (type_compteur?: string) => api.get<any[]>(`/prestataires/releves${type_compteur ? '?type_compteur=' + encodeURIComponent(type_compteur) : ''}`),
	createReleve: (data: unknown) => api.post<any>('/prestataires/releves', data),
	updateReleve: (id: number, data: unknown) => api.patch<any>(`/prestataires/releves/${id}`, data),
	deleteReleve: (id: number) => api.delete(`/prestataires/releves/${id}`),
	uploadRelevePhoto: (id: number, file: File) =>
		postFormData(`/prestataires/releves/${id}/photo`, { file }),
	compteurConfigs: () => api.get<any[]>('/prestataires/compteurs-config'),
	createCompteurConfig: (data: unknown) => api.post<any>('/prestataires/compteurs-config', data),
	updateCompteurConfig: (id: number, data: unknown) => api.patch<any>(`/prestataires/compteurs-config/${id}`, data),
	deleteCompteurConfig: (id: number) => api.delete(`/prestataires/compteurs-config/${id}`),
	// Notations
	notations: (prestataireId?: number) => api.get<any[]>(`/prestataires/notations${prestataireId ? '?prestataire_id=' + prestataireId : ''}`),
	createNotation: (data: { prestataire_id: number; note: number; commentaire?: string; devis_id?: number; contrat_id?: number }) => api.post<any>('/prestataires/notations', data),
	deleteNotation: (id: number) => api.delete(`/prestataires/notations/${id}`),
	// Synthèse
	synthese: (prestataireId: number) => api.get<any>(`/prestataires/synthese/${prestataireId}`),
};
