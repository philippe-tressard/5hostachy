/**
 * Le vocabulaire d'un **fil d'évolution** — écrit une fois pour les trois entités
 * qui en portent un : tickets, actualités, événements de calendrier.
 *
 * ## Pourquoi ce module (19/08/2026, signalé à l'écran)
 *
 * > *« Pourquoi mon commentaire sur un ticket a une icône de type relance et non
 * > commentaire ? »*
 *
 * Parce que la même notion était écrite **trois fois, avec trois valeurs** :
 *
 * | Où | `commentaire` | `reponse` | `etat` |
 * |---|---|---|---|
 * | le bouton qui ouvre le formulaire (`HistoriqueTicket`) | 💬 | — | — |
 * | le fil lui-même (`RubriqueHistorique`) | 📝 | 💬 | 🔄 |
 * | le flux d'activité (`api/app/routers/flux/tickets.py`) | 🔧 | 💬 | — |
 *
 * On cliquait donc « 💬 Commenter » et l'entrée s'affichait en 📝 — un mémo, que
 * l'utilisateur a lu comme une relance. Et 💬, l'icône qu'il attendait, était
 * prise par `reponse`.
 *
 * C'est le défaut de #415 (les statuts) et #413 (les champs), sur un troisième
 * objet : *« Chacune était cohérente avec elle-même ; c'est ce qui les rendait
 * invisibles à la relecture. »*
 *
 * ⚠️ **Le geste et son résultat doivent porter le MÊME signe.** C'est la règle
 * qui tranche ici : l'icône de l'entrée est celle du bouton qui l'a créée, pas
 * l'inverse. Un utilisateur ne relit pas une table, il reconnaît un dessin.
 *
 * ## Ce qui reste écrit deux fois, et pourquoi
 *
 * L'API a sa propre table (`flux/tickets.py`) : les contextes de build sont
 * `./api` et `./front`, rien de la racine n'entre dans les images — aucun fichier
 * ne peut être partagé (cf. la mémoire projet du 14/08/2026). Elle décrit
 * d'ailleurs un AUTRE rendu — une carte de flux « ticket mis à jour », pas une
 * entrée de fil — donc son 🔧 n'est pas forcément faux. L'écart est signalé, pas
 * corrigé en silence.
 */

/** Les trois types que porte une entrée de fil, côté serveur comme côté écran. */
export type TypeEvolution = 'commentaire' | 'etat' | 'reponse';

/**
 * Icône d'une entrée de fil.
 *
 * `commentaire` → 💬, **la même que le bouton « Commenter »**.
 * `reponse` → ↩️ : elle répond à quelque chose, ce que la bulle seule ne disait
 * pas — et la bulle revient à qui la mérite.
 * `etat` → 🔄, inchangée : une transition de workflow.
 */
export const EVOLUTION_ICONE: Record<string, string> = {
	commentaire: '\u{1F4AC}',
	reponse: '↩️',
	etat: '\u{1F504}',
};

/**
 * L'icône du type, ou celle du commentaire par défaut.
 *
 * ⚠️ Le repli est `commentaire` et non un point d'interrogation : un type inconnu
 * vient forcément d'une entrée de fil, et lui donner un signe d'erreur ferait
 * croire à un défaut de la donnée là où il n'y a qu'un type que l'écran ne
 * connaît pas encore.
 */
export function evolutionIcone(type: string | undefined | null): string {
	return EVOLUTION_ICONE[type ?? ''] ?? EVOLUTION_ICONE.commentaire;
}
