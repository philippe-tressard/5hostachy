/**
 * **Les champs d'un locataire sur un bail** — saisis à la création, corrigés
 * ensuite.
 *
 * ## 🔴 Pourquoi ce module (15/09/2026)
 *
 * `mon-lot/+page.svelte` énumérait ces champs **quatre fois** : la déclaration
 * du bail neuf, sa remise à zéro après enregistrement, la déclaration de
 * l'édition, et son remplissage depuis un bail existant.
 *
 * Ce n'est pas quatre fois la même ligne, c'est **deux structures écrites deux
 * fois chacune** — et ajouter un champ demandait de le poser aux quatre
 * endroits. Un champ manqué à l'un des quatre donne un formulaire qui
 * enregistre à la création et oublie à la correction, **en silence** : une clé
 * absente d'un objet JavaScript ne lève rien.
 *
 * ## Les deux structures, et ce qui les sépare
 *
 * `date_entree` ne figure que dans le bail **neuf**. Ce n'est pas un oubli :
 * elle se saisit à l'entrée du locataire et ne se corrige pas depuis cet
 * écran — la déplacer demanderait de décaler un bail, pas de rectifier une
 * coordonnée. La différence est donc **déclarée** par la forme des deux
 * fonctions, au lieu d'être devinée en comparant deux listes.
 */

/** Ce qui identifie et joint un locataire — commun aux deux gestes. */
export interface ChampsLocataire {
	locataire_nom: string;
	locataire_prenom: string;
	locataire_email: string;
	locataire_telephone: string;
	date_sortie_prevue: string;
	notes: string;
}

/** Un bail qu'on CRÉE : les champs du locataire, plus sa date d'entrée. */
export interface ChampsBailNeuf extends ChampsLocataire {
	date_entree: string;
}

/** Ce qu'un bail existant porte de son locataire — vide s'il n'y en a pas. */
type SourceBail = Partial<Record<keyof ChampsLocataire, string | null>> | null | undefined;

/**
 * Les champs du locataire, repris d'un bail ou vides.
 *
 * ⚠️ Tous présents, y compris vides : ce sont eux que le formulaire lie, et une
 * clé absente ferait un champ non contrôlé — Svelte lie alors `undefined`, et
 * l'`<input>` passe en non-contrôlé sans que rien ne le dise.
 */
export function champsLocataire(bail?: SourceBail): ChampsLocataire {
	return {
		locataire_nom: bail?.locataire_nom ?? '',
		locataire_prenom: bail?.locataire_prenom ?? '',
		locataire_email: bail?.locataire_email ?? '',
		locataire_telephone: bail?.locataire_telephone ?? '',
		date_sortie_prevue: bail?.date_sortie_prevue ?? '',
		notes: bail?.notes ?? '',
	};
}

/** Un bail NEUF, vierge. */
export function bailVierge(): ChampsBailNeuf {
	return { ...champsLocataire(), date_entree: '' };
}
