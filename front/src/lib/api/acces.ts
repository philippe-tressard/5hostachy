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

/**
 *  Un badge vu par le conseil syndical — le code, et surtout **qui le porte**.
 *
 *  ⚠️ Le type vit ici parce que c'est une réponse d'API (même raison que
 *  `ObjetRemis` et `ReleveOrphelins`). Il ne décrit PAS la table : `user_id` et
 *  `lot_id` y sont résolus en nom et en libellé côté serveur, une fois, plutôt
 *  que par un rapprochement que chaque écran referait à sa façon.
 */
export interface AccesAdmin {
	id: number;
	code: string;
	statut: string;
	/** Vrai quand le bailleur a transféré le badge à son locataire. */
	chez_locataire: boolean;
	porteur_nom: string;
	porteur_id: number;
	lot_libelle: string | null;
	cree_le: string;
}

export const acces = {
	mesVigiks: () => api.get<any[]>('/acces/mes-vigiks'),
	mesTelecommandes: () => api.get<any[]>('/acces/mes-telecommandes'),
	mesCommandes: () => api.get<any[]>('/acces/mes-commandes'),
	creerCommande: (data: unknown) => api.post<any>('/acces/commandes', data),
	signalerVigiKPerdu: (id: number) => api.patch(`/acces/vigiks/${id}/perdu`, {}),
	signalerTcPerdu: (id: number) => api.patch(`/acces/telecommandes/${id}/perdu`, {}),
	supprimerVigik: (id: number) => api.delete(`/acces/vigiks/${id}`),
	supprimerTc: (id: number) => api.delete(`/acces/telecommandes/${id}`),
	declarerBadge: (data: { type: string; code: string }) =>
		api.post<any>('/acces/declarer-badge', data),
	//  ── CS/Admin — QUELS badges circulent, et chez qui ────────────────────────
	//
	//  🔴 Ces deux routes ont porté la déclaration « sans appelant » de #805, avec
	//  trois autres qui CRÉAIENT et MODIFIAIENT des badges. Arbitrage du
	//  06/09/2026 : **lecture seule**. Les trois routes d'écriture ont été
	//  supprimées, client et endpoints.
	//
	//  Pourquoi celles-ci restent : elles répondent à une question qu'aucun autre
	//  écran ne sait poser — « qui a le badge 4521 ? ». Pourquoi les autres sont
	//  parties : enregistrer un badge est déjà couvert deux fois, par l'import
	//  Excel (en masse) et par `declarerBadge` (le résident, à l'unité). Une
	//  troisième voie jamais exercée est du code qui dérive sans qu'on le voie.
	//
	//  ⚠️ La réponse a été ENRICHIE en même temps qu'exposée : elle rendait
	//  l'objet brut, donc `user_id` — un écran bâti dessus aurait affiché
	//  « badge 4521 → utilisateur 37 ». Une route sans appelant n'est jamais mise
	//  à l'épreuve de la question à laquelle elle est censée répondre.
	listVigiks: () => api.get<AccesAdmin[]>('/acces/admin/vigiks'),
	listTelecommandes: () => api.get<AccesAdmin[]>('/acces/admin/telecommandes'),
	// CS/Admin — import vigik
	uploadImportVigik: (file: File, remplacer = false) =>
		uploadExcel('/acces/admin/imports-vigik/upload', file, remplacer),
	listImportsVigik: (statut?: string) =>
		api.get<any[]>(`/acces/admin/imports-vigik${statut ? `?statut=${statut}` : ''}`),
	statsImportsVigik: () => api.get<any>('/acces/admin/imports-vigik/stats'),
	autoMatchImportsVigik: () => api.post<any>('/acces/admin/imports-vigik/auto-match', {}),
	patchImportVigik: (id: number, data: unknown) =>
		api.patch<any>(`/acces/admin/imports-vigik/${id}`, data),
	resoudreImportVigik: (id: number) =>
		api.post<any>(`/acces/admin/imports-vigik/${id}/resoudre`, {}),
	ignorerImportVigik: (id: number) => api.post<any>(`/acces/admin/imports-vigik/${id}/ignorer`, {}),
	remettreEnAttenteImportVigik: (id: number) =>
		api.post<any>(`/acces/admin/imports-vigik/${id}/remettre-en-attente`, {}),
	// CS/Admin — import télécommandes
	uploadImportTC: (file: File, remplacer = false) =>
		uploadExcel('/acces/admin/imports/upload', file, remplacer),
	listImportsTC: (statut?: string) =>
		api.get<any[]>(`/acces/admin/imports${statut ? `?statut=${statut}` : ''}`),
	statsImportsTC: () => api.get<any>('/acces/admin/imports/stats'),
	autoMatchImportsTC: () => api.post<any>('/acces/admin/imports/auto-match', {}),
	patchImportTC: (id: number, data: unknown) => api.patch<any>(`/acces/admin/imports/${id}`, data),
	resoudreImportTC: (id: number) => api.post<any>(`/acces/admin/imports/${id}/resoudre`, {}),
	ignorerImportTC: (id: number) => api.post<any>(`/acces/admin/imports/${id}/ignorer`, {}),
	remettreEnAttenteImportTC: (id: number) =>
		api.post<any>(`/acces/admin/imports/${id}/remettre-en-attente`, {}),
};
