import { redirect } from '@sveltejs/kit';
import { urlDeConnexion } from '$lib/redirection';

export const load = ({ cookies, url }) => {
	if (!cookies.get('access_token') && !cookies.get('refresh_token')) {
		// Le fragment n'arrive jamais au serveur ; le navigateur le reporte sur
		// l'URL de connexion, où `destinationApresConnexion()` le récupère.
		throw redirect(302, urlDeConnexion(url.pathname + url.search));
	}
	return {};
};
