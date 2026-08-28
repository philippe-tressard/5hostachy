//  Le CONTRÔLE D'ACCÈS : badges Vigik, télécommandes, et les imports Excel qui
//  les alimentent. Un domaine à part parce qu'il a ses propres écrans
//  d'administration et son propre cycle d'appariement.
//
//  ⚠️ Fragment de `lib/api/` — extrait de `index.ts` le 27/08/2026 (#453). Ce
//  fichier portait VINGT ET UN domaines et 437 lignes ; `client.ts`, `types.ts`,
//  `documents.ts` et `communaute.ts` en étaient déjà sortis en leur temps, la
//  coupe suit donc une couture existante et non le compteur de lignes.
//
//  ⚠️ La surface publique NE BOUGE PAS : `index.ts` réexporte tout, et les
//  quarante et un `from '$lib/api'` du front ne changent pas d'une ligne.
import { api } from './client';
import { uploadExcel } from './documents';

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
	remettreEnAttenteImportVigik: (id: number) =>
		api.post<any>(`/acces/admin/imports-vigik/${id}/remettre-en-attente`, {}),
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
