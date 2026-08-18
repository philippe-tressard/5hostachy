/**
 * Le SONDAGE, déclaré une fois — les neuf sections, ce qu'elles portent, et
 * **chaque divergence entre états avec son motif** (R4).
 *
 * Cinquième entité mise au cadre #430, premier des deux lots restants de **#441**
 * (Communauté). L'idée suivra, après constat à l'écran de celui-ci — R5 : *un
 * écran à la fois, et jamais deux entités d'un coup.*
 *
 * ## Ce que la déclaration a trouvé, et qui n'était écrit nulle part
 *
 * 🔴 **Le sondage n'a AUCUN mode édition, alors que `PATCH /sondages/{id}`
 * existe et que personne ne l'appelle.** C'est le défaut de la petite annonce,
 * à l'identique : une correction de faute de frappe dans la question impose de
 * supprimer et recréer — ce qui perd tous les votes déjà exprimés. La différence
 * avec l'annonce est que la perte est ici irréversible pour les votants, qui ne
 * seront pas prévenus. Suivi séparément : ce lot le CONSTATE, il ne l'implémente
 * pas — une fonction absente se décide avant de se déclarer.
 *
 * ## Ce que le sondage n'a pas, et pourquoi ce n'est pas un manque
 *
 * **Ni photos ni documents.** Ce n'est pas une divergence entre états mais une
 * absence de notion : un sondage pose une question et propose des réponses. Rien
 * côté serveur n'en porte — `Sondage` n'a ni `photos_urls` ni `fichiers_urls`.
 *
 * ⚠️ À ne PAS confondre avec « on pourrait en ajouter ». `sansObjet` dit ce que
 * l'entité est, pas ce qu'elle pourrait devenir.
 */

import type { EntiteDeclaree } from './types';

