//  Présentation des publications : ce qui ne dépend ni du DOM ni d'un store, et
//  qui n'avait donc rien à faire dans `actualites/+page.svelte`.
//
//  Extrait le 12/08/2026 en y ajoutant le renvoi WhatsApp (#300) : le fichier
//  était à 756 lignes et le garde-fou de modularité (rang 1) refuse qu'un fichier
//  de plus de 500 lignes grossisse. La règle est « on découpe le fichier QUAND on
//  y touche » — la frontière retenue est la même que côté scripts d'infra : la
//  décision d'un côté, testable seule ; le rendu de l'autre.
import type { Publication } from '$lib/api';

//: Statuts d'une PUBLICATION — à ne pas confondre avec ceux d'un ticket
//: (`ouvert`/`résolu`/`annulé`), qui sont une autre notion et vivent ailleurs.
export const STATUT_LABELS: Record<string, string> = {
	publie: 'Publié', en_cours: 'En cours', resolu: 'Résolu', annule: 'Annulé',
};

export const STATUT_BADGE: Record<string, string> = {
	publie: 'badge-blue', en_cours: 'badge-orange', resolu: 'badge-green', annule: 'badge-gray',
};

/**
 * ⚠️ **Plus aucun écran ne propose ces états** depuis le 18/08/2026 : une actualité
 * n'a pas de workflow, elle est publiée puis bascule dans l'Historique au bout de
 * son délai. Cette liste n'est donc **plus exportée** — la garder aurait laissé
 * croire qu'un écran pouvait s'en servir.
 *
 * `STATUT_LABELS` et `STATUT_BADGE`, eux, restent : d'anciennes publications
 * portent un état en base, et la carte l'affiche encore **en lecture**.
 */

/**
 * Vrai quand un contenu riche ne porte aucun texte — `<p></p>` en est un.
 *
 * L'éditeur rend toujours du balisage, même vide : tester la chaîne brute
 * laisserait passer un formulaire vide.
 */
export const richEmpty = (html: string) => !html || html.replace(/<[^>]+>/g, '').trim() === '';

/**
 * Groupe des publications par année, de la plus récente à la plus ancienne.
 *
 * L'année retenue est celle de la dernière mise à jour, et à défaut celle de la
 * création : une publication archivée après plusieurs relances appartient à
 * l'année où elle a vécu, pas à celle où elle a été ouverte.
 */
export function grouperParAnnee(pubs: Publication[]): [number, Publication[]][] {
	const groupes = new Map<number, Publication[]>();
	for (const p of pubs ?? []) {
		const annee = new Date(p.mis_a_jour_le ?? p.cree_le).getFullYear();
		if (!groupes.has(annee)) groupes.set(annee, []);
		groupes.get(annee)!.push(p);
	}
	return [...groupes.entries()].sort(([a], [b]) => b - a);
}
