//  La COPROPRIÉTÉ physique et ses occupations : la fiche, les lots, les baux,
//  l'arborescence des périmètres, les règles de vie et les diagnostics
//  réglementaires. Tout ce qui décrit le bâtiment et qui y habite.
//
//  ⚠️ Fragment de `lib/api/` — extrait de `index.ts` le 27/08/2026 (#453). Ce
//  fichier portait VINGT ET UN domaines et 437 lignes ; `client.ts`, `types.ts`,
//  `documents.ts` et `communaute.ts` en étaient déjà sortis en leur temps, la
//  coupe suit donc une couture existante et non le compteur de lignes.
//
//  ⚠️ La surface publique NE BOUGE PAS : `index.ts` réexporte tout, et les
//  quarante et un `from '$lib/api'` du front ne changent pas d'une ligne.
import { api, buildQuery, postFormData, BASE } from './client';
import { uploadExcel } from './documents';
import type { Perimetre as PerimetreDTO } from '$lib/perimetres';

/**  Un contrat proposable comme référence de la fiche de copropriété.
 *
 *   ⚠️ Volontairement pauvre : de quoi reconnaître le contrat dans une liste, et
 *   rien de plus. Les détails viennent de la fiche elle-même une fois le choix
 *   fait — deux chemins pour la même donnée en feraient deux vérités. */
export type ContratCandidat = {
	id: number;
	libelle: string;
	prestataire?: string | null;
	numero_contrat?: string | null;
	date_debut: string;
	actif: boolean;
};

export const copropriete = {
	get: () => api.get<any>('/copropriete'),
	update: (data: unknown) => api.patch<any>('/copropriete', data),
	batiments: () => api.get<any[]>('/copropriete/batiments'),
	lots: (batiment_id?: number) =>
		api.get<any[]>(`/copropriete/lots${batiment_id ? `?batiment_id=${batiment_id}` : ''}`),
	/**  Les contrats parmi lesquels la fiche DÉSIGNE sa référence.
	 *
	 *   `section` vaut `'assurance'` ou `'syndic'` — le serveur la valide contre
	 *   une liste blanche, jamais contre l'énumération brute. */
	contratsCandidats: (section: 'assurance' | 'syndic') =>
		api.get<ContratCandidat[]>(`/copropriete/contrats-candidats/${section}`),
};

export const lots = {
	mesList: () => api.get<any[]>('/lots/mes-lots'),
	get: (id: number) => api.get<any>(`/lots/${id}`),
	mesCommandes: () => api.get<any[]>('/lots/commandes-acces/mes-commandes'),
	creerCommande: (data: unknown) => api.post<any>('/lots/commandes-acces', data),
	// Admin — tous les lots
	tous: () => api.get<any[]>('/lots/admin/tous'),
	// Admin — import staging
	uploadImport: (file: File, remplacer = false) =>
		uploadExcel('/lots/admin/imports/upload', file, remplacer),
	listImports: (statut?: string, tri?: string) =>
		api.get<any[]>(`/lots/admin/imports${buildQuery({ statut, tri })}`),
	statsImports: () => api.get<any>('/lots/admin/imports/stats'),
	autoMatchImports: () => api.post<any>('/lots/admin/imports/auto-match', {}),
	autoResoudreImports: () => api.post<any>('/lots/admin/imports/auto-resoudre', {}),
	patchImport: (
		id: number,
		data: {
			lot_id?: number | null;
			utilisateurs?: { user_id: number; type_lien: string }[];
			notes_admin?: string | null;
		},
	) => api.patch<any>(`/lots/admin/imports/${id}`, data),
	resoudreImport: (id: number) => api.post<any>(`/lots/admin/imports/${id}/resoudre`, {}),
	ignorerimport: (id: number) => api.post<any>(`/lots/admin/imports/${id}/ignorer`, {}),
};

