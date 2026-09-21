#!/usr/bin/env node
/**
 * Garde-fou : le mot de CODE ne sort pas dans un libellé que l'on LIT.
 *
 * ## 🔴 Le défaut (#1107, 21/09/2026)
 *
 * Après le renommage **Tickets → Affaires** (v2.1.0), les libellés d'action sont
 * restés à l'ancien vocabulaire — ou n'ont jamais suivi celui du menu :
 *
 *     + Nouvelle Publication      alors que la page s'appelle « Actualités »
 *     Signaler un problème        alors que l'objet s'appelle « Affaire »
 *     Ticket supprimé             dans un toast
 *
 * « Publication » est le nom du **modèle**, pas celui que l'utilisateur lit —
 * exactement la distinction déjà tranchée pour `TicketEvolution` / « Suite ». Le
 * renommage v2.1.0 a traité les écrans, la FAQ, le README et le manuel ; il n'a
 * pas traité les **verbes d'action**. Le mot de code a fui jusqu'au bouton.
 *
 * Le ticket en citait trois. Un relevé mécanique en a trouvé **vingt**, dans
 * seize fichiers — c'est la leçon de `project_doublons_trouves_mecaniquement` :
 * ce qu'on ne peut pas voir en relisant, un script le compte.
 *
 * ## 🔴 La liste des mots interdits n'est PAS écrite ici
 *
 * Elle se lit dans `src/lib/entites/*.ts`, où chaque entité renommée déclare son
 * `motDeCode` à côté de son `libelle`. Un troisième renommage n'ajoutera qu'une
 * ligne à sa déclaration, et ce contrôle le suivra sans qu'on y pense. Une liste
 * recopiée ici aurait divergé au premier.
 *
 * C'est aussi pourquoi ce contrôle vit côté front et non dans
 * `api/tests/test_vocabulaire_affaire.py`, qui lit les **sources de texte
 * servi** (pages.ts, FAQ, courriels, README, manuel) et **déclare ne pas lire
 * les `.svelte`** : *« le mot y apparaît des deux façons, en libellé et en
 * identifiant, sur la même ligne »*. Il a raison — et c'est justement ce que les
 * PORTES ci-dessous résolvent : on ne cherche pas le mot n'importe où, on le
 * cherche **là où un texte est composé pour être affiché**.
 *
 * ## Ce qui est vérifié
 *
 * 1. aucun `motDeCode` dans un libellé visible, hors exceptions déclarées ;
 * 2. `libelleNouveau` et `libelleModifier` **contiennent** le `libelle` — mais
 *    pour les seules entités qui portent un `motDeCode`. Ailleurs, un nom
 *    d'usage plus court est légitime (« Déposer une annonce » pour « Petite
 *    annonce »), et l'exiger ferait crier le contrôle sur du juste ;
 * 3. aucun `libelle` d'entité ne porte son propre `motDeCode` (le défaut
 *    d'origine : la source du bon mot affirmait le mauvais).
 *
 * Usage : npm run lint:vocabulaire-ecran  ·  --selftest pour exercer le contrôle
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

import { neutraliserCommentaires as sansCommentaires } from './lib-commentaires.mjs';

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..');
const SOURCE = join(RACINE, 'src');
const ENTITES = join(SOURCE, 'lib', 'entites');

/**
 * Les **portes** par lesquelles un texte devient visible.
 *
 * ⚠️ On ne cherche pas le mot dans tout le fichier : `{#each tickets as ticket}`
 * est du code, et le confondre avec un libellé ferait crier le contrôle sur du
 * légitime — un contrôle qui crie sur du légitime finit désarmé (leçon de C16).
 * Chaque motif capture ce qui sera **lu**.
 */
