#!/usr/bin/env node
/**
 *  Un nom d'icône écrit dans le code existe dans `$lib/icones-svg.json`
 *  (#1045, point 2).
 *
 *  ## Pourquoi ce contrôle
 *
 *  `Icon.svelte` retombe **en silence** sur `help-circle` pour un nom inconnu :
 *  l'écran affiche un point d'interrogation, la console ne dit rien, et aucun
 *  test ne le voit. `ux-patterns` §13 le signale depuis le 15/08/2026
 *  (`message-square-plus`, qui n'existait pas) et demande de « vérifier que
 *  l'icône existe » — une consigne, que personne ne relit avant d'écrire.
 *
 *  La mesure du 24/09/2026 en a trouvé une : `icone="database"` sur la section
 *  « Intégrité référentielle » de l'administration, rendue en point
 *  d'interrogation depuis sa création. Le tracé a été AJOUTÉ au catalogue
 *  (et à sa copie serveur, que `api/tests/test_icones_svg.py` tient identique).
 *
 *  ## Ce qu'il lit
 *
 *  Les noms LITTÉRAUX, sous les formes que le dépôt emploie :
 *
 *    <Icon name="…">   ·   icone="…"   ·   icone: '…'   ·   icone={'…'}
 *    icone={x.icone || '…'}                ← le repli d'un en-tête de page
 *
 *  ⚠️ Un nom CALCULÉ (`name={cond ? a : b}`, une variable) lui échappe : il ne
 *  peut pas juger ce qu'il ne lit pas. Les noms administrables (`pages.ts`) sont
 *  bien des littéraux, donc couverts.
 *
 *  Lancer : node scripts/check-icones.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const RACINE = 'src';
const CATALOGUE = 'src/lib/icones-svg.json';

const NOM = String.raw`["']([a-z0-9-]+)["']`;
const FORMES = [
	new RegExp(String.raw`<Icon\b[^>]*?\bname=${NOM}`, 'g'),
	new RegExp(String.raw`\bicone\s*[:=]\s*${NOM}`, 'g'),
	new RegExp(String.raw`\bicone=\{\s*${NOM}\s*\}`, 'g'),
	new RegExp(String.raw`\bicone\b[^\n]*?\|\|\s*${NOM}`, 'g'),
];

/**  Les noms littéraux d'une source, hors commentaires. PURE. */
export function nomsEmployes(source) {
	const code = neutraliserCommentaires(source);
	const noms = new Set();
	for (const forme of FORMES) for (const m of code.matchAll(forme)) noms.add(m[1]);
	return noms;
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const t = (libelle, source, attendus) => {
		const obtenus = [...nomsEmployes(source)].sort().join(',');
		const ok = obtenus === [...attendus].sort().join(',');
		console.log(`${ok ? 'PASS' : 'FAIL'}  ${libelle} → [${obtenus}]`);
		if (!ok) ko = 1;
	};
	t('balise Icon', '<Icon name="trash-2" size={16} />', ['trash-2']);
	t('prop icone', '<SectionFormulaire titre="x" icone="database" />', ['database']);
	t('déclaration de page', "{ id: 'faq', icone: 'help-circle' }", ['help-circle']);
	t('prop entre accolades', "<EntetePage icone={'newspaper'} />", ['newspaper']);
	t('repli d’en-tête', "<EntetePage icone={_pc.icone || 'calendar-days'} />", ['calendar-days']);
	//  Un nom calculé n'est pas lu — et ne doit pas produire un faux nom.
	t('nom calculé ignoré', '<Icon name={ouvert ? a : b} />', []);
	t('commentaire ignoré', '<!-- <Icon name="inexistant" /> -->', []);
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	process.exit(ko);
}

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (/\.(svelte|ts)$/.test(e)) acc.push(p);
	}
	return acc;
}

const catalogue = new Set(Object.keys(JSON.parse(readFileSync(CATALOGUE, 'utf8'))));
const inconnus = [];
let lus = 0;
for (const f of fichiers(RACINE)) {
	const rel = f.split(sep).join('/');
	for (const nom of nomsEmployes(readFileSync(f, 'utf8'))) {
		lus++;
		if (!catalogue.has(nom)) inconnus.push(`${rel} : « ${nom} »`);
	}
}

//  🔴 LE CAS ZÉRO (`standards/04` §2) : aucun nom lu, c'est une lecture perdue
//  — formes d'écriture changées, arborescence déplacée —, pas un dépôt conforme.
if (lus === 0 || catalogue.size === 0) {
	console.error(
		`\n✗ INCONNU : ${lus} nom(s) d’icône lu(s), ${catalogue.size} entrée(s) au catalogue.\n\n` +
			'  Le contrôle ne mesure plus rien : le mettre à jour.\n',
	);
	process.exit(2);
}

if (inconnus.length) {
	console.error(`\n✗ ${inconnus.length} icône(s) absente(s) de \`${CATALOGUE}\` :\n`);
	for (const i of inconnus) console.error(`  ${i}`);
	console.error(
		'\n  `Icon` les rend en point d’interrogation, sans rien signaler.\n' +
			'  → choisir un nom du catalogue, ou y ajouter le tracé Lucide — puis\n' +
			'    `cp front/src/lib/icones-svg.json api/app/utils/icones-svg.json`.\n',
	);
	process.exit(1);
}
console.log(
	`✓ Icônes : ${lus} emploi(s) littéral(aux), tous présents au catalogue ` +
		`(${catalogue.size} tracés).`,
);
