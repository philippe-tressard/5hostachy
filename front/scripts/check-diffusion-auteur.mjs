#!/usr/bin/env node
/**
 * Garde-fou : une case de Diffusion LIÉE doit être ENVOYÉE.
 *
 * ## 🔴 Le piège, rencontré deux fois le 31/08/2026
 *
 * Le matin, `demanderApercu` a été fourni à deux écrans sans que l'interception
 * le soit : tout avait l'air branché, et le message partait sans aperçu.
 * L'utilisateur l'a découvert **en recevant le mail**.
 *
 * La quatrième case de la Diffusion — « M'envoyer une copie » — a exactement la
 * même forme : un écran peut la lier (`bind:auteur={…}`) et ne jamais mettre
 * `envoyer_auteur` dans ce qu'il envoie. La case s'affiche, se coche, et ne fait
 * rien. Aucun contrôle existant ne le voit : `svelte-check` est vert, l'API est
 * correcte, et le seul symptôme est une copie qui n'arrive pas — c'est-à-dire
 * une absence, qui ne se remarque pas.
 *
 * ## Ce qui est vérifié
 *
 * Tout fichier qui lie `auteur` doit citer `envoyer_auteur` — dans sa charge
 * utile, ou en le passant à un composant qui l'enverra.
 *
 * ⚠️ **L'inverse n'est PAS vérifié.** Un écran peut légitimement envoyer
 * `envoyer_auteur` sans lier la case : c'est le cas d'un relais qui reçoit la
 * valeur en propriété. Exiger les deux ferait crier sur du légitime, et un
 * contrôle qui crie sur du légitime finit désarmé (leçon de C16).
 *
 * Usage : npm run lint:diffusion-auteur
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

import { neutraliserCommentaires as sansCommentaires } from './lib-commentaires.mjs';

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..');
const SOURCE = join(RACINE, 'src');

/**
 * Les composants qui PORTENT la case ou la relaient sans rien envoyer.
 *
 * `CanauxNotification` la déclare ; `SectionDiffusion` et `ChampsCommuns` la
 * transmettent. Aucun des trois ne compose de charge utile — c'est l'écran qui
 * sait ce qu'il envoie, et à qui.
 */
const RELAIS = [
	'lib/components/CanauxNotification.svelte',
	'lib/components/SectionDiffusion.svelte',
	'lib/components/ChampsCommuns.svelte',
];

function fichiers(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...fichiers(chemin));
		else if (nom.endsWith('.svelte')) sortie.push(chemin);
	}
	return sortie;
}

const tous = fichiers(SOURCE);
//  Cas zéro : sans fichiers lus, « aucun écart » ne veut rien dire.
if (tous.length < 50) {
	console.error(
		`\n✗ Cas zéro : ${tous.length} fichier(s) analysé(s), au moins 50 attendus —\n` +
			'  le parcours ne correspond plus à `src/`.\n',
	);
	process.exit(1);
}

const lient = [];
const fautifs = [];
for (const chemin of tous) {
	const rel = relative(SOURCE, chemin).split(sep).join('/');
	if (RELAIS.includes(rel)) continue;
	const source = sansCommentaires(readFileSync(chemin, 'utf8'));
	if (!/bind:auteur\b/.test(source)) continue;
	lient.push(rel);
	if (!/envoyer_auteur/.test(source)) {
		fautifs.push(rel);
	}
}

//  🔴 Le relevé légitime est VIDE : il ne peut pas distinguer « rien trouvé » de
//  « rien lu ». Le témoin est le nombre d'écrans qui lient réellement la case.
if (lient.length === 0) {
	console.error(
		'\n✗ Cas zéro : aucun écran ne lie `bind:auteur`. Soit la propriété a été\n' +
			'  renommée, soit plus personne n’offre la copie — ne pas lire ceci comme\n' +
			'  un succès.\n',
	);
	process.exit(1);
}

if (fautifs.length) {
	console.error('\n✗ Case « M’envoyer une copie » liée mais JAMAIS envoyée :\n');
	for (const f of fautifs) console.error(`   ${f}`);
	console.error(
		'\n  🔴 La case s’affiche, se coche, et ne fait rien. Aucun autre contrôle ne' +
			'\n  le voit : svelte-check est vert, l’API est correcte, et le seul symptôme' +
			'\n  est une copie qui n’arrive pas — une absence, qui ne se remarque pas.' +
			'\n\n  Ajouter `envoyer_auteur` à la charge utile de cet écran.\n',
	);
	process.exit(1);
}

console.log(
	`✓ Diffusion : ${lient.length} écran(s) lient « M’envoyer une copie », et tous ` +
		`l’envoient (${tous.length} composants vérifiés).`,
);
