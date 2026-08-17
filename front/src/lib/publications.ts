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

//: La pastille de couleur qui précède le libellé dans les listes de choix. Elle
//: ne sert QU'À ça — le badge d'une carte, lui, se colore par `STATUT_BADGE`.
const STATUT_PUCE: Record<string, string> = {
	publie: '\u{1F535}', en_cours: '\u{1F7E1}', resolu: '\u{1F7E2}', annule: '⚫',
};

/**
 * Les états proposables d'une publication — **dérivés**, jamais réécrits.
 *
 * Cette liste existait en clair dans `actualites/+page.svelte`, et le formulaire
 * d'édition en portait une **seconde** copie sous forme de quatre `<option>`
 * écrites à la main. C'est la panne des statuts de ticket à l'identique (#415,
 * quatre copies) : deux listes d'accord entre elles ne prouvent rien.
 *
 * ⚠️ Le pendant serveur est `api/app/routers/publications/commun.py`
 * (`STATUTS_PUBLICATION`, `STATUT_LABELS`). Les contextes de build sont `./api`
 * et `./front` : rien de la racine n'entre dans les images, le partage d'un
 * fichier est impossible — toute modification ici en appelle une là-bas.
 */
export const STATUT_PUBLICATION_OPTIONS = Object.entries(STATUT_LABELS).map(
	([value, label]) => ({ value, label: `${STATUT_PUCE[value] ?? ''} ${label}`.trim() }),
);

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
