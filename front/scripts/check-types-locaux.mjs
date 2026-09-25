#!/usr/bin/env node
/**
 *  Un type d'ENTITÉ se déclare là où le client le rend, jamais dans un écran (#1044).
 *
 *  ## Pourquoi ce contrôle
 *
 *  L'audit du 19/09/2026 a trouvé la seconde source de types du front : les
 *  écrans. Le client rendait `any`, et chaque écran retypait l'entité de son
 *  côté — `Bail` dans `mon-lot`, l'accès d'un bail dans `ModaleAccesBail`,
 *  les membres du CS dans `annuaire`… C'est `standards/02` §4 quater : deux
 *  écrans qui affichent la même entité la décrivent chacun, et le premier champ
 *  ajouté côté serveur n'arrive que dans l'un des deux. Le `Bail` de `mon-lot`
 *  omettait déjà trois champs du contrat.
 *
 *  ## Ce qu'il refuse
 *
 *  Dans `src/routes/**` et `src/lib/components/**`, une `interface` — ou un
 *  `type` littéral — portant un champ `id` à son premier niveau. Le champ `id`
 *  est le signe d'une entité : c'est la clé que le serveur lui donne.
 *
 *  Le type va dans `$lib/api/types.ts` ou dans le module du domaine
 *  (`$lib/api/patrimoine.ts` pour un bail), et le CLIENT le rend.
 *
 *  ## Ce qui est déclaré, et pourquoi deux listes
 *
 *  - `DETTE` : les types d'entité encore dans un écran, à monter au fil de
 *    l'eau (#1044). La liste ne peut que DÉCROÎTRE : une entrée qui ne sert
 *    plus fait échouer le contrôle, comme un plafond périmé.
 *  - `LEGITIMES` : un `id` qui n'est pas celui d'une entité rendue par l'API —
 *    un objet d'interface, un état de formulaire. Chacun dit pourquoi.
 *
 *  ⚠️ Le relevé lit l'ARBRE syntaxique (parseur TypeScript), pas le texte : un
 *  `id` imbriqué (`options: { id: number }[]`) n'est pas le champ du type, et
 *  une regex l'aurait confondu.
 *
 *  Lancer : node scripts/check-types-locaux.mjs [--selftest]
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';
import ts from 'typescript';

const RACINES = ['src/routes', 'src/lib/components'];

/** Types d'entité encore déclarés dans un écran — à monter (#1044). */
const DETTE = {
	'lib/components/RechercheLocataire.svelte::Compte': '#1044',
	'lib/components/RubriqueHistorique.svelte::Entree': '#1044',
	'routes/(app)/annuaire/+page.svelte::MembreCS': '#1044',
	'routes/(app)/annuaire/+page.svelte::MembreSyndic': '#1044',
	'routes/(app)/espace-cs/+page.svelte::LotRow': '#1044',
	'routes/(app)/espace-cs/+page.svelte::PendingAcces': '#1044',
	'routes/(app)/espace-cs/+page.svelte::PendingUser': '#1044',
	'routes/(app)/espace-cs/+page.svelte::SimpleUser': '#1044',
	'routes/(app)/mon-lot/+page.svelte::LotDetail': '#1044',
};

/** Un `id` qui n'est pas celui d'une entité de l'API. */
const LEGITIMES = {
	'lib/components/Toast.svelte::ToastMessage':
		"l'identifiant d'un toast à l'écran, attribué par le store — aucune entité serveur",
	'lib/components/FormulaireEditionDocument.svelte::CorrectionDocument':
		"l'état d'une correction en cours : `id: null` signifie « aucune », le document vient d'un autre type",
	'lib/components/FormulaireSondage.svelte::OptionForm':
		"une ligne du formulaire : `id` absent pour une réponse neuve, c'est la charge utile d'un PATCH",
};

