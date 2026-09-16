/**
 * Les listes rendues par `{#each … (clé)}` n'ont JAMAIS deux fois la même clé.
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
 * Le MÊME JOUR, le même défaut a frappé une seconde fois, ailleurs : la colonne
 * « Rôles actifs » de l'écran Utilisateurs rend `{#each … (d.label)}`, et
 * `bailleur` est l'alias hérité de `copropriétaire_bailleur` — **deux rôles, un
 * seul libellé**. Un compte portant les deux figeait l'écran entier. C'est
 * pourquoi ce fichier ne garde pas « l'ordre des pages » mais la NOTION :
 * chaque fonction qui alimente une liste à clé doit garantir l'unicité.
 *
 * ⚠️ Toute nouvelle fonction de ce genre s'ajoute ici. Deux contrôles pour une
 * seule règle divergeraient au premier cas limite — c'est précisément ce qui a
 * causé le premier incident (`Nav` et `pages.ts` avaient chacun leur version).
 *
 * Ces contrôles **exécutent** les fonctions plutôt que de relire leur code :
 * c'est le comportement qui compte, et une relecture aurait laissé passer
 * n'importe quelle réécriture qui perd le dédoublonnage. Le bundle esbuild sert
 * seulement à résoudre les alias `$lib` que Node ne connaît pas.
 */
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

import { build } from 'esbuild';

const SOURCE_PAGES = 'src/lib/pages.ts';
const SOURCE_ROLES = 'src/lib/roles.ts';
const SOURCE_FLUX = 'src/lib/flux.ts';

async function charger(source, nom) {
	const dossier = await mkdtemp(join(tmpdir(), 'cles-listes-'));
	const sortie = join(dossier, `${nom}.mjs`);
	await build({
		entryPoints: [source],
		bundle: true,
		format: 'esm',
		outfile: sortie,
		logLevel: 'error',
	});
	const module = await import(pathToFileURL(sortie).href);
	return { module, nettoyer: () => rm(dossier, { recursive: true, force: true }) };
}

