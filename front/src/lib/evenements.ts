//  Le MODÈLE du formulaire d'un événement de calendrier — sa forme vierge et sa
//  forme chargée depuis un événement existant.
//
//  ## Pourquoi ce fichier (15/09/2026)
//
//  `calendrier/+page.svelte` portait le littéral des seize champs **deux fois** :
//  `formulaireVierge()` et le corps de `startEdit()`, à deux cents lignes
//  d'écart. Le commentaire de la première le disait lui-même — *« la duplication
//  que le plafond de modularité a fait remonter »* — mais la remontée s'était
//  arrêtée à mi-chemin : la fonction avait été extraite de ses deux appels, pas
//  de son jumeau de lecture.
//
//  ⚠️ La page est à 864 lignes ; le garde-fou (rang 1) refusait donc d'y ajouter
//  la moindre ligne pour « Saisi pour ». Des trois réponses possibles
//  (`ux-patterns` §0), c'est la deuxième qui s'imposait : **remonter la règle
//  d'un cran**. Ces deux fonctions ne parlent pas de l'écran, elles parlent de
//  l'événement.
//
//  ⚠️ **Des FONCTIONS, pas des constantes** : un objet partagé serait muté par le
//  premier `bind:`, et le « vierge » cesserait de l'être.
//
//  ⚠️ **Tous les champs y figurent, y compris les booléens.** Un champ absent
//  n'existe pas dans le type inféré de `form`, et tous ses usages passent en
//  erreur TypeScript.

/** Ce que le formulaire manipule. Les nombres sont des CHAÎNES : ce sont des
 *  `<input>`, et convertir à la saisie ferait disparaître le champ vide. */
export interface EvenementForm {
	titre: string;
	description: string;
	type: string;
	lieu: string;
	debut: string;
	debut_heure: string;
	fin: string;
	statut_kanban: string;
	prestataire_id: string;
	frequence_type: string;
	frequence_valeur: string;
	affichable: boolean;
	epingle: boolean;
	reserve_cs: boolean;
	partager_whatsapp: boolean;
	envoyer_syndic: boolean;
	envoyer_cs: boolean;
	//  « Saisi pour » — écrits par `SectionSaisiPour`, qui mute l'objet lié.
	//  📖 `$lib/saisiPour` pour les deux conversions.
	saisi_pour_user_id: number | null;
	saisi_pour_nom: string | null;
	saisi_pour_email: string | null;
}

/** Le formulaire d'un événement qui n'existe pas encore. */
export function formulaireVierge(debut = ''): EvenementForm {
	return {
		titre: '',
		description: '',
		type: 'autre',
		lieu: '',
		debut,
		debut_heure: '',
		fin: '',
		statut_kanban: '',
		prestataire_id: '',
		frequence_type: '',
		frequence_valeur: '',
		affichable: true,
		epingle: false,
		reserve_cs: false,
		partager_whatsapp: false,
		envoyer_syndic: false,
		envoyer_cs: false,
		saisi_pour_user_id: null,
		saisi_pour_nom: null,
		saisi_pour_email: null,
	};
}

/** Le formulaire chargé depuis un événement existant, pour le corriger. */
export function formulaireDepuis(ev: any): EvenementForm {
	return {
		titre: ev.titre,
		description: ev.description ?? '',
		type: ev.type,
		lieu: ev.lieu ?? '',
		debut: ev.debut?.slice(0, 10) ?? '',
		debut_heure: ev.debut?.slice(11, 16) ?? '',
		fin: ev.fin?.slice(0, 16) ?? '',
		statut_kanban: ev.statut_kanban ?? '',
		prestataire_id: ev.prestataire_id ? String(ev.prestataire_id) : '',
		frequence_type: ev.frequence_type ?? '',
		frequence_valeur: ev.frequence_valeur ? String(ev.frequence_valeur) : '',
		affichable: ev.affichable ?? true,
		epingle: ev.epingle ?? false,
		reserve_cs: ev.reserve_cs ?? false,
		partager_whatsapp: ev.partager_whatsapp ?? false,
		envoyer_syndic: ev.envoyer_syndic ?? false,
		envoyer_cs: ev.envoyer_cs ?? false,
		saisi_pour_user_id: ev.saisi_pour_user_id ?? null,
		saisi_pour_nom: ev.saisi_pour_nom ?? null,
		saisi_pour_email: ev.saisi_pour_email ?? null,
	};
}
