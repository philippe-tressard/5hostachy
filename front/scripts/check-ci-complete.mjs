/**
 * Garde-fou : un contrôle déclaré dans `package.json` doit être LANCÉ par la CI.
 *
 * ## Pourquoi il existe (#561, 28/08/2026 — et c'est arrivé le soir même)
 *
 * `lint:a11y` a été écrit, éprouvé en le déclenchant, déclaré dans
 * `package.json`… et son étape de CI **n'est pas partie dans le commit** : un
 * `git add -A front` ne prend pas `.github/`. Le contrôle existait, il était
 * juste, et **rien ne l'exécutait**.
 *
 * 🔴 C'est le pire des faux verts, parce qu'il ne ressemble pas à une panne :
 * `npm run lint:a11y` marche quand on le tape, la CI est verte, et le dépôt
 * n'est plus protégé. Le même défaut a déjà frappé ici deux fois — `--selftest`
 * exposé mais jamais lancé (`lib-analyse-styles`, #562), et `check-stack.sh`
 * retiré du cron d'un nœud (#301).
 *
 * ⚠️ Ce contrôle ne dit pas qu'un contrôle est BON. Il dit qu'il TOURNE. C'est
 * une question plus étroite, et c'est justement celle que personne ne posait.
 *
 * Usage : npm run lint:ci
 */
import { readFileSync } from 'node:fs';

const PACKAGE = new URL('../package.json', import.meta.url);
const WORKFLOW = new URL('../../.github/workflows/ci.yml', import.meta.url);

/**
 * Les contrôles déclarés que la CI ne lance PAS, chacun avec sa raison.
 *
 * ⚠️ Une entrée qui ne sert plus fait échouer : sinon la liste couvrirait un
 * contrôle redevenu câblé, et masquerait le prochain qui ne l'est pas.
 */
const EXCEPTIONS = {
	'lint:format':
		'prettier — le reformatage n’a pas eu lieu (#419, points 3 et 4). Le câbler ' +
		'aujourd’hui rendrait le job rouge sur 51 fichiers, donc désarmé dans la semaine.',
};

function abandonner(message) {
	//  Un contrôle qui ne peut pas s'exécuter renvoie INCONNU, jamais OK.
	console.error(`\n✗ lint:ci — ${message}\n`);
	process.exit(1);
}

let scripts;
try {
	scripts = JSON.parse(readFileSync(PACKAGE, 'utf8')).scripts ?? {};
} catch (e) {
	abandonner(`\`package.json\` illisible : ${e.message}`);
}

let workflow;
try {
	workflow = readFileSync(WORKFLOW, 'utf8');
} catch (e) {
	abandonner(
		`\`.github/workflows/ci.yml\` illisible (${e.message}). Sans lui, ce contrôle ne\n` +
			'  peut rien vérifier — et se taire vaudrait un vert.',
	);
}

const declares = Object.keys(scripts).filter((n) => n.startsWith('lint:'));
//  Cas zéro : un `package.json` sans script `lint:` ne veut pas dire « tout va
//  bien », il veut dire que la lecture est cassée.
if (declares.length < 20) {
	abandonner(
		`${declares.length} script(s) \`lint:*\` lu(s) dans package.json, au moins 20 attendus.\n` +
			'  Le motif de lecture ne correspond plus au fichier.',
	);
}
//  Idem côté workflow : s'il ne cite aucun `npm run lint:`, ce n'est pas que la
//  CI n'en lance aucun, c'est qu'on ne lit pas le bon fichier.
if (!/npm run lint:/.test(workflow)) {
	abandonner(
		'aucun `npm run lint:` dans le workflow. Ce n’est pas un dépôt sans contrôles,\n' +
			'  c’est une lecture qui ne correspond plus à la CI.',
	);
}

const manquants = declares.filter(
	(n) => !new RegExp(`\\b${n.replace(':', ':')}(\\s|$|"|')`).test(workflow) && !(n in EXCEPTIONS),
);
const perimees = Object.keys(EXCEPTIONS).filter(
	(n) => !declares.includes(n) || new RegExp(`\\b${n}(\\s|$|"|')`).test(workflow),
);

if (perimees.length) {
	console.error(
		'\n✗ lint:ci — ces exceptions ne servent plus :\n\n' +
			perimees.map((n) => `  ${n}\n      « ${EXCEPTIONS[n]} »`).join('\n') +
			'\n\n  Le contrôle est câblé, ou il a disparu. Retirer l’entrée.\n',
	);
	process.exit(1);
}

if (manquants.length) {
	console.error(
		`\n✗ lint:ci — ${manquants.length} contrôle(s) déclaré(s) que la CI ne lance PAS :\n\n` +
			manquants.map((n) => `  npm run ${n}`).join('\n') +
			'\n\n  Un contrôle qui existe et que rien n’exécute est le pire des faux verts :\n' +
			'  il marche quand on le tape, la CI est verte, et le dépôt n’est plus protégé.\n' +
			'  Ajouter son étape dans `.github/workflows/ci.yml` — ou, si c’est délibéré,\n' +
			'  le déclarer dans EXCEPTIONS avec sa raison.\n',
	);
	process.exit(1);
}

console.log(
	`✓ lint:ci — ${declares.length} contrôle(s) déclaré(s), tous lancés par la CI ` +
		`(${Object.keys(EXCEPTIONS).length} exception(s) nommée(s)).`,
);
