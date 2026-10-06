import { get } from 'svelte/store';
import DialogueFusion from '$lib/components/DialogueFusion.svelte';
import { toast } from '$lib/components/Toast.svelte';
import { tickets as ticketsApi, type CandidateFusion } from '$lib/api';
import { messageErreur } from '$lib/erreurs';
import { modaleImperative } from '$lib/modale-imperative';
import { isCS } from '$lib/stores/auth';
import { STATUT_TICKET_LABELS, estTicketClos } from '$lib/tickets';

/**
 * **À la clôture, demander s'il faut fusionner les affaires liées** (#1704).
 *
 * Écrit une fois pour les trois gestes qui clôturent une affaire — la Suite
 * (`SuiteAffaire`), le glissement au kanban (`VueKanbanAffaires`) et la
 * correction de l'affaire (`FormulaireTicket`) : la question ne dépend pas du
 * chemin pris pour clore.
 *
 * Rend :
 * - `[]` quand il n'y a rien à demander — l'état ne CLÔT pas (déjà close, ou
 *   un état actif), le lecteur n'est pas du conseil, aucune liée n'est
 *   ouverte — ou qu'on clôt sans fusionner ;
 * - les identifiants cochés ;
 * - `null` quand on renonce, ou que la liste n'a pas pu être lue : le geste
 *   de clôture ne part pas. Clore sans avoir pu poser la question ferait
 *   passer « je n'ai pas pu regarder » pour « il n'y avait rien ».
 *
 * ⚠️ Le CONSEIL seul fusionne (`utils/fusion_affaires`) — la liste des
 * candidates lui est réservée, d'où la garde sur `isCS`.
 */
export async function demanderFusion(
	ticket: { id: number; numero: string; statut: string },
	statut: string | undefined,
): Promise<number[] | null> {
	if (!get(isCS) || !estTicketClos(statut) || estTicketClos(ticket.statut)) return [];
	let candidates: CandidateFusion[];
	try {
		candidates = await ticketsApi.candidatesFusion(ticket.id);
	} catch (e) {
		toast('error', messageErreur(e));
		return null;
	}
	if (!candidates.length) return [];
	return modaleImperative<number[] | null>(
		DialogueFusion,
		{ numero: ticket.numero, etat: STATUT_TICKET_LABELS[statut ?? ''] ?? statut, candidates },
		null,
	);
}
