/**
 * Garde-fou — **le nom de la section écrit deux fois**.
 *
 * ## Le défaut, vu deux fois, signalé deux fois par l'utilisateur
 *
 * `SectionFormulaire` pose un intitulé en petites capitales au-dessus de son
 * contenu. Trois composants portent DÉJÀ leur propre intitulé par défaut —
 * `FichiersUpload` (« Photos », « Documents »), `PerimetrePicker` (« Périmètre »),
 * `DestinatairePicker` (« Destinataires »). Mis dans une section du même nom, ils
 * l'affichent une seconde fois, en dessous et dans une autre typographie :
 *
 *     PÉRIMÈTRE
 *     Périmètre *          [Copropriété entière]
 *
 *     PHOTOS
 *     Photos
 *     [Ajouter des photos]
 *
 * Le premier cas est du **16/08/2026**, sur le périmètre. `SectionFormulaire`
 * en a tiré une règle, écrite dans son propre en-tête :
 *
 * > Une section qui ne contient qu'UN champ ne répète pas son nom. Le titre de
 * > section devient le libellé, et le champ n'écrit plus rien (`titre=""`).
 *
 * Le second est du **18/08/2026**, sur les photos de l'annonce de hall — capture
 * à l'appui, deux jours après. La règle était écrite, connue, appliquée dans
 * `ChampsCommuns` et `EvolForm`, et l'écran suivant l'a manquée quand même.
 *
 * 🔴 **C'est la définition d'une règle sans garde-fou** : elle tient tant que
 * celui qui écrit s'en souvient, et le défaut est trouvé par l'utilisateur, à
 * l'écran, en production (`standards/05-tests-et-garde-fous.md`).
 *
 * ## Ce que ce contrôle cherche — volontairement étroit
 *
 * Un des trois composants ci-dessus, à l'intérieur d'une `<SectionFormulaire>`
 * dont le `titre` n'est pas vide, sans `titre=""` explicite. Rien d'autre : un
 * contrôle large sur du balisage produit des faux positifs, et un contrôle qu'on
 * apprend à ignorer ne garde plus rien (`standards/04`).
 *
 * Il ne juge PAS si la section a un ou plusieurs champs : porter son propre nom
 * sous une section homonyme est redondant dans les deux cas. Le titre du champ
 * reste possible quand la section n'en a pas (`titre=""` sur la section), ce que
 * ce contrôle laisse passer.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');

/**
 * Les composants qui posent un intitulé par défaut — **calculés, jamais listés**.
 *
 * 🔴 CETTE LISTE ÉTAIT TENUE À LA MAIN, et elle a laissé passer le cas du
 * 02/09/2026 : `SectionDiffusion` rend lui-même `<SectionFormulaire titre="Diffusion">`,
 * et `FormulaireAnnonceHall` l'enveloppait dans une seconde section du même nom.
 * Deux bandes « DIFFUSION » l'une sous l'autre, signalé à l'écran, capture à
 * l'appui — TROISIÈME signalement de ce défaut, et le premier APRÈS l'écriture de
 * ce contrôle.
 *
 * Une liste recopiée diverge au premier composant ajouté, et c'est justement le
 * composant ajouté qui échappe au contrôle. Le dépôt l'a appris quatre fois
 * (périmètres #316, canaux, libellés de tâches, table des pages #401), et
 * `check-formulaire-creation` en avait tiré la leçon dès le 30/08 en CALCULANT
 * ses porteurs. Ce fichier-ci ne l'avait pas fait.
 *
 * Un composant est porteur s'il annonce un intitulé de deux façons :
 *
 *   1. il rend lui-même une `<SectionFormulaire titre="X">` — `SectionDiffusion` ;
 *   2. il expose `export let titre = 'X'` — `FichiersUpload`, `PerimetrePicker`,
 *      `DestinatairePicker`.
 *
 * @returns Map<nom du composant, Set<intitulés qu'il pose, en minuscules>>
 */
function porteursDIntitule(fichiers) {
	const porteurs = new Map();
	for (const chemin of fichiers) {
		const nom = chemin
			.replace(/\\/g, '/')
			.split('/')
			.pop()
			.replace(/\.svelte$/, '');
		const source = readFileSync(chemin, 'utf8');
		const titres = new Set();
		for (const m of source.matchAll(/<SectionFormulaire[^>]*\stitre\s*=\s*"([^"]+)"/g))
			titres.add(m[1].trim().toLowerCase());
		for (const m of source.matchAll(/export let titre\s*=\s*'([^']+)'/g))
			titres.add(m[1].trim().toLowerCase());
		if (titres.size > 0) porteurs.set(nom, titres);
	}
	return porteurs;
}

/** Nombre minimal de sections attendues — cas zéro. */
const SECTIONS_MINIMALES = 20;

