#!/usr/bin/env node
/**
 *  Self-test de la **teinte d'une pastille de périmètre** (`$lib/perimetres/teinte`).
 *
 *  🔴 Pourquoi il existe (12/09/2026, signalé à l'écran) : sur le kanban, la
 *  pastille « Bât. 1 » était bleu clair et « Ascenseur », qui est DANS le
 *  bâtiment 1, sortait rose. La couleur venait d'un condensat du code ENTIER,
 *  donc deux nœuds d'une même branche tombaient sur deux teintes sans rapport.
 *
 *  ⚠️ C'est un défaut qu'aucun contrôle ne pouvait voir et que je ne peux pas
 *  voir non plus — les écrans sont derrière une connexion. La règle est donc
 *  isolée en fonction **pure** et éprouvée ici : c'est le seul moyen de vérifier
 *  une décision d'affichage sans l'écran (le motif de `boot-role-guard.sh`,
 *  étendu au front par `listeDepliable.ts`).
 *
 *  ⚠️ `--experimental-strip-types` : l'import porte sur le `.ts` par son chemin
 *  RELATIF, un alias `$lib` ne se résolvant pas hors de Vite. C'est pourquoi
 *  `teinte.ts` n'importe rien de `$lib`.
 *
 *  Lancer : npm run lint:teinte
 */
import { codeDeTeinte, teinteDuCode } from '../src/lib/perimetres/teinte.ts';

//  Une arborescence de copropriété réduite à ce qui compte : une racine, deux
//  bâtiments, et des espaces sous chacun — dont un à trois niveaux.
const ARBRE = {
	residence: { code: 'residence', parent: null, profondeur: 0 },
	'bat:1': { code: 'bat:1', parent: 'residence', profondeur: 1 },
	'bat:2': { code: 'bat:2', parent: 'residence', profondeur: 1 },
	ascenseur1: { code: 'ascenseur1', parent: 'bat:1', profondeur: 2 },
	hall1: { code: 'hall1', parent: 'bat:1', profondeur: 2 },
	cage1: { code: 'cage1', parent: 'ascenseur1', profondeur: 3 },
	ascenseur2: { code: 'ascenseur2', parent: 'bat:2', profondeur: 2 },
	//  Un cycle, écrit à la main en base : il ne doit pas figer l'écran.
	boucleA: { code: 'boucleA', parent: 'boucleB', profondeur: 2 },
	boucleB: { code: 'boucleB', parent: 'boucleA', profondeur: 2 },
};
const lire = (c) => ARBRE[c];

let echecs = 0;
let cas = 0;
const verifier = (nom, obtenu, attendu) => {
	cas++;
	if (obtenu === attendu) return;
	echecs++;
	console.error(`  ✗ ${nom}\n      attendu : ${attendu}\n      obtenu  : ${obtenu}`);
};

//  🔴 LE CAS SIGNALÉ : un espace sous un bâtiment prend la teinte du bâtiment.
verifier(
	"l'ascenseur du bât. 1 prend la teinte du bât. 1",
	codeDeTeinte('ascenseur1', lire),
	'bat:1',
);
verifier('le hall du bât. 1 aussi', codeDeTeinte('hall1', lire), 'bat:1');
verifier(
	'et ils ont donc la MÊME couleur',
	teinteDuCode(codeDeTeinte('hall1', lire)),
	teinteDuCode(codeDeTeinte('ascenseur1', lire)),
);
//  Trois niveaux : on remonte jusqu'au premier, pas jusqu'au parent immédiat.
verifier('à trois niveaux, on remonte au bâtiment', codeDeTeinte('cage1', lire), 'bat:1');
//  ⚠️ Le contre-exemple, sans quoi le test passerait aussi avec « tout en une
//  couleur » : deux bâtiments différents gardent deux teintes différentes.
verifier('le bât. 2 garde sa propre teinte', codeDeTeinte('ascenseur2', lire), 'bat:2');
if (teinteDuCode('bat:1') === teinteDuCode('bat:2')) {
	console.error(
		'  ✗ les deux bâtiments tombent sur la même couleur — la palette ne distingue plus',
	);
	echecs++;
}
cas++;
//  Un nœud de premier niveau est sa propre teinte ; la racine aussi.
verifier('un bâtiment est sa propre teinte', codeDeTeinte('bat:1', lire), 'bat:1');
verifier('la racine reste elle-même', codeDeTeinte('residence', lire), 'residence');
//  🔴 CAS ZÉRO : arbre non chargé. On rend le code, jamais une chaîne vide —
//  une pastille sans couleur se lirait « aucun périmètre ».
verifier(
	'arbre vide → le code lui-même',
	codeDeTeinte('bat:1', () => undefined),
	'bat:1',
);
verifier('code inconnu → lui-même', codeDeTeinte('jamais-vu', lire), 'jamais-vu');
//  Un cycle en base ne doit pas suspendre la remontée : elle s'arrête sur le
//  premier nœud déjà vu, et rend celui-là. Ce qui compte est qu'elle RENDE.
verifier('cycle borné', codeDeTeinte('boucleA', lire), 'boucleA');
//  La couleur est STABLE : deux appels rendent la même, et c'en est bien une.
verifier('teinte stable', teinteDuCode('bat:1'), teinteDuCode('bat:1'));
if (!/^#[0-9a-f]{6}$/.test(teinteDuCode('bat:1'))) {
	console.error('  ✗ la teinte n’est pas une couleur hexadécimale');
	echecs++;
}
cas++;

if (echecs) {
	console.error(`\n✗ Teinte de périmètre : ${echecs} cas en échec sur ${cas}.\n`);
	process.exit(1);
}
console.log(`✓ Teinte de périmètre : ${cas} cas — un espace prend la couleur de son bâtiment.`);
