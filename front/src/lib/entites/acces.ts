/**
 * L'ACCÈS du parc — un badge Vigik, une télécommande —, déclaré une fois : les
 * sections du cadre, ce qu'elles portent, et pourquoi huit sont sans objet
 * (#1329, 27/09/2026).
 *
 * ## Pourquoi maintenant
 *
 * `FormulaireAcces` rangeait ses sections dans SON ordre — Type · Code · Lot et
 * porteur · Accès · État · Affaire liée —, justifié par un commentaire (« ce
 * qui identifie l'objet d'abord »). C'était l'ordre d'un écran, pas celui du
 * cadre : Titre avant Nature, Suivi avant Périmètre, Au nom de en fin. Arbitré
 * par Philippe le 27/09/2026 : **l'ordre du cadre**, comme partout ailleurs.
 *
 * ## Les correspondances
 *
 * | Section du cadre | À l'écran | Pourquoi elle |
 * |---|---|---|
 * | Titre | Code | la référence gravée IDENTIFIE l'objet, comme un titre |
 * | Nature | Type | Vigik ou télécommande : ce que l'objet EST |
 * | Suivi | État | Actif · Suspendu · Perdu : où en est l'objet |
 * | Périmètre | Accès | ce que l'objet ouvre — un accès EST un périmètre |
 * | Affaires liées | Affaire liée | l'affaire dont le geste relève |
 * | Au nom de | Lot et porteur | à qui l'objet appartient, et qui l'a en main |
 *
 * ## Qui consomme cette déclaration
 *
 *   • `FormulaireAcces.svelte` — la saisie (`sectionPresente`, `pliageDe`)
 *   • `BadgesCopropriete.svelte` — le bouton d'ouverture
 */

import type { EntiteDeclaree } from './types';

export const ACCES: EntiteDeclaree = {
	id: 'acces',
	libelle: 'Accès',
	libelleNouveau: 'Enregistrer un accès',
	libelleModifier: "Corriger l'accès",
	sections: [
		{
			id: 'titre',
			objet: 'La référence gravée sur l’objet',
			requis: true,
			titreEcran: ['Code'],
		},
		{
			id: 'nature',
			objet: 'Vigik ou télécommande',
			requis: true,
			titreEcran: ['Type'],
			absente: {
				edition: {
					motif: 'geste',
					explication:
						"Le type IDENTIFIE l'objet : un badge ne devient pas une télécommande. Une " +
						'saisie fautive se retire (administrateur) et se refait.',
				},
			},
		},
		{
			id: 'equipement',
			sansObjet:
				'Un accès ouvre des lieux — c’est son périmètre —, il n’entretient aucun équipement.',
		},
		{
			id: 'suivi',
			objet: 'Actif · Suspendu · Perdu',
			//  Toujours valué (« Actif » à la création) : obligatoire, donc déplié.
			requis: true,
			titreEcran: ['État'],
		},
		{
			id: 'quand',
			sansObjet:
				"Un accès n'est pas un fait daté : il est en service, suspendu ou perdu. Ce qui " +
				"lui arrive se lit dans le fil de l'affaire liée.",
		},
		{
			id: 'intervenant',
			sansObjet: 'Personne n’intervient sur un badge : il est remis, suspendu ou déclaré perdu.',
		},
		{
			id: 'perimetre',
			objet: 'Ce que l’accès ouvre — restreint par type, par le serveur',
			titreEcran: ['Accès'],
			//  Facultatif (déduit du lot s'il est laissé vide) : plié. Une valeur
			//  saisie le rouvre d'office (`SectionFormulaire`).
			pliee: true,
		},
		{
			id: 'description',
			sansObjet:
				'Un accès se dit par son type, son code et ce qu’il ouvre ; un commentaire libre ' +
				'en ferait une seconde source, que personne ne tiendrait à jour.',
		},
		{
			id: 'pieces_jointes',
			sansObjet: 'Un badge ne se photographie pas ; un justificatif appartient à l’affaire liée.',
		},
		{
			id: 'affaires_liees',
			objet: 'Le numéro de l’affaire (TK-…) dont le geste relève',
			titreEcran: ['Affaire liée'],
			pliee: true,
		},
		{
			id: 'au_nom_de',
			objet: 'Le lot (le badge lui appartient) et qui l’a en main — l’un ou l’autre',
			requis: true,
			titreEcran: ['Lot et porteur'],
		},
		{
			id: 'destinataires',
			requis: true,
			sansObjet:
				"Personne n'est destinataire d'une ligne du parc. Qui la voit relève des droits, " +
				'pas de la saisie — la sécurité est centralisée.',
		},
		{
			id: 'mise_en_avant',
			sansObjet: 'Une ligne du parc ne se met pas en avant : le parc se lit par filtre.',
		},
		{
			id: 'diffusion',
			sansObjet:
				"Le porteur désigné est prévenu dans l'application, d'office : ce n'est pas une " +
				'diffusion qu’on choisit.',
		},
	],
};
