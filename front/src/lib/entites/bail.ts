/**
 * Le BAIL — un locataire dans un ou plusieurs lots, déclaré une fois : les
 * sections du cadre, ce qu'elles portent, et pourquoi les autres sont sans
 * objet (#1329, 28/09/2026).
 *
 * ## Pourquoi maintenant
 *
 * `FormulaireBail` posait ses champs à plat, sans aucune section — lots, puis
 * locataire, puis dates, puis notes : rien n'était déclaré, donc rien n'était
 * contrôlé. Arbitré par Philippe le 28/09/2026 sur maquette (option A) :
 * **l'ordre du cadre**, le locataire « au nom de ».
 *
 * ## Les correspondances
 *
 * | Section du cadre | À l'écran | Pourquoi elle |
 * |---|---|---|
 * | Quand | Date d'entrée · Sortie prévue | le bail est un fait daté |
 * | Périmètre | Lot(s) concerné(s) | ce que le bail couvre — un lot EST un lieu |
 * | Description | Notes | ce qu'on en dit, librement |
 * | Au nom de | Le locataire | à qui le bail est consenti |
 *
 * Pas de Titre : un bail se nomme par son lot et son locataire. Lui en donner
 * un ferait une troisième façon de le désigner, que personne ne tiendrait.
 *
 * ## Qui consomme cette déclaration
 *
 *   • `FormulaireBail.svelte` — la saisie (`sectionPresente`, `pliageDe`)
 */

import type { EntiteDeclaree } from './types';

const SANS_OBJET_BAIL = 'Un bail met un locataire dans un lot : il ne porte pas cette notion.';

export const BAIL: EntiteDeclaree = {
	id: 'bail',
	libelle: 'Bail',
	libelleNouveau: 'Nouveau bail',
	libelleModifier: 'Modifier le bail',
	sections: [
		{
			id: 'titre',
			sansObjet:
				'Un bail se nomme par son lot et son locataire ; un titre en ferait une troisième ' +
				'désignation, que personne ne tiendrait à jour.',
		},
		{ id: 'nature', sansObjet: 'Il n’y a qu’une sorte de bail ici : l’habitation.' },
		{ id: 'equipement', sansObjet: SANS_OBJET_BAIL },
		{
			id: 'suivi',
			sansObjet:
				'L’état du bail (en cours, terminé) change par le geste « Terminer le bail », ' +
				'jamais par une saisie.',
		},
		{
			id: 'quand',
			objet: 'Date d’entrée · Sortie prévue',
			requis: true,
		},
		{ id: 'intervenant', sansObjet: SANS_OBJET_BAIL },
		{
			id: 'perimetre',
			objet: 'Les lots que le bail couvre — un bail est créé pour chacun',
			requis: true,
			titreEcran: ['Lot(s) concerné(s)'],
			absente: {
				edition: {
					motif: 'geste',
					explication:
						'Un bail existant ne change pas de lot : le lot est sa raison d’être. On en ' +
						'termine un, on en ouvre un autre.',
				},
			},
		},
		{
			id: 'description',
			objet: 'Les notes sur le bail',
			pliee: true,
		},
		{ id: 'pieces_jointes', sansObjet: 'La saisie d’un bail ne joint aucun fichier.' },
		{ id: 'affaires_liees', sansObjet: SANS_OBJET_BAIL },
		{
			id: 'au_nom_de',
			objet: 'Le locataire — un compte associé, ou saisi à la main',
			exceptionPliage:
				'Facultatif (un bail peut s’ouvrir avant de connaître son locataire), mais c’est ' +
				'ce qu’on vient saisir presque à chaque fois : plié, il serait manqué.',
		},
		{
			id: 'destinataires',
			sansObjet: 'Qui lit un bail relève des droits (le bailleur, le locataire, le conseil).',
		},
		{ id: 'mise_en_avant', sansObjet: SANS_OBJET_BAIL },
		{ id: 'diffusion', sansObjet: 'Un bail ne se diffuse pas.' },
	],
};
