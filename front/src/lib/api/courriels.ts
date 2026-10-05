//  Le domaine **Courriels des affaires** : ce que la relève de la boîte des
//  réponses a fait de chaque message reçu à l'adresse des affaires (#1447).
//
//  Né le 05/10/2026 avec l'onglet Espace CS › Courriels. Le client de
//  l'administration (`administration.ts`) et ses types sont au plafond de
//  modularité : un domaine neuf a son propre fichier.
import { api } from './client';

/**  Un message relevé dans la boîte des réponses (`GET /courriels-affaires`).
 *   Jamais son texte : le journal dit ce qu'on a DÉCIDÉ (#1447). L'expéditeur est
 *   son adresse en entier pour l'administrateur, son nom seul pour le conseil. */
export interface CourrielReleve {
	id: number;
	releve_le: string;
	envoye_le: string | null;
	expediteur: string;
	objet: string;
	decision: 'accepte' | 'relance' | 'refuse' | 'ignore';
	motif: string;
	ticket_id: number | null;
	affaire: string | null;
}

/**  Le journal tel que l'onglet Courriels le lit : `limite` est le paramètre du site. */
export interface JournalCourriels {
	limite: number;
	messages: CourrielReleve[];
}

export const courriels = {
	/**  Ce que la relève a fait des derniers messages, et pourquoi (#1447). */
	journal: (): Promise<JournalCourriels> => api.get<JournalCourriels>('/courriels-affaires'),
};
