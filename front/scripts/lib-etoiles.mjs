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
			if (/ \*<\/(label|span)>/.test(ligne) || /\{requis \? ' \*' : ''\}/.test(ligne)) {
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
//  dans neuf fichiers : plafond décroissant, comme `lint:confirmation` ; la
//  conversion des quatorze restantes est suivie par #1254.
//  Seul le BALISAGE est lu — dans un `<script>`, « a * » en fin de ligne est une
//  multiplication.
export const PLAFOND_ETOILES_FIN_DE_LIGNE = 14;

/** Astérisques en fin de ligne d'un libellé, dans le balisage seul. */
export function etoilesFinDeLigne(brut) {
	const source = sansCommentaires(brut);
	const debut = source.lastIndexOf('</script>');
	const decalage = debut >= 0 ? source.slice(0, debut).split('\n').length - 1 : 0;
	const fautes = [];
	(debut >= 0 ? source.slice(debut) : source).split('\n').forEach((ligne, i) => {
		if (/[A-Za-zÀ-ÿ)'’/] \*\s*$/.test(ligne) && !/^\s*\*/.test(ligne)) {
			fautes.push({ ligne: decalage + i + 1, texte: ligne.trim().slice(0, 70) });
		}
	});
	return fautes;
}
