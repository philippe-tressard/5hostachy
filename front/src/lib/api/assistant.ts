/**
 *  L'assistant IA des formulaires — l'usage « description » (#985).
 *
 *  Deux routes, réservées au conseil syndical et à l'administration : l'appel
 *  est facturé. L'écran n'affiche l'icône ✨ qu'à eux ; le serveur refuse aux
 *  autres — ce que l'interface masque n'est qu'un confort.
 *
 *  ⚠️ La synthèse de contrat garde sa route dans `prestataires` : elle part
 *  d'un contrat en base, celle-ci part d'un texte en cours de saisie.
 */
import { api } from './client';

/** Ce que la section Description envoie — voir `utils/assistant_description.py`. */
export interface DemandeDescription {
	/** La nature de l'objet : `ticket`, `actualité`, `commentaire`… */
	entite: string;
	titre?: string | null;
	description?: string | null;
	/** Des libellés courts, déclarés par l'écran : catégorie, périmètre, état… */
	contexte?: Record<string, string>;
	/** « plus court », « plus formel » — complète le prompt de l'admin. */
	precision?: string | null;
	/** Faux sur une entrée de fil : un commentaire n'a pas de titre à proposer. */
	avec_titre: boolean;
}

/** Ce que le modèle propose — et ce qui a changé, calculé par le SERVEUR. */
export interface PropositionDescription {
	titre: string | null;
	description: string;
	titre_modifie: boolean;
	description_modifiee: boolean;
}

//  ── Les types de l'onglet Admin › Assistant IA — déplacés d'`administration`
//  (30/09/2026), qui franchissait 500 lignes : ils sont de ce domaine-ci.

/**  Une ligne de consommation : un usage, un modèle, un mois. */
export interface LigneConsommationIA {
	usage: string;
	libelle: string;
	modele: string;
	appels: number;
	erreurs: number;
	/** Appels refusés AVANT l'envoi : plafond mensuel atteint. */
	refus: number;
	jetons_entree: number;
	jetons_sortie: number;
	/** La part de `jetons_entree` lue en cache — facturée au prix du cache. */
	jetons_cache: number;
	/** En DOLLARS, texte décimal (« 0.0900 »), au tarif saisi ; `null` sans tarif. */
	cout_usd: string | null;
}

/**  La consommation de l'assistant IA (`GET /config/llm-consommation`). */
export interface ConsommationIA {
	mois: { mois: string; usages: LigneConsommationIA[] }[];
	plafonds: { usage: string; libelle: string; plafond: number; consommes: number }[];
	mois_courant: string;
}

type ChampUsageIA = 'actif' | 'modele' | 'prompt' | 'max_jetons' | 'plafond_mois' | PrixIA;
/** Les trois prix d'un usage, dans l'ordre de l'écran (`llm_usages.CHAMPS_USAGE`). */
export type PrixIA = 'prix_entree' | 'prix_sortie' | 'prix_cache';

/** Un usage de l'assistant IA, tel que `GET /config/llm-usages` le décrit. */
export interface UsageIA {
	code: string;
	libelle: string;
	description: string;
	prompt_defaut: string;
	max_jetons_defaut: number;
	/** Les clés `ConfigSite` de ses réglages — prix en DOLLARS par million. */
	cles: Record<ChampUsageIA, string>;
}

/** Le tarif ENREGISTRÉ du modèle d'un usage — en DOLLARS par million de
 *  jetons, texte décimal comme la grille (« 0.075 ») ; `null` quand la grille
 *  ne le donne pas (le champ n'a alors pas été touché). */
export type TarifEnregistre = Record<PrixIA, string | null> & {
	/** La grille lue, la ligne retenue et les prix recopiés. */
	remarque: string;
};

export const assistant = {
	/** L'icône ✨ a-t-elle un sens ? — décidé par le serveur, rien de la
	 *  configuration ne sort (ni fournisseur, ni modèle, ni prompt). */
	disponible: () => api.get<{ description: boolean }>('/assistant/disponible'),
	/** Une PROPOSITION : rien n'est enregistré. Se rejoue à volonté, chaque
	 *  appel partant du texte COURANT du formulaire. */
	description: (demande: DemandeDescription) =>
		api.post<PropositionDescription>('/assistant/description', demande),
	/** Cherche le tarif du modèle ENREGISTRÉ de `usage` dans la grille de son
	 *  fournisseur et l'ENREGISTRE, en dollars (admin). `modele`
	 *  est celui qu'affiche l'écran : refusé s'il n'est pas l'enregistré. */
	tarif: (usage: string, modele: string) =>
		api.post<TarifEnregistre>('/config/llm-tarif', { usage, modele }),
};
