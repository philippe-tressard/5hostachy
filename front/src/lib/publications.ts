//  Présentation des publications : ce qui ne dépend ni du DOM ni d'un store, et
//  qui n'avait donc rien à faire dans `actualites/+page.svelte`.
//
//  Extrait le 12/08/2026 en y ajoutant le renvoi WhatsApp (#300) : le fichier
//  était à 756 lignes et le garde-fou de modularité (rang 1) refuse qu'un fichier
//  de plus de 500 lignes grossisse. La règle est « on découpe le fichier QUAND on
//  y touche » — la frontière retenue est la même que côté scripts d'infra : la
//  décision d'un côté, testable seule ; le rendu de l'autre.

//: Statuts d'une PUBLICATION — à ne pas confondre avec ceux d'un ticket
//: (`ouvert`/`résolu`/`annulé`), qui sont une autre notion et vivent ailleurs.
export const STATUT_LABELS: Record<string, string> = {
	publie: 'Publié',
	en_cours: 'En cours',
	resolu: 'Résolu',
	annule: 'Annulé',
};

export const STATUT_BADGE: Record<string, string> = {
	publie: 'badge-blue',
	en_cours: 'badge-orange',
	resolu: 'badge-green',
	annule: 'badge-gray',
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
 *  Combien d'entrées un sélecteur de PRÉ-REMPLISSAGE propose au plus.
 *
 *  🔴 Le geste existe dans les deux sens depuis #832 — une affiche de hall
 *  pré-remplie depuis une actualité, une actualité pré-remplie depuis une
 *  affiche — et le plafond était écrit dans le premier (`AH_PUBS_MAX`). Deux
 *  écritures d'un même seuil divergent au premier ajustement, et le sélecteur
 *  d'un côté proposerait dix entrées quand l'autre en propose vingt, sans que
 *  personne sache lequel a raison.
 *
 *  ⚠️ Dix, et pas plus : c'est une liste déroulante qu'on parcourt des yeux
 *  pour retrouver quelque chose qu'on vient d'écrire, pas un historique. Au-delà,
 *  chercher dans le sélecteur coûte plus que ressaisir.
 */
export const MAX_SOURCES_PREREMPLISSAGE = 10;

//  ⚠️ **Il ne gouverne plus qu'UN sens du geste depuis le 10/09/2026** : le
//  choix d'une affiche pour pré-remplir une actualité. L'autre sens — choisir un
//  élément du fil pour composer une affiche — n'a plus de plafond ET n'est plus
//  décidé ici : la liste, son tri et ses exclusions viennent du serveur
//  (`GET /annonces-hall/sources`, `api/app/utils/sources_affiche.py`). Le fil
//  agrège trois familles, et seul le serveur sait lesquelles sont reprenables.
