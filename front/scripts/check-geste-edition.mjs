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
 * ## Les deux règles
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
		'  Ces deux règles ont été signalées à l’écran le 10/09/2026, et la première\n' +
			'  était déjà écrite dans un commentaire qui se croyait le dernier concerné.\n',
	);
	process.exit(1);
}

console.log(
	`✓ Geste d’édition : ${tous.length} composant(s) vérifié(s) — crayon seul partout, ` +
		`aucun formulaire rendu loin de son jumeau, ${Object.keys(EXCEPTIONS).length} exception(s) déclarée(s).`,
);
