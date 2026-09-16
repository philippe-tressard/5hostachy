/**
 * `ordonnerPages` ne rend JAMAIS deux fois la même page.
 *
 * POURQUOI CE CONTRÔLE (16/09/2026) :
 *
 * `pages_order` est une DONNÉE — elle vit en base et s'édite depuis « Descriptif
 * pages ». Quand elle a porté deux fois le même identifiant, `ordonnerPages` a
 * rendu deux fois la même page, et le `{#each … (pg.id)}` qui l'affiche a levé
 * `each_key_duplicate` : une erreur **fatale et non rattrapable** de Svelte.
 *
 * Ce que ça donnait à l'écran : l'onglet basculait, le contenu restait celui
 * d'avant, et plus aucune mise à jour ne passait — sur toutes les pages. Seule
 * la fermeture de la fenêtre en sortait. C'est arrivé deux fois en production et
 * a été pris pour un « figeage du site », alors que le serveur répondait en
 * moins de 200 ms et que Caddy ne voyait pas une seule requête lente.
 *
 * ⚠️ Le défaut se PROPAGEAIT : `movePage` réécrit `pages_order` à partir de la
 * liste rendue, donc le premier déplacement enregistrait le doublon en base.
 *
 * Ce contrôle **exécute** la fonction plutôt que de relire son code : c'est le
 * comportement qui compte, et une relecture aurait laissé passer n'importe
 * quelle réécriture qui perd le dédoublonnage. Le bundle esbuild sert seulement
 * à résoudre les alias `$lib` que Node ne connaît pas.
 */
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

import { build } from 'esbuild';

const SOURCE = 'src/lib/pages.ts';

async function charger() {
	const dossier = await mkdtemp(join(tmpdir(), 'ordre-pages-'));
	const sortie = join(dossier, 'pages.mjs');
	await build({
		entryPoints: [SOURCE],
		bundle: true,
		format: 'esm',
		outfile: sortie,
		logLevel: 'error',
	});
	const module = await import(pathToFileURL(sortie).href);
	return { module, nettoyer: () => rm(dossier, { recursive: true, force: true }) };
}

/** Un jeu de pages minimal : deux ordonnables, une qui ne l'est pas. */
const PAGES = [
	{ id: 'a', href: '/a' },
	{ id: 'b', href: '/b' },
	{ id: 'sans-route', href: null },
];

const CAS = [
	{ nom: 'ordre sain', ordre: ['b', 'a'], attendu: 'b,a,sans-route' },
	{ nom: 'identifiant répété', ordre: ['b', 'b', 'a'], attendu: 'b,a,sans-route' },
	{ nom: 'répété trois fois', ordre: ['a', 'a', 'a'], attendu: 'a,b,sans-route' },
	{ nom: 'identifiant inconnu', ordre: ['b', 'fantome', 'a'], attendu: 'b,a,sans-route' },
	{ nom: 'page sans route citée', ordre: ['sans-route', 'a'], attendu: 'a,b,sans-route' },
	{ nom: 'ordre vide', ordre: [], attendu: 'a,b,sans-route' },
];

const echecs = [];

const { module, nettoyer } = await charger();
try {
	const { ordonnerPages, identifiantsRepetes } = module;
	if (typeof ordonnerPages !== 'function' || typeof identifiantsRepetes !== 'function') {
		console.error(`✗ ${SOURCE} n'exporte plus ordonnerPages / identifiantsRepetes.`);
		process.exit(1);
	}

	for (const cas of CAS) {
		const rendu = ordonnerPages(PAGES, cas.ordre);
		const ids = rendu.map((p) => p.id);
		const vus = new Set();
		const doublons = ids.filter((id) => (vus.has(id) ? true : (vus.add(id), false)));
		if (doublons.length) {
			echecs.push(
				`« ${cas.nom} » rend ${doublons.length} page(s) en double (${[...new Set(doublons)].join(', ')}) ` +
					`— un {#each … (pg.id)} lèverait each_key_duplicate et figerait l'écran`,
			);
		} else if (ids.join(',') !== cas.attendu) {
			echecs.push(`« ${cas.nom} » rend « ${ids.join(',')} », attendu « ${cas.attendu} »`);
		}
	}

	//  Le cas zéro : sans lui, les assertions ci-dessus pourraient toutes porter
	//  sur des listes déjà saines et ne rien refuser (standards/04 §2).
	const repetes = identifiantsRepetes(['b', 'b', 'a', 'a', 'c']);
	if (repetes.sort().join(',') !== 'a,b') {
		echecs.push(
			`identifiantsRepetes(['b','b','a','a','c']) rend « ${repetes.join(', ')} », attendu « a, b » — ` +
				"le signalement d'une donnée incohérente ne fonctionne plus",
		);
	}
	if (identifiantsRepetes(['a', 'b']).length !== 0) {
		echecs.push('identifiantsRepetes signale une répétition sur un ordre sain');
	}
} finally {
	await nettoyer();
}

if (echecs.length) {
	console.error(`\n✗ ${echecs.length} défaut(s) dans l'ordre des pages :\n`);
	for (const e of echecs) console.error(`  ${e}`);
	console.error(
		"\n  `pages_order` est une donnée en base, éditable depuis l'écran d'administration :\n" +
			'  elle peut être incohérente, et le rendu ne doit jamais en mourir.\n',
	);
	process.exit(1);
}

console.log(`✓ Ordre des pages : ${CAS.length} cas exercés, aucune page rendue deux fois.`);
