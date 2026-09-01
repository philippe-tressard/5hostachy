// Règles de visibilité kanban — source unique de vérité
// Utilisé par calendrier/+page.svelte et tableau-de-bord/+page.svelte

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
	)
		return false;
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
/**
 * Largeur en dessous de laquelle un kanban passe en vue étroite.
 *
 * 🔴 Le site rend le kanban à DEUX endroits — la page Calendrier (colonnes
 * empilées) et le tableau de bord (une colonne à la fois). Ils basculaient à
 * **767** et **900 px**, si bien qu'entre les deux l'un était lisible et l'autre
 * non : exactement la plage des tablettes en portrait (768 à 820 px), que ni un
 * téléphone ni un ordinateur n'occupent. Signalé le 01/09/2026 sur un iPad.
 *
 * ⚠️ Le condensé ne bascule plus par le CSS mais par un `{#if}` sur cette valeur.
 * Deux tentatives de bascule CSS ont échoué le même soir — la première parce
 * qu'une règle globale ne surcharge pas une règle scopée, la seconde pour une
 * raison que je n'ai jamais pu observer, faute de voir l'écran connecté. Un
 * rendu conditionnel ne dépend d'aucune cascade : une seule vue existe à la fois,
 * et ce qui n'est pas rendu ne peut pas être masqué par erreur.
 *
 * Le kanban complet, lui, garde sa bascule CSS (`.kanban`, `composants.css`) :
 * elle n'empile que des colonnes, sans changer ce qui est rendu.
 * `api/tests/test_seuil_kanban.py` refuse que les deux valeurs divergent.
 */
export const SEUIL_KANBAN_ETROIT = 900;

export function kanbanColVisible(colId: string, ctx: KanbanCtx): boolean {
	if (colId === 'ag' || colId === 'cs') return ctx.canSeeAG;
	return true;
}

/** Retourne l'année de référence d'un événement kanban (pour le filtre exercice). */
export function kanbanEvYear(ev: any): number {
	const refDate =
		(ev.statut_kanban === 'termine' || ev.statut_kanban === 'annule') && ev.fin ? ev.fin : ev.debut;
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
