#!/usr/bin/env node
/**
 * Le GESTE D'ÉDITION se rend partout de la même façon.
 *
 * ## Pourquoi ce contrôle existe (10/09/2026)
 *
 * Deux anomalies signalées à l'écran sur les contrats — *« il n'y a pas d'icône
 * édition mais un bouton Modifier »*, et *« le formulaire d'édition apparaît en
 * bas de page »*. L'audit qui a suivi en a trouvé **cinq autres** du premier
 * genre et **un** du second, sur des écrans que personne n'avait signalés.
 *
 * 🔴 **Et la décision était déjà prise.** `RubriqueHistorique` porte, depuis un
 * lot antérieur, ce commentaire :
 *
 *   « Le CRAYON SEUL, comme partout ailleurs sur le site : ce bouton portait
 *     "✏️ Modifier" et était **le dernier à écrire le mot**. »
 *
 * Il en restait cinq. C'est le motif que ce dépôt connaît déjà — *le seul
 * fichier qui parle du sujet affirme que le problème n'existe plus*, et cette
 * affirmation dispense tout le monde de vérifier. Une consigne écrite dans un
 * commentaire ne se maintient pas : il faut un contrôle qui échoue.
 *
 * ## Les quatre règles
 *
 * **A. Le crayon SEUL.** Un bouton qui ouvre une édition porte `btn-icon-edit`
 * ou `btn-icon`, l'icône, et son sens dans `title` + `aria-label`. Le MOT
 * « Modifier » à côté de l'icône est la seconde forme du même geste.
 *
 * **B. Un formulaire, un endroit.** Le même composant de formulaire rendu deux
 * fois dans un écran, à plus de `ECART_MAX` lignes d'écart, n'est pas « la même
 * boîte » : c'est la même boîte à deux endroits, dont un que l'utilisateur ne
 * voit pas. `ux-patterns` §14 bis dit *créer et corriger emploient la même
 * boîte* — et la lettre en était respectée sur les contrats, l'esprit non.
 *
 * **C. Un identifiant d'édition ne gouverne qu'UN rendu.** La variable qui dit
 * *quel objet est en cours de correction* ne peut pas à la fois ouvrir un
 * formulaire dans l'écran ET être déléguée à un composant enfant : les deux
 * rendus s'affichent alors ENSEMBLE. Signalé à l'écran le 10/09/2026 —
 * *« plusieurs contrats sont ouverts en édition simultanément »* — quelques
 * heures après que la correction d'un contrat eut déménagé dans sa carte. Le
 * bloc de tête était resté ouvert sur `contratFormOuvert || editContratId`.
 *
 * 🔴 **La règle B ne pouvait pas le voir, et c'est l'extraction qui l'a
 * aveuglée** : elle compte les rendus d'un formulaire FICHIER PAR FICHIER, et
 * le second venait d'être déplacé dans un second fichier. Un contrôle dont la
 * portée est le fichier perd sa prise le jour où l'on découpe — la portée du
 * contrôle fait partie du contrôle (`standards/05` §9).
 *
 * **D. Le formulaire ne défile QUE s'il s'ouvre ailleurs que sous les yeux.**
 * `FormulaireCreation` ne peut appeler `ramener()` que depuis la ligne réactive
 * gardée par `cle !== undefined`. Signalé à l'écran le 10/09/2026, trois fois de
 * suite : *« le contrat édité remonte en haut »*. Le montage appelait
 * `ramener(cle)` sans condition — donc `ramener(undefined)` pour tous les
 * formulaires qui s'ouvrent DANS la carte de l'objet corrigé, lesquels se
 * faisaient ramener en haut de l'écran dès qu'ils dépassaient la bande visible
 * de quelques pixels, en emportant leur carte.
 *
 * 🔴 **L'intention était écrite dans le fichier même**, à dix lignes de là : *« un
 * formulaire qui s'ouvre sous les yeux n'a pas à faire sauter la page »*. Le code
 * ne testait que la POSITION, jamais la raison d'être là — et la position seule
 * ne distingue pas « ouvert loin du geste » de « ouvert un peu bas ».
 *
 * ⚠️ La règle B admet des séparations JUSTIFIÉES : deux rendus dont les
 * propriétés diffèrent réellement (un bail à la création porte des lots, pas à
 * la correction) restent séparés — mais le second doit alors se ramener à
 * l'écran, ce que `FormulaireCreation` fait par sa `cle`. Le contrôle exige donc
 * cette clé, pas la fusion.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const ICI = dirname(fileURLToPath(import.meta.url));
const SRC = join(ICI, '..', 'src');

/** Deux rendus plus éloignés que cela ne sont plus « au même endroit ». */
const ECART_MAX = 200;

