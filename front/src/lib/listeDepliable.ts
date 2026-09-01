/**
 * LA MÉCANIQUE d'une liste de cartes dépliables et éditables — écrite une fois.
 *
 * ## 🔴 Pourquoi (01/09/2026, #640)
 *
 * `espace-cs` portait cette mécanique **deux fois**, à l'identifiant près : une
 * pour les membres du conseil syndical (`csOpenIdx` / `csEditIdx`), une pour ceux
 * du syndic (`syndicOpenIdx` / `syndicEditIdx`). Les deux fonctions de retrait
 * étaient **littéralement identiques** :
 *
 *     function removeMembreCS(i) {
 *       membresCS = membresCS.filter((_, j) => j !== i);
 *       if (csOpenIdx === i) { csOpenIdx = null; csEditIdx = null; }
 *       else if (csOpenIdx !== null && csOpenIdx > i) csOpenIdx--;
 *       if (csEditIdx !== null && csEditIdx !== i && csEditIdx > i) csEditIdx--;
 *     }
 *
 * Deux entités différentes — leurs champs n'ont rien à voir —, mais **le même
 * comportement** : on déplie une carte, on la passe en édition, on en ajoute une
 * qui s'ouvre déjà éditable, on en retire une et les index des suivantes glissent.
 *
 * ⚠️ Le décalage d'index est la partie **subtile**, et c'est celle qu'on recopie
 * sans la relire. Elle est ici pure, donc éprouvée par
 * `scripts/check-liste-depliable.mjs --selftest`, en CI.
 *
 * ## Ce que la version factorisée corrige au passage
 *
 * L'écriture dupliquée supposait, sans le dire, qu'on ne peut pas éditer une carte
 * sans l'avoir ouverte — vrai aujourd'hui, parce que le bouton « Modifier » pose
 * les deux ensemble. Si cette invariance cessait, `edite` resterait pointé sur une
 * carte supprimée et l'écran passerait en édition sur la voisine. La version
 * ci-dessous n'en dépend pas : elle traite `edite` pour lui-même.
 */

/** Quelle carte est dépliée, laquelle est en cours d'édition. */
export interface EtatDepliable {
	/** Index de la carte dépliée, ou `null`. */
	ouvert: number | null;
	/** Index de la carte en édition, ou `null`. Toujours dépliée aussi. */
	edite: number | null;
}

/** Rien d'ouvert, rien en édition — l'état de départ, et celui d'un rechargement. */
export const REPLIE: EtatDepliable = { ouvert: null, edite: null };

/**
 * Clic (ou Entrée / Espace) sur une carte : elle se déplie, ou se replie.
 *
 * ⚠️ Sans effet quand la carte est **en édition** : le clic servirait alors à
 * poser le curseur dans un champ, et replier la carte effacerait la saisie en
 * cours sans prévenir.
 */
export function basculer(etat: EtatDepliable, i: number): EtatDepliable {
	if (etat.edite === i) return etat;
	return { ouvert: etat.ouvert === i ? null : i, edite: etat.edite };
}

/** « Modifier » : la carte s'ouvre ET passe en édition — les deux vont ensemble. */
export function editer(i: number): EtatDepliable {
	return { ouvert: i, edite: i };
}

/** Fin d'édition : la carte reste dépliée, on relit ce qu'on vient d'écrire. */
export function terminerEdition(etat: EtatDepliable): EtatDepliable {
	return { ouvert: etat.ouvert, edite: null };
}

/**
 * Après un ajout : la nouvelle carte est la dernière, ouverte et éditable.
 *
 * `longueur` est celle de la liste **après** l'ajout — c'est ce dont l'appelant
 * dispose, et lui demander `longueur - 1` invite à l'erreur d'un cran.
 */
export function ajouter(longueur: number): EtatDepliable {
	return { ouvert: longueur - 1, edite: longueur - 1 };
}

/**
 * Après le retrait de la carte `i` : les index des suivantes glissent d'un cran.
 *
 * Trois cas, et le troisième est celui qu'on oublie :
 * 1. la carte retirée était ouverte ou éditée → plus rien ne l'est ;
 * 2. une carte **après** elle l'était → son index descend de 1 ;
 * 3. une carte **avant** elle l'était → rien ne bouge.
 */
export function retirer(etat: EtatDepliable, i: number): EtatDepliable {
	const glisser = (n: number | null): number | null => {
		if (n === null || n === i) return null;
		return n > i ? n - 1 : n;
	};
	return { ouvert: glisser(etat.ouvert), edite: glisser(etat.edite) };
}
