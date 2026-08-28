/**
 * Garde-fou : le fond d'une modale s'écrit d'UNE seule façon — `Modale`.
 *
 * ## Pourquoi ce contrôle existe (#561, 28/08/2026)
 *
 * `Modale.svelte` a été créé le 28/08/2026 pour porter le fond, le rôle, `Échap`
 * et le verrou de défilement une seule fois. Le lot qui l'a créé a converti **un
 * écran sur dix** : `residence`. Les **dix-neuf autres modales** sont restées
 * écrites à la main dans neuf fichiers, et **seize d'entre elles ne se fermaient
 * toujours qu'à la souris** — c'est-à-dire exactement le défaut que le composant
 * venait corriger.
 *
 * 🔴 La CI était verte. Rien ne rapproche un composant neuf des copies qu'il est
 * censé remplacer : `standards/05-tests-et-garde-fous.md` — *un défaut corrigé
 * sans garde-fou revient*. Ici il n'est même pas revenu, il n'était jamais parti.
 *
 * C'est le motif de la mémoire projet « PR vide : un titre sans code » : le
 * paquet est ajouté, le monolithe reste. Ce contrôle est ce qui manquait pour
 * que « le composant existe » et « le composant est employé » cessent d'être
 * deux choses différentes.
 *
 * ## Ce qui est interdit hors de `Modale.svelte`
 *
 *   1. rendre `class="modal-overlay"` à la main — passer par `<Modale>` ;
 *   2. redéfinir `.modal-overlay`, `.modal` ou `.modal-box` en CSS local — les
 *      trois vivent dans `styles/composants.css`. Les copies avaient divergé :
 *      elles perdaient le `padding` et l'animation du fond, et l'une réduisait
 *      la boîte de 560 à 420 px sans que personne l'ait décidé.
 *
 * Le contrôle s'auto-contrôle : si le composant disparaît, change de contrat ou
 * n'est plus employé, il ÉCHOUE au lieu de conclure au vert
 * (`standards/04-fiabilite-des-controles.md` §2, cas zéro).
 */
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { cssGlobal } from './lib-css-global.mjs';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const COMPOSANT = join(RACINE, 'lib', 'components', 'Modale.svelte');

/**
 * Emplois légitimes du fond hors du composant, avec leur raison.
 *
 * Vide, et c'est l'état voulu : les vingt-six copies ont toutes été converties.
 * Une entrée ajoutée ici doit dire POURQUOI cette modale ne peut pas passer par
 * le composant — et le contrôle la refuse dès qu'elle cesse de servir.
 */
const EXCEPTIONS = {};

