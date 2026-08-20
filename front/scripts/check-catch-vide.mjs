/**
 * Refuse un appel d'API dont l'échec devient une **collection vide** (#522).
 *
 * ## Le défaut, en trois caractères
 *
 * `.catch(() => [])` transforme toute erreur — session expirée, 500, réseau —
 * en tableau vide. L'écran rend alors **exactement la même chose** que s'il n'y
 * avait rien. Le 19/08/2026, l'utilisateur a cru deux sondages et trois annonces
 * détruits, et en a demandé la restauration : ils étaient intacts en base.
 *
 * 🔴 **Une sortie vide n'est pas un constat** (`standards/04` §1). Un écran qui
 * affirme une absence qu'il n'a pas constatée provoque la réaction qu'une perte
 * réelle provoquerait — avec au bout le risque d'écraser des données saines.
 *
 * ## Pourquoi ce contrôle est ÉTROIT, et doit le rester
 *
 * Le dépôt compte une cinquantaine de `catch` silencieux parfaitement
 * légitimes : marquage de lecture, télémétrie, révocation de jeton, fermeture
 * d'un menu. Les refuser tous ferait désarmer le contrôle dans la semaine — le
 * ticket le disait avant même qu'il existe :
 *
 * > « Le relevé doit précéder la règle : tous les `catch` silencieux ne sont pas
 * >   fautifs. Un contrôle qui les refuserait tous serait désarmé dans la
 * >   semaine. »
 *
 * Il ne vise donc **qu'une** forme : celle qui substitue une **collection vide**
 * à un échec, parce que c'est la seule qui se rend à l'écran comme une absence.
 * `.catch(() => {})` (on ignore, aucune valeur n'est lue) n'est pas concerné.
 *
 * ## Le remède, quand il échoue
 *
 * `$lib/chargement.ts` → `essayer(promesse, repli)` rend `[valeur, erreur]`.
 * Puis, selon la nature de la donnée :
 *   - **liste affichée**   → `EtatListe` (l'échec passe AVANT le vide) ;
 *   - **donnée de référence** (un `<select>`, une table de correspondance)
 *     → `ChargementPartiel`, car un sélecteur vide et un sélecteur en échec ne
 *       se rendent pas de la même façon.
 *
 * Test : node front/scripts/check-catch-vide.mjs --selftest
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const RACINE = new URL('..', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const SRC = join(RACINE, 'src');

/**
 * Les formes refusées : un `catch` qui rend une collection vide.
 *
 * ⚠️ `null` en fait partie quand la valeur est ensuite lue comme un objet —
 * mais `null` sert aussi de « pas de valeur » légitime (un `get()` optionnel),
 * et le distinguer demanderait de suivre l'usage. Le relevé du 20/08/2026 n'a
 * trouvé que deux `.catch(() => null)`, tous deux sur un objet unique et non
 * sur une liste : hors périmètre, assumé, et écrit ici pour que le prochain
 * relevé sache que la question a été posée.
 */
const MOTIF = /\.catch\(\s*\(\s*\)\s*=>\s*(\[\s*\]|\(\s*\{\s*\}\s*\))\s*\)/g;

/**
 * Les exceptions DÉCLARÉES. Vide aujourd'hui, et c'est le point : le lot #522
 * a converti les quinze appels existants, il n'en reste aucun à tolérer.
 *
 * 🔴 Une exception non écrite n'est pas une exception, c'est un oubli qui
 * ressemble à une décision. Toute entrée ajoutée ici porte sa raison — et le
 * contrôle ÉCHOUE si une exception cesse de servir, pour qu'une tolérance
 * devenue inutile ne survive pas à ce qui la justifiait.
 */
const EXCEPTIONS = [];

function fichiers(dossier) {
	const out = [];
	for (const e of readdirSync(dossier)) {
		const p = join(dossier, e);
		if (statSync(p).isDirectory()) out.push(...fichiers(p));
		else if (/\.(svelte|ts)$/.test(e)) out.push(p);
	}
	return out;
}

/**
 * Les occurrences fautives d'un contenu. **Pure** : éprouvable sans dépôt.
 *
 * ⚠️ Les commentaires sont retirés AVANT la recherche. Sans cela, ce contrôle
 * refuserait `chargement.ts`, `erreurs.ts` et `EtatListe.svelte` — les trois
 * fichiers qui expliquent le défaut en le citant. Un contrôle qui interdit d'en
 * parler oblige à taire la raison, et c'est la raison qui se perd en premier.
 */
