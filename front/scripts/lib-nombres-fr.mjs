/**
 * Les nombres d'une prose française — en chiffres ou en toutes lettres (#1541).
 *
 * Deux contrôles confrontent un nombre ÉCRIT à un compte LU dans le code :
 * `lint:consignes` (aucune consigne ne recopie le nombre de sections) et
 * `lint:manuel-profils` (le titre de la table du manuel dit le bon nombre). Ils
 * lisent les mêmes mots : la table est ici, une fois.
 *
 * ⚠️ De deux à vingt seulement. « un » est un article et « zéro » ne compte
 * rien : les accepter ferait lire un nombre dans chaque phrase. Au-delà de
 * vingt, une consigne n'écrit plus un compte en lettres.
 */

const EN_LETTRES = [
	'deux',
	'trois',
	'quatre',
	'cinq',
	'six',
	'sept',
	'huit',
	'neuf',
	'dix',
	'onze',
	'douze',
	'treize',
	'quatorze',
	'quinze',
	'seize',
	'dix-sept',
	'dix-huit',
	'dix-neuf',
	'vingt',
];

/** Les mots en lettres, les plus longs d'abord : sinon « dix » est lu dans
 *  « dix-sept », et le compte rendu est faux. */
export const MOTS_NOMBRES = [...EN_LETTRES].sort((a, b) => b.length - a.length);

/**
 * Un nombre isolé — pas un numéro de ticket (`#1342`), un paragraphe (`§12`),
 * un morceau de date (`26/09`) ni de version (`2.91`).
 *
 * @param {{ chiffres?: boolean }} [options]  `chiffres: false` pour les seuls mots
 * @returns {string} source d'expression rationnelle, avec un groupe capturant
 */
export function motifNombre({ chiffres = true } = {}) {
	const alternatives = [...MOTS_NOMBRES, ...(chiffres ? ['\\d{1,3}'] : [])].join('|');
	return `(?<![\\p{L}\\d#§/.,-])(${alternatives})(?![\\p{L}\\d/.,-])`;
}

/** La valeur d'un nombre lu par `motifNombre`, ou `null`. */
export function valeurNombre(texte) {
	const t = texte.toLowerCase();
	if (/^\d+$/.test(t)) return Number(t);
	const rang = EN_LETTRES.indexOf(t);
	return rang < 0 ? null : rang + 2;
}