/** Retire commentaires et balisage commenté : expliquer la règle ne doit pas l'enfreindre. */
function sansCommentaires(texte) {
	return texte
		.replace(/<!--[\s\S]*?-->/g, '')
		.replace(/\/\*[\s\S]*?\*\//g, '')
		.replace(/(^|[^:'"`\\])\/\/[^\n]*/g, '$1');
}

function fichiers(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...fichiers(chemin));
		else if (nom.endsWith('.svelte')) sortie.push(chemin);
	}
	return sortie;
}

//  ── Auto-contrôle (cas zéro) ────────────────────────────────────────────────
if (!existsSync(COMPOSANT)) {
	console.error(`✗ Cas zéro : ${COMPOSANT} est introuvable — contrôle inopérant.`);
	process.exit(1);
}
const composant = readFileSync(COMPOSANT, 'utf8');
//  `titre` devient l'`aria-label` de la boîte, `fermetureAuFond` porte la
//  décision d'écran qu'`OngletPerimetres` avait raison de prendre. Si l'un des
//  deux disparaît, ce contrôle interdirait des copies sans offrir de remplaçant.
for (const prop of ['titre', 'classeBoite', 'styleBoite', 'fermetureAuFond']) {
	if (!new RegExp(`export let ${prop}\\b`).test(composant)) {
		console.error(
			`✗ Cas zéro : Modale n'expose plus \`${prop}\`. Le contrat a changé — mettre ce ` +
				'contrôle à jour, sinon il interdit un geste sans en offrir le remplaçant.',
		);
		process.exit(1);
	}
}
//  Le fond, le rôle et `Échap` sont ce que les copies oubliaient. S'ils quittent
//  le composant, interdire les copies ne protège plus de rien.
for (const [motif, quoi] of [
	[/class="modal-overlay"/, 'le fond'],
	[/role="dialog"/, 'le rôle de dialogue'],
	[/'Escape'/, 'la fermeture au clavier'],
]) {
	if (!motif.test(composant)) {
		console.error(`✗ Cas zéro : Modale ne porte plus ${quoi} — ce contrôle ne mesure plus rien.`);
		process.exit(1);
	}
}
if (!/^\.modal-overlay\s*\{/m.test(cssGlobal(RACINE))) {
	console.error(
		'✗ Cas zéro : la feuille commune ne porte plus `.modal-overlay`. Elle a déménagé, et ' +
			"interdire les redéfinitions locales n'aurait plus de sens.",
	);
	process.exit(1);
}

const tous = [...fichiers(join(RACINE, 'routes')), ...fichiers(join(RACINE, 'lib'))].filter(
	(f) => f !== COMPOSANT,
);
if (tous.length === 0) {
	console.error("✗ Cas zéro : aucun fichier analysé — l'arborescence a changé.");
	process.exit(1);
}

//  ── Recherche ───────────────────────────────────────────────────────────────
const MOTIFS = [
	{
		regex: /class="[^"]*\bmodal-overlay\b/g,
		quoi: 'le fond de modale est rendu à la main',
		remede: '<Modale titre="…" on:fermer={…}> … </Modale>',
	},
	{
		//  Les trois règles ensemble : une copie locale de la boîte est le même
		//  défaut qu'une copie locale du fond, et c'est celle qui avait divergé.
		regex: /^[\t ]*\.modal(-overlay|-box)?[\s.,:[{]/gm,
		quoi: 'une règle de modale est redéfinie en CSS local',
		remede: "elle vit dans `styles/composants.css` — passer par `classeBoite`/`styleBoite`",
	},
];

const fautifs = [];
const exceptionsUtiles = new Set();
let fichiersAvecModale = 0;

for (const f of tous) {
	const rel = relative(RACINE, f).split(sep).join('/');
	const brut = readFileSync(f, 'utf8');
	if (brut.includes('<Modale ')) fichiersAvecModale++;
	const contenu = sansCommentaires(brut);
	const trouves = [];
	for (const motif of MOTIFS) {
		const m = contenu.match(motif.regex);
		if (m) trouves.push({ ...motif, exemples: [...new Set(m.map((s) => s.trim()))].slice(0, 3) });
	}
	if (trouves.length === 0) continue;
	if (rel in EXCEPTIONS) {
		exceptionsUtiles.add(rel);
		continue;
	}
	fautifs.push({ fichier: rel, trouves });
}

//  Le composant peut exister, être conforme, et n'être employé nulle part : le
//  contrôle serait alors vert sur un site qui aurait tout réécrit à la main.
//  C'est EXACTEMENT l'état du 28/08/2026 au matin — un seul écran l'employait.
if (fichiersAvecModale < 2) {
	console.error(
		`✗ Cas zéro : ${fichiersAvecModale} fichier(s) emploient <Modale>. Le composant existe ` +
			'mais ne sert pas — ce contrôle ne mesure alors plus rien.',
	);
	process.exit(1);
}

if (fautifs.length > 0) {
	console.error('✗ Fond(s) de modale écrit(s) hors du composant :');
	for (const { fichier, trouves } of fautifs) {
		for (const t of trouves) {
			console.error(`    ${fichier} — ${t.exemples.join(' · ')}`);
			console.error(`        ${t.quoi}`);
			console.error(`        → ${t.remede}`);
		}
	}
	console.error(
		"\n  Une copie du fond n'emporte pas ce qui compte : `Échap`, le rôle et le verrou de\n" +
			'  défilement. Seize modales sur vingt-six ne se fermaient qu\'à la souris (#561).',
	);
	process.exit(1);
}

const inutiles = Object.keys(EXCEPTIONS).filter((f) => !exceptionsUtiles.has(f));
if (inutiles.length > 0) {
	console.error('✗ Exception(s) devenue(s) inutile(s) :');
	for (const f of inutiles) console.error(`    ${f} — retirer l'entrée de EXCEPTIONS`);
	process.exit(1);
}

console.log(
	`✓ Modales : ${fichiersAvecModale} fichier(s) passent par Modale, ${tous.length} fichier(s) ` +
		`vérifié(s), ${Object.keys(EXCEPTIONS).length} exception(s) déclarée(s) et justifiée(s).`,
);
