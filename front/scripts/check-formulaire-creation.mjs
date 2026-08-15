/**
 * Garde-fou : un formulaire de création s'écrit d'UNE seule façon.
 *
 * ## Pourquoi (#367, 15/08/2026)
 *
 * Le produit offrait **trois paradigmes** pour la même intention — créer un objet :
 * une boîte dans la page (actualités, sondages), une modale (calendrier,
 * prestataires — avec deux largeurs différentes), une page dédiée (nouveau
 * ticket). Un résident qui publie une actualité, ouvre un ticket et propose un
 * événement faisait trois gestes différents.
 *
 * Signalé **trois fois** par l'utilisateur avant d'être traité. Les deux premiers
 * lots (#361 largeur de saisie, #363 en-tête de page) avaient corrigé des
 * symptômes périphériques sans jamais ouvrir le formulaire lui-même.
 *
 * Le paradigme retenu est la **boîte dans la page**, sur désignation de
 * l'utilisateur : les actualités sont le modèle.
 *
 * ## Ce qui est interdit dans `routes/`
 *
 *   1. `class="card largeur-saisie"` écrit à la main — passer par
 *      `<FormulaireCreation titre="…">` ;
 *   2. un `<h2>` de titre de formulaire portant `font-size` en ligne — le
 *      composant le porte.
 *
 * Le contrôle s'auto-contrôle : composant absent, prop disparue ou plus aucune
 * page utilisatrice → il ÉCHOUE au lieu de conclure au vert
 * (`standards/04-fiabilite-des-controles.md` §2, cas zéro).
 */
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, relative, sep } from 'node:path';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const ROUTES = join(RACINE, 'routes');
const COMPOSANT = join(RACINE, 'lib', 'components', 'FormulaireCreation.svelte');

/**
 * Emplois légitimes hors du composant, avec leur raison.
 *
 * Une tolérance sans raison devient un dépotoir : chacune est nommée, et le
 * contrôle échoue si l'une cesse de servir.
 */
const EXCEPTIONS = {
	'(app)/prestataires/+page.svelte':
		'quatre formulaires encore en MODALE, dans un fichier de 2 182 lignes qui doit ' +
		"d'abord être découpé. S'y ajoute un écart de fond : le périmètre y est une " +
		'CHAÎNE dans un `<select>`, là où `PerimetrePicker` travaille sur un tableau — ' +
		"c'est un changement de contrat, pas un remplacement de composant. Instruit dans #367",
};

