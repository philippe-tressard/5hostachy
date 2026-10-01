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
import { controler, lignesPortant } from './lib-source-unique.mjs';

/**  `bind:value={form.nb_lots_total}`, `bind:value={editImmatriculation}`… :
 *   un champ d'identité de la copropriété lié à la main. */
const COPIE = /bind:value=\{[^}]*(?:immatriculation|nb_?lots|annee_?construction)/i;

process.exit(
	controler({
		sources: ['src/lib/components/ChampsIdentiteCopropriete.svelte'],
		fautes: lignesPortant(COPIE),
		cas: [
			['\t\t<input type="number" min="1" bind:value={form.nb_lots_total} />', 1],
			['\t\t\tbind:value={editNbLotsPrincipaux}', 1],
			['\t\t<input bind:value={form.numero_immatriculation} />', 1],
			['\t\t<input type="number" bind:value={valeurs.annee_construction} />', 1],
			//  La forme voulue, jamais signalée.
			['\t\t<ChampsIdentiteCopropriete bind:valeurs={form} />', 0],
			//  Un autre champ lié : hors portée.
			['\t\t<input bind:value={form.adresse_facturation} />', 0],
		],
		ok: 'Identité de la copropriété : saisie seulement par ChampsIdentiteCopropriete',
		ko: "champ(s) d'identité de la copropriété lié(s) à la main",
		conseil:
			'Employer `<ChampsIdentiteCopropriete bind:valeurs>` et `chargeIdentite` (même composant).',
	}),
);
