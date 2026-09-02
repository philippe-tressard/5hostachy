//  Formes de données échangées avec l'API. Rassemblées ici depuis trois
//  endroits différents de l'ancien `api.ts`, où elles étaient intercalées
//  entre les clients — donc introuvables autrement qu'au grep.
export interface User {
	id: number;
	nom: string;
	prenom: string;
	email: string;
	telephone?: string | null;
	societe?: string | null;
	fonction?: string | null;
	statut: string;
	role: string;
	roles: string[]; // multi-rôles cumulables
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
	/**
	 * Le MOTIF du refus d'accès à la Communauté, ou `null` si l'accès est ouvert.
	 *
	 * Calculé par l'API (`app/utils/communaute.py`), qui est la seule à porter la
	 * règle. Le front l'AFFICHE, il ne le recalcule pas : il en portait sa propre
	 * copie dans `sondages/+page.svelte`, avec un libellé encore différent de
	 * celui de l'API et de celui de l'administration (29/08/2026).
	 */
	communaute_motif_refus?: string | null;
	onboarding_complete: boolean;
	onboarding_etape: number;
	photo_url?: string;
	preferences_notifications: string;
	/** Préférence d'AFFICHAGE, jamais un droit : n'afficher que ses bâtiments (#339). */
	restreindre_a_mes_batiments?: boolean;
	demarche_arrivant?: string | null;
	batiment_id?: number | null;
	batiment_nom?: string | null; // "Bât. A"
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
	/** « Saisi pour » — le CS peut ouvrir un ticket au nom d'un tiers (section 2). */
	saisi_pour_user_id?: number | null;
	saisi_pour_nom?: string | null;
	saisi_pour_email?: string | null;
	saisi_pour_affichage?: string | null;
	non_relancable?: boolean;
	non_relancable_motif?: string | null;
	relance_count?: number;
	cree_le: string;
	mis_a_jour_le: string;
	/**  Ce que la carte repliée montre en vignette : les pièces du ticket, ou
	     celles de l'entrée d'Historique la plus récente qui en porte. Calculé par
	     le serveur (#464) — le front ne rejoue pas la règle. */
	apercu_pieces?: string[];
	/**  Le ticket a-t-il quitté la liste active pour les Archives ? Calculé par la
	     règle du SITE (`app/utils/archivage.py`, #515) : 30 jours après « Résolu »,
	     immédiat sur « Annulé », le délai étant réglable en administration.

	     🔴 L'écran appliquait sa propre règle — 7 jours, en dur, sur
	     `mis_a_jour_le` — pendant que le site en annonçait 30. Le front ne la rejoue
	     plus : deux règles pour la même notion trancheraient différemment, et un
	     ticket apparaîtrait dans la liste sans être dans les Archives. */
	archivee?: boolean;
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
	/**  Le périmètre que CETTE entrée déclare — absent quand elle n'en parle pas,
	     ce qui est le cas de l'immense majorité des commentaires (#497). */
	perimetre_cible?: string[];
}

/**  Un canal de diffusion, tel qu'il partira — ou pourquoi il ne partira pas (#498).
 *
 *   ⚠️ `inactif_motif` est ce qui distingue cet aperçu d'une maquette : bridge
 *   éteint, aucun destinataire joignable, droit manquant. L'écran doit le dire
 *   AVANT l'envoi plutôt que laisser croire à une diffusion qui n'aura pas lieu. */
export interface ApercuCanal {
	canal: 'email' | 'whatsapp';
	actif: boolean;
	inactif_motif?: string | null;
	destinataires: string[];
	sujet?: string | null;
	corps_html?: string | null;
	texte?: string | null;
	/** Le message WhatsApp est réduit à « avertissement + périmètre + lien ». */
	ampute: boolean;
	avec_photo: boolean;
}

export interface ApercuDiffusion {
	canaux: ApercuCanal[];
	/** Champs qui n'existeront qu'après la création — nommés, jamais inventés. */
	attribues_a_la_creation: string[];
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
	/** Lecture réservée au périmètre visé — incompatible avec l'affiche de hall (#347). */
	confidentiel?: boolean;
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
	/** File de l'onglet « Comptes & accès » de l'Espace CS : comptes + demandes d'accès. */
	validations_cs: number;
	/** File de `/admin` : les deux mêmes, plus les demandes de modification de profil. */
	validations_admin: number;
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
	/**  État EFFECTIF : archivée à la main, **ou** par la règle du site — 30 jours
	     après l'envoi (#515). C'est ce que les deux listes emploient. */
	archivee: boolean;
	/**  La décision HUMAINE seule. « Restaurer » n'a d'effet que sur elle : sur
	     une affiche archivée par le TEMPS, retirer le drapeau manuel ne la
	     ramènerait pas, et l'écran ne propose donc pas le geste. */
	archivee_manuellement?: boolean;
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
	//  Les TROIS canaux de la Diffusion (#480). Ils étaient absents : l'écran ne
	//  portait qu'une case, et le serveur ne consommait qu'un canal sur trois.
	envoyer_cs?: boolean;
	envoyer_syndic?: boolean;
	partager_whatsapp?: boolean;
	envoyer_auteur?: boolean;
}

/** Champs d'une actualité, prêts à alimenter le formulaire d'annonce de hall. */
export interface AnnonceHallPrefill {
	titre: string;
	message: string;
	perimetre_cible: string[];
	images: string[];
}
