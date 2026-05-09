// Règles de visibilité kanban — source unique de vérité
// Utilisé par calendrier/+page.svelte et tableau-de-bord/+page.svelte

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
	// Copropriétaires : bypass du filtre affichable (assouplissement)
	if (ctx.statut.startsWith('copropriétaire')) return true;
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
	const perimetre = d.perimetre ?? (d.batiment_id ? `bat:${d.batiment_id}` : 'résidence');
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
