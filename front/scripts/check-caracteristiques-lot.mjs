#!/usr/bin/env node
/**
 *  Les CARACTÉRISTIQUES d'un lot — type, étage, superficie — se rendent par
 *  `CaracteristiquesLot` (#779, 01/10/2026).
 *
 *  🔴 La liste de définitions était écrite TROIS fois dans « Mes lots » (le lot
 *  loué, les lots en propre d'un locataire, le lot choisi d'un copropriétaire),
 *  et les copies avaient divergé : le type conditionnel dans l'une, pas dans les
 *  deux autres ; l'étage testé contre `null` seulement dans deux, contre
 *  `undefined` aussi dans la troisième.
 *
 *  Ce contrôle refuse la quatrième : un intitulé `<dt>Étage</dt>` ou
 *  `<dt>Superficie</dt>` écrit hors du composant.
 *
 *  Lancer : node scripts/check-caracteristiques-lot.mjs [--selftest]
 */
import { controler, lignesPortant } from './lib-source-unique.mjs';

/**  Un intitulé de caractéristique de lot, posé à la main. */
const COPIE = /<dt>\s*(?:Étage|Superficie)\s*<\/dt>/;

process.exit(
	controler({
		temoin: 'src/lib/components/CaracteristiquesLot.svelte',
		fautes: lignesPortant(COPIE),
		cas: [
			['\t\t\t\t{#if lot.etage !== null}<dt>Étage</dt>', 1],
			['\t\t<dt>Superficie</dt>', 1],
			['\t\t<dt> Étage </dt>', 1],
			//  La forme voulue, jamais signalée.
			['\t<CaracteristiquesLot type={lot.type} etage={lot.etage} />', 0],
			//  Un autre intitulé : hors portée.
			['\t<dt>Bâtiment</dt>', 0],
		],
		ok: "Caractéristiques d'un lot : rendues par CaracteristiquesLot seul",
		ko: 'caractéristique(s) de lot écrite(s) à la main',
		conseil: 'Employer `<CaracteristiquesLot type typeAppartement etage superficie>`.',
	}),
);
