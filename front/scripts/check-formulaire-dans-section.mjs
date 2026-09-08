/**
 * **Un formulaire de section se rend DANS sa section** — jamais en bas de page.
 *
 * ## Le défaut (#852, 08/09/2026)
 *
 * Signalé à l'écran :
 *
 * > *« l'édition est en bas de page et non dans la section sélectionnée […]
 * > quand on édite on ne se retrouve pas en bas de page mais à l'endroit où on
 * > édite (faire de même que la référence Actualité ou ticket) »*
 *
 * Les **sept** formulaires de l'écran Résidence étaient rendus à la FIN du
 * fichier, après toutes les sections. Cliquer « + Ajouter » dans « Plans »
 * ouvrait donc une boîte quatre cents pixels plus bas, sous les diagnostics —
 * hors de l'écran, et sans rapport visible avec le geste qu'on venait de faire.
 *
 * 🔴 **Ce n'est pas un défaut de style, c'est un défaut de PLACE.** Le balisage
 * était juste, le cadre était le bon, `lint:formulaires` était vert — il vérifie
 * *quel* cadre, jamais *où*. Aucun contrôle du dépôt ne regardait la position.
 *
 * ## Ce que celui-ci mesure
 *
 * Dans une page qui rend des **sections**, un formulaire monté au **premier
 * niveau** du balisage est un formulaire hors de sa section. Le contrôle compte
 * l'indentation : un `<Formulaire…>` collé à la marge, dans un fichier qui porte
 * des `<section>` ou des `<Section…>`, est signalé.
 *
 * ⚠️ **Ce qu'il ne mesure PAS**, et c'est assumé : une page sans section (un
 * formulaire de création pleine page, `/tickets/nouveau`) n'a pas de « section
 * d'appartenance ». La question ne s'y pose pas, et l'y poser donnerait des
 * dérogations à la pelle — donc un contrôle qu'on désarme.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';

const RACINE = new URL('..', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const ROUTES = join(RACINE, 'src', 'routes');

/**
 * Exceptions déclarées, avec leur raison.
 *
 * ⚠️ Le contrôle échoue si l'une devient inutile : une dérogation oubliée est
 * une porte qu'on croit fermée.
 */
const EXCEPTIONS = {};

/** Tous les `+page.svelte` sous `routes/`. */
function pages(dossier) {
	const trouves = [];
	for (const nom of readdirSync(dossier)) {
		const chemin = join(dossier, nom);
		if (statSync(chemin).isDirectory()) trouves.push(...pages(chemin));
		else if (nom === '+page.svelte') trouves.push(chemin);
	}
	return trouves;
}

/** Le balisage seul : sans le `<script>` ni le `<style>`, ni les commentaires. */
function balisage(source) {
	return source
		.replace(/<script[\s\S]*?<\/script>/g, '')
		.replace(/<style[\s\S]*?<\/style>/g, '')
		.replace(/<!--[\s\S]*?-->/g, '');
}

const fautifs = [];
const exceptionsUtiles = new Set();
let pagesAvecSections = 0;

for (const chemin of pages(ROUTES)) {
	const rel = relative(RACINE, chemin)
		.split(sep)
		.join('/')
		.replace(/^src\//, '');
	const corps = balisage(readFileSync(chemin, 'utf-8'));

	//  Une page sans section n'a pas de « section d'appartenance » : hors sujet.
	if (!/<section\b|<Section[A-Z]\w*\b/.test(corps)) continue;
	pagesAvecSections++;

	//  Un formulaire monté à la MARGE : aucune indentation devant lui.
	const horsSection = [...corps.matchAll(/^<(Formulaire[A-Z]\w*)\b/gm)].map((m) => m[1]);
	if (horsSection.length === 0) continue;

	if (EXCEPTIONS[rel]) {
		exceptionsUtiles.add(rel);
		continue;
	}
	fautifs.push(
		`  ${rel}\n      ${horsSection.length} formulaire(s) rendus au premier niveau : ` +
			`${[...new Set(horsSection)].join(', ')}\n` +
			`      Cette page rend des sections — un formulaire posé à la marge s'ouvre\n` +
			`      APRÈS elles toutes, loin du bouton qui l'a déclenché.`,
	);
}

//  🔴 CAS ZÉRO : sans page à sections lue, « aucun fautif » ne veut rien dire.
//  Un contrôle qui ne peut pas s'exécuter rend INCONNU, jamais OK
//  (`standards/04` §1).
if (pagesAvecSections < 3) {
	console.error(
		`\n✗ ${pagesAvecSections} page(s) à sections lue(s) — la portée du contrôle est\n` +
			`  cassée, et son vert ne veut rien dire. Vérifier le chemin ${ROUTES}.\n`,
	);
	process.exit(1);
}

const inutiles = Object.keys(EXCEPTIONS).filter((rel) => !exceptionsUtiles.has(rel));
if (inutiles.length > 0) {
	console.error(
		'\n✗ Exception(s) devenue(s) inutile(s) — le formulaire est rentré dans sa section :\n' +
			inutiles.map((f) => `    ${f} — « ${EXCEPTIONS[f]} »`).join('\n') +
			'\n  Les retirer d’EXCEPTIONS : une dérogation oubliée est une porte qu’on croit fermée.\n',
	);
	process.exit(1);
}

if (fautifs.length > 0) {
	console.error(
		`\n✗ ${fautifs.length} page(s) rendent un formulaire hors de sa section :\n\n` +
			fautifs.join('\n\n') +
			`\n\n  Règle signalée à l'écran le 08/09/2026 (#852) : le formulaire s'ouvre LÀ\n` +
			`  où le geste a été fait. Le rendre dans la section — un slot \`formulaire\`\n` +
			`  sur le composant de section, ou le balisage à l'intérieur du \`<section>\`.\n\n` +
			`  Une exception réelle se déclare dans EXCEPTIONS, avec sa raison.\n`,
	);
	process.exit(1);
}

console.log(
	`✓ Formulaires dans leur section : ${pagesAvecSections} page(s) à sections vérifiée(s), ` +
		`${Object.keys(EXCEPTIONS).length} exception(s) déclarée(s).`,
);
