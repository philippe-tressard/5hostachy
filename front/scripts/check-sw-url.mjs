#!/usr/bin/env node
/**
 * Garde-fou : le service worker doit s'enregistrer depuis une URL ABSOLUE.
 *
 * Le 26/07/2026 (v2.24.0), `vite-plugin-pwa` a hérité du `base` de Vite — vide sous
 * SvelteKit — et a généré `new Workbox('./sw.js', { scope: './' })`. Un chemin
 * relatif est résolu par rapport à la page courante : depuis `/auth/connexion`, le
 * navigateur demandait `/auth/sw.js`, recevait un 404 et abandonnait. Résultat en
 * production : PLUS AUCUN service worker enregistré sur les routes autres que la
 * racine — ni cache hors ligne, ni bandeau de mise à jour — sans la moindre trace,
 * l'erreur n'étant remontée qu'à un `onRegisterError` qu'on ne branchait pas.
 *
 * Ce contrôle porte sur le BUNDLE CONSTRUIT et non sur `vite.config.ts` : c'est
 * l'artefact livré qui compte, et la valeur fautive venait justement d'un défaut du
 * plugin, pas d'une ligne écrite à la main. Une option renommée, un changement de
 * défaut ou une régression amont seraient tous attrapés ici.
 *
 * Les points 1 à 6 du post-check MEP étaient au vert ce jour-là ; seule la
 * vérification du comportement réel (P7) a levé le lièvre. Ce script en automatise
 * la partie mécanique.
 *
 * Script Node sans dépendance, comme `check-dates.mjs`.
 *
 * Usage : npm run build && npm run lint:sw   (exit 1 si violation)
 */
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..');
const CLIENT = join(RACINE, 'build', 'client');

if (!existsSync(CLIENT)) {
	console.error(
		`\n✗ ${relative(RACINE, CLIENT)} est introuvable — lancer \`npm run build\` avant ce contrôle.` +
			`\n  Un contrôle qui ne peut pas s'exécuter renvoie INCONNU, jamais OK.\n`,
	);
	process.exit(1);
}