/** Les clés rendues deux fois — ce qu'un `{#each … (clé)}` ne pardonne pas. */
function doublons(cles) {
	const vus = new Set();
	return [...new Set(cles.filter((c) => (vus.has(c) ? true : (vus.add(c), false))))];
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

const { module, nettoyer } = await charger(SOURCE_PAGES, 'pages');
try {
	const { ordonnerPages, identifiantsRepetes } = module;
	if (typeof ordonnerPages !== 'function' || typeof identifiantsRepetes !== 'function') {
		console.error(`✗ ${SOURCE_PAGES} n'exporte plus ordonnerPages / identifiantsRepetes.`);
		process.exit(1);
	}

	for (const cas of CAS) {
		const ids = ordonnerPages(PAGES, cas.ordre).map((p) => p.id);
		const repetees = doublons(ids);
		if (repetees.length) {
			echecs.push(
				`pages : « ${cas.nom} » rend ${repetees.length} page(s) en double (${repetees.join(', ')}) ` +
					`— un {#each … (pg.id)} lèverait each_key_duplicate et figerait l'écran`,
			);
		} else if (ids.join(',') !== cas.attendu) {
			echecs.push(`pages : « ${cas.nom} » rend « ${ids.join(',')} », attendu « ${cas.attendu} »`);
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

// ── Les badges de rôles : deux rôles peuvent rendre UN SEUL libellé ──────────
const CAS_ROLES = [
	{ nom: 'rôles distincts', roles: ['admin', 'résident'] },
	//  Le cas RÉEL qui a figé l'écran Utilisateurs : alias hérité + rôle courant.
	{ nom: 'alias hérité et rôle courant', roles: ['bailleur', 'copropriétaire_bailleur'] },
	{ nom: 'même rôle deux fois', roles: ['résident', 'résident'] },
	{ nom: 'rôle inconnu répété', roles: ['zzz_inconnu', 'zzz_inconnu'] },
	{ nom: 'liste vide', roles: [] },
];

const roles = await charger(SOURCE_ROLES, 'roles');
try {
	const { badgesDeRoles, libelleRole } = roles.module;
	if (typeof badgesDeRoles !== 'function') {
		console.error(`✗ ${SOURCE_ROLES} n'exporte plus badgesDeRoles.`);
		process.exit(1);
	}

	//  Le cas zéro : si plus aucun couple de rôles ne partageait un libellé, les
	//  assertions ci-dessous porteraient sur des listes déjà distinctes et ne
	//  refuseraient plus rien (standards/04 §2).
	if (libelleRole('bailleur') !== libelleRole('copropriétaire_bailleur')) {
		echecs.push(
			'rôles : « bailleur » et « copropriétaire_bailleur » ne rendent plus le même libellé — ' +
				'ce contrôle exerçait ce couple précis ; en trouver un autre, ou le retirer en le disant',
		);
	}

	for (const cas of CAS_ROLES) {
		const repetes = doublons(badgesDeRoles(cas.roles).map((b) => b.label));
		if (repetes.length) {
			echecs.push(
				`rôles : « ${cas.nom} » rend ${repetes.length} badge(s) au même libellé (${repetes.join(', ')}) ` +
					"— un {#each … (d.label)} lèverait each_key_duplicate et figerait l'écran Utilisateurs",
			);
		}
	}
} finally {
	await roles.nettoyer();
}

// ── Le fil : plusieurs tables, donc des `id` qui se répètent ────────────────
//  `publication` #12 et `ticket_mis_a_jour` #12 coexistent, et
//  `sondage_ouvert` / `sondage_clos` d'un même sondage portent le même id : une
//  clé `(item.id)` s'y répète forcément.
const CAS_FLUX = [
	{
		nom: 'types différents, même id',
		items: [
			{ type: 'publication', id: 12 },
			{ type: 'ticket_mis_a_jour', id: 12 },
		],
	},
	{
		nom: 'même sondage, ouvert puis clos',
		items: [
			{ type: 'sondage_ouvert', id: 4 },
			{ type: 'sondage_clos', id: 4 },
		],
	},
	{
		nom: 'même type, ids distincts',
		items: [
			{ type: 'annonce', id: 1 },
			{ type: 'annonce', id: 2 },
		],
	},
];

const flux = await charger(SOURCE_FLUX, 'flux');
try {
	const { cleFluxItem } = flux.module;
	if (typeof cleFluxItem !== 'function') {
		console.error(`✗ ${SOURCE_FLUX} n'exporte plus cleFluxItem.`);
		process.exit(1);
	}
	for (const cas of CAS_FLUX) {
		const repetees = doublons(cas.items.map(cleFluxItem));
		if (repetees.length) {
			echecs.push(
				`fil : « ${cas.nom} » rend ${repetees.length} clé(s) répétée(s) (${repetees.join(', ')}) ` +
					"— un {#each … } du fil lèverait each_key_duplicate et figerait l'écran",
			);
		}
	}
} finally {
	await flux.nettoyer();
}

// ── La porte : aucun écran ne doit reprendre `(item.id)` sur une liste du fil ─
const FICHIERS_DU_FIL = [
	'src/routes/(app)/tableau-de-bord/+page.svelte',
	'src/lib/components/ArchivesDuFil.svelte',
];

/**
 * Les listes de ces fichiers qui ne portent PAS des éléments du fil.
 *
 * ⚠️ Une exception non écrite n'est pas une exception, c'est un oubli qui
 * ressemble à une décision : chacune porte donc sa raison, et le contrôle
 * échoue si l'une d'elles cesse de servir.
 */
const PAS_DU_FIL = {
	dashKanbanCols: 'colonnes constantes (DASH_KANBAN_COLS) — ids fixes et distincts',
	'col.items': 'événements du calendrier — une seule table, donc des id uniques',
	'mobileKanbanCurrent.items': 'idem, la même liste au format mobile',
};
for (const fichier of FICHIERS_DU_FIL) {
	const src = await readFile(fichier, 'utf-8');
	const vues = new Set();
	for (const m of src.matchAll(/\{#each\s+([^}]*?)\s+as\s+(\w+)\s*\(\s*\2\.id\s*\)\s*\}/g)) {
		const collection = m[1].trim();
		if (collection in PAS_DU_FIL) {
			vues.add(collection);
			continue;
		}
		echecs.push(
			`fil : ${fichier} rend « ${m[1].trim()} » par (${m[2]}.id) — le fil agrège ` +
				"plusieurs tables, donc les id s'y répètent. Passer par cleFluxItem().",
		);
	}
	//  Le cas zéro des exceptions : une dérogation qui ne sert plus se retire.
	for (const [collection, raison] of Object.entries(PAS_DU_FIL)) {
		if (!vues.has(collection) && fichier.includes('tableau-de-bord')) {
			echecs.push(
				`fil : l'exception « ${collection} » (${raison}) ne correspond plus à rien dans ` +
					`${fichier} — la retirer de PAS_DU_FIL.`,
			);
		}
	}
}

if (echecs.length) {
	console.error(`\n✗ ${echecs.length} clé(s) de liste non garantie(s) :\n`);
	for (const e of echecs) console.error(`  ${e}`);
	console.error(
		'\n  Une clé de {#each} doit être unique PAR CONSTRUCTION, jamais par confiance :\n' +
			'  ces listes viennent de la base ou de saisies libres, et le rendu ne doit\n' +
			'  jamais mourir de leur incohérence.\n',
	);
	process.exit(1);
}

console.log(
	`✓ Clés de listes : ${CAS.length + CAS_ROLES.length + CAS_FLUX.length} cas exercés (ordre des pages, badges de rôles, fil), aucune clé répétée.`,
);
