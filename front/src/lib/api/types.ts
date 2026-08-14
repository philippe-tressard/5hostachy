//  Formes de données échangées avec l'API. Rassemblées ici depuis trois
//  endroits différents de l'ancien `api.ts`, où elles étaient intercalées
//  entre les clients — donc introuvables autrement qu'au grep.
export interface User {
	id: number;
	nom: string;
	prenom: string;
	email: string;
	telephone?: string | null;
	societe?: string | null;	fonction?: string | null;	statut: string;
	role: string;
	roles: string[];  // multi-rôles cumulables
	actif: boolean;
	opt_out_telemetrie?: boolean;
	// Modération de la Communauté. Ces champs étaient absents de l'interface
	// alors que `UserRead` les renvoie et que la page Sondages s'en sert pour
	// bloquer un membre suspendu : le contrôle fonctionnait, mais TypeScript ne
	// pouvait pas le vérifier — une faute de frappe sur le nom du champ serait
	// passée inaperçue et aurait rouvert l'accès à un membre banni.
	communaute_interdit?: boolean;
	communaute_ban_count?: number;
	communaute_ban_jusqu_au?: string | null;
	onboarding_complete: boolean;
	onboarding_etape: number;
	photo_url?: string;
	preferences_notifications: string;
	/** Préférence d'AFFICHAGE, jamais un droit : n'afficher que ses bâtiments (#339). */
	restreindre_a_mes_batiments?: boolean;
	demarche_arrivant?: string | null;
	batiment_id?: number | null;
	batiment_nom?: string | null;  // "Bât. A"
	last_seen_actualites?: string | null;
	delegations_aidant?: { delegation_id: number; mandant_id: number; mandant_nom: string }[];
	cree_le: string;
	derniere_connexion?: string | null;
}

export interface Ticket {
	id: number;
	numero: string;
	titre: string;
	description: string;
	categorie: string;
	statut: string;
	priorite: string;
	auteur_id: number;
	auteur_nom?: string | null;
	auteur_batiment_nom?: string | null;
	lot_id?: number;
	batiment_id?: number;
	perimetre_cible?: string[];
	photos_urls?: string[];
	/** Documents joints (PDF, bureautique) — les images restent dans photos_urls. */
	fichiers_urls?: string[];
	destinataire_syndic?: boolean;
	destinataire_cs?: boolean;
	non_relancable?: boolean;
	non_relancable_motif?: string | null;
	relance_count?: number;
	cree_le: string;
	mis_a_jour_le: string;
}

export interface RelanceSyndicResponse {
	delai_jours: number;
	tickets: Ticket[];
}

/** Message d'un fil de ticket. Vit ici, pas dans la page : le client TypeScript
 *  est la source unique des types d'API (cf. CLAUDE.md, checklist backend). */
export interface TicketMessage {
	id: number;
	contenu: string;
	interne: boolean;
	auteur: { id: number; prenom: string; nom: string; role: string };
	cree_le: string;
	fichiers_urls?: string[];
}

export interface TicketEvolution {
	id: number;
	ticket_id: number;
	type: 'commentaire' | 'etat' | 'reponse';
	contenu?: string;
	ancien_statut?: string;
	nouveau_statut?: string;
	auteur_id: number;
	auteur_nom?: string;
	cree_le: string;
	fichiers_urls?: string[];
}

export interface PublicationEvolution {
	id: number;
	publication_id: number;
	type: 'commentaire' | 'etat' | 'correction';
	contenu?: string;
	ancien_statut?: string;
	nouveau_statut?: string;
	auteur_id: number;
	auteur_nom?: string;
	cree_le: string;
	fichiers_urls?: string[];
}

export interface Publication {
	id: number;
	titre: string;
	contenu: string;
	perimetre: string;
	batiment_id?: number;
	epingle: boolean;
	urgente: boolean;
	auteur_id: number;
	auteur_nom?: string;
	photos_urls?: string[];
	cree_le: string;
	mis_a_jour_le?: string;
	perimetre_cible: string[];
	public_cible: string[];
	statut?: 'publie' | 'en_cours' | 'resolu' | 'annule' | null;
	statut_change_le?: string | null;
	brouillon: boolean;
	partager_whatsapp?: boolean;
	envoyer_syndic?: boolean;
	envoyer_cs?: boolean;
	annonce_hall?: boolean;
	evolutions: PublicationEvolution[];
}

export interface Document {
	id: number;
	titre: string;
	fichier_nom: string;
	taille_octets?: number;
	mime_type: string;
	categorie_id: number;
	perimetre: string;
	publie_le: string;
}

export interface Notification {
	id: number;
	type: string;
	titre: string;
	corps: string;
	lien?: string;
	lue: boolean;
	urgente: boolean;
	cree_le: string;
}


export interface FluxItem {
	id: string;
	type: string;
	date: string;
	cree_le?: string;
	titre: string;
	detail?: string;
	badges: string[];
	icon: string;
	lien?: string;
	meta: Record<string, unknown>;
}
export interface FluxProchain {
	id: string;
	date: string;
	titre: string;
	type: string;
	icon: string;
	ev_type?: string;
	description?: string;
	lieu?: string;
	perimetre?: string;
	prestataire?: string;
	fin?: string;
	statut_kanban?: string;
}
export interface FluxSante {
	tickets_ouverts: number;
	tickets_urgents: number;
	resolution_moyenne_heures: number | null;
	sondages_actifs: number;
	validations_cs: number;
	tickets_relance_syndic: number;
	prochains: FluxProchain[];
}
export interface FluxResponse {
	items: FluxItem[];
	sante: FluxSante;
}
export interface EpinglesCompte {
	total: number;
	publications: number;
	evenements: number;
}

export interface AnnonceHall {
	id: number;
	titre: string;
	message: string;
	apercu: string;
	perimetre_cible: string[];
	perimetre_label: string;
	format_demande: string;
	format_effectif: string;
	format_label: string;
	images: string[];
	pdf_nom: string;
	taille_octets: number | null;
	destinataires: string[];
	envoye_le: string | null;
	archivee: boolean;
	publication_id: number | null;
	cree_le: string;
	auteur_nom: string;
}

export interface AnnonceHallInput {
	titre: string;
	message: string;
	perimetre_cible: string[];
	format_demande: string;
	images?: string[];
}

/** Champs d'une actualité, prêts à alimenter le formulaire d'annonce de hall. */
export interface AnnonceHallPrefill {
	titre: string;
	message: string;
	perimetre_cible: string[];
	images: string[];
}