export const SONDAGE: EntiteDeclaree = {
	id: 'sondage',
	libelle: 'Sondage',
	sections: [
		{
			//  Le titre d'un sondage EST la question posée — d'où `titreEcran`.
			//  R3 impose le même libellé d'un formulaire à l'autre, et « Question »
			//  est ce que l'écran a toujours dit.
			id: 'titre',
			objet: 'La question posée',
			titreEcran: 'Question',
			requis: true,
			absente: {
				evolution: {
					motif: 'hérité',
					explication:
						'Un commentaire se rattache au sondage ; il ne reformule pas la question posée.',
				},
			},
		},
		{
			//  DEUX groupes nommés, comme la section 2 du ticket en porte deux
			//  champs : les réponses proposées, et les règles de clôture (date +
			//  visibilité des résultats avant le terme).
			//
			//  ⚠️ « Afficher les résultats avant la clôture » est un champ
			//  SPÉCIFIQUE, pas une diffusion : il ne décide pas par quels canaux on
			//  prévient à l'extérieur (section 9), mais ce que les destinataires
			//  voient pendant le vote. Des résultats visibles influencent les votes
			//  suivants (#397) — c'est une propriété du sondage.
			id: 'specifiques',
			objet: 'Réponses possibles (2 minimum, champ libre facultatif) · Date de clôture · Résultats visibles avant la clôture',
			titreEcran: ['Réponses possibles', 'Clôture'],
			absente: {
				evolution: {
					motif: 'hérité',
					explication:
						'Les réponses proposées et la date de clôture appartiennent au sondage. Un ' +
						'commentaire ne rouvre pas le vote et ne rajoute pas une option.',
				},
			},
		},
		{
			//  🔴 LE SONDAGE A UN WORKFLOW — Ouvert · Clôturé — et c'est le point de
			//  cette déclaration qui demande un arbitrage.
			//
			//  La question de la section 3 est « où en est cet objet ? », et non
			//  « qui l'y a mis » : c'est la leçon du revirement sur la petite annonce
			//  (18/08/2026), où le raisonnement « il n'y a qu'un acteur » s'était
			//  révélé hors sujet. Un sondage est ouvert, puis clos ; ses lecteurs
			//  ont besoin de savoir lequel des deux, et l'écran l'affiche déjà en
			//  badge « 🔒 Clôturé ».
			//
			//  Ce qui le distingue de l'ARCHIVAGE, qui est une conséquence du temps
			//  et n'a jamais de bouton : la clôture, elle, PEUT être posée. Le
			//  serveur porte `cloture_forcee` et expose `PATCH /{id}/cloturer`, et
			//  l'écran en fait un bouton réservé à l'auteur et à l'administrateur.
			//  Un geste explicite sur l'état de vie de l'objet, c'est un workflow.
			//
			//  ⚠️ Il n'est PAS proposé à la création : on n'ouvre pas un sondage en
			//  le clôturant. D'où le motif `geste` — la section est un acte qui n'a
			//  pas lieu dans cet état.
			//  ⚠️ **L'état lui-même n'est pas transporté de façon fiable** : le serveur
			//  calcule `cloture` (`sondage_clos()`) et ne l'expose que sur la FICHE ;
			//  la liste recalcule donc la règle côté client, fuseau du navigateur
			//  compris. Deux implémentations d'une même question, dont une seule fait
			//  autorité — le défaut que `ux-patterns` §16 nomme. Suivi en **#468**.
			id: 'workflow',
			objet: 'Ouvert · Clôturé (à la date prévue, ou par clôture anticipée)',
			absente: {
				creation: {
					motif: 'geste',
					explication:
						"On n'ouvre pas un sondage en le clôturant : la clôture est un acte posé " +
						'plus tard, ou atteint par la date. Seule la DATE de clôture se saisit à la ' +
						'création, et elle est en section 2.',
				},
			},
		},
		{
			id: 'perimetre',
			objet: 'PerimetrePicker — qui est concerné par la question',
			requis: true,
			absente: {
				evolution: {
					motif: 'hérité',
					explication: 'Le périmètre est celui du sondage ; un commentaire ne le redéfinit pas.',
				},
			},
		},
		{
			id: 'destinataires',
			objet: 'DestinatairePicker — quels profils peuvent voter',
			absente: {
				evolution: {
					motif: 'hérité',
					explication:
						"Le public visé est celui du sondage. Un commentaire qui l'élargirait " +
						'montrerait un débat à des résidents qui n’ont jamais vu la question.',
				},
			},
		},
		{
			//  Non requise, comme sur l'événement : la question se suffit souvent à
			//  elle-même. La description sert à poser le contexte quand il en faut un.
			id: 'description',
			objet: 'RichEditor — le contexte de la question',
		},
		{
			id: 'photos',
			sansObjet:
				'Un sondage pose une question et propose des réponses ; il ne montre rien. ' +
				'`Sondage` ne porte pas de `photos_urls`, et aucun écran n’en a jamais proposé.',
		},
		{
			id: 'documents',
			sansObjet:
				"Même raison que les photos : rien côté serveur n'en porte. Un document qui " +
				'éclaire une question relève de la publication qui l’accompagne, pas du bulletin ' +
				'de vote.',
		},
		{
			id: 'diffusion',
			objet: 'CanauxNotification — WhatsApp, syndic, conseil syndical',
			absente: {
				affichage: {
					motif: 'geste',
					explication: "On n'affiche pas un envoi : la diffusion a eu lieu, elle ne se lit pas.",
				},
			},
		},
	],
};

/**
 * ⚠️ **Ce que cette déclaration ne gouverne pas encore.**
 *
 * `FormulaireSondage` ne sert que la **création** : l'état `edition` est déclaré
 * ici sans rendu correspondant, et ce n'est pas une divergence à motiver mais une
 * fonction qui n'existe pas. Elle se décide avant de se déclarer.
 *
 * L'état `evolution` — les commentaires d'un sondage (`POST /{id}/commenter`) —
 * ne passe pas par `EvolForm` mais par un formulaire propre à la fiche. Il rejoint
 * la même dette que les quatre autres entités : **#463**.
 */
