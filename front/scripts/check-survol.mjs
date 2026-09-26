#!/usr/bin/env node
/**
 *  Un survol ne sert qu'à la SOURIS : il vit sous `@media (hover: hover) and
 *  (pointer: fine)` (ux-patterns §17 ; `emil-design-eng`, « Touch device hover
 *  states »). Au doigt, `:hover` RESTE COLLÉ après un appui : le bouton garde sa
 *  couleur de survol jusqu'au prochain tap ailleurs.
 *
 *  ## La dette — résorbée le jour même (26/09/2026, #1329)
 *
 *  Relevé : 90 règles `:hover` hors de ce média. Les 27 des feuilles communes
 *  puis les 62 des composants y ont été rangées (même ordre, même spécificité :
 *  un `@media` ne change ni l'un ni l'autre). Le plafond est à ZÉRO, et le reste.
 *
 *  ⚠️ Deux pièges trouvés en le faisant :
 *   • un `:focus-visible` groupé avec un `:hover` ne se range PAS avec lui — le
 *     clavier n'est pas la souris (trois cas, ressortis) ;
 *   • un survol qui RÉVÈLE un contrôle ne doit pas le cacher pour toujours au
 *     doigt : le montrer là où il n'y a pas de survol (`ImageUpload`, spinner).
 *
 *  Lancer : node scripts/check-survol.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';

//  Ce qui reste, et ne doit que baisser.
const PLAFOND = 0;

/** Les sélecteurs `:hover` hors d'un `@media (hover: hover)`. PURE. */
export function survolsNus(css) {
	const s = css.replace(/\/\*[\s\S]*?\*\//g, '');
	let n = 0;
	const pile = []; // pour chaque `{` ouvert : est-ce un média de survol ?
	let tampon = '';
	for (const c of s) {
		if (c === '{') {
			const tete = tampon.trim();
			const media = /^@media[^{]*\(\s*hover\s*:\s*hover\s*\)/.test(tete);
			const dansMedia = pile.includes(true);
			if (!tete.startsWith('@') && /:hover\b/.test(tete) && !dansMedia) {
				n += (tete.match(/:hover\b/g) ?? []).length;
			}
			pile.push(media);
			tampon = '';
		} else if (c === '}') {
			pile.pop();
			tampon = '';
		} else if (c === ';') {
			tampon = '';
		} else tampon += c;
	}
	return n;
}

function styles(source, fichier) {
	if (fichier.endsWith('.css')) return source;
	return [...source.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map((m) => m[1]).join('\n');
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const t = (libelle, attendu, css) => {
		const r = survolsNus(css);
		console.log(`${r === attendu ? 'PASS' : 'FAIL'}  ${libelle} → ${r}`);
		if (r !== attendu) ko = 1;
	};
	t('survol nu', 1, '.btn:hover { background: red; }');
	t('deux sélecteurs', 2, '.a:hover,\n.b:hover { color: red; }');
	t('sous le média', 0, '@media (hover: hover) and (pointer: fine) { .a:hover { color: red; } }');
	t('autre média', 1, '@media (max-width: 600px) { .a:hover { color: red; } }');
	t('commentaire ignoré', 0, '/* .a:hover { } */');
	t('après le média', 1, '@media (hover: hover) { .a:hover { x: 1; } } .b:hover { y: 2; }');
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	process.exit(ko);
}

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (e.endsWith('.svelte') || e.endsWith('.css')) acc.push(p);
	}
	return acc;
}

const parFichier = [];
let total = 0;
for (const f of fichiers('src')) {
	const n = survolsNus(styles(readFileSync(f, 'utf8'), f));
	if (n) parFichier.push([f.split(sep).join('/'), n]);
	total += n;
}
//  🔴 CAS ZÉRO : aucun fichier lu n'est pas « zéro survol ».
if (!parFichier.length && total === 0 && fichiers('src').length < 50) {
	console.error('\n✗ INCONNU : le contrôle ne lit plus les styles — le mettre à jour.\n');
	process.exit(2);
}
if (total > PLAFOND) {
	console.error(`\n✗ ${total} survol(s) hors de \`@media (hover: hover)\`, plafond ${PLAFOND} :\n`);
	for (const [f, n] of parFichier) console.error(`  ${f} (${n})`);
	console.error(
		'\n  → ranger le nouveau survol sous `@media (hover: hover) and (pointer: fine)`.\n',
	);
	process.exit(1);
}
if (total < PLAFOND) {
	console.error(
		`\n✗ Le plafond dit ${PLAFOND}, le dépôt en porte ${total} : l'abaisser (PLAFOND = ${total}).\n`,
	);
	process.exit(1);
}
console.log(
	`✓ Survol : ${total} règle(s) hors du média souris, au plafond — il ne fait que baisser.`,
);
