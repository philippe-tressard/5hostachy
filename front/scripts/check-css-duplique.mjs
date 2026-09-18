#!/usr/bin/env node
/**
 *  Garde-fou : une règle CSS ne s'écrit pas deux fois sous le même nom.
 *
 *  ## L'angle mort qu'il bouche
 *
 *  `lint:charte` compare les règles d'un écran aux classes de la CHARTE, et il le
 *  fait bien. Mais une règle dupliquée entre deux composants sous un nom qui n'est
 *  PAS dans la charte lui est **invisible** : il n'a rien à quoi la comparer.
 *
 *  C'est exactement ce qu'était `.auth-wrapper` — le nom local de ce que la charte
 *  appelle `.auth-page` —, écrit à l'identique dans les deux écrans de mot de
 *  passe et resté là pendant que deux consolidations successives (#495, #607)
 *  passaient à côté. Une copie sous un autre nom échappe à tout.
 *
 *  ## Ce qu'il mesure
 *
 *  Une règle est un doublon quand le MÊME sélecteur porte les MÊMES déclarations
 *  dans deux fichiers différents. Les déclarations sont comparées **triées** : un
 *  ordre différent ne sauve pas une copie.
 *
 *  Seuil à **3 déclarations** : en dessous, la coïncidence est banale
 *  (`display:flex; gap:.5rem` se rencontre partout) et le contrôle crierait sur du
 *  bruit — donc serait désarmé dans la semaine.
 *
 *  ## Ce qu'il ne mesure PAS, délibérément
 *
 *  Deux règles au même contenu sous des noms DIFFÉRENTS. C'est la même notion et
 *  c'est une vraie duplication, mais la nommer demande de savoir laquelle des deux
 *  est la bonne : un contrôle ne peut pas trancher ça, et il crierait sur des
 *  voisinages légitimes. Ce cas se traite à la main, avec le relevé qui a produit
 *  ce fichier.
 *
 *  🔴 Cet angle mort a repris du service le 18/09/2026, et il est désormais
 *  MESURÉ plutôt qu'affirmé. `.rich-toolbar` et `.legal-toolbar` — les barres
 *  d'outils des deux éditeurs riches — portaient les mêmes onze déclarations
 *  sous deux noms, dans deux fichiers. Ce contrôle ne pouvait pas les voir, et
 *  une seconde raison s'y ajoutait : elles avaient DÉRIVÉ, `0.85rem` contre
 *  `0.82rem` sur la taille des boutons. Une copie qui a dérivé n'est plus une
 *  copie exacte — elle échappe même à un contrôle qui chercherait le même nom.
 *
 *  Un relevé mécanique du cas général — mêmes propriétés, au plus une valeur
 *  différente, au moins cinq déclarations — rend **seize** paires sur ce dépôt,
 *  dont la plupart sont des voisinages banals (un libellé qui ressemble à un
 *  autre libellé). C'est la preuve chiffrée que ce contrôle a raison de ne pas
 *  trancher : à seize alertes dont deux vraies, il serait désarmé dans la
 *  semaine. Le relevé reste l'outil, et il se lance à la main.
 *
 *  Usage : node scripts/check-css-duplique.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..', 'src');

/** En dessous, la coïncidence est banale — voir l'en-tête. */
const SEUIL_DECLARATIONS = 3;

/**
 *  Les doublons ASSUMÉS, avec leur raison. Une entrée qui ne sert plus fait
 *  échouer ce contrôle : une exception qui survit à son objet finit par couvrir
 *  la copie suivante.
 */
const EXCEPTIONS = {};

const BLOC = /([^{}@/]+?)\{([^{}]*)\}/gs;

function fichiers(dir, acc = []) {
	for (const nom of readdirSync(dir)) {
		const p = join(dir, nom);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (nom.endsWith('.svelte') || nom.endsWith('.css')) acc.push(p);
	}
	return acc;
}

