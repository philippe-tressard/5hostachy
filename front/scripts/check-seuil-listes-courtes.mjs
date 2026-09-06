#!/usr/bin/env node
// SPDX-FileCopyrightText: 2026 Philippe Tressard
// SPDX-License-Identifier: MIT
/**
 * Une liste COURTE qui fait choisir se rend en pastilles, pas en `<select>`.
 *
 * ## Pourquoi ce contrôle, et pourquoi maintenant
 *
 * La règle existe depuis le **29/08/2026** (`ux-patterns`, « Le seuil des listes
 * courtes »), et elle est explicite : au-delà de six entrées la liste reste ce
 * qu'elle est, en dessous elle passe en pastilles. Elle nomme même le cas qui
 * reste dehors — `CATEGORIES_ANNONCE`, neuf valeurs.
 *
 * 🔴 **Elle n'a pas été appliquée au filtre « type » des petites annonces, trois
 * valeurs, pendant huit jours.** Personne ne l'a vu : une règle écrite dans une
 * skill ne se relit pas avant de toucher un écran qu'on croit sans rapport.
 *
 * C'est le même motif que `EnteteCarte` (une carte sur six ne l'employait pas),
 * `ChoixPastilles` (trois rangées recopiées après sa création) et
 * `parse_json_perimetres` (quatre lecteurs réécrits à la main). **Le composant
 * existait, la règle existait, et rien ne les faisait appliquer.**
 *
 * ## Ce qu'il vérifie
 *
 * Tout `<select>` porteur d'une classe de filtre (`filter-select`) dont la liste
 * d'options tient sous le seuil. La cardinalité se lit sur la constante que le
 * `{#each}` parcourt, dans `src/lib/*.ts`.
 *
 * ⚠️ Il ne mesure PAS les `<select>` de formulaire — un champ de saisie n'est
 * pas un filtre, et `ux-patterns` réserve la conversion aux listes « qui font
 * choisir » dans une barre. Le seuil s'applique aussi aux champs (le type de
 * prestataire l'a montré), mais leur conversion se décide à l'écran : ce
 * contrôle-ci garde le cas net.
 *
 * Usage :  node scripts/check-seuil-listes-courtes.mjs [--selftest]
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const ICI = dirname(fileURLToPath(import.meta.url));
const SOURCE = resolve(ICI, '..', 'src');

/**  Le seuil de `ux-patterns` : six entrées ou moins → pastilles.
 *
 *   ⚠️ L'utilisateur a énoncé « ≤ 5 » le 06/09/2026. Les deux valeurs donnent le
 *   MÊME verdict sur tout le produit — aucune liste n'a cinq ni six entrées : 3
 *   (types d'annonce), 3 (tri), 4 (états d'idée), 4 (états de ticket), 9
 *   (catégories d'annonce). Le seuil écrit est conservé, avec sa justification
 *   d'origine ; le noter ici évite qu'on croie à une divergence. */
export const SEUIL = 6;

