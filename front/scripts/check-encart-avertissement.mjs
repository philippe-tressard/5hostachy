#!/usr/bin/env node
/**
 *  L'encart d'avertissement s'écrit UNE fois : `EncartAvertissement` (#1455).
 *
 *  Le 29/09/2026, le bloc « fond et filet d'avertissement, texte d'avertissement »
 *  était recopié dans sept écrans — chacun avec sa marge, son rayon, sa taille —
 *  et `.alert-warning` en portait une huitième, aux couleurs en dur et au texte
 *  ambre que la charte refuse. Le composant existait déjà (#779) : rien ne
 *  faisait passer par lui.
 *
 *  Ce qu'il refuse : le FOND d'avertissement (`--color-warning-fond`) ailleurs
 *  que dans le composant, hors des EMPRUNTS déclarés ci-dessous — ce qui prend la
 *  teinte sans être un encart (un survol, un badge, une carte mise en avant).
 *  Chaque emprunt porte son nombre : un de plus est un encart recopié, un de
 *  moins une exception qui ne sert plus. Les deux échouent.
 *
 *  Lancer : node scripts/check-encart-avertissement.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';

/** La porte : le seul fichier où l'encart s'écrit. */
const PORTE = 'lib/components/EncartAvertissement.svelte';

/** Fichier → [occurrences, pourquoi ce n'est pas un encart]. */
const EMPRUNTS = {
	'lib/components/AlerteRelanceSyndic.svelte': [1, 'le SURVOL d’une carte de relance'],
	'lib/components/RaccourcisRapides.svelte': [1, 'le SURVOL de la pastille du conseil'],
	'lib/components/BandeauDelegation.svelte': [
		1,
		'le bandeau « vous agissez pour… » du menu : une ligne de navigation, sans filet',
	],
	'lib/components/DroitsRgpd.svelte': [1, 'une CARTE de section teintée, titre et contenu'],
	'lib/components/PanneauModeration.svelte': [
		1,
		'un PANNEAU dépliable (en-tête bouton, réponses), pas un texte',
	],
	'routes/(app)/espace-cs/+page.svelte': [1, 'le BADGE de rôle « président »'],
	'routes/(app)/tableau-de-bord/+page.svelte': [1, 'la CARTE des consignes mise en avant'],
	'styles/composants.css': [2, 'le SURVOL de `.btn-icon-warn` et le badge `.badge-orange`'],
	'styles/ecrans.css': [2, 'la carte KPI en alerte, à l’écran et à l’impression'],
};

/** Le nombre de fonds d'avertissement d'une source. PURE. */
export function fonds(source) {
	const s = source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/<!--[\s\S]*?-->/g, '');
	return (s.match(/background(?:-color)?\s*:\s*var\(--color-warning-fond\)/g) ?? []).length;
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const t = (libelle, attendu, src) => {
		const r = fonds(src);
		const ok = r === attendu;
		console.log(`${ok ? 'PASS' : 'FAIL'}  ${libelle} → ${r}`);
		if (!ok) ko = 1;
	};
	t('encart recopié en CSS', 1, '.x { background: var(--color-warning-fond); }');
	t('encart en style en ligne', 1, '<p style="background:var(--color-warning-fond)">');
	t('background-color aussi', 1, '.x { background-color: var(--color-warning-fond); }');
	t('commentaire CSS ignoré', 0, '/* background: var(--color-warning-fond); */');
	t('commentaire HTML ignoré', 0, '<!-- background: var(--color-warning-fond) -->');
	t('le filet seul ne compte pas', 0, '.x { border: 1px solid var(--color-warning-bordure); }');
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	process.exit(ko);
}

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (e.endsWith('.svelte') || e.endsWith('.css')) acc.push(p);
	}
	return acc;
}

const fautes = [];
const vus = {};
for (const f of fichiers('src')) {
	const rel = f
		.split(sep)
		.join('/')
		.replace(/^src\//, '');
	const n = fonds(readFileSync(f, 'utf8'));
	if (n && rel !== PORTE) vus[rel] = n;
}
for (const [rel, n] of Object.entries(vus)) {
	const attendu = EMPRUNTS[rel]?.[0];
	if (attendu === undefined)
		fautes.push(`${rel} — ${n} fond(s) d'avertissement : passer par EncartAvertissement`);
	else if (n !== attendu)
		fautes.push(
			`${rel} — ${n} fond(s), ${attendu} déclaré(s) : encart recopié, ou emprunt à mettre à jour`,
		);
}
for (const rel of Object.keys(EMPRUNTS))
	if (!vus[rel]) fautes.push(`${rel} — emprunt déclaré qui ne sert plus : le retirer`);
if (!fonds(readFileSync(join('src', ...PORTE.split('/')), 'utf8')))
	fautes.push(`${PORTE} — la porte ne porte plus le fond : le contrôle ne mesure plus rien`);

if (fautes.length) {
	console.error(`\n✗ Encart d'avertissement hors du composant :\n\n  ${fautes.join('\n  ')}\n`);
	process.exit(1);
}
console.log(
	`✓ Encart d'avertissement : une porte, ${Object.keys(EMPRUNTS).length} emprunt(s) de teinte déclaré(s).`,
);
