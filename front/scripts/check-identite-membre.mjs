#!/usr/bin/env node
/**
 *  L'identité d'un membre d'annuaire — civilité, prénom, NOM — se saisit dans
 *  `CarteMembre`, et nulle part ailleurs.
 *
 *  ## Pourquoi ce contrôle (18/09/2026, #779)
 *
 *  `espace-cs/+page.svelte` rendait DEUX fiches modifiables : le membre du
 *  conseil syndical et celui du syndic. Les trois champs d'identité, le lien
 *  vers un inscrit (« Inscrit lié », « Délier », « Aucun inscrit avec ce NOM »)
 *  et le geste de dépliage y étaient recopiés au caractère près.
 *
 *  🔴 **Et les copies avaient divergé sur ce qui coûte** : la fiche du syndic
 *  n'avait **pas** de pied de formulaire. On y entrait par le crayon, et on ne
 *  pouvait en sortir que par lui — « Annuler » n'existait pas de ce côté. Cette
 *  différence-là ne se voit pas en relisant l'un des deux blocs : il faut les
 *  comparer, à cent cinquante lignes d'écart.
 *
 *  ## Ce que le contrôle mesure
 *
 *  Tout fichier qui écrit le libellé `Civilité` doit importer `CarteMembre`.
 *  C'est volontairement grossier — il ne juge pas la composition de la fiche,
 *  seulement qu'elle n'est pas réécrite. Le libellé est le marqueur le plus sûr :
 *  une troisième fiche d'annuaire le portera, quel que soit son balisage.
 *
 *  ⚠️ La liste d'exceptions est VIDE, et c'est le bon moment pour l'ouvrir : le
 *  dépôt est conforme aujourd'hui. Une exception ajoutée plus tard devra dire
 *  pourquoi, et une exception qui ne sert plus fait échouer ce contrôle.
 *
 *  Lancer : node scripts/check-identite-membre.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';

const RACINE = 'src';
/** Le composant qui a le droit — et le devoir — de saisir une identité. */
const SOURCE = 'lib/components/CarteMembre.svelte';

/**  Le marqueur d'une fiche d'identité : le libellé du premier champ. */
//  `"` compte (#1329) : la civilité est un champ en pastilles, `libelle="Civilité"`.
const IDENTITE = /(^|>|\s|")Civilité(\s|<|$|")/m;
/**  L'emploi du composant — par l'IMPORT, qu'une portée locale ne peut pas feindre. */
const EMPLOI = /import\s+CarteMembre(\s*,\s*\{[^}]*\})?\s+from/;

/**
 *  Les fichiers autorisés à saisir une identité eux-mêmes, avec leur motif.
 *
 *  🔴 VIDE au 18/09/2026 — les deux copies ont été converties dans le même lot.
 *  Une entrée devenue inutile fait échouer le contrôle : une exception
 *  reconduite « au cas où » masquerait la suivante.
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

/**  La décision, PURE — testable sans toucher au disque.
 *   @returns {'ok'|'sans-composant'|'hors-sujet'} */
export function verdictIdentite(source) {
	if (!IDENTITE.test(source)) return 'hors-sujet';
	return EMPLOI.test(source) ? 'ok' : 'sans-composant';
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const t = (libelle, attendu, src) => {
		const r = verdictIdentite(src);
		if (r === attendu) console.log(`PASS  ${libelle} → ${r}`);
		else {
			console.error(`FAIL  ${libelle}  attendu=${attendu} obtenu=${r}`);
			ko = 1;
		}
	};
	t('fiche conforme', 'ok', "import CarteMembre from './x';\n<label>Civilité</label>");
	//  L'import avec le type de base, la forme réelle de l'appelant.
	t(
		'fiche conforme, import avec le type',
		'ok',
		"import CarteMembre, { type MembreBase } from './x';\n Civilité\n",
	);
	//  🔴 LE cas qui donne sa raison d'être au contrôle : l'état exact des deux
	//  blocs de l'Espace CS avant ce lot.
	t('fiche qui réécrit son identité', 'sans-composant', '<label class="field">\n\tCivilité\n');
	//  Un fichier qui ne saisit aucune identité n'est ni bon ni mauvais.
	t('fichier sans identité', 'hors-sujet', '<div>Prénom</div>');
	//  ⚠️ Le mot DANS UN AUTRE MOT ne compte pas : « incivilité » n'est pas un
	//  champ. C'est le faux positif qui ferait désarmer le contrôle.
	t('le mot dans un autre mot', 'hors-sujet', '<p>une incivilité signalée</p>');
	//  Le cas zéro : une source vide ne rend pas « ok », elle rend « hors-sujet ».
	t('source vide', 'hors-sujet', '');
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	process.exit(ko);
}

const tous = fichiers(RACINE);
const fautifs = [];
const exceptionsVues = new Set();
let fiches = 0;

for (const f of tous) {
	const rel = f
		.split(sep)
		.join('/')
		.replace(/^src\//, '');
	const verdict = verdictIdentite(readFileSync(f, 'utf8'));
	if (verdict === 'hors-sujet') continue;
	fiches++;
	if (verdict === 'ok' || rel === SOURCE) continue;
	if (rel in EXCEPTIONS) {
		exceptionsVues.add(rel);
		continue;
	}
	fautifs.push(rel);
}

let echec = false;

//  🔴 LE CAS ZÉRO (`standards/04` §2) : si le parcours n'a trouvé AUCUNE fiche,
//  le contrôle n'a pas mesuré — il ne rend pas OK. C'est l'erreur qui le rendrait
//  silencieux le jour où le libellé change.
if (fiches === 0) {
	console.error(
		'\n✗ INCONNU : aucune fiche d’identité trouvée sous `src/`.\n\n' +
			'  Le contrôle ne peut pas mesurer — libellé renommé, ou composant déplacé.\n' +
			'  Un relevé vide n’est pas un dépôt conforme.\n',
	);
	process.exit(2);
}

if (fautifs.length) {
	echec = true;
	console.error(`\n✗ ${fautifs.length} fichier(s) saisissent une identité de membre eux-mêmes :\n`);
	for (const f of fautifs) console.error(`  ${f}`);
	console.error(
		'\n  `CarteMembre` porte la carte, son en-tête (donc R1 et le geste asymétrique),\n' +
			'  les trois champs d’identité, le lien vers un inscrit et le pied du\n' +
			'  formulaire — celui qui manquait à la fiche du syndic.\n' +
			'  → employer `CarteMembre`, ou inscrire le fichier dans `EXCEPTIONS` avec\n' +
			'    son motif.\n',
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
	`✓ Identité de membre : ${fiches} fiche(s) trouvée(s), toutes rendues par ` +
		`CarteMembre — ${Object.keys(EXCEPTIONS).length} exception(s) déclarée(s).`,
);
