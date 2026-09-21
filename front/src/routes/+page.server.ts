import { redirect } from '@sveltejs/kit';

import { CHEMIN_CONNEXION } from '$lib/redirection';

/**
 * Redirection serveur selon l'état de la session.
 * Évite les 2 appels API inutiles (auth.me + tryRefresh) côté client
 * quand l'utilisateur n'est clairement pas connecté.
 */
export const load = ({ cookies }) => {
	if (!cookies.get('access_token') && !cookies.get('refresh_token')) {
		//  La racine n'est pas une destination : elle ne fait que trier. Rien à
		//  conserver, donc, mais l'adresse se lit à la source (#1083).
		throw redirect(302, CHEMIN_CONNEXION);
	}
	// Cookies présents → le client gère la vérification et redirige vers le tableau de bord
	return {};
};
