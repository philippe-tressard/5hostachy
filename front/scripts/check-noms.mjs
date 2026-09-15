#!/usr/bin/env node
/**
 * Garde-fou : « Prénom NOM » se rend pareil des deux côtés — et il est EXÉCUTÉ.
 *
 * ## Pourquoi (31/08/2026)
 *
 * La règle « le nom passe en capitales, le prénom garde sa casse » est écrite
 * **deux fois** : `front/src/lib/noms.ts` et `api/app/utils/noms.py`. Ce n'est
 * pas un oubli — les contextes de construction sont `./api` et `./front`, rien
 * de la racine n'entre dans les images (mémoire
 * `project_partage_front_api_impossible`). Le seul motif viable est la copie.
 *
 * Elle s'est déjà payée sur `perimetreLabel` : corrigée d'un seul côté le
 * 18/08/2026, elle a mis **neuf jours** à se voir — et c'est l'utilisateur qui
 * l'a vue. Un contrôle qui lirait le fichier ne saurait pas si le code marche ;
 * celui-ci transpile le TypeScript, l'exécute, et compare à ce que le test
 * Python attend.
 *
 * ## Une seule attente, écrite UNE fois
 *
 * Les cas ne sont pas recopiés ici : ils sont **lus** dans
 * `api/tests/test_noms_affichage.py`. Deux listes divergeraient au premier cas
 * ajouté — et c'est le cas ajouté qui compte, puisqu'on ne l'ajoute que quand
 * quelque chose s'est mal passé.
 *
 * Usage : npm run lint:noms
 */
import { readFileSync, existsSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { chargerModule } from './lib/charger-module.mjs';
import { dirname, resolve, relative, join, sep } from 'node:path';

const ICI = dirname(fileURLToPath(import.meta.url));
const SOURCE = resolve(ICI, '..', 'src', 'lib', 'noms.ts');
const TEST_PYTHON = resolve(ICI, '..', '..', 'api', 'tests', 'test_noms_affichage.py');

const RACINE_SRC = resolve(ICI, '..', 'src');
const SAUT = String.fromCharCode(10);

/** Tous les .svelte et .ts de `src/`, pour le contrôle du CLASSEMENT ci-dessous. */
function fichiersSources(dossier) {
	const out = [];
	for (const entree of readdirSync(dossier)) {
		const chemin = join(dossier, entree);
		if (statSync(chemin).isDirectory()) out.push(...fichiersSources(chemin));
		else if (/\.(svelte|ts)$/.test(entree)) out.push(chemin);
	}
	return out;
}

function echouer(message) {
	console.error(`\n✗ ${message}\n`);
	process.exit(1);
}

//  ── Auto-contrôle (cas zéro) ────────────────────────────────────────────────
for (const [chemin, quoi] of [
	[SOURCE, 'le rendu du front'],
	[TEST_PYTHON, 'le test jumeau côté API'],
]) {
	if (!existsSync(chemin)) {
		echouer(`Cas zéro : ${quoi} est introuvable (${chemin}) — contrôle inopérant.`);
	}
}

//  ── Les cas, LUS dans le test Python ────────────────────────────────────────
//  Chaque ligne a la forme  ("prénom", "nom", "rendu"),  guillemets doubles et
//  aucun échappement (aucun cas n'en porte). Si cette forme cesse de
//  correspondre, le plancher plus bas le dit — il ne conclut pas au vert.
const python = readFileSync(TEST_PYTHON, 'utf8');
const bloc = python.slice(
	python.indexOf('CAS = ['),
	python.indexOf(']', python.indexOf('CAS = [')),
);
const CAS = [...bloc.matchAll(/\("([^"]*)",\s*"([^"]*)",\s*"([^"]*)"\)/g)].map((m) => ({
	prenom: m[1],
	nom: m[2],
	attendu: m[3],
}));

const PLANCHER = 6;
if (CAS.length < PLANCHER) {
	echouer(
		`Cas zéro : ${CAS.length} cas lu(s) dans ${TEST_PYTHON} (au moins ${PLANCHER} attendus) —\n` +
			'  le motif ne correspond plus à la liste `CAS` du test Python.\n' +
			'  Ne pas lire ceci comme un succès : la concordance ne serait plus vérifiée.',
	);
}

//  ── Le front, EXÉCUTÉ ───────────────────────────────────────────────────────
const module = await chargerModule(SOURCE, echouer);

