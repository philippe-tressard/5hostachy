import adapter from '@sveltejs/adapter-node';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),
	kit: {
		adapter: adapter({
			out: 'build',
			precompress: true,
		}),
		alias: {
			$lib: 'src/lib',
		},
		//  🔒 CSP — `script-src` en mode BLOQUANT, ce que Caddy ne pouvait pas faire (#770).
		//
		//  SvelteKit sert DEUX scripts inline par page (hydratation) : ils
		//  totalisaient 370 des 404 violations du relevé. Poser `script-src 'self'`
		//  dans le Caddyfile aurait rendu le site blanc — seul le framework connaît
		//  le contenu de ses scripts, donc seul lui peut en calculer le condensat.
		//
		//  Mode `hash` et non `nonce` : un nonce doit être unique par réponse, ce
		//  qui interdit toute mise en cache de la page. Les condensats, eux, sont
		//  déterministes par build et traversent le cache Cloudflare.
		csp: {
			mode: 'hash',
			directives: {
				'script-src': ['self'],
			},
		},
	},
};

export default config;
