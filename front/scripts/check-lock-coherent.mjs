/**
 * Garde-fou — **le lock ne ment pas sur les versions qu'il verrouille.**
 *
 * ## Pourquoi (15/09/2026)
 *
 * `package-lock.json` annonçait `prosemirror-transform@1.28.0` et
 * `@types/resolve@1.28.0`. **Aucune de ces deux versions n'a jamais été
 * publiée** : le registre s'arrête à 1.12.1 et 1.20.6.
 *
 * L'historique est sans ambiguïté — `prosemirror-transform` suivait le numéro de
 * version de l'APPLICATION depuis la v1.16.2 : 1.16.2, 1.17.0, 1.18.0… 1.28.0.
 * Quinze bumps, quinze réécritures. La cause est le bump de version fait « à la
 * main » dans le lock par un remplacement de chaîne : deux dépendances portaient
 * par hasard le même numéro que l'application, et le remplacement les a
 * emportées à chaque fois.
 *
 * ## Ce que ça coûtait réellement — et ce que ça ne coûtait pas
 *
 * ✅ **La production n'a jamais été cassée.** `npm ci` télécharge l'archive
 * nommée par `resolved` et en vérifie l'empreinte ; ces deux champs, eux,
 * désignaient les VRAIES versions (1.12.0, 1.20.2). Le code installé était
 * correct.
 *
 * 🔴 **En revanche `npm audit` lit le champ `version`.** Un avis visant
 * `prosemirror-transform` ≤ 1.12.x était donc évalué contre « 1.28.0 » — hors de
 * toute plage vulnérable, pour une version qui n'existe pas. Le contrôle rendait
 * « 0 vulnérabilité » **sans avoir examiné ces paquets**. C'est un faux vert, la
 * famille exacte de `standards/04` §2.
 *
 * ⚠️ Et le témoin existait. La consigne de bump prescrivait de vérifier que
 * `git diff --stat` annonce `| 4 ++--`, en disant mot pour mot que « six lignes,
 * c'est déjà une dépendance emportée ». Il en affichait six, à chaque bump,
 * depuis quinze versions. **Un témoin qu'aucune machine ne lit ne protège que
 * les fois où l'on y pense.**
 *
 * ## Ce que ce contrôle vérifie
 *
 *   1. la version de tête du lock et celle de son paquet racine valent celle de
 *      `package.json` — c'est ce que le bump est censé changer, et rien d'autre ;
 *   2. pour chaque entrée, la version déclarée est celle que nomme l'archive
 *      `resolved`. C'est la seule comparaison possible sans réseau : le lock
 *      porte les deux faits, et ils doivent coïncider.
 */
import { readFileSync } from 'node:fs';

const LOCK = 'package-lock.json';
const MANIFESTE = 'package.json';

//: `…/prosemirror-transform/-/prosemirror-transform-1.12.0.tgz` → `1.12.0`.
//: Le nom est répété avant la version dans le chemin de l'archive ; on ancre sur
//: `/-/` puis on prend ce qui suit le dernier tiret précédant `.tgz`.
const ARCHIVE = /\/-\/(.+)-(\d[^/]*)\.tgz$/;

/** Les entrées dont la version déclarée contredit son archive. */
export function incoherences(lock) {
	const fautes = [];
	for (const [chemin, entree] of Object.entries(lock.packages ?? {})) {
		if (!entree?.resolved || !entree?.version) continue;
		const m = ARCHIVE.exec(entree.resolved);
		//  Une archive hors registre (git, lien, fichier) ne porte pas de version
		//  dans son chemin : il n'y a rien à comparer, et inventer une comparaison
		//  reviendrait à signaler ce qu'on ne sait pas lire.
		if (!m) continue;
		if (m[2] !== entree.version) {
			fautes.push(`${chemin} — déclare ${entree.version}, archive ${m[2]}`);
		}
	}
	return fautes;
}

