/**
 * Le PRESTATAIRE, déclaré une fois — les treize sections, ce qu'elles portent, et
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
	libelleNouveau: 'Nouveau prestataire',
	libelleModifier: 'Modifier le prestataire',
	sections: [
		{
			id: 'titre',
			objet: 'Nom',
			requis: true,
			titreEcran: ['Nom'],
		},
		{
			//  🔴 Les sections STANDARD (24/09/2026, signalé à l'écran : « Prendre
			//  exemple sur l'UX d'Affaires »). « L'entreprise » mêlait le type, la
			//  spécialité et le courriel ; le type est la CATÉGORIE de l'entreprise,
			//  comme celle d'une affaire.
			id: 'nature',
			objet: 'Type',
			requis: true,
			titreEcran: ['Catégorie'],
		},
		{
			//  🔴 La « Spécialité » ÉTAIT l'équipement (24/09/2026, question posée à
			//  l'écran : « spécialité c'est équipement ? ») — même liste
			//  (`TypeEquipement`), et le carnet s'en sert quand un contrat n'en
			//  désigne pas. Elle prend le nom et le rang de la section qui le porte
			//  partout ailleurs.
			id: 'equipement',
			objet: 'Équipement dont l’entreprise s’occupe',
			requis: true,
		},
		{
			id: 'suivi',
			sansObjet:
				"Un prestataire n'a pas d'états : il est référencé, ou il ne l'est plus. " +
				"L'archivage suffit, et il se fait d'un geste sur la carte — pas d'une " +
				'colonne à déplacer.',
		},
		{
			id: 'quand',
			sansObjet: "un prestataire est une fiche d'annuaire, pas un fait daté",
		},
		{
			//  Les personnes à joindre, et le courriel de l'entreprise : une fiche
			//  d'annuaire se lit par eux. 🔴 OBLIGATOIRE, donc dépliée, depuis le
			//  24/09/2026 (#1229) : un contact avec un nom, et un téléphone ou un
			//  e-mail — exigé à la CRÉATION par le serveur (`prestataires_schemas`).
			id: 'intervenant',
			objet: 'Courriel · contacts (prénom, nom, fonction · téléphone, courriel)',
			titreEcran: ['Contacts'],
			requis: true,
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
			id: 'description',
			sansObjet:
				"Ce qu'il y a à dire d'une entreprise tient dans son type et sa spécialité, " +
				"tous deux choisis dans des listes — donc comparables d'un prestataire à " +
				"l'autre. Un texte libre ne le serait pas, et c'est la NOTE (1 à 5, avec " +
				'commentaire) qui porte le jugement, depuis la carte de son contrat.',
		},
		{
			id: 'pieces_jointes',
			sansObjet:
				"Un carnet d'adresses ne se photographie pas, et les documents appartiennent " +
				'au CONTRAT — le contrat signé, ses avenants, ses conditions générales. Les ' +
				"rattacher à l'entreprise les détacherait de ce qu'ils engagent.",
		},
		{
			id: 'au_nom_de',
			sansObjet: 'Un carnet d’adresses se tient, il ne se saisit pas pour un tiers.',
		},
		{
			id: 'destinataires',
			//  🔴 OBLIGATOIRE, donc DÉPLIÉE (22/09/2026, signé à l'écran deux fois).
			//
			//  L'astérisque était écrite en dur par `SectionDestinataires` : la
			//  déclaration ne savait donc pas que la section était obligatoire, et
			//  `lint:etats` — qui CALCULE le pliage à partir d'elle — ne voyait
			//  aucune contradiction à la déclarer pliée. L'écran affichait donc
			//  « DESTINATAIRES* » sur une ligne fermée, ce que la règle interdit.
			requis: true,
			sansObjet:
				"Personne n'est destinataire d'une fiche de carnet d'adresses. Qui la " +
				'consulte relève des droits, pas de la saisie — la sécurité est centralisée.',
		},
		{
			id: 'mise_en_avant',
			sansObjet: 'Une fiche d’annuaire ne se met pas en avant : l’annuaire se lit par recherche.',
		},
		{
			id: 'diffusion',
			sansObjet:
				"Référencer une entreprise n'est pas un événement : rien à annoncer, ni au " +
				'syndic, ni au conseil syndical, ni sur WhatsApp.',
		},
	],
};
