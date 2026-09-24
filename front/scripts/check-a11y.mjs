/**
 * Garde-fou : les avertissements d'accessibilité de `svelte-check` ne défilent
 * plus — ils sont NOMMÉS, et la liste ne peut que décroître.
 *
 * ## Pourquoi (#561, 28/08/2026)
 *
 * Le job de CI ne regarde que les **erreurs** (`--threshold error`), et à raison :
 * rendre les avertissements bloquants d'un coup aurait rendu le job rouge en
 * permanence, donc désarmé dans la semaine.
 *
 * Mais **un avertissement permanent ne se lit plus** (`standards/04` §18). Ces
 * lignes défilaient à chaque exécution depuis des semaines, et le compte ne
 * bougeait que vers le haut. Quarante-cinq d'entre elles étaient des défauts
 * d'accessibilité — une exigence permanente du projet, écrite dans `CLAUDE.md`,
 * dans `ux-patterns` §3 **et** dans `standards/11`. La règle était écrite à trois
 * endroits ; rien ne l'appliquait.
 *
 * ## Ce qu'il fait, et ce qu'il ne fait pas
 *
 * Il refuse **tout** avertissement `a11y_*` non déclaré. Il ne juge pas : c'est
 * `svelte-check` qui trouve, lui qui empêche d'en ajouter.
 *
 * ⚠️ **Pas de seuil chiffré.** Un « au plus N avertissements » masque tout, y
 * compris ce qu'on ajoutera demain — c'est ce que #419 interdit nommément. Une
 * exception se nomme, avec sa raison, et disparaît quand l'écran est repris.
 *
 * ⚠️ Le tuyau (lancer, décolorer, apparier au fichier) vit dans
 * `lib-svelte-check.mjs`, avec son propre `--selftest` : deux de ces gestes ont
 * déjà coûté un défaut ici, et recopiés ils divergent.
 *
 * ## 🔴 La porte de derrière : `svelte-ignore` (#1045, 24/09/2026)
 *
 * Ce contrôle lit les avertissements de `svelte-check`. Une directive
 * `<!-- svelte-ignore a11y_… -->` les supprime **en amont** : l'avertissement
 * n'est jamais émis, donc jamais lu, donc jamais refusé. Quatre directives le
 * faisaient (`Nav`, `FluxCorps`, `Saisie`) — hors de toute liste, sans raison
 * écrite. Une exception non déclarée n'est pas une exception, c'est un oubli qui
 * ressemble à une décision (CLAUDE.md, règle XSS : même défaut, même remède).
 *
 * Toute directive `svelte-ignore` qui vise un code `a11y` est donc **refusée**,
 * sans liste de tolérance qui lui soit propre. Le cas réellement légitime se
 * déclare dans `EXCEPTIONS` ci-dessous, par `fichier::code` : l'avertissement y
 * reste **émis**, et c'est `svelte-check` qui constate qu'il sert encore. Une
 * liste de directives tolérées ne pourrait vérifier que la présence du
 * commentaire — pas que le défaut qu'il tait existe toujours.
 *
 * Usage : npm run lint:a11y            (auto-test : --selftest)
 */
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { avertissements, lignesDuRapport } from './lib-svelte-check.mjs';

const FRONT = fileURLToPath(new URL('..', import.meta.url));

const TROIS_CAS =
	'  Les trois cas, et ils ne se traitent PAS pareil (ux-patterns §3) :\n' +
	'    • un vrai geste (déplier, sélectionner) → `role="button"` + `tabindex="0"` + `on:keydown`\n' +
	'    • un `stopPropagation` sans action → `role="presentation"` : il n’y a RIEN à activer\n' +
	'    • un fond de modale → `role="presentation"` : `Échap` ferme, un `tabindex` y serait une régression\n';

/**
 * Les avertissements d'accessibilité ENCORE présents, chacun avec sa raison et
 * la date où il a été déclaré.
 *
 * Clé : `src/chemin.svelte::code`. ⚠️ Le chemin, pas la ligne : une ligne bouge à
 * chaque édition, et une exception qui pointe à côté ne protège plus rien.
 */
