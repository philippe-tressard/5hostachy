#!/usr/bin/env node
/**
 * Garde-fou : le renouvellement silencieux de session ne se désactive que par une
 * liste NOMINATIVE de chemins — jamais par un préfixe.
 *
 * Le 16/08/2026 (#379), un utilisateur signale qu'après un temps d'utilisation un
 * rafraîchissement affiche la page demandée mais avec un menu réduit à la seule
 * marque, et qu'il faut un SECOND rafraîchissement pour voir la mire.
 *
 * La cause était une exception écrite en préfixe. `client.ts` désactivait le
 * renouvellement sur 401 pour tout chemin commençant par `/auth/` — l'intention
 * étant d'empêcher `/auth/refresh` de se rappeler lui-même. Le préfixe attrapait
 * aussi `/auth/me`, l'appel qui charge l'utilisateur au démarrage. Or l'access
 * token vit 120 min et le refresh token 7 jours (`api/app/config.py`) : pendant
 * sept jours la session restait renouvelable, les requêtes de la page se
 * renouvelaient bien et s'affichaient, mais `me()` était refusé sans qu'on ait
 * essayé — utilisateur nul, menu vide, contenu à l'écran.
 *
 * Ce que ce contrôle vérifie, et pourquoi chaque point compte :
 *
 *   1. Aucun test de PRÉFIXE ne gouverne le renouvellement. C'est la forme même du
 *      défaut : elle est correcte pour la cible visée et fausse pour ses voisines,
 *      et rien à la lecture ne dit lesquelles elle emporte.
 *   2. `/auth/me` (et ses sous-chemins) n'entrent PAS dans la liste. C'est le seul
 *      appel dont l'échec vide le menu sans vider l'écran — donc celui dont la
 *      régression est la plus discrète.
 *   3. Toute entrée de la liste correspond à un chemin RÉELLEMENT appelé. Une
 *      exception qui a cessé de servir doit faire échouer le contrôle, sans quoi
 *      elle survit à ce qu'elle protégeait et personne ne la retire.
 *
 * Script Node sans dépendance, comme `check-dates.mjs`. Il porte sur la SOURCE :
 * la valeur fautive est ici une ligne écrite à la main, pas un défaut de plugin.
 *
 * Usage : npm run lint:session   (exit 1 si violation)
 */
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..');
const PAQUET_API = join(RACINE, 'src', 'lib', 'api');
const CLIENT = join(PAQUET_API, 'client.ts');

function abandonner(message) {
	//  Un contrôle qui ne peut pas s'exécuter renvoie INCONNU, jamais OK.
	console.error(`\n✗ ${message}\n`);
	process.exit(1);
}

if (!existsSync(CLIENT)) {
	abandonner(
		`${relative(RACINE, CLIENT)} est introuvable — le transport HTTP a été déplacé.` +
			`\n  Ce contrôle ne sait plus où regarder : il ne peut pas conclure.`,
	);
}

const source = readFileSync(CLIENT, 'utf-8');

