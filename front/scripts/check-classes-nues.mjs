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
 * ## Ce qu'il cherche
 *
 * Toute classe écrite dans le balisage d'un composant, qui n'est définie **ni**
 * dans son propre `<style>`, **ni** dans `app.css`, **ni** en `:global(…)` par un
 * autre composant.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');

/**
 * Classes employées sans définition, **avec la raison**.
 *
 * ⚠️ Une entrée qui ne sert plus fait échouer le contrôle : une dérogation
 * oubliée est une porte qu'on croit fermée.
 */
const TOLEREES = {};

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
	global = readFileSync(join(RACINE, 'app.css'), 'utf8');
} catch {
	console.error('✗ INCONNU : `app.css` est illisible — ce contrôle ne conclut pas.');
	process.exit(1);
}
const definiesGlobal = new Set([...global.matchAll(/\.([a-zA-Z][\w-]*)/g)].map((m) => m[1]));
if (definiesGlobal.size === 0) {
	console.error('✗ Cas zéro : aucune classe trouvée dans `app.css`.');
	process.exit(1);
}

//  Les classes qu'un composant expose en `:global(…)` pour ses enfants.
const globalesDeComposants = new Set();
for (const f of fichiers) {
	for (const m of readFileSync(f, 'utf8').matchAll(/:global\(([^)]*)\)/g)) {
		for (const c of m[1].matchAll(/\.([a-zA-Z][\w-]*)/g)) globalesDeComposants.add(c[1]);
	}
}

// ── 2. Le relevé ─────────────────────────────────────────────────────────────
const erreurs = [];
const toleranceServies = new Set();
let employeesTotal = 0;

for (const chemin of fichiers) {
	const relatif = relative(RACINE, chemin).replace(/\\/g, '/');
	const source = readFileSync(chemin, 'utf8');

	const style = (source.match(/<style[^>]*>([\s\S]*?)<\/style>/) || [, ''])[1];
	const definiesLocal = new Set([...style.matchAll(/\.([a-zA-Z][\w-]*)/g)].map((m) => m[1]));

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
		if (definiesLocal.has(c) || definiesGlobal.has(c) || globalesDeComposants.has(c)) continue;
		if (tolerees.includes(c)) { toleranceServies.add(`${relatif}::${c}`); continue; }
		erreurs.push(`${relatif} — .${c}`);
	}
}

if (employeesTotal < CLASSES_MINIMALES) {
	console.error(
		`✗ Cas zéro : ${employeesTotal} classe(s) employée(s) relevée(s), ${CLASSES_MINIMALES} attendues au minimum.`,
	);
	console.error(
		"Le front en portait plus de 900 le 19/08/2026. Un effondrement du relevé dit\n" +
			"que le contrôle a cessé de voir, pas que le défaut a disparu.",
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
			'   ici, dans `app.css`, ou exposée en `:global(…)` par un composant.\n\n' +
			'   Le cas le plus fréquent est un DÉPLACEMENT de balisage : le style est resté\n' +
			'   dans le fichier d’origine. Il part AVEC le balisage — c’est la régression des\n' +
			'   pastilles nues (v2.67.11), et elle s’est reproduite trois fois le 19/08/2026,\n' +
			'   dont une constatée en production par l’utilisateur.\n\n' +
			'   Si la classe est portée par une bibliothèque tierce, la déclarer dans\n' +
			'   `TOLEREES` avec sa raison.\n',
	);
	process.exit(1);
}

console.log(
	`✓ Classes : ${employeesTotal} employées dans ${fichiers.length} composants — ` +
		`toutes définies, ${Object.keys(TOLEREES).length} tolérance(s) déclarée(s) et servie(s).`,
);
