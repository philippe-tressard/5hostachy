#!/usr/bin/env node
// SPDX-FileCopyrightText: 2026 Philippe Tressard
// SPDX-License-Identifier: LicenseRef-5Hostachy
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
 * 🔴 Et toute `<PastilleDeroulante options={CONSTANTE}>` (24/09/2026) : depuis
 * qu'une liste de filtre se rend par ce composant, le `{#each}` vit chez lui et
 * ne nomme plus la constante — sans cette seconde lecture, le contrôle serait
 * devenu vert par cécité le jour même où il devenait nécessaire.
 * **Une exception, déclarée par la prop `tri`** : un TRI est un ordre, pas un
 * filtre — trois pastilles de tri à côté des pastilles de type se liraient
 * comme un seul filtre (arbitré par l'utilisateur, Petites annonces).
 *
 * 🔴 Il mesure AUSSI les `<select>` de formulaire depuis le 26/09/2026 (#1329) :
 * l'utilisateur a tranché, capture à l'appui — « toutes en pastilles ». Le Type
 * d'une annonce (3 valeurs) était une liste déroulante juste sous le filtre qui
 * propose les mêmes trois valeurs en pastilles. Une liste de saisie se compte
 * par ses `<option>` écrites et par les constantes qu'elle parcourt ; une liste
 * construite à la volée (lots, résidents) n'est pas jugée — sa taille ne se lit
 * pas dans le code.
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
	//  La pastille déroulante : la constante est dans `options={…}`. Un tri
	//  (prop `tri`) est l'exception déclarée — voir l'en-tête.
	const pd = /<PastilleDeroulante\b([^>]*)>/g;
	while ((m = pd.exec(source))) {
		const attrs = m[1];
		if (/(^|\s)tri(\s|=|\/|$)/.test(attrs)) continue;
		const opt = attrs.match(/options=\{([A-Z_][A-Z0-9_]*)\}/);
		if (!opt) continue; // liste construite à la volée : cardinalité non déclarée
		const n = tailles.get(opt[1]);
		if (n !== undefined && n <= seuil) {
			fautifs.push({ constante: opt[1], valeurs: n });
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

/**
 * 🔴 Un `<select>` NATIF lié à une variable de FILTRE (#1329, 26/09/2026).
 *
 * La détection ci-dessus lit la classe `filter-select` — que plus aucun écran
 * ne porte depuis `PastilleDeroulante` (24/09/2026). Elle ne voyait donc plus
 * rien, et les deux filtres de la liste des utilisateurs (Admin) sont restés des
 * listes natives repeintes à la main. Le signe qui ne dépend pas d'une classe :
 * la variable liée s'appelle un filtre. PURE.
 */
export function selectsDeFiltre(source) {
	const re = /<select\b[^>]*\bbind:value=\{([^}]*(?:[Ff]ilter|[Ff]iltre)[^}]*)\}/g;
	return [...source.matchAll(re)].map((m) => m[1].trim());
}

/**
 * Un `<select>` de SAISIE de six choix ou moins (#1329). PURE.
 * L'option vide (`value=""`, `value={null}`) ne compte pas : c'est l'absence de
 * choix, qu'une pastille « Aucune » ou « Tous » porte. Rend les tailles fautives.
 */
export function selectsCourtsDeSaisie(source, tailles, seuil = SEUIL) {
	const fautes = [];
	for (const m of source.matchAll(/<select\b[^>]*>([\s\S]*?)<\/select>/g)) {
		const corps = m[1];
		//  Une liste construite à la volée : sa taille ne se lit pas ici.
		if (/\{#each\s+(?![A-Z_][A-Z0-9_]*\b)/.test(corps)) continue;
		const constantes = [...corps.matchAll(/\{#each\s+([A-Z_][A-Z0-9_]*)\b/g)].map((x) =>
			tailles.get(x[1]),
		);
		if (constantes.some((t) => t === undefined)) continue;
		const ecrites = [
			...corps
				.replace(/\{#each[\s\S]*?\{\/each\}/g, '')
				.matchAll(/<option\b(?![^>]*value="")(?![^>]*value=\{null\})/g),
		].length;
		const n = ecrites + constantes.reduce((a, t) => a + t, 0);
		if (n > 0 && n <= seuil) fautes.push(n);
	}
	return fautes;
}

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
	//  La pastille déroulante : même seuil, et le tri seul y échappe.
	const lib3 = "export const L3 = [{ val: 'a' }, { val: 'b' }, { val: 'c' }];";
	const lib9 = `export const L9 = [${Array.from({ length: 9 }, (_, i) => `{ val: '${i}' }`).join(',')}];`;
	const t = cardinalites([lib3, lib9]);
	for (const [nom, vue, attendu] of [
		[
			'pastille déroulante, 3 valeurs → refusé',
			'<PastilleDeroulante options={L3} bind:valeur={x} />',
			1,
		],
		[
			'pastille déroulante, 9 valeurs → accepté',
			'<PastilleDeroulante options={L9} bind:valeur={x} />',
			0,
		],
		[
			'pastille déroulante de TRI, 3 valeurs → accepté',
			'<PastilleDeroulante\n\toptions={L3}\n\ttri\n/>',
			0,
		],
		[
			"« tri » dans un autre attribut n'exempte pas",
			'<PastilleDeroulante options={L3} libelle="tri" />',
			1,
		],
	]) {
		const obtenu = selectsFautifs(vue, t).length;
		const okp = obtenu === attendu;
		echecs += okp ? 0 : 1;
		console.log(`${okp ? 'PASS' : 'ÉCHEC'}  ${nom} → ${obtenu} signalement(s)`);
	}
	//  Et le contrôle doit savoir COMPTER, sinon tout passerait pour long.
	const compte = cardinalites(["export const L = [{ val: 'a' }, { val: 'b' }];"]).get('L');
	const ok2 = compte === 2;
	echecs += ok2 ? 0 : 1;
	console.log(`${ok2 ? 'PASS' : 'ÉCHEC'}  comptage d'une liste → ${compte}`);

	//  Le <select> de SAISIE court (#1329) : écrit, par constante, et à la volée.
	const t3 = cardinalites(["export const L3 = [{ val: 'a' }, { val: 'b' }, { val: 'c' }];"]);
	for (const [nom, vue, attendu] of [
		[
			'saisie, 2 options écrites + vide → refusé',
			'<select><option value="">—</option><option>a</option><option>b</option></select>',
			1,
		],
		['saisie, constante de 3 → refusé', '<select>{#each L3 as o}<option/>{/each}</select>', 1],
		[
			'saisie construite à la volée → pas jugée',
			'<select>{#each lots as l}<option/>{/each}</select>',
			0,
		],
	]) {
		const obtenu = selectsCourtsDeSaisie(vue, t3).length;
		const oks = obtenu === attendu;
		echecs += oks ? 0 : 1;
		console.log(`${oks ? 'PASS' : 'ÉCHEC'}  ${nom} → ${obtenu} signalement(s)`);
	}

	//  Le <select> natif lié à un filtre (#1329), quelle que soit sa classe.
	for (const [nom, vue, attendu] of [
		[
			'select natif lié à un filtre → refusé',
			'<select class="x" bind:value={userCompteFilter}>',
			1,
		],
		['select de filtre en français → refusé', '<select bind:value={filtreType} style="a">', 1],
		['select de SAISIE → hors portée', '<select bind:value={form.type}>', 0],
	]) {
		const obtenu = selectsDeFiltre(vue).length;
		const okf = obtenu === attendu;
		echecs += okf ? 0 : 1;
		console.log(`${okf ? 'PASS' : 'ÉCHEC'}  ${nom} → ${obtenu} signalement(s)`);
	}

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
	for (const n of selectsCourtsDeSaisie(src, tailles)) {
		ecarts.push(
			`  ${relative(SOURCE, chemin).split(sep).join('/')} — <select> de saisie à ${n} choix : ChoixPastilles`,
		);
	}
	for (const v of selectsDeFiltre(src)) {
		ecarts.push(
			`  ${relative(SOURCE, chemin).split(sep).join('/')} — <select> natif lié au filtre « ${v} » : PastilleDeroulante ou ChoixPastilles`,
		);
	}
	if (!src.includes('filter-select') && !src.includes('<PastilleDeroulante')) continue;
	selectsLus++;
	for (const f of selectsFautifs(src, tailles)) {
		ecarts.push(
			`  ${relative(SOURCE, chemin).split(sep).join('/')} — ${f.constante} (${f.valeurs} valeurs)`,
		);
	}
}

if (ecarts.length) {
	console.error(`✗ ${ecarts.length} liste(s) courte(s) rendue(s) en liste déroulante :\n`);
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
