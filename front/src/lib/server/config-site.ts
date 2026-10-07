import { env } from '$env/dynamic/public';

/**
 * La configuration du site, lue CÔTÉ SERVEUR (rendu SSR) — une seule écriture.
 *
 * Deux lecteurs : le layout racine, qui la sérialise dans la page (zéro requête
 * au premier rendu), et le manifeste de l'application installée, qui y lit le
 * nom de la résidence (#1725). Le second aurait recopié le premier.
 *
 * Sans `PUBLIC_API_URL` (poste de développement) ou sans réponse de l'API, rend
 * `{}` : le client prend le relais, et le manifeste se replie sur le nom neutre.
 */
export async function lireConfigServeur(
	fetch: typeof globalThis.fetch,
): Promise<Record<string, string>> {
	const apiBase = env.PUBLIC_API_URL;
	if (!apiBase) return {};
	try {
		const r = await fetch(`${apiBase}/config`);
		if (r.ok) return await r.json();
	} catch {
		/* réseau indisponible : le client chargera la config */
	}
	return {};
}
