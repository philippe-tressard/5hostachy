/*
 *  `/tickets/nouveau` n'existe plus comme écran : la création d'un ticket se fait
 *  dans une boîte au sein de `/tickets`, comme partout ailleurs sur le site (#367).
 *
 *  Cette route survit uniquement pour REDIRIGER. Un chemin public qui a existé
 *  reste dans les favoris, les historiques de navigation et les liens déjà
 *  envoyés : le supprimer sec transforme un signet en 404, sans que personne ne
 *  l'apprenne autrement qu'en tombant dessus. Cf. `standards/08` §8 — un point
 *  d'entrée qui vit hors du dépôt n'est réparé par aucun remaniement interne.
 *
 *  `?nouveau=1` ouvre la boîte de création à l'arrivée : celui qui visait un
 *  écran de saisie doit obtenir un écran de saisie, pas une liste où retrouver
 *  le bouton.
 */
import { redirect } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const load: PageLoad = () => {
	// 308 : permanent, et qui préserve la méthode. Les navigateurs et la PWA
	// mettront la cible en cache — ce qui est voulu, l'ancienne route ne
	// reviendra pas.
	redirect(308, '/tickets?nouveau=1');
};
