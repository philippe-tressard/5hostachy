/**
 * Traduire une erreur d'appel API en une phrase **actionnable** pour l'écran.
 *
 * ## Pourquoi (#519)
 *
 * Trois listes de la Communauté portaient `.catch(() => [])` : toute erreur
 * devenait un tableau vide, et l'écran affichait « Aucun sondage » — le même
 * rendu que s'il n'y avait rien. L'utilisateur a cru ses données détruites.
 *
 * Distinguer l'échec du vide ne suffit pas : encore faut-il **dire quoi faire**.
 * « Une erreur est survenue » n'est pas plus actionnable que « aucun sondage » ;
 * « votre session a expiré, rechargez la page » l'est.
 *
 * ⚠️ Écrit ici et non dans une page : tout écran qui charge une liste en a
 * besoin, et #515 va en demander sur sept pages. Une copie par écran divergerait
 * au premier message ajusté.
 */
import { ApiError } from '$lib/api';

export function messageErreur(e: unknown): string {
	if (e instanceof ApiError) {
		//  401 : le cas le plus fréquent, et le seul que l'utilisateur peut régler
		//  lui-même. Le nommer évite de chercher une panne qui n'existe pas.
		if (e.status === 401) return 'Votre session a expiré — rechargez la page pour vous reconnecter.';
		//  403 : le serveur a répondu et refuse. Son message est plus précis que
		//  tout ce qu'on pourrait écrire ici (accès suspendu, profil non autorisé).
		if (e.status === 403) return e.message || 'Vous n’avez pas accès à cette rubrique.';
		return e.message || 'Le serveur n’a pas répondu correctement.';
	}
	//  Ni ApiError ni rien de connu : réseau coupé, serveur injoignable.
	return 'Impossible de joindre le serveur — vérifiez votre connexion.';
}
