/**
 * Garde-fou — **une classe employée par un composant doit être définie quelque part.**
 *
 * ## Pourquoi (19/08/2026, et c'est la quatrième fois)
 *
 * Svelte scope ses styles au FICHIER. Déplacer du balisage d'un fichier à un
 * autre sans emporter ses règles produit un écran **nu** : la page compile, les
 * types passent, le build ne dit rien, et l'utilisateur voit du texte brut.
 *
 * Ce dépôt cite cette régression dans une dizaine de commentaires depuis la
 * v2.67.11 — les pastilles parties nues en production, qui ont fait créer
 * `Pastille.svelte`. La règle « le style part AVEC le balisage » est écrite dans
 * `ux-patterns`, dans `app.css`, dans les commentaires de quatre composants.
 *
 * **Elle a été enfreinte trois fois de plus le même jour, par la même main.**
 *
 *   • `OngletTelemetrie` — extrait d'`admin/+page.svelte` en v2.95.0, ses dix-sept
 *     règles restées derrière. Panneau nu EN PRODUCTION : KPI empilés en texte
 *     brut, graphe rendu en colonne de chiffres. Signalé à l'écran, capture à
 *     l'appui, par l'utilisateur ;
 *   • `OngletModelesEmail` — la boîte de dialogue et l'aperçu, même cause ;
 *   • `OngletSmtp` — le champ de test, même cause.
 *
 * Et avant elles, deux découvertes du même jour : `OngletWhatsApp` (extrait
 * d'`admin` sans ses styles, six libellés et une grille nus depuis des semaines)
 * et `acces-securite` (dont le formulaire n'était pas une grille).
 *
 * 🔴 **Une règle qu'on écrit et qui n'échoue nulle part ne protège rien.** C'est
 * le principe de `standards/05` §1, et la démonstration a coûté une régression en
 * production.
 *
 * ## Pourquoi `svelte-check` ne suffit pas
 *
 * Il signale l'autre bout : `Unused CSS selector`, une règle qui ne matche rien.
 * Sur les dix-sept règles orphelines laissées dans `admin/+page.svelte`, **il en a
 * signalé UNE**. Il regarde le fichier qui garde la règle, pas celui qui a perdu
 * le style — et sa détection est partielle. Ce contrôle-ci prend le problème par
 * le côté qui se voit à l'écran.
 *
 * ## Deux volets, une seule notion : la PORTÉE d'une définition CSS
 *
 * ### Volet A — une classe employée doit être définie LÀ OÙ ELLE EST EMPLOYÉE
 *
 * Toute classe écrite dans le balisage d'un composant, qui n'est définie **ni**
 * dans son propre `<style>`, **ni** dans le CSS global (`app.css` + `styles/`).
 *
 * ### Volet B — une définition ne déborde pas sur le reste du site
 *
 * Un `:global(.x)` de **premier niveau** dans un composant, quand `.x` est déjà
 * portée par le CSS global : c'est une redéfinition de la charte, écrite depuis
 * un écran, qui s'applique à tous les autres.
 *
 * ## Pourquoi le volet B a été ajouté (#562, 28/08/2026)
 *
 * 🔴 **Le volet A demandait la mauvaise question, et elle avait un nom trompeur.**
 * Il acceptait qu'une classe soit fournie par le `:global(…)` de **n'importe quel
 * autre fichier du dépôt** — un sac où tout se valait. Or Svelte n'y met aucune
 * barrière et SvelteKit charge la CSS **à la visite** de la page : une règle
 * écrite dans une page ne protège aucune autre page tant qu'on n'y est pas passé,
 * et **continue** de s'appliquer partout une fois qu'on y est passé.
 *
 * Le sac ne servait à personne : le relevé du 28/08/2026 n'a trouvé **aucune**
 * classe qui en dépendait. Il ne couvrait donc rien — il masquait. Retiré.
 *
 * Ce qu'il masquait, le volet B le nomme : **huit** `:global(.badge-*)` écrits
 * dans quatre pages, redéfinissant les couleurs de la charte de `composants.css`
 * avec d'autres valeurs. Conséquence à l'écran : la teinte d'un badge dépendait
 * des pages **déjà visitées dans la session**. Le fichier `tickets/+page.svelte`
 * portait le diagnostic écrit en commentaire depuis #431 — la règle est restée.
 *
 * ⚠️ Une règle décrite dans un commentaire n'est pas un garde-fou : elle a été
 * lue, comprise, laissée en place, et rien n'a échoué (`standards/05` §1).
 *
 * ## Ce qui reste autorisé, et pourquoi
 *
 * `:global(.custom-content p)`, `:global(.rich-content-editable .tiptap)` — le
 * HTML **injecté** par un éditeur riche, qu'aucune règle scopée ne peut atteindre
 * puisque Svelte ne connaît pas ce balisage à la compilation. Le volet B ne vise
 * que le sélecteur réduit à **une classe seule**, donc à une pure redéfinition.
 *
 * ⚠️ La logique de lecture des `:global(…)` vit dans `lib-analyse-styles.mjs`, et
 * c'est là qu'elle s'éprouve : `node scripts/lib-analyse-styles.mjs --selftest`.
 * Ce module exposait un `--selftest` que **rien ne lançait** — ni la CI, ni
 * `rejouer-ci.sh` — alors qu'il porte les fonctions pures de deux contrôles.
 * Ajouté au job « Auto-tests des garde-fous du front » le 28/08/2026.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { cssGlobal, fichiersCssGlobal } from './lib-css-global.mjs';
import { globalesDeFeuille } from './lib-analyse-styles.mjs';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');

/**
 * Classes employées sans définition, **avec la raison**.
 *
 * ⚠️ Une entrée qui ne sert plus fait échouer le contrôle : une dérogation
 * oubliée est une porte qu'on croit fermée. La liste ne peut donc que décroître —
 * le jour où l'une de ces zones reçoit son style, le contrôle exige son retrait.
 *
 * ## Comment on est passé de 54 à 5 (#495)
 *
 * **34 réparations mécaniques** — une variante inexistante remplacée par celle qui
 * existe (`.btn-secondary` → `.btn-outline`, `.badge-success` → `.badge-green`…),
 * une notion partagée promue dans `app.css`.
 *
 * **15 crochets MORTS retirés du balisage.** Vérifiés un par un : leur élément
 * était déjà stylé par une classe voisine, ou l'état qu'ils nommaient est rendu
 * autrement. 🔴 Le cas exemplaire est `epingle` : une actualité épinglée **se
 * voit** — badge 📌 sur la carte et rubrique « 📌 Épinglé » du tableau de bord,
 * rendu validé à l'écran le 19/08/2026. La classe sur le conteneur ne portait
 * aucune règle ; elle faisait croire à un accroche-style qui n’existait pas.
 *
 * ⚠️ **La leçon** : « classe sans définition » ne veut pas dire « intention
 * perdue ». Il faut regarder si l'état est rendu AILLEURS avant de conclure —
 * je l'avais d'abord classé à l'inverse, et l'écran m'a détrompé.
 *
 * **Les 5 qui restent** sont de vraies zones sans style, à trancher à l'écran.
 */
