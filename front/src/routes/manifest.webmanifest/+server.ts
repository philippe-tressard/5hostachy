import type { RequestHandler } from './$types';
import { NOM_SITE_PAR_DEFAUT } from '$lib/configSite';
import { lireConfigServeur } from '$lib/server/config-site';

/**
 * Le manifeste de l'application installée — servi, et non plus généré au build.
 *
 * 🔴 Il portait « 5Hostachy » en dur (`vite.config.ts`) : le nom de CETTE
 * résidence, sur l'écran d'accueil du téléphone de toute autre. Arbitré le
 * 07/10/2026 (#1725) : l'application installée porte le nom de la RÉSIDENCE,
 * celui que l'administration saisit (`site_nom`), pas celui de la plateforme.
 * Un même code servant plusieurs domaines (phase 2 du chantier multi-copropriétés)
 * ne pourrait de toute façon pas en figer un au build.
 *
 * ⚠️ `Cache-Control: no-cache`, comme le pose Caddy sur cette adresse : un nom
 * changé doit atteindre le navigateur à sa prochaine visite.
 */
export const GET: RequestHandler = async ({ fetch }) => {
	const cfg = await lireConfigServeur(fetch);
	const nom = (cfg['site_nom'] ?? '').trim() || NOM_SITE_PAR_DEFAUT;
	const manifeste = {
		name: nom,
		short_name: nom,
		description: 'Application de gestion de copropriété',
		//  Les couleurs du navigateur autour de l'application installée : celles
		//  de la charte (`--color-primary`, fond de page), que le manifeste ne
		//  peut pas lire par une variable CSS.
		theme_color: '#1E3A5F',
		background_color: '#ffffff',
		display: 'standalone',
		start_url: '/',
		icons: [
			{ src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
			{ src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
		],
	};
	return new Response(JSON.stringify(manifeste), {
		headers: {
			'Content-Type': 'application/manifest+json; charset=utf-8',
			'Cache-Control': 'no-cache, must-revalidate',
		},
	});
};