const { nomAffiche } = module;
if (typeof nomAffiche !== 'function') {
	echouer(
		"Cas zéro : lib/noms.ts n'exporte plus `nomAffiche` — la fonction a disparu ou\n" +
			'  changé de nom, et ce contrôle ne mesure plus rien.',
	);
}

const echecs = [];
for (const { prenom, nom, attendu } of CAS) {
	//  Les DEUX formes d'appel, parce que les deux servent à l'écran : un objet
	//  quand on tient la personne, deux champs quand l'API les a aplatis.
	for (const [forme, obtenu] of [
		['deux champs', nomAffiche(prenom, nom)],
		['un objet', nomAffiche({ prenom, nom })],
	]) {
		if (obtenu !== attendu) {
			echecs.push(
				`   (${forme}) ${JSON.stringify(prenom)} + ${JSON.stringify(nom)}\n` +
					`       attendu ${JSON.stringify(attendu)}, obtenu ${JSON.stringify(obtenu)}`,
			);
		}
	}
}

//  Et l'absence totale, que le test Python vérifie séparément : elle ne doit
//  jamais produire « undefined » à l'écran.
for (const [quoi, obtenu] of [
	['nomAffiche(null)', nomAffiche(null)],
	['nomAffiche(undefined)', nomAffiche(undefined)],
	['nomAffiche(null, null)', nomAffiche(null, null)],
]) {
	if (obtenu !== '') echecs.push(`   ${quoi} rend ${JSON.stringify(obtenu)} au lieu de ""`);
}

//  ── Et le CLASSEMENT, qui est l'autre moitié de la notion ──────────────────
//
//  🔴 Signalé à l'écran le 15/09/2026 : « le classement des badges &
//  télécommandes par Nom doit se faire sur le nom et pas le prénom ». La table
//  triait sur `porteur_nom`, qui vaut « Alain GARCIA » — donc sur le prénom. Et
//  `FormulaireTicket` comparait littéralement le prénom suivi du nom.
//
//  ⚠️ La règle juste existait déjà, écrite TROIS fois (annuaire, administration,
//  espace CS). Elle vit maintenant dans `comparerParNom`, et ce contrôle exige
//  qu'aucun écran ne la recompose : une quatrième copie reviendrait au premier
//  tableau ajouté.
//
//  La cible est reconnue à sa FORME — une comparaison de `.nom` par
//  `localeCompare` —, pas au mot « nom » : `batiment_nom`, `prestataire_nom` et
//  les autres libellés sont des chaînes, pas des personnes, et crier dessus
//  désarmerait le contrôle (la leçon de C16 et de `check-stack`).
const COMPARAISON_NOM =
	/\.nom\s*\?\?\s*''\)\s*\.localeCompare|\$\{[a-z.]*prenom\}[^`]*\$\{[a-z.]*nom\}`\s*\.localeCompare/;
const recomposent = [];
for (const chemin of fichiersSources(RACINE_SRC)) {
	const rel = relative(RACINE_SRC, chemin).split(sep).join('/');
	if (rel === 'lib/noms.ts') continue; // la source a le droit : c'est elle la règle
	const source = readFileSync(chemin, 'utf8');
	for (const ligne of source.split(SAUT)) {
		if (COMPARAISON_NOM.test(ligne)) recomposent.push(`   ${rel} : ${ligne.trim().slice(0, 100)}`);
	}
}
if (recomposent.length) {
	echecs.push(
		['Ces écrans recomposent le CLASSEMENT des personnes :', ...recomposent].join(SAUT) +
			SAUT +
			'   Emploie `comparerParNom` de $lib/noms — nom de famille, puis prénom.',
	);
}

if (echecs.length) {
	//  ⚠️ DEUX familles d'échec passent par ici — l'AFFICHAGE d'un nom et son
	//  CLASSEMENT. L'en-tête ne doit pas n'en nommer qu'une : il enverrait
	//  chercher au mauvais endroit, ce qui est le défaut d'un contrôle qui dit
	//  autre chose que ce qu'il a mesuré.
	console.error('\n✗ La règle du NOM d’une personne n’est pas tenue :\n');
	console.error(echecs.join('\n'));
	console.error(
		'\n  Les deux implémentations sont tenues par une seule attente, écrite dans' +
			`\n  ${TEST_PYTHON}. Corriger les DEUX, jamais une seule : c’est en n’en` +
			'\n  corrigeant qu’une que « Toit · Toit » a survécu neuf jours (#497).\n',
	);
	process.exit(1);
}

console.log(
	`✓ Nom affiché : ${CAS.length} cas concordent entre lib/noms.ts et test_noms_affichage.py, ` +
		'sur les deux formes d’appel.',
);
