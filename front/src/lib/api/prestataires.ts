//  Les PRESTATAIRES : fiches, contrats d'entretien, relevés de compteurs et
//  notations.
//
//  ⚠️ Les huit méthodes « devis » sont parties avec la prestation ponctuelle
//  (#603). `ApiError` et `BASE` les ont suivies : ils ne servaient qu'à
//  `deleteDevisFichier`, seul appel de ce fichier à ne pas passer par `api`.
//
//  ⚠️ Fragment de `lib/api/` — extrait de `index.ts` le 27/08/2026 (#453). Ce
//  fichier portait VINGT ET UN domaines et 437 lignes ; `client.ts`, `types.ts`,
//  `documents.ts` et `communaute.ts` en étaient déjà sortis en leur temps, la
//  coupe suit donc une couture existante et non le compteur de lignes.
//
//  ⚠️ La surface publique NE BOUGE PAS : `index.ts` réexporte tout, et les
//  quarante et un `from '$lib/api'` du front ne changent pas d'une ligne.
import { api, postFormData } from './client';

export const prestataires = {
	list: () => api.get<any[]>('/prestataires'),
	create: (data: unknown) => api.post<any>('/prestataires', data),
	update: (id: number, data: unknown) => api.patch<any>(`/prestataires/${id}`, data),
	delete: (id: number) => api.delete(`/prestataires/${id}`),
	contrats: () => api.get<any[]>('/prestataires/contrats'),
	createContrat: (data: unknown) => api.post<any>('/prestataires/contrats', data),
	updateContrat: (id: number, data: unknown) =>
		api.patch<any>(`/prestataires/contrats/${id}`, data),
	deleteContrat: (id: number) => api.delete(`/prestataires/contrats/${id}`),
	releves: (type_compteur?: string) =>
		api.get<any[]>(
			`/prestataires/releves${type_compteur ? '?type_compteur=' + encodeURIComponent(type_compteur) : ''}`,
		),
	createReleve: (data: unknown) => api.post<any>('/prestataires/releves', data),
	updateReleve: (id: number, data: unknown) => api.patch<any>(`/prestataires/releves/${id}`, data),
	deleteReleve: (id: number) => api.delete(`/prestataires/releves/${id}`),
	uploadRelevePhoto: (id: number, file: File) =>
		postFormData(`/prestataires/releves/${id}/photo`, { file }),
	compteurConfigs: () => api.get<any[]>('/prestataires/compteurs-config'),
	createCompteurConfig: (data: unknown) => api.post<any>('/prestataires/compteurs-config', data),
	updateCompteurConfig: (id: number, data: unknown) =>
		api.patch<any>(`/prestataires/compteurs-config/${id}`, data),
	deleteCompteurConfig: (id: number) => api.delete(`/prestataires/compteurs-config/${id}`),
	// Notations
	notations: (prestataireId?: number) =>
		api.get<any[]>(
			`/prestataires/notations${prestataireId ? '?prestataire_id=' + prestataireId : ''}`,
		),
	createNotation: (data: {
		prestataire_id: number;
		note: number;
		commentaire?: string;
		contrat_id?: number;
	}) => api.post<any>('/prestataires/notations', data),
	//  @sans-appelant Aucun bouton ne permet de retirer sa propre notation : une
	//  fois publiée, elle est définitive — et elle nomme un tiers. (#807)
	deleteNotation: (id: number) => api.delete(`/prestataires/notations/${id}`),
	// Synthèse
	synthese: (prestataireId: number) => api.get<any>(`/prestataires/synthese/${prestataireId}`),
};
