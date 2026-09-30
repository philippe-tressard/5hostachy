#!/usr/bin/env node
/**
 *  Le libellé du TYPE d'un lot ne se réécrit pas dans un écran (#779, 30/09/2026).
 *
 *  🔴 `$lib/utils` exportait déjà `lotTypeLabel`, et `mon-lot` l'importait — mais
 *  le même libellé était recalculé À LA MAIN six fois (cinq dans `mon-lot`, une
 *  dans `OngletGestionLocative`) : `type.replace('_', ' ')` suivi de
 *  `type_appartement`. Les deux écritures divergeaient déjà : la fonction rendait
 *  `local_commercial` brut et taisait le « T3 », les copies non.
 *
 *  La fonction a été ENRICHIE de ce que traitaient les copies (`lotTypeComplet`),
 *  et ce contrôle refuse la septième : la FORME d'une copie, c'est-à-dire le
 *  remplacement du soulignement d'un champ `type` / `lot_type`. Un `replace('_')`
 *  sur une autre valeur n'est pas concerné.
 *
 *  Lancer : node scripts/check-type-lot.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';

const RACINE = 'src';
const SOURCE = 'src/lib/utils.ts';

/**  `lot.type.replace('_', ' ')`, `monBailData.lot_type.replace(/_/g, ' ')`… :
 *   le soulignement d'un TYPE de lot remplacé à la main. */
const COPIE = /\b(?:lot_)?type\s*\.\s*replace(?:All)?\(\s*(?:['"`]_['"`]|\/_\/g?)/;

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (e.endsWith('.svelte') || e.endsWith('.ts')) acc.push(p);
	}
	return acc;
}

export function fautes(source) {
	return (
		source
			.split('\n')
			.map((ligne, i) => [ligne, i + 1])
			//  Un commentaire ne pose pas de libellé — celui-ci cite la forme refusée.
			.filter(([l]) => !l.trim().startsWith('//') && !l.trim().startsWith('*'))
			.filter(([l]) => COPIE.test(l))
			.map(([, n]) => n)
	);
}

function selftest() {
	const cas = [
		["\t\t\t\t>{lot.type.replace('_', ' ')}{lot.type_appartement", 1],
		["\t\t{monBailData.lot_type.replace('_', ' ')}{monBailData.lot_type_appartement", 1],
		['\t\tconst t = lot.type.replaceAll(/_/g, " ");', 1],
		//  La forme voulue, jamais signalée.
		['\t\t\t{lotTypeComplet(lot.type, lot.type_appartement)}', 0],
		//  Un `replace('_')` sur autre chose qu'un type de lot : hors portée.
		["\t\t\t{statut.replace('_', ' ')}", 0],
		//  Un commentaire qui cite la forme refusée.
		["\t// on écrivait lot.type.replace('_', ' ') ici", 0],
	];
	let ko = 0;
	for (const [ligne, attendu] of cas) {
		const obtenu = fautes(ligne).length;
		console.log(`${obtenu === attendu ? 'PASS' : 'FAIL'}  ${ligne.trim()}`);
		if (obtenu !== attendu) ko = 1;
	}
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	return ko;
}

function main() {
	if (process.argv.includes('--selftest')) return selftest();
	const trouves = [];
	for (const f of fichiers(RACINE)) {
		const rel = f.split(sep).join('/');
		if (rel === SOURCE) continue;
		for (const n of fautes(readFileSync(f, 'utf8'))) trouves.push(`${rel}:${n}`);
	}
	if (!trouves.length) {
		console.log(
			'✓ Type de lot : aucun libellé recalculé hors de `lotTypeLabel` / `lotTypeComplet`.',
		);
		return 0;
	}
	console.error(`\n✗ ${trouves.length} libellé(s) de type de lot recalculé(s) à la main :`);
	for (const t of trouves) console.error(`   ${t}`);
	console.error(
		'\n  Employer `lotTypeComplet(type, typeAppartement)` ou `lotTypeLabel(type)` (`$lib/utils`).\n',
	);
	return 1;
}

process.exit(main());