/** Les blocs de code d'un fichier : le fichier entier pour `.ts`, les `<script>` pour `.svelte`. */
function blocs(source, chemin) {
	if (chemin.endsWith('.ts')) return [source];
	return [...source.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map((m) => m[1]);
}

/**  Les types d'une source qui portent un `id` à leur premier niveau. PUR. */
export function typesAvecId(source, chemin = 'x.svelte') {
	const trouves = [];
	for (const code of blocs(source, chemin)) {
		const sf = ts.createSourceFile('x.ts', code, ts.ScriptTarget.Latest, true);
		const visiter = (n) => {
			let membres = null;
			if (ts.isInterfaceDeclaration(n)) membres = n.members;
			else if (ts.isTypeAliasDeclaration(n) && ts.isTypeLiteralNode(n.type))
				membres = n.type.members;
			if (membres && membres.some((m) => m.name && m.name.getText(sf) === 'id'))
				trouves.push(n.name.text);
			ts.forEachChild(n, visiter);
		};
		visiter(sf);
	}
	return trouves;
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const t = (libelle, attendu, src, chemin) => {
		const r = typesAvecId(src, chemin).join(',');
		console.log(`${r === attendu ? 'PASS' : 'FAIL'}  ${libelle} → [${r}]`);
		if (r !== attendu) ko = 1;
	};
	//  🔴 L'état exact de `mon-lot` avant le 25/09/2026.
	t(
		'interface d’entité dans un écran',
		'Bail',
		'<script lang="ts">\n\tinterface Bail {\n\t\tid: number;\n\t\tlot_id: number;\n\t}\n</script>',
	);
	t(
		'alias de type littéral',
		'Compte',
		'<script>type Compte = { id: number; nom: string };</script>',
	);
	t('id optionnel', 'Ligne', '<script>type Ligne = { id?: number; libelle: string };</script>');
	t(
		'id IMBRIQUÉ seulement : pas une entité',
		'',
		'<script>interface Saisie { question: string; options: { id: number }[] }</script>',
	);
	t('type sans id', '', '<script>interface Medaillon { nom: string; photo: string }</script>');
	t(
		'script de module ET d’instance',
		'A,B',
		'<script context="module">interface A { id: number }</script>\n<script>interface B { id: number }</script>',
	);
	t('fichier .ts', 'C', 'export interface C { id: number }', 'x.ts');
	process.exit(ko);
}

function fichiers(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...fichiers(chemin));
		else if (/\.(svelte|ts)$/.test(nom)) sortie.push(chemin);
	}
	return sortie;
}

const tous = RACINES.flatMap(fichiers);
//  Cas zéro : l'arborescence a changé, le contrôle ne mesure plus rien.
if (tous.length < 100) {
	console.error(`✗ Cas zéro : ${tous.length} fichier(s), au moins 100 attendus.`);
	process.exit(1);
}

const vus = new Set();
const nouveaux = [];
for (const chemin of tous) {
	const rel = chemin
		.split(sep)
		.join('/')
		.replace(/^src\//, '');
	for (const nom of typesAvecId(readFileSync(chemin, 'utf8'), chemin)) {
		const cle = `${rel}::${nom}`;
		vus.add(cle);
		if (!(cle in DETTE) && !(cle in LEGITIMES)) nouveaux.push(cle);
	}
}

const perimees = [...Object.keys(DETTE), ...Object.keys(LEGITIMES)].filter((c) => !vus.has(c));

if (nouveaux.length) {
	console.error(`\n✗ ${nouveaux.length} type(s) d'entité déclaré(s) dans un écran :\n`);
	for (const c of nouveaux) console.error(`   ${c}`);
	console.error(
		'\n  Le déclarer dans `$lib/api/types.ts` ou le module de son domaine, et que le' +
			'\n  CLIENT le rende — sinon chaque écran retype la même entité, et diverge.' +
			"\n  Si ce `id` n'est pas celui d'une entité de l'API, le déclarer dans" +
			'\n  `LEGITIMES`, avec sa raison.\n',
	);
	process.exit(1);
}
if (perimees.length) {
	console.error(`\n✗ ${perimees.length} déclaration(s) qui ne servent plus :\n`);
	for (const c of perimees) console.error(`   ${c}`);
	console.error(
		'\n  Le type a quitté l’écran (ou a été renommé) : retirer la ligne. Une liste' +
			'\n  qui garde ses entrées mortes laisse la place d’en réintroduire.\n',
	);
	process.exit(1);
}

console.log(
	`✓ Types locaux : aucun type d'entité nouveau dans les écrans — ` +
		`${Object.keys(DETTE).length} en dette (#1044), ${Object.keys(LEGITIMES).length} légitimes.`,
);
