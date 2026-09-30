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

/** Le tarif d'un modèle proposé par l'assistant — en CENTIMES par million de
 *  jetons, l'unité stockée ; `null` quand le modèle ne le connaît pas. */
export interface TarifPropose {
	prix_entree: number | null;
	prix_sortie: number | null;
	/** Prix d'origine, devise, taux, date des connaissances — à montrer. */
	remarque: string;
}

export const assistant = {
	/** L'icône ✨ a-t-elle un sens ? — décidé par le serveur, rien de la
	 *  configuration ne sort (ni fournisseur, ni modèle, ni prompt). */
	disponible: () => api.get<{ description: boolean }>('/assistant/disponible'),
	/** Une PROPOSITION : rien n'est enregistré. Se rejoue à volonté, chaque
	 *  appel partant du texte COURANT du formulaire. */
	description: (demande: DemandeDescription) =>
		api.post<PropositionDescription>('/assistant/description', demande),
	/** Le tarif de `modele`, demandé à l'usage « Tarif d'un modèle » (admin).
	 *  Une PROPOSITION : l'écran remplit les deux prix, « Enregistrer » écrit. */
	tarif: (modele: string) => api.post<TarifPropose>('/config/llm-tarif', { modele }),
};
