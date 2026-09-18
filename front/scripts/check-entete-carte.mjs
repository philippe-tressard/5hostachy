#!/usr/bin/env node
/**
 *  Une carte de liste rend son haut par `EnteteCarte` — sans exception.
 *
 *  ## Pourquoi ce contrôle (12/09/2026)
 *
 *  `EnteteCarte` existe depuis le 18/08/2026 et porte trois décisions qu'on ne
 *  peut pas reprendre carte par carte :
 *
 *    • le TITRE occupe sa ou ses propres lignes, et rien ne le pousse. Sur un
 *      téléphone, une ligne en `flex` partagée avec des badges de largeur fixe
 *      réduit le titre à trois points — on lit une liste sans savoir de quoi
 *      elle parle. C'est **R1** : la responsivité appartient au squelette.
 *    • le geste est ASYMÉTRIQUE — repliée, toute la carte ouvre ; dépliée, seul
 *      le titre referme, pour qu'on puisse lire et copier le corps.
 *    • l'ordre de lecture : tags à gauche, date puis actions puis chevron à
 *      droite.
 *
 *  🔴 Onze cartes l'employaient. DEUX ne l'employaient pas — `CarteContrat` et
 *  `CartePrestataire` — et elles portaient exactement les défauts qu'il supprime,
 *  y compris l'ancien `role="button"` sur le conteneur, remplacé partout ailleurs
 *  le 18/08. Personne ne l'a vu pendant un mois : rien ne relit une carte qu'on
 *  ne touche pas, et les deux étaient cohérentes *entre elles*.
 *
 *  Signalé à l'écran : *« le comportement et l'UX ne doivent pas diverger »*.
 *
 *  ## Ce que le contrôle mesure
 *
 *  Tout fichier qui rend `class="carte-liste"` (ou `class:carte-liste`) doit
 *  importer `EnteteCarte`. C'est volontairement grossier : il ne vérifie pas
 *  QUE l'en-tête est bien composé, seulement qu'il n'est pas réécrit. Un
 *  contrôle qui prétendrait juger la composition rendrait des verdicts qu'on
 *  finirait par ignorer.
 *
 *  ⚠️ La liste d'exceptions est VIDE, et c'est le bon moment pour l'ouvrir : le
 *  dépôt est conforme aujourd'hui. Une exception ajoutée plus tard devra dire
 *  pourquoi, et une exception qui ne sert plus fait échouer ce contrôle.
 *
 *  Lancer : node scripts/check-entete-carte.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';

const RACINE = 'src';

/** Le marqueur d'une carte de liste, sous ses deux écritures Svelte. */
const CARTE = /class="[^"]*\bcarte-liste\b|class:carte-liste/;
/** L'emploi du composant — par l'IMPORT, qu'une portée locale ne peut pas feindre. */
const EMPLOI = /import\s+EnteteCarte\s+from/;

/**
 *  Les fichiers qui rendent `.carte-liste` sans `EnteteCarte`, avec leur motif.
 *
 *  🔴 VIDE au 12/09/2026 — le dépôt est entièrement conforme. Toute entrée
 *  ajoutée ici doit porter sa raison, et une entrée devenue inutile fait échouer
 *  le contrôle : une exception reconduite « au cas où » masquerait la suivante.
 */
const EXCEPTIONS = {};

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (e.endsWith('.svelte')) acc.push(p);
	}
	return acc;
}

/**  Un chevron rendu par la carte elle-même.
 *
 *   🔴 SIX cartes remplissaient un `slot="chevron"` avec la même ligne, et deux
 *   d'entre elles y écrivaient `expanded || enEdition` là où les quatre autres
 *   écrivaient `expanded` — deux façons de dire « cette carte est dépliée »,
 *   pour une classe que l'appelant pose DÉJÀ sur la carte. `EnteteCarte` rend
 *   le chevron depuis le 18/09/2026, et sa rotation se lit sur
 *   `.carte-liste.expanded`. */
