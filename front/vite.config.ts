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

export default defineConfig({
	define: {
		'import.meta.env.VITE_GIT_HASH': JSON.stringify(gitHash()),
		'import.meta.env.VITE_BUILD_DATE': JSON.stringify(new Date().toISOString().slice(0, 16).replace(/^(\d{4})-(\d{2})-(\d{2})T/, '$1/$2/$3-')),
	},
	plugins: [
		sveltekit(),
		VitePWA({
			registerType: 'autoUpdate',
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