const EXCEPTIONS = {
	'src/routes/(app)/tableau-de-bord/+page.svelte::a11y_no_noninteractive_element_to_interactive_role':
		{
			depuis: '28/08/2026',
			raison:
				'la carte d’urgence est un `<fieldset>` porteur de `role="link"` — un élément non ' +
				'interactif ne peut pas prendre un rôle interactif. Le remède n’est PAS un attribut : ' +
				'il faut remplacer `<fieldset>`/`<legend>` par un `<div>` et une étiquette positionnée, ' +
				'car la légende chevauche la bordure, ce que seul `<legend>` fait nativement. Le rendu ' +
				'se REFAIT, donc se constate à l’écran (#561).',
		},
};

/**
 * Les directives `svelte-ignore` d'un source qui visent un code d'accessibilité.
 *
 * Fonction PURE, éprouvée par `--selftest`. Elle prend les deux graphies —
 * `a11y_…` (Svelte 5) et `a11y-…` (héritée de Svelte 4, que Svelte 5 accepte
 * encore) — et les deux formes, commentaire HTML ou `//` dans un `<script>`.
 */
export function directivesA11y(source) {
	const trouvees = [];
	source.split(/\r?\n/).forEach((texte, i) => {
		const m = /svelte-ignore\b(.*)$/.exec(texte);
		if (m && /\ba11y[-_]/.test(m[1])) trouvees.push({ ligne: i + 1, texte: texte.trim() });
	});
	return trouvees;
}

/** Une exception sans raison ou sans date n'est pas une décision nommée. */
export function exceptionsMalFormees(exceptions) {
	return Object.entries(exceptions)
		.filter(
			([, e]) =>
				typeof e?.raison !== 'string' ||
				e.raison.trim().length < 20 ||
				!/^\d{2}\/\d{2}\/\d{4}$/.test(e?.depuis ?? ''),
		)
		.map(([cle]) => cle);
}

function fichiersSvelte(dossier) {
	return readdirSync(dossier, { withFileTypes: true }).flatMap((d) => {
		const chemin = join(dossier, d.name);
		if (d.isDirectory()) return fichiersSvelte(chemin);
		return d.name.endsWith('.svelte') ? [chemin] : [];
	});
}

function selftest() {
	let echecs = 0;
	const verifier = (nom, obtenu, attendu) => {
		const ok = obtenu === attendu;
		if (!ok) echecs++;
		console.log(`${ok ? 'PASS' : 'ÉCHEC'}  ${nom} → ${obtenu} (attendu ${attendu})`);
	};
	for (const [nom, source, attendu] of [
		['graphie Svelte 4 (tiret)', '<!-- svelte-ignore a11y-autofocus -->', 1],
		['graphie Svelte 5 (souligné)', '<!-- svelte-ignore a11y_autofocus -->', 1],
		[
			'plusieurs codes sur une ligne : UNE directive',
			'<!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->',
			1,
		],
		['code a11y après un autre code', '<!-- svelte-ignore unused-export-let a11y_label -->', 1],
		['forme `//` dans un script', '\t// svelte-ignore a11y_no_static_element_interactions', 1],
		['deux lignes consécutives', '<!-- svelte-ignore a11y-x -->\n<!-- svelte-ignore a11y-y -->', 2],
		[
			'directive hors accessibilité : pas notre affaire',
			'<!-- svelte-ignore state_referenced_locally -->',
			0,
		],
		['« a11y » dans du texte, sans directive', '<p>a11y_autofocus est un code</p>', 0],
		['cas zéro : source vide', '', 0],
	]) {
		verifier(nom, directivesA11y(source).length, attendu);
	}
	verifier(
		'exception sans date refusée',
		exceptionsMalFormees({ k: { raison: 'une raison assez longue pour compter' } }).length,
		1,
	);
	verifier(
		'exception en chaîne nue (ancienne forme) refusée',
		exceptionsMalFormees({ k: 'une raison assez longue pour compter' }).length,
		1,
	);
	verifier(
		'exception complète acceptée',
		exceptionsMalFormees({
			k: { raison: 'une raison assez longue pour compter', depuis: '24/09/2026' },
		}).length,
		0,
	);
	verifier('les EXCEPTIONS réelles sont bien formées', exceptionsMalFormees(EXCEPTIONS).length, 0);
	console.log(echecs ? `== ${echecs} ÉCHEC(S) ==` : '== TOUS OK ==');
	return echecs ? 1 : 0;
}

if (process.argv.includes('--selftest')) process.exit(selftest());

