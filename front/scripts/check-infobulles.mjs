#!/usr/bin/env node
/*
 *  **L'infobulle d'un bouton icône est celle du NAVIGATEUR, et son nom vient de `aria-label`.**
 *
 *  Deux règles, et elles ne disent pas la même chose :
 *
 *  1. **Aucun `data-info` sur un bouton `btn-icon*`.** Cet attribut alimentait
 *     l'infobulle CSS du projet, **supprimée le 07/09/2026**. Un `data-info`
 *     résiduel est donc un libellé que plus rien n'affiche — pire qu'absent,
 *     puisqu'il a l'air d'un libellé.
 *  2. **Un `aria-label` obligatoire.** L'infobulle native n'apparaît **ni au
 *     clavier ni au tactile**, et aucun lecteur d'écran ne l'annonce de façon
 *     fiable. Sans `aria-label`, le bouton est **muet** — il n'énonce que son
 *     emoji.
 *
 *  ## Pourquoi ce contrôle dit l'INVERSE de ce qu'il disait le matin même
 *
 *  Le projet avait sa propre infobulle, en CSS. Signalée à l'écran le
 *  07/09/2026 : *« le curseur cache le libellé, qui apparaît en bas de
 *  l'icône »* — elle s'ouvrait sous le bouton, exactement là où arrive la
 *  flèche du pointeur.
 *
 *  Le premier correctif l'a ancrée au-dessus, et a migré **88 boutons** de
 *  `title` vers `data-info` pour supprimer la bulle NATIVE que `title`
 *  déclenchait par-dessus. Puis, les deux vues côte à côte : *« la bulle sombre
 *  est inutile, la claire est plus pertinente »*.
 *
 *  🔴 La bulle maison a donc été **supprimée**, et `title` rétabli. La native se
 *  place seule, ne déborde jamais de la fenêtre et ne s'efface pas tant que la
 *  souris ne bouge plus — trois choses qu'une bulle CSS ne fait bien qu'avec du
 *  JavaScript. **L'écran a tranché ce que le raisonnement laissait ouvert**, et
 *  c'est la bonne façon de trancher une question d'ergonomie.
 *
 *  ⚠️ Ce qui SURVIT au renversement : les `aria-label` ajoutés en chemin. Le
 *  relevé avait montré que **31 boutons icône n'avaient QUE `title`**, donc
 *  aucun nom accessible, alors que `ux-patterns` §3 l'exige depuis toujours.
 *  Rien ne le disait : `lint:a11y` s'appuie sur `svelte-check`, qui ne signale
 *  pas un bouton dont le contenu est un emoji. C'est le trou que la seconde
 *  règle ferme, et il ne dépendait d'aucun choix d'infobulle.
 *
 *  ⚠️ `aria-label` compte sous ses DEUX formes — `aria-label="Texte"` et
 *  `aria-label={expression}`. Mon premier relevé ne connaissait que la première
 *  et a compté cinq boutons « sans libellé » qui en avaient un ; c'est la même
 *  erreur que le motif qui exigeait `.<nom>(` dans #801.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

const RACINE = 'src';

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (e.endsWith('.svelte')) acc.push(p);
	}
	return acc;
}

/**
 *  Les balises `<button …>` d'une source, avec leur ligne.
 *
 *  ⚠️ Le découpage suit les accolades et les quotes : un attribut Svelte peut
 *  contenir `>` dans une expression (`{a > b ? 'x' : 'y'}`), et s'arrêter au
 *  premier `>` couperait la balise au mauvais endroit.
 */
export function boutons(source) {
	const trouves = [];
	for (const m of source.matchAll(/<button\b/g)) {
		let i = m.index + 7,
			prof = 0,
			dans = null;
		while (i < source.length) {
			const c = source[i];
			if (dans) {
				if (c === dans) dans = null;
			} else if (c === '"' || c === "'") dans = c;
			else if (c === '{') prof++;
			else if (c === '}') prof--;
			else if (c === '>' && prof === 0) break;
			i++;
		}
		trouves.push({
			balise: source.slice(m.index, i),
			ligne: source.slice(0, m.index).split('\n').length,
		});
	}
	return trouves;
}