/** Les listes de valeurs déclarées dans `src/lib/*.ts`, et leur cardinalité. */
export function cardinalites(sources) {
	const tailles = new Map();
	for (const src of sources) {
		const re = /export const ([A-Z_][A-Z0-9_]*)\s*(?::[^=]+)?=\s*\[/g;
		let m;
		while ((m = re.exec(src))) {
			//  Bornage par le `];` de fin — une liste imbriquée resterait dedans, ce
			//  qui gonflerait le compte plutôt que de le sous-estimer : on préfère
			//  qu'un cas limite passe pour LONG et échappe au contrôle, plutôt que
			//  d'accuser une liste longue d'être courte.
			const fin = src.indexOf('];', m.index);
			if (fin === -1) continue;
			const corps = src.slice(m.index, fin);
			const n = (corps.match(/\b(val|value)\s*:/g) ?? []).length;
			if (n > 0) tailles.set(m[1], n);
		}
	}
	return tailles;
}

/** La décision, pure : ce `<select>` de filtre est-il sous le seuil ? */
export function selectsFautifs(source, tailles, seuil = SEUIL) {
	const fautifs = [];
	const re = /<select\b[^>]*class="[^"]*\bfilter-select\b[^"]*"[^>]*>([\s\S]*?)<\/select>/g;
	let m;
	while ((m = re.exec(source))) {
		const each = m[1].match(/\{#each\s+([A-Z_][A-Z0-9_]*)\b/);
		if (!each) continue; // options écrites en dur : cardinalité non déclarée
		const n = tailles.get(each[1]);
		if (n !== undefined && n <= seuil) {
			fautifs.push({ constante: each[1], valeurs: n });
		}
	}
	return fautifs;
}

function fichiers(dir, ext) {
	const out = [];
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) out.push(...fichiers(p, ext));
		else if (p.endsWith(ext)) out.push(p);
	}
	return out;
}

const CAS = [
	['3 valeurs en select → refusé', 3, 1],
	['6 valeurs en select → refusé (le seuil est inclusif)', 6, 1],
	['7 valeurs en select → accepté', 7, 0],
	['9 valeurs en select → accepté', 9, 0],
];

function selftest() {
	let echecs = 0;
	for (const [nom, n, attendu] of CAS) {
		const lib = `export const LISTE = [${Array.from({ length: n }, (_, i) => `{ val: '${i}', label: 'x' }`).join(',')}];`;
		const vue = `<select class="filter-select">{#each LISTE as o}<option/>{/each}</select>`;
		const obtenu = selectsFautifs(vue, cardinalites([lib])).length;
		const ok = obtenu === attendu;
		echecs += ok ? 0 : 1;
		console.log(`${ok ? 'PASS' : 'ÉCHEC'}  ${nom} → ${obtenu} signalement(s)`);
	}
	//  Cas zéro : sans constante repérée, on ne conclut rien — un `{#each}` sur une
	//  liste construite à la volée ne doit pas être accusé faute de cardinalité.
	const sansConstante = `<select class="filter-select">{#each options as o}<option/>{/each}</select>`;
	const ok = selectsFautifs(sansConstante, new Map()).length === 0;
	echecs += ok ? 0 : 1;
	console.log(`${ok ? 'PASS' : 'ÉCHEC'}  cardinalité inconnue → on ne conclut pas`);
	//  Et le contrôle doit savoir COMPTER, sinon tout passerait pour long.
	const compte = cardinalites(["export const L = [{ val: 'a' }, { val: 'b' }];"]).get('L');
	const ok2 = compte === 2;
	echecs += ok2 ? 0 : 1;
	console.log(`${ok2 ? 'PASS' : 'ÉCHEC'}  comptage d'une liste → ${compte}`);

	console.log(echecs ? `== ${echecs} ÉCHEC(S) ==` : '== TOUS OK ==');
	return echecs ? 1 : 0;
}

if (process.argv.includes('--selftest')) process.exit(selftest());

const libs = fichiers(join(SOURCE, 'lib'), '.ts').map((p) => readFileSync(p, 'utf8'));
const tailles = cardinalites(libs);
if (tailles.size === 0) {
	//  Cas zéro : sans aucune liste repérée, le contrôle serait vert par cécité.
	console.error('✗ Cas zéro : aucune liste de valeurs trouvée dans src/lib — analyse cassée.');
	process.exit(1);
}

const ecarts = [];
let selectsLus = 0;
for (const chemin of fichiers(SOURCE, '.svelte')) {
	const src = readFileSync(chemin, 'utf8');
	if (!src.includes('filter-select')) continue;
	selectsLus++;
	for (const f of selectsFautifs(src, tailles)) {
		ecarts.push(
			`  ${relative(SOURCE, chemin).split(sep).join('/')} — ${f.constante} (${f.valeurs} valeurs)`,
		);
	}
}

if (ecarts.length) {
	console.error(`✗ ${ecarts.length} liste(s) courte(s) rendue(s) en <select> :\n`);
	console.error(ecarts.join('\n'));
	console.error(
		`\n  Seuil : ${SEUIL} entrées ou moins → pastilles (\`ChoixPastilles\`),` +
			`\n  \`ux-patterns\` « Le seuil des listes courtes » (29/08/2026, #491).` +
			`\n  Au-delà, le <select> reste le bon rendu — la cardinalité choisit, pas l'écran.\n`,
	);
	process.exit(1);
}
console.log(
	`✓ Seuil des listes courtes : ${selectsLus} fichier(s) à filtres, ${tailles.size} liste(s) ` +
		`déclarée(s), aucune liste de ${SEUIL} entrées ou moins rendue en <select>.`,
);
