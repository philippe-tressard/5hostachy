#!/usr/bin/env node
/**
 *  La catégorie d'une affaire s'affiche par son LIBELLÉ — jamais sa valeur
 *  brute (26/09/2026, signalé à l'écran).
 *
 *  ## Pourquoi ce contrôle
 *
 *  L'infobulle de l'icône de catégorie, sur la liste des affaires, disait
 *  « etude_travaux » au lieu de « Étude & travaux ». Le libellé existait
 *  (`categorieTicketLabel`, `$lib/tickets-categories`) ; rien n'obligeait à le
 *  prendre. La recherche en a trouvé deux autres : le tableau des reportings
 *  et la relance du syndic rendaient la même valeur brute.
 *
 *  ## Ce qu'il refuse
 *
 *  Dans le balisage d'un `.svelte`, un `X.categorie` rendu TEL QUEL :
 *
 *    title={ticket.categorie}          aria-label={t.categorie}
 *    <td>{row.categorie}</td>          <span>{t.categorie}</span>
 *
 *  La forme conforme : `categorieTicketLabel(x.categorie)`.
 *
 *  ⚠️ Il ne regarde pas une catégorie passée à une fonction, comparée ou
 *  servant de clé — c'est son usage normal. Seul l'AFFICHAGE est en cause.
 *
 *  Lancer : node scripts/check-categorie-brute.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const RACINE = 'src';
const ATTRIBUT = /\b(?:title|aria-label|alt)=\{[\w.?$]+\.categorie\}/g;
const TEXTE = />\s*\{[\w.?$]+\.categorie\}\s*</g;
const EMPLOI = /categorieTicketLabel\(/;

/**  Les catégories rendues brutes dans une source. PURE. */
export function categoriesBrutes(source) {
	const s = neutraliserCommentaires(source);
	return (s.match(ATTRIBUT) ?? []).length + (s.match(TEXTE) ?? []).length;
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const t = (libelle, attendu, src) => {
		const r = categoriesBrutes(src);
		console.log(`${r === attendu ? 'PASS' : 'FAIL'}  ${libelle} → ${r}`);
		if (r !== attendu) ko = 1;
	};
	//  🔴 Les trois formes trouvées le 26/09/2026.
	t('infobulle brute', 1, '<span class="tk-cat" title={ticket.categorie}>🏗️</span>');
	t('cellule brute', 1, '<tr><td>{row.categorie}</td><td>{row.total}</td></tr>');
	t('badge brut', 1, '<span class="badge badge-gray">{t.categorie}</span>');
	t('nom accessible brut', 1, '<span aria-label={t.categorie}>🏗️</span>');
	t('libellé conforme', 0, '<span title={categorieTicketLabel(ticket.categorie)}>🏗️</span>');
	t('texte conforme', 0, '<td>{categorieTicketLabel(row.categorie)}</td>');
	t(
		'clé et comparaison',
		0,
		"{#each l as r (r.categorie)}{#if r.categorie === 'bug'}x{/if}{/each}",
	);
	t('commentaire ignoré', 0, '<!-- <td>{row.categorie}</td> -->');
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	process.exit(ko);
}

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (e.endsWith('.svelte')) acc.push(p);
	}
	return acc;
}

const fautifs = [];
let emplois = 0;
for (const f of fichiers(RACINE)) {
	const rel = f
		.split(sep)
		.join('/')
		.replace(/^src\//, '');
	const source = readFileSync(f, 'utf8');
	if (EMPLOI.test(neutraliserCommentaires(source))) emplois++;
	const n = categoriesBrutes(source);
	if (n) fautifs.push(`${rel} (${n})`);
}

//  🔴 LE CAS ZÉRO (`standards/04` §2) : plus aucun écran n'emploie le libellé,
//  c'est que la règle a changé de forme — le contrôle ne mesure plus rien.
if (emplois === 0) {
	console.error(
		'\n✗ INCONNU : aucun écran n’appelle `categorieTicketLabel` — mettre le contrôle à jour.\n',
	);
	process.exit(2);
}

if (fautifs.length) {
	console.error(`\n✗ ${fautifs.length} fichier(s) affichent une catégorie brute :\n`);
	for (const f of fautifs) console.error(`  ${f}`);
	console.error('\n  → `categorieTicketLabel(x.categorie)` (`$lib/tickets-categories`).\n');
	process.exit(1);
}
console.log(`✓ Catégories : ${emplois} écran(s) les affichent par leur libellé, aucune brute.`);