const estIcone = (b) => /class="[^"]*btn-icon/.test(b);
//  Résidu de l'infobulle maison supprimée : un libellé que plus rien n'affiche.
const aDataInfo = (b) => /\sdata-info\s*=/.test(b);
//  Les deux formes, littérale et dynamique.
const aAriaLabel = (b) => /\saria-label\s*=/.test(b);

//  ── Cas zéro ────────────────────────────────────────────────────────────────
function selftest() {
	const cas = [
		//  [source, doit être signalé pour data-info, doit être signalé pour aria]
		//  Le cas nominal depuis le 07/09 : `title` pour la bulle, `aria-label` pour le nom.
		['<button class="btn-icon" title="X" aria-label="X">a</button>', false, false],
		//  🔴 Le défaut que la 2ᵉ règle ferme : un bouton icône sans nom accessible.
		['<button class="btn-icon" title="X">a</button>', false, true],
		//  Résidu de la bulle maison supprimée.
		['<button class="btn-icon" data-info="X" aria-label="X">a</button>', true, false],
		//  🔴 Le cas qui a fait échouer mon premier relevé : l'aria-label dynamique.
		['<button class="btn-icon" title="X" aria-label={libelle}>a</button>', false, false],
		//  Un bouton ORDINAIRE n'est pas visé : il porte son libellé en toutes lettres.
		['<button class="btn btn-primary" title="X">Enregistrer</button>', false, false],
		//  Une expression contenant `>` ne doit pas couper la balise trop tôt.
		['<button class="btn-icon" title={a > b ? "x" : "y"} aria-label="X">a</button>', false, false],
	];
	let ko = 0;
	for (const [src, attData, attAria] of cas) {
		const b = boutons(src)[0].balise;
		const icone = estIcone(b);
		if ((icone && aDataInfo(b)) !== attData) {
			console.error(`  ✗ verdict « data-info » inattendu : ${src}`);
			ko++;
		}
		if ((icone && !aAriaLabel(b)) !== attAria) {
			console.error(`  ✗ verdict « aria-label » inattendu : ${src}`);
			ko++;
		}
	}
	if (ko) {
		console.error(`\n✗ Auto-test : ${ko} cas en échec.`);
		process.exit(1);
	}
	console.log('✓ Auto-test : les deux règles refusent et acceptent ce qu’il faut.');
}

selftest();

const avecDataInfo = [];
const sansNom = [];
let icones = 0;

for (const p of fichiers(RACINE)) {
	const chemin = p.split('\\').join('/');
	for (const { balise, ligne } of boutons(readFileSync(p, 'utf8'))) {
		if (!estIcone(balise)) continue;
		icones++;
		if (aDataInfo(balise)) avecDataInfo.push(`${chemin}:${ligne}`);
		if (!aAriaLabel(balise)) sansNom.push(`${chemin}:${ligne}`);
	}
}

let echec = false;

if (avecDataInfo.length) {
	echec = true;
	console.error(`\n✗ ${avecDataInfo.length} bouton(s) icône portant un \`data-info\` :\n`);
	for (const e of avecDataInfo) console.error(`  ${e}`);
	console.error(
		"\n  `data-info` alimentait l'infobulle CSS du projet, SUPPRIMÉE le 07/09/2026\n" +
			'  au profit de la bulle native du navigateur (arbitrage à l’écran :\n' +
			'  « la bulle sombre est inutile, la claire est plus pertinente »).\n' +
			'  Un `data-info` restant est donc un libellé que plus rien n’affiche.\n' +
			'  → le renommer en `title`, que le navigateur lit.\n',
	);
}

if (sansNom.length) {
	echec = true;
	console.error(`\n✗ ${sansNom.length} bouton(s) icône sans \`aria-label\` :\n`);
	for (const e of sansNom) console.error(`  ${e}`);
	console.error(
		"\n  L'infobulle native n'apparaît ni au clavier ni au tactile, et aucun\n" +
			"  lecteur d'écran ne l'annonce de façon fiable. Sans `aria-label`, le\n" +
			'  bouton n’annonce que son emoji — « point d’exclamation », « corbeille ».\n' +
			'  → ajouter `aria-label`, plus précis que l’infobulle si possible\n' +
			'    (« Supprimer l’annonce » plutôt que « Supprimer »).\n',
	);
}

if (echec) process.exit(1);

console.log(
	`✓ ${icones} boutons icône — tous nommés par \`aria-label\`, aucun \`data-info\` résiduel.`,
);