const malFormees = exceptionsMalFormees(EXCEPTIONS);
if (malFormees.length) {
	console.error(
		"\n✗ lint:a11y — exception(s) sans raison ou sans date (`{ depuis: 'JJ/MM/AAAA', raison }`) :\n\n  " +
			malFormees.join('\n  ') +
			'\n',
	);
	process.exit(1);
}

//  La porte de derrière d'abord : c'est un relevé de fichiers, il ne dépend pas
//  de `svelte-check`. Il est rapporté avec le reste, pas à sa place.
const src = join(FRONT, 'src');
const fichiers = fichiersSvelte(src);
//  🔴 CAS ZÉRO — un répertoire illisible rendrait « aucune directive » sans rien lire.
if (fichiers.length < 50) {
	console.error(
		`\n⚠️  INCONNU — ${fichiers.length} fichier(s) .svelte sous src/ : le relevé n'a rien lu.\n`,
	);
	process.exit(2);
}
const directives = fichiers.flatMap((f) =>
	directivesA11y(readFileSync(f, 'utf8')).map(
		(d) => `${relative(FRONT, f).split('\\').join('/')}:${d.ligne} — ${d.texte}`,
	),
);

if (directives.length) {
	console.error(
		`\n✗ lint:a11y — ${directives.length} directive(s) \`svelte-ignore\` qui taisent l’accessibilité :\n\n  ` +
			directives.join('\n  ') +
			'\n\n  Elles suppriment l’avertissement AVANT que ce contrôle le lise : c’est une\n' +
			'  exception qui ne se déclare nulle part (#1045). Corriger le balisage :\n' +
			TROIS_CAS +
			'\n  Si le défaut est réellement voulu : retirer la directive\n' +
			'  et déclarer `fichier::code` dans EXCEPTIONS, avec sa raison et sa date :\n' +
			'  l’avertissement y reste émis, donc vérifié.\n',
	);
}

const lignes = lignesDuRapport();
const vus = new Set();
const fautes = [];

//  ⚠️ Le marqueur est `Warn:` et NON `a11y_` : le rapport est multiligne, et le
//  code de la règle vit sur la ligne SUIVANTE, dans l'URL de documentation.
//  Chercher `a11y_` directement trouverait la ligne de l'URL — dont la ligne
//  précédente est le message, pas l'emplacement : tous les fichiers seraient
//  rapportés en « ? », vert de forme et muet sur le fond.
for (const a of avertissements(lignes, 'Warn:')) {
	const code = /a11y_[a-z_]+/.exec(lignes[a.indice + 1] ?? '')?.[0];
	if (!code) continue;
	const cle = `${a.fichier}::${code}`;
	if (cle in EXCEPTIONS) {
		vus.add(cle);
		continue;
	}
	fautes.push(`${a.fichier}:${a.ligne} — ${code}\n      ${a.message.slice(0, 150)}`);
}

//  Une exception qui ne sert plus doit disparaître, sinon la liste couvre un
//  écran devenu conforme et masque le prochain vrai défaut au même endroit.
const perimees = Object.keys(EXCEPTIONS).filter((c) => !vus.has(c));
if (perimees.length) {
	console.error(
		'\n✗ lint:a11y — ces exceptions ne servent plus :\n\n' +
			perimees.map((c) => `  ${c}\n      « ${EXCEPTIONS[c].raison} »`).join('\n') +
			'\n\n  L’écran est devenu conforme. Retirer l’entrée — une exception reconduite\n' +
			'  « au cas où » masque le prochain défaut au même endroit.\n',
	);
	process.exit(1);
}

if (fautes.length || directives.length) {
	if (fautes.length)
		console.error(
			`\n✗ lint:a11y — ${fautes.length} avertissement(s) d’accessibilité non déclaré(s) :\n\n  ` +
				fautes.join('\n\n  ') +
				'\n\n' +
				TROIS_CAS +
				'\n  Une correction en bloc casserait ce qui marche. Une exception réelle se\n' +
				'  déclare dans EXCEPTIONS, avec sa raison et sa date.\n',
		);
	process.exit(1);
}

console.log(
	`✓ lint:a11y — aucun avertissement d’accessibilité hors des ${Object.keys(EXCEPTIONS).length} ` +
		'exception(s) nommée(s).',
);
