import { api, BASE } from './client';
import type {
	AnnonceHall,
	AnnonceHallInput,
	ActualitePrefill,
	AffaireLiee,
	AnnonceHallPrefill,
	ApercuDiffusion,
	EpinglesCompte,
	FluxResponse,
	Notification,
	RelanceSyndicResponse,
	ReponseRelance,
	SourceAffiche,
	Ticket,
	TicketEvolution,
	TicketMessage,
	User,
} from './types';
//  Le type des périmètres vit dans `$lib/perimetres` et non dans `./types` : ce
//  module-là ne doit dépendre de rien pour rester importable depuis `lib/utils.ts`
//  sans créer de cycle. Il est réexporté ici pour que `from '$lib/api'` suffise.

export type { Perimetre } from '$lib/perimetres';

//  Le paquet expose exactement ce que `api.ts` exposait : les 41 imports
//  `from '$lib/api'` du front n'ont pas à changer, et ne changent pas.
export * from './client';
export * from './types';
export * from './documents';
export * from './communaute';
export * from './patrimoine';
export * from './acces';
export * from './prestataires';
export * from './administration';
export * from './assistant';

export const auth = {
	me: () => api.get<User>('/auth/me'),
	login: (email: string, password: string) => api.post<User>('/auth/login', { email, password }),
	register: (data: unknown) => api.post<User>('/auth/register', data),
	logout: () => api.post('/auth/logout'),
	//  @sans-appelant-direct Le renouvellement de session est fait par
	//  `tryRefresh()` dans `client.ts`, en `fetch` DIRECT — et c'est nécessaire :
	//  le client ne peut pas s'appeler lui-même pour renouveler la session sans
	//  récursion sur le 401 qu'il vient d'intercepter. Cette méthode reste la
	//  déclaration lisible de la route ; l'appel réel est ailleurs, par
	//  construction.
	refresh: () => api.post('/auth/refresh'),
	updateMe: (data: unknown) => api.patch<User>('/auth/me', data),
	changePassword: (data: unknown) => api.post('/auth/change-password', data),
	requestPasswordReset: (data: unknown) => api.post('/auth/mot-de-passe-oublie', data),
	resetPassword: (data: { token: string; nouveau_mot_de_passe: string }) =>
		api.post('/auth/reinitialiser-mot-de-passe', data),
	verifierEmail: (token: string) =>
		api.get<{ message: string }>(`/auth/verifier-email?token=${encodeURIComponent(token)}`),
	renvoyerVerification: (email: string) => api.post('/auth/renvoyer-verification', { email }),
	batiments: () => api.get<{ id: number; numero: string }[]>('/auth/batiments'),
	mesDemandes: () => api.get<any[]>('/auth/me/demandes-modification'),
	demanderModification: (data: unknown) => api.post<any>('/auth/me/demande-modification', data),
	declarerNouvelArrivant: (data: {
		batiment?: string | null;
		ancien_resident?: string | null;
		ancien_resident_inconnu?: boolean;
	}) => api.post<any>('/admin/me/accueil-arrivant', data),
	exportTelemetrie: () => api.get<any[]>('/auth/me/telemetrie'),
	effacerTelemetrie: () => api.delete('/auth/me/telemetrie'),
	toggleOptOutTelemetrie: (data: { opt_out_telemetrie: boolean }) =>
		api.patch('/auth/me/opt-out-telemetrie', data),
};

