import { lireConfigServeur } from '$lib/server/config-site';

/**
 * Pré-charge la configuration du site côté serveur (SSR).
 * Les données sont sérialisées dans le HTML → zéro requête réseau côté client au premier rendu.
 * En développement local sans PUBLIC_API_URL, on retourne {} et le client prend le relais.
 */
export const load = async ({ fetch }) => ({ siteConfig: await lireConfigServeur(fetch) });
