#!/usr/bin/env node
/**
 * Garde-fou : un intitulé de section du cadre ne s'écrit pas en dur.
 *
 * ## Le défaut (22/09/2026, signalé à l'écran)
 *
 * `ChampSaisiPour` affichait **« SAISI POUR »** alors que la table déclare
 * « Au nom de » depuis le cadre à treize sections. Deux noms pour une section,
 * dont un seul est déclaré — et c'est celui qui ne l'est pas que l'écran
 * montrait. Personne ne pouvait le voir sans ouvrir le formulaire.
 *
 * ⚠️ Écrit à part de `check-etats.mjs`, qui a franchi ses 500 lignes en
 * l'accueillant : la modularité se règle au fil de l'eau, et cette règle-ci se
 * tient seule — elle ne lit que la table et les écrans.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { relative, join, sep } from 'node:path';

import { extraire } from './lib-lecture-source.mjs';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const TYPES = join(RACINE, 'lib', 'entites', 'types.ts');

const LIBELLES = extraire(readFileSync(TYPES, 'utf8'), 'SECTIONS_LIBELLE', 'types.ts', {
	echec: (message) => {
		console.error(`
✗ Cas zéro : ${message}
  Ne pas lire ceci comme un succès.
`);
		process.exit(1);
	},
});

function svelte(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...svelte(chemin));
		else if (nom.endsWith('.svelte')) sortie.push(chemin);
	}
	return sortie;
}

// ════════════════════════════════════════════════════════════════════════════
//  UN INTITULÉ DE SECTION NE S'ÉCRIT PAS EN DUR (22/09/2026)
// ════════════════════════════════════════════════════════════════════════════
//
//  🔴 `ChampSaisiPour` affichait « Saisi pour » alors que la table déclare
//  « Au nom de » depuis le cadre à treize sections. Deux noms pour une section,
//  dont un seul est déclaré : c'est celui qui n'est pas déclaré que l'écran
//  montrait, et personne ne pouvait le voir sans ouvrir le formulaire.
//
//  ⚠️ Ce qui est refusé : un `titre="…"` de `SectionFormulaire` dont le texte
//  est l'un des treize intitulés de la table. Les autres restent libres — une
//  section « Le contrat » ou « Activation » n'appartient pas au cadre, et le
//  contrôle n'a rien à en dire.
/**
 *  Les écrans qui portent des sections HORS du cadre, et leur raison.
 *
 *  ⚠️ Une exception qui cesse de servir fait échouer le contrôle : sans cela
 *  elle survivrait à son objet et couvrirait un défaut réintroduit au même
 *  endroit.
 */
const HORS_CADRE = {
	'components/FormulaireAnnonceHall.svelte':
		'une affiche de hall est un DOCUMENT imprimé, pas une entité du cadre : ' +
		'« Format », « Message » et « Photos » lui sont propres et ne figurent dans ' +
		'aucune autre déclaration.',
};

const LIBELLES_CADRE = new Set(Object.values(LIBELLES));
const ENDUR = [];
for (const chemin of svelte(RACINE)) {
	const relatif = relative(RACINE, chemin).split(sep).join('/');
	if (Object.keys(HORS_CADRE).some((f) => relatif.endsWith(f))) continue;
	const source = readFileSync(chemin, 'utf8');
	source.split('\n').forEach((ligne, i) => {
		const m =
			ligne.match(/<SectionFormulaire[^>]*\btitre="([^"]+)"/) ?? ligne.match(/^\s*titre="([^"]+)"/);
		if (m && LIBELLES_CADRE.has(m[1])) {
			ENDUR.push(`src/${relatif}:${i + 1}  titre="${m[1]}"`);
		}
	});
}
if (ENDUR.length > 0) {
	console.error(`\n✗ ${ENDUR.length} intitulé(s) de section du cadre écrit(s) en dur :\n`);
	for (const e of ENDUR) console.error(`  ${e}`);
	console.error(
		'\n  Le jour où la table renomme la section, ces écrans gardent l’ancien nom —' +
			'\n  et rien ne le dit, puisque le texte est juste au moment où on l’écrit.' +
			'\n\n  → titre={SECTIONS_LIBELLE.<id>}\n',
	);
	process.exit(1);
}

console.log(
	`✓ Intitulés de section : ${Object.keys(LIBELLES).length} déclarés, aucun réécrit dans un écran ` +
		`— ${Object.keys(HORS_CADRE).length} écran(s) hors cadre, déclaré(s).`,
);
