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
import { avertissements, lignesDuRapport } from './lib-svelte-check.mjs';

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

//  ⚠️ Le TUYAU — lancer `svelte-check`, retirer les couleurs, reconnaître un
//  rapport valide, apparier chaque message à son emplacement — vivait ICI, et il
//  a été extrait dans `lib-svelte-check.mjs` quand un SECOND contrôle en a eu
//  besoin (`lint:libelles`, #561). Deux de ces quatre gestes ont déjà coûté un
//  défaut à ce dépôt : recopiés, ils divergent, et c'est du côté non testé qu'ils
//  sont faux. Le module porte leur `--selftest`.
const orphelins = avertissements(lignesDuRapport(), 'Unused CSS selector').map((a) => {
	const selecteur = /"([^"]+)"/.exec(a.message);
	return { fichier: a.fichier, ligne: a.ligne, selecteur: selecteur ? selecteur[1] : a.message };
});

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
