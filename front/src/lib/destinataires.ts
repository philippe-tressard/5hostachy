/**
 * Le vocabulaire du PUBLIC CIBLE — « à qui ça s'adresse ? » — écrit une fois.
 *
 * Il vivait dans `DestinatairePicker.svelte`, donc uniquement dans le
 * SÉLECTEUR : rien ne permettait d'afficher un ciblage ailleurs sans recopier la
 * table. C'est ce qui s'est passé sur la liste des sondages, qui affichait les
 * valeurs BRUTES de la base (« copropriétaire_résident ») dans ses badges.
 *
 * Même partage que `$lib/perimetres.ts` pour l'axe géographique : le sélecteur
 * et l'affichage lisent la même liste, et une valeur ajoutée ici se dit des deux
 * côtés sans qu'on y pense.
 *
 * ⚠️ Les codes sont ceux du serveur (`app/utils/visibility.py`,
 * `CODES_PUBLIC_CIBLE` et `public_cible_visible`). Rien dans le code n'oblige
 * les deux côtés à rester d'accord, et un écart est SILENCIEUX : un code proposé
 * ici mais inconnu du serveur rend la publication invisible de tous, puisque la
 * règle refuse ce qu'elle ne reconnaît pas. C'est
 * `api/tests/test_destinataires_vocabulaire.py` qui lit les deux fichiers et
 * exige le même vocabulaire, dans le même ordre — il a d'ailleurs trouvé que la
 * règle serveur n'honorait pas `conseil_syndical` par elle-même.
 */

/** Ce que « rien de précisé » veut dire. Vide et `['résidents']` sont équivalents. */
export const TOUS_LES_RESIDENTS = 'résidents';

export type Destinataire = { code: string; libelle: string; icone: string };

export const DESTINATAIRES: Destinataire[] = [
	{ code: 'copropriétaires', libelle: 'Copropriétaires', icone: 'key-round' },
	//  `home` pour l'occupant (il y habite), `building-2` pour le bailleur (il le
	//  loue). Les deux existent au catalogue `$lib/icones-svg.json` — un nom
	//  inconnu y retombe SILENCIEUSEMENT sur `help-circle`.
	{ code: 'copropriétaires_occupants', libelle: 'Copropriétaires occupants', icone: 'home' },
	{ code: 'bailleurs', libelle: 'Bailleurs', icone: 'building-2' },
	{ code: 'locataires', libelle: 'Locataires', icone: 'user' },
	{ code: 'conseil_syndical', libelle: 'Conseil syndical', icone: 'shield-check' },
];

const PAR_CODE = new Map(DESTINATAIRES.map((d) => [d.code, d]));

/** Le ciblage vise-t-il tout le monde ? Vide ou `résidents` = oui. */
export function concerneTousLesResidents(codes: string[] | null | undefined): boolean {
	if (!codes || codes.length === 0) return true;
	return codes.length === 1 && codes[0] === TOUS_LES_RESIDENTS;
}

/**
 * Libellé affichable d'un public cible.
 *
 * Accepte un tableau OU une chaîne JSON — c'est ce que rend l'API, et faire la
 * conversion chez chaque appelant est exactement la recopie qu'on évite ici.
 * Une valeur inconnue est rendue telle quelle : mieux vaut un code brut qu'un
 * badge vide, qui laisserait croire à « tout le monde ».
 *
 * Séparateur ` · `, le même que `perimetreLabel` — deux ciblages voisins doivent
 * se lire de la même façon.
 */
export function destinatairesLabel(valeur: string[] | string | null | undefined): string {
	let codes: string[];
	if (Array.isArray(valeur)) {
		codes = valeur;
	} else if (typeof valeur === 'string' && valeur.trim()) {
		try {
			const parse = JSON.parse(valeur);
			codes = Array.isArray(parse) ? parse.map(String) : [];
		} catch {
			//  Ancien format CSV, ou donnée abîmée : on rend ce qu'on a plutôt que rien.
			codes = valeur.split(',').map((v) => v.trim()).filter(Boolean);
		}
	} else {
		codes = [];
	}
	if (concerneTousLesResidents(codes)) return 'Tous les résidents';
	return codes.map((c) => PAR_CODE.get(c)?.libelle ?? c).join(' · ');
}