export const bailleur = {
	mesBaux: () => api.get<any[]>('/bailleur/mes-baux'),
	creerBail: (lot_id: number, data: unknown) =>
		api.post<any>(`/bailleur/lots/${lot_id}/bail`, data),
	creerBailMulti: (data: unknown) => api.post<any[]>('/bailleur/baux/creer-multi', data),
	//  🔴 `getBail` A ÉTÉ RETIRÉE (#801) : l'écran `mon-lot` tient déjà ses baux
	//  par `mesBaux()` / `tousBaux()` / `monBail()`, et travaille dessus. Relire
	//  un bail seul depuis le serveur donnerait un second exemplaire du même
	//  objet, libre de diverger de celui de la liste affichée.
	updateBail: (id: number, data: unknown) => api.patch<any>(`/bailleur/baux/${id}`, data),
	terminerBail: (id: number, data: unknown) => api.post<any>(`/bailleur/baux/${id}/terminer`, data),
	//  @sans-appelant On peut RETOURNER et SUPPRIMER un objet remis au locataire,
	//  pas en ajouter ni en corriger un : les objets ne se saisissent qu'à la
	//  création du bail. Un bailleur qui remet une clé en cours de bail n'a aucun
	//  moyen de l'enregistrer. (#806)
	ajouterObjet: (bail_id: number, data: unknown) =>
		api.post<any>(`/bailleur/baux/${bail_id}/objets`, data),
	//  @sans-appelant Corriger un objet est aussi impossible que d'en ajouter un —
	//  et donc corriger une faute de frappe demande de le supprimer, ce qui
	//  supprimerait la ligne au lieu de la corriger. (#806)
	updateObjet: (bail_id: number, obj_id: number, data: unknown) =>
		api.patch<any>(`/bailleur/baux/${bail_id}/objets/${obj_id}`, data),
	retourObjet: (bail_id: number, obj_id: number, data: unknown) =>
		api.post<any>(`/bailleur/baux/${bail_id}/objets/${obj_id}/retour`, data),
	supprimerObjet: (bail_id: number, obj_id: number) =>
		api.delete(`/bailleur/baux/${bail_id}/objets/${obj_id}`),
	supprimerBail: (bail_id: number) => api.delete(`/bailleur/baux/${bail_id}`),
	tousBaux: () => api.get<any[]>('/bailleur/tous-les-baux'),
	// Recherche locataire & gestion accès
	searchLocataire: (q: string) =>
		api.get<any[]>(`/bailleur/search-locataire?q=${encodeURIComponent(q)}`),
	locatairesSuggeres: () => api.get<any[]>('/bailleur/locataires-suggeres'),
	accesBail: (bail_id: number) => api.get<any[]>(`/bailleur/baux/${bail_id}/acces`),
	transfererAcces: (bail_id: number, data: { vigik_ids: number[]; tc_ids: number[] }) =>
		api.post<any[]>(`/bailleur/baux/${bail_id}/transferer-acces`, data),
	recupererAcces: (bail_id: number, data?: { vigik_ids: number[]; tc_ids: number[] }) =>
		api.post<any[]>(`/bailleur/baux/${bail_id}/recuperer-acces`, data ?? {}),
	mesAccesRecus: () => api.get<any[]>('/bailleur/mes-acces-recus'),
	monBail: () => api.get<any>('/bailleur/mon-bail'),
};

/**
 * Périmètres — l'arborescence « où se situe une demande ».
 *
 * Lecture pour tout utilisateur connecté, écriture réservée à l'administration.
 * Le type `Perimetre` vit dans `$lib/perimetres`, qui n'importe rien : c'est ce
 * qui permet à `perimetreLabel()` de rester synchrone dans les gabarits.
 */
export const perimetres = {
	list: () => api.get<PerimetreDTO[]>('/perimetres'),
	create: (data: Partial<PerimetreDTO> & { code: string; libelle: string }) =>
		api.post<PerimetreDTO>('/perimetres', data),
	update: (id: number, data: Partial<PerimetreDTO>) =>
		api.patch<PerimetreDTO>(`/perimetres/${id}`, data),
	remove: (id: number) => api.delete(`/perimetres/${id}`),
};

export const reglesResidence = {
	list: () => api.get<any[]>('/regles-residence'),
	create: (data: { titre: string; contenu?: string }) => api.post<any>('/regles-residence', data),
	update: (id: number, data: { titre?: string; contenu?: string; ordre?: number }) =>
		api.patch<any>(`/regles-residence/${id}`, data),
	remove: (id: number) => api.delete(`/regles-residence/${id}`),
};

export const diagnostics = {
	listTypes: () => api.get<any[]>('/diagnostics/types'),
	uploadRapport: async (
		typeId: number,
		titre: string,
		dateRapport: string | undefined,
		file: File,
	): Promise<any> => {
		return postFormData(`/diagnostics/types/${typeId}/rapports`, {
			titre,
			date_rapport: dateRapport,
			file,
		});
	},
	// `synthese` est bien géré par l'API (`if "synthese" in body.model_fields_set`)
	// et stocké sur le modèle : c'est la signature d'ici qui était en retard.
	updateRapport: (
		id: number,
		data: { titre?: string; date_rapport?: string | null; synthese?: string | null },
	) => api.patch<any>(`/diagnostics/rapports/${id}`, data),
	deleteRapport: (id: number) => api.delete(`/diagnostics/rapports/${id}`),
	downloadUrl: (id: number) => `${BASE}/diagnostics/rapports/${id}/télécharger`,
	toggleNonApplicable: (typeId: number, nonApplicable: boolean) =>
		api.patch<any>(`/diagnostics/types/${typeId}/non-applicable`, {
			non_applicable: nonApplicable,
		}),
};
