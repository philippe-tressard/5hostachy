#!/usr/bin/env node
/**
 * Garde-fou : une section se nomme par SON TITRE, jamais par un libellé de champ.
 *
 * ## Le défaut, signalé à l'écran (23/09/2026)
 *
 * > « Normalise les polices / styles / positionnement des titres des sections,
 * >   qui semblent ne pas être normalisés »
 *
 * Capture à l'appui : TITRE ne ressemblait pas à CATÉGORIE, SUIVI, QUAND,
 * PÉRIMÈTRE juste en dessous. Mesuré : sept formulaires ouvraient leur section 1
 * par `<SectionFormulaire premiere>` SANS titre, suivi d'un `.field` qui portait
 * un `<label>`. L'intitulé prenait alors le style d'un libellé de champ
 * (`.field label`), et non celui d'une section (`.section-titre`).
 *
 * La règle était pourtant écrite dans `SectionFormulaire` depuis le 16/08/2026 :
 * *une section à un seul champ, le titre EST le libellé*. Aucun contrôle ne la
 * tenait, et le même bloc s'est recopié sept fois sans elle. Il vit désormais
 * dans `SectionTitre`.
 *
 * ## Ce qui est refusé
 *
 * Un `<SectionFormulaire …>` **sans `titre=`** dont le contenu porte un
 * `<label>` de champ — c'est-à-dire une section qui se nomme par son champ.
 *
 * ⚠️ Une section sans titre qui ne porte AUCUN libellé reste permise : c'est le
 * groupe évident, que `SectionFormulaire` prévoit (« Vide : aucun titre, mais la
 * séparation reste »). Une case à cocher (`checkbox-field`) n'est pas un libellé
 * de champ : elle nomme sa case, pas la section.
 *
 * Test : node scripts/check-section-nommee.mjs --selftest
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');

/** Les sections fautives d'un source : `[{ ligne, extrait }]`. */
export function sectionsNommeesParUnChamp(source) {
	const src = neutraliserCommentaires(source);
	const fautes = [];
	const motif = /<SectionFormulaire\b([^>]*)>([\s\S]*?)<\/SectionFormulaire>/g;
	let m;
	while ((m = motif.exec(src)) !== null) {
		const attributs = m[1];
		if (/\btitre\s*=|\{titre\}/.test(attributs)) continue;
		const corps = m[2];
		const libelles = [...corps.matchAll(/<label\b([^>]*)>/g)].filter(
			(l) => !/checkbox-field/.test(l[1]),
		);
		if (libelles.length === 0) continue;
		const ligne = src.slice(0, m.index).split('\n').length;
		fautes.push({ ligne, extrait: m[0].split('\n')[0].trim() });
	}
	return fautes;
}

function* fichiers(dossier) {
	for (const nom of readdirSync(dossier)) {
		const chemin = join(dossier, nom);
		if (statSync(chemin).isDirectory()) yield* fichiers(chemin);
		else if (nom.endsWith('.svelte')) yield chemin;
	}
}

function selftest() {
	let ko = 0;
	const t = (libelle, attendu, source) => {
		const obtenu = sectionsNommeesParUnChamp(source).length;
		if (obtenu === attendu) console.log(`PASS  ${libelle}`);
		else {
			console.log(`FAIL  ${libelle} — attendu ${attendu}, obtenu ${obtenu}`);
			ko = 1;
		}
	};
	//  🔴 LE cas signalé : la section 1 qui se nomme par son champ.
	t(
		'section sans titre, champ libellé',
		1,
		'<SectionFormulaire premiere>\n<div class="field"><label for="t">Titre</label><input id="t" /></div>\n</SectionFormulaire>',
	);
	t(
		'section titrée, le titre EST le libellé',
		0,
		'<SectionFormulaire premiere titre="Titre" pour="t">\n<div class="field"><input id="t" /></div>\n</SectionFormulaire>',
	);
	t('titre passé en raccourci', 0, '<SectionFormulaire {titre}><label for="x">X</label></SectionFormulaire>');
	t('groupe évident, sans aucun libellé', 0, '<SectionFormulaire premiere><input /></SectionFormulaire>');
	t(
		'une case à cocher n’est pas un libellé de champ',
		0,
		'<SectionFormulaire><label class="checkbox-field"><input type="checkbox" /> Épingler</label></SectionFormulaire>',
	);
	t(
		'un libellé cité en commentaire ne compte pas',
		0,
		'<SectionFormulaire premiere><!-- <label>Titre</label> --><input /></SectionFormulaire>',
	);
	console.log(ko === 0 ? '\n✓ Autotest : la section nommée par son champ est refusée, le reste non.' : '\n✗ Autotest en échec');
	return ko;
}

function main() {
	if (process.argv.includes('--selftest')) return selftest();
	const fautes = [];
	let sections = 0;
	for (const f of fichiers(RACINE)) {
		const src = readFileSync(f, 'utf8');
		sections += (src.match(/<SectionFormulaire\b/g) ?? []).length;
		for (const faute of sectionsNommeesParUnChamp(src)) {
			fautes.push(`  ${relative(RACINE, f).split(sep).join('/')}:${faute.ligne}  ${faute.extrait}`);
		}
	}
	//  Cas zéro : sans section trouvée, ce contrôle ne regarderait rien.
	if (sections < 20) {
		console.error(`✗ Seulement ${sections} <SectionFormulaire> trouvée(s) — le relevé est cassé, INCONNU.`);
		return 2;
	}
	if (fautes.length) {
		console.error('✗ Section nommée par un libellé de champ — le titre de section doit être le libellé :\n');
		console.error(fautes.join('\n'));
		console.error(
			'\n  → `SectionTitre` pour la section 1, ou `titre=` + `pour=` sur `SectionFormulaire`\n' +
				'    quand la section n’a qu’un champ (le `<label>` du champ disparaît).',
		);
		return 1;
	}
	console.log(`✓ Sections : ${sections} relevée(s), aucune ne se nomme par un libellé de champ.`);
	return 0;
}

process.exit(main());
