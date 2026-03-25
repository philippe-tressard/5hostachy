import { redirect } from '@sveltejs/kit';

export const load = ({ cookies }) => {
	if (!cookies.get('access_token') && !cookies.get('refresh_token')) {
		throw redirect(302, '/auth/connexion');
	}
	return {};
};
