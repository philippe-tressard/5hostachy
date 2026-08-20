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

/**
 * **La charge utile qu'un formulaire d'évolution émet** — le contrat entre
 * `EvolForm` et ceux qui la relaient à l'API.
 *
 * ## Pourquoi ce type existe (#529, 20/08/2026)
 *
 * Signalé à l'écran : *« j'ai créé une réponse au ticket en changeant le
 * périmètre, celui-ci n'a pas été pris en compte »*.
 *
 * `CarteTicket` proposait bien la section Périmètre, `EvolForm` la collectait et
 * l'émettait — et `tickets/+page.svelte` la **jetait** en recopiant la charge
 * utile champ par champ, à partir d'un type local qui l'ignorait. Ce type local
 * portait pourtant le commentaire *« même contrat que la fiche détail »*, ce qui
 * était faux : la fiche, elle, relaie la charge entière.
 *
 * 🔴 **Le défaut ne lève rien.** Le formulaire annonce l'enregistrement, le
 * serveur enregistre une évolution parfaitement valide, et seul le périmètre
 * affiché ensuite trahit la perte. C'est le profil d'erreur qu'aucun test
 * fonctionnel ne voit et qu'une relecture ne trouve pas — il faut comparer deux
 * fichiers distants de quatre cents lignes.
 *
 * ⚠️ Un champ ajouté ici doit l'être **aussi** dans le `dispatch` d'`EvolForm` et
 * dans le client d'API. `npm run lint:charge-utile` échoue si un relais oublie
 * un champ que le formulaire émet.
 */
export interface ChargeUtileEvolution {
	type: string;
	contenu?: string;
	nouveau_statut?: string;
	fichiers_urls?: string[];
	email_externe?: string;
	partager_whatsapp?: boolean;
	envoyer_syndic?: boolean;
	envoyer_cs?: boolean;
	/**  Le périmètre que l'entrée PRÉCISE — absent quand elle n'en parle pas, et
	 *   le serveur ne touche alors pas à celui de l'objet (#497). */
	perimetre_cible?: string[];
	/**  Message interne : proposé seulement là où `avecInterne` est activé, donc
	 *   aujourd'hui la seule fiche d'un ticket. */
	interne?: boolean;
}
