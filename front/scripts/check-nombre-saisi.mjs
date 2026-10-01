#!/usr/bin/env node
/**
 *  Une valeur SAISIE se convertit en nombre par `nombreOuNull` (`$lib/utils`),
 *  jamais à la main (#1516, 01/10/2026).
 *
 *  🔴 Un `<input type="number" bind:value>` vidé rend `null` (Svelte), pas
 *  `''`. Les conversions écrites à la main ne testaient que l'un des deux :
 *
 *  | Forme | Champ vidé | Défaut |
 *  |---|---|---|
 *  | `v === '' ? null : Number(v)` | `Number(null)` = **0** | l'index d'un relevé enregistré à 0 m³, un nombre de lots à 0 (#779) |
 *  | `v ? Number(v) : null` | `null` | juste, mais un **0** saisi devient `null` |
 *  | `Number(v) \|\| null` | `null` | idem |
 *
 *  Dix copies, trois comportements pour une notion. Ce contrôle refuse la
 *  onzième : une conversion `Number` / `parseFloat` / `parseInt` gardée par un
 *  test de vide (`=== ''`, `!== ''`, ternaire sur la valeur, `|| null`).
 *  Une lecture de configuration avec repli (`parseInt(x) || 587`) n'est pas une
 *  saisie, et n'est pas visée.
 *
 *  Lancer : node scripts/check-nombre-saisi.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';

const RACINE = 'src';
const SOURCE = 'src/lib/utils.ts';

/**  Écarts déclarés, avec leur raison. Une entrée qui ne sert plus fait échouer. */
const EXCEPTIONS = {
	'src/lib/deepLink.ts': "un fragment d'adresse déjà filtré par une expression, pas une saisie",
};
const CONV = String.raw`(?:Number|parseFloat|parseInt)\(`;

/**  Les trois formes d'une conversion de saisie écrite à la main. */
const COPIES = [
	//  `v === '' ? null : Number(v)` · `v !== '' ? Number(v) : null`
	new RegExp(String.raw`[!=]==\s*''\s*\?\s*(?:null|undefined|${CONV})`),
	//  `v ? Number(v) : null|undefined`
	new RegExp(String.raw`\?\s*${CONV}[^()]*\)\s*:\s*(?:null|undefined)\b`),
	//  `Number(v) || null`
	new RegExp(String.raw`${CONV}[^()]*\)\s*\|\|\s*(?:null|undefined)\b`),
];

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (e.endsWith('.svelte') || e.endsWith('.ts')) acc.push(p);
	}
	return acc;
}

export function fautes(source) {
	//  Une expression coupée par Prettier se relit sur une ligne.
	const lignes = source.split('\n');
	const trouvees = [];
	for (let i = 0; i < lignes.length; i++) {
		const l = lignes[i].trim();
		if (l.startsWith('//') || l.startsWith('*')) continue;
		const fenetre = [l, (lignes[i + 1] ?? '').trim(), (lignes[i + 2] ?? '').trim()].join(' ');
		const suite = (lignes[i + 1] ?? '').trim();
		const coupee = /\?\s*$/.test(l) || suite.startsWith('?');
		//  Coupée : comptée sur sa PREMIÈRE ligne, et seulement si la suivante ne
		//  la porte pas déjà entière — sinon `...(cond` puis `? { a: v ? Number(v)
		//  : null }` compterait deux fois la même conversion.
		const entiere = (t) => COPIES.some((m) => m.test(t));
		if (entiere(l) || (coupee && entiere(fenetre) && !entiere(suite))) trouvees.push(i + 1);
	}
	return trouvees;
}

function selftest() {
	const cas = [
		["\t\tindex: releveForm.index !== '' ? Number(releveForm.index) : null,", 1],
		["\t\tprestataireId = choix === '' ? null : Number(choix);", 1],
		['\t\tlot_id: editLot ? Number(editLot) : null,', 1],
		['\t\tannee: s.annee ? Number(s.annee) : undefined,', 1],
		["\t\tconst prixEnvoye = typeAnnonce === 'vente' && prix ? parseFloat(prix) : null;", 1],
		['\t\tfrequence_valeur: entretien ? Number(s.frequenceValeur) || null : null,', 1],
		//  Coupée par Prettier sur trois lignes.
		['\t\tduree: f.duree\n\t\t\t? Number(f.duree)\n\t\t\t: null,', 1],
		//  Entière sur la ligne qui suit un `...(cond` : comptée une fois.
		['\t\t...(avecAg\n\t\t\t? { annee: s.annee ? Number(s.annee) : undefined }\n\t\t\t: {}),', 1],
		//  La forme voulue, jamais signalée.
		['\t\tindex: nombreOuNull(releveForm.index),', 0],
		//  Une configuration lue avec repli : hors portée.
		["\t\tsmtpConfig.port = parseInt(lues['smtp_port'] ?? '587') || 587;", 0],
		['\t$: plafondMois = Number(valeurs[cles.plafond_mois]) || 0;', 0],
		//  Un commentaire qui cite la forme refusée.
		["\t// on écrivait v === '' ? null : Number(v)", 0],
	];
	let ko = 0;
	for (const [source, attendu] of cas) {
		const obtenu = fautes(source).length;
		console.log(`${obtenu === attendu ? 'PASS' : 'FAIL'}  ${source.trim().split('\n')[0]}`);
		if (obtenu !== attendu) ko = 1;
	}
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	return ko;
}

function main() {
	if (process.argv.includes('--selftest')) return selftest();
	const trouves = [];
	const servies = new Set();
	let lus = 0;
	for (const f of fichiers(RACINE)) {
		lus++;
		const rel = f.split(sep).join('/');
		if (rel === SOURCE) continue;
		const n = fautes(readFileSync(f, 'utf8'));
		if (rel in EXCEPTIONS) {
			if (n.length) servies.add(rel);
			continue;
		}
		for (const l of n) trouves.push(`${rel}:${l}`);
	}
	const mortes = Object.keys(EXCEPTIONS).filter((r) => !servies.has(r));
	if (mortes.length) {
		console.error(`✗ Exception(s) qui ne servent plus — les retirer : ${mortes.join(', ')}`);
		return 1;
	}
	//  Cas zéro (standards/04 §2) : aucun fichier lu n'est pas « aucune copie ».
	if (!lus) {
		console.error(`✗ Aucun fichier lu sous ${RACINE} : contrôle INCONNU.`);
		return 1;
	}
	if (!trouves.length) {
		console.log(`✓ Nombres saisis : convertis par nombreOuNull seulement (${lus} fichiers lus).`);
		return 0;
	}
	console.error(`\n✗ ${trouves.length} conversion(s) de saisie en nombre écrite(s) à la main :`);
	for (const t of trouves) console.error(`   ${t}`);
	console.error(
		"\n  Employer `nombreOuNull(v)` (`$lib/utils`) : '', null et undefined donnent null, 0 reste 0.\n",
	);
	return 1;
}

process.exit(main());
