#!/usr/bin/env node
// SPDX-FileCopyrightText: 2026 Philippe Tressard
// SPDX-License-Identifier: MIT
/**
 * Le lien d'évitement clavier tient à QUATRE pièces, et aucune ne voit les autres.
 *
 * ## Pourquoi ce contrôle
 *
 * #778 a posé « Aller au contenu » dans le squelette de l'application (WCAG
 * 2.4.1) : une seule ligne, dans un seul fichier, qui épargne au clavier la
 * traversée du menu à chaque page.
 *
 * 🔴 **Un lien d'évitement échoue en silence de quatre façons différentes**, et
 * aucune ne se voit à la relecture du fichier où elle se produit :
 *
 * | Ce qui casse | Symptôme |
 * |---|---|
 * | le lien disparaît | le clavier retraverse le menu — rien ne change à l'œil |
 * | l'ancre ne correspond à aucun `id` | Tab montre le lien, Entrée ne fait rien |
 * | la cible perd `tabindex="-1"` | le focus ne s'y pose pas : un `<main>` n'est pas focusable |
 * | le CSS ne le ramène plus au focus | il reste à `-9999px`, donc invisible et inatteignable |
 *
 * Les deux derniers sont les plus traîtres : le lien EST là, le HTML est correct,
 * et la fonctionnalité ne marche pas. C'est exactement le mode d'échec du bandeau
 * PWA de la v2.24.0 — artefacts corrects, comportement mort.
 *
 * ⚠️ Ce contrôle vérifie la **cohérence des quatre pièces**, pas le comportement :
 * seul un navigateur, une fois connecté, prouve que Tab puis Entrée déplacent
 * vraiment le focus. Il ne remplace pas ce coup d'œil — il garantit que ce qui a
 * été vu une fois ne se défera pas sans que personne le sache.
 *
 * Usage :  node scripts/check-lien-evitement.mjs [--selftest]
 */
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ICI = dirname(fileURLToPath(import.meta.url));
const LAYOUT = resolve(ICI, '..', 'src/routes/(app)/+layout.svelte');
//  Le squelette RACINE : il précède celui de `(app)` dans le DOM, donc au
//  clavier. Ce qu'il monte avant le `<slot />` passe AVANT le lien d'évitement.
const RACINE_LAYOUT = resolve(ICI, '..', 'src/routes/+layout.svelte');
const FEUILLE = resolve(ICI, '..', 'src/styles/socle.css');

/** La décision, pure : ces deux sources portent-elles un lien d'évitement qui marche ? */
export function verdict(layout, css) {
	const manques = [];

	const lien = layout.match(/<a[^>]*class="[^"]*lien-evitement[^"]*"[^>]*href="#([\w-]+)"/);
	if (!lien) {
		manques.push('aucun lien `.lien-evitement` avec un `href="#ancre"` dans le squelette (app)');
		return manques; // sans lui, les trois autres questions n'ont pas d'objet
	}

	const ancre = lien[1];
	//  La cible doit exister DANS LE MÊME squelette : une ancre qui pointe vers un
	//  id posé par une page ne vaudrait que sur cette page-là.
	const cible = layout.match(new RegExp(`<(\\w+)([^>]*\\bid="${ancre}"[^>]*)>`));
	if (!cible) {
		manques.push(`le lien vise \`#${ancre}\`, mais aucun \`id="${ancre}"\` dans le squelette`);
	} else if (!/\btabindex="-1"/.test(cible[2])) {
		manques.push(
			`\`#${ancre}\` n'a pas \`tabindex="-1"\` : un \`<${cible[1]}>\` n'est pas focusable, ` +
				'et le saut ne déplacerait pas le focus',
		);
	}

	//  Le CSS : sorti de l'écran au repos, ramené au focus. Les deux règles
	//  comptent — la première seule le rendrait invisible pour toujours.
	const repos = css.match(/\.lien-evitement\s*\{([^}]*)\}/);
	const focus = css.match(/\.lien-evitement:focus\s*\{([^}]*)\}/);
	if (!repos) manques.push('aucune règle `.lien-evitement` dans la feuille de socle');
	else if (!/position:\s*absolute|position:\s*fixed/.test(repos[1]))
		manques.push('`.lien-evitement` sans positionnement : il pousserait la page au repos');
	if (!focus) {
		manques.push(
			'aucune règle `.lien-evitement:focus` : le lien resterait hors de l’écran, ' +
				'donc invisible ET inatteignable',
		);
	}

	return manques;
}

