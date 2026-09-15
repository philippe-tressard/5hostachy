//  **« SAISI POUR »** — au nom de qui le conseil syndical dépose un objet.
//
//  En son nom, pour un résident inscrit, ou pour une personne extérieure. La
//  saisie vit dans `ChampSaisiPour.svelte` ; ce module porte les **deux
//  conversions** qui l'entourent, et rien d'autre :
//
//    objet chargé   → mode        (`modeDepuis`)
//    mode + valeurs → charge utile (`chargeUtile`)
//
//  ## 🔴 Pourquoi il existe (15/09/2026)
//
//  Ces deux conversions n'étaient écrites qu'une fois, dans
//  `FormulaireTicket.svelte`. En ouvrant « Saisi pour » aux actualités et au
//  calendrier, elles allaient l'être **trois fois** — et trois écritures d'une
//  même règle divergent au premier ajout. C'est le motif que ce dépôt connaît le
//  mieux : les destinataires CS en ont compté quatre, dont un qui affirmait être
//  le seul endroit où la règle s'écrivait.
//
//  La règle monte donc d'un cran AVANT la copie, pas après — et le formulaire de
//  ticket l'emploie lui aussi, sans quoi la factorisation aurait créé la
//  deuxième écriture qu'elle prétendait supprimer.
//
//  📖 Pendant serveur : `api/app/utils/saisi_pour.py`.

/** Les trois façons de déposer. Vivait dans `$lib/tickets`, qui la réexporte. */
export type ModeSaisiPour = 'moi' | 'resident' | 'exterieur';

/** Ce que porte un objet déjà enregistré. */
export interface SaisiPourValeurs {
	saisi_pour_user_id?: number | null;
	saisi_pour_nom?: string | null;
	saisi_pour_email?: string | null;
}

/**
 * Le mode que décrit un objet chargé — `'moi'` quand il n'en porte aucun.
 *
 * ⚠️ Le résident inscrit PRIME sur le nom libre, comme côté serveur : quand les
 * deux sont posés, c'est le compte qui fait foi, puisque c'est lui qui porte le
 * droit de correction. Les deux écritures d'une même règle doivent dire la même
 * chose jusque dans leurs cas limites, sinon les comparer ne prouve rien.
 */
export function modeDepuis(objet: SaisiPourValeurs | null | undefined): ModeSaisiPour {
	if (objet?.saisi_pour_user_id) return 'resident';
	if (objet?.saisi_pour_nom) return 'exterieur';
	return 'moi';
}

/**
 * Les trois champs à transmettre, **toujours les trois**, quitte à `null`.
 *
 * 🔴 C'est leur PRÉSENCE qui dit au serveur d'écrire, et c'est elle qui permet
 * de revenir à « En mon nom ». Omettre un champ remis à vide le laisserait
 * inchangé en base : le choix resterait sans effet, en silence. C'est très
 * exactement la dette qui a tenu ce champ fermé en édition sur les tickets
 * jusqu'au 18/08/2026.
 *
 * ⚠️ Et les trois voyagent ENSEMBLE. N'en réécrire que deux laisserait le nom
 * d'une personne extérieure survivre au résident inscrit désigné depuis.
 */
export function chargeUtile(
	mode: ModeSaisiPour,
	userId: number | null,
	nom: string,
	email: string,
): Required<SaisiPourValeurs> {
	return {
		saisi_pour_user_id: mode === 'resident' ? userId : null,
		saisi_pour_nom: mode === 'exterieur' ? nom.trim() || null : null,
		saisi_pour_email: mode === 'exterieur' ? email.trim() || null : null,
	};
}

/**
 * La saisie est-elle complète ? Rend le message à afficher, ou `null`.
 *
 * Une personne extérieure sans nom ne désigne personne — et laisserait la
 * mention « Saisi pour » vide à l'affichage.
 */
export function motifIncomplet(
	mode: ModeSaisiPour,
	userId: number | null,
	nom: string,
): string | null {
	if (mode === 'exterieur' && !nom.trim()) return 'Le nom de la personne extérieure est requis';
	if (mode === 'resident' && !userId) return 'Sélectionnez le résident concerné';
	return null;
}
