#!/usr/bin/env node
/**
 *  Le lien vers les **consignes de la copropriété** se rend par un seul
 *  composant, `LienConsignes` (#779, 01/10/2026).
 *
 *  🔴 Il était écrit TROIS fois — l'accueil, l'annuaire, l'onglet Annuaire de
 *  l'Espace CS — et les copies avaient divergé :
 *
 *  | | Accueil | Annuaire · Espace CS |
 *  |---|---|---|
 *  | libellé | « Consignes **de la** copropriété » | « Consignes **de** copropriété » |
 *  | icône | 📋 | 📄 |
 *  | style | carte, feuille du composant | bouton, `style="…"` en ligne |
 *
 *  Le libellé retenu est celui du manuel et du courriel d'arrivée
 *  (`routers/admin/arrivants.py`) : c'est le nom sous lequel l'arrivant les
 *  reçoit. Les deux FORMES restent — une carte en tête de l'accueil, un bouton
 *  au pied d'un annuaire — et se choisissent par la prop `forme`.
 *
 *  Ce contrôle refuse la quatrième copie : l'adresse de la fiche écrite hors du
 *  composant.
 *
 *  Lancer : node scripts/check-lien-consignes.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';

const RACINE = 'src';
const SOURCE = 'src/lib/components/LienConsignes.svelte';

/**  L'adresse de la fiche, quelle que soit la façon de l'écrire. */
const COPIE = /\/admin\/fiche-arrivant\b/;

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (e.endsWith('.svelte') || e.endsWith('.ts')) acc.push(p);
	}
	return acc;
}

export function fautes(source) {
	return source
		.split('\n')
		.map((ligne, i) => [ligne, i + 1])
		.filter(([l]) => COPIE.test(l))
		.map(([, n]) => n);
}

function selftest() {
	const cas = [
		['\t\thref="/api/admin/fiche-arrivant"', 1],
		["\tconst url = '/api/admin/fiche-arrivant';", 1],
		['\t<a href={`/api/admin/fiche-arrivant`} target="_blank">', 1],
		//  La forme voulue, jamais signalée.
		['\t<LienConsignes forme="bouton" />', 0],
		//  Une autre route d'administration des arrivants : hors portée.
		["\tawait api.post('/admin/arrivants/accueil', corps);", 0],
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
	let lus = 0;
	let source = false;
	for (const f of fichiers(RACINE)) {
		lus++;
		const rel = f.split(sep).join('/');
		if (rel === SOURCE) {
			//  L'exception doit SERVIR : un composant qui ne porterait plus
			//  l'adresse laisserait ce contrôle vert sur un lien disparu.
			source = fautes(readFileSync(f, 'utf8')).length > 0;
			continue;
		}
		for (const n of fautes(readFileSync(f, 'utf8'))) trouves.push(`${rel}:${n}`);
	}
	//  Cas zéro (standards/04 §2) : aucun fichier lu n'est pas « aucune copie ».
	if (!lus) {
		console.error(`✗ Aucun fichier lu sous ${RACINE} : contrôle INCONNU.`);
		return 1;
	}
	if (source && !trouves.length) {
		console.log(
			`✓ Consignes de la copropriété : liées par LienConsignes seul (${lus} fichiers lus).`,
		);
		return 0;
	}
	if (!source) {
		console.error(`✗ ${SOURCE} ne porte pas l'adresse de la fiche : la source unique manque.`);
	}
	if (trouves.length) {
		console.error(`\n✗ ${trouves.length} lien(s) vers la fiche des consignes écrit(s) à la main :`);
		for (const t of trouves) console.error(`   ${t}`);
		console.error('\n  Employer `<LienConsignes forme="carte" | "bouton" />`.\n');
	}
	return 1;
}

process.exit(main());
