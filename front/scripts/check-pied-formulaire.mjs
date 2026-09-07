#!/usr/bin/env node
/*
 *  **Le pied d'un formulaire passe par `PiedFormulaire`.**
 *
 *  Le motif refusé : une rangée `.form-actions` qui contient un bouton
 *  « Annuler » et un bouton « Enregistrer » écrits à la main.
 *
 *  ## 🔴 Pourquoi ce contrôle (#822, 07/09/2026)
 *
 *  Il était écrit **neuf fois**, à l'identique — les neuf formulaires du
 *  produit. Mêmes classes, même ordre, mêmes libellés au caractère près. Et les
 *  neuf copies avaient déjà divergé sur quatre points :
 *
 *  | | Ce qu'on trouvait |
 *  |---|---|
 *  | l'événement d'annulation | `annule` dans sept, **`annuler`** dans deux |
 *  | `type="button"` sur Annuler | présent dans six, **absent** dans trois |
 *  | `disabled` sur Annuler | **un seul** le posait |
 *  | le bouton principal | `type="submit"`, rien, ou `on:click` |
 *
 *  🔴 La première ligne est celle qui coûte : deux orthographes du même
 *  événement, et **rien ne lève**. Un parent qui écoute `on:annule` sur un
 *  formulaire qui émet `annuler` ne réagit pas — le bouton semble mort, sans
 *  erreur, sans trace. Sept écoutes existaient de ce fait.
 *
 *  ## Ce que le contrôle vise, et ce qu'il laisse passer
 *
 *  ⚠️ Il ne refuse PAS `.form-actions` en général : la classe habille toutes les
 *  rangées d'actions, dont beaucoup n'ont rien d'un pied de formulaire — un
 *  bouton unique, un « Fermer », une paire « Précédent / Suivant ». Les refuser
 *  toutes aurait produit une liste d'exceptions et un contrôle désarmé.
 *
 *  Il cherche la **paire** : « Annuler » ET un libellé d'enregistrement dans la
 *  même rangée. C'est cette forme-là qui a été écrite neuf fois.
 *
 *  Test : node front/scripts/check-pied-formulaire.mjs --selftest
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const RACINE = 'src';
const SOURCE = 'src/lib/components/PiedFormulaire.svelte';

/**
 *  Les écrans autorisés à écrire un pied à la main, avec leur RAISON.
 *
 *  🔴 Vide aujourd'hui, et c'est le but : les neuf copies sont parties d'un
 *  coup. Une entrée ajoutée ici doit dire pourquoi le composant ne convient
 *  pas — pas pourquoi il était plus rapide de recopier.
 */
export const EXCEPTIONS = {};

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (e.endsWith('.svelte')) acc.push(p);
	}
	return acc;
}

/**
 *  Les lignes où s'ouvre une rangée `.form-actions` contenant la PAIRE.
 *
 *  ⚠️ Les commentaires sont neutralisés d'abord : ce fichier-ci décrit le motif
 *  qu'il refuse, et `PiedFormulaire` le cite dans son en-tête. Deux contrôles se
 *  sont déjà pris eux-mêmes le 06/09/2026 (`standards/04` §39).
 */
export function pieds(source) {
	const src = neutraliserCommentaires(source);
	const trouves = [];
	//  La rangée s'étend jusqu'à son `</div>` de fermeture — approximé par les
	//  quinze lignes suivantes, ce qui couvre largement le motif à deux boutons.
	const lignes = src.split('\n');
	for (let i = 0; i < lignes.length; i++) {
		if (!/class="form-actions"/.test(lignes[i])) continue;
		const fenetre = lignes.slice(i, i + 15).join('\n');
		const fin = fenetre.indexOf('</div>');
		const rangee = fin === -1 ? fenetre : fenetre.slice(0, fin);
		if (/>Annuler</.test(rangee) && /Enregistr/.test(rangee)) trouves.push(i + 1);
	}
	return trouves;
}

//  ── Cas zéro ────────────────────────────────────────────────────────────────
function selftest() {
	const cas = [
		//  🔴 Le motif écrit neuf fois — celui qu'on vient de retirer.
		[
			'<div class="form-actions">\n<button type="button" class="btn btn-outline">Annuler</button>\n<button class="btn btn-primary">Enregistrer</button>\n</div>',
			1,
		],
		//  Une rangée d'actions QUI N'EST PAS un pied de formulaire : un seul bouton.
		['<div class="form-actions">\n<button class="btn">Fermer</button>\n</div>', 0],
		//  « Annuler » seul, sans enregistrement en face — un panneau qu'on referme.
		['<div class="form-actions">\n<button class="btn">Annuler</button>\n</div>', 0],
		//  L'appel au composant passe, évidemment.
		['<PiedFormulaire enCours={saving} on:annule />', 0],
		//  🔴 Le contrôle ne doit pas se déclencher sur sa PROPRE prose.
		['<!--  `<div class="form-actions">` avec Annuler et Enregistrer : refusé -->', 0],
	];
	let ko = 0;
	for (const [src, attendu] of cas) {
		const n = pieds(src).length;
		if (n !== attendu) {
			console.error(`  ✗ ${n} au lieu de ${attendu} : ${src.slice(0, 60)}…`);
			ko++;
		}
	}
	if (ko) {
		console.error(`\n✗ Auto-test : ${ko} cas en échec.`);
		process.exit(1);
	}
	console.log('✓ Auto-test : la paire est reconnue, et elle seule.');
}

