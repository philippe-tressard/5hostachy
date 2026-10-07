#!/usr/bin/env node
/**
 *  Le nom de CETTE résidence ne s'écrit pas dans le code du site (#1725).
 *
 *  🔴 « 5Hostachy » était écrit dans le repli du nom du site (`siteNomStore`),
 *  l'état initial du formulaire d'administration, le titre d'une fiche de
 *  sondage, la mention du responsable de traitement à l'inscription, une
 *  catégorie d'affaire, le lien vers le code source et le manifeste de
 *  l'application installée. Le produit doit servir une autre copropriété
 *  (`specs/architecture/multi-coproprietes.md`) : chacune de ces lignes
 *  affichait le nom de celle-ci chez une autre.
 *
 *  Deux noms, deux sources — jamais un littéral :
 *    - la RÉSIDENCE : `siteNomStore` (`$lib/stores/pageConfig`), repli neutre
 *      `NOM_SITE_PAR_DEFAUT` (`$lib/configSite`) ;
 *    - la PLATEFORME : `$lib/plateforme` — le logiciel s'appelle CoproConnect
 *      (D9), et ce module porte aussi l'adresse du dépôt et la licence en
 *      vigueur, qui gardent le nom historique.
 *
 *  Le pendant serveur est `api/tests/test_nom_site.py`.
 *
 *  Lancer : node scripts/check-nom-residence.mjs [--selftest]
 */
import { controler, lignesPortant } from './lib-source-unique.mjs';

process.exit(
	controler({
		extensions: ['.svelte', '.ts', '.js', '.css'],
		temoin: 'src/lib/plateforme.ts',
		exceptions: {
			'src/lib/stores/locale.ts':
				'`hostachy_locale` : la clé de stockage de la langue choisie. La renommer ' +
				'ferait perdre leur réglage aux navigateurs déjà configurés, et elle ne ' +
				"s'affiche nulle part.",
		},
		fautes: lignesPortant(/hostachy/i),
		cas: [
			[
				"export const siteNomStore = derived(configStore, ($c) => $c['site_nom'] ?? '5Hostachy');",
				1,
			],
			['<title>{sondage.question} — 5Hostachy</title>', 1],
			['\t\thref="https://github.com/philippe-tressard/5hostachy"', 1],
			['\t\t\tplaceholder="— Envoyé depuis 5hostachy.fr"', 1],
			//  Les commentaires racontent l'histoire et peuvent la nommer.
			['// « 5Hostachy » était écrit ici', 0],
			['/*  5Hostachy — Styles globaux */', 0],
			['<!-- 5Hostachy › Communauté -->', 0],
			['<title>{titre} — {$siteNomStore}</title>', 0],
		],
		ok: 'Nom de la résidence : jamais écrit dans le code du site',
		ko: 'ligne(s) qui écrivent « hostachy »',
		conseil:
			'La résidence : `$siteNomStore` (`$lib/stores/pageConfig`) ; la plateforme : ' +
			'`$lib/plateforme`. Une exception se déclare dans ce contrôle, avec sa raison.',
	}),
);
