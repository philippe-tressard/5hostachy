/**
 * **« Saisi pour »** — au nom de qui une entrée est ouverte, côté écran.
 *
 * ## Pourquoi ce module (15/09/2026)
 *
 * La notion vivait dans le seul circuit des tickets. Son extension aux
 * **actualités** et aux **événements**, demandée à l'écran, aurait recopié deux
 * fois chacune de ses trois règles :
 *
 * 1. **quel mode** un objet déjà enregistré rouvre (`modeDepuis`) ;
 * 2. **ce qui part** vers l'API selon le mode (`lotSaisiPour`) ;
 * 3. quelles valeurs le formulaire remet à zéro.
 *
 * Aucune n'est évidente, et la deuxième est franchement contre-intuitive.
 *
 * ## ⚠️ Les trois champs partent TOUJOURS, y compris à `null`
 *
 * C'est leur **présence** dans la charge utile qui dit au serveur d'écrire
 * (`model_fields_set` côté Python, cf. `api/app/utils/saisi_pour.py`), et c'est
 * ce qui permet de revenir à « En mon nom » : sans elles, un `null` serait
 * indistinguable d'un champ non transmis, et le choix resterait sans effet — en
 * silence.
 *
 * ⚠️ Et le mode décide **lesquels** valent quelque chose : revenir d'« une
 * personne extérieure » à « un résident inscrit » doit effacer le nom saisi,
 * sinon un ancien destinataire survivrait à la personne qui le remplace.
 *
 * ## Le pendant serveur
 *
 * `api/app/utils/saisi_pour.py` — même notion, mêmes trois champs, et le mixin
 * dont héritent `Ticket`, `Publication` et `Evenement`. Les contextes de build
 * étant `./api` et `./front`, le partage d'un fichier est impossible (mémoire
 * `project_partage_front_api_impossible`) : ce sont deux écritures assumées
 * d'une même règle, et c'est le serveur qui tranche.
 */

/** En son nom, pour un résident inscrit, ou pour une personne extérieure. */
export type ModeSaisiPour = 'moi' | 'resident' | 'exterieur';

/** Ce qu'un objet déjà enregistré porte de « Saisi pour ». */
export interface PorteSaisiPour {
	saisi_pour_user_id?: number | null;
	saisi_pour_nom?: string | null;
	saisi_pour_email?: string | null;
}

/**
 * Le mode qu'un objet ROUVRE à l'édition.
 *
 * 🔴 L'ordre des deux tests n'est pas indifférent : un résident inscrit peut
 * avoir laissé un nom d'une saisie antérieure, et c'est l'identifiant qui fait
 * foi. L'inverse rouvrirait « personne extérieure » sur un ticket rattaché à un
 * compte.
 *
 * ⚠️ Rouvrir sur « En mon nom » par défaut effacerait le « Saisi pour » au
 * premier enregistrement — c'est pour cela que cette fonction existe plutôt
 * qu'un `'moi'` initial.
 */
export function modeDepuis(objet: PorteSaisiPour | null | undefined): ModeSaisiPour {
	if (objet?.saisi_pour_user_id) return 'resident';
	if (objet?.saisi_pour_nom) return 'exterieur';
	return 'moi';
}

/**
 * Ce qui part vers l'API — les **trois** champs, toujours.
 *
 * ⚠️ Ne jamais filtrer ce que cette fonction rend, ni l'étaler
 * conditionnellement : c'est la présence des trois clés qui permet d'effacer.
 */
export function lotSaisiPour(
	mode: ModeSaisiPour,
	userId: number | null,
	nom: string,
	email: string,
): Required<PorteSaisiPour> {
	return {
		saisi_pour_user_id: mode === 'resident' ? userId : null,
		saisi_pour_nom: mode === 'exterieur' ? nom.trim() || null : null,
		saisi_pour_email: mode === 'exterieur' ? email.trim() || null : null,
	};
}

/**
 * Les trois champs d'un formulaire, repris d'un objet existant ou vides.
 *
 * ⚠️ **Les trois sont toujours présents**, y compris pour une création : c'est
 * ce qui garantit qu'ils partiront vers l'API (`lotSaisiPour` en fait autant à
 * l'envoi), et donc qu'un retour à « En mon nom » soit enregistré.
 *
 * ⚠️ `saisi_pour_user_id` vaut `null` et non `''` — c'est un identifiant, et un
 * `''` envoyé à un champ entier serait refusé par le serveur.
 */
export function champsSaisiPour(
	objet: PorteSaisiPour | Record<string, unknown> | null | undefined,
): {
	saisi_pour_user_id: number | null;
	saisi_pour_nom: string;
	saisi_pour_email: string;
} {
	const o = (objet ?? {}) as PorteSaisiPour;
	return {
		saisi_pour_user_id: o.saisi_pour_user_id ?? null,
		saisi_pour_nom: o.saisi_pour_nom ?? '',
		saisi_pour_email: o.saisi_pour_email ?? '',
	};
}

import { comparerParNom } from '$lib/noms';

/** Une personne proposable dans le sélecteur « pour un résident inscrit ». */
export interface ResidentProposable {
	id: number;
	prenom: string;
	nom: string;
	email: string;
}

/**
 * Les résidents proposables — actifs, classés par nom de famille.
 *
 * ⚠️ **Ne lève jamais.** La section reste utilisable en « En mon nom » et pour
 * une personne extérieure : bloquer la saisie entière pour un défaut qui ne
 * concerne qu'un des trois modes coûterait plus qu'il ne protège.
 *
 * 🔴 Écrite ici parce que les trois formulaires en avaient besoin le même jour.
 * Recopiée, elle aurait divergé sur le tri — c'est précisément ce qui venait
 * d'arriver au classement des porteurs de badges.
 */
export async function chargerResidents(
	lister: () => Promise<unknown[]>,
): Promise<ResidentProposable[]> {
	try {
		const tous = (await lister()) as (ResidentProposable & { actif?: boolean })[];
		//  ⚠️ `comparerParNom` n'est PAS un paramètre : classer des personnes par
		//  nom de famille est la règle du site (`$lib/noms`), pas une option de
		//  l'appelant. La laisser choisir rouvrirait les cinq tris divergents que
		//  la centralisation vient de fermer.
		return tous.filter((u) => u.actif).sort(comparerParNom);
	} catch {
		return [];
	}
}