export const tickets = {
	list: () => api.get<Ticket[]>('/tickets'),
	get: (id: number) => api.get<Ticket>(`/tickets/${id}`),
	/** Les affaires que je peux lier : numéro, titre, statut (#1342). */
	choix: () => api.get<AffaireLiee[]>('/tickets/choix'),
	//  Le miroir du pré-remplissage des affiches (#832) : le CS compose souvent
	//  l'affiche du hall d'abord, puis veut la même information en ligne. Une
	//  actualité étant une affaire (#1091), la route vit chez les affaires.
	depuisAnnonceHall: (annonceId: number) =>
		api.get<ActualitePrefill>(`/tickets/depuis-annonce-hall/${annonceId}`),
	create: (data: unknown) => api.post<Ticket>('/tickets', data),
	/** « Init. prestataires » : les visites de l'exercice, toutes ou aucune (#1193). */
	creerLot: (affaires: unknown[]) => api.post<{ crees: number }>('/tickets/lot', { affaires }),
	update: (id: number, data: unknown) => api.patch<Ticket>(`/tickets/${id}`, data),
	delete: (id: number) => api.delete(`/tickets/${id}`),
	messages: (id: number) => api.get<TicketMessage[]>(`/tickets/${id}/messages`),
	addMessage: (
		id: number,
		data: {
			contenu: string;
			interne?: boolean;
			fichiers_urls?: string[];
			email_externe?: string;
			assiste_ia?: boolean;
		},
	) => api.post<TicketMessage>(`/tickets/${id}/messages`, data),
	evolutions: (id: number) => api.get<TicketEvolution[]>(`/tickets/${id}/evolutions`),
	//  L'aperçu de ce qui partira, avant de confirmer la diffusion (#498). Il ne
	//  crée rien : le brouillon est composé par les MÊMES fonctions que l'envoi.
	apercuDiffusion: (brouillon: {
		/** Renseigné pour un COMMENTAIRE sur un ticket existant (#498). */
		ticket_id?: number;
		commentaire?: string;
		titre?: string;
		description?: string;
		categorie?: string;
		perimetre_cible?: string[];
		photos_urls?: string[];
		fichiers_urls?: string[];
		destinataire_syndic?: boolean;
		destinataire_cs?: boolean;
		partager_whatsapp?: boolean;
		/** « M'envoyer une copie » — la 4e case de la Diffusion (31/08/2026). */
		envoyer_auteur?: boolean;
		/** Ce qu'une actualité ajoute : l'urgence, et à qui l'on parle (#1091). */
		urgente?: boolean;
		public_cible?: string[];
	}) => api.post<ApercuDiffusion>('/tickets/apercu-diffusion', brouillon),
	//  `perimetre_cible` : le périmètre que l'entrée PRÉCISE, absent quand elle
	//  n'en parle pas — le serveur ne touche alors pas à celui du ticket (#497).
	addEvolution: (
		id: number,
		data: {
			type: string;
			contenu?: string;
			nouveau_statut?: string;
			fichiers_urls?: string[];
			email_externe?: string;
			partager_whatsapp?: boolean;
			/** « M'envoyer une copie » — la 4e case de la Diffusion (31/08/2026). */
			envoyer_auteur?: boolean;
			envoyer_syndic?: boolean;
			envoyer_cs?: boolean;
			/** Faux : n'avertir personne — le glissement au kanban (#1092). */
			notifier?: boolean;
			perimetre_cible?: string[];
			/**  🔴 LES OPTIONS DE PUBLICATION, corrigées depuis un commentaire
			 *   (05/09/2026) — comme sur une actualité : le formulaire montre le
			 *   dernier état, ce qu'on enregistre devient l'état.
			 *
			 *   `undefined` veut dire « cette entrée ne dit rien de cette option » :
			 *   le ticket garde la sienne, même convention que `perimetre_cible`.
			 *
			 *   ⚠️ `urgente` n'est pas une colonne du ticket : elle pilote sa
			 *   `priorite`, ce que fait déjà la catégorie « Urgence ». Le pont vit
			 *   dans `$lib/tickets` (`optionsVersTicket`). */
			epingle?: boolean;
			urgente?: boolean;
			confidentiel?: boolean;
			/** Une actualité (#1091) : à qui l'on parle et l'Accès — conseil seul. */
			public_cible?: string[];
			reserve_perimetre?: boolean;
			/** « Rédigé avec l'assistant IA » (#985) — seulement quand c'est vrai. */
			assiste_ia?: boolean;
		},
	) => api.post<TicketEvolution>(`/tickets/${id}/evolutions`, data),
	updateEvolution: (
		id: number,
		evolId: number,
		//  `perimetre_cible` : la CORRECTION d'une erreur d'affectation
		//  (01/09/2026). Le serveur ne la propage au ticket que si cette entrée
		//  est la dernière à avoir précisé — `app/utils/perimetre_fil.py`.
		data: {
			contenu?: string;
			fichiers_urls?: string[];
			perimetre_cible?: string[];
			assiste_ia?: boolean;
		},
	) => api.patch<TicketEvolution>(`/tickets/${id}/evolutions/${evolId}`, data),
	//  Réservé à l'ADMIN côté serveur (`require_admin`) : effacer une trace que
	//  d'autres ont pu lire n'est pas corriger son propre texte.
	deleteEvolution: (id: number, evolId: number) =>
		api.delete<void>(`/tickets/${id}/evolutions/${evolId}`),
	relanceSyndicList: () => api.get<RelanceSyndicResponse>('/tickets/relance-syndic'),
	//  Les réponses du syndic aux relances groupées : conservées et relues ici,
	//  parce qu'une notification se lit une fois puis descend dans la pile.
	relanceReponses: () =>
		api.get<{ reponses: ReponseRelance[] }>('/tickets/relance-syndic/reponses'),
	envoiRelance: (ticket_ids: number[]) =>
		api.post<{ sent: number; relance_to: string }>('/tickets/relance-syndic', { ticket_ids }),
	// Pas de `uploadPhoto` : photos et documents passent par `fichiersApi.upload`
	// AVANT la création, et voyagent dans `photos_urls` / `fichiers_urls`.
};