/** Retire commentaires et balisage commenté : expliquer la règle ne doit pas l'enfreindre. */
function sansCommentaires(texte) {
	return texte
		.replace(/<!--[\s\S]*?-->/g, '')
		.replace(/\/\*[\s\S]*?\*\//g, '')
		.replace(/(^|[^:'"`\\])\/\/[^\n]*/g, '$1');
}

function fichiers(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...fichiers(chemin));
		else if (nom.endsWith('.svelte')) sortie.push(chemin);
	}
	return sortie;
}

//  ── Auto-contrôle (cas zéro) ────────────────────────────────────────────────
if (!existsSync(COMPOSANT)) {
	console.error(`✗ Cas zéro : ${COMPOSANT} est introuvable — contrôle inopérant.`);
	process.exit(1);
}
if (!/export let titre\b/.test(readFileSync(COMPOSANT, 'utf8'))) {
	console.error(
		"✗ Cas zéro : FormulaireCreation n'expose plus `titre`. Le contrat a changé — " +
			'mettre ce contrôle à jour, sinon il laisse passer les formulaires écrits à la main.',
	);
	process.exit(1);
}

const tous = fichiers(ROUTES);
if (tous.length === 0) {
	console.error("✗ Cas zéro : aucune page analysée — l'arborescence a changé.");
	process.exit(1);
}

//  ── Recherche ───────────────────────────────────────────────────────────────
const MOTIFS = [
	{
		//  Le cadre N'EST fautif que s'il enveloppe un `<form>` : `card largeur-saisie`
		//  sert aussi, légitimement, à des cartes de LECTURE (les lots de `mon-lot`,
		//  par exemple, qui n'ont rien d'un formulaire). Sans cette condition, le
		//  contrôle criait sur elles — et un contrôle qui crie sur du légitime finit
		//  désarmé.
		regex: /class="[^"]*\bcard\b[^"]*\blargeur-saisie\b[^"]*"[\s\S]{0,400}?<form/g,
		quoi: 'un cadre de formulaire est rendu à la main',
		remede: '<FormulaireCreation titre="…"> … </FormulaireCreation>',
	},
	{
		//  Le paradigme à éliminer. Une modale qui enveloppe un `<form>` EST un
		//  formulaire de création déguisé — c'est ce que faisaient le calendrier et
		//  prestataires. Les modales de confirmation, d'upload ponctuel ou la
		//  visionneuse n'ont pas de `<form>` et ne sont pas visées.
		regex: /class="[^"]*\bmodal-overlay\b[^"]*"[\s\S]{0,900}?<form/g,
		quoi: 'un formulaire est rendu dans une MODALE',
		remede: 'une boîte dans la page — <FormulaireCreation titre="…">',
	},
	//  Pas de motif sur `<h2 style="font-size…">`. Il avait été écrit, et il criait
	//  sur neuf pages dont sept portaient un titre de SECTION parfaitement légitime
	//  (admin, espace-cs, faq, profil, fiches de ticket et de sondage). Rien dans le
	//  balisage ne distingue un titre de formulaire d'un titre de section — et un
	//  contrôle qui crie sur du légitime finit désarmé, c'est la leçon de C16.
	//  L'uniformisation des titres de section est un autre sujet, qui aura son
	//  propre invariant le jour où il sera tranché.
];

const fautifs = [];
const exceptionsUtiles = new Set();
let pagesAvecFormulaire = 0;

for (const f of tous) {
	const rel = relative(ROUTES, f).split(sep).join('/');
	const brut = readFileSync(f, 'utf8');
	if (brut.includes('<FormulaireCreation')) pagesAvecFormulaire++;
	const contenu = sansCommentaires(brut);
	const trouves = [];
	for (const motif of MOTIFS) {
		const m = contenu.match(motif.regex);
		if (m) trouves.push({ ...motif, exemples: [...new Set(m.map((s) => s.trim()))].slice(0, 2) });
	}
	if (trouves.length === 0) continue;
	if (rel in EXCEPTIONS) {
		exceptionsUtiles.add(rel);
		continue;
	}
	fautifs.push({ fichier: rel, trouves });
}

//  Le composant peut exister, être conforme, et n'être employé nulle part.
if (pagesAvecFormulaire === 0) {
	console.error(
		"✗ Cas zéro : aucune page n'utilise <FormulaireCreation>. Le composant existe mais " +
			'ne sert plus — ce contrôle ne mesure alors plus rien.',
	);
	process.exit(1);
}

if (fautifs.length > 0) {
	console.error('✗ Formulaire(s) de création écrit(s) hors du composant :');
	for (const { fichier, trouves } of fautifs) {
		for (const t of trouves) {
			console.error(`    ${fichier} — ${t.exemples.join(' · ')}`);
			console.error(`        ${t.quoi}`);
			console.error(`        → ${t.remede}`);
		}
	}
	console.error(
		'\n  Trois paradigmes de création coexistaient pour la même intention, et il a fallu\n' +
			"  que l'utilisateur le signale trois fois. Un seul est retenu : la boîte dans la\n" +
			'  page, dont les actualités sont le modèle (#367).',
	);
	process.exit(1);
}

const inutiles = Object.keys(EXCEPTIONS).filter((f) => !exceptionsUtiles.has(f));
if (inutiles.length > 0) {
	console.error('✗ Exception(s) devenue(s) inutile(s) :');
	for (const f of inutiles) console.error(`    ${f} — retirer l'entrée de EXCEPTIONS`);
	process.exit(1);
}

console.log(
	`✓ Formulaires : ${pagesAvecFormulaire} page(s) passent par FormulaireCreation, ` +
		`${tous.length} page(s) vérifiée(s), ${Object.keys(EXCEPTIONS).length} exception(s) justifiée(s).`,
);
