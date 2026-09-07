#!/usr/bin/env node
/**
 * Garde-fou : le filtre d'états d'une liste de tickets couvre CE QUI S'AFFICHE.
 *
 * ## Le défaut (01/09/2026, signalé à l'écran)
 *
 * > *« Le filtre de mes tickets ne comprend pas tous les états du workflow
 * > pouvant être affichés sur la page (notamment résolu ?) »*
 *
 * La liste des boutons était écrite à part — « les états actifs, puisque les
 * clos ont leur section Historique ». C'était faux d'une semaine : un ticket
 * clôturé reste **sept jours** dans la liste principale. Un ticket « Résolu »
 * hier s'affichait donc sans qu'aucun bouton puisse l'isoler.
 *
 * 🔴 Le défaut n'était pas la liste, c'était sa **source** : elle décrivait ce
 * qu'on croyait afficher, pas ce qui s'affiche. Aucune relecture ne l'aurait
 * trouvé — les deux listes étaient chacune correcte, et c'est leur écart qui ne
 * l'était pas.
 *
 * ## Ce qui est vérifié
 *
 * `statutsPresents` est une fonction PURE : elle est **transpilée et exécutée**
 * ici, comme `lint:perimetre-herite` le fait déjà. Trois propriétés, dont deux
 * se perdent facilement :
 *
 *   1. tout état présent dans la liste a son bouton — y compris un état CLOS ;
 *   2. l'ordre est celui du workflow, jamais celui d'apparition ;
 *   3. un état **historique** (`fermé`, retiré du workflow en 2026) apparaît
 *      quand même s'il est là — c'est celui qu'aucune liste écrite à la main
 *      n'aurait pensé à inclure.
 *
 * Usage : npm run lint:filtre-statuts
 */
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..');
const SOURCE = join(RACINE, 'src', 'lib', 'tickets.ts');

function echouer(message) {
	console.error(`\n✗ ${message}\n`);
	process.exit(1);
}

if (!existsSync(SOURCE)) echouer(`Cas zéro : ${SOURCE} est introuvable — contrôle inopérant.`);

const esbuild = await import('esbuild');
let module;
try {
	const { code } = await esbuild.transform(readFileSync(SOURCE, 'utf8'), {
		loader: 'ts',
		format: 'esm',
	});
	module = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
} catch (e) {
	echouer(`Cas zéro : lib/tickets.ts ne se transpile pas (${e.message}).`);
}

const { statutsPresents, STATUTS_TICKET } = module;
if (typeof statutsPresents !== 'function') {
	echouer(
		"Cas zéro : lib/tickets.ts n'exporte plus `statutsPresents` — la fonction a\n" +
			'  disparu ou changé de nom, et ce contrôle ne mesure plus rien.',
	);
}
if (!Array.isArray(STATUTS_TICKET) || STATUTS_TICKET.length < 3) {
	echouer(
		`Cas zéro : ${STATUTS_TICKET?.length ?? 0} état(s) dans STATUTS_TICKET — le workflow\n` +
			'  a changé de forme. Ne pas lire ceci comme un succès.',
	);
}

const t = (statut) => ({ statut });
const valeurs = (r) => r.map((o) => o.value);

const CAS = [
	{
		quoi: 'liste vide : aucun bouton, jamais une liste par défaut',
		tickets: [],
		attendu: [],
	},
	{
		quoi: 'un état CLOS présent a son bouton — c’est le défaut signalé',
		tickets: [t('ouvert'), t('résolu')],
		attendu: ['ouvert', 'résolu'],
	},
	{
		quoi: 'l’ordre est celui du workflow, pas celui d’apparition',
		tickets: [t('résolu'), t('ouvert'), t('en_cours')],
		attendu: ['ouvert', 'en_cours', 'résolu'],
	},
	{
		quoi: 'un doublon ne produit pas deux boutons',
		tickets: [t('ouvert'), t('ouvert'), t('ouvert')],
		attendu: ['ouvert'],
	},
	{
		quoi: 'un état HISTORIQUE (`fermé`) apparaît s’il est là',
		tickets: [t('ouvert'), t('fermé')],
		attendu: ['ouvert', 'fermé'],
	},
	{
		quoi: 'un état inconnu n’invente pas de bouton',
		tickets: [t('ouvert'), t('inventé')],
		attendu: ['ouvert'],
	},
];

const echecs = [];
for (const { quoi, tickets, attendu } of CAS) {
	const obtenu = valeurs(statutsPresents(tickets));
	if (JSON.stringify(obtenu) !== JSON.stringify(attendu)) {
		echecs.push(
			`   ${quoi}\n       attendu ${JSON.stringify(attendu)}, obtenu ${JSON.stringify(obtenu)}`,
		);
	}
}

//  Et la propriété qui les résume toutes : aucun état affichable ne doit rester
//  sans bouton. C'est la formulation exacte du défaut, éprouvée sur TOUS les
//  états du workflow d'un coup — un cas par état aurait pu en oublier un.
const tous = STATUTS_TICKET.map((s) => s.value);
const rendus = valeurs(statutsPresents(tous.map(t)));
const manquants = tous.filter((v) => !rendus.includes(v));
if (manquants.length) {
	echecs.push(
		`   des états s’affichent SANS bouton de filtre : ${JSON.stringify(manquants)}\n` +
			'       c’est exactement le défaut du 01/09/2026',
	);
}

//  Chaque option porte un libellé lisible : un bouton vide serait pire qu'absent.
for (const o of statutsPresents(tous.map(t))) {
	if (!o.label || !o.label.trim()) echecs.push(`   l’option « ${o.value} » n’a pas de libellé`);
}

if (echecs.length) {
	console.error('\n✗ `statutsPresents` ne couvre pas ce que la liste affiche :\n');
	console.error(echecs.join('\n'));
	console.error(
		'\n  Le filtre doit se déduire des tickets RÉELLEMENT rendus, jamais d’une' +
			'\n  liste écrite à côté : c’est l’écart entre les deux qui a laissé un' +
			'\n  ticket « Résolu » visible et impossible à isoler pendant sept jours.\n',
	);
	process.exit(1);
}

console.log(
	`✓ Filtre d’états : ${CAS.length} cas vérifiés, et les ${tous.length} états du workflow ` +
		'ont tous leur bouton dès qu’ils s’affichent.',
);
