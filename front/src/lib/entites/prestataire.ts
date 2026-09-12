/**
 * Le PRESTATAIRE, déclaré une fois — les neuf sections, ce qu'elles portent, et
 * chaque divergence entre états avec son motif (R4).
 *
 * Huitième entité du cadre #430, déclarée le 12/09/2026 avec le contrat, sur le
 * même signalement (#910).
 *
 * ## Ce que la déclaration a fait apparaître
 *
 * 🔴 **Six sections sur neuf sont sans objet.** Un prestataire n'est pas un
 * événement de la copropriété : c'est une entrée de carnet d'adresses. Rien à
 * situer, rien à diffuser, rien à dater — et c'est exactement pour cela que la
 * déclaration valait la peine : sans elle, on aurait pu croire qu'il manquait un
 * périmètre ou une description, alors que leur absence est la bonne réponse.
 *
 * ⚠️ La différence avec le CONTRAT est instructive : le contrat, lui, a un
 * périmètre (ce qu'il entretient) et une description (sa synthèse). Deux objets
 * voisins, deux formes — et le cadre rend la différence lisible au lieu de la
 * laisser à l'appréciation de l'écran.
 *
 * ## Qui consomme cette déclaration
 *
 *   • `ChampsPrestataire.svelte` — la saisie (`sectionPresente`)
 */

import type { EntiteDeclaree } from './types';

export const PRESTATAIRE: EntiteDeclaree = {
	id: 'prestataire',
	libelle: 'Prestataire',
	sections: [
		{
			id: 'titre',
			objet: 'Nom',
			requis: true,
			titreEcran: ['Nom'],
		},
		{
			id: 'specifiques',
			objet: 'Type · Spécialité · Courriel',
			requis: true,
			titreEcran: ["L'entreprise"],
		},
		{
			id: 'workflow',
			sansObjet:
				"Un prestataire n'a pas d'états : il est référencé, ou il ne l'est plus. " +
				"L'archivage suffit, et il se fait d'un geste sur la carte — pas d'une " +
				'colonne à déplacer.',
		},
		{
			id: 'perimetre',
			sansObjet:
				"Une entreprise n'est attachée à aucun lieu de la copropriété : c'est son " +
				"CONTRAT qui porte ce qu'elle entretient, et lui seul (déclaré dans " +
				'`entites/contrat`). Donner un périmètre au prestataire ferait deux endroits ' +
				'où le lire, donc deux occasions de les désaccorder.',
		},
		{
			id: 'destinataires',
			sansObjet:
				"Personne n'est destinataire d'une fiche de carnet d'adresses. Qui la " +
				'consulte relève des droits, pas de la saisie — la sécurité est centralisée.',
		},
		{
			id: 'description',
			sansObjet:
				"Ce qu'il y a à dire d'une entreprise tient dans son type et sa spécialité, " +
				"tous deux choisis dans des listes — donc comparables d'un prestataire à " +
				"l'autre. Un texte libre ne le serait pas, et c'est la NOTE (1 à 5, avec " +
				'commentaire) qui porte le jugement, depuis la carte de son contrat.',
		},
		{
			id: 'photos',
			sansObjet: "Un carnet d'adresses ne se photographie pas.",
		},
		{
			id: 'documents',
			sansObjet:
				'Les documents appartiennent au CONTRAT — le contrat signé, ses avenants, ses ' +
				"conditions générales. Les rattacher à l'entreprise les détacherait de ce " +
				"qu'ils engagent.",
		},
		{
			id: 'diffusion',
			sansObjet:
				"Référencer une entreprise n'est pas un événement : rien à annoncer, ni au " +
				'syndic, ni au conseil syndical, ni sur WhatsApp.',
		},
	],
};
