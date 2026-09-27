/**
 * La QUESTION FRÉQUENTE, déclarée une fois — les quatorze sections, ce qu'elles
 * portent, et pourquoi onze d'entre elles sont sans objet (#1329, 27/09/2026).
 *
 * ## Pourquoi maintenant
 *
 * La passe de cohérence #1329 a mis `FormulaireFaq` au cadre — Titre, Nature,
 * Description, dans l'ordre de toutes les entités, avec le pied standard — mais
 * sans déclaration : ses intitulés (« Question », « Catégorie », « Réponse »)
 * et ses mots (« Nouvelle question », « Modifier la question ») n'étaient écrits
 * que dans l'écran, donc tenus par aucun contrôle. Une entité rendue au cadre
 * sans être déclarée est conforme par chance.
 *
 * ## Ce que la déclaration dit
 *
 * Une question fréquente est une **fiche de référence** : on la consulte, on ne
 * la suit pas. Rien à dater, à situer, à diffuser ni à attribuer — la réponse
 * vaut pour toute la copropriété, et c'est ce qui la distingue d'une actualité.
 * Son RANG dans la catégorie (`ordre`) existe, mais il se règle dans la LISTE,
 * par glisser-déposer : ce n'est pas une section de saisie.
 *
 * ## Qui consomme cette déclaration
 *
 *   • `FormulaireFaq.svelte` — la saisie (titre de la boîte, intitulés)
 *   • `routes/(app)/faq` — le bouton « Nouvelle question »
 */

import type { EntiteDeclaree } from './types';

const FICHE =
	'Une question fréquente est une fiche de référence : elle se consulte, elle ne se suit pas.';

export const FAQ: EntiteDeclaree = {
	id: 'faq',
	libelle: 'Question',
	libelleNouveau: 'Nouvelle question',
	libelleModifier: 'Modifier la question',
	sections: [
		{
			id: 'titre',
			objet: 'La question, telle qu’un résident la poserait',
			requis: true,
			titreEcran: ['Question'],
		},
		{
			id: 'nature',
			objet: 'Catégorie — une existante, ou une nouvelle',
			requis: true,
			titreEcran: ['Catégorie'],
		},
		{
			id: 'equipement',
			sansObjet: `${FICHE} Une réponse n'est rattachée à aucun équipement du bâti.`,
		},
		{
			id: 'suivi',
			sansObjet: `${FICHE} Elle est publiée ou retirée, sans étapes entre les deux.`,
		},
		{
			id: 'quand',
			sansObjet: `${FICHE} Elle ne porte pas de date : elle vaut jusqu'à ce qu'on la corrige.`,
		},
		{
			id: 'intervenant',
			sansObjet: `${FICHE} Personne n'intervient sur une réponse.`,
		},
		{
			id: 'perimetre',
			sansObjet:
				'Une réponse vaut pour toute la copropriété. Une règle propre à un bâtiment se ' +
				'dit dans la réponse elle-même, pas par un ciblage qui la cacherait aux autres.',
		},
		{
			id: 'description',
			objet: 'La réponse — texte riche',
			requis: true,
			titreEcran: ['Réponse'],
		},
		{
			id: 'pieces_jointes',
			sansObjet:
				'Un document de référence (règlement, plan) vit dans « Ma résidence » ; la ' +
				'réponse y renvoie par un lien, elle ne le recopie pas.',
		},
		{
			id: 'affaires_liees',
			sansObjet: `${FICHE} Elle ne se lie pas à une affaire.`,
		},
		{
			id: 'au_nom_de',
			sansObjet: 'La foire aux questions est tenue par le conseil syndical, pour tous.',
		},
		{
			id: 'destinataires',
			requis: true,
			sansObjet:
				'Tous les résidents lisent la foire aux questions. Qui peut la modifier relève ' +
				'des droits, pas de la saisie — la sécurité est centralisée.',
		},
		{
			id: 'mise_en_avant',
			sansObjet:
				'Son rang dans la catégorie se règle dans la liste, par glisser-déposer : ce ' +
				"n'est pas un champ du formulaire.",
		},
		{
			id: 'diffusion',
			sansObjet: `${FICHE} Corriger une réponse n'est pas une nouvelle à annoncer.`,
		},
	],
};
