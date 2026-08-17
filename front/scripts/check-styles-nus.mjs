/**
 * Garde-fou : on ne réécrit pas à la main ce qu'`app.css` porte déjà.
 *
 * Deux volets, nés du même défaut à deux endroits différents :
 *
 *   A. dans un `<style>` de composant — un sélecteur d'ÉLÉMENT nu ;
 *   B. dans le balisage d'une PAGE comme d'un composant — un `style="…"` en ligne
 *      qui RECOMPOSE une classe déjà offerte par `app.css`.
 *
 * ## Volet A — le défaut qui a fait naître ce contrôle (16/08/2026)
 *
 * `sondages/+page.svelte` portait `input, textarea { … width: 100% }`. Le sélecteur
 * visait les champs de saisie et atteignait **toutes les cases à cocher de la
 * page**, qui s'étiraient sur la largeur du formulaire. Signalé sur DEUX écrans
 * sans lien apparent — c'était une seule ligne, et quatre composants l'annulaient
 * déjà case par case avec un `style="width:auto"` recopié. Détail : ux-patterns
 * §9 octies. Est refusé : un sélecteur EXACTEMENT réduit à un nom d'élément de
 * formulaire. Reste autorisé, et c'est l'essentiel du besoin légitime : `.case
 * input[type="checkbox"]`, `.form-grid select`, `input[type="range"]`.
 *
 * ## Volet B — pourquoi la portée s'élargit au balisage (17/08/2026, #425)
 *
 * Le formulaire d'édition d'un ticket portait depuis le 19/04/2026 des `style="…"`
 * recomposant `.field`, `.field label`, `.field input` et `.form-actions`. **Aucun
 * contrôle ne le regardait** : `lint:styles` ne lisait que les blocs `<style>`,
 * `lint:formulaires` ne juge que l'usage de `FormulaireCreation`, `lint:entetes`
 * que les en-têtes. Un formulaire écrit à la main dans une page passait entre les
 * trois.
 *
 * C'est la DEUXIÈME fois en deux jours qu'un garde-fou a une portée plus étroite
 * que la règle qu'il défend : `lint:soumission` ne regardait que les fichiers
 * nommés `Formulaire*.svelte` (#416), et a laissé passer le formulaire le plus
 * réutilisé du site. Même remède ici : **le tri se fait sur ce que le balisage
 * FAIT, pas sur le fichier où il est écrit**.
 *
 * ### Recomposition ≠ variation légitime
 *
 * Il y a plus de mille `style="…"` dans `src/`, presque tous des ajustements sains
 * (`flex:1`, `width:120px`, une couleur de statut) : les refuser en bloc
 * désarmerait le contrôle en une semaine. Ne sont refusées que les **signatures**
 * déclarées plus bas, chacune reproduisant une règle précise d'`app.css`, plus la
 * `redite-classe` — un élément qui porte DÉJÀ la classe et redéclare en ligne ce
 * qu'elle lui donne, no-op qui fait croire que la valeur est locale et invite à la
 * faire diverger.
 *
 * ⚠️ Volontairement HORS signature sur un contrôle de saisie : `width`, `font-size`
 * et `flex`. Un champ de filtre plus dense ou une colonne de 120 px sont des
 * variations réelles — les refuser reviendrait à crier sur du légitime, et « un
 * contrôle qui crie sur du légitime finit désarmé » (`check-pages.mjs`).
 *
 * ### Les valeurs ne sont PAS recopiées ici — elles sont LUES dans `app.css`
 *
 * `.875rem`, `flex-end`, `720px` : les écrire ici en ferait une seconde source,
 * libre de diverger de la première (`standards/02` §2). Pire, le jour où `app.css`
 * changerait une valeur, la signature ne correspondrait plus à rien et **ce
 * contrôle passerait au vert sans rien contrôler**. Elles sont donc extraites
 * d'`app.css` à chaque exécution, et le cas zéro échoue si la règle qu'une
 * signature vise a disparu ou ne déclare plus ce qu'elle prétend lire.
 *
 * ⚠️ `app.css` n'est PAS analysé comme une source : c'est justement l'endroit où
 * une règle d'élément est légitime, parce qu'elle y est globale et assumée.
 *
 * Le contrôle s'auto-contrôle : s'il ne trouve rien à lire — pas de `.svelte`, pas
 * d'`app.css`, plus aucun `style=` reconnu, une balise qu'il n'arrive pas à nommer,
 * une tolérance périmée — il ÉCHOUE au lieu de conclure au vert
 * (`standards/04-fiabilite-des-controles.md` §2).
 *
 * ## Trois fichiers, et pourquoi
 *
 * Ce contrôle a dépassé 500 lignes en recevant le volet B, et le garde-fou de
 * modularité — rang 1, sans dérogation — a refusé le push. Découpé sur la même
 * frontière que `precheck-mep.sh` / `scripts/lib/lib-verdicts-mep.sh` (11/08/2026),
 * qui s'était fait arrêter par son propre pré-check :
 *
 *   • `check-styles-nus.mjs`         — la DÉTECTION : cas zéro, parcours du disque,
 *                                      verdicts et messages. C'est le seul des trois
 *                                      qui fasse des entrées/sorties.
 *   • `check-styles-nus.regles.mjs`  — la RÈGLE : signatures, classes de structure,
 *                                      tolérances nommées. Bouge à chaque écran repris.
 *   • `lib-analyse-styles.mjs`       — l'ANALYSE, fonctions PURES, éprouvées seules
 *                                      par `node scripts/lib-analyse-styles.mjs --selftest`.
 *
 * Usage : npm run lint:styles   (exit 1 si violation)
 */
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
//  La RÈGLE (ce qui est refusé, et les écarts déjà connus) vit à côté ; ce fichier-ci
//  porte la DÉTECTION. La première bouge à chaque écran repris, la seconde ne bouge pas.
import { SIGNATURES, CLASSES_STRUCTURE, ELEMENTS, TOLERANCES } from './check-styles-nus.regles.mjs';
//  Les fonctions d’ANALYSE sont PURES et vivent à part : elles ne touchent ni au
//  disque ni à la sortie, et s’éprouvent seules — `--selftest` sur ce module.
import {
	balisageSeul,
	baliseAvant,
	blocsStyle,
	classesDe,
	declarationsDe,
	decouperDeclarations,
	reglesCss,
	selecteursNus,
} from './lib-analyse-styles.mjs';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const APP_CSS = join(RACINE, 'app.css');

