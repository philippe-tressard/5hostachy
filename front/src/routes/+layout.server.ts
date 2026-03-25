import { env } from '$env/dynamic/public';

/**
 * Pré-charge la configuration du site côté serveur (SSR).
 * Les données sont sérialisées dans le HTML → zéro requête réseau côté client au premier rendu.
 * En développement local sans PUBLIC_API_URL, on retourne {} et le client prend le relais.
 */
export const load = async ({ fetch }) => {
	const apiBase = env.PUBLIC_API_URL;
	if (!apiBase) return { siteConfig: {} };
	try {
		const r = await fetch(`${apiBase}/config`);
		if (r.ok) return { siteConfig: await r.json() };
	} catch { /* réseau indisponible : le client chargera la config */ }
	return { siteConfig: {} };
};
