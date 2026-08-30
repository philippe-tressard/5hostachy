/**
 * Garde-fou : le badge 📍 d'un ticket ne se montre QUE s'il apprend quelque chose.
 *
 * ## La règle (#653, arbitrée à l'écran le 30/08/2026)
 *
 * > « ne montre le badge que s'il diffère du périmètre »
 *
 * Le badge dit le bâtiment du **demandeur**, le tag 🔹 dit le périmètre **visé**.
 * Deux notions différentes — mais elles cohabitent sur la même ligne, portent le
 * même texte, et un seul caractère d'icône les sépare : on lisait « Bât. 4 »
 * deux fois sans pouvoir deviner laquelle disait quoi.
 *
 * Or le cas fréquent est celui-là : on signale surtout ce qui est chez soi. Le
 * badge n'apprend donc quelque chose que dans le cas INVERSE — *« qui signale un
 * problème ailleurs que chez lui ? »* —, et c'est précisément ce que le CS
 * cherche.
 *
 * ## Pourquoi ce contrôle EXÉCUTE le module au lieu de le relire
 *
 * La règle repose sur `batimentsCibles()`, qui **remonte l'arbre** : un ticket
 * visant « Bât. 4 › Toit » concerne le bâtiment 4 sans que le toit le répète.
 * Rien de cela ne se vérifie en lisant le source — il faut un arbre et un appel.
 *
 * 🔴 Et c'est ce qui distingue cette règle d'une comparaison de libellés, qui
 * serait le réflexe : « Bât. 4 » n'est pas une sous-chaîne de « Bât. 4 › Toit »
 * par hasard mais par construction, et ce raccourci se tromperait au premier
 * bâtiment dont le numéro en préfixe un autre — « Bât. 1 » dans « Bât. 12 ».
 * Le dernier cas de ce fichier verrouille exactement cela.
 *
 * Même motif que `check-libelle-perimetre.mjs` : transpiler avec esbuild, puis
 * exécuter. Une règle recopiée dans un test ne prouve rien sur celle qui sert.
 *
 * Usage : node scripts/check-badge-demandeur.mjs --selftest
 */
import { readFileSync, existsSync } from 'node:fs';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const SRC_TICKETS = `${RACINE}/lib/tickets.ts`;
const SRC_PERIMETRES = `${RACINE}/lib/perimetres.ts`;

function echouer(message) {
	console.error(`✗ ${message}`);
	process.exit(1);
}

for (const [quoi, chemin] of [
	['lib/tickets.ts', SRC_TICKETS],
	['lib/perimetres.ts', SRC_PERIMETRES],
]) {
	if (!existsSync(chemin)) echouer(`Cas zéro : ${quoi} est introuvable — contrôle inopérant.`);
}

// ── Les deux modules, EXÉCUTÉS ───────────────────────────────────────────────
const esbuild = await import('esbuild');

async function charger(chemin, reecrire = (s) => s) {
	const { code } = await esbuild.transform(reecrire(readFileSync(chemin, 'utf8')), {
		loader: 'ts',
		format: 'esm',
	});
	return import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
}

let perimetres, tickets;
try {
	perimetres = await charger(SRC_PERIMETRES);
	//  `tickets.ts` importe `./perimetres` : en data: URL, ce chemin relatif ne
	//  résout pas. On le remplace par le module déjà transpilé, réinjecté en
	//  data: URL — c'est ainsi que les DEUX partagent le même arbre, condition
	//  sans laquelle `batimentsCibles` rendrait toujours une liste vide et tous
	//  les cas passeraient au vert pour la mauvaise raison.
	const { code: codePerimetres } = await esbuild.transform(readFileSync(SRC_PERIMETRES, 'utf8'), {
		loader: 'ts',
		format: 'esm',
	});
	const urlPerimetres = `data:text/javascript;base64,${Buffer.from(codePerimetres).toString('base64')}`;
	tickets = await charger(SRC_TICKETS, (s) =>
		s.replace("from './perimetres'", `from '${urlPerimetres}'`),
	);
} catch (e) {
	echouer(`Cas zéro : le module ne se transpile pas (${e.message}).`);
}

const { definirPerimetres, batimentsCibles } = perimetres;
const { afficherBatimentDemandeur } = tickets;
if (typeof afficherBatimentDemandeur !== 'function' || typeof definirPerimetres !== 'function') {
	echouer(
		"Cas zéro : `afficherBatimentDemandeur` ou `definirPerimetres` n'est plus exporté — " +
			'la règle a changé de forme, mettre ce contrôle à jour.',
	);
}

const noeud = (code, parent, libelle, court, ordre, extra = {}) => ({
	id: 0,
	code,
	parent,
	libelle,
	libelle_court: court,
	description: '',
	icone: null,
	batiment_id: null,
	profondeur: 0,
	ordre,
	actif: true,
	portee_globale: false,
	concerne_tous: false,
	selectionnable: true,
	utilise: false,
	...extra,
});