export const publications = {
	/**
	 * **Où une ancienne actualité est allée** — et rien d'autre (#1091, lot 4).
	 *
	 * Une actualité est une affaire depuis le 23/09/2026. Les adresses
	 * `/actualites#pub-N` envoyées par courriel et sur WhatsApp restent en
	 * circulation : le serveur rend 410 avec `promu_en_affaire`, et 404 pour un
	 * numéro jamais attribué. Tout le reste de ce client est parti avec l'entité.
	 */
	get: (id: number) => api.get<void>(`/publications/${id}`),
};

export const notifications = {
	list: () => api.get<Notification[]>('/notifications'),
	markRead: (id: number) => api.patch<Notification>(`/notifications/${id}/lue`),
	markAllRead: () => api.post('/notifications/tout-marquer-lu'),
	delete: (id: number) => api.delete(`/notifications/${id}`),
};

//  Le calendrier n'est plus qu'une ADRESSE (#1092, lot 5) : ses événements sont
//  des affaires. Reste la question des anciens liens `#ev-N` — le serveur répond
//  410 avec l'affaire née de l'événement (`routers/calendrier.py`).
export const calendrier = {
	get: (id: number) => api.get<void>(`/calendrier/${id}`),
};

export const flux = {
	get: () => api.get<FluxResponse>('/flux'),
	/** Compte des éléments épinglés, toutes rubriques confondues (CS/admin) —
	 *  alimente l'avertissement de plafond souple des formulaires. */
	epingles: () => api.get<EpinglesCompte>('/flux/epingles'),
	//  Retirer une carte du FIL — admin uniquement (31/08/2026).
	//
	//  ⚠️ Le nom du verbe est trompeur et c'est celui du protocole : `DELETE` ne
	//  supprime ici qu'une LIGNE D'AFFICHAGE. Le fil est une vue calculée ;
	//  l'actualité, le membre du conseil ou le ticket restent consultables depuis
	//  leur écran. C'est ce que la demande dit : « celle-ci reste tracée à
	//  l'origine : actualité, annuaire, ticket, … ».
	masquer: (itemId: string) => api.delete<void>(`/flux/${encodeURIComponent(itemId)}`),
};

