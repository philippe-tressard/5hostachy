/**
 * Les classes des FEUILLES GLOBALES — `app.css` et `src/styles/*.css` — que
 * plus aucune source n'emploie.
 *
 * ## Pourquoi (#1537, 02/10/2026)
 *
 * `lint:css-orphelin` annonçait « aucun sélecteur orphelin » alors que **23**
 * classes des feuilles globales n'étaient plus employées nulle part — dont des
 * familles entières (`.kb-item-*`, l'ancien kanban de l'accueil ; `.event-row`,
 * la page Calendrier retirée par #1092) et un commentaire qui citait comme
 * appelant un composant disparu (`CarteEvenement`).
 *
 * 🔴 Il ne mentait sur aucune ligne : il portait les `Unused CSS selector` de
 * `svelte-check`, qui ne lit que les `<style>` des composants. Une feuille
 * globale n'est le `<style>` de personne — l'outil ne peut pas savoir qui
 * l'emploie, donc il ne dit rien. Le contrôle héritait de ce silence
 * (`standards/04` §26 et §38) et son verdict parlait de « CSS » sans borne
 * (`standards/04` §12 : le nom d'un contrôle est lu comme sa portée).
 *
 * ## La règle
 *
 * Une classe définie dans une feuille globale est EMPLOYÉE si son nom apparaît
 * comme mot entier dans une source du front (`.svelte`, `.ts`, `.js`, `.html`
 * de `src/`) — **hors commentaires** et **hors `<style>` d'un composant** : un
 * commentaire qui la cite n'est pas un emploi (`standards/04` §39), une règle
 * locale qui la surcharge non plus.
 *
 * ⚠️ **Le relevé est INDULGENT, jamais sévère** — et il le dit : n'importe quelle
 * occurrence du mot compte (une table `{ ok: 'badge-green' }`, un
 * `classList.add('x')`, une clé qui porterait le même nom). Une classe dont le
 * nom sert aussi à autre chose peut donc passer pour employée ; l'inverse —
 * crier sur une classe vivante — n'arrive que pour une classe construite par
 * morceaux (`class="kb-{x}"`, `` `kb-${x}` ``), qu'on DÉCLARE alors en exception.
 *
 * Ce que le relevé ne lit pas : `static/` et `docs/` (le manuel embarque ses
 * propres styles ; le CSS du site, haché par Vite, ne l'atteint pas).
 *
 * Auto-test : node scripts/lib-classes-globales.mjs --selftest
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { feuillesCssGlobal } from './lib-css-global.mjs';
import { fichiersSources } from './lib-source-unique.mjs';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

/** Les sources où une classe globale peut être employée. */
export const EXTENSIONS_SOURCES = ['.svelte', '.ts', '.js', '.html'];

/** Blanchit un fragment en gardant sa longueur et ses sauts de ligne. */
const blanchir = (bloc) => bloc.replace(/[^\n]/g, ' ');

/**
 * Les classes DÉFINIES par une feuille, avec la ligne de leur première
 * définition. PURE.
 *
 * Seuls les SÉLECTEURS sont lus — jamais les déclarations : `url(x.png)` ou
 * `content: '.'` ne définissent rien. Les sélecteurs d'attribut sont blanchis
 * (`a[href$=".pdf"]` ne définit pas `.pdf`), comme les commentaires, en gardant
 * les longueurs pour que les numéros de ligne restent justes. On descend dans
 * les `@media` et `@supports` : une classe qui n'existe qu'en responsive reste
 * une classe définie.
 *
 * @returns {Map<string, number>} classe → ligne
 */
export function classesDefinies(css) {
	const src = css.replace(/\/\*[\s\S]*?\*\//g, blanchir);
	const definies = new Map();
	let debut = 0;
	let profondeurRegle = 0;
	for (let i = 0; i < src.length; i++) {
		const c = src[i];
		if (profondeurRegle > 0) {
			//  Dans les déclarations d'une règle : rien n'y est un sélecteur.
			if (c === '{') profondeurRegle++;
			else if (c === '}') profondeurRegle--;
			if (profondeurRegle === 0) debut = i + 1;
			continue;
		}
		if (c === ';' || c === '}') {
			debut = i + 1;
			continue;
		}
		if (c !== '{') continue;
		const tete = src.slice(debut, i);
		if (tete.trim().startsWith('@')) {
			//  `@media`, `@supports` : on entre lire leurs règles. `@keyframes`
			//  aussi — `from`, `50%` n'y portent aucune classe.
			debut = i + 1;
			continue;
		}
		const selecteur = tete.replace(/\[[^\]]*\]/g, blanchir);
		for (const m of selecteur.matchAll(/\.(-?[A-Za-z_][\w-]*)/g)) {
			if (definies.has(m[1])) continue;
			const position = debut + m.index;
			definies.set(m[1], src.slice(0, position).split('\n').length);
		}
		profondeurRegle = 1;
	}
	return definies;
}

/**
 * Les mots d'une source qui peuvent nommer une classe, hors commentaires et
 * hors `<style>` d'un composant. PURE.
 */
export function motsEmployes(source) {
	const code = neutraliserCommentaires(source).replace(/<style[\s\S]*?<\/style>/g, ' ');
	return new Set(code.split(/[^\w-]+/).filter(Boolean));
}

/**
 * Le relevé, sans entrée ni sortie. PURE.
 *
 * @param {{ fichier: string, css: string }[]} feuilles
 * @param {Record<string, string>} sources  chemin → texte
 * @param {Record<string, string>} exceptions  classe → raison ; doivent servir
 * @param {string} temoin  une classe qu'on SAIT employée : si elle ne l'est
 *        pas, la lecture est cassée et le relevé ne conclut pas
 */
