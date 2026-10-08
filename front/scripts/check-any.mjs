#!/usr/bin/env node
/**
 *  Les `any` hors du client d'API — un PLAFOND, et il ne fait que baisser (#1571).
 *
 *  ## Pourquoi
 *
 *  Le client d'API ne rend plus aucun `any` depuis la v2.105.0 : ESLint l'y refuse
 *  en erreur (`eslint.config.js`, #1572). Partout ailleurs, la règle était COUPÉE
 *  sans plafond — 275 `any` dans 79 fichiers au 07/10/2026, et rien pour dire
 *  qu'il n'en fallait pas un de plus. C'était la seule dette de la carte #1571
 *  tenue par une tolérance ouverte (`standards/05` §2).
 *
 *  ## Ce qu'il mesure
 *
 *  Ce qu'ESLint lui-même compte, `@typescript-eslint/no-explicit-any` forcée en
 *  erreur sur `src/` : les commentaires, les chaînes et les noms qui contiennent
 *  « any » ne comptent pas, et une regex ne saurait pas les écarter. Le client
 *  (`src/lib/api/`) est hors du compte : il est déjà à zéro, et en erreur.
 *
 *  ## Deux sens, et un témoin
 *
 *  Le contrôle échoue si le compte DÉPASSE le plafond, et aussi s'il passe
 *  DESSOUS : le plafond se baisse alors dans le même lot, sinon la marge regagnée
 *  serait reprise sans un mot par le suivant. Avant de compter, il fait lire à
 *  ESLint un `any` témoin : si la règle ne se déclenche plus (greffon absent,
 *  bloc de configuration déplacé), le compte vaudrait zéro et rien ne le dirait.
 *
 *  Lancer : node scripts/check-any.mjs [--selftest]
 */
import { ESLint } from 'eslint';
import { dirname, join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 *  Le compte autorisé, et son historique.
 *  07/10/2026 (#1571) : 275 relevés ; 245 le même jour — les modèles d'import
 *  d'accès, les colonnes des tâches planifiées, les comptes et les prestataires
 *  typés sur les types du client, un champ lu par son nom passant par `champDe`.
 *  Puis 214 (#1571) : trente et un `catch (e: any)` deviennent `catch (e)`, leur
 *  message passant par `messageErreur` au lieu d'un `e.message ?? '…'` recopié.
 */
export const PLAFOND = 214;

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..');
const REGLE = '@typescript-eslint/no-explicit-any';
const CLIENT = `src${sep}lib${sep}api${sep}`;

/** Le nombre d'`any` par fichier, hors du client, à partir des résultats d'ESLint. */
export function compter(resultats, racine = RACINE) {
	const parFichier = new Map();
	for (const r of resultats) {
		const chemin = relative(racine, r.filePath);
		if (chemin.startsWith(CLIENT)) continue;
		const n = r.messages.filter((m) => m.ruleId === REGLE).length;
		if (n) parFichier.set(chemin, n);
	}
	return parFichier;
}

/** OK, ou la raison de l'échec — dans les deux sens. */
export function verdict(total, plafond) {
	if (total > plafond)
		return `${total} \`any\` hors du client, plafond ${plafond} : ${total - plafond} de trop — typer plutôt (types du client, \`unknown\`, \`champDe\`).`;
	if (total < plafond)
		return `${total} \`any\` hors du client, plafond ${plafond} : baisser PLAFOND à ${total} dans ce lot, et l'écrire dans l'historique.`;
	return 'OK';
}

const eslint = () => new ESLint({ cwd: RACINE, overrideConfig: { rules: { [REGLE]: 'error' } } });

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const cas = (libelle, obtenu, attendu) => {
		const ok = JSON.stringify(obtenu) === JSON.stringify(attendu);
		if (!ok) ko = 1;
		console.log(`${ok ? 'PASS' : 'FAIL'}  ${libelle} → ${JSON.stringify(obtenu)}`);
	};
	const msg = (ruleId) => ({ ruleId });
	const res = (chemin, ...regles) => ({
		filePath: join('/r', chemin),
		messages: regles.map(msg),
	});
	cas(
		'le client est hors du compte, les autres règles aussi',
		[
			...compter(
				[
					res(`src${sep}lib${sep}api${sep}x.ts`, REGLE),
					res(`src${sep}a.ts`, REGLE, REGLE, 'no-undef'),
					res(`src${sep}b.svelte`),
				],
				'/r',
			),
		],
		[[`src${sep}a.ts`, 2]],
	);
	cas('au plafond : OK', verdict(245, 245), 'OK');
	cas('au-dessus : échec', verdict(246, 245).startsWith('246'), true);
	cas('dessous : échec, le plafond se baisse', verdict(240, 245).includes('baisser'), true);
	//  Le témoin : ESLint, tel que configuré, voit-il encore un `any` ?
	const [temoin] = await eslint().lintText('export const x: any = 1;\n', {
		filePath: join(RACINE, 'src', 'lib', 'temoin-check-any.ts'),
	});
	cas(
		'témoin : un `any` dans src/lib est compté par ESLint',
		temoin.messages.filter((m) => m.ruleId === REGLE).length,
		1,
	);
	process.exit(ko);
}

const parFichier = compter(await eslint().lintFiles(['src']));
const total = [...parFichier.values()].reduce((a, b) => a + b, 0);
const v = verdict(total, PLAFOND);
if (v !== 'OK') {
	console.error(`✗ ${v}`);
	const tri = [...parFichier].sort((a, b) => b[1] - a[1]).slice(0, 10);
	console.error('  Les plus chargés : ' + tri.map(([f, n]) => `${f} (${n})`).join(', '));
	process.exit(1);
}
console.log(`✓ ${total} \`any\` hors du client d'API, ${parFichier.size} fichiers — au plafond.`);
