//  Le MODÈLE du formulaire d'un contrat d'entretien — sa forme vide, sa forme
//  chargée depuis un contrat, et la charge utile envoyée à l'API.
//
//  ## Pourquoi ce fichier (11/09/2026)
//
//  `prestataires/+page.svelte` portait le littéral des treize champs **deux
//  fois**, à 430 lignes d'écart : une fois à la déclaration de `contratForm`,
//  une fois dans `resetContratForm()`. Identiques — donc rien n'empêchait la
//  troisième, ni la divergence au premier champ ajouté. C'est le motif que ce
//  dépôt connaît le mieux : personne n'a décidé que le même objet aurait deux
//  écritures, ce sont les deux copies qui l'ont produit.
//
//  ⚠️ Le contrôle de modularité (rang 1) a refusé que la page grossisse d'une
//  ligne de plus. Trois réponses sont possibles (`ux-patterns` §0) — découper,
//  remonter la règle d'un cran, ou raboter. **Raboter n'en est jamais une.**
//  Ici la bonne est la deuxième : ces trois fonctions ne parlent pas de l'écran,
//  elles parlent du contrat.
//
//  🔴 Ce module ne connaît NI le client d'API, NI les composants : il transforme
//  des objets, et rien d'autre. C'est ce qui le rend lisible seul — et ce qui
//  permettra de l'éprouver le jour où le front aura un exécuteur de tests
//  unitaires (il n'en a pas aujourd'hui : les garde-fous y sont des scripts
//  d'analyse, pas des tests).
import { perimetreDefautListe } from '$lib/perimetres';
import { typeEquipementDuContrat } from '$lib/reporting';

/**  Ce que le formulaire manipule. Volontairement en CHAÎNES pour les nombres :
 *   ce sont des `<input>`, et convertir à la saisie ferait disparaître le champ
 *   vide (`''` devient `0`, qui s'affiche). La conversion se fait une fois, à
 *   l'envoi — voir `payloadContrat`. */
export interface ContratForm {
	copropriete_id: number;
	perimetre_cible: string[];
	prestataire_id: string;
	type_equipement: string;
	libelle: string;
	numero_contrat: string;
	date_debut: string;
	duree_initiale_valeur: number | string;
	duree_initiale_unite: string;
	frequence_type: string;
	frequence_valeur: number | string;
	prochaine_visite: string;
	notes: string;
}

/**  Le formulaire d'un contrat qui n'existe pas encore. */
export function contratFormVide(): ContratForm {
	return {
		copropriete_id: 1,
		//  Le PÉRIMÈTRE remplace `batiment_id`, qui n'était rempli par aucun champ
		//  (10/09/2026). Le serveur en dérive le bâtiment.
		perimetre_cible: perimetreDefautListe(),
		prestataire_id: '',
		type_equipement: 'autre',
		libelle: '',
		numero_contrat: '',
		//  `toISOString()` SEUL est autorisé par `lint:dates` : c'est une
		//  sérialisation UTC pour un `<input type="date">`, pas un affichage.
		date_debut: new Date().toISOString().slice(0, 10),
		duree_initiale_valeur: '',
		duree_initiale_unite: 'mois',
		frequence_type: '',
		frequence_valeur: '',
		prochaine_visite: '',
		notes: '',
	};
}

/**  Le formulaire chargé depuis un contrat existant, pour le corriger. */
export function contratFormDepuis(c: any, prestataires: any[]): ContratForm {
	return {
		copropriete_id: c.copropriete_id,
		perimetre_cible: c.perimetre_cible?.length ? c.perimetre_cible : perimetreDefautListe(),
		prestataire_id: String(c.prestataire_id ?? ''),
		//  La règle vit dans `reporting.ts` — elle était écrite dans l'écran, dans
		//  le groupement des cartes et dans le chargement du formulaire, avec trois
		//  résultats différents sur le même contrat (29/08/2026).
		type_equipement: typeEquipementDuContrat(c, prestataires),
		libelle: c.libelle,
		numero_contrat: c.numero_contrat ?? '',
		date_debut: c.date_debut,
		duree_initiale_valeur: c.duree_initiale_valeur ?? '',
		duree_initiale_unite: c.duree_initiale_unite ?? 'mois',
		frequence_type: c.frequence_type ?? '',
		frequence_valeur: c.frequence_valeur ?? '',
		prochaine_visite: c.prochaine_visite ?? '',
		notes: c.notes ?? '',
	};
}

/**  La charge utile envoyée à l'API — chaînes vides converties en `null`.
 *
 *   ⚠️ `duree_initiale_unite` ne part QUE si une valeur l'accompagne : « mois »
 *   sans nombre ne décrit aucune durée, et le stocker donnerait une unité
 *   orpheline que l'échéance lirait comme une donnée. */
export function payloadContrat(form: ContratForm, prestataires: any[]) {
	const prestataireId = Number(form.prestataire_id);
	return {
		...form,
		type_equipement: typeEquipementDuContrat(
			{ ...form, prestataire_id: prestataireId },
			prestataires,
		),
		prestataire_id: prestataireId,
		duree_initiale_valeur: form.duree_initiale_valeur ? Number(form.duree_initiale_valeur) : null,
		duree_initiale_unite: form.duree_initiale_valeur ? form.duree_initiale_unite : null,
		frequence_type: form.frequence_type || null,
		frequence_valeur: form.frequence_valeur ? Number(form.frequence_valeur) : null,
		prochaine_visite: form.prochaine_visite || null,
	};
}

/**  Les contrats triés par échéance — ceux qui n'en ont pas passent en dernier.
 *
 *   ⚠️ Un contrat sans `prochaine_visite` n'est pas « le plus lointain » : il est
 *   HORS classement. Le trier comme une date vide le placerait en tête, c'est-à-dire
 *   là où l'œil cherche ce qui est urgent.
 *
 *   Remonté ici depuis l'écran le 11/09/2026, avec le reste de ce qui parle du
 *   contrat et non de la page (`ux-patterns` §0 : *remonter la règle d'un cran*).
 */
export function parEcheance(liste: any[]): any[] {
	return [...liste].sort((a, b) => {
		if (!a.prochaine_visite && !b.prochaine_visite) return 0;
		if (!a.prochaine_visite) return 1;
		if (!b.prochaine_visite) return -1;
		return a.prochaine_visite < b.prochaine_visite ? -1 : 1;
	});
}
