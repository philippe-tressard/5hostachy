#!/usr/bin/env node
/**
 * Garde-fou — **aucun sélecteur CSS ne survit au balisage qu'il stylait.**
 *
 * ## Pourquoi (#557, 20/08/2026)
 *
 * `svelte-check` sait déjà le dire : `Unused CSS selector`. Il le disait pour
 * **33 sélecteurs dans 9 fichiers**, à chaque exécution, depuis des semaines —
 * noyés parmi **95 avertissements**. Le job de CI ne regarde que les *erreurs*,
 * et à raison : rendre les avertissements bloquants d'un coup rendrait le job
 * rouge en permanence, donc désarmé dans la semaine.
 *
 * 🔴 Mais **un avertissement permanent ne se lit plus** (`standards/04` §18).
 * C'est le même mécanisme que les huit `SKIPPED` de #542 : ce qui se confond
 * avec le vert cesse d'être lu.
 *
 * Ce contrôle prend **une** famille d'avertissements, celle qui est maintenant à
 * zéro, et la rend bloquante. Les autres restent des avertissements tant qu'on
 * ne les a pas ramenées à zéro — c'est la seule façon d'en faire des contrôles
 * plutôt que du bruit.
 *
 * ## C'est #550 par l'autre bout
 *
 * #550 a retiré 74 symboles morts — imports et déclarations laissés par des
 * extractions. Ceci en est le pendant **côté styles** : le balisage part, la
 * règle reste. Les deux garde-fous prennent chacun un sens de la relation :
 *
 * | Contrôle | Question |
 * |---|---|
 * | `lint:classes-nues` | une classe **employée** est-elle **définie** ? |
 * | celui-ci | un sélecteur **défini** est-il **employé** ? |
 *
 * ⚠️ Une relation a deux sens de rupture, et un contrôle qui n'en garde qu'un
 * laisse passer l'autre (`standards/05` §9 bis).
 *
 * ## Ce que le relevé a trouvé au passage, et qui ne relevait PAS du nettoyage
 *
 * `.muted-sm` était définie dans **un seul** fichier et employée par **quatre
 * autres** — qui la rendaient donc **nue**. Elle n'a pas été supprimée : elle a
 * été **remontée** dans `app.css`. C'est la régression des pastilles de la
 * v2.67.11, trouvée par l'autre bout — par le sélecteur orphelin resté dans le
 * fichier d'origine, et non par l'écran nu.
 *
 * 🔴 Et `lint:classes-nues` ne pouvait pas la voir : il demande « cette classe
 * est-elle définie quelque part ? » — elle l'était. La question qu'il ne pose
 * pas est « une définition **s'applique-t-elle** à ce balisage ? ». Angle mort
 * relevé en #562.
 *
 * Usage : `npm run lint:css-orphelin`
 *   exit 0 = aucun sélecteur orphelin hors exception
 *   exit 1 = sélecteur orphelin, ou exception devenue inutile
 *   exit 2 = INCONNU (svelte-check n'a pas pu être mesuré)
 */
import { spawnSync } from 'node:child_process';

/**
 * Sélecteurs orphelins TOLÉRÉS, avec leur raison.
 *
 * ⚠️ Une entrée qui ne sert plus FAIT ÉCHOUER le contrôle : une dérogation
 * oubliée est une porte qu'on croit fermée. La liste ne peut que décroître.
 *
 * Elle est vide, et c'est le but : le relevé a été ramené à zéro avant que ce
 * contrôle ne devienne bloquant. Un garde-fou posé sur une dette non soldée est
 * un job rouge en permanence, donc un job désarmé.
 */
const TOLERANCES = {};

function inconnu(raison, detail) {
	console.error(`\n⚠️  INCONNU — ${raison}`);
	if (detail) console.error(`   ${String(detail).trim().split('\n').slice(0, 5).join('\n   ')}`);
	console.error(
		"   Le relevé n'a PAS été mesuré : ce n'est ni un succès ni un échec. Relancer le job.\n"
	);
	process.exit(2);
}

//  ⚠️ `svelte-check` sort en 1 dès qu'il trouve une ERREUR, et en 0 avec des
//  avertissements. Son code de sortie ne dit donc rien sur ce qui nous intéresse :
//  c'est sa SORTIE qui fait foi, et son illisibilité qui vaut INCONNU.
const res = spawnSync('npx svelte-check --output human', {
	encoding: 'utf8',
	shell: true,
	maxBuffer: 32 * 1024 * 1024,
});

if (res.error) inconnu('`svelte-check` n\'a pas pu être lancé', res.error.message);

//  ⚠️ Les codes de couleur ANSI se retirent par une expression construite À
//  L'EXÉCUTION. Écrire le caractère d'échappement en clair dans un littéral
//  régulier y met un CARACTÈRE DE CONTRÔLE INVISIBLE — c'est exactement le
//  défaut trouvé le matin même dans `check-workflow-envoye.mjs` (un U+0008
//  au milieu d'un motif, qui le rendait inerte). ESLint le refuse, à raison.
const ANSI = new RegExp(String.fromCharCode(27) + '\\[[0-9;]*m', 'g');
const sortie = `${res.stdout || ''}${res.stderr || ''}`.replace(ANSI, '');

//  🔴 CAS ZÉRO — une sortie qui ne ressemble pas à un rapport `svelte-check`
//  rendrait « aucun orphelin » sans avoir rien lu.
if (!/svelte-check found/.test(sortie)) {
	inconnu('sortie de `svelte-check` non reconnue', sortie.slice(-400));
}

const lignes = sortie.split('\n');
const orphelins = [];
for (let i = 0; i < lignes.length; i++) {
	if (!lignes[i].includes('Unused CSS selector')) continue;
	//  L'emplacement est sur la ligne non vide qui précède.
	let j = i - 1;
	while (j >= 0 && !lignes[j].trim()) j--;
	const emplacement = /front[\\/](src[^\s:]+):(\d+)/.exec(lignes[j] ?? '');
	const selecteur = /"([^"]+)"/.exec(lignes[i]);
	orphelins.push({
		fichier: emplacement ? emplacement[1].replace(/\\/g, '/') : '?',
		ligne: emplacement ? emplacement[2] : '?',
		selecteur: selecteur ? selecteur[1] : lignes[i].trim(),
	});
}

const fautifs = orphelins.filter((o) => !(o.selecteur in TOLERANCES));
const inutiles = Object.keys(TOLERANCES).filter(
	(s) => !orphelins.some((o) => o.selecteur === s)
);

if (fautifs.length || inutiles.length) {
	console.error(`\n✗ ${fautifs.length} sélecteur(s) CSS orphelin(s)\n`);
	for (const o of fautifs) console.error(`   ${o.fichier}:${o.ligne}  ${o.selecteur}`);
	for (const s of inutiles) {
		console.error(`   ✗ tolérance « ${s} » devenue inutile : la retirer de TOLERANCES`);
	}
	console.error(
		"\n  Un sélecteur qui ne style plus rien est le RESTE d'un balisage parti.\n" +
			"  ⚠️ Avant de le supprimer, vérifier qu'il n'est pas employé par un AUTRE\n" +
			'  fichier : Svelte scope au fichier, et une règle « orpheline » ici peut être\n' +
			"  la SEULE définition d'une classe qu'un autre écran rend alors NUE.\n" +
			"  Dans ce cas, elle se REMONTE dans `app.css` — elle ne se supprime pas.\n"
	);
	process.exit(1);
}

console.log(`✓ CSS : aucun sélecteur orphelin (${orphelins.length} toléré(s) et déclaré(s))`);
