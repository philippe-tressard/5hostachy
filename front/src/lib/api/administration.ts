//  L'ADMINISTRATION : comptes et validations, délégations d'aidant, réglages du
//  site. Ce que seuls l'administrateur et le conseil syndical appellent.
//
//  ⚠️ Fragment de `lib/api/` — extrait de `index.ts` le 27/08/2026 (#453). Ce
//  fichier portait VINGT ET UN domaines et 437 lignes ; `client.ts`, `types.ts`,
//  `documents.ts` et `communaute.ts` en étaient déjà sortis en leur temps, la
//  coupe suit donc une couture existante et non le compteur de lignes.
//
//  ⚠️ La surface publique NE BOUGE PAS : `index.ts` réexporte tout, et les
//  quarante et un `from '$lib/api'` du front ne changent pas d'une ligne.
import { api } from './client';

export const annuaireAdmin = {
	getCS: () => api.get<any>('/admin/annuaire/cs'),
	putCS: (data: unknown) => api.put<any>('/admin/annuaire/cs', data),
	getSyndic: () => api.get<any>('/admin/annuaire/syndic'),
	putSyndic: (data: unknown) => api.put<any>('/admin/annuaire/syndic', data),
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
	// Modèles e-mail
	emailTemplates: () => api.get<any[]>('/admin/modeles-email'),
	updateEmailTemplate: (id: number, data: unknown) => api.patch(`/admin/modeles-email/${id}`, data),
	resetEmailTemplates: () => api.post<{ message: string }>('/admin/modeles-email/reinitialiser'),
	// Utilisateurs & rôles
	utilisateurs: () => api.get<any[]>('/admin/utilisateurs'),
	changerRole: (id: number, role: string) =>
		api.post(`/admin/utilisateurs/${id}/changer-role`, { role }),
	ajouterRole: (id: number, role: string) =>
		api.post(`/admin/utilisateurs/${id}/ajouter-role`, { role }),
	retirerRole: (id: number, role: string) =>
		api.post(`/admin/utilisateurs/${id}/retirer-role`, { role }),
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
	// Télémétrie
	telemetryDashboard: () => api.get<any>('/telemetry/dashboard'),
	telemetryUsersActive: () => api.get<any[]>('/telemetry/users-active'),
	telemetryAgreger: () => api.post('/admin/telemetry/agreger'),
	telemetryHistorique: () => api.get<any[]>('/admin/telemetry/historique'),
};

export const config = {
	get: (): Promise<Record<string, string>> => api.get<Record<string, string>>('/config'),
	save: (data: Record<string, string>): Promise<void> => api.put('/config', data),
};
