#!/usr/bin/env node
/**
 *  Une couleur et une taille de texte se lisent dans la charte, pas en dur
 *  (#1055, 27/09/2026).
 *
 *  ## Pourquoi
 *
 *  `styles/socle.css` définit la charte — couleurs, et depuis #1055 une échelle
 *  typographique (`--fs-*`). Les écrans l'ignoraient : 265 couleurs et 566
 *  tailles de texte écrites en dur dans leurs `<style>` et leurs `style="…"`,
 *  dont 42 valeurs de taille différentes. Chaque changement de charte demandait
 *  donc de rouvrir cinquante fichiers — et `lint:charte` comme `lint:css-duplique`
 *  contrôlent des RÈGLES et des CLASSES, jamais des VALEURS : ils ne voyaient rien.
 *
 *  ## Ce qu'il mesure
 *
 *  Dans les fichiers `.svelte` (les feuilles de `src/styles/` sont la charte,
 *  elles sont hors relevé) : les couleurs hexadécimales et les `font-size` en
 *  `rem`, dans les blocs `<style>` et les attributs `style="…"`, commentaires
 *  retirés.
 *
 *  ## Un PLAFOND, et il ne fait que baisser
 *
 *  Tout convertir d'un coup changerait des rendus avant qu'on en ait regardé un
 *  seul (R5 du cadre #430). Le plafond empêche d'en AJOUTER ; il échoue aussi
 *  quand le compte passe DESSOUS — le plafond se baisse alors dans le même lot,
 *  sinon la marge regagnée serait reprise sans un mot par le suivant.
 *
 *  Lancer : node scripts/check-charte-valeurs.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 *  Le compte autorisé, et son historique : c'est lui qui dit à quel rythme la
 *  dette se solde.
 *  27/09/2026 (#1055) : relevé 266 couleurs, 569 tailles → 235 et 258 dans le
 *  même lot, en convertissant les seules valeurs ÉGALES à un jeton (aucun rendu
 *  changé ; un repli redondant `var(--x, #valeur-de-x)` compte parmi elles).
 *  27/09/2026, même jour, après arbitrage sur maquette : 124 et 62 — les
 *  tailles hors échelle rangées au cran supérieur, les couleurs d'état de
 *  Tailwind remplacées par la charte (voir « Ce qui est INTERDIT »).
 */
const PLAFOND = { couleurs: 124, tailles: 62 };

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..', 'src');