/**
 * Les fichiers où le MOT « Modifier » accompagne l'icône pour une raison.
 * Chacun avec son motif — une tolérance sans raison devient un dépotoir.
 */
const EXCEPTIONS = {
	'lib/components/RubriqueHistorique.svelte':
		"le mot n'apparaît que dans le COMMENTAIRE qui raconte sa suppression — " +
		"et c'est ce commentaire qui affirmait être « le dernier », alors qu'il " +
		'en restait cinq. Le garder est utile : il porte la décision.',
};

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (e.endsWith('.svelte')) acc.push(p);
	}
	return acc;
}

const tous = fichiers(SRC);
const fautes = [];
const exceptionsVues = new Set();

//  ── A. Le crayon seul ───────────────────────────────────────────────────────
const MOT = /(?:✏️|✏|&#x270F;&#xFE0F;|&#x270F;)\s*Modifier/g;
for (const f of tous) {
	const rel = relative(SRC, f).replace(/\\/g, '/');
	const src = readFileSync(f, 'utf8');
	const trouve = [...src.matchAll(MOT)];
	if (trouve.length === 0) continue;
	if (rel in EXCEPTIONS) {
		exceptionsVues.add(rel);
		continue;
	}
	for (const m of trouve) {
		fautes.push({
			regle: 'A',
			fichier: rel,
			ligne: src.slice(0, m.index).split('\n').length,
			quoi: 'le mot « Modifier » accompagne l’icône',
			remede: 'le crayon SEUL, le sens dans `title` et `aria-label` — `btn-icon-edit`',
		});
	}
}

//  ── B. Un formulaire, un endroit ────────────────────────────────────────────
const COMPOSANT = /<(Formulaire[A-Z][A-Za-z]*)\b/g;
for (const f of tous) {
	const rel = relative(SRC, f).replace(/\\/g, '/');
	const src = readFileSync(f, 'utf8');
	const parNom = new Map();
	for (const m of src.matchAll(COMPOSANT)) {
		const ligne = src.slice(0, m.index).split('\n').length;
		if (!parNom.has(m[1])) parNom.set(m[1], []);
		parNom.get(m[1]).push(ligne);
	}
	for (const [nom, lignes] of parNom) {
		if (lignes.length < 2) continue;
		const ecart = Math.max(...lignes) - Math.min(...lignes);
		if (ecart <= ECART_MAX) continue;
		//  Le second rendu doit au moins se ramener à l'écran : `cle` sur le
		//  `FormulaireCreation` qui l'enveloppe, ou sur lui-même.
		const zone = src
			.split('\n')
			.slice(Math.max(...lignes) - 12, Math.max(...lignes) + 4)
			.join('\n');
		if (/\bcle=\{/.test(zone)) continue;
		fautes.push({
			regle: 'B',
			fichier: rel,
			ligne: Math.max(...lignes),
			quoi: `<${nom}> rendu aux lignes ${lignes.join(', ')} — ${ecart} lignes d’écart`,
			remede:
				'un seul rendu au même endroit, ou `cle={…}` sur le second pour qu’il se ' +
				'ramène à l’écran (`FormulaireCreation`)',
		});
	}
}

//  ── C. Un identifiant d'édition ne gouverne qu'un rendu ─────────────────────
const IDENT_EDITION = /\bedit[A-Z][A-Za-z]*Id\b/;

for (const f of tous) {
	const rel = relative(SRC, f).replace(/\\/g, '/');
	const lignes = readFileSync(f, 'utf8').split('\n');

	for (let i = 0; i < lignes.length; i++) {
		const ouverture = lignes[i].match(/\{#if\s[^}]*/);
		if (!ouverture) continue;
		const nom = ouverture[0].match(IDENT_EDITION)?.[0];
		if (!nom) continue;

		//  Le bloc gouverné par ce `{#if}`, jusqu'à son `{/if}`.
		let prof = 0;
		let fin = lignes.length - 1;
		for (let j = i; j < lignes.length; j++) {
			prof += (lignes[j].match(/\{#if\b/g) || []).length;
			prof -= (lignes[j].match(/\{\/if\}/g) || []).length;
			if (prof <= 0) {
				fin = j;
				break;
			}
		}
		const bloc = lignes.slice(i, fin + 1).join('\n');
		if (!/<Formulaire[A-Z]/.test(bloc)) continue;

		//  Le même identifiant confié à un composant, HORS de ce bloc : l'enfant
		//  rendra sa propre boîte, et les deux seront à l'écran ensemble.
		const confie = `{${nom}}`;
		const nomme = `${nom}={`;
		const ailleurs = lignes.findIndex(
			(l, n) => (n < i || n > fin) && (l.trim().startsWith(confie) || l.trim().startsWith(nomme)),
		);
		if (ailleurs === -1) continue;

		fautes.push({
			regle: 'C',
			fichier: rel,
			ligne: i + 1,
			quoi:
				`\`${nom}\` ouvre un formulaire ici ET est confié à un composant ` +
				`(ligne ${ailleurs + 1}) — deux boîtes d'édition à l'écran en même temps`,
			remede:
				"ne garder qu'un rendu : l'écran ouvre la CRÉATION, le composant qui porte " +
				"l'objet ouvre sa CORRECTION",
		});
	}
}

//  ── D. Le formulaire ne défile que s'il porte une `cle` ─────────────────────
{
	const f = join(SRC, 'lib', 'components', 'FormulaireCreation.svelte');
	const src = readFileSync(f, 'utf8');
	//  Cas zéro : si ce composant cesse de défiler du tout, la règle n'a plus
	//  d'objet — et un contrôle sans objet doit le DIRE, pas rendre vert.
	if (!src.includes('scrollIntoView')) {
		console.error(
			'✗ Cas zéro : FormulaireCreation ne défile plus du tout — la règle D ne mesure rien.',
		);
		process.exit(1);
	}
	src.split('\n').forEach((ligne, i) => {
		//  ⚠️ Les COMMENTAIRES parlent de `ramener()` — c'est même là que
		//  l'intention est écrite. Les compter serait le faux positif de l'audit du
		//  10/09 (23 sur 23), qui attrapait des `role="button"` cités dans du texte.
		if (/^\s*(?:\/\/|\*|\/\*)/.test(ligne)) return;
		if (!/(?:^|[^a-zA-Z])ramener\(/.test(ligne)) return;
		//  Les deux seules écritures légitimes : la déclaration de la fonction, et
		//  l'appel réactif gardé par la présence d'une `cle`.
		if (/function ramener/.test(ligne)) return;
		if (/cle !== undefined\).*ramener\(/.test(ligne)) return;
		fautes.push({
			regle: 'D',
			fichier: 'lib/components/FormulaireCreation.svelte',
			ligne: i + 1,
			quoi: 'appel à `ramener()` hors de la garde `cle !== undefined`',
			remede:
				'un formulaire qui s’ouvre SOUS LES YEUX ne défile pas ; seule une `cle` ' +
				'demande à être ramené à l’écran',
		});
	});
}

//  ── Cas zéro : le contrôle regarde-t-il quelque chose ? ─────────────────────
if (tous.length < 50) {
	console.error(`✗ Cas zéro : ${tous.length} composant(s) analysé(s) — le relevé est cassé.`);
	process.exit(1);
}

//  ── Une exception qui ne sert plus fait ÉCHOUER ─────────────────────────────
const inutiles = Object.keys(EXCEPTIONS).filter((f) => !exceptionsVues.has(f));
if (inutiles.length > 0) {
	console.error('✗ Exception(s) devenue(s) inutile(s), à retirer d’EXCEPTIONS :');
	for (const f of inutiles) console.error(`    ${f}`);
	process.exit(1);
}

if (fautes.length > 0) {
	console.error('✗ Le geste d’édition n’est pas rendu partout de la même façon :\n');
	for (const d of fautes) {
		console.error(`  [${d.regle}] ${d.fichier}:${d.ligne}`);
		console.error(`      ${d.quoi}`);
		console.error(`      → ${d.remede}\n`);
	}
	console.error(
		'  Ces quatre règles ont été signalées à l’écran le 10/09/2026, et la première\n' +
			'  était déjà écrite dans un commentaire qui se croyait le dernier concerné.\n',
	);
	process.exit(1);
}

console.log(
	`✓ Geste d’édition : ${tous.length} composant(s) vérifié(s) — crayon seul partout, ` +
		`aucun formulaire rendu loin de son jumeau, aucun identifiant d’édition à deux rendus, défilement gardé par une clé, ${Object.keys(EXCEPTIONS).length} exception(s) déclarée(s).`,
);
