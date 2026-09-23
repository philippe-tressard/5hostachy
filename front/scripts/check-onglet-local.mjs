#!/usr/bin/env node
/**
 * Garde-fou : un « onglet » `.tab-btn` ne se rend et ne se style que par
 * `Onglet` et `BarreOnglets`.
 *
 * ## 🔴 Le défaut, signalé à l'écran le 23/09/2026 (#1160)
 *
 * > « Cette section “Au nom de” n'est pas conforme : les boutons ont un design
 * >   différent de ceux de Périmètre ou Suivi (angles moins arrondis), et un
 * >   cadre entoure ces boutons. »
 *
 * `ChampSaisiPour` rendait trois `<button class="tab-btn">` et les restylait
 * localement (« ces onglets-ci sont ENCADRÉS ») : une variante que la charte ne
 * déclarait pas, pour un choix que `ChoixPastilles` sait faire — avec son groupe
 * accessible, que les trois boutons n'avaient pas.
 *
 * ## Ce qui est vérifié
 *
 * Dans tout `.svelte` autre que les deux composants d'onglets :
 *   - aucun `class="tab-btn"` dans le balisage ;
 *   - aucune règle CSS dont le sélecteur commence par `.tab-btn`.
 *
 * Un onglet de page passe par `Onglet`/`BarreOnglets` ; un choix dans un
 * formulaire passe par `ChoixPastilles`. Les commentaires qui NOMMENT la
 * classe ne sont pas visés.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, basename } from 'node:path';
import { fileURLToPath } from 'node:url';

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..');

/** Les seuls porteurs légitimes — chacun avec sa raison. */
const PORTEURS = new Set([
	'Onglet.svelte', //  rend l'onglet
	'BarreOnglets.svelte', //  borne son style à la rangée (`:global()` imbriqué)
]);

const BALISAGE = /class="[^"]*\btab-btn\b/;
const REGLE = /^\s*\.tab-btn\b/;

const fautive = (ligne) => BALISAGE.test(ligne) || REGLE.test(ligne);

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
	//  Le contrôle se prouve sur le cas fautif AVANT de servir (socle 04 §2).
	const fautifs = [
		'\t\t\t\tclass="tab-btn"',
		'<button type="button" class="tab-btn">',
		'\t.tab-btn {',
		'\t.tab-btn.active {',
	];
	const licites = [
		'\t/*  `.tabs` et `.tab-btn` restent dans `app.css` */',
		'<Onglet actif={x} />',
		'\t.tabs :global(.tab-btn) {',
		'<ChoixPastilles options={o} bind:valeur={v} />',
	];
	const rates = [
		...fautifs.filter((l) => !fautive(l)).map((l) => `NON REFUSÉ : ${l.trim()}`),
		...licites.filter((l) => fautive(l)).map((l) => `REFUSÉ À TORT : ${l.trim()}`),
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

const fichiers = fichiersSvelte(join(RACINE, 'src'));
//  Cas zéro : un parcours qui ne trouve rien ne prouve rien (socle 04 §2).
if (fichiers.length < 100) {
	console.error(`✗ Seulement ${fichiers.length} fichier(s) .svelte lus : le parcours a dérivé.`);
	process.exit(1);
}
const ecarts = [];
const vus = new Set();
for (const fichier of fichiers) {
	const nom = basename(fichier);
	const lignes = readFileSync(fichier, 'utf8').split(/\r?\n/);
	if (PORTEURS.has(nom)) {
		if (lignes.some((l) => l.includes('tab-btn'))) vus.add(nom);
		continue;
	}
	lignes.forEach((ligne, i) => {
		if (fautive(ligne))
			ecarts.push(`${fichier.slice(RACINE.length + 1)}:${i + 1} — ${ligne.trim()}`);
	});
}

//  Une exception qui ne sert plus se retire : elle ne doit pas survivre à son objet.
const inutiles = [...PORTEURS].filter((p) => !vus.has(p));
if (inutiles.length) {
	console.error(`✗ Porteur déclaré qui ne porte plus \`.tab-btn\` : ${inutiles.join(', ')}.`);
	process.exit(1);
}

if (ecarts.length) {
	console.error('\n✗ Onglet `.tab-btn` rendu ou stylé hors des composants d’onglets :\n');
	for (const e of ecarts) console.error(`   ${e}`);
	console.error(
		'\n  Un onglet de page passe par `Onglet`/`BarreOnglets` ; un choix dans un' +
			'\n  formulaire passe par `ChoixPastilles` (#1160, signalé à l’écran le 23/09/2026).\n',
	);
	process.exit(1);
}

console.log(`✓ Onglets : \`.tab-btn\` n’est porté que par ${[...PORTEURS].join(' et ')}.`);