// ── Upload fichiers ─────────────────────────────────────────────────────────

export const faq = {
	list: () => api.get<any[]>('/faq'),
	listAll: () => api.get<any[]>('/faq/all'),
	categories: () => api.get<string[]>('/faq/categories'),
	create: (data: unknown) => api.post<any>('/faq', data),
	update: (id: number, data: unknown) => api.patch<any>(`/faq/${id}`, data),
	reorder: (data: { id: number; ordre: number }[]) => api.patch<void>('/faq/reorder', data),
	renameCategory: (old_name: string, new_name: string) =>
		api.patch<any>('/faq/categories/rename', { old_name, new_name }),
	delete: (id: number) => api.delete(`/faq/${id}`),
};

export const annuaire = {
	get: () =>
		api.get<{
			cs: { ag_annee: number | null; ag_date: string | null; membres: any[] };
			syndic: {
				nom_syndic: string;
				nom_syndic_source?: 'contrat' | 'saisie' | 'aucune';
				adresse: string;
				membres: any[];
			};
		}>('/admin/annuaire'),
};

export const annoncesHall = {
	//  L'aperçu de ce qui partira, avant de confirmer la diffusion (#498/#480).
	//
	//  🔴 Dernier des points de diffusion à le recevoir, et le seul qui en était
	//  privé DÉLIBÉRÉMENT : tant que le serveur ne consommait qu'un canal sur
	//  trois, un aperçu y aurait montré un envoi qui n'a pas lieu. Comme les
	//  trois autres, il ne crée RIEN et ne recompose rien — l'e-mail et le
	//  message sont composés par les MÊMES fonctions que l'envoi.
	apercuDiffusion: (brouillon: {
		/** Renseigné quand l'affiche est pré-remplie depuis une actualité — une
		 *  affaire (#1091) : c'est ce qui donne son lien au message WhatsApp. */
		ticket_id?: number;
		titre?: string;
		message?: string;
		perimetre_cible?: string[];
		format_demande?: string;
		images?: string[];
		envoyer_cs?: boolean;
		envoyer_syndic?: boolean;
		partager_whatsapp?: boolean;
		/** « M'envoyer une copie » — la 4e case de la Diffusion. */
		envoyer_auteur?: boolean;
	}) => api.post<ApercuDiffusion>('/annonces-hall/apercu-diffusion', brouillon),
	list: (archivees = false) => api.get<AnnonceHall[]>(`/annonces-hall?archivees=${archivees}`),
	create: (data: AnnonceHallInput) => api.post<AnnonceHall>('/annonces-hall', data),
	/**  Ce que le fil propose de reprendre au hall — actualités, tickets ET
	 *   événements (10/09/2026). Le sélecteur ne montrait que des actualités. */
	sources: () => api.get<SourceAffiche[]>('/annonces-hall/sources'),
	/**  Pré-remplissage depuis n'importe laquelle des trois familles. Un élément
	 *   confidentiel, archivé ou brouillon rend 404 — la règle est au serveur. */
	depuisElement: (type: string, id: number) =>
		api.get<AnnonceHallPrefill>(`/annonces-hall/depuis/${type}/${id}`),
	previsualiser: (data: AnnonceHallInput) =>
		api.post<{
			format_effectif: string;
			format_label: string;
			perimetre_label: string;
			html: string;
		}>('/annonces-hall/previsualiser', data),
	archiver: (id: number, archivee: boolean) =>
		api.patch<AnnonceHall>(`/annonces-hall/${id}`, { archivee }),
	renvoyerEmail: (id: number) => api.post(`/annonces-hall/${id}/renvoyer-email`, {}),
	delete: (id: number) => api.delete(`/annonces-hall/${id}`),
	pdfUrl: (id: number) => `${BASE}/annonces-hall/${id}/pdf`,
};