const TOLEREES = {
	//  Le libellé d’une entrée de navigation : sa mise en forme vient du `<a>`
	//  parent. Le crochet est inoffensif, mais il attend sa règle ou son retrait.
	'lib/components/Nav.svelte': ['nav-label'],
	//  🔴 La carte « nouvel arrivant » COCHÉE ne se distingue pas de la décochée :
	//  le `class:` est posé, la règle n’existe pas.
	'routes/(app)/admin/+page.svelte': ['nouvel-arrivant-checked'],
	//  Les libellés de mois de la frise, rendus en texte courant.
	//  Suivi la frise dans `VueRenouvellements` en extrayant le reporting (#453),
	//  puis dans `VueRenouvellementsContrats` en découpant celui-ci (27/08/2026).
	//  ⚠️ Une tolérance suit le BALISAGE qu'elle décrit, jamais le nom du fichier :
	//  ce contrôle a échoué au découpage parce qu'elle était restée sur l'ancien,
	//  et c'est la bonne façon d'échouer — l'entrée devenue inutile fait échouer.
	'lib/components/reporting/VueRenouvellementsContrats.svelte': ['frise-month-label'],
	//  🔴 La notation par étoiles : `class:active` sur chaque étoile, et aucune
	//  règle — l’étoile choisie ne se distingue pas de celle qu’on n’a pas prise.
	'routes/(app)/prestataires/+page.svelte': ['star-btn'],
	//  ⚠️ `ListeSondages` → `sondage-body` A DISPARU le 06/09/2026 : la carte est
	//  passée à `EnteteCarte` (#794) et n'a plus de conteneur de corps. Le
	//  contrôle l'a signalée comme tolérance morte le jour même — c'est la
	//  seconde fois que cette entrée échoue en disant la vérité, après son
	//  déplacement du 02/09. Une tolérance qui ne sert plus finit par en couvrir
	//  une qui compte.
};

