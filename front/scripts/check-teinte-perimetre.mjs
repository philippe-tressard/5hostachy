#!/usr/bin/env node
/**
 *  Self-test de la **teinte d'une pastille de périmètre** (`$lib/perimetres/teinte`).
 *
 *  ## La règle, arbitrée à l'écran
 *
 *  > « La couleur des catégories de niveau *n* hérite de la catégorie de
 *  >   niveau 1. »
 *  > « Si plusieurs catégories de niveau 1 : celle du bâtiment s'il n'y en a
 *  >   qu'un, sinon celle de toute la copropriété. » (13/09/2026)
 *
 *  ## Pourquoi ce contrôle existe, et pourquoi il a dû être RENFORCÉ
 *
 *  12/09 : sur le kanban, « Bât. 1 » était bleu clair et « Ascenseur », qui est
 *  DANS le bâtiment 1, sortait rose — la couleur venait d'un condensat du code
 *  entier. Corrigé, testé, livré.
 *
 *  🔴 13/09, le défaut était **toujours là** : « Bât. 1 › ascenseur » et « Local
 *  technique › eau » partageaient une couleur. Le correctif lisait le champ
 *  `profondeur` pour remonter l'arbre, et ce champ ne portait pas ce qu'on
 *  croyait : `undefined > 1` vaut `false`, la remontée s'arrêtait aussitôt, et
 *  tout retombait sur le condensat — une chance sur neuf de collision par paire.
 *
 *  ⚠️ Mes onze cas d'essai passaient, parce qu'ils fournissaient eux-mêmes un
 *  `profondeur` juste. **Un test qui construit sa donnée d'entrée ne prouve rien
 *  sur celle que la production fournit.** Le niveau se CALCULE désormais depuis
 *  la chaîne des `parent`, et les arbres d'essai ci-dessous ne portent plus
 *  aucune profondeur : le test ne peut plus mentir dans ce sens-là.
 *
 *  Lancer : npm run lint:teinte
 */
import {
	PALETTE_PERIMETRE,
	TEINTE_COPROPRIETE,
	codeDeTeinte,
	premierNiveauDe,
	rangPremierNiveau,
	teinteDuCode,
} from '../src/lib/perimetres/teinte.ts';

//  ⚠️ AUCUN champ `profondeur` ici : c'est le point du renforcement. L'arbre ne
//  porte que ce dont la règle a besoin — un code et un parent.
const ARBRE = {
	residence: { code: 'residence', parent: null },
	'bat:1': { code: 'bat:1', parent: 'residence' },
	'bat:2': { code: 'bat:2', parent: 'residence' },
	'local-technique': { code: 'local-technique', parent: 'residence' },
	ascenseur1: { code: 'ascenseur1', parent: 'bat:1' },
	hall1: { code: 'hall1', parent: 'bat:1' },
	cage1: { code: 'cage1', parent: 'ascenseur1' },
	eau: { code: 'eau', parent: 'local-technique' },
	ascenseur2: { code: 'ascenseur2', parent: 'bat:2' },
	//  Un cycle, écrit à la main en base : il ne doit pas figer l'écran.
	boucleA: { code: 'boucleA', parent: 'boucleB' },
	boucleB: { code: 'boucleB', parent: 'boucleA' },
};
const lire = (c) => ARBRE[c];
const PREMIER = premierNiveauDe(Object.keys(ARBRE), lire);
const couleur = (code) => teinteDuCode(code, rangPremierNiveau(codeDeTeinte(code, lire), PREMIER));

let echecs = 0;
let cas = 0;
const verifier = (nom, obtenu, attendu) => {
	cas++;
	if (obtenu === attendu) return;
	echecs++;
	console.error(`  ✗ ${nom}\n      attendu : ${attendu}\n      obtenu  : ${obtenu}`);
};

//  ── Le premier niveau se reconnaît sans `profondeur` ────────────────────────
verifier(
	'les trois espaces de tête sont reconnus',
	PREMIER.join(','),
	'bat:1,bat:2,local-technique',
);