export function occurrences(contenu) {
	return [...neutraliserCommentaires(contenu).matchAll(MOTIF)].map((m) => m[0]);
}

function selftest() {
	let ko = 0;
	const t = (libelle, attendu, contenu) => {
		const obtenu = occurrences(contenu).length;
		if (obtenu === attendu) console.log(`PASS  ${libelle}`);
		else {
			console.log(`FAIL  ${libelle} — attendu ${attendu}, obtenu ${obtenu}`);
			ko = 1;
		}
	};

	t('le cas du 19/08 : liste avalée', 1, 'const x = await api.list().catch(() => []);');
	t('espaces à l’intérieur', 1, 'api.list().catch( ( ) => [ ] )');
	t('objet vide, même faute', 1, 'api.get().catch(() => ({}));');
	//  🔴 Ce qu'il ne doit PAS refuser — sinon il est désarmé dans la semaine.
	t('catch qui ignore, sans valeur lue', 0, 'marquerLu(id).catch(() => {});');
	t('catch avec un vrai traitement', 0, 'api.list().catch((e) => { toast(e); return []; });');
	t('repli sur null (hors périmètre, assumé)', 0, 'api.get().catch(() => null);');
	t('try/catch ordinaire', 0, 'try { f(); } catch { /* rien */ }');
	//  🔴 Les fichiers qui EXPLIQUENT le défaut le citent : les refuser
	//  obligerait à taire la raison, et la raison se perd en premier.
	t('cité dans un commentaire de ligne', 0, '// on écrivait .catch(() => []) ici');
	t('cité dans un commentaire de bloc', 0, '/* .catch(() => []) était la faute */');
	t('cité dans un commentaire Svelte', 0, '<!-- .catch(() => []) -->');
	//  Une URL contient `//` : le retrait des commentaires ne doit pas tronquer
	//  la ligne et faire disparaître un appel fautif placé après.
	t('URL puis appel fautif sur la même ligne', 1,
		"const u = 'https://x.fr'; api.list().catch(() => []);");

	console.log(ko === 0 ? '\n✓ Autotest : la forme fautive est refusée, les catch légitimes passent.'
	                     : '\n✗ Autotest en échec');
	return ko;
}

function main() {
	if (process.argv.includes('--selftest')) return selftest();

	const coupables = [];
	const exceptionsVues = new Set();
	for (const f of fichiers(SRC)) {
		const rel = relative(RACINE, f).replace(/\\/g, '/');
		const trouve = occurrences(readFileSync(f, 'utf8'));
		if (!trouve.length) continue;
		if (EXCEPTIONS.includes(rel)) {
			exceptionsVues.add(rel);
			continue;
		}
		coupables.push([rel, trouve.length]);
	}

	//  Une exception qui ne sert plus doit FAIRE ÉCHOUER : sinon la liste des
	//  tolérances grossit sans que personne ne la relise, et le contrôle finit
	//  par autoriser plus que ce qu'on croit. Même règle que `check-html.mjs`.
	const mortes = EXCEPTIONS.filter((e) => !exceptionsVues.has(e));
	if (mortes.length) {
		console.error('✗ Exception(s) déclarée(s) qui ne servent plus — les retirer :');
		for (const m of mortes) console.error(`    ${m}`);
		return 1;
	}

	if (!coupables.length) {
		console.log('✓ Aucun appel dont l’échec se rendrait comme une absence.');
		return 0;
	}
	console.error('');
	console.error('✗ Un échec d’appel devient une collection vide — donc une ABSENCE à l’écran :');
	console.error('');
	for (const [f, n] of coupables) console.error(`    ${f}  (${n})`);
	console.error('');
	console.error('  Un écran qui affirme une absence qu’il n’a pas constatée provoque la');
	console.error('  réaction qu’une perte réelle provoquerait (vécu le 19/08/2026).');
	console.error('');
	console.error('  Remède : `essayer()` de `$lib/chargement`, puis `EtatListe` pour une');
	console.error('  liste affichée, ou `ChargementPartiel` pour une donnée de référence.');
	console.error('');
	return 1;
}

process.exit(main());
