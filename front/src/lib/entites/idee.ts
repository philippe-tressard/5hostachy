/**
 * L'IDÉE, déclarée une fois — les neuf sections, ce qu'elles portent, et **chaque
 * divergence entre états avec son motif** (R4).
 *
 * Sixième et dernière entité de **#441** (Communauté). Le ticket parlait de trois
 * entités sans déclaration ; l'annonce et le sondage l'ont reçue les 18/08, celle-ci
 * les rejoint et **ferme le lot**.
 *
 * ## Ce que la déclaration a trouvé
 *
 * 🔴 **L'idée était la dernière entité de la Communauté sans aucune notion de
 * lieu.** « Ajouter un local à vélos dans le bâtiment 3 », « refaire l'éclairage du
 * parking », « planter des arbres dans les espaces verts » ne concernent pas les
 * mêmes voisins — et n'avaient aucun moyen de le dire. Demandé à l'écran :
 * *« Boîte à idées […] ajouter la section périmètre »*. Migration **0153**.
 *
 * ⚠️ Le périmètre reprend la MÊME forme que partout ailleurs — du JSON de codes.
 * Une quatrième forme diverge : c'est ce que le sondage avait fait
 * (`batiments_ids` + `profils_autorises`), et il a fallu une migration pour l'en
 * sortir (#316, 0147).
 *
 * ## Qui consomme cette déclaration
 *
 *   • `FormulaireIdee.svelte` — le dépôt (`sectionPresente`)
 */

import type { EntiteDeclaree } from './types';

export const IDEE: EntiteDeclaree = {
	id: 'idee',
	libelle: 'Idée',
	sections: [
		{
			id: 'titre',
			objet: 'Titre',
			requis: true,
			absente: {
				evolution: {
					motif: 'hérité',
					explication: "Une réponse se rattache à l'idée ; elle ne la renomme pas.",
				},
			},
		},
		{
			id: 'specifiques',
			sansObjet:
				"Une idée n'a rien à qualifier : ni catégorie, ni date, ni destinataire nommé. " +
				'Elle se pose en un titre et une description, et c\'est le vote des voisins qui ' +
				'la qualifie ensuite. C\'est la plus dépouillée des six entités du cadre, et ce ' +
				'dépouillement est voulu — une boîte à idées qui demande de remplir un formulaire ' +
				'ne reçoit pas d\'idées.',
		},
		{
			//  🔴 L'idée A un workflow — Ouverte · Retenue · Réalisée · Rejetée — et il
			//  répond exactement à la question de la section 3 : « où en est cet
			//  objet ? ». Quatre états ordonnés, franchis par le conseil syndical
			//  devant des résidents qui ont voté : c'est un cycle de vie, pas un
			//  attribut.
			//
			//  ⚠️ ABSENT de la création, motif `geste` : on ne dépose pas une idée en
			//  la déclarant « Réalisée ». L'état se pose depuis la CARTE, en pastilles
			//  (`WorkflowPastilles`, #423), et il est réservé au conseil syndical —
			//  l'auteur propose, le CS arbitre.
			id: 'workflow',
			objet: 'Ouverte · Retenue · Réalisée · Rejetée',
			absente: {
				creation: {
					motif: 'geste',
					explication:
						"On ne dépose pas une idée en la déclarant réalisée : elle naît « Ouverte ». " +
						"L'état se pose ensuite depuis la carte, et c'est le conseil syndical qui " +
						"l'arbitre — pas l'auteur.",
				},
			},
		},
		{
			//  ✅ AJOUTÉ le 18/08/2026 (migration 0153), sur demande à l'écran.
			id: 'perimetre',
			objet: 'PerimetrePicker — ce que l’idée concerne',
			absente: {
				evolution: {
					motif: 'hérité',
					explication: "Le périmètre est celui de l'idée ; une réponse ne le redéfinit pas.",
				},
			},
		},
		{
			id: 'destinataires',
			sansObjet:
				"Une idée s'adresse à toute la Communauté : c'est le principe même d'une boîte à " +
				'idées, où le vote des voisins décide de ce qui monte. Le périmètre dit de quoi ' +
				'elle parle ; restreindre qui peut la lire la priverait des voix qui la portent. ' +
				'Même raisonnement que la petite annonce.',
		},
		{
			id: 'description',
			objet: 'RichEditor — l’idée, en détail',
			requis: true,
		},
		{
			id: 'photos',
			sansObjet:
				'Une idée se raconte, elle ne se photographie pas — elle porte sur ce qui ' +
				"n'existe pas encore. Rien côté serveur n'en porte.",
		},
		{
			id: 'documents',
			sansObjet:
				"Même raison que les photos : rien côté serveur n'en porte. Un devis ou un plan " +
				"relèvent du ticket ou de l'événement qui suivra, si l'idée est retenue.",
		},
		{
			id: 'diffusion',
			sansObjet:
				"Une idée ne s'annonce pas à l'extérieur : elle vit dans la Communauté, où les " +
				'résidents la découvrent et la votent. Ni WhatsApp, ni syndic, ni conseil ' +
				"syndical — le CS la voit comme les autres, et c'est le nombre de votes qui la " +
				'lui signale, pas un courriel.',
		},
	],
};
