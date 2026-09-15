/**
 * **Pré-remplir une actualité depuis une annonce de hall** (#832).
 *
 * Le miroir exact du mécanisme de `FormulaireAnnonceHall`, qui propose
 * « Pré-remplir depuis une actualité » depuis le 01/09/2026 : le conseil
 * syndical compose souvent l'affiche d'abord, et le geste n'existait que dans un
 * sens.
 *
 * ## Pourquoi un module (15/09/2026)
 *
 * Sorti de `FormulaireActualite.svelte` au fil de l'eau, le plafond de
 * modularité ayant refusé que le formulaire grossisse pour accueillir la section
 * « Saisi pour ». La couture existait déjà : ce bloc ne partage rien avec le
 * reste du formulaire sinon les champs qu'il remplit, et il porte **trois**
 * décisions qui lui sont propres.
 *
 * ## Les trois décisions
 *
 * 1. **Non bloquant.** Si la liste des annonces ne vient pas, la saisie libre
 *    reste possible et le sélecteur ne s'affiche simplement pas. Une erreur ici
 *    empêcherait de publier pour un raccourci dont on peut se passer.
 * 2. **Les plus récentes d'abord, et pas toutes** — un sélecteur de cent lignes
 *    ne se lit pas.
 * 3. **Uniquement en CRÉATION.** Pré-remplir une actualité qu'on corrige
 *    écraserait le texte publié : l'écran de correction n'a pas à proposer un
 *    geste qui défait ce qu'il sert à ajuster. Le garde est chez l'appelant, qui
 *    seul sait s'il crée ou corrige.
 */
import type { AnnonceHall } from '$lib/api';
//  🔴 Le plafond vient de `$lib/publications`, où il vivait déjà : le
//  redéclarer ici en aurait fait une seconde valeur, libre de diverger.
import { MAX_SOURCES_PREREMPLISSAGE } from '$lib/publications';

/**
 * Les annonces proposables — les plus récentes, et jamais une erreur.
 *
 * :param lister: l'appel d'API, passé par l'appelant : ce module ne choisit pas
 *   quelles annonces sont visibles, c'est une question de droits.
 */
export async function annoncesProposables(
	lister: () => Promise<AnnonceHall[]>,
): Promise<AnnonceHall[]> {
	try {
		const liste = await lister();
		return [...liste]
			.sort((a, b) => new Date(b.cree_le).getTime() - new Date(a.cree_le).getTime())
			.slice(0, MAX_SOURCES_PREREMPLISSAGE);
	} catch {
		return [];
	}
}

/** Ce que le pré-remplissage RAPPORTE — les champs du formulaire, et rien d'autre. */
export interface PrefillActualite {
	titre: string;
	contenu: string;
	perimetreCible: string[];
	photos: string[];
	/** Le message à afficher — il dépend du nombre d'images reprises. */
	message: string;
}

/**
 * Compose le message de confirmation.
 *
 * ⚠️ Il NOMME le nombre d'images reprises : sans lui, le rédacteur découvre en
 * publiant que l'affiche en portait cinq. Le pluriel est accordé — un « 1
 * images » se remarque plus qu'on ne croit.
 */
export function messagePrefill(nbPhotos: number): string {
	return nbPhotos > 0
		? `Actualité pré-remplie (${nbPhotos} image${nbPhotos > 1 ? 's' : ''}) — ajustez avant de publier`
		: 'Actualité pré-remplie — ajustez le texte avant de publier';
}
