#!/usr/bin/env node
/**
 * Garde-fou : une classe RELAYÉE à un composant doit être stylée en `:global()`.
 *
 * ## 🔴 Le défaut, et il était en production depuis toujours (01/09/2026)
 *
 * `LibelleGroupe` accepte une prop `classe` et l'applique sur **son** `<div>` :
 *
 *     <div class={classe} role="group" …><slot /></div>
 *
 * Ce `<div>` appartient à `LibelleGroupe.svelte`. Il reçoit donc le hash de scope
 * de `LibelleGroupe`, **jamais** celui du fichier qui passe la classe. Une règle
 * écrite à plat chez l'appelant est compilée en `.ma-classe.svelte-<hash-appelant>`
 * et ne correspond à rien :
 *
 *     .lot-checklist.svelte-1f4cvca{display:flex;flex-direction:column;border:…}
 *                    ^^^^^^^^^^^^^ le hash de la PAGE, pas celui du div rendu
 *
 * Les **deux** appelants du site étaient dans ce cas, et leur mise en page était
 * morte depuis leur écriture :
 *
 * | Appelant | Classe | Ce qui ne s'appliquait pas |
 * |---|---|---|
 * | `mon-lot` (via `FormulaireBail`) | `lot-checklist` | bordure, colonne, arrondi |
 * | `auth/inscription` | `field-row` | la grille à deux colonnes |
 *
 * ⚠️ **Rien ne pouvait le signaler.** `svelte-check` n'émet « Unused CSS selector »
 * que si le fichier n'a **aucun** autre usage de la classe — or les deux en avaient
 * un ailleurs dans le même fichier. Le défaut n'est apparu qu'en extrayant le
 * formulaire dans son propre composant, où la classe est devenue seule.
 *
 * C'est la famille de la panne des pastilles nues (v2.67.11) : un style posé d'un
 * côté d'une frontière de composant, le balisage de l'autre.
 *
 * ## Ce que ce contrôle refuse
 *
 * Une classe passée en prop `classe="…"` à un composant, dont le fichier appelant
 * définit la règle **à plat** (`.ma-classe {`) sans `:global(`.
 *
 * La forme juste est le `:global()` **borné par une enveloppe** :
 *
 *     <div class="mon-enveloppe">
 *       <LibelleGroupe … classe="ma-classe">…</LibelleGroupe>
 *     </div>
 *
 *     .mon-enveloppe :global(.ma-classe) { … }
 *
 * ⚠️ Un `:global(.ma-classe)` **nu** est refusé lui aussi : SvelteKit charge la
 * feuille d'une route à la visite et ne la décharge jamais, donc il fuirait vers
 * tout le site, une page à la fois (mémoire `project_css_route_fuite_globale`).
 *
 * Usage : node scripts/check-classe-relayee.mjs
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

import { neutraliserCommentaires as sansCommentaires } from './lib-commentaires.mjs';

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..');
const SOURCE = join(RACINE, 'src');

/**
 * Le composant qui PORTE la prop : il la déclare, il ne la relaie pas. Le lire
 * ferait s'accuser lui-même — comme `SectionDiffusion` pour `lint:apercu`.
 */
const PORTEURS = new Set(['lib/components/LibelleGroupe.svelte']);

function fichiers(dir) {
	const out = [];
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) out.push(...fichiers(p));
		else if (e.endsWith('.svelte')) out.push(p);
	}
	return out;
}

/** Les classes passées en prop `classe="…"` dans ce source. */
function classesRelayees(source) {
	const trouvees = new Set();
	for (const m of source.matchAll(/\bclasse=["']([^"'{}]+)["']/g)) {
		for (const c of m[1].trim().split(/\s+/)) if (c) trouvees.add(c);
	}
	return trouvees;
}

const fautifs = [];
const conformes = [];

for (const chemin of fichiers(SOURCE)) {
	const rel = relative(SOURCE, chemin).split(sep).join('/');
	if (PORTEURS.has(rel)) continue;

	const brut = readFileSync(chemin, 'utf8');
	const source = sansCommentaires(brut);
	const relayees = classesRelayees(source);
	if (relayees.size === 0) continue;

	//  On ne lit que le bloc <style> : une classe peut légitimement apparaître
	//  ailleurs dans le balisage sans que cela dise quoi que ce soit du style.
	const i = source.indexOf('<style');
	const style = i === -1 ? '' : source.slice(i);

	for (const classe of relayees) {
		const echappee = classe.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
		//  Défini à plat : le sélecteur commence la règle, sans `:global(` avant.
		const plat = new RegExp(`(^|[\\s,>])\\.${echappee}(?![\\w-])[^{;]*\\{`, 'm');
		const enGlobal = new RegExp(`:global\\([^)]*\\.${echappee}(?![\\w-])`);
		if (!plat.test(style)) continue;
		if (enGlobal.test(style)) {
			conformes.push(`${rel} → .${classe}`);
			continue;
		}
		fautifs.push({ fichier: rel, classe });
	}
}

//  🔴 Le relevé légitime est VIDE. Sans témoin, ce contrôle ne peut pas distinguer
//  « aucun défaut » de « le motif ne trouve plus rien » — le faux vert que
//  `standards/04` §27 décrit. On affiche donc ce qu'on a EXAMINÉ.
const relayeesTotal = fichiers(SOURCE)
	.filter((c) => !PORTEURS.has(relative(SOURCE, c).split(sep).join('/')))
	.reduce((n, c) => n + classesRelayees(sansCommentaires(readFileSync(c, 'utf8'))).size, 0);

if (relayeesTotal === 0) {
	console.error(
		'✗ Aucune prop `classe="…"` trouvée dans tout `src/` — le motif de ce contrôle\n' +
			'  ne correspond plus à rien. INCONNU, pas OK : corriger le motif.',
	);
	process.exit(1);
}

if (fautifs.length > 0) {
	console.error(
		'✗ Classe relayée à un composant et stylée À PLAT — la règle ne peut pas\n' +
			"  l'atteindre : le `<div>` qui la porte appartient au composant, et prend SON\n" +
			'  scope. La mise en page est morte, sans que rien ne lève.\n',
	);
	for (const f of fautifs) {
		console.error(`  ${f.fichier}`);
		console.error(`    .${f.classe} — envelopper, puis borner :`);
		console.error(`      .mon-enveloppe :global(.${f.classe}) { … }\n`);
	}
	process.exit(1);
}

console.log(
	`✓ ${relayeesTotal} classe(s) relayée(s) examinée(s)` +
		(conformes.length ? ` — ${conformes.length} stylée(s) en \`:global()\` borné` : '') +
		', aucune définie à plat.',
);
