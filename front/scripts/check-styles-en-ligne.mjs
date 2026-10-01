#!/usr/bin/env node
/**
 *  Un style s'écrit dans une feuille, pas dans un attribut `style="…"` (#1329,
 *  28/09/2026).
 *
 *  ## Pourquoi
 *
 *  La passe de cohérence demandée le 25/09/2026 (« j'ai l'impression qu'il y a
 *  du laisser-aller ») a relevé des écrans entiers composés d'attributs
 *  `style` : quarante dans l'onglet WhatsApp, dix-sept sur la page d'un
 *  sondage. Un style en ligne échappe à tout ce qui tient la charte — il ne se
 *  réemploie pas, ne se surcharge pas au doigt (`@media`), et deux écrans qui
 *  veulent la même allure la réécrivent chacun. 524 dans le front ce jour-là,
 *  et rien pour dire qu'il n'en fallait pas un de plus.
 *
 *  ## Ce qu'il mesure
 *
 *  Les attributs `style="…"` **statiques** des `.svelte`, commentaires HTML
 *  retirés. Un style qui porte une expression (`style="width:{pct}%"`) est
 *  légitime : la valeur vient des données, aucune feuille ne peut la porter.
 *
 *  ## Un PLAFOND, et il ne fait que baisser
 *
 *  Tout convertir d'un coup changerait des centaines de rendus sans qu'on en
 *  regarde un seul. Le plafond refuse d'en AJOUTER ; il échoue aussi quand le
 *  compte passe DESSOUS — le plafond se baisse alors dans le même lot, sinon
 *  la marge regagnée serait reprise sans un mot par le suivant.
 *
 *  Lancer : node scripts/check-styles-en-ligne.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 *  Le compte autorisé, et son historique.
 *  28/09/2026 (#1329) : 495 relevés ; 474 le même jour — l'onglet WhatsApp
 *  a rendu 21 des siens en extrayant ses messages planifiés et son historique,
 *  rendu identique au pixel près (bureau et mobile). Puis 458 : la page d'un
 *  sondage, ses résultats extraits en composant et ses styles passés en
 *  classes, rendu identique (quatre états, bureau et mobile). Puis 457 : le
 *  badge « Bail actif » du formulaire de bail, passé dans sa feuille (#1329).
 *  Puis 455 : la barre de réorganisation de la FAQ, extraite en composant (#779).
 *  Puis 451 : la démarche « Nouvel arrivant » du profil, idem (#779).
 *  Puis 449 : le bail parking/cave et le QR WhatsApp, passés par
 *  `EncartAvertissement` (#1455).
 *  Puis 445 : l'annuaire de l'espace CS, extrait en deux composants (#779).
 */
const PLAFOND = 444;

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..', 'src');

/** Les styles en ligne STATIQUES d'une source : sans expression `{…}`. */
export function stylesEnLigne(source) {
	const sans = source.replace(/<!--[\s\S]*?-->/g, '');
	return [...sans.matchAll(/\bstyle="([^"]*)"/g)]
		.map((m) => m[1])
		.filter((v) => v.trim() && !v.includes('{'));
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const cas = (libelle, obtenu, attendu) => {
		const ok = JSON.stringify(obtenu) === JSON.stringify(attendu);
		if (!ok) ko = 1;
		console.log(`${ok ? 'PASS' : 'FAIL'}  ${libelle} → ${JSON.stringify(obtenu)}`);
	};
	cas(
		'un style statique compte, un style tiré des données non',
		stylesEnLigne('<div style="margin:0">a</div><div style="width:{pct}%"></div>'),
		['margin:0'],
	);
	cas('un commentaire ne compte pas', stylesEnLigne('<!-- <p style="color:red"></p> -->'), []);
	cas('un attribut vide ne compte pas', stylesEnLigne('<p style="">a</p>'), []);
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

let total = 0;
let lus = 0;
const parFichier = [];
for (const chemin of fichiers(RACINE)) {
	lus++;
	const n = stylesEnLigne(readFileSync(chemin, 'utf8')).length;
	total += n;
	if (n) parFichier.push([relative(RACINE, chemin).split(sep).join('/'), n]);
}

if (!lus) {
	console.error('\n✗ Aucun composant lu : contrôle inopérant (INCONNU).\n');
	process.exit(2);
}
if (total > PLAFOND) {
	console.error(
		`\n✗ ${total} styles en ligne statiques, plafond ${PLAFOND}. Écrire le style dans ` +
			'le `<style>` du composant ou dans `src/styles/`. Les plus chargés :',
	);
	parFichier
		.sort((a, b) => b[1] - a[1])
		.slice(0, 8)
		.forEach(([f, n]) => console.error(`   ${n}  ${f}`));
	process.exit(1);
}
if (total < PLAFOND) {
	console.error(
		`\n✗ ${total} styles en ligne statiques, sous le plafond de ${PLAFOND} : ` +
			`le baisser à ${total} dans ce lot (PLAFOND, en tête du fichier).`,
	);
	process.exit(1);
}
console.log(
	`✓ Styles en ligne : ${total}, au plafond — aucun ajouté (${parFichier.length} fichiers en portent).`,
);
