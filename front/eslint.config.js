// Configuration eslint « à plat » — posée le 17/08/2026 (#419).
//
// Avant ce fichier, `eslint .` ne démarrait pas du tout :
//
//     ESLint couldn't find an eslint.config.(js|mjs|cjs) file.
//
// eslint et @typescript-eslint étaient installés, tenus à jour par Dependabot, et
// n'avaient jamais analysé une seule ligne du dépôt. Un linter installé, à jour et
// inerte ressemble à un linter — c'est tout le sujet du ticket.
//
// Jeu de règles volontairement MINIMAL : les presets « recommended », rien de plus.
// Les règles de style ne se négocient pas dans le lot qui met le linter en place ;
// on mesure d'abord la dette, on la traite ensuite.
//
// ⚠️ Ce fichier ne câble rien dans la CI. Tant que le relevé n'est pas vert,
// `npm run lint` reste hors du job `build-frontend` (point 4 de #419). Et il n'y a
// pas de `--max-warnings <chiffre>` ici : un seuil posé pour obtenir du vert est un
// contrôle qui ment (`standards/04-fiabilite-des-controles.md`).

import js from '@eslint/js';
import ts from 'typescript-eslint';
import svelte from 'eslint-plugin-svelte';
import globals from 'globals';
import { defineConfig } from 'eslint/config';
import svelteConfig from './svelte.config.js';

