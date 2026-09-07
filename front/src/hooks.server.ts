import type { Handle } from '@sveltejs/kit';

export const handle: Handle = async ({ event, resolve }) => {
	// L'authentification est gérée côté client via cookies HttpOnly.
	// Le serveur SvelteKit n'inspecte pas les tokens directement.
	// La protection des routes se fait dans +page.server.ts de chaque section.
	return resolve(event);
};
