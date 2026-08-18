/**
 * Garde-fou — **une consigne qui énumère ce que le code déclare**.
 *
 * ## Le défaut (#482, trouvé le 19/08/2026 en traitant #429)
 *
 * `svelte/no-at-html-tags` étant désactivée, la règle XSS du projet repose sur une
 * liste de fonctions d'assainissement. Cette liste est écrite **six fois** : dans
 * `CLAUDE.md` (deux endroits), dans trois skills, et — la seule qui fasse foi —
 * dans `src/lib/sanitize.ts`.
 *
 * Le 19/08, **cinq de ces six copies ne nommaient qu'une fonction sur trois**. La
 * consigne décrivait un dépôt qui n'existait plus depuis la factorisation qui avait
 * créé `safeDescription` et `safeRichContent`.
 *
 * Ce n'est pas resté théorique. `svelte-patterns` déclarait `renderDesc` — le corps
 * exact de `safeDescription` — comme « le seul helper qui reste légitimement
 * local », alors que cette fonction avait justement été écrite pour le supprimer.
 * Résultat : une **troisième** copie est apparue dans `tickets/[id]` sous le nom
 * `renderContent`, et c'est un contrôle écrit six jours plus tard qui l'a trouvée.
 *
 * 🔴 **La consigne fabriquait la duplication.** C'est le résidu de factorisation le
 * plus nocif, parce que c'est le seul qui soit **actif** : les autres dorment,
 * celui-ci fait réécrire du code — par quelqu'un qui suit correctement la
 * documentation (`standards/02-factorisation.md` §5).
 *
 * ## Pourquoi aucun contrôle ne pouvait l'attraper
 *
 *   • `lint:html` regarde le **code**, et le code produit par la consigne était
 *     *correct* — c'est sa raison d'être qui était périmée ;
 *   • la CI ne lit ni `CLAUDE.md` ni `.claude/skills/` ;
 *   • une relecture ne voit pas une consigne fausse : elle décrit un dépôt
 *     plausible.
 *
 * ## Ce que ce contrôle vérifie
 *
 * **Tout fichier de consigne qui parle d'assainissement HTML doit nommer TOUTES
 * les fonctions que `sanitize.ts` exporte.** La liste attendue est lue à la source,
 * jamais recopiée — c'est le principe même de `lint:html`, retourné vers la
 * documentation : une liste recopiée ici retomberait dans le défaut qu'elle garde.
 *
 * « Parle d'assainissement » = cite au moins une des fonctions, ou la balise
 * `{@html`. Un fichier muet sur le sujet n'est pas concerné : ce contrôle vérifie
 * la **complétude** de ce qui est dit, jamais qu'il faille en parler.
 *
 * ⚠️ Volontairement limité à cette énumération-là. D'autres consignes énumèrent ce
 * que le code déclare (dépendances d'auth, `lint:*`, statuts de ticket), et elles
 * relèvent du même motif — mais un contrôle qui produirait des faux positifs sur du
 * texte libre serait désarmé dans la semaine (`standards/04`). On commence par
 * celle qui a coûté quelque chose.
 */
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, relative } from 'node:path';

const RACINE_FRONT = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const RACINE_DEPOT = new URL('../..', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');

/** Nombre minimal de fichiers de consigne attendus — cas zéro. */
const CONSIGNES_MINIMALES = 3;

// ── 1. La liste qui fait foi, lue à la source ────────────────────────────────
const SOURCE = join(RACINE_FRONT, 'lib', 'sanitize.ts');
let attendues;
try {
	const src = readFileSync(SOURCE, 'utf8');
	attendues = [...src.matchAll(/^export function (safe\w+)\s*\(/gm)].map(m => m[1]);
} catch {
	console.error('✗ INCONNU : src/lib/sanitize.ts est illisible — ce contrôle ne conclut pas.');
	process.exit(1);
}
if (attendues.length === 0) {
	console.error('✗ Cas zéro : aucune fonction `export function safe…()` dans sanitize.ts.');
	console.error('Ne pas lire ceci comme un succès.');
	process.exit(1);
}

// ── 2. Les fichiers de consigne ──────────────────────────────────────────────
function markdown(dir) {
	if (!existsSync(dir)) return [];
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...markdown(chemin));
		else if (nom.endsWith('.md')) sortie.push(chemin);
	}
	return sortie;
}

const candidats = [
	join(RACINE_DEPOT, 'CLAUDE.md'),
	...markdown(join(RACINE_DEPOT, '.claude', 'skills')),
].filter(existsSync);

if (candidats.length < CONSIGNES_MINIMALES) {
	console.error(
		`✗ Cas zéro : ${candidats.length} fichier(s) de consigne trouvé(s), ` +
			`${CONSIGNES_MINIMALES} attendus au minimum.`,
	);
	console.error(
		"L'arborescence des consignes a changé, ou le contrôle ne sait plus la lire —\n" +
			'ne pas lire ceci comme un succès (`standards/04` §2).',
	);
	process.exit(1);
}

// ── 3. Ceux qui en parlent doivent tout nommer ───────────────────────────────
const erreurs = [];
let concernes = 0;

for (const chemin of candidats) {
	const relatif = relative(RACINE_DEPOT, chemin).replace(/\\/g, '/');
	const texte = readFileSync(chemin, 'utf8');

	const parle = attendues.some(f => texte.includes(f)) || texte.includes('{@html');
	if (!parle) continue;
	concernes++;

	const absentes = attendues.filter(f => !texte.includes(f));
	if (absentes.length) {
		erreurs.push(
			`${relatif} — parle d'assainissement mais ne nomme pas : ${absentes.join(', ')}. ` +
				`Attendu (lu dans sanitize.ts) : ${attendues.join(', ')}.`,
		);
	}
}

if (concernes === 0) {
	console.error("✗ Cas zéro : aucun fichier de consigne ne parle d'assainissement HTML.");
	console.error(
		'La règle XSS est la première des « quatre règles qui ne se négocient pas » :\n' +
			"si plus aucune consigne ne la porte, c'est le contrôle qui a cessé de voir.",
	);
	process.exit(1);
}

if (erreurs.length) {
	console.error('✗ Consigne incomplète — elle décrit un dépôt qui n’existe pas :\n');
	for (const e of erreurs) console.error(`  • ${e}`);
	console.error(
		"\n🔴 Une consigne périmée est le seul résidu de factorisation qui RÉGÉNÈRE le\n" +
			"   défaut : elle fait réécrire à la main ce que le dépôt a mutualisé, par\n" +
			'   quelqu’un qui la suit correctement. C’est ainsi que `renderContent` est né\n' +
			'   (#429), et personne ne pouvait le voir — le code produit était correct.\n',
	);
	process.exit(1);
}

console.log(
	`✓ Consignes : ${concernes} fichier(s) parlant d'assainissement sur ${candidats.length} lus — ` +
		`tous nomment ${attendues.join(', ')}.`,
);
