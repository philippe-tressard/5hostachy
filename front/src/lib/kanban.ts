// Règles de visibilité kanban — source unique de vérité
// Utilisé par calendrier/+page.svelte et tableau-de-bord/+page.svelte
import { perimetreDuBatiment } from '$lib/perimetres';

/**
 * Les COLONNES du Kanban — la source unique, extraite de `calendrier/+page.svelte`
 * le 18/08/2026.
 *
 * 🔴 **Ces colonnes SONT le workflow d'un événement** : elles répondent
 * exactement à la question de la section 3 du cadre #430 — *« où en est cet
 * objet ? »*. Arbitré ainsi : *« peut-être que le kanban tu le glisses dans
 * Workflow ? »*. Aucun second champ d'état n'a été créé — deux notions de suivi
 * sur le même objet se contredisent au premier écart.
 *
 * Elles alimentent trois choses qui doivent rester d'accord : la vue Kanban, les
 * pastilles du formulaire d'événement, et les libellés de l'Historique
 * (« État : X → Y »). Le pendant serveur est `KANBAN_LABELS` dans
 * `calendrier_historique.py` — les contextes de build sont `./api` et `./front`,
 * le partage d'un fichier est impossible, seule la copie l'est.
 */
export const KANBAN_COLS = [
	{ id: 'ag', label: 'AG', color: '#8b5cf6' },
	{ id: 'cs', label: 'CS (en cours)', color: '#3b82f6' },
	{ id: 'syndic', label: 'Syndic (en cours)', color: '#f59e0b' },
	{ id: 'fournisseur', label: 'Prestataire (en cours)', color: '#f97316' },
	{ id: 'termine', label: 'Terminé', color: '#22c55e' },
	{ id: 'annule', label: 'Annulé', color: '#9ca3af' },
];

export interface KanbanCtx {
	isCS: boolean;
	isAdmin: boolean;
	canSeeAG: boolean;
	statut: string; // copropriétaire_résident, copropriétaire_bailleur, syndic, mandataire…
}

/** Retourne true si l'événement doit être visible dans le kanban pour cet utilisateur.
 *  Pré-condition : les locataires n'ont pas accès au kanban — ne pas appeler pour eux. */
export function kanbanEvVisible(ev: any, ctx: KanbanCtx): boolean {
	// Items archivés : masqués sauf annulé et maintenance récurrente en cours fournisseur
	if (
		ev.archivee &&
		ev.statut_kanban !== 'annule' &&
		!(ev.type === 'maintenance_recurrente' && ev.statut_kanban === 'fournisseur')
	) return false;
	// CS / Admin : voient tout
	if (ctx.isCS || ctx.isAdmin) return true;
	// Maintenance récurrente : toujours visible
	if (ev.type === 'maintenance_recurrente') return true;
	// Copropriétaires et aidants (héritent de la vision du délégant) : bypass du filtre affichable
	if (ctx.statut.startsWith('copropriétaire') || ctx.statut === 'aidant') return true;
	// Autres (syndic non-CS, mandataire, externe) : seulement les items affichables
	return !!ev.affichable;
}

/** Retourne true si la colonne doit être affichée pour cet utilisateur. */
export function kanbanColVisible(colId: string, ctx: KanbanCtx): boolean {
	if (colId === 'ag' || colId === 'cs') return ctx.canSeeAG;
	return true;
}

/** Retourne l'année de référence d'un événement kanban (pour le filtre exercice). */
export function kanbanEvYear(ev: any): number {
	const refDate =
		(ev.statut_kanban === 'termine' || ev.statut_kanban === 'annule') && ev.fin
			? ev.fin
			: ev.debut;
	return new Date(refDate).getFullYear();
}

/** Retourne true si l'événement correspond à l'exercice donné
 *  (inclut les items en retard non récurrents des années précédentes). */
export function kanbanEvMatchesYear(ev: any, exercice: number): boolean {
	const year = kanbanEvYear(ev);
	const isOverdue =
		ev.type !== 'maintenance_recurrente' &&
		year < exercice &&
		ev.statut_kanban !== 'termine' &&
		ev.statut_kanban !== 'annule';
	return isOverdue || year === exercice;
}

const _DEVIS_STATUT_MAP: Record<string, string> = {
	en_attente: 'syndic',
	accepte: 'fournisseur',
	realise: 'termine',
	refuse: 'annule',
};

/** Mappe le statut d'un devis vers la colonne kanban correspondante. */
export function devisStatutToKanban(statut: string | null | undefined): string {
	return _DEVIS_STATUT_MAP[statut ?? ''] ?? 'syndic';
}

/** Transforme un devis ponctuel en item kanban compatible avec les événements calendrier. */
export function devisPonctuelToKanban(
	d: any,
	opts?: { prestataireNom?: (id: number | null) => string }
): any {
	const rawDate = d.date_prestation ?? d.cree_le ?? new Date().toISOString();
	const debut =
		typeof rawDate === 'string' && rawDate.includes('T') ? rawDate : `${rawDate}T09:00`;
	const perimetre = d.perimetre ?? perimetreDuBatiment(d.batiment_id);
	return {
		id: -(100000 + Number(d.id)),
		_source: 'devis_ponctuel',
		type: 'maintenance',
		titre: d.titre,
		debut,
		fin: null,
		statut_kanban: devisStatutToKanban(d.statut),
		archivee: false,
		perimetre,
		affichable: true,
		prestataire_id: d.prestataire_id ?? null,
		prestataire_nom: opts?.prestataireNom?.(d.prestataire_id) ?? null,
		description: d.notes ?? null,
		cree_le: d.cree_le ?? debut,
		mis_a_jour_le: d.mis_a_jour_le ?? null,
		auteur_nom: d.auteur_nom ?? null,
	};
}
