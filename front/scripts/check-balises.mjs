/**
 * Garde-fou — **une balise ouvrante fermée trop tôt**.
 *
 * ## L'incident (18/08/2026, deux fois dans la même journée)
 *
 * Une réécriture a inséré le `>` d'une balise **au milieu** de sa liste
 * d'attributs. Les attributs restants sont alors sortis du balisage et se sont
 * affichés **en texte brut**, à l'écran, en production :
 *
 *     class:history-item=false class:expanded class:urgent=false >
 *     Fuite provenant du parking public – suspicion appartement B4 RDC
 *
 * 🔴 **Aucun contrôle ne l'a vu.** `svelte-check` compile sans broncher : un
 * `class:x={…}` après le `>` est du **texte**, et du texte est valide. Le build
 * passe, les types passent, les tests passent — et la page affiche du code.
 *
 * C'est la définition d'un angle mort : l'outillage vérifie que le fichier est
 * *correct*, jamais qu'il dit ce qu'on voulait. Seul l'œil a rattrapé, et il a
 * fallu que l'utilisateur regarde la bonne carte.
 *
 * ## Ce que ce contrôle cherche
 *
 * La signature est nette et sans ambiguïté : une ligne qui **termine une balise**
 * (`>` final, hors `/>` et hors balise fermante) immédiatement suivie d'une ligne
 * qui **commence par un attribut** (`class:`, `on:`, `role=`, `aria-…`, `style=`,
 * `id=`, `bind:`, `{...`). Un attribut ne commence jamais une ligne de contenu.
 *
 * ⚠️ Volontairement étroit. Un contrôle large sur du balisage produit des faux
 * positifs, et un contrôle qu'on apprend à ignorer ne garde plus rien
 * (`standards/04`). Celui-ci ne connaît qu'un défaut — celui qui est passé.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');

/** Ce par quoi une ligne d'ATTRIBUT peut commencer, et jamais une ligne de contenu. */
const DEBUT_ATTRIBUT = /^\s*(class:|on:|bind:|use:|transition:|role=|aria-[\w-]+=|style=|id=|tabindex=|\{\.\.\.)/;

/** Une ligne qui ferme une balise ouvrante : se termine par `>` sans être `/>`. */
const FIN_DE_BALISE = /[^/\s]>\s*$/;

function svelte(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...svelte(chemin));
		else if (nom.endsWith('.svelte')) sortie.push(chemin);
	}
	return sortie;
}

const fichiers = svelte(RACINE);

//  Cas zéro : un contrôle qui n'a rien lu ne conclut pas au vert
//  (`standards/04-fiabilite-des-controles.md` §2).
if (fichiers.length === 0) {
	console.error("✗ Cas zéro : aucun composant analysé — l'arborescence a changé.");
	console.error("Ne pas lire ceci comme un succès.");
	process.exit(1);
}

const erreurs = [];
let lignesLues = 0;

for (const chemin of fichiers) {
	const lignes = readFileSync(chemin, 'utf8').split(/\r?\n/);
	lignesLues += lignes.length;
	for (let i = 0; i < lignes.length - 1; i++) {
		const ligne = lignes[i];
		//  On ignore les commentaires et les balises fermantes.
		if (/^\s*(<!--|-->|<\/)/.test(ligne)) continue;
		if (!FIN_DE_BALISE.test(ligne)) continue;

		//  La ligne suivante non vide.
		let j = i + 1;
		while (j < lignes.length && lignes[j].trim() === '') j++;
		if (j >= lignes.length) continue;

		if (DEBUT_ATTRIBUT.test(lignes[j])) {
			erreurs.push(
				`${relative(RACINE, chemin)}:${j + 1} — « ${lignes[j].trim()} » suit une balise ` +
					`déjà fermée (ligne ${i + 1}). Cet attribut sera affiché EN TEXTE à l'écran.`,
			);
		}
	}
}

if (erreurs.length) {
	console.error('✗ Balise ouvrante fermée trop tôt — les attributs suivants partiront en texte brut :\n');
	for (const e of erreurs) console.error(`  • ${e}`);
	console.error(
		"\n⚠️ `svelte-check` ne voit rien : un attribut après le `>` est du texte, et du\n" +
			"texte est valide. Le build passe, la page affiche du code. Constaté en\n" +
			'production le 18/08/2026, sur deux cartes.\n',
	);
	process.exit(1);
}

console.log(
	`✓ Balises : ${fichiers.length} composants, ${lignesLues} lignes — aucune balise ouvrante fermée avant ses attributs.`,
);