/** En dessous, le motif de lecture ne correspond plus au balisage (cas zéro). */
const PLANCHER_STYLES = 200;


// ── Entrées/sorties : tout ce qui touche le disque ou la sortie vit ICI ─────

function abandonner(message) {
	//  Un contrôle qui ne peut pas s'exécuter renvoie INCONNU, jamais OK.
	console.error(`\n✗ lint:styles — ${message}\n`);
	process.exit(1);
}

function fichiersSvelte(dossier) {
	const trouves = [];
	for (const entree of readdirSync(dossier)) {
		const chemin = join(dossier, entree);
		if (statSync(chemin).isDirectory()) trouves.push(...fichiersSvelte(chemin));
		else if (entree.endsWith('.svelte')) trouves.push(chemin);
	}
	return trouves;
}

// ── Cas zéro : un contrôle qui n'a rien lu ne dit pas « tout va bien » ───────

if (!existsSync(APP_CSS)) {
	abandonner(
		`${APP_CSS} est introuvable.\n` +
			'  Les valeurs de référence des signatures y sont lues : sans lui, ce contrôle ne\n' +
			'  sait plus ce qu’est une recomposition, et se taire reviendrait à conclure au vert.',
	);
}

const REGLES_APP = reglesCss(readFileSync(APP_CSS, 'utf8'));

for (const sig of SIGNATURES) {
	const decl = declarationsDe(REGLES_APP, sig.regle);
	const manquantes = sig.proprietes.filter((p) => !decl.has(p));
	if (decl.size === 0 || manquantes.length) {
		abandonner(
			`la règle \`${sig.regle}\` d’app.css ${
				decl.size === 0
					? 'a disparu'
					: `ne déclare plus ${manquantes.map((p) => `\`${p}\``).join(', ')}`
			}.\n` +
				`  La signature « ${sig.nom} » ne correspondrait donc plus à rien, et ce contrôle\n` +
				'  passerait au vert sans rien contrôler. Mettre la signature à jour — ou la retirer\n' +
				'  si la classe qu’elle défend n’existe plus.',
		);
	}
	sig.reference = decl;
}

