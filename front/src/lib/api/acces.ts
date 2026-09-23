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
import { api, BASE } from './client';
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
	porteur_id: number | null;
	lot_libelle: string | null;
	lot_id: number | null;
	/**  🔹 Ce que le badge OUVRE — des CODES, jamais un libellé.
	 *
	 *   ⚠️ L'écran les met en forme (`BadgePerimetre`), comme partout ailleurs :
	 *   un libellé venu du serveur obligerait celui-ci à décider d'un rendu, et
	 *   c'est le défaut que le fil d'activité portait jusqu'au 14/09/2026. */
	perimetre_cible: string[];
	cree_le: string;
}

/**  Ce qu'un type d'accès a le droit d'ouvrir, et comment son défaut se décide.
 *
 *   ⚠️ `suitLeLot` n'est pas cosmétique : sans lui, l'écran devrait écrire
 *   `type === 'vigik'` pour choisir son libellé d'aide — reconnaître un type par
 *   son nom, exactement ce que le descripteur `TypeAcces` a supprimé côté
 *   serveur. Un objet dit ce qu'il est ; on ne le devine pas à sa clé. */
export interface ChoixAcces {
	codes: string[];
	suit_le_lot: boolean;
}

export const acces = {
	mesVigiks: () => api.get<any[]>('/acces/mes-vigiks'),
	mesTelecommandes: () => api.get<any[]>('/acces/mes-telecommandes'),
	creerCommande: (data: unknown) => api.post<any>('/acces/commandes', data),
	signalerVigiKPerdu: (id: number) => api.patch(`/acces/vigiks/${id}/perdu`, {}),
	signalerTcPerdu: (id: number) => api.patch(`/acces/telecommandes/${id}/perdu`, {}),
	//  🔴 `supprimerVigik` et `supprimerTc` sont partis le 15/09/2026, avec
	//  leurs routes : un résident ne supprime pas un accès, il signale une perte.
	//  La suppression définitive reste à l'administrateur (`supprimerAcces`).
	declarerBadge: (data: { type: string; code: string }) =>
		api.post<any>('/acces/declarer-badge', data),
	//  ── CS/Admin — LE PARC : qui a quoi, et que peut-on en faire ──────────────
	//
	//  🔴 Cet écran a été **en lecture seule du 06/09 au 14/09/2026**, et ce
	//  n'était pas un oubli : trois routes d'écriture avaient été supprimées ce
	//  jour-là (#805) au motif qu'enregistrer un badge était déjà couvert deux
	//  fois — l'import Excel en masse, et `declarerBadge` par le résident.
	//
	//  Le choix est **renversé sur demande explicite** (#953) : le conseil
	//  syndical remet des badges en main propre, et rien ne le lui permettait.
	//
	//  ⚠️ Ce qui aurait été fautif n'était pas d'ouvrir l'écriture, c'était de la
	//  RECOPIER. Côté serveur, les gestes passent par le descripteur
	//  `utils/types_acces` — celui dont l'absence avait laissé diverger le report
	//  du `lot_id` entre vigik et télécommande (corrigé en v1.36.8).
	//
	//  ⚠️ La réponse rendait l'objet BRUT avant #805, donc `user_id` : un écran
	//  bâti dessus aurait affiché « badge 4521 → utilisateur 37 ». Une route sans
	//  appelant n'est jamais mise à l'épreuve de la question à laquelle elle est
	//  censée répondre.
	//  🔹 Ce que chaque type d'accès a le DROIT d'ouvrir, par clé de type.
	//
	//  ⚠️ L'écran s'en sert pour PROPOSER ; ce qui contraint est la validation
	//  côté serveur, sur les deux gestes d'écriture. Une restriction qui ne
	//  vivrait que dans le formulaire n'en serait pas une — la route accepterait
	//  toujours n'importe quel code.
	//
	//  ⚠️ Des codes, pas des libellés : l'écran les met en forme depuis l'arbre
	//  qu'il a déjà chargé, comme `BadgePerimetre` et `PerimetrePicker` partout
	//  ailleurs. Deux mises en forme du même objet, c'est la divergence de demain.
	choixAcces: () => api.get<Record<string, ChoixAcces>>('/acces/admin/choix-acces'),
	listVigiks: () => api.get<AccesAdmin[]>('/acces/admin/vigiks'),
	listTelecommandes: () => api.get<AccesAdmin[]>('/acces/admin/telecommandes'),
	//  Le TYPE est un paramètre de chemin, pas deux méthodes : `vigik` et
	//  `telecommande` répondent à la même question, et deux méthodes jumelles
	//  auraient divergé au premier champ ajouté — c'est ce qui est arrivé à
	//  `declarerBadge`.
	creerAcces: (type: string, data: unknown) => api.post<AccesAdmin>(`/acces/admin/${type}`, data),
	modifierAcces: (type: string, id: number, data: unknown) =>
		api.patch<AccesAdmin>(`/acces/admin/${type}/${id}`, data),
	//  🔒 Réservé à l'ADMIN côté serveur : le conseil syndical passe un badge en
	//  « perdu » par `modifierAcces`. Un badge perdu a existé, et le parc doit
	//  pouvoir le dire (`ux-patterns` §8).
	supprimerAcces: (type: string, id: number) => api.delete(`/acces/admin/${type}/${id}`),
	//: L'adresse de l'export d'UN type — le navigateur la suit, on ne la lit pas ici.
	//
	//  ⚠️ Pas de `api.get` : la réponse est un FICHIER, et la passer par le client
	//  obligerait à fabriquer un `blob:` puis un lien de téléchargement. Le
	//  navigateur sait le faire ; les cookies de session partent avec.
	//
	//  🔴 **Un export PAR TYPE depuis le 15/09/2026.** Le fichier unique de la
	//  veille obligeait à filtrer sur une colonne « Type » avant tout usage : un
	//  vigik et une télécommande n'ont ni les mêmes accès possibles, ni le même
	//  rapport au lot. La fonction reste **une seule**, paramétrée — deux
	//  fonctions jumelles auraient divergé au premier ajustement d'URL.
	urlExportParc: (type: string) => `${BASE}/acces/admin/${type}/export.csv`,
	// CS/Admin — import vigik
	uploadImportVigik: (file: File, remplacer = false) =>
		uploadExcel('/acces/admin/imports-vigik/upload', file, remplacer),
	listImportsVigik: (statut?: string) =>
		api.get<any[]>(`/acces/admin/imports-vigik${statut ? `?statut=${statut}` : ''}`),
	statsImportsVigik: () => api.get<any>('/acces/admin/imports-vigik/stats'),
	autoMatchImportsVigik: () => api.post<any>('/acces/admin/imports-vigik/auto-match', {}),
	rattacherImportsVigik: () => api.post<any>('/acces/admin/imports-vigik/rattacher', {}),
	/** Les lots, avec le copropriétaire que le FICHIER leur donne — pour les deux imports. */
	lotsImports: () => api.get<any[]>('/acces/admin/imports-lots'),
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
	rattacherImportsTC: () => api.post<any>('/acces/admin/imports/rattacher', {}),
	patchImportTC: (id: number, data: unknown) => api.patch<any>(`/acces/admin/imports/${id}`, data),
	resoudreImportTC: (id: number) => api.post<any>(`/acces/admin/imports/${id}/resoudre`, {}),
	ignorerImportTC: (id: number) => api.post<any>(`/acces/admin/imports/${id}/ignorer`, {}),
	remettreEnAttenteImportTC: (id: number) =>
		api.post<any>(`/acces/admin/imports/${id}/remettre-en-attente`, {}),
};
