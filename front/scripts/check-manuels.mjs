#!/usr/bin/env node
/**
 * Garde-fou : les manuels lus par les résidents doivent être du HTML BIEN FORMÉ.
 *
 * Le 17/08/2026 (#410), `docs/manuel-utilisateur.html` portait un `</li>` qui ne
 * fermait rien et un `<li>` jamais fermé, dans un `<div>` qui n'est pas une liste.
 * Le défaut vivait dans les DEUX copies (`docs/` et `front/static/`), c'est-à-dire
 * dans le document que lisent les résidents.
 *
 * Pourquoi personne ne l'avait vu : les navigateurs réparent ce balisage en
 * silence. La page s'affiche, donc elle a l'air correcte — l'artefact est cassé et
 * le comportement le masque. Seul un analyseur strict pouvait le dire, et il
 * n'était branché nulle part : `npm run lint` (`prettier --check . && eslint .`)
 * n'était dans aucun job de CI.
 *
 * Ce contrôle valide SANS exiger la mise en forme. C'est délibéré : ces manuels
 * sont des documents denses écrits à la main, que `prettier --write` réécrirait de
 * bout en bout pour un diff énorme et sans valeur — au point qu'on les a mis dans
 * `.prettierignore`. Or c'est justement `prettier --check` qui avait trouvé le
 * défaut. On garde donc l'analyseur et on jette la mise en forme : `prettier.format`
 * est appelé pour son PARSEUR, et son résultat est ignoré. Un ignore posé sans
 * remplacer le contrôle qu'il éteint rendrait le défaut invisible à nouveau.
 *
 * Les quatre fichiers sont contrôlés, y compris les copies de `front/static/` : la
 * synchronisation est vérifiée ailleurs (`api/tests/test_documentation.py`), mais
 * un contrôle qui ne regarderait que la source croirait sur parole que la copie lui
 * ressemble.
 *
 * Usage : npm run lint:manuels   (exit 1 si un manuel est mal formé)
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import * as prettier from 'prettier';

const FRONT = join(dirname(fileURLToPath(import.meta.url)), '..');
const RACINE = join(FRONT, '..');

//  🔴 UN SEUL manuel depuis le 02/09/2026 (#651) : la « version 1 page » a été
//  supprimée sur arbitrage. Deux documents sur le même produit divergent au
//  premier écran qui change.
const MANUELS = ['docs/manuel-utilisateur.html', 'front/static/manuel-utilisateur.html'];

const echecs = [];

for (const chemin of MANUELS) {
	const absolu = join(RACINE, chemin);
	let contenu;
	try {
		contenu = readFileSync(absolu, 'utf8');
	} catch (e) {
		// Un manuel absent n'est pas un « rien à signaler » : c'est le document que
		// lisent les résidents qui manque, ou qui a été déplacé sans mettre ce
		// contrôle à jour.
		echecs.push(`${chemin} : illisible — ${e.code === 'ENOENT' ? 'fichier absent' : e.message}`);
		continue;
	}
	try {
		// Le résultat est jeté : seul compte le fait que le document se PARSE.
		await prettier.format(contenu, { parser: 'html', filepath: absolu });
	} catch (e) {
		const lieu = e.loc?.start ? ` (ligne ${e.loc.start.line}, colonne ${e.loc.start.column})` : '';
		echecs.push(`${chemin}${lieu} : ${String(e.message).split('\n')[0]}`);
	}
}

if (echecs.length) {
	console.error('\n❌ Balisage mal formé dans la documentation lue par les résidents :\n');
	for (const l of echecs) console.error(`   ${l}`);
	console.error(
		"\nLes navigateurs réparent ce genre de balisage en silence : la page s'affiche quand même.\n" +
			"Corriger dans `docs/`, puis resynchroniser vers `front/static/` (copie à l'octet).\n" +
			'⚠️ Jamais avec `sed -i` : ces fichiers sont versionnés en CRLF, que sed réécrit en LF.\n',
	);
	process.exit(1);
}

console.log(`✓ ${MANUELS.length} manuels analysés — balisage bien formé.`);
