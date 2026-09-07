import { redirect } from '@sveltejs/kit';

/**
 * Redirection serveur selon l'état de la session.
 * Évite les 2 appels API inutiles (auth.me + tryRefresh) côté client
 * quand l'utilisateur n'est clairement pas connecté.
 */
export const load = ({ cookies }) => {
	if (!cookies.get('access_token') && !cookies.get('refresh_token')) {
		throw redirect(302, '/auth/connexion');
	}
	// Cookies présents → le client gère la vérification et redirige vers le tableau de bord
	return {};
};
