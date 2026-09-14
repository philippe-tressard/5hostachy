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
/**
 *  🔴 `900` A REJOINT L'ÉCHELLE le 12/09/2026, et c'est un CONSTAT, pas un
 *  assouplissement : la valeur était employée **quatre fois, pour une seule et
 *  même intention** — un contenu à plusieurs colonnes n'a plus la place d'en
 *  tenir autant.
 *
 *      ecrans.css     .imp-edit-grid    3+ colonnes → 2
 *      ecrans.css     .report-grid-2    2 → 1
 *      composants.css .kanban           colonnes → empilé
 *      OngletAnnoncesHall .ah-layout    2 → 1
 *
 *  ⚠️ Ce n'est pas la frontière mobile (767) : à 800 px on est sur un écran de
 *  bureau, avec un menu de bureau, et une grille à trois colonnes y est déjà
 *  trop serrée. Quatre fichiers l'avaient trouvée séparément — une valeur que
 *  personne n'a copiée et que tout le monde retrouve est une frontière réelle.
 *
 *  ⚠️ Et c'est la limite de ce raisonnement : il ne vaut QUE parce que les
 *  quatre usages disent la même chose. `640` est employé trois fois lui aussi,
 *  mais pour des ajustements sans rapport entre eux (un padding, une taille de
 *  vignette, une marge) — il reste une dette, suivie en #839.
 */
const ECHELLE = [480, 767, 768, 900, 1024];

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
	//  🔴 VIDE depuis le 14/09/2026 — les neuf dernières sont parties d'un coup,
	//  et la raison mérite d'être écrite, parce qu'elle explique aussi pourquoi
	//  elles avaient attendu.
	//
	//  Le ticket #839 les tenait pour « à trancher devant l'écran », et ce
	//  n'était vrai que de la question mal posée. Prise une par une, chaque
	//  largeur demandait « 520 ou 480 ? », « 640 ou 767 ? » — un arbitrage de
	//  pixels qu'on ne peut pas rendre sans voir. Prises ensemble, les neuf
	//  disaient la MÊME chose : passer en forme mobile. Grille à une colonne,
	//  enroulement d'une rangée, frise mise en colonne, espacement et vignette
	//  resserrés — c'est une seule intention, écrite avec cinq valeurs.
	//
	//  Or cette intention a déjà sa largeur DÉCLARÉE : `767`, celle du menu, de
	//  la grille et de la typographie. La question n'était donc pas « quelle
	//  largeur ? » mais « de quelle intention s'agit-il ? », et celle-là se lit
	//  dans le bloc, pas à l'écran.
	//
	//  ⚠️ Le sens du déplacement est ce qui rend le geste sûr sans voir : toutes
	//  montaient vers 767, donc la forme mobile s'applique sur une plage PLUS
	//  LARGE, jamais plus étroite. Rien de ce qui tenait hier ne cesse de tenir ;
	//  ce qui change est la bande 521-767, où l'écran était en bureau pendant que
	//  le reste du site était déjà en mobile. C'était précisément le défaut.
	//
	//  ⚠️ Ne rien remettre ici sans un motif qui dit ce que la largeur VEUT — pas
	//  « la mise en page casse à 640 », mais « ce bloc bascule en mobile » ou
	//  « ce tableau ne tient plus ». Une dette formulée en pixels ne se solde
	//  jamais : elle n'a pas de critère de sortie.
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
		//  Deux largeurs dans un même fichier : les deux comptent — et seule
		//  celle qui est HORS échelle est relevée. `900` y est entré le 12/09.
		['@media (max-width: 600px){}\n@media (max-width: 900px){}', [600]],
		//  🔴 Ce cas a ÉCHOUÉ au moment d'ajouter 900 à l'échelle, et c'était le
		//  bon comportement : l'auto-test a refusé que le contrôle change d'avis
		//  sans qu'on le dise. Un garde-fou qui suit silencieusement sa propre
		//  configuration ne garde plus rien.
		['@media (max-width: 900px){}', []],
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
const tous = fichiers(RACINE);

//  🔴 CAS ZÉRO — ajouté le 14/09/2026 en vidant DETTES, et c'est le moment où il
//  devenait indispensable : tant que la liste portait neuf entrées, une lecture à
//  zéro fichier échouait sur « ces dettes ne servent plus ». Ce filet-là disparaît
//  avec la dernière dette — le contrôle aurait alors annoncé « échelle respectée »
//  sans avoir ouvert un seul fichier (`standards/04` §2).
if (tous.length < 100) {
	console.error(`✗ Cas zéro : ${tous.length} fichier(s) analysé(s) — le relevé est cassé.`);
	process.exit(1);
}

for (const p of tous) {
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
		`${tous.length} fichier(s), ${Object.keys(DETTES).length} dette(s) déclarée(s).`,
);