//  ⚠️ « Bât. 1 » et « Bât. 12 » cohabitent VOLONTAIREMENT : c'est le piège qu'une
//  comparaison de libellés par sous-chaîne ne verrait pas.
definirPerimetres([
	noeud('racine', null, 'Copropriété entière', 'Copropriété', 0, { portee_globale: true }),
	noeud('groupe', null, 'Bâtiments', 'Bâtiments', 10, { selectionnable: false }),
	noeud('b1', 'groupe', 'Bâtiment 1', 'Bât. 1', 1, { batiment_id: 1 }),
	noeud('b1/toit', 'b1', 'Toit', 'Toit', 1),
	noeud('b3', 'groupe', 'Bâtiment 3', 'Bât. 3', 3, { batiment_id: 3 }),
	noeud('b3/toit', 'b3', 'Toit', 'Toit', 1),
	noeud('b4', 'groupe', 'Bâtiment 4', 'Bât. 4', 4, { batiment_id: 4 }),
	noeud('b4/toit', 'b4', 'Toit', 'Toit', 1),
	noeud('b12', 'groupe', 'Bâtiment 12', 'Bât. 12', 12, { batiment_id: 12 }),
	noeud('b12/toit', 'b12', 'Toit', 'Toit', 1),
]);

//  Le jeu d'essai ne vaut que si l'arbre a bien été posé — sans quoi
//  `batimentsCibles` rend [] partout et TOUS les cas « montrer » passeraient.
if (batimentsCibles(['b4/toit']).join() !== '4') {
	echouer(
		"Cas zéro : l'arbre d'essai n'est pas en place (`b4/toit` ne remonte pas au bâtiment 4). " +
			'Les cas ci-dessous seraient verts sans rien mesurer.',
	);
}

const CAS = [
	// [libellé, auteur_batiment_id, perimetre_cible, attendu]
	//  🔴 LE CAS DE #653 : le ticket vise le toit du 3 ET du 4, l'auteur est au 4.
	//  « Bât. 4 » apparaissait deux fois sur la même ligne.
	['auteur au 4, ticket sur les toits du 3 et du 4 → MASQUÉ', 4, ['b3/toit', 'b4/toit'], false],
	//  Le cas qui JUSTIFIE le badge : il signale ailleurs que chez lui.
	['auteur au 4, ticket sur le toit du 3 seul → montré', 4, ['b3/toit'], true],
	//  La remontée dans l'arbre : le toit ne répète pas son bâtiment.
	['auteur au 4, ticket sur le toit du 4 → MASQUÉ', 4, ['b4/toit'], false],
	['auteur au 4, ticket sur le bâtiment 4 lui-même → MASQUÉ', 4, ['b4'], false],
	//  Un périmètre global ne vise aucun bâtiment : le badge apprend donc où
	//  habite le demandeur, et il doit rester.
	['auteur au 4, ticket sur toute la copropriété → montré', 4, ['racine'], true],
	['auteur au 4, aucun périmètre → montré', 4, [], true],
	['auteur au 4, périmètre absent → montré', 4, null, true],
	//  Le correctif du point 2 : sans bâtiment, il n'y a rien à montrer — et
	//  surtout pas le périmètre du ticket sous une étiquette de personne.
	['auteur SANS bâtiment → masqué, quel que soit le périmètre', null, ['b3/toit'], false],
	['auteur SANS bâtiment, aucun périmètre → masqué', undefined, [], false],
	//  🔴 LE PIÈGE DE LA COMPARAISON PAR LIBELLÉ : « Bât. 1 » est une sous-chaîne
	//  de « Bât. 12 ». Un rapprochement textuel masquerait ce badge à tort — et
	//  le CS ne verrait pas qu'un résident du 1 signale un problème au 12.
	['auteur au 1, ticket sur le bâtiment 12 → montré', 1, ['b12/toit'], true],
	['auteur au 12, ticket sur le bâtiment 1 → montré', 12, ['b1/toit'], true],
];

let echecs = 0;
for (const [libelle, batiment, perimetre, attendu] of CAS) {
	const obtenu = afficherBatimentDemandeur({
		auteur_batiment_id: batiment,
		perimetre_cible: perimetre,
	});
	if (obtenu === attendu) console.log(`PASS  ${libelle}`);
	else {
		console.error(`FAIL  ${libelle} — attendu ${attendu}, obtenu ${obtenu}`);
		echecs++;
	}
}

if (echecs > 0) {
	console.error(`\n✗ ${echecs} échec(s).`);
	process.exit(1);
}
console.log(`\n✓ Badge du demandeur : ${CAS.length} cas, arbre réellement exécuté.`);
