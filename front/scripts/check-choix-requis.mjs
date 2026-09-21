#!/usr/bin/env node
/**
 * Garde-fou : une catégorie d'affaire ne se PRÉSÉLECTIONNE pas.
 *
 * ## 🔴 Le défaut, signalé à l'écran le 21/09/2026
 *
 * > « Catégorie : par défaut => Aucune catégorie de sélectionner (Actuellement :
 * >   Panne) »
 *
 * Le formulaire ouvrait sur « 🛠️ Panne » cochée. Enregistrer sans y toucher
 * classait donc l'affaire en panne — et la catégorie ne décore pas une carte :
 * c'est elle qui décide **de qui traite**, du circuit de suivi, et pour
 * « Étude & travaux » de l'entrée au tableau du conseil. Un défaut qui engage
 * quelqu'un d'autre n'est pas un défaut, c'est une réponse qu'on n'a pas
 * donnée et que personne ne sait manquante.
 *
 * ⚠️ Le champ est déclaré **requis** à l'écran (astérisque) depuis toujours :
 * on exigeait un choix tout en en posant un. L'astérisque ne pouvait donc
 * jamais se déclencher.
 *
 * ## Ce qui est vérifié
 *
 * Aucune **initialisation** d'une variable à une valeur de `CATEGORIES_TICKET`
 * dans un `.svelte` : ni `= 'panne'`, ni `?? 'panne'`, ni
 * `export let categorie = 'panne'`.
 *
 * 🔴 **La liste des catégories n'est pas écrite ici** : elle se lit dans
 * `src/lib/tickets-categories.ts`, où `CATEGORIES_TICKET` la déclare. Une liste recopiée
 * diverge à la première catégorie ajoutée — et c'est celle-là, la nouvelle,
 * qu'on présélectionnerait sans que rien ne le refuse.
 *
 * ⚠️ Une **comparaison** (`categorie === 'etude_travaux'`) n'est pas visée, et
 * c'est voulu : lire la catégorie pour en tirer une conséquence est le travail
 * normal de l'écran. Seule l'affectation d'une valeur de départ est refusée.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..');
const SOURCE_CATEGORIES = join(RACINE, 'src/lib/tickets-categories.ts');

/** Les valeurs déclarées par `CATEGORIES_TICKET`, lues à la source. */
function categories() {
	const texte = readFileSync(SOURCE_CATEGORIES, 'utf8');
	const debut = texte.indexOf('CATEGORIES_TICKET');
	if (debut < 0) throw new Error(`CATEGORIES_TICKET introuvable dans ${SOURCE_CATEGORIES}`);
	const valeurs = [...texte.slice(debut).matchAll(/^\s*value: '([a-z_]+)'/gm)].map((m) => m[1]);
	if (!valeurs.length) throw new Error('Aucune catégorie lue : le motif de lecture a dérivé.');
	return valeurs;
}

/**  L'initialisation, et elle seule. `=` ou `??` suivis du littéral — jamais
 *   `===`, `!==` ni `==`, qui sont des lectures. */
function motif(valeurs) {
	return new RegExp(`(?<![=!<>])= *'(?:${valeurs.join('|')})'|[?][?] *'(?:${valeurs.join('|')})'`);
}

function fichiersSvelte(dossier) {
	const sortie = [];
	for (const nom of readdirSync(dossier)) {
		const chemin = join(dossier, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...fichiersSvelte(chemin));
		else if (nom.endsWith('.svelte')) sortie.push(chemin);
	}
	return sortie;
}

if (process.argv.includes('--selftest')) {
	//  🔴 Le contrôle se prouve sur le cas fautif AVANT de servir : un motif trop
	//  étroit rend un vert qui ne veut rien dire (socle 04 §2).
	const m = motif(categories());
	const fautifs = [
		"\tlet categorie = 'panne';",
		"\texport let categorie = 'panne';",
		"\tlet categorie = ticket?.categorie ?? 'panne';",
	];
	const licites = [
		"\tlet categorie = '';",
		"\tlet categorie = ticket?.categorie ?? '';",
		"\t{#if categorie === 'etude_travaux'}",
		"\tif (categorie !== 'sinistre') return;",
	];
	const rates = [
		...fautifs.filter((l) => !m.test(l)).map((l) => `NON REFUSÉ : ${l.trim()}`),
		...licites.filter((l) => m.test(l)).map((l) => `REFUSÉ À TORT : ${l.trim()}`),
	];
	if (rates.length) {
		console.error('✗ Autotest du garde-fou :\n   ' + rates.join('\n   '));
		process.exit(1);
	}
	console.log(
		`✓ Autotest : ${fautifs.length} cas fautif(s) refusé(s), ${licites.length} licite(s) laissé(s) passer.`,
	);
	process.exit(0);
}

const valeurs = categories();
const m = motif(valeurs);
const ecarts = [];
for (const fichier of fichiersSvelte(join(RACINE, 'src'))) {
	readFileSync(fichier, 'utf8')
		.split(/\r?\n/)
		.forEach((ligne, i) => {
			if (m.test(ligne))
				ecarts.push(`${fichier.slice(RACINE.length + 1)}:${i + 1} — ${ligne.trim()}`);
		});
}

if (ecarts.length) {
	console.error('\n✗ Catégorie d’affaire présélectionnée :\n');
	for (const e of ecarts) console.error(`   ${e}`);
	console.error(
		'\n  La catégorie décide de QUI traite : la poser d’office engage quelqu’un' +
			"\n  d’autre à la place de l’auteur. Initialiser à `''`, et laisser le" +
			'\n  contrôle de saisie exiger le choix (21/09/2026, demandé à l’écran).\n',
	);
	process.exit(1);
}

console.log(
	`✓ Catégorie : aucune des ${valeurs.length} catégories déclarées n’est présélectionnée dans un écran.`,
);
