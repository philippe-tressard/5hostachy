#!/usr/bin/env node
// SPDX-FileCopyrightText: 2026 Philippe Tressard
// SPDX-License-Identifier: LicenseRef-5Hostachy
/**
 * Ce que git ignore sous `front/` est PRODUIT — donc ESLint ne doit pas le lire.
 *
 * ## Pourquoi ce contrôle (#1064, 20/09/2026)
 *
 * `bash scripts/poste/rejouer-ci.sh` rendait **trois verdicts différents sur le
 * même commit** : ESLint y échouait une fois sur deux avec ~2075 erreurs
 * `@typescript-eslint/no-unused-expressions` en « ligne 5, colonne 1842 » — la
 * signature d'un fichier **minifié**. Lancé seul, il passait à tous les coups.
 *
 * La cause : `front/e2e-rapport/`, le rapport HTML de Playwright. Il est dans
 * `.gitignore` depuis toujours, mais **pas** dans les `ignores` d'ESLint, qui en
 * tenait sa propre liste. Le rapporteur y écrit des bundles `.js` le temps de son
 * exécution, puis les incorpore à `index.html` et les supprime : le défaut
 * n'existait donc que **pendant** une fenêtre de quelques secondes — d'où
 * l'intermittence, et d'où le réflexe le plus dangereux qui soit, « relancer
 * jusqu'au vert ». Le jour où le rouge aurait été vrai, le geste aurait été le
 * même (`standards/04` — la fiabilité du contrôle passe avant ce qu'il contrôle).
 *
 * ## Ce que ce contrôle exige
 *
 * Tout **répertoire** de `front/` listé dans `.gitignore` figure dans les
 * `ignores` d'ESLint. Le sens de la règle compte : `.gitignore` est la liste de ce
 * que le dépôt considère comme produit, donc c'est la source — et une seconde
 * liste tenue à la main diverge au premier outil qui écrit ailleurs. C'est
 * exactement ce qui s'est passé : `e2e-rapport/` a été ajouté à `.gitignore` en
 * même temps que les tests Playwright, et personne n'a pensé à ESLint.
 *
 * ⚠️ L'inverse n'est PAS exigé : ESLint ignore aussi `static/`, qui est versionné
 * (manuels et ressources tierces, non écrits ici). Ignorer plus que le produit est
 * une décision ; en ignorer moins est un accident.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const ICI = dirname(fileURLToPath(import.meta.url));
const RACINE = join(ICI, '..', '..');

/** Les répertoires que git ignore sous `front/`, sans le préfixe. */
function repertoiresIgnoresParGit() {
	return readFileSync(join(RACINE, '.gitignore'), 'utf8')
		.split(/\r?\n/)
		.map((l) => l.trim())
		.filter((l) => l.startsWith('front/') && l.endsWith('/'))
		.map((l) => l.slice('front/'.length));
}

/** Les motifs de la clause `ignores` d'`eslint.config.js`. */
function ignoresDEslint() {
	const source = readFileSync(join(ICI, '..', 'eslint.config.js'), 'utf8');
	const clause = source.match(/ignores:\s*\[([^\]]*)\]/);
	if (!clause) {
		console.error(
			'✗ Aucune clause `ignores: [...]` trouvée dans eslint.config.js — ce contrôle\n' +
				'  ne mesure plus rien. La clause a changé de forme : reprendre le motif.',
		);
		process.exit(2);
	}
	return [...clause[1].matchAll(/['"]([^'"]+)['"]/g)].map((m) => m[1]);
}

const attendus = repertoiresIgnoresParGit();
const declares = ignoresDEslint();

if (attendus.length === 0) {
	console.error('✗ Aucun répertoire `front/…/` dans .gitignore : le motif ne lit plus rien.');
	process.exit(2);
}

//  Auto-test : la sonde doit être vue manquante quand elle n'est pas déclarée.
const SONDE = '__sonde-inexistante__/';
if (declares.includes(SONDE)) {
	console.error('✗ Auto-test : la sonde figure dans les `ignores`, le contrôle ne prouve rien.');
	process.exit(2);
}
console.log('✓ Auto-test : un répertoire non déclaré est bien vu comme manquant.');

const manquants = attendus.filter((d) => !declares.includes(d));
if (manquants.length > 0) {
	console.error(
		`\n✗ ${manquants.length} répertoire(s) produit(s) qu'ESLint analyse quand même :\n` +
			manquants.map((d) => `    front/${d}`).join('\n') +
			'\n\n  Ils sont dans .gitignore, donc ils ne sont pas écrits à la main. ESLint les\n' +
			'  lira, et le relevé dépendra de ce qui traîne sur la machine au moment du\n' +
			"  passage — c'est le rouge intermittent de #1064.\n" +
			'  → les ajouter à `ignores` dans front/eslint.config.js.\n',
	);
	process.exit(1);
}

console.log(
	`✓ Les ${attendus.length} répertoires produits de front/ sont hors du périmètre d'ESLint.`,
);