for (const classe of CLASSES_STRUCTURE) {
	const decl = declarationsDe(REGLES_APP, `.${classe}`);
	if (decl.size === 0) {
		abandonner(
			`la classe \`.${classe}\` a disparu d’app.css — le volet « redite-classe » ne peut\n` +
				'  plus dire ce qu’elle porte, et laisserait repasser toute redéclaration en ligne.',
		);
	}
}
const PROPS_STRUCTURE = Object.fromEntries(
	CLASSES_STRUCTURE.map((c) => [c, [...declarationsDe(REGLES_APP, `.${c}`).keys()]]),
);

const fichiers = fichiersSvelte(RACINE);
if (fichiers.length < 20) {
	abandonner(
		`${fichiers.length} fichier(s) .svelte trouvé(s) sous ${RACINE} : le contrôle ne peut\n` +
			'  pas s’exécuter, il ne passe donc pas au vert.',
	);
}

const inconnues = Object.keys(TOLERANCES).filter((cle) => {
	const sig = cle.split('::')[1];
	return sig !== undefined && sig !== 'redite-classe' && !SIGNATURES.some((s) => s.nom === sig);
});
if (inconnues.length) {
	abandonner(
		'ces tolérances nomment une signature qui n’existe pas — elles ne protègent donc\n' +
			`  rien, en silence :\n    ${inconnues.join('\n    ')}`,
	);
}

// ── Relevé ───────────────────────────────────────────────────────────────────

const fautes = [];
const tolerancesVues = new Set();
let stylesLus = 0;
const balisesIllisibles = [];

/** Enregistre une faute, ou la tolérance qui la couvre. */
function signaler(relatif, cle, ligne, quoi, remede, detail) {
	if (cle in TOLERANCES) {
		tolerancesVues.add(cle);
		return;
	}
	fautes.push(
		`${relatif}:${ligne} — ${quoi}\n      ${detail}\n      → ${remede}`,
	);
}

for (const fichier of fichiers) {
	const relatif = relative(RACINE, fichier).split(sep).join('/');
	const source = readFileSync(fichier, 'utf8');

	//  Volet A — les sélecteurs d'élément nus des blocs `<style>`.
	for (const { contenu, ligneDebut } of blocsStyle(source)) {
		for (const { selecteur, ligne } of selecteursNus(contenu, ELEMENTS)) {
			const cle = `${relatif}:${selecteur}`;
			if (cle in TOLERANCES) {
				tolerancesVues.add(cle);
				continue;
			}
			fautes.push(
				`${relatif}:${ligneDebut + ligne - 1} — sélecteur d’ÉLÉMENT nu « ${selecteur} »\n` +
					`      il atteint TOUS les <${selecteur}> du composant, y compris ceux qu’on n’avait pas en tête\n` +
					'      → qualifier le sélecteur (`.mon-champ input`, `input[type="range"]`) ou porter la règle dans `app.css`',
			);
		}
	}

	//  Volet B — les `style="…"` en ligne du balisage.
	const balisage = balisageSeul(source);
	const motif = /\bstyle="([^"]*)"/g;
	let m;
	while ((m = motif.exec(balisage)) !== null) {
		stylesLus++;
		const ligne = balisage.slice(0, m.index).split('\n').length;
		const balise = baliseAvant(balisage, m.index);
		if (!balise) {
			balisesIllisibles.push(`${relatif}:${ligne}`);
			continue;
		}
		const declarations = decouperDeclarations(m[1]);
		const parPropriete = new Map(declarations.map((d) => [d.propriete, d.valeur]));

		for (const sig of SIGNATURES) {
			if (sig.elements && !sig.elements.includes(balise.nom)) continue;
			let touchees;
			if (sig.mode === 'valeurs') {
				//  Toutes les propriétés, ET la même valeur qu'`app.css` : c'est cette
				//  double exigence qui distingue la recomposition de l'ajustement.
				const identiques = sig.proprietes.filter(
					(p) => parPropriete.has(p) && parPropriete.get(p) === sig.reference.get(p),
				);
				touchees = identiques.length === sig.proprietes.length ? identiques : [];
			} else {
				touchees = sig.proprietes.filter((p) => parPropriete.has(p));
			}
			if (!touchees.length) continue;
			signaler(
				relatif,
				`${relatif}::${sig.nom}`,
				ligne,
				`<${balise.nom}> recompose ${sig.quoi}`,
				sig.remede,
				`${touchees.map((p) => `${p}:${parPropriete.get(p)}`).join(' ; ')}  ` +
					`(déjà porté par \`${sig.regle}\` dans app.css)`,
			);
		}

		//  Volet B bis — la classe est DÉJÀ là, et le style la redit.
		for (const classe of classesDe(balise.attributs)) {
			const portees = PROPS_STRUCTURE[classe];
			if (!portees) continue;
			const redites = declarations
				.map((d) => d.propriete)
				.filter((p) => portees.includes(p));
			if (!redites.length) continue;
			signaler(
				relatif,
				`${relatif}::redite-classe`,
				ligne,
				`<${balise.nom} class="${classe}"> redit une propriété que \`.${classe}\` porte déjà`,
				`retirer \`${redites.join('`, `')}\` du style en ligne — la valeur vit dans \`.${classe}\` (app.css), ` +
					'et une seconde écriture est exactement ce qui finit par diverger',
				redites.map((p) => `${p}:${parPropriete.get(p)}`).join(' ; '),
			);
		}
	}
}

