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
//  choix d'une affiche pour pré-remplir une actualité. L'autre sens — choisir
//  une actualité pour composer une affiche — n'a plus de plafond : « permet la
//  génération d'une affiche à partir de n'importe quelle publication du fil,
//  non archivée », demandé à l'écran. Voir `sourcesPreremplissage` ci-dessous.

/**
 *  Les publications proposées au PRÉ-REMPLISSAGE d'une affiche de hall, dans
 *  l'ordre où le sélecteur doit les montrer.
 *
 *  🔴 **TOUT le fil d'actualité non archivé, quel que soit le type de
 *  publication** (demandé à l'écran le 10/09/2026). Il n'y a plus de plafond :
 *  la liste était coupée aux dix plus récentes, et c'est ce plafond — pas un
 *  filtre — qui rendait la plupart des publications impossibles à reprendre au
 *  hall.
 *
 *  ⚠️ Le périmètre de la liste est celui du FIL : `publications.list()` sans
 *  argument ne rend que les publications non archivées, tous types confondus.
 *  On ne refiltre donc rien ici — refaire côté écran un tri que le serveur
 *  applique déjà, c'est se donner deux réponses à la même question.
 *
 *  🔴 **Une publication ÉPINGLÉE vient en tête** (même jour). Le tri se faisait
 *  par date, et une actualité épinglée — donc celle qu'on veut précisément
 *  garder sous les yeux — se retrouvait noyée. Épingler dit « ceci reste
 *  d'actualité » : c'est exactement ce qu'on veut afficher dans le hall.
 *
 *  ⚠️ Les BROUILLONS restent exclus — proposer de recopier un texte non publié
 *  ferait paraître au hall ce que personne n'a encore validé. C'est la seule
 *  exclusion, et elle ne dépend pas de l'âge.
 */
export function sourcesPreremplissage<
	T extends { brouillon?: boolean; epingle?: boolean; cree_le: string },
>(publications: T[]): T[] {
	const parDateDesc = (a: T, b: T) => new Date(b.cree_le).getTime() - new Date(a.cree_le).getTime();
	const publiees = publications.filter((p) => !p.brouillon).sort(parDateDesc);
	return [...publiees.filter((p) => p.epingle), ...publiees.filter((p) => !p.epingle)];
}