selftest();

const fautifs = [];
let appels = 0;

for (const p of fichiers(RACINE)) {
	const chemin = p.split('\\').join('/');
	if (chemin === SOURCE) continue;
	const src = readFileSync(p, 'utf8');
	if (/<PiedFormulaire\b/.test(src)) appels++;
	const relatif = chemin.replace(/^src\//, '');
	if (relatif in EXCEPTIONS) continue;
	for (const ligne of pieds(src)) fautifs.push(`${chemin}:${ligne}`);
}

const erreurs = [];

/**
 *  D. Le verbe générique, vérifié LÀ OÙ IL VIT depuis #822.
 *
 *  Deux moitiés, et il faut les deux :
 *
 *  1. les valeurs par DÉFAUT de PiedFormulaire sont bien le verbe commun —
 *     sinon la règle serait déplacée dans un fichier qui ne la tient pas ;
 *  2. aucun appelant ne passe un libellé — sinon un écran rétablirait son verbe
 *     métier, et on serait revenu aux six libellés de #396 avec un composant en
 *     plus.
 *
 *  ⚠️ Une prop existe pour être passée, et la refuser peut sembler
 *  contradictoire. Elle ne l'est pas : elle sert au jour où un formulaire aura
 *  une raison, et ce jour-là la raison s'écrira dans EXCEPTIONS. C'est le même
 *  arbitrage que partout ici — une exception réelle se déclare, elle ne se prend
 *  pas en silence.
 */
const sourcePied = readFileSync(SOURCE, 'utf-8');
for (const [prop, attendu] of [
	['libelle', 'Enregistrer'],
	['libelleEnCours', 'Enregistrement…'],
	['libelleAnnuler', 'Annuler'],
]) {
	const m = sourcePied.match(new RegExp('export let ' + prop + " = '([^']*)'"));
	if (!m) {
		//  Pas de valeur par defaut : le verbe n'est plus garanti nulle part — ni
		//  par le balisage (c'est une variable), ni par le defaut (il n'y en a plus).
		erreurs.push(
			prop +
				" n'a plus de valeur par défaut dans " +
				SOURCE +
				'.\n      Le verbe générique ne serait alors garanti par rien.',
		);
		continue;
	}
	if (m[1] !== attendu) {
		erreurs.push(
			SOURCE +
				' — ' +
				prop +
				' vaut « ' +
				m[1] +
				' », attendu « ' +
				attendu +
				' ».\n' +
				"      C'est le libellé de DIX-SEPT formulaires : le changer les change tous.",
		);
	}
}
for (const chemin of fichiers(RACINE)) {
	const rel = chemin.split('\\').join('/');
	if (rel === SOURCE || rel.replace(/^src\//, '') in EXCEPTIONS) continue;
	const src = readFileSync(chemin, 'utf-8');
	for (const m of src.matchAll(/<PiedFormulaire\b[^>]*?(libelle(?:EnCours|Annuler)?)=/g)) {
		erreurs.push(
			rel +
				' — passe ' +
				m[1] +
				' à PiedFormulaire.\n' +
				'      Le verbe est GÉNÉRIQUE partout (#396) : sept formulaires portaient six\n' +
				"      libellés différents, aucun faux, l'ensemble sans logique.",
		);
	}
}

if (fautifs.length || erreurs.length) {
	for (const e of erreurs) console.error('\n✗ ' + e);
	console.error(`\n✗ ${fautifs.length} pied(s) de formulaire écrit(s) à la main :\n`);
	for (const e of fautifs) console.error(`  ${e}`);
	console.error(
		'\n  Ce pied était écrit NEUF fois, et les neuf copies avaient divergé —\n' +
			'  deux orthographes du même événement (`annule` / `annuler`), trois\n' +
			'  boutons « Annuler » sans `type="button"`, un seul figé pendant\n' +
			"  l'enregistrement.\n" +
			'  → `<PiedFormulaire enCours={…} on:annule />` — voir son en-tête pour\n' +
			"    `soumission={false}` quand le formulaire n'a pas de `<form>`.\n",
	);
	process.exit(1);
}

//  Cas zéro du RELEVÉ : si plus personne n'appelle le composant, le contrôle
//  serait vert en ne mesurant plus rien.
if (appels < 5) {
	console.error(
		`\n✗ Seulement ${appels} appel(s) à \`PiedFormulaire\` — il y en avait neuf.\n` +
			"  Un contrôle vert sur un composant que plus personne n'emploie ne mesure\n" +
			'  rien : soit les formulaires ont disparu, soit ils ont cessé de passer par\n' +
			'  lui sans écrire le motif que ce contrôle sait reconnaître.\n',
	);
	process.exit(1);
}

console.log(`✓ ${appels} formulaire(s) passent par \`PiedFormulaire\` — aucun pied à la main.`);
