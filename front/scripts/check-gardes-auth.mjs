#!/usr/bin/env node
// SPDX-FileCopyrightText: 2026 Philippe Tressard
// SPDX-License-Identifier: LicenseRef-5Hostachy
/**
 * Un garde de route refuse sur un « non » avéré, jamais sur un « pas encore ».
 *
 * ## Le défaut, et sa récidive (#1083, audit du 19/09/2026)
 *
 * `stores/auth.ts` porte la distinction, écrite noir sur blanc :
 *
 * > `isAuthenticated` vaut faux dans **deux** cas très différents : « pas
 * > connecté » et « on ne sait pas encore ». `authResolue` les sépare.
 *
 * Elle existe parce qu'un garde l'avait confondue : `admin/+layout.svelte`
 * testait `$isAdmin` dans son `onMount`, pendant que `(app)/+layout.svelte`
 * chargeait encore l'utilisateur. Il décidait donc toujours sur une valeur vide,
 * et **toute adresse `/admin/**` ouverte directement — lien partagé, favori, F5 —
 * renvoyait au tableau de bord, y compris pour un administrateur.** En navigation
 * interne l'utilisateur est déjà chargé : le défaut était invisible.
 *
 * 🔴 **Corrigé le 12/08/2026 sur `/admin`, et reproduit à l'identique sur
 * `/espace-cs`** — même `onMount`, même store de rôle, même conséquence pour un
 * membre du conseil syndical. Un an de commentaires explicatifs dans `auth.ts`
 * n'a pas empêché la deuxième occurrence : c'est le motif exact que les
 * garde-fous existent pour couvrir (`standards/05` §1).
 *
 * ## Ce que ce contrôle refuse
 *
 * Une redirection qui dépend d'un store de rôle **sans** consulter `authResolue`,
 * quel que soit l'endroit où elle est écrite — `onMount`, bloc réactif, fonction.
 * C'est la conjonction qui compte : rediriger est légitime, tester un rôle aussi ;
 * faire les deux sans savoir si la réponse est connue ne l'est pas.
 *
 * ⚠️ Ce qu'il ne regarde PAS : les redirections qui ne dépendent d'aucun rôle
 * (retour après une action, lien profond). Elles n'ont rien à attendre.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, sep } from 'node:path';
import { globSync } from 'node:fs';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const ICI = dirname(fileURLToPath(import.meta.url));
const SRC = join(ICI, '..', 'src');

/** Les stores qui disent un RÔLE — ceux dont la valeur est vide avant résolution. */
const STORES_DE_ROLE = [
	'isAdmin',
	'isCS',
	'isProprio',
	'isProprioOuCS',
	'isLocataire',
	'isBailleur',
];

/** Ce qui prouve qu'on a attendu de savoir. */
const TEMOIN = 'authResolue';

/**
 * Aucune exception, et ce n'est pas un oubli.
 *
 * J'en avais déclaré une — `lib/stores/auth.ts`, le fichier qui définit
 * `authResolue` — et le contrôle l'a refusée **à sa première exécution** : il ne
 * lit que les `.svelte`, donc cette exception ne couvrait rien. C'est exactement
 * ce qu'une liste d'exceptions doit faire quand une entrée cesse de servir
 * (`standards/04` §40), et elle l'a fait contre celui qui l'écrivait.
 *
 * Si une exception devient nécessaire, elle s'écrit ici **avec sa raison et sa
 * date** — et le bloc ci-dessous la refusera dès qu'elle cessera de servir.
 */
const EXCEPTIONS = {};

/**
 * Ce rôle GOUVERNE-t-il une redirection, ou vit-il ailleurs dans le fichier ?
 *
 * 🔴 « un `goto` quelque part et un rôle quelque part » signalait huit écrans,
 * dont six où les deux n'ont aucun rapport : le calendrier navigue vers un
 * événement et filtre par rôle, sans qu'aucune garde n'existe. Un contrôle qui
 * rougit six fois sur huit à tort est désarmé dans la semaine.
 *
 * Ce qui compte est la **conjonction dans une même instruction** : une condition
 * qui teste le rôle, et un `goto` qu'elle gouverne à moins de 300 caractères.
 */
function gouverneUnGoto(script, role) {
	const motif = new RegExp(`if\\s*\\([^)]*\\$${role}\\b[\\s\\S]{0,300}?goto\\s*\\(`);
	return motif.test(script);
}

const fautes = [];
const exceptionsVues = new Set();

for (const relatif of globSync('**/*.svelte', { cwd: SRC }).map((p) => p.split(sep).join('/'))) {
	const source = neutraliserCommentaires(readFileSync(join(SRC, relatif), 'utf8'));
	//  Le `<script>` seul : une redirection ne s'écrit pas dans le balisage, et
	//  y chercher ajouterait du bruit sans ajouter de cas.
	const script = source.match(/<script[^>]*>([\s\S]*?)<\/script>/)?.[1] ?? '';
	if (!/goto\s*\(/.test(script)) continue;

	const roles = STORES_DE_ROLE.filter((r) => gouverneUnGoto(script, r));
	if (roles.length === 0) continue;

	//  Le fichier attend-il de SAVOIR avant de décider ?
	if (script.includes(TEMOIN)) continue;

	if (EXCEPTIONS[relatif]) {
		exceptionsVues.add(relatif);
		continue;
	}
	fautes.push({ relatif, roles });
}

//  Cas zéro : si plus aucun fichier ne combine `goto` et un store de rôle, ce
//  contrôle ne mesure plus rien — soit les gardes ont changé de forme, soit le
//  motif est périmé (`standards/04` §1 et §27).
const candidats = globSync('**/*.svelte', { cwd: SRC })
	.map((p) => p.split(sep).join('/'))
	.filter((p) => {
		const s = neutraliserCommentaires(readFileSync(join(SRC, p), 'utf8'));
		return STORES_DE_ROLE.some((r) => gouverneUnGoto(s, r));
	});
if (candidats.length === 0) {
	console.error('✗ Cas zéro : aucun écran ne combine `goto()` et un store de rôle.');
	console.error("Les gardes ont changé de forme — ce n'est pas un vert.");
	process.exit(2);
}
console.log(`✓ Cas zéro : ${candidats.length} écran(s) combinent une redirection et un rôle.`);

const perimees = Object.keys(EXCEPTIONS).filter((f) => !exceptionsVues.has(f));
if (perimees.length > 0) {
	console.error(
		`✗ Exception(s) qui ne servent plus : ${perimees.join(', ')} — les retirer, ` +
			`sinon elles couvriront un homonyme réintroduit plus tard.`,
	);
	process.exit(1);
}

if (fautes.length > 0) {
	console.error(`\n✗ ${fautes.length} garde(s) qui décident avant de savoir :\n`);
	for (const f of fautes) {
		console.error(`  src/${f.relatif}  — redirige selon ${f.roles.map((r) => `$${r}`).join(', ')}`);
	}
	console.error(
		`\n  Ces stores valent faux tant que \`authApi.me()\` n'a pas répondu : le garde\n` +
			`  refuse alors sur « on ne sait pas encore », et l'adresse ouverte directement\n` +
			`  — lien partagé, favori, F5 — renvoie au tableau de bord y compris l'ayant droit.\n` +
			`\n  → conditionner la redirection à \`$${TEMOIN}\`, comme \`admin/+layout.svelte\`.\n`,
	);
	process.exit(1);
}

console.log('✓ Toute garde qui refuse selon un rôle attend que l’authentification soit résolue.');
