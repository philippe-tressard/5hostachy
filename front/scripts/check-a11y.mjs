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
 * Usage : npm run lint:a11y
 */
import { avertissements, lignesDuRapport } from './lib-svelte-check.mjs';

/**
 * Les avertissements d'accessibilité ENCORE présents, chacun avec sa raison.
 *
 * Clé : `src/chemin.svelte::code`. ⚠️ Le chemin, pas la ligne : une ligne bouge à
 * chaque édition, et une exception qui pointe à côté ne protège plus rien.
 */
const EXCEPTIONS = {
	'src/routes/(app)/tableau-de-bord/+page.svelte::a11y_no_noninteractive_element_to_interactive_role':
		'la carte d’urgence est un `<fieldset>` porteur de `role="link"` — un élément non ' +
		'interactif ne peut pas prendre un rôle interactif. Le remède n’est PAS un attribut : ' +
		'il faut remplacer `<fieldset>`/`<legend>` par un `<div>` et une étiquette positionnée, ' +
		'car la légende chevauche la bordure, ce que seul `<legend>` fait nativement. Le rendu ' +
		'se REFAIT, donc se constate à l’écran (#561).',
};

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
			perimees.map((c) => `  ${c}\n      « ${EXCEPTIONS[c]} »`).join('\n') +
			'\n\n  L’écran est devenu conforme. Retirer l’entrée — une exception reconduite\n' +
			'  « au cas où » masque le prochain défaut au même endroit.\n',
	);
	process.exit(1);
}

if (fautes.length) {
	console.error(
		`\n✗ lint:a11y — ${fautes.length} avertissement(s) d’accessibilité non déclaré(s) :\n\n  ` +
			fautes.join('\n\n  ') +
			'\n\n  Les trois cas, et ils ne se traitent PAS pareil (ux-patterns §3) :\n' +
			'    • un vrai geste (déplier, sélectionner) → `role="button"` + `tabindex="0"` + `on:keydown`\n' +
			'    • un `stopPropagation` sans action → `role="presentation"` : il n’y a RIEN à activer\n' +
			'    • un fond de modale → rien à faire : `Échap` ferme, et un `tabindex` y serait une régression\n' +
			'\n  Une correction en bloc casserait ce qui marche. Une exception réelle se\n' +
			'  déclare dans EXCEPTIONS, avec sa raison.\n',
	);
	process.exit(1);
}

console.log(
	`✓ lint:a11y — aucun avertissement d’accessibilité hors des ${Object.keys(EXCEPTIONS).length} ` +
		'exception(s) nommée(s).',
);
