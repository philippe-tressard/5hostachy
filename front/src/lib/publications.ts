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

/**
 *  Les actualités proposées au PRÉ-REMPLISSAGE d'une affiche de hall, dans
 *  l'ordre où le sélecteur doit les montrer.
 *
 *  🔴 **Une actualité ÉPINGLÉE est toujours proposée, quel que soit son âge**
 *  (demandé à l'écran le 10/09/2026). Le tri se faisait par date seule, puis
 *  coupait aux dix premières : une actualité épinglée — donc celle qu'on veut
 *  précisément garder sous les yeux, donc souvent la plus ancienne des
 *  importantes — sortait de la liste et devenait la seule qu'on ne pouvait pas
 *  reprendre. Le geste manquait exactement là où il servait le plus.
 *
 *  ⚠️ Épingler dit « ceci reste d'actualité ». Trier par date de création revient
 *  à dire le contraire : c'est la date qui décidait de ce qui est encore d'usage,
 *  alors que quelqu'un l'avait déjà décidé à la main.
 *
 *  ⚠️ Le plafond ne bouge pas — dix, et c'est la même constante des deux côtés du
 *  geste. Si plus de dix actualités sont épinglées, elles occupent toute la
 *  liste, et c'est la bonne réponse : ce sont celles qu'on a désignées comme
 *  encore utiles.
 *
 *  ⚠️ Les BROUILLONS restent exclus — proposer de recopier un texte non publié
 *  ferait paraître au hall ce que personne n'a encore validé.
 */
export function sourcesPreremplissage<
	T extends { brouillon?: boolean; epingle?: boolean; cree_le: string },
>(publications: T[], plafond: number = MAX_SOURCES_PREREMPLISSAGE): T[] {
	const parDateDesc = (a: T, b: T) => new Date(b.cree_le).getTime() - new Date(a.cree_le).getTime();
	const publiees = publications.filter((p) => !p.brouillon).sort(parDateDesc);
	return [...publiees.filter((p) => p.epingle), ...publiees.filter((p) => !p.epingle)].slice(
		0,
		plafond,
	);
}