//  Le motif de lecture correspond-il encore au balisage ? Zéro `style=` reconnu
//  sur plus de mille écrits ne veut pas dire « le dépôt est propre ».
if (stylesLus < PLANCHER_STYLES) {
	abandonner(
		`${stylesLus} attribut(s) \`style="…"\` lus dans ${fichiers.length} fichiers, au moins\n` +
			`  ${PLANCHER_STYLES} attendus. Le motif de lecture ne correspond plus au balisage : le\n` +
			'  volet « recomposition » ne mesure alors plus rien.',
	);
}

//  Une balise qu'on n'arrive pas à nommer, c'est une signature qu'on n'applique
//  pas — et un silence qui ressemble à un feu vert. On le dit.
if (balisesIllisibles.length) {
	abandonner(
		`${balisesIllisibles.length} attribut(s) \`style="…"\` dont la balise porteuse n’a pas pu\n` +
			'  être nommée — les signatures visant un `<input>`, `<select>` ou `<textarea>` n’y ont\n' +
			'  donc pas été appliquées. Mettre `baliseAvant()` à jour :\n    ' +
			balisesIllisibles.join('\n    '),
	);
}

//  Une tolérance qui ne sert plus doit disparaître, sinon la liste couvre un jour
//  un cas redevenu normal et le contrôle reste vert sans rien contrôler.
const perimees = Object.keys(TOLERANCES).filter((c) => !tolerancesVues.has(c));
if (perimees.length) {
	console.error(
		'\n✗ lint:styles — ces tolérances ne servent plus :\n\n' +
			perimees.map((c) => `  ${c}\n      « ${TOLERANCES[c]} »`).join('\n') +
			'\n\n  Le fichier a disparu, ou il est devenu conforme. Retirer l’entrée : reconduite\n' +
			'  « au cas où », elle protège un écran qui n’en a plus besoin et masque la prochaine\n' +
			'  vraie recomposition. Si AUCUNE ne sert plus, c’est la DÉTECTION qui est cassée.\n',
	);
	process.exit(1);
}

if (fautes.length) {
	console.error(
		'\n✗ lint:styles — ' +
			`${fautes.length} écriture(s) refont à la main ce qu’\`app.css\` porte déjà :\n\n  ` +
			fautes.join('\n\n  ') +
			'\n\n  Une seconde écriture d’une règle n’est pas une commodité : c’est une valeur libre\n' +
			'  de diverger de celle qu’elle copie. Le formulaire d’édition de ticket portait ses\n' +
			'  `style=` depuis avril, et personne ne le voyait (#425).\n' +
			'\n  Une exception réelle se déclare dans TOLERANCES, avec sa raison.\n',
	);
	process.exit(1);
}

console.log(
	`✓ lint:styles — ${fichiers.length} fichiers, ${stylesLus} styles en ligne lus : ` +
		'aucun sélecteur d’élément nu, aucune recomposition de classe ' +
		`(${Object.keys(TOLERANCES).length} tolérances nommées).`,
);
