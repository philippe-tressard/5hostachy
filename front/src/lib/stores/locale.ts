import { writable } from 'svelte/store';
import { browser } from '$app/environment';

export type Locale = 'fr' | 'en';

const saved = browser ? (localStorage.getItem('hostachy_locale') as Locale | null) : null;

// Default to 'fr'; only switch to 'en' if explicitly saved
export const locale = writable<Locale>(saved === 'en' ? 'en' : 'fr');

if (browser) {
	locale.subscribe((v) => localStorage.setItem('hostachy_locale', v));
}

/** Labels traduits (extensible) */
export const ROLE_LABELS: Record<Locale, Record<string, string>> = {
	fr: {
		résident: 'Résident',
		locataire: 'Locataire',
		'copropriétaire_résident': 'Copropriétaire Résident',
		'copropriétaire_bailleur': 'Copropriétaire Bailleur',
		bailleur: 'Copropriétaire Bailleur',
		syndic: 'Syndic',
		mandataire: 'Mandataire',
		conseil_syndical: 'Conseil syndical',
		admin: 'Admin',
	},
	en: {
		résident: 'Resident',
		locataire: 'Tenant',
		'copropriétaire_résident': 'Owner-Occupier',
		'copropriétaire_bailleur': 'Landlord',
		bailleur: 'Landlord',
		syndic: 'Manager',
		mandataire: 'Proxy',
		conseil_syndical: 'Board Member',
		admin: 'Admin',
	},
};

export const NAV_LABELS: Record<Locale, Record<string, string>> = {
	fr: {
		'/tableau-de-bord': 'Accueil',
		'/actualites': 'Actualités',
		'/residence': 'Résidence',
		'/calendrier': 'Calendrier',
		'/tickets': 'Demandes',
		'/mon-lot': 'Mon lot',
		'/acces-securite': 'Accès & badges',
		'/sondages': 'Communauté',
		'/idees': 'Boîte à idées',
		'/gouvernance': 'Gouvernance',
		'/prestataires': 'Prestataires',
		'/annuaire': 'Annuaire',
		'/faq': 'FAQ',
		'/espace-cs': 'Espace CS',
		'/admin': 'Paramétrage',
		'/profil': 'Profil',
		deconnexion: 'Déconnexion',
	},
	en: {
		'/tableau-de-bord': 'Home',
		'/actualites': 'News',
		'/residence': 'Building',
		'/calendrier': 'Calendar',
		'/tickets': 'Requests',
		'/mon-lot': 'My unit',
		'/acces-securite': 'Access & badges',
		'/sondages': 'Participation',
		'/idees': 'Ideas box',
		'/gouvernance': 'Governance',
		'/prestataires': 'Contractors',
		'/annuaire': 'Directory',
		'/faq': 'FAQ',
		'/espace-cs': 'Board space',
		'/admin': 'Settings',
		'/profil': 'Profile',
		deconnexion: 'Sign out',
	},
};