/** Le CSS d'un composant : ses blocs `<style>` et ses attributs `style="…"`. */
export function stylesDe(source) {
	const sans = source.replace(/<!--[\s\S]*?-->/g, '');
	const blocs = [...sans.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map((m) => m[1]);
	const attributs = [...sans.matchAll(/\bstyle="([^"]*)"/g)].map((m) => m[1]);
	return [...blocs, ...attributs].join('\n').replace(/\/\*[\s\S]*?\*\//g, '');
}

/** Couleurs hexadécimales et tailles de texte en `rem` écrites en dur. */
export function valeursEnDur(css) {
	return {
		couleurs: [...css.matchAll(/#[0-9a-fA-F]{3,8}\b/g)].map((m) => m[0]),
		tailles: [...css.matchAll(/font-size\s*:\s*([0-9]*\.?[0-9]+)rem/g)].map((m) => m[1]),
	};
}

/**
 *  ## Ce qui est INTERDIT, sans plafond (arbitré le 27/09/2026, sur maquette)
 *
 *  Le plafond tolère une dette ; ces valeurs-ci ont été TRANCHÉES, elles ne se
 *  tolèrent plus nulle part — ni dans un composant, ni dans `src/styles/`.
 *
 *  - une taille hors échelle se range au cran SUPÉRIEUR : aucun texte ne
 *    rétrécit en se normalisant (lisibilité au pouce) ;
 *  - une couleur d'ÉTAT vient de la charte, jamais de la palette de Tailwind —
 *    le bloc des urgences de l'accueil portait deux rouges côte à côte ;
 *  - le texte sur un fond d'avertissement prend `--color-warning-texte` :
 *    `--color-warning` (3,62 sur blanc) ne sert pas au texte.
 *
 *  Le tableau dit la valeur de REMPLACEMENT : le message d'échec la donne.
 *
 *  ⚠️ Les palettes CATÉGORIELLES ne sont pas des états et restent hors de ce
 *  contrôle : la teinte d'un type du fil (`$lib/flux`), d'un périmètre
 *  (`$lib/perimetres/teinte`), d'une colonne de kanban, d'une nature
 *  (`--nature-fort`), l'orange de l'urgence, `.badge-yellow` (#495).
 */
export const TAILLES_HORS_ECHELLE = {
	0.65: '--fs-2xs',
	0.68: '--fs-2xs',
	0.7: '--fs-2xs',
	0.78: '--fs-sm',
	0.82: '--fs-md',
	0.875: '--fs-base',
	0.88: '--fs-base',
	0.92: '--fs-lg',
};

export const COULEURS_ETAT_ETRANGERES = {
	'#dc2626': '--color-danger',
	'#b91c1c': '--color-danger',
	'#991b1b': '--color-danger',
	'#7f1d1d': '--color-danger',
	'#ef4444': '--color-danger',
	'#fef2f2': '--color-danger-fond',
	'#fee2e2': '--color-danger-fond',
	'#fecaca': '--color-danger-bordure',
	'#16a34a': '--color-success',
	'#15803d': '--color-success',
	'#22c55e': '--color-success',
	'#166534': '--color-success',
	'#065f46': '--color-success',
	'#059669': '--color-success',
	'#10b981': '--color-success',
	'#f0fdf4': '--color-success-fond',
	'#dcfce7': '--color-success-fond',
	'#d1fae5': '--color-success-fond',
	'#ecfdf5': '--color-success-fond',
	'#bbf7d0': '--color-success-bordure',
	'#f59e0b': '--color-warning',
	'#d97706': '--color-warning',
	'#fbbf24': '--color-warning',
	'#b45309': '--color-warning',
	'#92400e': '--color-warning-texte',
	'#78350f': '--color-warning-texte',
	'#fffbeb': '--color-warning-fond',
	'#fef3c7': '--color-warning-fond',
	'#fde68a': '--color-warning-bordure',
	'#fcd34d': '--color-warning-bordure',
};

/** Les mêmes rouges, verts et ambres écrits en `rgb()` / `rgba()`. */
const RGB_ETAT =
	/rgba?\(\s*(220\s*,\s*38\s*,\s*38|239\s*,\s*68\s*,\s*68|22\s*,\s*163\s*,\s*74|245\s*,\s*158\s*,\s*11|217\s*,\s*119\s*,\s*6)\b/g;

/**
 *  Ce qui est interdit dans une source, commentaires retirés — le HISTORIQUE
 *  d'une couleur (« elle était `#f59e0b` ») reste lisible en commentaire.
 *  Les couleurs sont cherchées dans TOUT le fichier : une chaîne de style
 *  composée en JavaScript rend autant qu'un `<style>`.
 */
export function interditsDe(source) {
	const code = source
		.replace(/<!--[\s\S]*?-->/g, '')
		.replace(/\/\*[\s\S]*?\*\//g, '')
		.replace(/(^|[^:'"])\/\/.*$/gm, '$1');
	const trouves = [];
	for (const m of code.matchAll(/font-size\s*:\s*([0-9]*\.?[0-9]+)rem/g)) {
		const jeton = TAILLES_HORS_ECHELLE[parseFloat(m[1])];
		if (jeton) trouves.push([`${m[1]}rem`, `var(${jeton})`]);
	}
	for (const m of code.matchAll(/#[0-9a-fA-F]{6}\b/g)) {
		const jeton = COULEURS_ETAT_ETRANGERES[m[0].toLowerCase()];
		if (jeton) trouves.push([m[0], `var(${jeton})`]);
	}
	for (const m of code.matchAll(RGB_ETAT))
		trouves.push([m[0] + '…)', 'color-mix(… var(--color-…) …)']);
	return trouves;
}

/**
 *  Les exceptions : aucune. Une entrée s'écrit `'chemin': 'raison'`, et le
 *  contrôle échoue si elle ne sert plus — une exception sans objet est un
 *  passe-droit en attente.
 */
const EXCEPTIONS = {};

/**
 *  ## Le texte d'un badge se LIT (#1410, 27/09/2026)
 *
 *  Chaque `.badge-<teinte>` de `styles/composants.css` pose un texte de
 *  0,75 rem sur un fond : il lui faut 4,5:1 (standards/11 §2). Le vert de la
 *  charte faisait 4,44 sur son propre fond — un écart que personne ne voit à
 *  l'œil, et que la règle « un état prend son jeton » a répandu partout.
 *  Le contrôle résout les `var(--…)` dans `socle.css` et MESURE le rapport ;
 *  une valeur qu'il ne sait pas résoudre le fait échouer (INCONNU, jamais OK).
 */
export function contraste(a, b) {
	const lum = (h) => {
		const c = [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
		const [r, g, v] = c.map((x) => (x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4));
		return 0.2126 * r + 0.7152 * g + 0.0722 * v;
	};
	const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
	return (x + 0.05) / (y + 0.05);
}

/** `var(--x)` → la valeur hexadécimale de `--x` dans les jetons, ou null. */
export function resoudre(valeur, jetons, profondeur = 0) {
	const v = valeur.trim().toLowerCase();
	if (/^#[0-9a-f]{6}$/.test(v)) return v;
	const m = v.match(/^var\(\s*(--[a-z0-9-]+)\s*\)$/);
	if (!m || profondeur > 5 || !(m[1] in jetons)) return null;
	return resoudre(jetons[m[1]], jetons, profondeur + 1);
}

/** Les badges et leur rapport de contraste ; `null` quand une valeur échappe. */
export function contrastesBadges(composants, socle) {
	const jetons = Object.fromEntries(
		[...socle.matchAll(/^\s*(--[a-z0-9-]+)\s*:\s*([^;]+);/gm)].map((m) => [m[1], m[2]]),
	);
	return [...composants.matchAll(/^\.badge-([a-z]+)\s*\{([^}]*)\}/gm)]
		.map(([, nom, corps]) => {
			const fond = corps.match(/background\s*:\s*([^;]+);/);
			const texte = corps.match(/(?:^|[\s;])color\s*:\s*([^;]+);/);
			if (!fond || !texte) return null;
			const f = resoudre(fond[1], jetons);
			const t = resoudre(texte[1], jetons);
			return { nom, rapport: f && t ? contraste(t, f) : null };
		})
		.filter(Boolean);
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const cas = (libelle, obtenu, attendu) => {
		const ok = JSON.stringify(obtenu) === JSON.stringify(attendu);
		if (!ok) ko = 1;
		console.log(`${ok ? 'PASS' : 'FAIL'}  ${libelle} → ${JSON.stringify(obtenu)}`);
	};
	const composant = `<div style="font-size:.8rem;color:#fff">a</div>
<!-- <p style="color:#123456"></p> -->
<style>
	/* #abcdef dans un commentaire ne compte pas */
	.a { color: #dc2626; font-size: 0.85rem; }
	.b { color: var(--color-danger); font-size: var(--fs-sm); }
</style>`;
	const v = valeursEnDur(stylesDe(composant));
	cas('couleurs du bloc et de l’attribut, pas des commentaires', v.couleurs, ['#dc2626', '#fff']);
	cas('tailles en rem du bloc et de l’attribut', v.tailles, ['0.85', '.8']);
	cas('une variable de charte ne compte pas', valeursEnDur('.b{color:var(--x)}').couleurs, []);
	cas(
		'le hors-style ne compte pas (texte, script)',
		valeursEnDur(stylesDe('<p>#1 font-size: 2rem</p><script>const c="#fff"</script>')),
		{ couleurs: [], tailles: [] },
	);
	cas(
		'taille hors échelle → cran supérieur',
		interditsDe('<style>.a{font-size:.78rem}.b{font-size: 0.875rem}.c{font-size:0.8rem}</style>'),
		[
			['.78rem', 'var(--fs-sm)'],
			['0.875rem', 'var(--fs-base)'],
		],
	);
	cas(
		'couleur d’état étrangère, en style ET en chaîne JavaScript',
		interditsDe(
			'<script>const s = "color:#92400e"</script><style>.a{border:1px solid #DC2626}</style>',
		),
		[
			['#92400e', 'var(--color-warning-texte)'],
			['#DC2626', 'var(--color-danger)'],
		],
	);
	cas(
		'rgba d’un rouge Tailwind',
		interditsDe('.a{box-shadow:0 2px 8px rgba(220, 38, 38, 0.15)}').length,
		1,
	);
	cas(
		'un commentaire garde l’historique, une couleur de charte passe',
		interditsDe('<!-- #f59e0b --><style>/* #dc2626 */ .a{color:#c0392b} // #16a34a\n</style>'),
		[],
	);
	cas(
		'contraste du vert de la charte sur son fond',
		contraste('#2e7d52', '#e6f4ee').toFixed(2),
		'4.44',
	);
	cas(
		'un badge se résout par les jetons, et une valeur inconnue rend null',
		contrastesBadges(
			'.badge-a {\n\tbackground: var(--f);\n\tcolor: var(--t);\n}\n.badge-b {\n\tbackground: var(--absent);\n\tcolor: #000000;\n}',
			':root {\n\t--f: #ffffff;\n\t--t: #000000;\n}',
		).map((b) => [b.nom, b.rapport && Math.round(b.rapport)]),
		[
			['a', 21],
			['b', null],
		],
	);
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	process.exit(ko);
}

function fichiers(dir, acc = []) {
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) fichiers(chemin, acc);
		else if (nom.endsWith('.svelte')) acc.push(chemin);
	}
	return acc;
}

const total = { couleurs: 0, tailles: 0 };
const parFichier = [];
let blocsLus = 0;
for (const chemin of fichiers(RACINE)) {
	const css = stylesDe(readFileSync(chemin, 'utf8'));
	if (css.trim()) blocsLus++;
	const v = valeursEnDur(css);
	total.couleurs += v.couleurs.length;
	total.tailles += v.tailles.length;
	const n = v.couleurs.length + v.tailles.length;
	if (n) parFichier.push([relative(RACINE, chemin).split(sep).join('/'), n]);
}

if (!blocsLus) {
	console.error('\n✗ Aucun style lu : contrôle inopérant (INCONNU).\n');
	process.exit(2);
}

let echec = 0;

//  Les interdits se cherchent aussi dans `src/styles/` : la charte elle-même ne
//  doit pas les porter.
const STYLES = join(RACINE, 'styles');
const sources = [
	...fichiers(RACINE),
	...readdirSync(STYLES)
		.filter((n) => n.endsWith('.css'))
		.map((n) => join(STYLES, n)),
];
const exceptionsServies = new Set();
const interdits = [];
for (const chemin of sources) {
	const rel = relative(RACINE, chemin).split(sep).join('/');
	const trouves = interditsDe(readFileSync(chemin, 'utf8'));
	if (!trouves.length) continue;
	if (rel in EXCEPTIONS) {
		exceptionsServies.add(rel);
		continue;
	}
	for (const [valeur, par] of trouves) interdits.push(`   ${rel} : ${valeur} → ${par}`);
}
if (interdits.length) {
	echec = 1;
	console.error(
		`\n✗ ${interdits.length} valeur(s) tranchée(s) le 27/09/2026 encore écrite(s) ` +
			'(taille au cran supérieur, couleur d’état de la charte) :',
	);
	interdits.slice(0, 40).forEach((l) => console.error(l));
	if (interdits.length > 40) console.error(`   … et ${interdits.length - 40} de plus`);
}
const badges = contrastesBadges(
	readFileSync(join(STYLES, 'composants.css'), 'utf8'),
	readFileSync(join(STYLES, 'socle.css'), 'utf8'),
);
if (!badges.length) {
	echec = 1;
	console.error(
		'\n✗ Aucun badge lu dans composants.css : contrôle de contraste inopérant (INCONNU).',
	);
}
for (const { nom, rapport } of badges) {
	if (rapport == null) {
		echec = 1;
		console.error(`\n✗ .badge-${nom} : couleur non résolue — contraste INCONNU.`);
	} else if (rapport < 4.5) {
		echec = 1;
		console.error(
			`\n✗ .badge-${nom} : texte à ${rapport.toFixed(2)}:1 sur son fond, sous 4,5 ` +
				'— un dérivé `-texte` (socle.css), comme --color-warning-texte.',
		);
	}
}
for (const rel of Object.keys(EXCEPTIONS)) {
	if (!exceptionsServies.has(rel)) {
		echec = 1;
		console.error(`\n✗ Exception sans objet : ${rel} ne porte plus rien d’interdit — la retirer.`);
	}
}
for (const cle of ['couleurs', 'tailles']) {
	if (total[cle] > PLAFOND[cle]) {
		echec = 1;
		console.error(
			`\n✗ ${total[cle]} ${cle} en dur, plafond ${PLAFOND[cle]}. Employer la charte : ` +
				(cle === 'couleurs' ? '`var(--color-…)`' : '`var(--fs-…)`') +
				' (styles/socle.css). Les plus chargés :',
		);
		parFichier
			.sort((a, b) => b[1] - a[1])
			.slice(0, 8)
			.forEach(([f, n]) => console.error(`   ${n}  ${f}`));
	} else if (total[cle] < PLAFOND[cle]) {
		echec = 1;
		console.error(
			`\n✗ ${total[cle]} ${cle} en dur, sous le plafond de ${PLAFOND[cle]} : ` +
				`le baisser à ${total[cle]} dans ce lot (PLAFOND, en tête du fichier).`,
		);
	}
}
if (echec) process.exit(1);
console.log(
	`✓ Charte : ${total.couleurs} couleurs et ${total.tailles} tailles en dur, ` +
		`au plafond — aucune ajoutée (${parFichier.length} fichiers portent encore de la dette).`,
);
