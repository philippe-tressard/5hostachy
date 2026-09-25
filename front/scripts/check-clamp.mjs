#!/usr/bin/env node
/**
 *  La troncature d'un aperçu vit dans `styles/normes.css`, et une CARTE tronque
 *  à trois lignes (#1045, point 2).
 *
 *  ## Pourquoi ce contrôle
 *
 *  `ux-patterns` §7 et la checklist de `CLAUDE.md` posent la règle :
 *
 *    `.clamp-3` → l'aperçu d'une carte de liste · `.clamp-5` → un bloc
 *    expansible qui n'est pas une carte · `.clamp-2` → un titre de carte.
 *
 *  Elle a déjà été enfreinte de la façon la plus ordinaire : `.clamp-3` était
 *  écrit à la main dans `FluxCard`, et c'est lui qui a servi de référence le
 *  18/09/2026 ; l'audit du 19/09 a relevé trois écarts de plus, corrigés depuis
 *  à la main. Rien ne les empêchait de revenir.
 *
 *  ## Ce qu'il refuse
 *
 *   1. une propriété `line-clamp` écrite ailleurs que dans `styles/normes.css` —
 *      c'est une quatrième classe de troncature qui naît ;
 *   2. `clamp-5` dans un fichier qui rend une `.carte-liste` — l'aperçu d'une
 *      carte fait trois lignes, validé à l'écran (densité « F1 », §3).
 *   3. un SOUS-TEXTE déclaré dans `SOUS_TEXTES` qui ne porte pas `.clamp-3`,
 *      ou qui a disparu. Le sous-libellé d'une vignette de catégorie faisait
 *      quatre lignes (#1310, 25/09/2026) : raccourcir le texte ne suffit pas,
 *      la retouche suivante l'aurait rallongé.
 *
 *  ⚠️ Il ne vérifie pas qu'un bloc HORS carte emploie `clamp-5` plutôt que
 *  rien : « ce texte est un aperçu » ne se lit pas dans le balisage.
 *
 *  Lancer : node scripts/check-clamp.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const RACINE = 'src';
const SOURCE = 'styles/normes.css';
const CLASSES = ['clamp-2', 'clamp-3', 'clamp-5'];

const PROPRIETE = /(?:-webkit-)?line-clamp\s*:/;
const CARTE = /class="[^"]*\bcarte-liste\b|class:carte-liste/;
const CINQ_LIGNES = /\bclamp-5\b/;

/**  Le verdict d'un fichier, PUR.
 *   @returns {'ok'|'propriete-recopiee'|'carte-a-cinq-lignes'} */
export function verdictFichier(rel, source) {
	const code = neutraliserCommentaires(source);
	if (rel !== SOURCE && PROPRIETE.test(code)) return 'propriete-recopiee';
	if (CARTE.test(code) && CINQ_LIGNES.test(code)) return 'carte-a-cinq-lignes';
	return 'ok';
}

/**  Les sous-textes qui se coupent à trois lignes : fichier → classe. Une entrée
 *   dont la classe a disparu fait échouer — elle ne garderait plus rien. */
const SOUS_TEXTES = { 'lib/components/Pastille.svelte': 'pastille-detail' };

/**  Chaque `class="<classe> …"` du fichier porte-t-il `clamp-3` ? PUR.
 *   @returns {'ok'|'non-tronque'|'absent'} */
