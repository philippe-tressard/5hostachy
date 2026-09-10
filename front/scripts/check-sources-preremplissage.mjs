#!/usr/bin/env node
/**
 * Une actualité ÉPINGLÉE est toujours proposée au pré-remplissage d'une affiche.
 *
 * ## Ce qui a été demandé (10/09/2026)
 *
 * *« Fais une évolution sur l'annonce de hall : la présélection peut se faire sur
 * une actualité, même si elle est épinglée. »*
 *
 * Le sélecteur triait par date de création et coupait aux dix premières. Une
 * actualité **épinglée** — donc celle qu'on veut précisément garder sous les
 * yeux, donc souvent la plus ancienne des importantes — sortait de la liste et
 * devenait la seule qu'on ne pouvait PAS reprendre. Le geste manquait exactement
 * là où il servait le plus.
 *
 * ⚠️ Épingler dit « ceci reste d'actualité ». Trier par date seule revient à dire
 * le contraire : c'est la date qui décidait de ce qui est encore d'usage, alors
 * que quelqu'un l'avait déjà décidé à la main.
 *
 * ## Pourquoi un contrôle, et pas seulement une fonction
 *
 * La règle tient en trois lignes, et c'est justement ce qui la rend fragile : le
 * prochain qui voudra « simplifier » remettra un tri par date, sans rien casser
 * de visible. Le défaut ne se voit que sur une base où une actualité épinglée est
 * plus vieille que les dix dernières — c'est-à-dire en production, et tard.
 *
 * Le contrôle **exécute la vraie fonction** (esbuild, comme
 * `check-libelle-perimetre`) plutôt que de relire le fichier : une règle se
 * vérifie sur son comportement, jamais sur son texte.
 */
import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ICI = dirname(fileURLToPath(import.meta.url));
const SOURCE = join(ICI, '..', 'src', 'lib', 'publications.ts');

function echouer(message) {
	console.error(`✗ ${message}`);
	process.exit(1);
}

if (!existsSync(SOURCE)) echouer(`Cas zéro : ${SOURCE} est introuvable — contrôle inopérant.`);

const esbuild = await import('esbuild');
let module;
try {
	const { outputFiles } = await esbuild.build({
		entryPoints: [SOURCE],
		bundle: true,
		write: false,
		format: 'esm',
		platform: 'neutral',
	});
	module = await import(
		`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}`
	);
} catch (e) {
	echouer(`Cas zéro : lib/publications.ts ne se transpile pas (${e.message}).`);
}

const { sourcesPreremplissage, MAX_SOURCES_PREREMPLISSAGE } = module;
if (typeof sourcesPreremplissage !== 'function') {
	echouer(
		"Cas zéro : lib/publications.ts n'exporte plus `sourcesPreremplissage` — " +
			'la sélection a changé de forme, mettre ce contrôle à jour.',
	);
}

/** Une actualité, réduite à ce dont la règle a besoin. */
const pub = (id, jours, extra = {}) => ({
	id,
	titre: `Actualité ${id}`,
	cree_le: new Date(Date.UTC(2026, 8, 10) - jours * 86400000).toISOString(),
	brouillon: false,
	epingle: false,
	...extra,
});

const echecs = [];
const verifier = (nom, condition, detail) => {
	if (!condition) echecs.push(`${nom} — ${detail}`);
};

//  ── 1. L'épinglée ancienne est proposée, et les récentes aussi ──────────────
{
	//  Douze publications récentes, plus une épinglée vieille de six mois.
	const recentes = Array.from({ length: 12 }, (_, i) => pub(i + 1, i));
	const ancienneEpinglee = pub(99, 180, { epingle: true });
	const retenues = sourcesPreremplissage([...recentes, ancienneEpinglee]);
	const ids = retenues.map((p) => p.id);

	verifier(
		"l'épinglée ancienne est proposée",
		ids.includes(99),
		`obtenu ${JSON.stringify(ids)} — c'est LE défaut signalé le 10/09/2026`,
	);
	verifier(
		"l'épinglée vient en tête",
		ids[0] === 99,
		`obtenu ${ids[0]} — une entrée qu'on ne trouve pas vaut une entrée absente`,
	);
	verifier(
		'AUCUNE publication du fil n’est écartée',
		retenues.length === 13,
		`${retenues.length} entrée(s) sur 13 — le plafond de dix a été retiré le ` +
			'10/09/2026 : « n’importe quelle publication du fil, non archivée »',
	);
}

//  ── 2. Les brouillons restent dehors ────────────────────────────────────────
{
	const ids = sourcesPreremplissage([
		pub(1, 0),
		pub(2, 1, { brouillon: true }),
		pub(3, 2, { brouillon: true, epingle: true }),
	]).map((p) => p.id);
	verifier(
		'un brouillon n’est jamais proposé',
		!ids.includes(2) && !ids.includes(3),
		`obtenu ${JSON.stringify(ids)} — même épinglé, un texte non publié n'a pas à ` +
			'paraître au hall',
	);
}

//  ── 3. À défaut d'épinglée, l'ordre reste chronologique inverse ─────────────
{
	const ids = sourcesPreremplissage([pub(1, 5), pub(2, 1), pub(3, 3)]).map((p) => p.id);
	verifier(
		'sans épinglée, la plus récente vient en tête',
		JSON.stringify(ids) === JSON.stringify([2, 3, 1]),
		`obtenu ${JSON.stringify(ids)}`,
	);
}

//  ── 4. Cas zéro : le contrôle sait-il REFUSER ? ─────────────────────────────
{
	//  L'implémentation d'AVANT — tri par date seule, coupé à dix — doit échouer
	//  au premier test. Sans cela, ce contrôle passerait sur les deux et ne
	//  mesurerait rien.
	const ancienne = (pubs) =>
		[...pubs]
			.filter((p) => !p.brouillon)
			.sort((a, b) => new Date(b.cree_le).getTime() - new Date(a.cree_le).getTime())
			.slice(0, MAX_SOURCES_PREREMPLISSAGE);
	const recentes = Array.from({ length: 12 }, (_, i) => pub(i + 1, i));
	const ids = ancienne([...recentes, pub(99, 180, { epingle: true })]).map((p) => p.id);
	if (ids.includes(99) || ids.length === 13) {
		echouer(
			'Cas zéro : le jeu d’essai ne distingue plus les deux implémentations — ' +
				'l’ancienne le passerait aussi, donc ce contrôle ne mesure rien.',
		);
	}
}

if (echecs.length > 0) {
	console.error('✗ Le pré-remplissage ne propose pas ce qu’il doit :\n');
	for (const e of echecs) console.error(`  • ${e}`);
	console.error(
		'\n  Une actualité épinglée est toujours proposée, quel que soit son âge —\n' +
			'  c’est précisément celle qu’on veut reprendre au hall.\n',
	);
	process.exit(1);
}

console.log(
	`✓ Pré-remplissage : tout le fil non archivé est proposé, les épinglées en tête, ` +
		`les brouillons exclus — 5 vérification(s).`,
);
