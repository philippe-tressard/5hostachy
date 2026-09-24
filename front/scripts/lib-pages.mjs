/**
 *  Lire les deux tables de pages du code — `pages.ts` (ouvertes à tous) et
 *  `pages-roles.ts` (réservées) — sans les importer : ce sont des modules
 *  TypeScript, et les scripts de contrôle tournent en Node nu.
 *
 *  Sorti de `check-manuel-menus.mjs` le 24/09/2026 (#1114), quand la sonde de
 *  `pages_order` a eu besoin de la même lecture : une seconde découpe des blocs
 *  aurait divergé de la première au premier reformatage.
 *
 *  Un bloc de page commence par une ligne `\t{` et finit par `\t},` ; ses
 *  champs de premier niveau sont indentés de deux tabulations — les onglets,
 *  plus profonds, ne s'y confondent pas.
 */
import { readFileSync } from 'node:fs';

const RACINE = new URL('..', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
export const FICHIERS_PAGES = [`${RACINE}src/lib/pages.ts`, `${RACINE}src/lib/pages-roles.ts`];

/** Les blocs de premier niveau des deux tables, dans l'ordre du menu par défaut. */
export function blocsDePages() {
	const blocs = [];
	for (const fichier of FICHIERS_PAGES) {
		const src = readFileSync(fichier, 'utf8').replace(/\r\n/g, '\n');
		const table = src.slice(src.indexOf('PageDef[] = ['));
		for (const bloc of table.split(/^\t\{$/m).slice(1)) blocs.push(bloc.split(/^\t\},$/m)[0]);
	}
	return blocs;
}

/** Les identifiants de page que le code connaît — ceux qu'un `pages_order` peut citer. */
export function idsDePages() {
	return blocsDePages()
		.map((bloc) => bloc.match(/^\t\tid: '([^']+)'/m)?.[1])
		.filter(Boolean);
}
