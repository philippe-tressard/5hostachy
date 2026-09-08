#!/usr/bin/env node
/**
 *  Le libellé d'un étage ne se réécrit pas dans un écran (#835, 08/09/2026).
 *
 *  🔴 Il était écrit **six fois** dans trois écrans, en **trois rendus
 *  différents** : un lot au premier sous-sol s'affichait « -1 » sur `mon-lot`,
 *  « SS 1 » sur le profil et « -1 » sur le tableau de bord. Ce n'est pas une
 *  variante assumée — c'est ce que trois personnes ont écrit séparément en
 *  croyant chacune être seule.
 *
 *  ⚠️ **La portée fait partie du contrôle.** Il ne cherche pas « RDC » en
 *  général : le mot apparaît légitimement dans une aide, une option de sélecteur
 *  ou un commentaire. Il cherche la FORME d'une copie — une comparaison d'étage
 *  à zéro qui décide d'un texte, c'est-à-dire exactement ce que les six
 *  écritures avaient en commun.
 *
 *  Lancer : node scripts/check-etage-libelle.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';

const RACINE = 'src';
const SOURCE = 'src/lib/utils.ts';

/**  Une comparaison d'étage à zéro suivie d'un littéral : la signature exacte
 *   des six copies. `etage === 0 ? 'RDC'` et `if (x.etage === 0) parts.push(…)`
 *   la portent toutes les deux. */
const COMPARAISON = /\betage\s*(===|==)\s*0\b[^\n]{0,40}['"`]/;

/*  🔴 LA SECONDE FORME, ajoutée le 08/09/2026 quelques heures après la
 *  première — et c'est la leçon.
 *
 *  Le motif ci-dessus ne cherchait que la forme CORRIGÉE du défaut : une
 *  comparaison à zéro, c'est-à-dire une écriture qui avait DÉJÀ tenté de
 *  traiter le rez-de-chaussée. Celles qui n'avaient jamais essayé lui
 *  échappaient toutes — il en restait **six**, dont trois dans un seul
 *  fichier, et côté serveur un `if m.get("etage")` qui masque purement et
 *  simplement l'étage d'un RDC.
 *
 *  Un contrôle qui cherche ce qu'il sait déjà chercher ne trouve que ce qu'on
 *  a déjà vu. Celui-ci décrit la NOTION — « l'étage paraît dans du texte » —
 *  et non une écriture fautive connue.
 *
 *  ⚠️ `etageLabel(` est le seul appel légitime, et il est exclu par le filtre
 *  ci-dessous plutôt que par le motif : une exclusion dans une expression
 *  régulière se lit mal et se contourne sans qu'on s'en aperçoive. */
const INTERPOLATION = /[ÉéE]tage[^\n]{0,8}[{$][^\n]{0,30}\betage\b/i;

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (e.endsWith('.svelte') || e.endsWith('.ts')) acc.push(p);
	}
	return acc;
}

function fautes(source) {
	return (
		source
			.split('\n')
			.map((ligne, i) => [ligne, i + 1])
			//  Les commentaires ne posent pas de libellé — et celui qui explique ce
			//  contrôle cite justement la forme qu'il refuse.
			.filter(([l]) => !l.trim().startsWith('//') && !l.trim().startsWith('*'))
			.filter(([l]) => COMPARAISON.test(l) || (INTERPOLATION.test(l) && !/etageLabel\s*\(/.test(l)))
			.map(([, n]) => n)
	);
}

function selftest() {
	const cas = [
		["\t\t\t<dd>{lot.etage === 0 ? 'RDC' : lot.etage}</dd>", 1],
		["\t\t\tif (appt.etage === 0) parts.push('RDC');", 1],
		//  L'appel au module partagé : la forme voulue, jamais signalée.
		['\t\t\t<dd>{etageLabel(lot.etage)}</dd>', 0],
		//  Une comparaison d'étage qui ne décide PAS d'un texte — un tri, un filtre.
		['\t\t\tconst rdc = lots.filter((l) => l.etage === 0);', 0],
		//  🔴 Le contrôle ne doit pas se déclencher sur sa PROPRE prose.
		["//  `etage === 0 ? 'RDC'` est la forme refusée", 0],
	];
	let ko = 0;
	for (const [src, attendu] of cas) {
		const n = fautes(src).length;
		if (n !== attendu) {
			console.error(`  ✗ ${n} au lieu de ${attendu} : ${src.trim().slice(0, 60)}…`);
			ko++;
		}
	}
	if (ko) {
		console.error(`\n✗ Auto-test : ${ko} cas en échec.`);
		process.exit(1);
	}
	console.log('✓ Auto-test : la forme est reconnue, et elle seule.');
}

selftest();
if (process.argv.includes('--selftest')) process.exit(0);

const fautifs = [];
for (const p of fichiers(RACINE)) {
	const chemin = p.split(sep).join('/');
	if (chemin === SOURCE) continue;
	const lignes = fautes(readFileSync(p, 'utf8'));
	if (lignes.length) fautifs.push(`${chemin}:${lignes.join(',')}`);
}

if (fautifs.length) {
	console.error(`\n✗ ${fautifs.length} écran(s) réécrivent le libellé d'un étage :\n`);
	for (const f of fautifs) console.error(`  ${f}`);
	console.error(
		"\n  Il était écrit SIX fois, en trois rendus : un sous-sol s'affichait « -1 »\n" +
			'  sur un écran et « SS 1 » sur un autre.\n' +
			'  → employer `etageLabel(etage, { suffixe })` de `$lib/utils`.\n',
	);
	process.exit(1);
}
console.log("✓ Le libellé d'un étage n'est écrit qu'une fois.");