// ── 1. Aucun test de préfixe ne gouverne le renouvellement ────────────────────
const MOTIFS_PREFIXE = [
	/\bpath\s*\.\s*startsWith\s*\(/,
	/\bcheminNu\s*\([^)]*\)\s*\.\s*startsWith\s*\(/,
	/\bpath\s*\.\s*indexOf\s*\(\s*["'`]\/auth/,
	/\/\^\\?\/auth/,
];
const prefixes = MOTIFS_PREFIXE.map((m) => source.match(m)).filter(Boolean);
if (prefixes.length > 0) {
	abandonner(
		`Le renouvellement de session est gouverné par un test de PRÉFIXE dans ` +
			`${relative(RACINE, CLIENT)} :\n\n` +
			prefixes.map((m) => `      ${m[0]}`).join('\n') +
			`\n\n  Un préfixe est correct pour la cible visée et faux pour ses voisines.` +
			`\n  « /auth/ » emportait ainsi /auth/me : la session restait renouvelable` +
			`\n  sept jours, mais le menu se vidait au premier rafraîchissement (#379).` +
			`\n\n  Nommer les chemins un par un dans CHEMINS_SANS_RENOUVELLEMENT.`,
	);
}

// ── 2. La liste existe, et /auth/me n'y figure pas ────────────────────────────
const decl = source.match(/CHEMINS_SANS_RENOUVELLEMENT\s*=\s*\[([^\]]*)\]/);
if (!decl) {
	abandonner(
		`CHEMINS_SANS_RENOUVELLEMENT est introuvable dans ${relative(RACINE, CLIENT)}.` +
			`\n  C'est la liste nominative qui remplace le préfixe : sans elle, ce` +
			`\n  contrôle ne vérifie plus rien et ne peut pas conclure.`,
	);
}

const chemins = [...decl[1].matchAll(/["'`]([^"'`]+)["'`]/g)].map((m) => m[1]);
if (chemins.length === 0) {
	abandonner(
		`CHEMINS_SANS_RENOUVELLEMENT est vide dans ${relative(RACINE, CLIENT)}.` +
			`\n  /auth/refresh doit au minimum y figurer : sans lui, un 401 sur le` +
			`\n  renouvellement rappellerait le renouvellement — récursion infinie.`,
	);
}

if (!chemins.includes('/auth/refresh')) {
	abandonner(
		`/auth/refresh ne figure PAS dans CHEMINS_SANS_RENOUVELLEMENT.` +
			`\n  C'est lui qui renouvelle la session : un 401 de sa part relancerait` +
			`\n  un renouvellement, qui relancerait un renouvellement…`,
	);
}

const fautifs = chemins.filter((c) => c === '/auth/me' || c.startsWith('/auth/me/'));
if (fautifs.length > 0) {
	abandonner(
		`${fautifs.join(', ')} figure(nt) dans CHEMINS_SANS_RENOUVELLEMENT.` +
			`\n\n  /auth/me ne renvoie 401 que par get_current_user, c'est-à-dire pour une` +
			`\n  session RENOUVELABLE. L'en exclure reproduit exactement #379 : les` +
			`\n  requêtes de la page se renouvellent et s'affichent, l'utilisateur reste` +
			`\n  nul, et le menu tombe à sa seule marque — un écran qui affirme une` +
			`\n  session qui n'existe plus.`,
	);
}

// ── 3. Une exception devenue inutile doit échouer ─────────────────────────────
//
// Sans ce point, une entrée survit au chemin qu'elle protégeait : la liste
// grossit, personne ne sait plus laquelle sert, et la prochaine relecture la
// reconduit « au cas où ». C'est la règle posée en #374 — les exceptions se
// déclarent nommément ET échouent quand elles deviennent inutiles.
//
// ⚠ La déclaration elle-même est RETIRÉE du texte fouillé. `client.ts` fait partie
// du paquet analysé : sans cette soustraction, chaque entrée se trouvait dans sa
// propre liste et le contrôle concluait au vert quoi qu'il arrive. Trouvé par le
// test de sensibilité — le contrôle passait, et ne vérifiait rien.
const appels = readdirSync(PAQUET_API)
	.filter((f) => f.endsWith('.ts'))
	.map((f) => readFileSync(join(PAQUET_API, f), 'utf-8'))
	.join('\n')
	.replace(decl[0], '');

const orphelins = chemins.filter((c) => !appels.includes(c));
if (orphelins.length > 0) {
	abandonner(
		`${orphelins.length} exception(s) de CHEMINS_SANS_RENOUVELLEMENT ne correspondent` +
			`\n  à aucun chemin appelé dans ${relative(RACINE, PAQUET_API).replace(/\\/g, '/')} :\n\n` +
			orphelins.map((c) => `      ${c}`).join('\n') +
			`\n\n  Une exception qui a cessé de servir doit être retirée, pas reconduite :` +
			`\n  sinon elle protège un chemin disparu et masque celui qui l'a remplacé.`,
	);
}

console.log(
	`✓ Renouvellement de session : ${chemins.length} exception(s) nominative(s) ` +
		`(${chemins.join(', ')}), aucune sur /auth/me, aucun préfixe, aucune orpheline.`,
);
