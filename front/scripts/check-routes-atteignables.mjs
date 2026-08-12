/**
 * Garde-fou : un écran d'administration doit être atteignable par l'interface.
 *
 * POURQUOI. Le 11/08/2026, trois routes sous `admin/` compilaient, étaient
 * protégées par le layout, avaient leurs endpoints et leur client TypeScript —
 * et **aucun écran n'y menait** (#307). Parmi elles, la configuration des
 * sauvegardes : fréquence, heure et nombre de versions conservées n'étaient
 * réglables par aucun chemin de l'interface. Il fallait connaître l'URL et la
 * taper à la main.
 *
 * Un écran inaccessible est pire qu'un écran absent : son code, ses tests et ses
 * endpoints sont maintenus, la capacité est réputée livrée, et personne ne peut
 * s'en servir. Rien ne pouvait le voir — ni la compilation, ni les tests, ni le
 * contrôle des endpoints orphelins, qui vérifie l'autre bout de la chaîne.
 *
 * LA RÈGLE : toute route sous `routes/(app)/admin/` est citée quelque part par
 * un `href=` ou un `goto(`, ailleurs que dans la route elle-même.
 *
 * Une exception se déclare dans `TOLEREES`, avec sa raison. Si la raison ne tient
 * pas en une ligne, c'est probablement que la route doit être supprimée ou reliée.
 * Les deux sens sont vérifiés : une tolérance qui a retrouvé un lien fait échouer
 * le contrôle, sinon la liste se remplit et ne protège plus rien.
 *
 * Le contrôle s'auto-contrôle : s'il n'analyse aucun fichier ou ne trouve aucune
 * route, il ÉCHOUE au lieu de conclure au vert
 * (`standards/04-fiabilite-des-controles.md` §2, cas zéro).
 */
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const ADMIN = join(RACINE, 'routes', '(app)', 'admin');

/**
 * Routes admin légitimement sans lien, avec la raison.
 *
 * ⚠️ Une entrée ici est une décision consciente, pas un contournement.
 */
const TOLEREES = {
	'templates-email':
		"doublon partiel de l'onglet « Modèles e-mail » de admin/+page.svelte, mais " +
		"seul porteur du « remettre tous les modèles au design par défaut » : relier " +
		'les deux écrans referait le doublon corrigé par #299, les fusionner est une ' +
		'décision fonctionnelle — instruit dans #307',
};

function fichiers(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...fichiers(chemin));
		else if (/\.(svelte|ts|js)$/.test(nom)) sortie.push(chemin);
	}
	return sortie;
}

if (!existsSync(ADMIN)) {
	console.error(`✗ Routes admin introuvables (${ADMIN}) — contrôle inopérant.`);
	process.exit(1);
}

//  Sous-répertoires de `admin/` portant une page : ce sont les routes à atteindre.
const routes = readdirSync(ADMIN).filter(
	(nom) => statSync(join(ADMIN, nom)).isDirectory() && existsSync(join(ADMIN, nom, '+page.svelte')),
);

const tous = fichiers(RACINE);
if (tous.length === 0 || routes.length === 0) {
	console.error(
		`✗ Cas zéro : ${tous.length} fichier(s) analysé(s), ${routes.length} route(s) admin trouvée(s) — ` +
			"l'arborescence a changé, ce contrôle ne mesure plus rien.",
	);
	process.exit(1);
}

const orphelines = [];
const tolereesLiees = [];

for (const route of routes) {
	//  On cherche le lien PARTOUT sauf dans la route elle-même : une page qui
	//  se cite (un onglet interne, un retour) ne la rend pas atteignable.
	const dossier = join(ADMIN, route) + '/';
	const motif = new RegExp(`(href=["'\`][^"'\`]*|goto\\(\\s*["'\`][^"'\`]*)/admin/${route}(?![\\w-])`);
	const lie = tous.some((f) => !f.startsWith(dossier) && motif.test(readFileSync(f, 'utf8')));

	if (!lie && !(route in TOLEREES)) orphelines.push(route);
	if (lie && route in TOLEREES) tolereesLiees.push(route);
}

let echec = false;

if (orphelines.length > 0) {
	echec = true;
	console.error("✗ Écran(s) d'administration qu'aucun lien ne permet d'atteindre :");
	for (const r of orphelines) console.error(`    /admin/${r}`);
	console.error(
		"\n  Ajouter un lien (`href`) depuis l'écran qui les porte, supprimer la route si\n" +
			'  elle fait doublon, ou la déclarer dans TOLEREES avec sa raison.',
	);
}

if (tolereesLiees.length > 0) {
	echec = true;
	console.error('\n✗ Tolérance(s) devenue(s) inutile(s) — un lien existe désormais :');
	for (const r of tolereesLiees) console.error(`    /admin/${r} — retirer l'entrée de TOLEREES`);
}

if (echec) process.exit(1);

console.log(
	`✓ Routes admin atteignables : ${routes.length - Object.keys(TOLEREES).length} liée(s), ` +
		`${Object.keys(TOLEREES).length} tolérée(s) et justifiée(s).`,
);
