/**
 * Garde-fou : un écran ne redéfinit pas une classe que la charte porte déjà.
 *
 * ## Le défaut (#607, 28/08/2026)
 *
 * `residence/+page.svelte` portait dans son `<style>` :
 *
 *     .pill { border: 1px solid …; background: var(--color-surface); font-size: .8rem; }
 *
 * `styles/ecrans.css` porte la même classe avec **d'autres valeurs** — bordure
 * 1.5px, fond `--color-bg`, `.85rem`. Deux styles de pastille coexistaient donc
 * sur le site, et lequel s'appliquait dépendait de l'écran. Signalé à l'écran, pas
 * par un contrôle.
 *
 * ⚠️ `ecrans.css` portait l'avertissement **en toutes lettres** : « residence porte
 * SA variante de `.pill` ». Lu, compris, laissé en place, et rien n'échouait —
 * `standards/05` §1 : un commentaire n'est pas un garde-fou.
 *
 * ## Pourquoi `lint:classes-nues` était vert
 *
 * Son volet B ne refuse qu'un `:global(.x)` de premier niveau. C'est juste, et ce
 * n'est pas la même question :
 *
 * | Question | Contrôle |
 * |---|---|
 * | cette règle **déborde**-t-elle sur les autres écrans ? | `lint:classes-nues` |
 * | cette règle fait-elle rendre **cet écran-ci** autrement que la charte ? | celui-ci |
 *
 * Une règle **scopée** ne déborde pas — Svelte l'isole. Elle gagne simplement
 * contre la charte sur sa propre page, par la classe de portée que Svelte ajoute
 * au sélecteur. Le site devient incohérent d'un écran à l'autre, sans décision.
 *
 * 🔴 C'est le quatrième garde-fou de ce dépôt dont la portée était plus étroite
 * que la règle qu'il défend — après `lint:soumission` (#416), le volet B de
 * `lint:styles` (#425) et son volet C (#593).
 *
 * ## Ce qui est refusé, et ce qui ne l'est pas
 *
 * Refusé : une règle dont le sélecteur est **exactement** `.x`, quand `.x` est
 * portée par le CSS global, et qui redéclare au moins une propriété que la charte
 * déclare déjà.
 *
 * ⚠️ **Pas** refusé : la règle qui n'AJOUTE que des propriétés absentes de la
 * charte (`.card { overflow: hidden }`), ni le sélecteur qualifié (`.form-grid
 * .field`), ni un modificateur (`.pill.compacte`). Le tri est le même que celui du
 * volet B de `lint:styles` — refuser en bloc désarmerait le contrôle en une
 * semaine.
 *
 * ⚠️ Les valeurs de la charte sont lues **hors `@media`** : en y descendant, la
 * valeur MOBILE devient la référence, et le contrôle annoncerait des
 * recompositions qui n'existent pas. C'est ce qui faussait le premier relevé.
 *
 * Usage : npm run lint:charte   (exit 1 si violation)
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { blocsStyle, declarationsDe, reglesCss } from './lib-analyse-styles.mjs';
import { cssGlobal } from './lib-css-global.mjs';
import { TOLERANCES } from './check-charte-recomposee.regles.mjs';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');

/** En dessous, la charte n'a pas été lue : le contrôle ne mesure plus rien. */
const PLANCHER_CLASSES_CHARTE = 80;