export function verdictSousTexte(source, classe) {
	const code = neutraliserCommentaires(source);
	const attributs = [...code.matchAll(/class="([^"]*)"/g)]
		.map((m) => m[1].split(/\s+/))
		.filter((c) => c.includes(classe));
	if (!attributs.length) return 'absent';
	return attributs.every((c) => c.includes('clamp-3')) ? 'ok' : 'non-tronque';
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const t = (libelle, attendu, rel, src) => {
		const r = verdictFichier(rel, src);
		console.log(`${r === attendu ? 'PASS' : 'FAIL'}  ${libelle} → ${r}`);
		if (r !== attendu) ko = 1;
	};
	//  🔴 L'état exact de `FluxCard` avant le 18/09/2026.
	t(
		'troncature écrite dans un composant',
		'propriete-recopiee',
		'lib/components/X.svelte',
		'<style>.x { -webkit-line-clamp: 3; }</style>',
	);
	t('la source elle-même', 'ok', SOURCE, '.clamp-3 { -webkit-line-clamp: 3; }');
	t(
		'carte à cinq lignes',
		'carte-a-cinq-lignes',
		'lib/components/C.svelte',
		'<div class="carte-liste"><p class="clamp-5">x</p></div>',
	);
	t('carte à trois lignes', 'ok', 'c.svelte', '<div class="carte-liste"><p class="clamp-3">x</p>');
	t(
		'bloc hors carte à cinq lignes',
		'ok',
		'l.svelte',
		'<div class="idee"><p class="clamp-5">x</p>',
	);
	t('commentaire ignoré', 'ok', 'k.svelte', '<style>/* -webkit-line-clamp: 3 */</style>');
	const u = (libelle, attendu, src) => {
		const r = verdictSousTexte(src, 'pastille-detail');
		if (r === attendu) console.log(`PASS  ${libelle} → ${r}`);
		else {
			console.error(`FAIL  ${libelle}  attendu=${attendu} obtenu=${r}`);
			ko = 1;
		}
	};
	u('sous-texte tronqué', 'ok', '<span class="pastille-detail clamp-3">x</span>');
	//  🔴 L'état d'avant #1310 : la vignette « Sinistre » tenait sur quatre lignes.
	u('sous-texte libre', 'non-tronque', '<span class="pastille-detail">x</span>');
	u(
		'un sur deux tronqué',
		'non-tronque',
		'<span class="pastille-detail clamp-3">a</span><span class="pastille-detail">b</span>',
	);
	u('classe disparue', 'absent', '<span class="autre">x</span>');
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	process.exit(ko);
}

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (/\.(svelte|css)$/.test(e)) acc.push(p);
	}
	return acc;
}

//  🔴 LE CAS ZÉRO (`standards/04` §2) : la source doit définir les trois
//  classes. Sinon ce contrôle vérifie qu'on ne recopie pas une règle… absente.
const normes = neutraliserCommentaires(readFileSync(join(RACINE, SOURCE), 'utf8'));
const manquantes = CLASSES.filter((c) => !new RegExp(String.raw`\.${c}\b`).test(normes));
if (manquantes.length || !PROPRIETE.test(normes)) {
	console.error(
		`\n✗ INCONNU : \`${SOURCE}\` ne définit plus ${manquantes.join(', ') || 'line-clamp'}.\n\n` +
			'  La source de la troncature a bougé : mettre ce contrôle à jour.\n',
	);
	process.exit(2);
}

const fautes = { 'propriete-recopiee': [], 'carte-a-cinq-lignes': [] };
for (const f of fichiers(RACINE)) {
	const rel = f
		.split(sep)
		.join('/')
		.replace(/^src\//, '');
	const v = verdictFichier(rel, readFileSync(f, 'utf8'));
	if (v !== 'ok') fautes[v].push(rel);
}

let echec = false;
for (const [rel, classe] of Object.entries(SOUS_TEXTES)) {
	const v = verdictSousTexte(readFileSync(join(RACINE, rel), 'utf8'), classe);
	if (v === 'ok') continue;
	echec = true;
	console.error(
		v === 'absent'
			? `
✗ \`${rel}\` ne rend plus \`.${classe}\` : retirer l’entrée de \`SOUS_TEXTES\`.
`
			: `
✗ \`${rel}\` : \`.${classe}\` sans \`.clamp-3\` — un sous-texte se coupe à trois lignes (#1310).
`,
	);
}
if (fautes['propriete-recopiee'].length) {
	echec = true;
	console.error('\n✗ Troncature écrite hors de `styles/normes.css` :\n');
	for (const f of fautes['propriete-recopiee']) console.error(`  ${f}`);
	console.error(
		'\n  Employer `.clamp-2` (titre), `.clamp-3` (aperçu de carte) ou `.clamp-5`\n' +
			'  (bloc hors carte). Une quatrième troncature se décide dans `normes.css`.\n',
	);
}
if (fautes['carte-a-cinq-lignes'].length) {
	echec = true;
	console.error('\n✗ Carte de liste tronquée à cinq lignes :\n');
	for (const f of fautes['carte-a-cinq-lignes']) console.error(`  ${f}`);
	console.error(
		'\n  L’aperçu d’une carte fait trois lignes (`.clamp-3`, par `ApercuCarte`) —\n' +
			'  `ux-patterns` §3 et §7. `.clamp-5` est réservé à ce qui n’est pas une carte.\n',
	);
}
if (echec) process.exit(1);
console.log(
	'✓ Troncature : écrite dans `normes.css` seul, aucune carte à cinq lignes, ' +
		`${Object.keys(SOUS_TEXTES).length} sous-texte(s) à trois lignes.`,
);
