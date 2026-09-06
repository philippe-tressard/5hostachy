import { api, BASE } from './client';
import type {
	AnnonceHall,
	AnnonceHallInput,
	AnnonceHallPrefill,
	ApercuDiffusion,
	EpinglesCompte,
	FluxResponse,
	Notification,
	Publication,
	PublicationEvolution,
	RelanceSyndicResponse,
	ReponseRelance,
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
	create: (data: unknown) => api.post<Ticket>('/tickets', data),
	update: (id: number, data: unknown) => api.patch<Ticket>(`/tickets/${id}`, data),
	delete: (id: number) => api.delete(`/tickets/${id}`),
	messages: (id: number) => api.get<TicketMessage[]>(`/tickets/${id}/messages`),
	addMessage: (
		id: number,
		data: { contenu: string; interne?: boolean; fichiers_urls?: string[]; email_externe?: string },
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
		},
	) => api.post<TicketEvolution>(`/tickets/${id}/evolutions`, data),
	updateEvolution: (
		id: number,
		evolId: number,
		//  `perimetre_cible` : la CORRECTION d'une erreur d'affectation
		//  (01/09/2026). Le serveur ne la propage au ticket que si cette entrée
		//  est la dernière à avoir précisé — `app/utils/perimetre_fil.py`.
		data: { contenu?: string; fichiers_urls?: string[]; perimetre_cible?: string[] },
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
	//  L'aperçu de ce qui partira, avant de confirmer la diffusion (#498).
	//
	//  🔴 Il n'existait que pour les tickets. Le 31/08/2026, une actualité est
	//  partie au conseil syndical sans que son auteur ait rien pu voir ni annuler.
	//  Comme celui des tickets, il ne crée RIEN et ne recompose rien : le message
	//  est composé par les MÊMES fonctions que l'envoi.
	apercuDiffusion: (brouillon: {
		/** Renseigné pour un COMMENTAIRE sur une publication existante. */
		publication_id?: number;
		commentaire?: string;
		titre?: string;
		contenu?: string;
		urgente?: boolean;
		perimetre_cible?: string[];
		photos_urls?: string[];
		fichiers_urls?: string[];
		envoyer_syndic?: boolean;
		envoyer_cs?: boolean;
		partager_whatsapp?: boolean;
		/** « M'envoyer une copie » — la 4e case de la Diffusion (31/08/2026). */
		envoyer_auteur?: boolean;
	}) => api.post<ApercuDiffusion>('/publications/apercu-diffusion', brouillon),
	list: (archived = false) =>
		api.get<Publication[]>(`/publications${archived ? '?archived=true' : ''}`),
	create: (data: unknown) => api.post<Publication>('/publications', data),
	update: (id: number, data: unknown) => api.patch<Publication>(`/publications/${id}`, data),
	archive: (id: number) => api.patch<Publication>(`/publications/${id}`, { archivee: true }),
	delete: (id: number) => api.delete(`/publications/${id}`),
	renvoyerEmail: (id: number) => api.post(`/publications/${id}/renvoyer-email`, {}),
	//  @sans-appelant-declare Le bouton de renvoi a été RETIRÉ des actualités le
	//  18/08/2026, sur arbitrage, avec sa conséquence écrite sur place : « un
	//  envoi qui a échoué sans qu'on s'en rende compte n'a plus de chemin de
	//  rattrapage depuis l'interface […] à rouvrir ailleurs si le besoin se
	//  représente ». Le chemin est donc gardé exprès, pas oublié.
	renvoyerWhatsapp: (id: number) => api.post(`/publications/${id}/renvoyer-whatsapp`, {}),
	addEvolution: (
		pubId: number,
		data: {
			type: string;
			contenu?: string;
			nouveau_statut?: string;
			partager_whatsapp?: boolean;
			/** « M'envoyer une copie » — la 4e case de la Diffusion (31/08/2026). */
			envoyer_auteur?: boolean;
			envoyer_syndic?: boolean;
			envoyer_cs?: boolean;
			fichiers_urls?: string[];
			email_externe?: string;
		},
	) => api.post<PublicationEvolution>(`/publications/${pubId}/evolutions`, data),
	updateEvolution: (
		pubId: number,
		evolId: number,
		data: { contenu?: string; fichiers_urls?: string[] },
	) => api.patch<PublicationEvolution>(`/publications/${pubId}/evolutions/${evolId}`, data),
	//  Même contrat que celui des tickets — même code côté serveur (#512).
	deleteEvolution: (pubId: number, evolId: number) =>
		api.delete<void>(`/publications/${pubId}/evolutions/${evolId}`),
};

