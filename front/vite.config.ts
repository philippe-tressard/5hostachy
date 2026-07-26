import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import { VitePWA } from 'vite-plugin-pwa';
import { execSync } from 'child_process';

function gitHash(): string {
	// En build Docker, VITE_GIT_HASH est injecté via ARG/ENV
	if (process.env.VITE_GIT_HASH && process.env.VITE_GIT_HASH !== 'dev') {
		return process.env.VITE_GIT_HASH;
	}
	try {
		return execSync('git rev-parse --short HEAD').toString().trim();
	} catch {
		return 'dev';
	}
}

function buildDate(): string {
	// Horodatage de build affiché dans le footer, en heure de PARIS.
	//
	// `new Date().toISOString()` est toujours en UTC : le footer annonçait
	// « 2026/07/26-08:48 » pour une MEP réellement effectuée à 10:48 (constaté le
	// 26/07/2026), soit 2 h de moins, et sans aucune mention du fuseau — donc lu
	// comme une heure locale fausse. Même classe que le bug des mois en anglais du
	// même jour : une date montrée à l'utilisateur qui ne suit pas la convention
	// Europe/Paris du projet (cf. `$lib/date.ts`).
	//
	// `formatToParts` plutôt qu'un `replace` sur une chaîne localisée : on
	// recompose explicitement, sans dépendre du format d'une locale.
	const parts = new Intl.DateTimeFormat('fr-FR', {
		timeZone: 'Europe/Paris',
		year: 'numeric', month: '2-digit', day: '2-digit',
		hour: '2-digit', minute: '2-digit', hour12: false,
	}).formatToParts(new Date());
	const p = (type: string) => parts.find((x) => x.type === type)?.value ?? '00';
	return `${p('year')}/${p('month')}/${p('day')}-${p('hour')}:${p('minute')}`;
}

export default defineConfig({
	define: {
		'import.meta.env.VITE_GIT_HASH': JSON.stringify(gitHash()),
		'import.meta.env.VITE_BUILD_DATE': JSON.stringify(buildDate()),
	},
	plugins: [
		sveltekit(),
		VitePWA({
			// `prompt` et non `autoUpdate` : en `autoUpdate`, workbox prend la main
			// (`skipWaiting` + `clientsClaim`) et la page se recharge d'elle-même dès
			// qu'une version est trouvée — un formulaire en cours de saisie serait
			// perdu sans avertissement. Ici le nouveau service worker reste en attente
			// et `$lib/components/MajDisponible.svelte` propose le rechargement.
			registerType: 'prompt',
			// Enregistrement explicite par ce même composant, qui a besoin des
			// callbacks (`onNeedRefresh`) et pose le contrôle périodique. `auto`
			// laisserait le plugin injecter en plus son propre script selon qu'il
			// détecte ou non l'import du module virtuel.
			injectRegister: null,
			strategies: 'generateSW',
			manifest: {
				name: '5Hostachy',
				short_name: '5Hostachy',
				description: 'Application de gestion de copropriété',
				theme_color: '#1E3A5F',
				background_color: '#ffffff',
				display: 'standalone',
				start_url: '/',
				icons: [
					{ src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
					{ src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
				],
			},
			workbox: {
				globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
				runtimeCaching: [
					{
						urlPattern: /^https?:\/\/.*\/api\/(lots|publications)/,
						handler: 'StaleWhileRevalidate',
						options: { cacheName: 'api-cache', expiration: { maxAgeSeconds: 60 * 60 } },
					},
				],
			},
		}),
	],
	server: {
		proxy: {
			'/api': {
				target: 'http://localhost:8000',
				changeOrigin: true,
				rewrite: (path) => path.replace(/^\/api/, ''),
			},
		},
	},
});