/** Un composant sans aucune classe reconnue signalerait une analyse cassée. */
const CLASSES_MINIMALES = 400;

function composants(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...composants(chemin));
		else if (nom.endsWith('.svelte')) sortie.push(chemin);
	}
	return sortie;
}

const fichiers = composants(RACINE);
if (fichiers.length === 0) {
	console.error("✗ Cas zéro : aucun composant analysé — l'arborescence a changé.");
	process.exit(1);
}

// ── 1. Ce qui est défini globalement ─────────────────────────────────────────
let global;
try {
	//  `app.css` ne porte plus de règle : il importe `styles/*.css` (#453). Le
	//  module lit l'ensemble, donc ajouter un fragment ne demande rien ici.
	global = cssGlobal(RACINE);
} catch {
	console.error('✗ INCONNU : le CSS global est illisible — ce contrôle ne conclut pas.');
	process.exit(1);
}
/**
 * Le CSS SANS ses commentaires.
 *
 * 🔴 Trouvé le 29/08/2026 en retirant `.pill` de la charte (#491). Les
 * commentaires étaient déjà décapés du côté EMPLOYÉ (le balisage, plus bas) mais
 * PAS du côté DÉFINI : un commentaire qui cite `.pill` pour expliquer qu'on l'a
 * retirée la faisait passer pour définie. Le contrôle restait vert sur un
 * `class="pill"` réintroduit — c'est-à-dire exactement l'écran nu qu'il existe
 * pour empêcher.
 *
 * ⚠️ L'asymétrie est le vrai défaut : décaper d'un seul côté produit un FAUX
 * VERT, et c'est le côté dangereux. Ce dépôt écrit de longs commentaires qui
 * citent le vocabulaire qu'ils retirent — plus il documente, plus il s'aveuglait.
 */
