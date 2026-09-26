#!/usr/bin/env node
/**
 *  Le badge NEW se rend par `BadgeNouveau`, et nulle part ailleurs (26/09/2026).
 *
 *  Il était écrit cinq fois (#1329), puis unifié en « Nouveau » gris — pendant
 *  que le fil d'activité gardait son propre « NEW » rouge, pulsant. Signalé à
 *  l'écran : deux badges pour une même notion. Arbitré : le NEW rouge, partout.
 *
 *  Ce qu'il refuse : dans le balisage d'un `.svelte` autre que `BadgeNouveau`,
 *  un nœud de texte « NEW » ou « Nouveau » seul (le badge écrit à la main).
 *
 *  Lancer : node scripts/check-badge-nouveau.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const SOURCE = 'lib/components/BadgeNouveau.svelte';
const BADGE = />\s*(?:NEW|New|Nouveau)\s*</g;

/** Les badges écrits à la main dans une source. PURE. */
export function badgesALaMain(source) {
	const balisage = neutraliserCommentaires(source).replace(/<(script|style)[\s\S]*?<\/\1>/g, '');
	return (balisage.match(BADGE) ?? []).length;
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const t = (libelle, attendu, src) => {
		const r = badgesALaMain(src);
		console.log(`${r === attendu ? 'PASS' : 'FAIL'}  ${libelle} → ${r}`);
		if (r !== attendu) ko = 1;
	};
	//  🔴 Les deux formes du 26/09/2026.
	t('NEW du fil', 1, '{#if nouveau}<span class="new-badge">NEW</span>{/if}');
	t('Nouveau gris', 1, '<span class="badge badge-gray">Nouveau</span>');
	t('forme conforme', 0, '<BadgeNouveau le={t.cree_le} />');
	t('mot dans une phrase', 0, '<p>Nouveau résident : bienvenue</p>');
	t('libellé de bouton', 0, '<button>{libelleNouveau}</button>');
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

let emplois = 0;
const fautifs = [];
for (const f of fichiers('src')) {
	const rel = f
		.split(sep)
		.join('/')
		.replace(/^src\//, '');
	const source = readFileSync(f, 'utf8');
	if (rel === SOURCE) continue;
	if (/<BadgeNouveau\b/.test(source)) emplois++;
	const n = badgesALaMain(source);
	if (n) fautifs.push(`${rel} (${n})`);
}
//  🔴 CAS ZÉRO : plus aucun écran ne l'emploie, la règle a changé de forme.
if (emplois === 0) {
	console.error(
		'\n✗ INCONNU : aucun écran n’emploie `BadgeNouveau` — mettre le contrôle à jour.\n',
	);
	process.exit(2);
}
if (fautifs.length) {
	console.error(
		`\n✗ Badge NEW écrit à la main :\n\n  ${fautifs.join('\n  ')}\n\n  → \`<BadgeNouveau le={…} />\`\n`,
	);
	process.exit(1);
}
console.log(`✓ Badge NEW : ${emplois} écran(s) l’emploient, aucun écrit à la main.`);