export const notifications = {
	list: () => api.get<Notification[]>('/notifications'),
	markRead: (id: number) => api.patch<Notification>(`/notifications/${id}/lue`),
	markAllRead: () => api.post('/notifications/tout-marquer-lu'),
	delete: (id: number) => api.delete(`/notifications/${id}`),
};

export const calendrier = {
	//  L'aperçu de ce qui partira, avant de confirmer la diffusion (#498).
	//
	//  🔴 Cet écran n'en avait pas : seuls les tickets en avaient un. Comme eux,
	//  il ne crée RIEN et ne recompose rien — le message est composé par les
	//  MÊMES fonctions que l'envoi (`contexte_evenement_canaux`).
	apercuDiffusion: (brouillon: {
		/** Renseigné pour une entrée d'Historique sur un événement existant. */
		evenement_id?: number;
		/** L'entrée en cours : sa présence bascule le gabarit ET le message. */
		suivi?: { etat?: string; commentaire?: string };
		fichiers_suivi?: string[];
		titre?: string;
		description?: string;
		type?: string;
		debut?: string;
		perimetre?: string;
		photos_urls?: string[];
		fichiers_urls?: string[];
		envoyer_syndic?: boolean;
		envoyer_cs?: boolean;
		partager_whatsapp?: boolean;
		/** « M'envoyer une copie » — la 4e case de la Diffusion (31/08/2026). */
		envoyer_auteur?: boolean;
	}) => api.post<ApercuDiffusion>('/calendrier/apercu-diffusion', brouillon),
	list: () => api.get<any[]>('/calendrier'),
	get: (id: number) => api.get<any>(`/calendrier/${id}`),
	create: (data: unknown) => api.post<any>('/calendrier', data),
	//  🔴 UNE requête, UNE transaction (#605, point 3). Le pré-remplissage du
	//  kanban écrivait en boucle : `for (const ev of aCreer) await create(ev)`.
	//  Un échec au 7e sur 20 laissait SIX événements créés et l'écran disait
	//  « Erreur lors de l'initialisation » sans dire lesquels.
	//
	//  ⚠️ Ce point d'entrée ne DIFFUSE jamais et refuse les types qui notifient
	//  (coupure, travaux) : un lot est un pré-remplissage silencieux, en faire un
	//  canal offrirait cent envois en une requête. Le serveur les rejette en 422
	//  plutôt que de les ignorer — sinon l'appelant croirait avoir diffusé.
	createLot: (evenements: unknown[]) => api.post<any[]>('/calendrier/lot', { evenements }),
	update: (id: number, data: unknown) => api.patch<any>(`/calendrier/${id}`, data),
	archive: (id: number) => api.patch<any>(`/calendrier/${id}`, { archivee: true }),
	delete: (id: number) => api.delete(`/calendrier/${id}`),
	// Pas de `uploadPhoto` : comme pour les tickets, les pièces jointes sont
	// téléversées par `fichiersApi.upload` avant la création et passent dans le
	// payload ; le retrait passe par `update`, qui n'accepte que nos URLs.

	//  L'HISTORIQUE d'un événement (18/08/2026). Le Kanban ÉTANT son workflow,
	//  une entrée de type `etat` déplace aussi l'événement : le fil ne raconte
	//  jamais un mouvement qui n'a pas eu lieu.
	addEvolution: (id: number, data: unknown) => api.post<any>(`/calendrier/${id}/evolutions`, data),
	updateEvolution: (id: number, evolId: number, data: unknown) =>
		api.patch<any>(`/calendrier/${id}/evolutions/${evolId}`, data),
	//  Même contrat que celui des tickets — même code côté serveur (#512).
	deleteEvolution: (id: number, evolId: number) =>
		api.delete<void>(`/calendrier/${id}/evolutions/${evolId}`),
};

// ── Flux temps réel (dashboard pouls) ───────────────────────────────────────

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
		/** Renseigné quand l'affiche est pré-remplie depuis une actualité : c'est
		 *  ce qui donne son lien au message WhatsApp, et lui seul. */
		publication_id?: number;
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
	depuisPublication: (pubId: number) =>
		api.get<AnnonceHallPrefill>(`/annonces-hall/depuis-publication/${pubId}`),
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