function sansCommentairesCss(css) {
	return css.replace(/\/\*[\s\S]*?\*\//g, ' ');
}

const definiesGlobal = new Set(
	[...sansCommentairesCss(global).matchAll(/\.([a-zA-Z][\w-]*)/g)].map((m) => m[1]),
);
if (definiesGlobal.size === 0) {
	console.error(
		`✗ Cas zéro : aucune classe trouvée dans ${fichiersCssGlobal(RACINE).join(', ') || '(aucun fichier)'}.`,
	);
	process.exit(1);
}

// ── 2. Le relevé ─────────────────────────────────────────────────────────────
const erreurs = [];
const fuites = [];
const toleranceServies = new Set();
let employeesTotal = 0;

for (const chemin of fichiers) {
	const relatif = relative(RACINE, chemin).replace(/\\/g, '/');
	const source = readFileSync(chemin, 'utf8');

	const style = (source.match(/<style[^>]*>([\s\S]*?)<\/style>/) || ['', ''])[1];
	//  Commentaires retirés ici AUSSI : un composant qui explique pourquoi il
	//  n'emploie pas une classe la ferait passer pour définie chez lui.
	const definiesLocal = new Set(
		[...sansCommentairesCss(style).matchAll(/\.([a-zA-Z][\w-]*)/g)].map((m) => m[1]),
	);

	//  Volet B — une définition qui déborde. Seule la fuite réduite à UNE classe
	//  déjà portée par la charte est refusée : c'est une redéfinition, pas un
	//  besoin. Voir `globalesDeFeuille` pour les trois formes et leurs portées.
	for (const { selecteur, classeSeule } of globalesDeFeuille(style).fuites) {
		if (classeSeule && definiesGlobal.has(classeSeule)) fuites.push(`${relatif} — ${selecteur}`);
	}

	//  Les COMMENTAIRES sont retirés : ce dépôt en écrit de longs, qui citent le
	//  balisage qu'ils interdisent — `FormulaireAnnonceHall` explique pourquoi il
	//  n'emploie PAS `<button class="pill">`. Les lire comme du balisage produit un
	//  faux positif, et un garde-fou qui crie sur du légitime finit désarmé.
	const gabarit = source
		.replace(/<script[\s\S]*?<\/script>/g, '')
		.replace(/<style[\s\S]*?<\/style>/g, '')
		.replace(/<!--[\s\S]*?-->/g, '');

	//  `class="a b"` littéral, et `class:x={…}`. Les classes calculées
	//  (`class="{expr}"`) ne sont PAS lues : on ne devine pas une expression.
	const employees = new Set();
	for (const m of gabarit.matchAll(/class="([^"{]*)"/g)) {
		for (const c of m[1].split(/\s+/)) if (c) employees.add(c);
	}
	for (const m of gabarit.matchAll(/class:([\w-]+)/g)) employees.add(m[1]);
	employeesTotal += employees.size;

	const tolerees = TOLEREES[relatif] ?? [];
	for (const c of employees) {
		if (definiesLocal.has(c) || definiesGlobal.has(c)) continue;
		if (tolerees.includes(c)) {
			toleranceServies.add(`${relatif}::${c}`);
			continue;
		}
		erreurs.push(`${relatif} — .${c}`);
	}
}

if (employeesTotal < CLASSES_MINIMALES) {
	console.error(
		`✗ Cas zéro : ${employeesTotal} classe(s) employée(s) relevée(s), ${CLASSES_MINIMALES} attendues au minimum.`,
	);
	console.error(
		'Le front en portait plus de 900 le 19/08/2026. Un effondrement du relevé dit\n' +
			'que le contrôle a cessé de voir, pas que le défaut a disparu.',
	);
	process.exit(1);
}

const mortes = Object.entries(TOLEREES).flatMap(([f, cs]) =>
	cs.filter((c) => !toleranceServies.has(`${f}::${c}`)).map((c) => `${f} — .${c}`),
);
if (mortes.length) {
	console.error('✗ Tolérance(s) qui ne servent plus — les retirer :\n');
	for (const m of mortes) console.error(`  • ${m}`);
	process.exit(1);
}

if (erreurs.length) {
	console.error('✗ Classe(s) employée(s) sans aucune définition — l’écran sera NU :\n');
	for (const e of erreurs) console.error(`  • ${e}`);
	console.error(
		'\n🔴 Svelte scope ses styles au FICHIER. Une classe écrite ici doit être définie\n' +
			'   ICI, ou dans le CSS global (`app.css` + `styles/`). Le `:global(…)` d’un AUTRE\n' +
			'   fichier ne compte pas : sa feuille n’est chargée qu’avec lui (#562).\n\n' +
			'   Le cas le plus fréquent est un DÉPLACEMENT de balisage : le style est resté\n' +
			'   dans le fichier d’origine. Il part AVEC le balisage — c’est la régression des\n' +
			'   pastilles nues (v2.67.11), et elle s’est reproduite trois fois le 19/08/2026,\n' +
			'   dont une constatée en production par l’utilisateur.\n\n' +
			'   Une notion PARTAGÉE par plusieurs écrans se remonte dans `src/styles/` — c’est\n' +
			'   ce qui a été fait pour `.text-muted-sm`, définie dans une page et employée par\n' +
			'   quatre autres, qui la rendaient nue (#557).\n\n' +
			'   Si la classe est portée par une bibliothèque tierce, la déclarer dans\n' +
			'   `TOLEREES` avec sa raison.\n',
	);
	process.exit(1);
}

if (fuites.length) {
	console.error(
		'✗ Redéfinition(s) de la charte depuis un écran — elles débordent sur tout le site :\n',
	);
	for (const f of fuites) console.error(`  • ${f}`);
	console.error(
		'\n🔴 Un `:global(.x)` de PREMIER NIVEAU n’est pas scopé, et SvelteKit charge la\n' +
			'   feuille d’une page à la VISITE sans la décharger ensuite. Quand `.x` est déjà\n' +
			'   portée par le CSS global, la teinte vue par le résident dépend donc des pages\n' +
			'   par lesquelles il est passé — huit `:global(.badge-*)` faisaient exactement\n' +
			'   cela dans quatre écrans (#562).\n\n' +
			'   Le geste : SUPPRIMER la règle et laisser la charte de `styles/composants.css`\n' +
			'   s’appliquer. Si la teinte doit vraiment différer, c’est une VARIANTE — elle se\n' +
			'   nomme et se définit dans `styles/`, pas en écrasant la classe commune.\n\n' +
			'   Reste autorisé : un `:global(…)` IMBRIQUÉ sous un ancêtre scopé, et un\n' +
			'   `:global(…)` qui vise du HTML injecté (`.custom-content p`, `.tiptap`) —\n' +
			'   aucune règle scopée ne peut atteindre un balisage que Svelte ne compile pas.\n',
	);
	process.exit(1);
}

console.log(
	`✓ Classes : ${employeesTotal} employées dans ${fichiers.length} composants — ` +
		`toutes définies, ${Object.keys(TOLEREES).length} tolérance(s) déclarée(s) et servie(s), ` +
		'aucune redéfinition de la charte depuis un écran.',
);
