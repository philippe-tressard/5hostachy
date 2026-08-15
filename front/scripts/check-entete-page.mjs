/**
 * Garde-fou : l'en-tête d'une page s'écrit d'UNE seule façon — `EntetePage`.
 *
 * ## Pourquoi ce contrôle existe (#363, 15/08/2026)
 *
 * L'en-tête était écrit de douze façons. `.page-header` vit dans `app.css`, et
 * pourtant **six pages le redéfinissaient en CSS local** et **six autres le
 * surchargeaient en ligne** — dont quatre en réécrivant `justify-content:
 * space-between`, la valeur que le global portait déjà. Le style du `<h1>` était
 * recopié **en ligne dans onze pages**.
 *
 * Le défaut visible : `tickets/nouveau` réécrivait `.page-header` avec
 * `display:flex; align-items:center; gap:1rem` — un groupe serré à gauche, dit
 * l'intention — sans redéclarer le `justify-content` du global, dont elle héritait
 * donc en silence. Le titre partait à l'autre bout de l'écran. Seul écran du site
 * dans ce cas, et personne ne l'avait voulu.
 *
 * C'est le « piège de l'héritage partiel » de `standards/11-interface-et-ux.md`
 * §1 bis. Une consigne ne suffit pas : la douzième page l'a enfreinte alors que la
 * règle globale existait déjà. D'où ce contrôle.
 *
 * ## Ce qui est interdit dans `routes/`
 *
 *   1. rendre `class="page-header"` à la main — passer par `<EntetePage>` ;
 *   2. redéfinir `.page-header` en CSS local — la règle vit dans `app.css` ;
 *   3. un `<h1>` qui porte `font-size` en ligne — le composant le porte.
 *
 * Le contrôle s'auto-contrôle : si le composant disparaît, change de props ou
 * n'est plus employé, il ÉCHOUE au lieu de conclure au vert
 * (`standards/04-fiabilite-des-controles.md` §2, cas zéro).
 */
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, relative, sep } from 'node:path';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const ROUTES = join(RACINE, 'routes');
const COMPOSANT = join(RACINE, 'lib', 'components', 'EntetePage.svelte');
const APP_CSS = join(RACINE, 'app.css');

/**
 * Emplois légitimes de `.page-header` hors du composant, avec leur raison.
 *
 * Une tolérance sans raison devient un dépotoir : chacune est nommée, et le
 * contrôle échoue si l'une cesse de servir.
 */
const EXCEPTIONS = {
	//  Pas d'exception pour la règle d'impression d'`espace-cs`
	//  (`:global(body.print-reporting .page-header)`) : le motif ne la voit pas, et
	//  c'est voulu — elle vise le composant depuis l'extérieur pour masquer l'en-tête
	//  sur le rapport papier, elle ne redéfinit pas la mise en page de l'écran. Une
	//  tolérance inutile aurait été refusée par le contrôle lui-même, plus bas.
	'(app)/tickets/[id]/+page.svelte':
		"le `<h1>` y est le titre du TICKET, à l'intérieur de sa carte — pas l'en-tête " +
		"de la page, qui n'existe pas sur cet écran (il n'a qu'un `.back-link` flottant). " +
		'Lui en donner un est une décision de mise en page — instruit dans #365',
	'(app)/sondages/[id]/+page.svelte':
		'même cas : le `<h1>` porte la question du sondage, dans sa carte — instruit dans #365',
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
const composant = readFileSync(COMPOSANT, 'utf8');
const props = ['titre', 'icone', 'retour', 'marge'];
const absentes = props.filter((p) => !new RegExp(`export let ${p}\\b`).test(composant));
if (absentes.length > 0) {
	console.error(
		`✗ Cas zéro : EntetePage n'expose plus ${absentes.join(', ')}. Le contrat a changé — ` +
			'mettre ce contrôle à jour, sinon il laisse passer les en-têtes écrits à la main.',
	);
	process.exit(1);
}
if (!existsSync(APP_CSS) || !/^\.page-header\s*\{/m.test(readFileSync(APP_CSS, 'utf8'))) {
	console.error(
		"✗ Cas zéro : `app.css` ne porte plus la règle `.page-header`. Elle a déménagé, et " +
			"interdire les redéfinitions locales n'aurait plus de sens.",
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
		//  `(?![-\w])` : sans lui, `page-header-btn` — la classe du bouton d'action,
		//  parfaitement légitime — serait pris pour le conteneur. Un contrôle qui crie
		//  sur du légitime finit désarmé.
		regex: /class="[^"]*\bpage-header(?![-\w])/g,
		quoi: "l'en-tête est rendu à la main",
		remede: '<EntetePage titre={…} icone={…} retour="/…"> … </EntetePage>',
	},
	{
		regex: /^[\t ]*\.page-header[\s.,:[{]/gm,
		quoi: '`.page-header` est redéfini en CSS local',
		remede: "la règle vit dans `app.css` — n'écrire ici que ce qu'elle ne dit pas",
	},
	{
		regex: /<h1[^>]*style="[^"]*font-size/g,
		quoi: 'le style du titre est écrit en ligne',
		remede: 'le composant porte la taille et la graisse du titre',
	},
];

const fautifs = [];
const exceptionsUtiles = new Set();
let pagesAvecEntete = 0;

for (const f of tous) {
	const rel = relative(ROUTES, f).split(sep).join('/');
	const brut = readFileSync(f, 'utf8');
	if (brut.includes('<EntetePage')) pagesAvecEntete++;
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

//  Le composant peut exister, être conforme, et n'être employé nulle part : le
//  contrôle serait alors vert sur un site qui aurait tout réécrit à la main.
if (pagesAvecEntete === 0) {
	console.error(
		"✗ Cas zéro : aucune page n'utilise <EntetePage>. Le composant existe mais ne sert " +
			'plus — ce contrôle ne mesure alors plus rien.',
	);
	process.exit(1);
}

if (fautifs.length > 0) {
	console.error("✗ En-tête(s) de page écrit(s) hors du composant :");
	for (const { fichier, trouves } of fautifs) {
		for (const t of trouves) {
			console.error(`    ${fichier} — ${t.exemples.join(' · ')}`);
			console.error(`        ${t.quoi}`);
			console.error(`        → ${t.remede}`);
		}
	}
	console.error(
		"\n  Redéfinir localement une règle globale sans redéclarer TOUS ses champs n'annule\n" +
			"  pas le global : on en hérite en silence. C'est ainsi que le titre de « Nouveau\n" +
			'  ticket » se retrouvait à droite de l\'écran (#363).',
	);
	process.exit(1);
}

const inutiles = Object.keys(EXCEPTIONS).filter((f) => !exceptionsUtiles.has(f));
if (inutiles.length > 0) {
	console.error("✗ Exception(s) devenue(s) inutile(s) :");
	for (const f of inutiles) console.error(`    ${f} — retirer l'entrée de EXCEPTIONS`);
	process.exit(1);
}

console.log(
	`✓ En-têtes : ${pagesAvecEntete} page(s) passent par EntetePage, ${tous.length} page(s) ` +
		`vérifiée(s), ${Object.keys(EXCEPTIONS).length} exception(s) déclarée(s) et justifiée(s).`,
);
