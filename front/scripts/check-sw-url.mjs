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

console.log(`✓ ${fichiers.length} fichiers du bundle analysés — service worker enregistré en URL absolue.`);