//  ── L'héritage : niveau n → niveau 1 ────────────────────────────────────────
verifier("l'ascenseur du bât. 1 hérite du bât. 1", codeDeTeinte('ascenseur1', lire), 'bat:1');
verifier('le hall du bât. 1 aussi', codeDeTeinte('hall1', lire), 'bat:1');
verifier('à trois niveaux, on remonte au niveau 1', codeDeTeinte('cage1', lire), 'bat:1');
verifier("l'eau hérite du local technique", codeDeTeinte('eau', lire), 'local-technique');
verifier('un espace de tête est sa propre teinte', codeDeTeinte('bat:1', lire), 'bat:1');
verifier('la racine reste elle-même', codeDeTeinte('residence', lire), 'residence');

//  ── 🔴 LE CAS SIGNALÉ DEUX FOIS ─────────────────────────────────────────────
verifier(
	'ascenseur du bât. 1 ≠ eau du local technique',
	couleur('ascenseur1') !== couleur('eau'),
	true,
);
verifier(
	'deux espaces du MÊME bâtiment partagent leur couleur',
	couleur('hall1'),
	couleur('ascenseur1'),
);
verifier('bât. 1 ≠ bât. 2', couleur('ascenseur1') !== couleur('ascenseur2'), true);
verifier('un espace hérite de la couleur de son bâtiment', couleur('cage1'), couleur('bat:1'));

//  ── Couleurs distinctes tant que la palette le permet ───────────────────────
const NEUF = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i'];
const couleurs = NEUF.map((c) => teinteDuCode(c, rangPremierNiveau(c, NEUF)));
if (new Set(couleurs).size !== NEUF.length) {
	console.error(`  ✗ neuf espaces de tête, ${new Set(couleurs).size} couleurs distinctes`);
	echecs++;
}
cas++;
//  ⚠️ Au-delà de la palette, la collision est inévitable — neuf couleurs ne
//  peuvent pas en distinguer dix. Le contrôle le CONSTATE plutôt que de laisser
//  croire à une garantie qui n'existe pas.
verifier(
	'le dixième reprend la première',
	teinteDuCode('x', PALETTE_PERIMETRE.length),
	teinteDuCode('x', 0),
);

//  ── Le repli : « toute la copropriété », jamais une couleur au hasard ───────
verifier('rang inconnu → couleur de la copropriété', teinteDuCode('bat:1', -1), TEINTE_COPROPRIETE);
verifier('code hors du premier niveau → rang -1', rangPremierNiveau('ascenseur1', PREMIER), -1);
//  🔴 CAS ZÉRO : arbre non chargé. On rend le code lui-même, donc le repli — et
//  jamais une pastille sans couleur, qui se lirait « aucun périmètre ».
verifier(
	'arbre vide → le code lui-même',
	codeDeTeinte('bat:1', () => undefined),
	'bat:1',
);
verifier(
	'arbre vide → couleur de la copropriété',
	teinteDuCode('bat:1', rangPremierNiveau('bat:1', [])),
	TEINTE_COPROPRIETE,
);
//  ⚠️ Le gris du repli n'est PAS dans la palette : un espace de tête ne peut pas
//  le porter, donc « non rattaché » ne peut pas se lire « rattaché à celui-là ».
if (PALETTE_PERIMETRE.includes(TEINTE_COPROPRIETE)) {
	console.error('  ✗ la couleur de repli appartient à la palette — elle serait ambiguë');
	echecs++;
}
cas++;

//  ── Robustesse ──────────────────────────────────────────────────────────────
verifier('cycle borné', codeDeTeinte('boucleA', lire), 'boucleA');
verifier(
	'rang insensible à la casse',
	rangPremierNiveau('BAT:1', PREMIER),
	rangPremierNiveau('bat:1', PREMIER),
);
//  Un arbre SANS racine unique — plusieurs têtes côte à côte — reste lisible.
const PLAT = { a: { code: 'a', parent: null }, b: { code: 'b', parent: null } };
verifier(
	'arbre plat : les racines SONT le premier niveau',
	premierNiveauDe(['a', 'b'], (c) => PLAT[c]).join(','),
	'a,b',
);
verifier('teinte stable', teinteDuCode('x', 0), teinteDuCode('x', 0));
if (!/^#[0-9a-f]{6}$/.test(teinteDuCode('x', 0))) {
	console.error('  ✗ la teinte n’est pas une couleur hexadécimale');
	echecs++;
}
cas++;

if (echecs) {
	console.error(`\n✗ Teinte de périmètre : ${echecs} cas en échec sur ${cas}.\n`);
	process.exit(1);
}
console.log(
	`✓ Teinte de périmètre : ${cas} cas — le niveau se calcule, deux branches ne partagent pas une couleur.`,
);
