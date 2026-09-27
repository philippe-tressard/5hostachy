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
 */
const PLAFOND = { couleurs: 235, tailles: 258 };

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