function abandonner(message) {
	//  Un contrôle qui ne peut pas s'exécuter renvoie INCONNU, jamais OK.
	console.error(`\n✗ lint:charte — ${message}\n`);
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

/**
 * La CLÉ de comparaison quand le sélecteur en a une, sinon `null`.
 *
 * Deux formes, et deux seulement :
 *   - `.x`          → `x`         (la classe seule)
 *   - `.x element`  → `x element` (un descendant par sa BALISE)
 *
 * 🔴 La seconde a été ajoutée le 30/08/2026, après un défaut visible en
 * production : *« on ne voit pas l'onglet actif »*. `prestataires` redéfinissait
 * `.tabs button` en entier — les neuf propriétés de la charte, dont `color` et
 * `border-bottom: transparent`, c'est-à-dire les deux que `.tabs button.active`
 * change. À spécificité égale, le style scopé du composant est injecté après la
 * feuille commune : il gagnait, et le liseré de l'onglet actif disparaissait.
 *
 * ⚠️ Ce contrôle était **vert**, et il ne pouvait pas faire autrement : il ne
 * lisait que les sélecteurs `.x` seuls. C'est le motif corrigé le matin même
 * dans `check-modales` — *un contrôle qui n'énumère que les formes qu'il connaît
 * est aveugle à la suivante*. Ici la forme manquante est celle qu'emploie tout
 * composant qui habille ses enfants : onglets, listes, tableaux.
 *
 * On s'arrête au descendant par balise : `.x .y` est déjà couvert par `.y`, et
 * les pseudo-classes (`:hover`, `.active`) sont des ÉTATS — les comparer
 * demanderait de résoudre la cascade, pas de comparer deux corps de règle.
 */
function classeSeule(selecteur) {
	const propre = selecteur.trim();
	const simple = /^\.([A-Za-z][\w-]*)$/.exec(propre);
	if (simple) return simple[1];
	const descendant = /^\.([A-Za-z][\w-]*)\s+([a-z][a-z0-9]*)$/.exec(propre);
	return descendant ? `${descendant[1]} ${descendant[2]}` : null;
}

// ── Cas zéro ────────────────────────────────────────────────────────────────

const CSS_GLOBAL = cssGlobal(RACINE);
if (!CSS_GLOBAL.trim()) {
	abandonner(
		`Aucun CSS global lisible dans ${RACINE} (app.css + styles/). Sans la charte, ce ` +
			'contrôle ne sait pas ce qui est une redéfinition, et se taire vaudrait un vert.',
	);
}

//  🔴 Hors `@media` : c'est la valeur de BASE qui fait référence. Voir l'en-tête.
const REGLES_CHARTE = reglesCss(CSS_GLOBAL, { horsMedia: true });
const CHARTE = new Map();
for (const [tete] of REGLES_CHARTE) {
	for (const part of tete.split(',')) {
		const nom = classeSeule(part);
		if (nom && !CHARTE.has(nom)) CHARTE.set(nom, declarationsDe(REGLES_CHARTE, `.${nom}`));
	}
}
if (CHARTE.size < PLANCHER_CLASSES_CHARTE) {
	abandonner(
		`${CHARTE.size} classe(s) de charte lue(s), au moins ${PLANCHER_CLASSES_CHARTE} attendues.\n` +
			'  Le motif de lecture ne correspond plus au CSS global : ce contrôle ne comparerait\n' +
			'  plus qu’à une poignée de classes, et se tairait sur toutes les autres.',
	);
}

const fichiers = fichiersSvelte(RACINE);
if (fichiers.length < 20) {
	abandonner(`${fichiers.length} fichier(s) .svelte sous ${RACINE} : le contrôle n’a rien lu.`);
}

// ── Relevé ──────────────────────────────────────────────────────────────────

const fautes = [];
const tolerancesVues = new Set();
let reglesLues = 0;

for (const fichier of fichiers) {
	const relatif = relative(RACINE, fichier).split(/[\\/]/).join('/');
	for (const { contenu } of blocsStyle(readFileSync(fichier, 'utf8'))) {
		//  Hors `@media` là aussi : une règle responsive d'écran est une VARIATION
		//  assumée — c'est même le seul endroit où réécrire une classe est normal.
		for (const [tete, corps] of reglesCss(contenu, { horsMedia: true })) {
			for (const part of tete.split(',')) {
				const nom = classeSeule(part);
				if (nom === null) continue;
				const charte = CHARTE.get(nom);
				if (!charte) continue;
				reglesLues++;
				const locales = declarationsDe([[part.trim(), corps]], `.${nom}`);
				const redites = [...locales.keys()].filter((p) => charte.has(p));
				if (!redites.length) continue; // n'ajoute que du neuf : légitime

				const cle = `${relatif}::${nom}`;
				if (cle in TOLERANCES) {
					tolerancesVues.add(cle);
					continue;
				}
				const detail = redites
					.map((p) =>
						locales.get(p) === charte.get(p)
							? `${p}: ${locales.get(p)} (IDENTIQUE — la règle ne sert à rien)`
							: `${p}: ${locales.get(p)} (charte ${charte.get(p)})`,
					)
					.join('\n        ');
				fautes.push(
					`${relatif} — \`.${nom}\` redéfinit ${redites.length} propriété(s) de la charte\n` +
						`        ${detail}`,
				);
			}
		}
	}
}

//  Une tolérance qui ne sert plus doit disparaître : reconduite « au cas où »,
//  elle couvre un écran devenu conforme et masque la prochaine vraie recomposition.
const perimees = Object.keys(TOLERANCES).filter((c) => !tolerancesVues.has(c));
if (perimees.length) {
	console.error(
		'\n✗ lint:charte — ces tolérances ne servent plus :\n\n' +
			perimees.map((c) => `  ${c}\n      « ${TOLERANCES[c]} »`).join('\n') +
			'\n\n  L’écran est devenu conforme, ou le fichier a disparu. Retirer l’entrée.\n' +
			'  Si AUCUNE ne sert plus, c’est la DÉTECTION qui est cassée.\n',
	);
	process.exit(1);
}

if (fautes.length) {
	console.error(
		`\n✗ lint:charte — ${fautes.length} règle(s) d’écran redéfinissent la charte :\n\n  ` +
			fautes.join('\n\n  ') +
			'\n\n  Une règle scopée ne déborde PAS sur les autres écrans — elle fait rendre\n' +
			'  CELUI-CI autrement, sans que personne l’ait décidé, et elle gagne : Svelte\n' +
			'  ajoute sa classe de portée au sélecteur, ce qui le rend plus spécifique que la\n' +
			'  charte à sélecteur égal.\n' +
			'\n  Le geste : SUPPRIMER la règle, ou ne garder que ce qui n’est PAS dans la\n' +
			'  charte. Une variation voulue se déclare dans TOLERANCES, avec sa raison.\n',
	);
	process.exit(1);
}

console.log(
	`✓ lint:charte — ${fichiers.length} composants, ${CHARTE.size} classes de charte, ` +
		`${reglesLues} règle(s) d’écran confrontée(s) : aucune redéfinition ` +
		`(${Object.keys(TOLERANCES).length} tolérance(s) nommée(s)).`,
);