/** `new Workbox('./sw.js'…)`, `register('sw.js'…)`, `scope: './'` — tout ce qui est relatif. */
const MOTIFS_RELATIFS = [
	/new\s+\w+\(\s*["']\.\/sw\.js["']/,
	/new\s+\w+\(\s*["']sw\.js["']/,
	/serviceWorker\.register\(\s*["']\.?\/?sw\.js["']/,
	/scope\s*:\s*["']\.\/["']/,
];

function collecter(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) collecter(p, acc);
		else if (e.endsWith('.js')) acc.push(p);
	}
	return acc;
}

const fichiers = collecter(CLIENT);
const fautifs = [];
let absoluTrouve = false;

for (const p of fichiers) {
	const contenu = readFileSync(p, 'utf-8');
	if (!contenu.includes('sw.js')) continue;
	const rel = relative(RACINE, p).replace(/\\/g, '/');
	if (/["']\/sw\.js["']/.test(contenu)) absoluTrouve = true;
	for (const motif of MOTIFS_RELATIFS) {
		const m = contenu.match(motif);
		if (m) fautifs.push(`  ${rel}\n      ${m[0]}`);
	}
}

if (fautifs.length > 0) {
	console.error(
		`\n✗ ${fautifs.length} enregistrement(s) de service worker en chemin relatif :\n\n` +
			fautifs.join('\n') +
			`\n\n  Un chemin relatif est résolu depuis la page courante : l'enregistrement` +
			`\n  échoue en 404 sur toute route imbriquée (/auth/sw.js, /tickets/sw.js…).` +
			`\n  Corriger via les options \`base: '/'\` et \`scope: '/'\` de VitePWA.\n`,
	);
	process.exit(1);
}

if (!absoluTrouve) {
	console.error(
		`\n✗ Aucune référence à '/sw.js' dans le bundle : l'enregistrement du service` +
			`\n  worker a disparu du build. Sans lui, ni cache hors ligne ni bandeau de` +
			`\n  mise à jour — et rien ne le signalerait à l'exécution.\n`,
	);
	process.exit(1);
}

// ── Repli de navigation vers un fichier qui n'existe pas ──────────────────────
//
// `vite-plugin-pwa` suppose une SPA et pose par défaut `navigateFallback:
// 'index.html'` : le service worker répond alors à CHAQUE navigation en servant
// cet `index.html` depuis son precache. SvelteKit en `adapter-node` rend les
// pages côté serveur et n'en produit aucun — workbox lève donc
// `non-precached-url :: [{"url":"index.html"}]`, la navigation cliente échoue et
// l'hydratation ne se termine pas.
//
// Constaté en production le 14/08/2026, signalé par l'utilisateur : sur /profil
// rechargée directement, prénom, nom et e-mail restaient VIDES — et « Enregistrer »
// aurait écrasé les vraies valeurs par du vide. Le défaut est intermittent (il
// dépend de l'état du cache et du chemin d'arrivée), ce qui explique qu'il ait
// traversé tous les post-checks : ils regardaient la racine, où le repli tombe
// juste. Il n'a été trouvé que par la console du navigateur, sur la page fautive.
//
// Le contrôle porte, comme celui du dessus, sur l'ARTEFACT construit : la valeur
// fautive vient d'un défaut du plugin, pas d'une ligne écrite à la main.
const SW = join(CLIENT, 'sw.js');
if (!existsSync(SW)) {
	console.error(
		`\n✗ ${relative(RACINE, SW)} est introuvable — le service worker n'a pas été généré.` +
			`\n  Un contrôle qui ne peut pas s'exécuter renvoie INCONNU, jamais OK.\n`,
	);
	process.exit(1);
}

const sw = readFileSync(SW, 'utf-8');
const repli = sw.match(/createHandlerBoundToURL\(\s*["']([^"']+)["']\s*\)/);
if (repli) {
	const cible = repli[1];
	//  Le repli n'est acceptable que si sa cible est RÉELLEMENT précachée.
	const precachee = new RegExp(`["']url["']\\s*:\\s*["']${cible.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}["']`).test(sw)
		|| new RegExp(`["']${cible.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}["']\\s*,\\s*["']revision["']`).test(sw);
	if (!precachee) {
		console.error(
			`\n✗ Le service worker replie les navigations sur « ${cible} », qui n'est PAS` +
				`\n  dans son precache. Workbox lèvera \`non-precached-url\` à chaque` +
				`\n  navigation : la page se charge, l'hydratation échoue, et les formulaires` +
				`\n  restent vides sans le moindre message côté serveur.` +
				`\n\n  SvelteKit rend les pages côté serveur : poser \`navigateFallback: null\`` +
				`\n  dans les options \`workbox\` de VitePWA (front/vite.config.ts).\n`,
		);
		process.exit(1);
	}
}

// ── Mise en cache d'une réponse d'API authentifiée ────────────────────────────
//
// Le service worker servait `/api/lots` et `/api/publications` en
// `StaleWhileRevalidate` pendant une heure. Les deux exigent `get_current_user`
// et leur contenu est filtré par utilisateur et par périmètre : ce cache
// contenait donc des réponses authentifiées et personnalisées.
//
// `StaleWhileRevalidate` rend le cache D'ABORD et revalide après, en arrière-plan.
// Une session expirée continuait d'afficher du contenu applicatif complet, et
// c'est la revalidation — après le rendu — qui prenait le 401 : l'écran affirmait
// une session qui n'existait plus (#379, signalé le 16/08/2026). Rien ne purgeait
// ce cache à la déconnexion ni à l'expiration, si bien que le piège se réarmait
// tout seul à chaque fois.
//
// Le contrôle porte sur le SW CONSTRUIT et non sur `vite.config.ts` : c'est
// l'artefact livré qui compte, et `runtimeCaching` peut revenir d'un défaut de
// plugin ou d'un changement de défaut amont autant que d'une ligne écrite à la
// main — exactement comme le repli de navigation ci-dessus.
//
// Ce qui reste légitime : le precache des ressources STATIQUES (js, css, icônes,
// polices), qui ne porte aucune donnée d'utilisateur.
const MOTIFS_CACHE_API = [
	{ motif: /["']api-cache["']/, quoi: `le cache nommé « api-cache »` },
	{ motif: /\\?\/api\\?\/[a-z]/i, quoi: `une route /api/ référencée par le service worker` },
];

const cacheApi = MOTIFS_CACHE_API.map(({ motif, quoi }) => {
	const m = sw.match(motif);
	return m ? `  ${quoi}\n      ${m[0]}` : null;
}).filter(Boolean);

if (cacheApi.length > 0) {
	console.error(
		`\n✗ Le service worker met en cache des réponses d'API :\n\n` +
			cacheApi.join('\n') +
			`\n\n  /api/lots et /api/publications exigent une session et sont filtrés par` +
			`\n  utilisateur : les mettre en cache fait afficher du contenu applicatif à` +
			`\n  une session expirée, la revalidation ne prenant le 401 qu'APRÈS le rendu.` +
			`\n  Rien ne purge ce cache à la déconnexion — le piège se réarme seul.` +
			`\n\n  Retirer l'entrée \`runtimeCaching\` des options \`workbox\` de VitePWA` +
			`\n  (front/vite.config.ts). Le precache des ressources statiques n'est pas` +
			`\n  concerné.\n`,
	);
	process.exit(1);
}

console.log(
	`✓ ${fichiers.length} fichiers du bundle analysés — service worker en URL absolue, ` +
		`sans repli de navigation orphelin, sans cache de réponse d'API.`,
);