/**  Cinquième pièce : rien de focusable ne doit précéder le lien.
 *
 * 🔴 `MajDisponible` était monté AVANT le `<slot />` du squelette racine, et il
 * porte deux boutons. Le premier Tab atteignait donc le bandeau de mise à jour
 * au lieu de « Aller au contenu » — **seulement quand une version était
 * disponible**, donc un défaut intermittent : celui qu'on ne reproduit jamais au
 * moment où on le cherche (06/09/2026).
 *
 * Les deux composants sont en `position: fixed` : les descendre après le
 * `<slot />` ne change rien à l'écran, et rend au clavier son premier arrêt.
 *
 * ⚠️ Le contrôle ne lit pas « ce qui est focusable » — il lit **ce qui est monté
 * avant le `<slot />`**. C'est plus grossier et plus sûr : un composant peut
 * devenir focusable sans que son nom change.
 */
export function verdictRacine(racine) {
	const slot = racine.indexOf('<slot');
	if (slot === -1) return ['le squelette racine ne rend pas de `<slot />` — analyse impossible'];
	const avant = racine.slice(0, slot);
	const composants = [...avant.matchAll(/<([A-Z]\w+)\b[^>]*\/?>/g)].map((m) => m[1]);
	if (composants.length === 0) return [];
	return [
		`${composants.join(', ')} monté(s) AVANT le <slot /> du squelette racine : ` +
			"ils précèdent le lien d'évitement au clavier. Les descendre après — " +
			"leur position à l'écran n'en dépend pas s'ils sont en `position: fixed`.",
	];
}

const CAS = [
	[
		'squelette complet',
		'<a class="lien-evitement" href="#contenu">Aller au contenu</a><main class="app-main" id="contenu" tabindex="-1">',
		'.lien-evitement { position: absolute; left: -9999px; } .lien-evitement:focus { left: 0; }',
		0,
	],
	[
		'lien absent',
		'<main class="app-main" id="contenu" tabindex="-1">',
		'.lien-evitement { position: absolute; } .lien-evitement:focus { left: 0; }',
		1,
	],
	[
		'ancre sans cible',
		'<a class="lien-evitement" href="#contenu">x</a><main id="autre" tabindex="-1">',
		'.lien-evitement { position: absolute; } .lien-evitement:focus { left: 0; }',
		1,
	],
	[
		'cible sans tabindex : le focus ne s’y pose pas',
		'<a class="lien-evitement" href="#contenu">x</a><main id="contenu">',
		'.lien-evitement { position: absolute; } .lien-evitement:focus { left: 0; }',
		1,
	],
	[
		'pas de règle :focus : invisible pour toujours',
		'<a class="lien-evitement" href="#contenu">x</a><main id="contenu" tabindex="-1">',
		'.lien-evitement { position: absolute; left: -9999px; }',
		1,
	],
	[
		'pas de positionnement : il pousserait la page',
		'<a class="lien-evitement" href="#contenu">x</a><main id="contenu" tabindex="-1">',
		'.lien-evitement { left: -9999px; } .lien-evitement:focus { left: 0; }',
		1,
	],
	['cas zéro : sources vides', '', '', 1],
];

function selftest() {
	let echecs = 0;
	for (const [nom, layout, css, attendu] of CAS) {
		const obtenu = verdict(layout, css).length;
		const ok = attendu === 0 ? obtenu === 0 : obtenu >= 1;
		if (!ok) echecs++;
		console.log(`${ok ? 'PASS' : 'ÉCHEC'}  ${nom} → ${obtenu} manque(s)`);
	}
	for (const [nom, racine, attendu] of [
		['racine : rien avant le slot', `<slot />\n<Toast />`, 0],
		['racine : un composant avant le slot', `<MajDisponible />\n<slot />`, 1],
		['racine : deux composants avant', `<Toast />\n<MajDisponible />\n<slot />`, 1],
		['racine sans slot : on ne conclut pas vert', `<Toast />`, 1],
	]) {
		const obtenu = verdictRacine(racine).length;
		const ok = attendu === 0 ? obtenu === 0 : obtenu >= 1;
		if (!ok) echecs++;
		console.log(`${ok ? 'PASS' : 'ÉCHEC'}  ${nom} → ${obtenu} manque(s)`);
	}

	console.log(echecs ? `== ${echecs} ÉCHEC(S) ==` : '== TOUS OK ==');
	return echecs ? 1 : 0;
}

if (process.argv.includes('--selftest')) process.exit(selftest());

const manques = [
	...verdict(readFileSync(LAYOUT, 'utf8'), readFileSync(FEUILLE, 'utf8')),
	...verdictRacine(readFileSync(RACINE_LAYOUT, 'utf8')),
];
if (manques.length) {
	console.error('❌ Le lien d’évitement clavier ne fonctionnerait pas (#778) :');
	for (const m of manques) console.error(`   • ${m}`);
	process.exit(1);
}
console.log('✅ Lien d’évitement : lien, ancre, cible focusable et bascule au focus.');