export function releveClassesGlobales(feuilles, sources, exceptions = {}, temoin = null) {
	const definies = new Map();
	for (const { fichier, css } of feuilles) {
		for (const [classe, ligne] of classesDefinies(css)) {
			if (!definies.has(classe)) definies.set(classe, { fichier, ligne });
		}
	}
	const employes = new Set();
	for (const texte of Object.values(sources))
		for (const mot of motsEmployes(texte)) employes.add(mot);

	const orphelines = [];
	const servies = new Set();
	for (const [classe, ou] of definies) {
		if (employes.has(classe)) continue;
		if (classe in exceptions) servies.add(classe);
		else orphelines.push({ classe, ...ou });
	}
	const mortes = Object.keys(exceptions)
		.filter((c) => !servies.has(c))
		.map((c) => ({
			classe: c,
			motif: definies.has(c) ? 'est employée' : "n'est plus définie",
		}));

	return {
		feuilles: feuilles.length,
		definies: definies.size,
		lues: Object.keys(sources).length,
		temoinVu: temoin === null || (definies.has(temoin) && employes.has(temoin)),
		orphelines,
		mortes,
	};
}

/**
 * Le relevé sur le dépôt.
 *
 * @param racine chemin de `front/src`
 */
export function releveDuDepot(racine, exceptions, temoin) {
	const sources = {};
	for (const f of fichiersSources(racine, EXTENSIONS_SOURCES)) sources[f] = readFileSync(f, 'utf8');
	return releveClassesGlobales(feuillesCssGlobal(racine), sources, exceptions, temoin);
}

function selftest() {
	const f = (css) => [{ fichier: 'styles/t.css', css }];
	const r = (css, sources, exceptions, temoin) =>
		releveClassesGlobales(f(css), sources, exceptions, temoin);
	const noms = (x) => x.orphelines.map((o) => o.classe);
	const cas = [
		['une classe employée dans le balisage', noms(r('.a{}', { 'x.svelte': '<p class="a">' })), []],
		['une classe que rien n’emploie', noms(r('.a{} .b{}', { 'x.svelte': '<p class="a">' })), ['b']],
		[
			'citée en commentaire seulement : orpheline',
			noms(r('.a{}', { 'x.svelte': '<!-- class="a" -->\n<script>// a\n</script>' })),
			['a'],
		],
		[
			'surchargée dans le <style> d’un composant : orpheline',
			noms(r('.a{}', { 'x.svelte': '<p></p>\n<style>.a { color: red; }</style>' })),
			['a'],
		],
		[
			'posée en JS (classList, table) : employée',
			noms(r('.a{} .b{}', { 'x.ts': "el.classList.add('a'); const T = { ok: 'b' };" })),
			[],
		],
		['class:x — employée', noms(r('.a{}', { 'x.svelte': '<p class:a={v}>' })), []],
		[
			'un préfixe interpolé ne rend pas la classe complète employée',
			noms(r('.kb-item{}', { 'x.svelte': '<p class="kb-{x}">' })),
			['kb-item'],
		],
		[
			'un sélecteur d’attribut ne définit pas de classe',
			r('a[href$=".pdf"] { color: red; }', {}).definies,
			0,
		],
		['un commentaire de feuille ne définit rien', r('/* .vieille {} */ .a{}', {}).definies, 1],
		[
			'les déclarations ne définissent rien (url, valeurs)',
			r('.a { background: url(x.png); margin: .5rem; }', {}).definies,
			1,
		],
		['une classe sous @media est définie', noms(r('@media (x) { .m { a: b; } }', {})), ['m']],
		[
			'les classes composées sont toutes lues',
			noms(r('.a:hover .b, .c > .d:not(.e) {}', { 'x.svelte': 'class="a b c d"' })),
			['e'],
		],
		[
			'la ligne de définition est juste',
			r('/* x\n y */\n.a {}\n\n.b {\n}', { s: 'a' }).orphelines[0].ligne,
			5,
		],
		[
			'une exception qui sert',
			r('.a{}', { s: '' }, { a: 'raison' }).mortes.length +
				r('.a{}', { s: '' }, { a: 'raison' }).orphelines.length,
			0,
		],
		[
			'une exception devenue employée se signale',
			r('.a{}', { s: 'a' }, { a: 'raison' }).mortes,
			[{ classe: 'a', motif: 'est employée' }],
		],
		[
			'une exception qui n’est plus définie se signale',
			r('.b{}', { s: 'b' }, { a: 'raison' }).mortes,
			[{ classe: 'a', motif: "n'est plus définie" }],
		],
		['le témoin employé est vu', r('.btn{}', { s: 'class="btn"' }, {}, 'btn').temoinVu, true],
		[
			'le témoin absent des sources : lecture cassée',
			r('.btn{}', { s: '' }, {}, 'btn').temoinVu,
			false,
		],
		[
			'cas zéro : rien lu se compte zéro',
			[releveClassesGlobales([], {}).definies, releveClassesGlobales([], {}).lues],
			[0, 0],
		],
	];
	let ko = 0;
	for (const [quoi, obtenu, attendu] of cas) {
		const ok = JSON.stringify(obtenu) === JSON.stringify(attendu);
		console.log(
			`${ok ? 'PASS' : 'FAIL'}  ${quoi}${ok ? '' : ` — obtenu ${JSON.stringify(obtenu)}`}`,
		);
		if (!ok) ko = 1;
	}
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	return ko;
}

if (process.argv[1] === fileURLToPath(import.meta.url) && process.argv.includes('--selftest')) {
	process.exit(selftest());
}
