/**
 *  Les questions au règlement de copropriété — Espace CS › Règlement.
 *
 *  Le serveur décide de tout : si l'assistant peut répondre (`disponible`), quel
 *  texte est en vigueur, et quels extraits ont été RETROUVÉS dans ce texte
 *  (`verifie`, `page`, `acte` — calculés par le code, jamais par le modèle).
 *  L'écran ne recompose rien.
 *
 *  Routes : `api/app/routers/reglement.py`, réservées au conseil et à l'admin.
 */
import { api } from './client';

/** Une version du texte du règlement chargée par le conseil. */
export interface TexteReglement {
	id: number;
	titre: string;
	nom_fichier: string;
	nb_caracteres: number;
	charge_par: string | null;
	cree_le: string;
}

/** Ce que l'onglet lit en arrivant. */
export interface EtatReglement {
	disponible: boolean;
	texte: TexteReglement | null;
	nb_versions: number;
}

/** Un extrait cité par l'assistant, et ce que le code en a vérifié. */
export interface ExtraitReglement {
	citation: string;
	/** La référence DONNÉE par le modèle. */
	reference: string;
	apport: string;
	/** Retrouvé mot pour mot dans le texte chargé. */
	verifie: boolean;
	/** Le repère de page qui le précède dans le texte — s'il a été retrouvé. */
	page: string | null;
	/** L'acte (« LIVRE I ») qui le contient. */
	acte: string | null;
}

/** Une question posée, et la réponse du juriste. */
export interface QuestionReglement {
	id: number;
	question: string;
	verdict: 'oui' | 'non' | 'sous_conditions' | 'non_prevu' | 'incertain';
	verdict_libelle: string;
	reponse: string;
	reserves: string | null;
	extraits: ExtraitReglement[];
	texte_id: number;
	/** Faux : la réponse a lu une version remplacée depuis. */
	texte_en_vigueur: boolean;
	texte_charge_le: string | null;
	auteur_nom: string | null;
	modele: string | null;
	cout_usd: string | null;
	faq_item_id: number | null;
	cree_le: string;
}

/** Une entrée de FAQ, telle que le conseil l'a relue. */
export interface PublicationFaq {
	categorie: string;
	question: string;
	reponse: string;
	ordre?: number;
}

export const reglement = {
	etat: () => api.get<EtatReglement>('/reglement'),
	charger: (nom_fichier: string, contenu: string) =>
		api.post<TexteReglement>('/reglement/textes', { nom_fichier, contenu }),
	questions: () => api.get<QuestionReglement[]>('/reglement/questions'),
	poser: (question: string) => api.post<QuestionReglement>('/reglement/questions', { question }),
	publierDansLaFaq: (id: number, corps: PublicationFaq) =>
		api.post<QuestionReglement>(`/reglement/questions/${id}/faq`, corps),
	supprimerQuestion: (id: number) => api.delete(`/reglement/questions/${id}`),
};