/** Les règles d'une source, en `[sélecteur, déclarations triées]`. */
export function reglesDe(source, estSvelte = false) {
	if (estSvelte) {
		const m = source.match(/<style[^>]*>(.*?)<\/style>/s);
		if (!m) return [];
		source = m[1];
	}
	source = source.replace(/\/\*.*?\*\//gs, '');
	const sorties = [];
	for (const [, sel, corps] of source.matchAll(BLOC)) {
		const selecteur = sel.replace(/\s+/g, ' ').trim();
		if (!selecteur || selecteur.startsWith('@') || /^(from|to|\d+%)$/.test(selecteur)) continue;
		const decls = corps
			.split(';')
			.map((d) => d.replace(/\s+/g, ' ').trim())
			.filter(Boolean)
			.sort();
		if (decls.length < SEUIL_DECLARATIONS) continue;
		sorties.push([selecteur, decls.join(' | ')]);
	}
	return sorties;
}

function selftest() {
	const cas = [
		//  Une règle courte n'est pas un doublon : la coïncidence est banale.
		['.a { display: flex; gap: .5rem }', 0],
		//  Trois déclarations : elle compte.
		['.a { display: flex; gap: .5rem; color: red }', 1],
		//  Une media query n'est pas un sélecteur — seule la règle qu'elle contient l'est.
		['@media (max-width: 480px) { .a { display: flex; gap: 1px; color: red } }', 1],
		//  Un commentaire qui contient des accolades ne doit rien produire.
		['/* .faux { a: 1; b: 2; c: 3 } */ .a { display: flex; gap: 1px; color: red }', 1],
	];
	let ko = 0;
	for (const [src, attendu] of cas) {
		const n = reglesDe(src).length;
		if (n !== attendu) {
			console.error(`  ✗ ${n} règle(s) au lieu de ${attendu} : ${src.slice(0, 60)}…`);
			ko++;
		}
	}
	//  🔴 Le cas qui fait tout le contrôle : deux écritures de la MÊME règle, dans
	//  un ordre différent, doivent se reconnaître. Sans lui, un simple
	//  réarrangement des lignes suffirait à masquer une copie.
	const a = reglesDe('.x { color: red; gap: 1px; display: flex }');
	const b = reglesDe('.x { display: flex; gap: 1px; color: red }');
	if (a[0]?.[1] !== b[0]?.[1]) {
		console.error('  ✗ deux écritures de la même règle ne se reconnaissent pas');
		ko++;
	}
	if (ko) {
		console.error(`\n✗ Auto-test : ${ko} cas en échec.`);
		process.exit(1);
	}
	console.log('✓ Auto-test : les règles sont reconnues, et le seuil tient.');
}

selftest();
if (process.argv.includes('--selftest')) process.exit(0);

const tous = fichiers(RACINE);
//  Cas zéro : l'arborescence a changé, le contrôle ne mesure plus rien.
if (tous.length < 50) {
	console.error(
		`✗ Cas zéro : ${tous.length} fichier(s) analysé(s), au moins 50 attendus — ` +
			'le parcours ne correspond plus à `src/`.',
	);
	process.exit(1);
}

//  ⚠️ Le séparateur s'écrit `\u0000`, il ne se TAPE pas. Il était un vrai
//  caractère NUL dans le fichier jusqu'au 13/09/2026 : même valeur à l'exécution,
//  mais invisible à la relecture. C'est la forme bénigne d'un accident qui, dans
//  `check-geste-edition`, avait transformé un `\b` en retour arrière et rendu une
//  règle entière muette — deux fois. `npm run lint:caracteres` les refuse désormais.
const parRegle = new Map();
for (const p of tous) {
	const rel = relative(RACINE, p).split(sep).join('/');
	for (const [sel, decls] of reglesDe(readFileSync(p, 'utf8'), p.endsWith('.svelte'))) {
		const cle = `${sel}\u0000${decls}`;
		if (!parRegle.has(cle)) parRegle.set(cle, new Set());
		parRegle.get(cle).add(rel);
	}
}

const doublons = [];
for (const [cle, fics] of parRegle) {
	if (fics.size < 2) continue;
	const sel = cle.split('\u0000')[0];
	if (EXCEPTIONS[sel]) continue;
	doublons.push([sel, [...fics].sort()]);
}

for (const sel of Object.keys(EXCEPTIONS)) {
	const sertEncore = [...parRegle].some(
		([cle, fics]) => cle.split('\u0000')[0] === sel && fics.size >= 2,
	);
	if (!sertEncore) {
		console.error(
			`✗ L'exception « ${sel} » ne sert plus : la règle n'est plus dupliquée. La retirer.`,
		);
		process.exit(1);
	}
}

if (doublons.length) {
	console.error(
		`\n✗ ${doublons.length} règle(s) CSS écrite(s) à l'identique dans plusieurs fichiers :\n`,
	);
	for (const [sel, fics] of doublons.sort()) {
		console.error(`  ${sel}`);
		for (const f of fics) console.error(`      ${f}`);
	}
	console.error(
		'\n  Une notion partagée par plusieurs écrans vit dans `src/styles/`, elle ne se\n' +
			'  recopie pas. Svelte scope ses styles : le second écran qui reprendra la classe\n' +
			'  héritera du balisage SANS le style — c’est la régression des pastilles nues.\n' +
			'\n  Un doublon VOULU se déclare dans `EXCEPTIONS`, avec sa raison.\n',
	);
	process.exit(1);
}

console.log(
	`✓ CSS : ${tous.length} fichiers, ${parRegle.size} règles de ${SEUIL_DECLARATIONS}+ déclarations — ` +
		`aucune écrite deux fois (${Object.keys(EXCEPTIONS).length} exception(s) nommée(s)).`,
);
