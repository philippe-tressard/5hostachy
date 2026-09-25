/**
 * L'astérisque des champs requis ne s'écrit pas à la main — les deux formes
 * que `lint:champs` refuse, extraites de `check-champs.mjs` le 24/09/2026
 * (#1186) : le contrôle passait 500 lignes en recevant la seconde, et le
 * garde-fou de modularité demande de découper, pas de raboter.
 *
 * PURE : lit une source, rend les lignes fautives. `check-champs.mjs` décide.
 */
import { neutraliserCommentaires as sansCommentaires } from './lib-commentaires.mjs';

// ════════════════════════════════════════════════════════════════════════════
//  L'ASTÉRISQUE DES CHAMPS REQUIS NE S'ÉCRIT PAS À LA MAIN (#1121, 22/09/2026)
// ════════════════════════════════════════════════════════════════════════════
//
//  🔴 La règle, demandée à l'écran : l'astérisque est **collée** au libellé, et
//  **rouge tant que le champ est vide** — elle cesse d'être une décoration pour
//  devenir l'état du champ.
//
//  Un caractère ne sait pas si le champ est vide. Elle était écrite trente-cinq
//  fois — vingt-six `<label>Titre *</label>` en clair et cinq composants qui
//  calculaient `{requis ? ' *' : ''}` —, et aucun de ces points ne connaissait
//  la valeur. C'est `EtoileRequis` qui la reçoit, et lui seul.
//
//  ⚠️ Ce qui est refusé : une astérisque **précédée d'un espace** juste avant
//  une fin de libellé. Pas toutes les astérisques — une note de bas de tableau,
//  un motif de recherche, une multiplication en gardent le droit.

/** Astérisques collées à une fin de libellé, ou calculées en chaîne. */
export function etoilesEnLigne(brut) {
	const fautes = [];
	sansCommentaires(brut)
		.split('\n')
		.forEach((ligne, i) => {
			//  🔴 Quatre formes de plus, relevées par l'audit du 25/09/2026 (#1329) :
			//  `</label` coupé par Prettier avant son `>`, un NOM autre que `requis`
			//  dans la chaîne calculée, et l'astérisque seule dans un `<span>` stylé.
			if (
				/ \*<\/(label|span)\b/.test(ligne) ||
				/ \*<(input|select|textarea)\b/.test(ligne) ||
				/\{\w+ \? ' \*' : ''\}/.test(ligne) ||
				/>\s*\*\s*<\/span>/.test(ligne)
			) {
				fautes.push({ ligne: i + 1, texte: ligne.trim().slice(0, 70) });
			}
		});
	return fautes;
}

//  🔴 L'AUTRE FORME, que le motif ci-dessus ne voyait pas (#1186, 24/09/2026) :
//  l'astérisque en FIN DE LIGNE, dans un libellé qui enveloppe son champ —
//
//      <label class="field">
//          Titre *
//          <input … />
//
//  Rien ne la suit sur la ligne, donc ni `</label>` ni `</span>`. La Boîte à
//  idées l'affichait en noir, signalée à l'écran. Le relevé en a trouvé QUINZE,
//  dans neuf fichiers ; un plafond décroissant les a tenues le temps de les
//  convertir, et il est tombé à zéro avec #1254 : c'est désormais un refus pur.
//  Seul le BALISAGE est lu — dans un `<script>`, « a * » en fin de ligne est une
//  multiplication.
//
//  ⚠️ En convertissant, #1254 en a trouvé TROIS d'une troisième forme, que ni
//  l'un ni l'autre motif ne voyait : l'astérisque collée au CONTRÔLE qui suit,
//  `>Question *<input …` (FAQ, relevé de consommation). `etoilesEnLigne` la
//  refuse désormais. Un relevé par motif ne prouve rien sur ce qu'il n'a pas
//  cherché — d'où les cas ci-dessous, que `--selftest` rejoue.

/** Astérisques en fin de ligne d'un libellé, dans le balisage seul. */
export function etoilesFinDeLigne(brut) {
	const source = sansCommentaires(brut);
	const debut = source.lastIndexOf('</script>');
	const decalage = debut >= 0 ? source.slice(0, debut).split('\n').length - 1 : 0;
	const fautes = [];
	(debut >= 0 ? source.slice(debut) : source).split('\n').forEach((ligne, i) => {
		//  `}` compte (#1329) : `{libelleFichier} *` passait, faute d'une lettre.
		if (/[A-Za-zÀ-ÿ)}'’/] \*\s*$/.test(ligne) && !/^\s*\*/.test(ligne)) {
			fautes.push({ ligne: decalage + i + 1, texte: ligne.trim().slice(0, 70) });
		}
	});
	return fautes;
}

/** Les cas que `check-champs.mjs --selftest` rejoue : [nom, source, fautes attendues]. */
export const CAS_ETOILES = [
	['collée à la fin du libellé', '<label for="t">Titre *</label>', 1],
	['calculée en chaîne', "<label>{libelle}{requis ? ' *' : ''}</label>", 1],
	['collée au contrôle qui suit', '<label class="field">Question *<input /></label>', 1],
	['en fin de ligne, libellé enveloppant', '<label class="field">\n\tTitre *\n\t<input />', 1],
	[
		'EtoileRequis dans un <span>',
		'<label class="field"><span>Titre<EtoileRequis vide={!t} /></span><input /></label>',
		0,
	],
	['multiplication dans le script', '<script>\nconst a = b *\n2;\n</script>\n<p>ok</p>', 0],
	//  Les quatre formes de l'audit du 25/09/2026 (#1329).
	['`</label` coupé par Prettier', '<label for="r">Réponse *</label\n>', 1],
	['autre nom dans la chaîne', "<label>{libelle}{titreRequis ? ' *' : ''}</label>", 1],
	[
		'après une expression, en fin de ligne',
		'<label class="field">\n\t{libelleFichier} *\n\t<input />',
		1,
	],
	['seule dans un <span> stylé', 'Précisez <span style="color:red">*</span>', 1],
];

/** Toutes les formes refusées, pour une source. */
export function etoiles(brut) {
	return [...etoilesEnLigne(brut), ...etoilesFinDeLigne(brut)];
}