/** La version que le lock annonce pour le projet lui-même, aux deux endroits. */
export function versionsDuProjet(lock) {
	return [lock.version, lock.packages?.['']?.version];
}

function selftest() {
	const sain = {
		version: '1.2.3',
		packages: {
			'': { version: '1.2.3' },
			'node_modules/a': { version: '1.12.0', resolved: 'https://r/a/-/a-1.12.0.tgz' },
			'node_modules/@types/b': { version: '1.20.2', resolved: 'https://r/@types/b/-/b-1.20.2.tgz' },
			//  Une dépendance servie autrement : rien à comparer, rien à signaler.
			'node_modules/c': { version: '0.1.0', resolved: 'git+ssh://git@h/c.git#abc' },
			//  Une entrée sans archive du tout (paquet lié, workspace).
			'node_modules/d': { version: '2.0.0' },
		},
	};
	//  🔴 Le défaut réel, dans sa forme exacte : la version suit le numéro de
	//  l'application, l'archive reste la vraie.
	const malade = JSON.parse(JSON.stringify(sain));
	malade.packages['node_modules/a'].version = '1.28.0';
	malade.packages['node_modules/@types/b'].version = '1.28.0';

	const cas = [
		['lock sain', incoherences(sain).length, 0],
		['lock corrompu par un bump', incoherences(malade).length, 2],
	];
	let ko = 0;
	for (const [quoi, obtenu, attendu] of cas) {
		if (obtenu !== attendu) {
			console.error(`  ✗ ${quoi} : ${obtenu} au lieu de ${attendu}`);
			ko++;
		}
	}
	if (ko) {
		console.error(`\n✗ Auto-test : ${ko} cas en échec.`);
		process.exit(1);
	}
	console.log('✓ Auto-test : la version qui ment est vue, celle qui dit vrai ne l’est pas.');
}

selftest();
if (process.argv.includes('--selftest')) process.exit(0);

const lock = JSON.parse(readFileSync(LOCK, 'utf8'));
const attendue = JSON.parse(readFileSync(MANIFESTE, 'utf8')).version;

//  🔴 Cas zéro : un lock vide, ou dont la forme aurait changé, rendrait « aucune
//  incohérence » sans avoir rien comparé.
const comparables = Object.values(lock.packages ?? {}).filter((e) =>
	ARCHIVE.test(e?.resolved ?? ''),
);
if (comparables.length < 50) {
	console.error(
		`\n⚠️  INCONNU — ${comparables.length} entrée(s) comparable(s) dans ${LOCK}.\n` +
			"   Le lecteur ne reconnaît plus la forme du lock : ce n'est pas un vert.\n",
	);
	process.exit(2);
}

const fautes = incoherences(lock);
const [tete, racine] = versionsDuProjet(lock);
if (tete !== attendue || racine !== attendue) {
	fautes.unshift(
		`le projet lui-même — package.json dit ${attendue}, le lock dit ${tete} (tête) / ${racine} (racine)`,
	);
}

if (fautes.length) {
	console.error(`\n✗ ${fautes.length} incohérence(s) dans ${LOCK} :\n`);
	for (const f of fautes) console.error(`  ${f}`);
	console.error(
		'\n  Une version qui ment n’empêche pas `npm ci` d’installer le bon code —\n' +
			'  il suit `resolved` et son empreinte. Mais `npm audit` lit `version` :\n' +
			'  il évalue alors les avis contre une version inexistante et ne trouve\n' +
			'  rien, sans jamais dire qu’il n’a rien examiné.\n' +
			'  → laisser npm écrire le lock (`npm install`), puis lui rendre son\n' +
			'    indentation d’origine (JSON à deux espaces) pour garder un diff lisible.\n',
	);
	process.exit(1);
}
console.log(
	`✓ Lock cohérent — ${comparables.length} archive(s) vérifiée(s), projet en ${attendue}.`,
);
