#!/usr/bin/env node
/**
 *  La dernière ligne d'une carte est la MÊME partout (27/09/2026).
 *
 *  ## Pourquoi
 *
 *  Arbitré à l'écran : la ligne de la carte d'affaire fait la norme, et le fil
 *  d'activité comme la carte d'actualité la rendent à l'identique. Elles
 *  différaient sur neuf points — catégorie en texte ou en emoji, état absent du
 *  fil, périmètre en tête ou après l'état, « urgent » rouge contre « ⚡ Urgente »
 *  orange, numéro en badge ou en texte, auteur avec ou sans ✍️, lecteurs et ✨
 *  absents du fil. Trois écritures d'une ligne, trois occasions de diverger.
 *
 *  ## Ce qu'il refuse
 *
 *  1. Une des trois cartes qui ne rend pas `<PastillesAffaire` ;
 *  2. ✍️ écrit ailleurs que dans `AuteurCarte` — l'auteur a UNE forme ;
 *  3. une pastille de la ligne recomposée hors de `PastillesAffaire` : la forme
 *     brève de la priorité, l'emoji de catégorie.
 *
 *  Lancer : node scripts/check-pastilles.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const CARTES = [
	'lib/components/CarteTicket.svelte',
	'lib/components/CarteActualite.svelte',
	'lib/components/FluxCard.svelte',
];
const SOURCE_LIGNE = 'lib/components/PastillesAffaire.svelte';
const SOURCE_AUTEUR = 'lib/components/AuteurCarte.svelte';

/** Ce que seule la ligne commune a le droit de rendre. */
const RENDUS_DE_LA_LIGNE = [/\bPRIORITE_BREVE\b/, /\bcategorieTicketEmoji\(/];

/** Les écarts d'une source, pour un fichier donné. PURE. */
export function ecarts(rel, source) {
	const s = neutraliserCommentaires(source);
	const sortie = [];
	if (CARTES.includes(rel) && !/<PastillesAffaire\b/.test(s))
		sortie.push('ne rend pas <PastillesAffaire> : sa dernière ligne diverge');
	if (rel !== SOURCE_AUTEUR && /✍️|✍/.test(s))
		sortie.push('✍️ écrit hors de AuteurCarte : l’auteur a une forme');
	if (rel.endsWith('.svelte') && rel !== SOURCE_LIGNE)
		for (const motif of RENDUS_DE_LA_LIGNE)
			if (motif.test(s)) sortie.push(`${motif.source} hors de PastillesAffaire`);
	return sortie;
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const t = (libelle, attendu, obtenu) => {
		const ok = attendu === obtenu;
		console.log(`${ok ? 'PASS' : 'FAIL'}  ${libelle} → ${obtenu}`);
		if (!ok) ko = 1;
	};
	const F = 'lib/components/FluxCard.svelte';
	//  🔴 La forme du 27/09/2026 : le fil composait sa ligne à la main.
	t('fil sans la ligne commune', 1, ecarts(F, '<span class="flux-auteur">x</span>').length);
	t('fil avec la ligne commune', 0, ecarts(F, '<PastillesAffaire {affaire} />').length);
	t('✍️ recopié', 1, ecarts('lib/components/X.svelte', '<span>✍️ {nom}</span>').length);
	t('✍️ en commentaire ignoré', 0, ecarts('lib/components/X.svelte', '<!-- ✍️ -->').length);
	t('priorité recomposée', 1, ecarts('lib/components/X.svelte', '{PRIORITE_BREVE[p]}').length);
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	process.exit(ko);
}

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (e.endsWith('.svelte')) acc.push(p);
	}
	return acc;
}

const fautifs = [];
const lus = new Set();
for (const f of fichiers('src')) {
	const rel = f
		.split(sep)
		.join('/')
		.replace(/^src\//, '');
	lus.add(rel);
	for (const e of ecarts(rel, readFileSync(f, 'utf8'))) fautifs.push(`${rel} — ${e}`);
}
const absents = [...CARTES, SOURCE_LIGNE, SOURCE_AUTEUR].filter((f) => !lus.has(f));
if (absents.length) {
	console.error(`\n✗ INCONNU : introuvable(s) — ${absents.join(', ')}.\n`);
	process.exit(2);
}
if (fautifs.length) {
	console.error(`\n✗ Dernière ligne de carte hors de la norme :\n\n  ${fautifs.join('\n  ')}\n`);
	process.exit(1);
}
console.log(`✓ Pastilles : ${CARTES.length} cartes rendent la même ligne, ✍️ a une forme.`);
