#!/usr/bin/env node
/**
 *  Les points de rupture viennent d'une ÉCHELLE déclarée (#839, 08/09/2026).
 *
 *  🔴 Le relevé du jour : **douze valeurs pour six intentions**, et aucune
 *  échelle nulle part.
 *
 *      480 ×13   767 ×8   900 ×4   640 ×3   600 ×3   700 ×2
 *      560 ×2    768 ×1   760 ×1   680 ×1   520 ×1   1024 ×1
 *
 *  Le cas net : `760px` (`RangeeCalendrier`) était à **sept pixels** du `767px`
 *  que la feuille globale emploie. Entre 761 et 767, le menu et la mise en page
 *  étaient déjà en mobile pendant que la rangée restait en bureau. Personne ne
 *  peut voir un écart de sept pixels — il se corrige en comptant.
 *
 *  ⚠️ `768` en `min-width` n'est PAS une anomalie : c'est le complément exact de
 *  `max-width: 767px`, les deux côtés de la même frontière.
 *
 *  ## Ce que ce contrôle NE fait pas
 *
 *  Il ne migre rien. Les huit valeurs restantes (520 à 900) répondent peut-être
 *  à des besoins réels — une grille à trois colonnes ne casse pas à la même
 *  largeur qu'un tableau à sept. Les déplacer changerait une mise en page à une
 *  largeur donnée, et cela **se décide devant l'écran**, pas dans un relevé.
 *
 *  Elles sont donc des DETTES nominatives : comptées, suivies en #839, et une
 *  entrée qui ne sert plus fait échouer le contrôle. Ce qui est empêché à partir
 *  d'aujourd'hui, c'est la **treizième**.
 *
 *  Lancer : node scripts/check-points-rupture.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';

const RACINE = 'src';

/**
 *  L'ÉCHELLE — les seules largeurs qu'un écran neuf peut employer.
 *
 *  `480` le petit téléphone · `767`/`768` la frontière mobile ⇄ bureau, celle de
 *  la feuille globale · `1024` le grand écran.
 *
 *  ⚠️ Trois valeurs, pas douze. Une échelle qui reprend tout ce qui existe ne
 *  déclare rien : elle constate.
 */
const ECHELLE = [480, 767, 768, 1024];

/**
 *  Les largeurs encore employées hors de l'échelle, par fichier — avec ce qu'on
 *  en sait. Ce sont des DETTES, pas des dérogations : chacune est un écran dont
 *  la mise en page bascule à une largeur qui n'est celle de personne d'autre.
 *
 *  Suivi : #839. Une entrée qui ne sert plus fait échouer ce contrôle.
 *
 *  🔴 Deux entrées sont parties le 09/09/2026 sans qu'aucun arbitrage soit
 *  nécessaire : leur bloc était VIDE — `@media (max-width: 680px) { }` et
 *  `@media (max-width: 560px) { }`. Le relevé les comptait comme des décisions de
 *  mise en page ; ce n'étaient que des accolades. Une dette qu'on suit sans
 *  l'ouvrir peut n'être rien du tout, et c'est le genre de ligne qui fait paraître
 *  un chantier plus lourd qu'il n'est.
 */
const DETTES = {
	'lib/components/ApercuCarte.svelte': [640],
	'lib/components/ApercuDiffusion.svelte': [700],
	'lib/components/FicheResidence.svelte': [560],
	'lib/components/FluxVignette.svelte': [640],
	'lib/components/OngletAnnoncesHall.svelte': [900],
	'lib/components/OngletImportLots.svelte': [600],
	'lib/components/SectionContratReference.svelte': [520],
	'lib/components/reporting/VueRenouvellementsContrats.svelte': [700],
	'routes/(app)/prestataires/+page.svelte': [600],
	'styles/composants.css': [900],
	'styles/ecrans.css': [600, 900],
	'styles/normes.css': [640],
};

const REQUETE = /@media[^{]*\((?:min|max)-width:\s*(\d+)px\)/g;

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (e.endsWith('.svelte') || e.endsWith('.css')) acc.push(p);
	}
	return acc;
}

/** Les largeurs hors échelle d'une source. */
function horsEchelle(source) {
	const vues = new Set();
	for (const m of source.matchAll(REQUETE)) {
		const px = Number(m[1]);
		if (!ECHELLE.includes(px)) vues.add(px);
	}
	return [...vues].sort((a, b) => a - b);
}

function selftest() {
	const cas = [
		['@media (max-width: 767px) { .a { color: red } }', []],
		['@media (min-width: 768px) { .a { color: red } }', []],
		['@media (max-width: 760px) { .a { color: red } }', [760]],
		//  Deux largeurs dans un même fichier : les deux comptent.
		['@media (max-width: 600px){}\n@media (max-width: 900px){}', [600, 900]],
		//  Une largeur hors d'une requête média ne dit rien de la mise en page.
		['.carte { max-width: 640px; }', []],
	];
	let ko = 0;
	for (const [src, attendu] of cas) {
		const vu = horsEchelle(src);
		if (JSON.stringify(vu) !== JSON.stringify(attendu)) {
			console.error(`  ✗ [${vu}] au lieu de [${attendu}] : ${src.slice(0, 48)}…`);
			ko++;
		}
	}
	if (ko) {
		console.error(`\n✗ Auto-test : ${ko} cas en échec.`);
		process.exit(1);
	}
	console.log('✓ Auto-test : les largeurs hors échelle sont reconnues, et elles seules.');
}

selftest();
if (process.argv.includes('--selftest')) process.exit(0);

const nouveaux = [];
const dettesVues = new Set();

for (const p of fichiers(RACINE)) {
	const chemin = p
		.split(sep)
		.join('/')
		.replace(/^src\//, '');
	const vues = horsEchelle(readFileSync(p, 'utf8'));
	if (!vues.length) continue;
	const admises = DETTES[chemin] ?? [];
	const inconnues = vues.filter((px) => !admises.includes(px));
	if (admises.length) dettesVues.add(chemin);
	if (inconnues.length) nouveaux.push(`${chemin} — ${inconnues.join(', ')}px`);
}

let echec = false;

if (nouveaux.length) {
	echec = true;
	console.error(`\n✗ ${nouveaux.length} point(s) de rupture hors de l’échelle :\n`);
	for (const n of nouveaux) console.error(`  ${n}`);
	console.error(
		`\n  L’échelle est ${ECHELLE.join(' · ')} px. Douze valeurs coexistaient pour six\n` +
			'  intentions, et `760px` était à SEPT pixels du `767px` global : entre 761 et\n' +
			'  767, le menu était en mobile et la rangée en bureau.\n' +
			'  → employer une largeur de l’échelle, ou inscrire la dette dans `DETTES`\n' +
			'    avec son motif, et l’ouvrir dans #839.\n',
	);
}

const perimees = Object.keys(DETTES).filter((f) => !dettesVues.has(f));
if (perimees.length) {
	echec = true;
	console.error('\n✗ Ces dettes ne servent plus — les retirer :\n');
	for (const f of perimees) console.error(`  ${f}`);
	console.error(
		'\n  Le fichier a été mis en conformité ou a disparu. Une dette reconduite\n' +
			'  « au cas où » masquerait la suivante.\n',
	);
}

if (echec) process.exit(1);
console.log(
	`✓ Points de rupture : échelle ${ECHELLE.join(' · ')} px respectée — ` +
		`${Object.keys(DETTES).length} dette(s) déclarée(s), suivies en #839.`,
);