export default defineConfig(
	// ── Périmètre : ce qui est écrit à la main, jamais ce qui est produit ────────
	// `build/` et `.svelte-kit/` sont des SORTIES : les analyser triple le relevé et
	// noie les vrais défauts (c'est ce qui était arrivé à prettier, #410 : 734
	// fichiers sur 785 venaient des répertoires de build). `static/` porte les
	// manuels et des ressources tierces, non écrites ici.
	{
		ignores: ['build/', '.svelte-kit/', 'node_modules/', 'static/']
	},

	// ── Sources TypeScript et JavaScript ────────────────────────────────────────
	{
		files: ['src/**/*.{js,ts}', 'scripts/**/*.{js,mjs,ts}'],
		extends: [js.configs.recommended, ts.configs.recommended],
		languageOptions: {
			ecmaVersion: 2022,
			sourceType: 'module',
			globals: { ...globals.browser, ...globals.node }
		}
	},

	// ── Scripts de contrôle (`npm run lint:*`) : Node pur, pas de navigateur ─────
	{
		files: ['scripts/**/*.{js,mjs,ts}'],
		languageOptions: {
			globals: { ...globals.node }
		}
	},

	// ── Composants Svelte ───────────────────────────────────────────────────────
	// `svelteConfig` est passé au parseur pour qu'il connaisse les préprocesseurs et
	// les alias de SvelteKit ; sans lui, le TypeScript des balises <script lang="ts">
	// n'est pas compris et le relevé serait faussement vide.
	// `projectService` n'est PAS activé : aucune règle « type-checked » n'est en
	// service ici, et l'activer coûterait le typage complet du projet à chaque
	// exécution sans rien mesurer de plus.
	{
		files: ['src/**/*.svelte', 'src/**/*.svelte.{js,ts}'],
		extends: [js.configs.recommended, ts.configs.recommended, svelte.configs.recommended],
		languageOptions: {
			globals: { ...globals.browser },
			parserOptions: {
				parser: ts.parser,
				extraFileExtensions: ['.svelte'],
				svelteConfig
			}
		},
		rules: {
			// ── `no-unused-vars` : la version TypeScript PLANTE sur les .svelte ────────
			// Avec svelte-eslint-parser 1.8.1 et typescript-eslint 8.67.0 (les deux à
			// jour au 17/08/2026), `@typescript-eslint/no-unused-vars` fait tomber
			// eslint tout entier sur le premier composant analysé :
			//
			//   TypeError: Cannot read properties of undefined (reading 'type')
			//   Rule: "@typescript-eslint/no-unused-vars"
			//
			// La règle de base, elle, fonctionne : elle comprend la portée du template
			// (un composant utilisé seulement dans le balisage n'est PAS signalé) et
			// trouve de vrais morts — imports de composants jamais rendus, fonctions
			// jamais appelées. On l'échange donc plutôt que de renoncer à la détection :
			// une règle désactivée sans remplacement, c'est un contrôle en moins.
			'@typescript-eslint/no-unused-vars': 'off',
			'no-unused-vars': 'error',

			// ── Trois règles inadaptées À CE PROJET, désactivées sur un fait vérifié ───
			// Aucune n'est éteinte pour le confort ni pour faire baisser un compteur :
			// chacune produit 100 % de faux positifs ici, et la condition de sa
			// réactivation est écrite en toutes lettres.
			//
			// `prefer-svelte-reactivity` (49 signalements) conseille SvelteSet/SvelteMap
			// à la place de Set/Map. Ces classes ne servent QU'EN MODE RUNES ; or aucun
			// des 92 composants n'utilise de rune (vérifié le 17/08/2026 : `$state(`,
			// `$derived(`, `$props(` → 0 fichier). La réactivité passe ici par la
			// réassignation de Svelte 4 (`x = x`), que la règle ne sait pas voir.
			// → À réactiver le jour de la migration aux runes.
			'svelte/prefer-svelte-reactivity': 'off',

			// `no-navigation-without-resolve` (95 signalements) exige `resolve()` autour
			// des `href` et des `goto()`. Cela ne sert qu'à une application servie sous
			// un chemin de base ; `svelte.config.js` ne définit AUCUN `paths.base` et le
			// site est servi à la racine.
			// → À réactiver le jour où un `paths.base` apparaît dans `svelte.config.js`.
			'svelte/no-navigation-without-resolve': 'off',

			// `no-irregular-whitespace` (10 signalements) : les 10 sont des U+00A0,
			// espaces INSÉCABLES de typographie française dans du texte affiché —
			// « Ex : », « N° 12 », « 34 m² ». Les retirer abîmerait l'affichage. La règle
			// ignore les chaînes JS par défaut, mais pas le texte d'un template Svelte.
			'no-irregular-whitespace': 'off',

			// NB : `@typescript-eslint/no-unused-expressions` (5 signalements) est
			// VOLONTAIREMENT laissée active. On aurait pu la croire du même tonneau —
			// l'idiome réactif `$: dep, action();` — mais un seul des 5 cas en relève
			// (Nav.svelte:86) ; les 4 autres sont des ternaires employés comme
			// instructions. Elle mesure donc quelque chose de réel : elle reste.

			// ⚠️ DÉSACTIVATION ASSUMÉE, ET ELLE LAISSE UN TROU — à lire avant d'y toucher.
			//
			// `svelte/no-at-html-tags` interdit tout `{@html …}`. Ce projet en compte 61
			// dans 25 fichiers, et ils sont voulus : les contenus riches (descriptions de
			// tickets, corps de notifications) sont assainis par DOMPurify dans
			// `src/lib/sanitize.ts` avant d'être rendus. La règle ne sait pas distinguer
			// `{@html safeHtml(x)}` de `{@html x}` : elle les condamne les deux, donc elle
			// ne mesure pas ce qui compte ici.
			//
			// ⚠️ MAIS il n'existe AUJOURD'HUI aucun garde-fou automatisé qui vérifie que
			// tout `{@html}` passe bien par une fonction d'assainissement : vérifié le
			// 17/08/2026, aucun `npm run lint:*` ni aucun test d'`api/tests/` ne mentionne
			// `safeHtml`. La seule protection est la règle écrite dans `CLAUDE.md`. Cette
			// ligne n'éteint donc pas un contrôle redondant — elle laisse la place vide.
			// Un `lint:html` doit la combler (cf. #419) : c'est le traitement retenu pour
			// le même cas de figure en #410, où `lint:manuels` a remplacé ce que l'ignore
			// prettier faisait disparaître.
			'svelte/no-at-html-tags': 'off'
		}
	}
);
