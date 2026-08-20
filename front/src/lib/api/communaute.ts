//  Le domaine **Communauté** : sondages, boîte à idées, petites annonces et
//  signalements. Quatre clients qui servent une seule page (`/sondages`, ses
//  trois onglets) et qui vivaient dispersés sur 130 lignes d'`index.ts`.
//
//  Extrait quand le contrôle de modularité a refusé qu'`index.ts` dépasse 500
//  lignes en recevant `deleteEvolution` (#512). Le refus disait vrai : un
//  fichier qui expose vingt-six domaines n'a pas un problème de taille, il a un
//  problème de découpage — et `documents.ts` avait déjà montré la voie.
import { api, ApiError, BASE } from './client';

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

export const idees = {
	list: () => api.get<any[]>('/idees'),
	create: (data: unknown) => api.post<any>('/idees', data),
	voter: (id: number) => api.post(`/idees/${id}/voter`),
	updateStatut: (id: number, statut: string) => api.patch(`/idees/${id}/statut`, { statut }),
	delete: (id: number) => api.delete(`/idees/${id}`),
	listReponses: (id: number) => api.get<any[]>(`/idees/${id}/reponses`),
	repondre: (id: number, contenu: string) => api.post<any>(`/idees/${id}/reponses`, { contenu }),
	supprimerReponse: (id: number, repId: number) => api.delete(`/idees/${id}/reponses/${repId}`),
};

export const annonces = {
	list: () => api.get<any[]>('/annonces'),
	create: (data: unknown) => api.post<any>('/annonces', data),
	//  La CORRECTION d'une annonce — `PATCH /annonces/{id}` existait depuis
	//  toujours, avec ses sept champs, et aucun écran ne l'appelait (18/08/2026).
	update: (id: number, data: unknown) => api.patch<any>(`/annonces/${id}`, data),
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
	listReponses: (id: number) => api.get<any[]>(`/annonces/${id}/reponses`),
	repondre: (id: number, contenu: string) => api.post<any>(`/annonces/${id}/reponses`, { contenu }),
	supprimerReponse: (id: number, repId: number) => api.delete(`/annonces/${id}/reponses/${repId}`),
};

export const signalements = {
	creer: (cible_type: string, cible_id: number, motif: string) =>
		api.post('/signalements', { cible_type, cible_id, motif }),
	liste: (statut = 'en_attente') => api.get<any[]>(`/signalements?statut=${statut}`),
	count: () => api.get<{ en_attente: number }>('/signalements/count'),
	resoudre: (id: number, statut: 'traite' | 'rejete') =>
		api.patch(`/signalements/${id}`, { statut }),
};
