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

/** Composants qui posent un intitulé par défaut — donc muets sous une section nommée. */
const PORTEURS = ['FichiersUpload', 'PerimetrePicker', 'DestinatairePicker'];

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

		for (const porteur of PORTEURS) {
			const balise = new RegExp(`<${porteur}\\b([^>]*)>`, 'g');
			let b;
			while ((b = balise.exec(contenu)) !== null) {
				//  `readonly` : le composant est en lecture, pas un champ de saisie.
				if (/\breadonly\b/.test(b[1])) continue;
				if (/\btitre\s*=\s*""/.test(b[1])) continue;

				const ligne = source.slice(0, m.index + m[0].indexOf(b[0])).split('\n').length;
				erreurs.push(
					`${relatif}:${ligne} — <${porteur}> sous la section « ${titre[1]} » sans titre="" : ` +
						"son intitulé par défaut s'affichera SOUS celui de la section, en double.",
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
			"   ne le laisse pas se nommer lui-même. Poser titre=\"\" sur le champ, et pour=\n" +
			"   sur la section quand le champ est labelable — le titre devient alors un vrai\n" +
			'   <label for>, ce dont un lecteur d\'écran a besoin.\n',
	);
	process.exit(1);
}

console.log(
	`✓ Titres : ${sectionsVues} sections de formulaire — aucun intitulé écrit deux fois ` +
		`(${PORTEURS.join(', ')}).`,
);
