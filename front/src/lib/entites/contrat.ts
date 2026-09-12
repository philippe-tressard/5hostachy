/**
 * Le CONTRAT d'entretien, déclaré une fois — les neuf sections, ce qu'elles
 * portent, et **chaque divergence entre états avec son motif** (R4).
 *
 * Septième entité du cadre #430, déclarée le 12/09/2026 sur signalement à
 * l'écran : *« l'édition de Contrats ne respecte pas l'UX — l'ordre des sections,
 * la séparation par un trait, l'intitulé des sections »* (#909).
 *
 * ## Pourquoi la déclaration vient AVANT le balisage
 *
 * `ChampsContrat` n'employait **aucune** `SectionFormulaire` : ni titre de
 * section, ni filet, ni ordre — quinze champs dans une seule grille. Réordonner
 * le balisage sans déclarer l'entité aurait produit un écran conforme *ce jour-là*
 * et rien pour le maintenir : c'est `lint:etats` qui refuse une section rendue
 * hors déclaration, et une absence non motivée.
 *
 * ## Ce que la déclaration a fait apparaître
 *
 * 🔴 **Quatre sections sur neuf sont sans objet ici, et aucune ne l'était par
 * hasard.** Les écrire oblige à dire pourquoi — et l'une d'elles, la Diffusion,
 * mérite d'être relue : un contrat signé n'est annoncé à personne aujourd'hui,
 * alors que son échéance concerne le conseil syndical. Ce n'est pas une omission
 * de ce lot, c'est une décision qui n'a jamais été prise.
 *
 * ⚠️ Le contrat n'a pas d'état `evolution` : il ne porte pas de fil. Ses
 * changements se lisent dans le **carnet d'entretien**, qui est une VUE sur trois
 * tables (`project_carnet_entretien`) — pas un historique de l'objet.
 *
 * ## Qui consomme cette déclaration
 *
 *   • `ChampsContrat.svelte` — la saisie (`sectionPresente`)
 */

import type { EntiteDeclaree } from './types';

export const CONTRAT: EntiteDeclaree = {
	id: 'contrat',
	libelle: "Contrat d'entretien",
	sections: [
		{
			id: 'titre',
			objet: 'Titre',
			requis: true,
		},
		{
			id: 'specifiques',
			objet:
				'Prestataire · Équipement · N° de contrat · Début · Durée · Fréquence · Prochaine visite',
			requis: true,
			//  L'intitulé rendu à l'écran : « Champs spécifiques » est le nom du
			//  CADRE, pas ce qu'un gestionnaire lit. `lint:etats` exige qu'il soit
			//  déclaré ici plutôt qu'inventé dans le balisage — sinon deux écrans
			//  nomment différemment la même section.
			titreEcran: ['Le contrat'],
		},
		{
			id: 'workflow',
			sansObjet:
				"Un contrat n'a pas d'états à parcourir : il court, ou son échéance est passée. " +
				"C'est une DATE qui le dit, pas un statut qu'on déplace à la main — et une date " +
				"ne se trompe pas d'un clic. Le carnet d'entretien s'en sert pour ranger les " +
				'contrats en cours et les contrats échus.',
		},
		{
			id: 'perimetre',
			objet: 'PerimetrePicker — ce que le contrat entretient',
			//  ⚠️ Pas `requis` : un contrat d'assurance ou de syndic couvre la
			//  copropriété entière, et l'imposer ferait cocher « résidence » à la
			//  main sur un tiers des contrats pour ne rien apprendre.
			//  ⚠️ L'aide (« il apparaît dans le carnet d'entretien de ce périmètre »)
			//  vit AVEC le champ : la déclaration dit ce qui est rendu, pas comment
			//  on l'explique.
		},
		{
			id: 'destinataires',
			sansObjet:
				"Un contrat ne s'adresse à personne : il lie la copropriété à une entreprise. " +
				'Qui le consulte est décidé par les droits (conseil syndical et administration), ' +
				'pas par un choix de saisie — la sécurité est centralisée, elle ne se règle pas ' +
				'dans un formulaire.',
		},
		{
			id: 'description',
			//  C'est ici qu'atterrit la synthèse proposée par l'assistant IA (#899),
			//  relue et corrigée avant enregistrement.
			objet: 'RichEditor — la synthèse du contrat',
		},
		{
			id: 'photos',
			sansObjet:
				"Un contrat est un document, pas une constatation. Ce qu'on photographie — un " +
				"désordre, une intervention — appartient au ticket ou à l'événement qui s'y " +
				'rapporte, et le carnet les rassemble déjà.',
		},
		{
			id: 'documents',
			objet: 'FichiersUpload — le contrat signé, ses avenants, ses conditions générales',
			absente: {
				creation: {
					motif: 'api',
					ticket: '#909',
					explication:
						"Un document se rattache à un `contrat_id` qui n'existe pas encore à la " +
						'création : `docsApi.uploadForContrat` exige un contrat enregistré. ' +
						"L'écran les propose donc à la correction seulement. Dette suivie en " +
						'#909 — la lever demande un endpoint qui accepte les fichiers AVEC le ' +
						'contrat, comme les actualités le font depuis #531.',
				},
			},
		},
		{
			id: 'diffusion',
			sansObjet:
				"Un contrat ne s'annonce pas : il se signe. Ni WhatsApp, ni courriel au syndic " +
				"à l'enregistrement.\n\n" +
				'⚠️ À RELIRE (12/09/2026) : son ÉCHÉANCE, elle, concerne le conseil syndical, et ' +
				"rien ne la lui signale depuis cet écran. Ce n'est pas une omission de ce lot — " +
				"c'est une décision qui n'a jamais été prise, et elle relève d'une relance " +
				"automatique plutôt que d'une case à cocher.",
		},
	],
};