function fichiersSvelte(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...fichiersSvelte(chemin));
		else if (nom.endsWith('.svelte')) sortie.push(chemin);
	}
	return sortie;
}

const fichiers = fichiersSvelte(RACINE);
if (fichiers.length === 0) {
	console.error("✗ Cas zéro : aucun composant analysé — l'arborescence a changé.");
	console.error('Ne pas lire ceci comme un succès.');
	process.exit(1);
}

const PORTEURS = porteursDIntitule(fichiers);
const erreurs = [];
let sectionsVues = 0;

//  Une `<SectionFormulaire …>` … `</SectionFormulaire>` avec ses attributs et son
//  contenu. Non imbriquée : le composant ne s'emboîte pas dans le dépôt.
const SECTION = /<SectionFormulaire\b([^>]*)>([\s\S]*?)<\/SectionFormulaire>/g;

for (const chemin of fichiers) {
	const relatif = relative(RACINE, chemin).replace(/\\/g, '/');
	const source = readFileSync(chemin, 'utf8');

	let m;
	SECTION.lastIndex = 0;
	while ((m = SECTION.exec(source)) !== null) {
		const [, attributs, contenu] = m;
		sectionsVues++;

		//  Une section sans titre ne peut rien dupliquer.
		const titre = /\btitre\s*=\s*"([^"]*)"/.exec(attributs);
		if (!titre || titre[1].trim() === '') continue;

		for (const [porteur, titresPortes] of PORTEURS) {
			//  ⚠️ On ne signale que l'HOMONYMIE. Un composant qui pose « Diffusion »
			//  sous une section « Photos » n'est pas une redite : c'est un autre
			//  intitulé, et crier dessus ferait un contrôle qu'on apprend à ignorer.
			if (!titresPortes.has(titre[1].trim().toLowerCase())) continue;
			//  🔴 `\\b` ET NON `\b` : dans un template literal, JavaScript
			//  interprète `\b` comme le caractère BACKSPACE (U+0008). Le motif
			//  cherchait donc `<SectionDiffusion␈`, qui ne correspond à rien.
			//
			//  ⚠️ Ce contrôle n'a JAMAIS rien pu trouver depuis son écriture — il
			//  était vert parce qu'il ne mesurait rien. C'est la QUATRIÈME occurrence
			//  de ce défaut dans le dépôt (#549, check-workflow-envoye, lib-cadres),
			//  et la première de cette variante : les trois autres portaient un U+0008
			//  écrit dans le FICHIER, que le contrôle du job test-scripts attrape. Ici
			//  le fichier contient deux caractères parfaitement lisibles, et c'est
			//  l'interprétation à l'exécution qui les transforme. Aucun octet suspect
			//  à trouver, aucune relecture ne le voit.
			const balise = new RegExp(`<${porteur}\\b([^>]*)>`, 'g');
			let b;
			while ((b = balise.exec(contenu)) !== null) {
				//  `readonly` : le composant est en lecture, pas un champ de saisie.
				if (/\breadonly\b/.test(b[1])) continue;
				if (/\btitre\s*=\s*""/.test(b[1])) continue;

				const ligne = source.slice(0, m.index + m[0].indexOf(b[0])).split('\n').length;
				erreurs.push(
					`${relatif}:${ligne} — <${porteur}> sous la section « ${titre[1]} » : ` +
						"il pose DÉJÀ cet intitulé, qui s'affichera une seconde fois en dessous.",
				);
			}
		}
	}
}

//  Cas zéro : un contrôle qui ne reconnaît presque rien ne conclut pas au vert.
if (sectionsVues < SECTIONS_MINIMALES) {
	console.error(
		`✗ Cas zéro : ${sectionsVues} <SectionFormulaire> reconnue(s), ${SECTIONS_MINIMALES} attendues au minimum.`,
	);
	console.error(
		'Le front en portait bien davantage le 18/08/2026. Un effondrement du relevé\n' +
			'signale que le contrôle a cessé de voir — pas que le défaut a disparu\n' +
			'(`standards/04-fiabilite-des-controles.md` §2).',
	);
	process.exit(1);
}

if (erreurs.length) {
	console.error("✗ Le nom de la section est écrit deux fois à l'écran :\n");
	for (const e of erreurs) console.error(`  • ${e}`);
	console.error(
		'\n🔴 Règle (`SectionFormulaire`, 16/08/2026) : une section qui nomme son contenu\n' +
			'   ne le laisse pas se nommer lui-même. Poser titre="" sur le champ, et pour=\n' +
			'   sur la section quand le champ est labelable — le titre devient alors un vrai\n' +
			"   <label for>, ce dont un lecteur d'écran a besoin.\n",
	);
	process.exit(1);
}

console.log(
	`✓ Titres : ${sectionsVues} sections de formulaire — aucun intitulé écrit deux fois ` +
		`(${[...PORTEURS.keys()].join(', ')}).`,
);
