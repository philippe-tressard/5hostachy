/**
 * Le CSS GLOBAL du site, quel que soit le nombre de fichiers qui le composent.
 *
 * ## Pourquoi ce module existe (27/08/2026, #453)
 *
 * `app.css` faisait 1 223 lignes — 1 961 une fois reformaté — et le garde-fou de
 * modularité (rang 1) refuse qu'il grossisse. Il a été découpé en quatre
 * fragments dans `src/styles/`, qu'il se contente désormais d'importer dans
 * l'ordre exact où leurs règles se trouvaient.
 *
 * 🔴 QUATRE CONTRÔLES LISAIENT `app.css` PAR SON CHEMIN, et les quatre ont
 * échoué au découpage — `check-classes-nues`, `check-entete-page`,
 * `check-styles-nus`, `check-modificateurs`. C'est la bonne façon d'échouer :
 * ils cherchaient les règles là où elles n'étaient plus, et l'ont dit. Un
 * contrôle qui aurait cherché « quelque part dans le front » serait resté vert
 * sur un fichier vidé de sa substance.
 *
 * ⚠️ Ils lisaient tous LA MÊME CHOSE, chacun à sa façon. C'est cette lecture qui
 * est mise en commun ici : ajouter un cinquième fragment de style ne demandera
 * de toucher à aucun contrôle.
 *
 * Le cas zéro est porté ici aussi : sans règle trouvée, on ne conclut pas — les
 * appelants reçoivent une chaîne vide et doivent la traiter comme INCONNU, pas
 * comme « rien n'est défini » (`standards/04` §2).
 */
import { readFileSync, existsSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

/**
 * Concatène `app.css` et tous les fragments de `styles/`, dans l'ordre des
 * `@import` puisque c'est celui de la cascade.
 *
 * @param racine chemin de `front/src`
 * @returns le CSS global concaténé — chaîne vide si rien n'a pu être lu
 */
export function cssGlobal(racine) {
	const morceaux = [];
	const appCss = join(racine, 'app.css');
	if (existsSync(appCss)) morceaux.push(readFileSync(appCss, 'utf8'));

	const dossier = join(racine, 'styles');
	if (existsSync(dossier)) {
		//  Tri alphabétique et non l'ordre des `@import` : ces contrôles cherchent
		//  ce qui est DÉFINI, pas ce qui l'emporte. La cascade ne les concerne pas.
		for (const nom of readdirSync(dossier).sort()) {
			if (nom.endsWith('.css')) morceaux.push(readFileSync(join(dossier, nom), 'utf8'));
		}
	}
	return morceaux.join('\n');
}

/** Les fichiers réellement lus — pour qu'un message d'erreur puisse les nommer. */
export function fichiersCssGlobal(racine) {
	const liste = [];
	if (existsSync(join(racine, 'app.css'))) liste.push('app.css');
	const dossier = join(racine, 'styles');
	if (existsSync(dossier)) {
		for (const nom of readdirSync(dossier).sort()) {
			if (nom.endsWith('.css')) liste.push(`styles/${nom}`);
		}
	}
	return liste;
}
