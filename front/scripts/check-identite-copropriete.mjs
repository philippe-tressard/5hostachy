#!/usr/bin/env node
/**
 *  Les champs d'IDENTITÉ de la copropriété se saisissent dans un seul composant
 *  (#779, 01/10/2026).
 *
 *  🔴 Nom, adresse, deux décomptes de lots, année de construction et numéro
 *  d'immatriculation étaient saisis DEUX fois : Admin › Fiche copropriété
 *  (`OngletCopropriete`) et la fiche de la page Résidence. Les deux copies
 *  divergeaient déjà :
 *
 *  | | Admin | Résidence |
 *  |---|---|---|
 *  | champ numérique vidé | parti à `null`, la valeur s'efface | **non envoyé** — impossible de l'effacer |
 *  | nom | obligatoire, étoile | facultatif |
 *  | libellés | ceux de la fiche ANAH, avec leur aide | abrégés, sans aide |
 *
 *  `ChampsIdentiteCopropriete` porte les champs ET la conversion du formulaire
 *  vers le schéma (`chargeIdentite`) ; ce contrôle refuse la troisième copie :
 *  un `bind:value` sur l'un de ces champs, hors du composant.
 *
 *  Lancer : node scripts/check-identite-copropriete.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';

const RACINE = 'src';
const SOURCE = 'src/lib/components/ChampsIdentiteCopropriete.svelte';

/**  `bind:value={form.nb_lots_total}`, `bind:value={editImmatriculation}`… :
 *   un champ d'identité de la copropriété lié à la main. */
const COPIE = /bind:value=\{[^}]*(?:immatriculation|nb_?lots|annee_?construction)/i;

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (e.endsWith('.svelte')) acc.push(p);
	}
	return acc;
}

export function fautes(source) {
	return source
		.split('\n')
		.map((ligne, i) => [ligne, i + 1])
		.filter(([l]) => COPIE.test(l))
		.map(([, n]) => n);
}

function selftest() {
	const cas = [
		['\t\t<input type="number" min="1" bind:value={form.nb_lots_total} />', 1],
		['\t\t\tbind:value={editNbLotsPrincipaux}', 1],
		['\t\t<input bind:value={form.numero_immatriculation} />', 1],
		['\t\t<input type="number" bind:value={valeurs.annee_construction} />', 1],
		//  La forme voulue, jamais signalée.
		['\t\t<ChampsIdentiteCopropriete bind:valeurs={form} />', 0],
		//  Un autre champ lié : hors portée.
		['\t\t<input bind:value={form.adresse_facturation} />', 0],
	];
	let ko = 0;
	for (const [ligne, attendu] of cas) {
		const obtenu = fautes(ligne).length;
		console.log(`${obtenu === attendu ? 'PASS' : 'FAIL'}  ${ligne.trim()}`);
		if (obtenu !== attendu) ko = 1;
	}
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	return ko;
}

function main() {
	if (process.argv.includes('--selftest')) return selftest();
	const trouves = [];
	let lus = 0;
	for (const f of fichiers(RACINE)) {
		lus++;
		const rel = f.split(sep).join('/');
		if (rel === SOURCE) continue;
		for (const n of fautes(readFileSync(f, 'utf8'))) trouves.push(`${rel}:${n}`);
	}
	//  Cas zéro (standards/04 §2) : aucun fichier lu n'est pas « aucune copie ».
	if (!lus) {
		console.error(`✗ Aucun fichier .svelte lu sous ${RACINE} : contrôle INCONNU.`);
		return 1;
	}
	if (!trouves.length) {
		console.log(
			`✓ Identité de la copropriété : saisie seulement par ChampsIdentiteCopropriete (${lus} fichiers lus).`,
		);
		return 0;
	}
	console.error(`\n✗ ${trouves.length} champ(s) d'identité de la copropriété lié(s) à la main :`);
	for (const t of trouves) console.error(`   ${t}`);
	console.error(
		'\n  Employer `<ChampsIdentiteCopropriete bind:valeurs>` et `chargeIdentite` (même composant).\n',
	);
	return 1;
}

process.exit(main());