const CHEVRON_RECOPIE = /slot=["']chevron["']|class=["']chevron["']/;

/**  La décision, PURE — testable sans toucher au disque.
 *   @returns {'ok'|'sans-entete'|'chevron-recopie'|'hors-sujet'} */
export function verdictCarte(source) {
	if (!CARTE.test(source)) return 'hors-sujet';
	if (!EMPLOI.test(source)) return 'sans-entete';
	return CHEVRON_RECOPIE.test(source) ? 'chevron-recopie' : 'ok';
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const t = (libelle, attendu, src) => {
		const r = verdictCarte(src);
		if (r === attendu) console.log(`PASS  ${libelle} → ${r}`);
		else {
			console.error(`FAIL  ${libelle}  attendu=${attendu} obtenu=${r}`);
			ko = 1;
		}
	};
	t(
		'carte conforme',
		'ok',
		'import EnteteCarte from \'./EnteteCarte.svelte\';\n<div class="carte-liste">',
	);
	t(
		'carte conforme (class:)',
		'ok',
		"import EnteteCarte from './x';\n<div class:carte-liste={!a}>",
	);
	//  🔴 LE cas qui donne sa raison d'être au contrôle : c'est l'état exact dans
	//  lequel `CarteContrat` et `CartePrestataire` sont restées un mois.
	t('carte qui réécrit son en-tête', 'sans-entete', '<div class="carte-liste expanded">');
	//  Un fichier qui ne rend aucune carte n'est ni bon ni mauvais : sans objet.
	t('fichier sans carte', 'hors-sujet', '<div class="autre-chose">');
	//  ⚠️ Le mot dans un COMMENTAIRE qui raconte la règle ne doit pas déclencher
	//  un import : c'est le faux positif que trois contrôles de ce dépôt ont déjà
	//  rencontré. Ici il est ACCEPTÉ comme carte — le motif est volontairement
	//  grossier — mais l'import suffit alors à le satisfaire.
	t(
		'mention en commentaire, avec import',
		'ok',
		'import EnteteCarte from \'./x\';\n// class="carte-liste"',
	);
	//  🔴 Le second cas que ce contrôle refuse depuis le 18/09/2026.
	t(
		'carte qui rend son propre chevron',
		'chevron-recopie',
		`import EnteteCarte from './x';
<div class="carte-liste"><span class="chevron">›</span>`,
	);
	t(
		'carte qui remplit le slot chevron',
		'chevron-recopie',
		`import EnteteCarte from './x';
<div class="carte-liste"><svelte:fragment slot="chevron">`,
	);
	//  Le cas zéro : une source vide ne rend pas « ok », elle rend « hors-sujet ».
	t('source vide', 'hors-sujet', '');
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	process.exit(ko);
}

const tous = fichiers(RACINE);
const fautifs = [];
const chevrons = [];
const exceptionsVues = new Set();
let cartes = 0;

for (const f of tous) {
	const rel = f
		.split(sep)
		.join('/')
		.replace(/^src\//, '');
	const verdict = verdictCarte(readFileSync(f, 'utf8'));
	if (verdict === 'hors-sujet') continue;
	cartes++;
	if (verdict === 'ok') continue;
	if (rel in EXCEPTIONS) {
		exceptionsVues.add(rel);
		continue;
	}
	(verdict === 'chevron-recopie' ? chevrons : fautifs).push(rel);
}

let echec = false;

//  🔴 LE CAS ZÉRO (`standards/04` §2) : si le parcours n'a trouvé AUCUNE carte,
//  le contrôle n'a pas mesuré — il ne rend pas OK. C'est l'erreur qui rendrait
//  ce garde-fou silencieux le jour où l'arborescence change.
if (cartes === 0) {
	console.error(
		'\n✗ INCONNU : aucune carte de liste trouvée sous `src/`.\n\n' +
			'  Le contrôle ne peut pas mesurer — arborescence déplacée, ou classe\n' +
			'  renommée. Un relevé vide n’est pas un dépôt conforme.\n',
	);
	process.exit(2);
}

if (fautifs.length) {
	echec = true;
	console.error(`\n✗ ${fautifs.length} carte(s) de liste réécrivent leur en-tête :\n`);
	for (const f of fautifs) console.error(`  ${f}`);
	console.error(
		'\n  `EnteteCarte` porte le titre sur sa propre ligne (R1 — sinon il disparaît\n' +
			'  sur téléphone), le geste asymétrique et l’ordre tags / date / actions /\n' +
			'  chevron. Réécrit à la main, chacun de ces trois points se reprend.\n' +
			'  → employer `EnteteCarte`, ou inscrire le fichier dans `EXCEPTIONS` avec\n' +
			'    son motif.\n',
	);
}

if (chevrons.length) {
	echec = true;
	console.error(`\n✗ ${chevrons.length} carte(s) rendent leur propre chevron :\n`);
	for (const f of chevrons) console.error(`  ${f}`);
	console.error(
		'\n  `EnteteCarte` le rend depuis le 18/09/2026, et sa rotation se lit sur\n' +
			'  `.carte-liste.expanded` — l’état que la carte porte déjà. Le transmettre\n' +
			'  une seconde fois, c’est écrire deux fois le même fait : c’est ainsi que\n' +
			'  quatre cartes en sont venues à dire `expanded` et deux\n' +
			'  `expanded || enEdition`, pour la même classe.\n' +
			'  → retirer le chevron de la carte.\n',
	);
}

const perimees = Object.keys(EXCEPTIONS).filter((f) => !exceptionsVues.has(f));
if (perimees.length) {
	echec = true;
	console.error('\n✗ Ces exceptions ne servent plus — les retirer :\n');
	for (const f of perimees) console.error(`  ${f}`);
	console.error('\n  Une exception reconduite « au cas où » masquerait la suivante.\n');
}

if (echec) process.exit(1);
console.log(
	`✓ En-tête de carte : ${cartes} carte(s) de liste, toutes rendues par ` +
		`EnteteCarte — ${Object.keys(EXCEPTIONS).length} exception(s) déclarée(s).`,
);
