#!/usr/bin/env node
/*
 *  **Le client TypeScript est la SEULE porte d'entrée de l'API.**
 *
 *  Refuse un appel `api.get/post/patch/put/delete` écrit ailleurs que dans
 *  `src/lib/api/` : une route recopiée dans un écran est une seconde écriture du
 *  contrat, libre de diverger de la première sans que rien ne lève.
 *
 *  ## Pourquoi ce contrôle (#801, 06/09/2026)
 *
 *  Le ticket relevait « 48 méthodes du client que personne n'appelle » et
 *  proposait de les trier pour supprimer les reliquats. Le tri a montré autre
 *  chose : **la moitié n'était pas morte, elle était CONTOURNÉE**. L'écran
 *  écrivait `api.get('/admin/modeles-email')` à la main pendant que
 *  `admin.emailTemplates()` faisait exactement cela, deux fichiers plus loin.
 *
 *  🔴 Et la cause était presque toujours la même : une méthode **trop pauvre**.
 *  `telemetryDashboard()` ne savait pas porter `?scope=` ; `traiterCompte()`
 *  rendait `{}` au lieu de `any`, donc l'écran qui lisait `res.auto_match` ne
 *  compilait pas. Une méthode qui ne couvre pas le besoin ne fait pas contourner
 *  un peu — elle fait recopier la route en entier.
 *
 *  Trois recopies étaient de vraies bombes à retardement :
 *    • `/admin/utilisateurs/{id}/accueil-arrivant` — écrit TROIS fois, corps
 *      compris, et il déclenche des e-mails. Un champ ajouté à deux endroits sur
 *      trois serait parti sans que rien ne lève ;
 *    • `/auth/batiments` et `/admin/utilisateurs` — deux écrans chacun ;
 *    • `ajouter-role` / `retirer-role` — l'URL était construite dans un ternaire,
 *      donc invisible à toute recherche par route. La forme la plus tenace du
 *      contournement : la chaîne recopiée ne ressemble même plus à une route.
 *
 *  ## ⚠️ ZÉRO EXCEPTION, et c'est délibéré
 *
 *  Le ticket refusait à juste titre de geler 48 cas dans une liste de
 *  tolérances — « une tolérance qui ne sert plus finit par en couvrir une qui
 *  compte ». Ce contrôle est posé APRÈS que le compte soit tombé à zéro, donc il
 *  n'a rien à tolérer. Le jour où une exception paraît nécessaire, la vraie
 *  question sera : quelle méthode du client manque, ou est trop pauvre ?
 *
 *  ⚠️ Ce que ce contrôle ne voit PAS : un `fetch()` direct. Il y en a un, dans
 *  `client.ts` lui-même (`tryRefresh`), et il est légitime — le client ne peut
 *  pas s'appeler lui-même pour renouveler la session sans récursion sur le 401.
 *  C'est aussi pourquoi `auth.refresh` figure au relevé des méthodes sans
 *  appelant : elle en a un, mais il ne passe pas par `api.*`.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

const RACINE = 'src';
const CLIENT = 'src/lib/api';

//  `api.get(`, `api.post<T>(`… — le point d'entrée générique, quel que soit le
//  verbe. On ne cherche PAS l'URL : c'est l'appel lui-même qui n'a pas sa place
//  hors du client, même vers une route qu'il déclare déjà.
//
//  ⚠️ `(?<![.\w])` — le `api` doit être une variable, pas la PROPRIÉTÉ d'un
//  objet. `imports-acces.ts` déclare des modèles portant un champ `api` (les
//  huit gestes d'un import, déjà pris dans le client), et `modele.api.patch(id,
//  …)` est justement l'inverse d'un contournement : c'est le paramétrage qui
//  supprime la duplication entre l'import Vigik et l'import télécommandes. Sans
//  cette garde, le contrôle refusait le code le mieux factorisé de l'écran.
const APPEL = /(?<![.\w])api\.(get|post|patch|put|delete)\s*(?:<[^>]*>)?\s*\(/g;

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (/\.(svelte|ts)$/.test(e)) acc.push(p);
	}
	return acc;
}

function analyser(source) {
	const lignes = source.split('\n');
	const trouves = [];
	for (let i = 0; i < lignes.length; i++) {
		//  Une ligne de commentaire ne pose pas d'appel. Le contrôle en cite
		//  plusieurs dans son propre en-tête, et les fichiers du client en citent
		//  aussi : les compter ferait échouer sur de la prose.
		const nue = lignes[i].trim();
		if (nue.startsWith('//') || nue.startsWith('*') || nue.startsWith('/*')) continue;
		APPEL.lastIndex = 0;
		let m;
		while ((m = APPEL.exec(lignes[i]))) trouves.push({ ligne: i + 1, verbe: m[1] });
	}
	return trouves;
}

//  ── Cas zéro : le contrôle doit REFUSER un appel hors du client ──────────────
//  Sans lui, un motif qui ne correspond plus à rien rendrait un vert parfait.
function selftest() {
	const doitRefuser = [
		["api.get<any[]>('/admin/utilisateurs')", 1],
		['const r = await api.post(`/x/${id}/y`, data);', 1],
		['api.delete(url); api.patch(url, d);', 2],
		//  L'URL dans un ternaire : la forme qui avait échappé au relevé manuel.
		['const updated = await api.post<any>(endpoint, { role });', 1],
	];
	const doitAccepter = [
		"//  l'écran écrivait api.get('/admin/modeles-email') en dur",
		' *  `api.post` rend `{}` sans argument de type',
		'adminApi.emailTemplates()',
		'await configApi.testerSmtp(email)',
		//  🔴 Le cas qui a fait resserrer le motif : un modèle d'import porte ses
		//  huit gestes dans un champ `api`, tous pris dans le client. C'est le
		//  paramétrage qui supprime la duplication Vigik / télécommandes, pas un
		//  contournement — et la version large du contrôle le refusait.
		'await modele.api.patch(editId, { …champs });',
		'const r = await this.api.get(id);',
	];
	let ko = 0;
	for (const [src, attendu] of doitRefuser) {
		const n = analyser(src).length;
		if (n !== attendu) {
			console.error(`  ✗ aurait dû trouver ${attendu} appel(s) : ${src} (trouvé ${n})`);
			ko++;
		}
	}
	for (const src of doitAccepter) {
		const n = analyser(src).length;
		if (n !== 0) {
			console.error(`  ✗ aurait dû ignorer : ${src}`);
			ko++;
		}
	}
	if (ko) {
		console.error(`\n✗ Auto-test : ${ko} cas en échec.`);
		process.exit(1);
	}
	console.log('✓ Auto-test : le contrôle refuse bien un appel hors du client.');
}

selftest();

const ecarts = [];
for (const p of fichiers(RACINE)) {
	const chemin = p.split('\\').join('/');
	if (chemin.startsWith(CLIENT + '/') || chemin === CLIENT) continue;
	for (const t of analyser(readFileSync(p, 'utf8'))) {
		ecarts.push(`${chemin}:${t.ligne} — api.${t.verbe}(…)`);
	}
}

if (ecarts.length) {
	console.error(`\n✗ ${ecarts.length} appel(s) à l'API écrit(s) hors de ${CLIENT}/ :\n`);
	for (const e of ecarts) console.error(`  ${e}`);
	console.error(
		`\n  La route appartient au client. Deux gestes possibles, jamais un troisième :\n` +
			`    • la méthode existe   → l'appeler (import depuis '$lib/api') ;\n` +
			`    • elle n'existe pas, ou ne couvre pas le besoin (paramètre manquant,\n` +
			`      retour non typé) → l'AJOUTER ou l'ENRICHIR dans src/lib/api/, puis l'appeler.\n`,
	);
	process.exit(1);
}

console.log(`✓ Aucun appel à l'API hors de ${CLIENT}/ — le client reste la seule porte d'entrée.`);