const PORTES = [
	{ nom: 'titre de boîte', re: /titreBoite\s*=\s*([^;\n]+)/g },
	{ nom: 'bouton de création', re: /libelle="([^"]+)"/g },
	{ nom: 'titre', re: /\btitre="([^"]+)"/g },
	{ nom: 'nom de l’objet copié', re: /quoi="([^"]+)"/g },
	{ nom: 'nom d’objet passé en prop', re: /\bobjet\s*=\s*'([^']+)'/g },
	{ nom: 'notification', re: /toast\(\s*'[a-z]+'\s*,\s*['"`]([^'"`]+)/g },
	{ nom: 'confirmation', re: /confirm\(\s*['"`]([^'"`]+)/g },
];

/**
 * Où le mot est bien le bon — chacune avec sa raison.
 *
 * 🔴 Une seule à ce jour, et elle tient à un homonyme : « publication » y
 * désigne **l'acte de publier** (épingler, rendre confidentiel, mettre en
 * brouillon), pas l'objet. Le remplacer par « actualité » rendrait la phrase
 * fausse — ces options gouvernent aussi des affaires et des événements.
 *
 * ⚠️ Une exception qui cesse de servir fait ÉCHOUER le contrôle : sans cela elle
 * survivrait à son objet et couvrirait un défaut réintroduit au même endroit.
 */
const EXCEPTIONS = [
	{
		texte: 'Options de publication',
		raison:
			"« publication » y est l'ACTE de publier, pas l'objet — la section sert aussi aux affaires et aux événements",
	},
];

function fichiers(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...fichiers(chemin));
		else if (/\.(svelte|ts)$/.test(nom)) sortie.push(chemin);
	}
	return sortie;
}

/**
 * Le vocabulaire déclaré, LU dans `entites/` — jamais recopié.
 *
 * @returns `[{ fichier, libelle, motDeCode, libelleNouveau, libelleModifier }]`
 */
export function vocabulaireDeclare(sources) {
	const champ = (s, nom) => {
		const m = new RegExp(`\\b${nom}:\\s*(?:'([^']*)'|"([^"]*)")`).exec(s);
		return m ? (m[1] ?? m[2]) : undefined;
	};
	return sources
		.map(({ fichier, source }) => ({
			fichier,
			libelle: champ(source, 'libelle'),
			motDeCode: champ(source, 'motDeCode'),
			libelleNouveau: champ(source, 'libelleNouveau'),
			libelleModifier: champ(source, 'libelleModifier'),
		}))
		.filter((e) => e.libelle);
}

/** La source se contredit-elle ? (points 2 et 3 de l'en-tête) */
export function incoherencesDeclaration(entites) {
	const fautes = [];
	for (const e of entites) {
		const attendu = (e.libelle ?? '').toLowerCase();
		if (e.motDeCode && attendu.includes(e.motDeCode.toLowerCase())) {
			fautes.push(
				`${e.fichier} : \`libelle: '${e.libelle}'\` porte son propre mot de code « ${e.motDeCode} »`,
			);
		}
		for (const clef of ['libelleNouveau', 'libelleModifier']) {
			const v = e[clef];
			if (v === undefined) {
				fautes.push(`${e.fichier} : \`${clef}\` manque`);
				continue;
			}
			//  🔴 L'inclusion n'est exigée que des entités RENOMMÉES, et c'est
			//  mesuré : « Déposer une annonce » ne contient pas « Petite annonce »,
			//  « Nouveau contrat » pas « Contrat d'entretien » — un nom formel et un
			//  nom d'usage, et les deux sont justes. Exiger l'inclusion partout
			//  faisait crier le contrôle sur ces deux-là, et un contrôle qui crie
			//  sur du légitime finit désarmé (leçon de C16).
			//
			//  Là où le mot de code existe, en revanche, l'enjeu est précisément
			//  que le libellé d'action NOMME la chose : « Signaler un problème » ne
			//  nommait rien, « Nouvelle publication » nommait le modèle. C'est le
			//  défaut #1107, et il ne se produit que sur ces entités-là.
			if (e.motDeCode && !v.toLowerCase().includes(attendu)) {
				fautes.push(`${e.fichier} : \`${clef}: '${v}'\` ne nomme pas « ${e.libelle} »`);
			}
			if (!e.motDeCode && !v.trim()) {
				fautes.push(`${e.fichier} : \`${clef}\` est vide`);
			}
		}
	}
	return fautes;
}

/** Les libellés visibles d'un fichier qui portent l'un des mots de code. */
export function libellesFautifs(source, motsDeCode, exceptions = []) {
	if (!motsDeCode.length) return [];
	const propre = sansCommentaires(source);
	const motif = new RegExp(`\\b(${motsDeCode.join('|')})s?\\b`, 'i');
	const fautes = [];
	//  🔴 Ne chercher le mot que dans ce qui est du TEXTE LITTÉRAL.
	//
	//  Ce qu'une porte capture n'est pas toujours une chaîne : `titreBoite` prend
	//  une expression, et un toast une interpolation. Or `${TICKET.libelle}` et
	//  `PUBLICATION.libelleNouveau` contiennent le mot du modèle et rendent
	//  pourtant « Affaire » et « Nouvelle actualité » — c'est précisément la
	//  forme CORRIGÉE. Les signaler reviendrait à refuser le correctif que ce
	//  contrôle existe pour imposer.
	//
	//  Deux choses partent donc : les interpolations `${…}` et les identifiants
	//  en MAJUSCULES, qui sont les constantes d'entité. Le contenu est remplacé
	//  par des espaces — jamais supprimé —, même parade que `lib-commentaires`.
	const blanchir = (t) =>
		t
			.replace(/\$\{[^}]*\}/g, (m) => ' '.repeat(m.length))
			.replace(/\b[A-Z][A-Z0-9_]{2,}\b(\.[A-Za-z][\w$]*)*/g, (m) => ' '.repeat(m.length));
	propre.split('\n').forEach((ligne, i) => {
		for (const { nom, re } of PORTES) {
			re.lastIndex = 0;
			let m;
			while ((m = re.exec(ligne))) {
				const texte = (m[1] ?? '').trim();
				if (!motif.test(blanchir(texte))) continue;
				if (exceptions.some((e) => texte.includes(e.texte ?? e))) continue;
				fautes.push({ ligne: i + 1, porte: nom, texte: texte.slice(0, 80) });
			}
		}
	});
	return fautes;
}

function selftest() {
	const cas = [];
	const verifier = (titre, obtenu, attendu) => {
		const ok = JSON.stringify(obtenu) === JSON.stringify(attendu);
		cas.push({ titre, ok, obtenu, attendu });
		console.log(`${ok ? '  ✓' : '  ✗'} ${titre}`);
	};

	//  Le vocabulaire se LIT, et le mot de code est facultatif.
	verifier(
		'le vocabulaire se lit dans la déclaration',
		vocabulaireDeclare([
			{
				fichier: 'ticket.ts',
				source: `id: 'ticket',\nlibelle: 'Affaire',\nmotDeCode: 'ticket',\nlibelleNouveau: 'Signaler une affaire',\nlibelleModifier: "Modifier l'affaire",`,
			},
			{
				fichier: 'idee.ts',
				source: `id: 'idee',\nlibelle: 'Idée',\nlibelleNouveau: 'Nouvelle idée',\nlibelleModifier: "Modifier l'idée",`,
			},
		]),
		[
			{
				fichier: 'ticket.ts',
				libelle: 'Affaire',
				motDeCode: 'ticket',
				libelleNouveau: 'Signaler une affaire',
				libelleModifier: "Modifier l'affaire",
			},
			{
				fichier: 'idee.ts',
				libelle: 'Idée',
				motDeCode: undefined,
				libelleNouveau: 'Nouvelle idée',
				libelleModifier: "Modifier l'idée",
			},
		],
	);

	//  🔴 Le défaut d'origine : la SOURCE du bon mot affirmait le mauvais.
	verifier(
		'un libelle qui porte son propre mot de code est refusé',
		incoherencesDeclaration([
			{
				fichier: 'x.ts',
				libelle: 'Publication',
				motDeCode: 'publication',
				libelleNouveau: 'Nouvelle publication',
				libelleModifier: 'Modifier la publication',
			},
		]).length,
		1,
	);
	verifier(
		'un libelleNouveau qui ne nomme pas son entité est refusé',
		incoherencesDeclaration([
			{
				fichier: 'x.ts',
				libelle: 'Affaire',
				motDeCode: 'ticket',
				libelleNouveau: 'Signaler un problème',
				libelleModifier: "Modifier l'affaire",
			},
		]).length,
		1,
	);
	//  🔴 La nuance mesurée le 21/09 : un nom FORMEL et un nom d'USAGE sont deux
	//  noms justes. Sans mot de code, l'inclusion n'est pas exigée.
	verifier(
		'sans mot de code, un nom d’usage plus court passe',
		incoherencesDeclaration([
			{
				fichier: 'annonce.ts',
				libelle: 'Petite annonce',
				libelleNouveau: 'Déposer une annonce',
				libelleModifier: "Modifier l'annonce",
			},
		]),
		[],
	);
	verifier(
		'une déclaration cohérente passe',
		incoherencesDeclaration([
			{
				fichier: 'x.ts',
				libelle: 'Affaire',
				motDeCode: 'ticket',
				libelleNouveau: 'Signaler une affaire',
				libelleModifier: "Modifier l'affaire",
			},
		]),
		[],
	);

	//  Les libellés visibles — et ce qui n'en est pas un.
	verifier(
		'le bouton de création fautif est trouvé',
		libellesFautifs('<BoutonNouveau libelle="Nouvelle publication" />', ['publication']).map(
			(f) => f.porte,
		),
		['bouton de création'],
	);
	verifier(
		'le pluriel aussi',
		libellesFautifs('<SectionFormulaire titre="Réponses aux tickets" />', ['ticket']).length,
		1,
	);
	//  🔴 Le cas que `test_vocabulaire_affaire.py` déclarait insoluble : le mot
	//  est présent DEUX fois sur la ligne, en identifiant et en libellé.
	verifier(
		'un identifiant sur la même ligne n’est pas un libellé',
		libellesFautifs('{#each tickets as ticket}<Carte titre={ticket.titre} />', ['ticket']),
		[],
	);
	verifier(
		'un commentaire qui cite le mot ne compte pas',
		libellesFautifs('<!--  libelle="Nouvelle publication" est interdit -->', ['publication']),
		[],
	);
	verifier(
		'une exception déclarée passe',
		libellesFautifs(
			'<SectionFormulaire titre="Options de publication" />',
			['publication'],
			[{ texte: 'Options de publication' }],
		),
		[],
	);
	verifier(
		'le corrigé passe',
		libellesFautifs('<BoutonNouveau libelle="Nouvelle actualité" />', ['publication']),
		[],
	);
	//  🔴 Le corrigé le plus courant EST une expression : le libellé vient de la
	//  déclaration. Le signaler reviendrait à refuser le correctif.
	verifier(
		'une interpolation qui nomme la constante n’est pas un libellé',
		libellesFautifs("toast('success', `${TICKET.libelle} supprimée`)", ['ticket']),
		[],
	);
	verifier(
		'une expression qui lit la déclaration non plus',
		libellesFautifs(
			'titreBoite = modeEdition ? PUBLICATION.libelleModifier : PUBLICATION.libelleNouveau',
			['publication'],
		),
		[],
	);
	//  ⚠️ Mais le mot EN CLAIR à côté d'une interpolation compte toujours —
	//  sinon il suffirait d'interpoler n'importe quoi pour se rendre invisible.
	verifier(
		'le mot en clair à côté d’une interpolation compte',
		libellesFautifs("toast('success', `Ticket ${t.numero} créé`)", ['ticket']).length,
		1,
	);
	//  Cas zéro : sans mot de code déclaré, le contrôle ne mesure rien.
	verifier(
		'aucun mot de code → aucun relevé (et le cas zéro le dira)',
		libellesFautifs('<BoutonNouveau libelle="Nouvelle publication" />', []),
		[],
	);

	const echecs = cas.filter((c) => !c.ok);
	if (echecs.length) {
		for (const c of echecs) {
			console.error(`\n✗ ${c.titre}\n  attendu : ${JSON.stringify(c.attendu)}`);
			console.error(`  obtenu  : ${JSON.stringify(c.obtenu)}`);
		}
		process.exit(1);
	}
	console.log(`\n✓ selftest : ${cas.length} cas, tous vérifiés.`);
	process.exit(0);
}

if (process.argv.includes('--selftest')) selftest();

const sources = readdirSync(ENTITES)
	.filter((n) => n.endsWith('.ts') && n !== 'types.ts')
	.map((n) => ({ fichier: `lib/entites/${n}`, source: readFileSync(join(ENTITES, n), 'utf8') }));

const entites = vocabulaireDeclare(sources);

//  🔴 Cas zéro : un relevé vide ne se distingue pas d'une lecture ratée. Le
//  témoin est le nombre d'entités lues — s'il tombe à zéro, c'est la forme de la
//  déclaration qui a bougé, pas le dépôt qui s'est assaini.
if (!entites.length) {
	console.error(
		'\n✗ Cas zéro : aucune entité lue dans `lib/entites/`. Soit la forme de la\n' +
			'  déclaration a changé, soit le répertoire a bougé — ne pas lire ceci comme\n' +
			'  un succès.\n',
	);
	process.exit(1);
}

const incoherences = incoherencesDeclaration(entites);
if (incoherences.length) {
	console.error('\n✗ La déclaration du vocabulaire se contredit :\n');
	for (const f of incoherences) console.error(`   ${f}`);
	console.error(
		'\n  🔴 C’est le défaut d’origine de #1107 : `libelle` disait « à l’écran »' +
			'\n  et portait le mot du modèle. La source du bon mot affirmait le mauvais.\n',
	);
	process.exit(1);
}

const motsDeCode = entites.map((e) => e.motDeCode).filter(Boolean);
const fautifs = [];
const exceptionsVues = new Set();
let libellesVus = 0;

for (const chemin of fichiers(SOURCE)) {
	const rel = relative(SOURCE, chemin).split(sep).join('/');
	if (rel.startsWith('lib/entites/')) continue;

	const source = readFileSync(chemin, 'utf8');
	for (const e of EXCEPTIONS) if (source.includes(e.texte)) exceptionsVues.add(e.texte);

	const fautes = libellesFautifs(source, motsDeCode, EXCEPTIONS);
	libellesVus += fautes.length;
	if (fautes.length) fautifs.push({ rel, fautes });
}

const exceptionsMortes = EXCEPTIONS.filter((e) => !exceptionsVues.has(e.texte));

if (fautifs.length) {
	console.error(`\n✗ Le mot du MODÈLE sort dans ${libellesVus} libellé(s) que l’on lit :\n`);
	for (const f of fautifs) {
		for (const o of f.fautes) console.error(`   ${f.rel}:${o.ligne}  (${o.porte})  « ${o.texte} »`);
	}
	console.error(
		'\n  🔴 « Publication » et « Ticket » sont des noms de MODÈLE. L’écran dit' +
			'\n  « Actualité » et « Affaire » — c’est la décision v2.0.0, et la FAQ, le' +
			'\n  README et le manuel l’appliquent déjà. Le renommage v2.1.0 a traité les' +
			'\n  écrans mais pas les VERBES D’ACTION : le mot de code a fui jusqu’au bouton.' +
			'\n\n  Le bon mot se lit dans `lib/entites/<entité>.ts` — `libelle`,' +
			'\n  `libelleNouveau`, `libelleModifier` — et ne se réécrit pas dans un écran.\n',
	);
	process.exit(1);
}

if (exceptionsMortes.length) {
	console.error('\n✗ Exception(s) déclarée(s) qui ne servent plus :\n');
	for (const e of exceptionsMortes) console.error(`   « ${e.texte} » — ${e.raison}`);
	console.error(
		'\n  Une exception qui survit à son objet couvre un défaut réintroduit au' +
			'\n  même endroit. La retirer d’`EXCEPTIONS`.\n',
	);
	process.exit(1);
}

console.log(
	`✓ Vocabulaire d’écran : ${entites.length} entité(s) déclarée(s), ` +
		`${motsDeCode.length} mot(s) de modèle surveillé(s) (${motsDeCode.join(', ')}), ` +
		`aucun dans un libellé — ${EXCEPTIONS.length} exception(s), toutes encore utiles.`,
);
