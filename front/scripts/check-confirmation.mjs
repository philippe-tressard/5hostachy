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

/** Le compte au 30/08/2026, après conversion de `residence` et `prestataires`. */
const PLAFOND = 31;

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

/**
 * 🔴 `confirmer()` rend une **promesse**. Sans `await`, l'appel est *truthy* :
 *
 *     if (!confirmer('Supprimer ?')) return;     // ← ne retourne JAMAIS
 *
 * Le geste s'exécute alors **sans que personne ait confirmé**, et rien ne le
 * dit : pas d'erreur, pas de journal, une boîte qui s'affiche puis disparaît
 * pendant que la suppression est déjà partie.
 *
 * C'est le risque que la conversion des quarante `confirm()` natifs introduit à
 * chaque écran repris — la forme native, elle, était synchrone. Le contrôle est
 * donc **préventif** : il n'y a aucun appel fautif aujourd'hui, et c'est
 * précisément le moment de le poser.
 *
 * ⚠️ Motif volontairement étroit : `confirmer(` non précédé de `await`. Une
 * affectation différée (`const p = confirmer(…)`) n'existe nulle part et serait
 * un usage à instruire, pas à tolérer en silence.
 */
const APPELS_SANS_AWAIT = /(?<!await\s{1,4})\bconfirmer\s*\(/;

const releve = [];
const sansAwait = [];
for (const chemin of tous) {
	const rel = relative(SOURCE, chemin).split(sep).join('/');
	if (HORS_RELEVE.includes(rel)) continue;
	const lignes = readFileSync(chemin, 'utf8').split('\n');
	lignes.forEach((ligne, i) => {
		//  `confirmer(` est le remplacement : il ne doit pas compter.
		if (/\bconfirm\s*\(/.test(ligne)) releve.push(`${rel}:${i + 1}`);
		//  `confirmer(` sans `await` — le geste part sans confirmation.
		if (/\bconfirmer\s*\(/.test(ligne) && APPELS_SANS_AWAIT.test(ligne)) {
			sansAwait.push(`${rel}:${i + 1} — ${ligne.trim().slice(0, 70)}`);
		}
	});
}

if (sansAwait.length) {
	console.error(
		`\n✗ ${sansAwait.length} appel(s) à \`confirmer()\` SANS \`await\` :\n\n` +
			sansAwait.map((l) => `   ${l}`).join('\n') +
			'\n\n  🔴 `confirmer()` rend une PROMESSE : sans `await`, elle est toujours' +
			'\n  *truthy*, la garde ne retourne jamais, et le geste part SANS que personne' +
			'\n  ait confirmé. Rien ne le signale — ni erreur, ni journal.\n' +
			"\n  La forme : `if (!(await confirmer('…'))) return;`\n",
	);
	process.exit(1);
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
