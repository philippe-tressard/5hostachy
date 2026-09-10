#!/usr/bin/env node
/**
 * Les seuils de format d'une affiche de hall sont écrits DEUX fois — et ils
 * doivent dire la même chose.
 *
 * ## Pourquoi deux copies
 *
 * L'API choisit le format ; l'écran en affiche une PRÉVISION pendant la saisie,
 * pour que le CS voie tout de suite quel feuillet sortira. Les deux contextes de
 * build sont `./api` et `./front` : rien de la racine n'entre dans les images, et
 * aucun fichier ne peut être partagé (mémoire `project_partage_front_api_impossible`).
 * Le seul motif viable est la copie, PLUS un contrôle qui compare.
 *
 * ## Pourquoi ce contrôle, maintenant (10/09/2026)
 *
 * Les seuils viennent d'être recalibrés sur une mesure du taux de remplissage —
 * signalé à l'écran : *« le mode auto n'est pas optimum, le but est que l'affiche
 * prenne moins de place sur le tableau d'affichage »*. Une annonce de 629
 * caractères sortait en A4 avec 45 % de blanc.
 *
 * Deux tables recopiées divergent au premier ajustement, et celle-ci vient d'en
 * subir un. Sans contrôle, l'écran annoncerait « A4 » pendant que l'API produit
 * un A5 — une prévision fausse est pire qu'aucune prévision.
 */
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ICI = dirname(fileURLToPath(import.meta.url));
const API = join(ICI, '..', '..', 'api', 'app', 'utils', 'annonce_hall.py');
const FRONT = join(ICI, '..', 'src', 'lib', 'components', 'FormulaireAnnonceHall.svelte');

function echouer(message) {
	console.error(`✗ ${message}`);
	process.exit(1);
}

/** Les couples (format, seuil) déclarés côté serveur. */
function seuilsApi() {
	const src = readFileSync(API, 'utf8');
	const bloc = src.match(/SEUILS_FORMAT[^=]*=\s*\(([\s\S]*?)\n\)/);
	if (!bloc) echouer('Cas zéro : SEUILS_FORMAT introuvable côté API — contrôle inopérant.');
	return [...bloc[1].matchAll(/\(\s*"(a\d)"\s*,\s*(\d+)\s*\)/g)].map((m) => [
		m[1].toUpperCase(),
		Number(m[2]),
	]);
}

/** Les couples (format, seuil) déclarés côté écran. */
function seuilsFront() {
	const src = readFileSync(FRONT, 'utf8');
	const bloc = src.match(/const SEUILS[^=]*=\s*\[([\s\S]*?)\n\t\];/);
	if (!bloc) echouer('Cas zéro : la table SEUILS est introuvable côté front — contrôle inopérant.');
	return [...bloc[1].matchAll(/\[\s*'(A\d)'\s*,\s*(\d+)\s*\]/g)].map((m) => [m[1], Number(m[2])]);
}

const api = seuilsApi();
const front = seuilsFront();

if (api.length === 0 || front.length === 0) {
	echouer(
		`Cas zéro : ${api.length} seuil(s) côté API, ${front.length} côté front — extraction cassée.`,
	);
}

//  Le dernier seuil de l'API est celui de l'A4 : il ne sert qu'à documenter le
//  point de débordement, l'écran n'a rien à en prévoir (au-delà, c'est A4 quoi
//  qu'il arrive). Il n'a donc pas de jumeau côté front, et c'est voulu.
const attendus = api.filter(([fmt]) => fmt !== 'A4');

const ecarts = [];
if (attendus.length !== front.length) {
	ecarts.push(
		`l'API déclare ${attendus.length} seuil(s) prévisibles (${attendus
			.map(([f]) => f)
			.join(', ')}), l'écran ${front.length} (${front.map(([f]) => f).join(', ')})`,
	);
}
for (const [fmt, seuil] of attendus) {
	const jumeau = front.find(([f]) => f === fmt);
	if (!jumeau) ecarts.push(`${fmt} : absent côté écran`);
	else if (jumeau[1] !== seuil) ecarts.push(`${fmt} : API ${seuil}, écran ${jumeau[1]}`);
}

if (ecarts.length > 0) {
	console.error('✗ Les seuils de format d’affiche divergent entre l’API et l’écran :\n');
	for (const e of ecarts) console.error(`  • ${e}`);
	console.error(
		'\n  L’écran annoncerait un format que l’API ne produirait pas. Aligner\n' +
			'  `FormulaireAnnonceHall.svelte` sur `api/app/utils/annonce_hall.py`.\n',
	);
	process.exit(1);
}

console.log(
	`✓ Seuils d’affiche : ${attendus.length} format(s) prévisibles, identiques des deux côtés ` +
		`(${attendus.map(([f, s]) => `${f}≤${s}`).join(' · ')}).`,
);
