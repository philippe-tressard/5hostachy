#!/usr/bin/env node
/**
 * Garde-fou : le nombre de `confirm()` NATIFS ne peut que DÉCROÎTRE (#605).
 *
 * ## Pourquoi un plafond et non une interdiction
 *
 * Quarante gestes du site demandaient confirmation avec la boîte native du
 * navigateur. Elle bloque le fil d'exécution, ignore la charte, et — le plus
 * grave — donne exactement le même aspect à « archiver » et à « supprimer
 * définitivement », alors que l'un se défait et l'autre non.
 *
 * Les convertir d'un coup toucherait vingt-cinq écrans avant qu'on en ait
 * regardé un seul, ce que **R5** du cadre #430 interdit : *l'enrichissement se
 * propose sur UN écran, se fait constater, puis se généralise.*
 *
 * Le plafond est donc la seule forme honnête : il empêche d'en AJOUTER, et il
 * baisse à chaque écran repris. Une interdiction sèche aurait été désarmée dans
 * la semaine ; un simple avertissement n'aurait rien empêché.
 *
 * ⚠️ **Le plafond se met à jour EN BAISSANT, jamais en montant.** Un lot qui
 * l'augmente a introduit un `confirm()` natif, ce que ce contrôle existe pour
 * refuser.
 *
 * Usage : npm run lint:confirmation   (exit 1 si le plafond est dépassé)
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..');
const SOURCE = join(RACINE, 'src');

/** Le compte au 29/08/2026, après conversion de l'écran Calendrier. */
const PLAFOND = 41;

/**
 * Fichiers qui PARLENT de `confirm()` sans en appeler un : le composant de
 * remplacement et son appel impératif, qui le citent dans leur documentation.
 */
const HORS_RELEVE = ['lib/components/Confirmation.svelte', 'lib/confirmation.ts'];

function fichiers(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...fichiers(chemin));
		else if (nom.endsWith('.svelte') || nom.endsWith('.ts')) sortie.push(chemin);
	}
	return sortie;
}

const tous = fichiers(SOURCE);
//  Cas zéro : l'arborescence a changé, le contrôle ne mesure plus rien.
if (tous.length < 50) {
	console.error(
		`✗ Cas zéro : ${tous.length} fichier(s) analysé(s), au moins 50 attendus — ` +
			'le parcours ne correspond plus à `src/`.',
	);
	process.exit(1);
}

const releve = [];
for (const chemin of tous) {
	const rel = relative(SOURCE, chemin).split(sep).join('/');
	if (HORS_RELEVE.includes(rel)) continue;
	const lignes = readFileSync(chemin, 'utf8').split('\n');
	lignes.forEach((ligne, i) => {
		//  `confirmer(` est le remplacement : il ne doit pas compter.
		if (/\bconfirm\s*\(/.test(ligne)) releve.push(`${rel}:${i + 1}`);
	});
}

if (releve.length > PLAFOND) {
	console.error(
		`\n✗ ${releve.length} appel(s) à \`confirm()\` natif — le plafond est ${PLAFOND}.\n\n` +
			releve.map((l) => `   ${l}`).join('\n') +
			`\n\n  La boîte native bloque le navigateur, ignore la charte, et donne le MÊME` +
			`\n  aspect à « archiver » et à « supprimer définitivement ».` +
			`\n  Employer \`confirmer()\` de \`$lib/confirmation\` — une ligne, comme avant.\n`,
	);
	process.exit(1);
}

if (releve.length < PLAFOND) {
	console.error(
		`\n✗ Le plafond est PÉRIMÉ : ${releve.length} appel(s) restants pour un plafond de ${PLAFOND}.\n\n` +
			`  Abaisser \`PLAFOND\` à ${releve.length} dans ce fichier. Un plafond qui reste\n` +
			`  au-dessus du réel laisse la place d'en réintroduire sans que rien ne le dise.\n`,
	);
	process.exit(1);
}

console.log(
	`✓ Confirmation : ${releve.length} \`confirm()\` natif(s) restant(s) sur un plafond de ${PLAFOND} ` +
		`(${tous.length} fichiers analysés) — la conversion vers \`confirmer()\` se poursuit écran par écran.`,
);
