/**
 * La PETITE ANNONCE, déclarée une fois — les neuf sections, ce qu'elles portent,
 * et **chaque divergence entre états avec son motif** (R4).
 *
 * Quatrième entité mise au cadre #430, et la première de la rubrique Communauté
 * (#441 en porte les trois : sondages, idées, annonces).
 *
 * ## Ce que la déclaration a trouvé, et qui n'était écrit nulle part
 *
 * L'annonce **n'avait aucun mode édition**. Une fois déposée, on pouvait changer
 * son statut, gérer ses photos, la supprimer — mais pas corriger une faute dans
 * son titre, ni baisser son prix. Le seul recours était supprimer et redéposer,
 * ce qui perdait les réponses des voisins.
 *
 * Ce n'était pas une contrainte serveur : `PATCH /annonces/{id}` existait, avec
 * ses sept champs, **et personne ne l'appelait**. Exactement le défaut de #433
 * côté actualités, dans l'autre sens : là, un second formulaire écrit à la main
 * perdait cinq notions ; ici, aucun formulaire du tout.
 *
 * ## Le périmètre : une absence de notion qu'un ÉCRAN avait décrétée
 *
 * `FormulaireAnnonce.svelte` portait, en toutes lettres :
 *
 * > « L'annonce n'a ni périmètre ni destinataires : elle s'adresse à tous les
 * >   résidents par nature. »
 *
 * 🔴 **C'est précisément ce que `sansObjet` sert à dire — et il se déclare ici,
 * pas dans un commentaire de formulaire.** La différence n'est pas cosmétique :
 * un commentaire n'est lu par aucun contrôle et ne coûte rien à contredire ; une
 * déclaration est confrontée au rendu à chaque `npm run lint:etats`.
 *
 * L'utilisateur a tranché le 18/08/2026 (*« pour les petites annonces tu peux
 * ajouter le périmètre »*), et il avait raison sur le fond : la copropriété
 * compte quatre bâtiments, un parking, des caves et une AFUL. Un vide-cave ou un
 * covoiturage du bâtiment C **a** un périmètre. Migration 0151.
 *
 * ⚠️ Les **Destinataires** (section 5), eux, restent `sansObjet`, et cette
 * fois-ci c'est une vraie absence de notion : le périmètre dit *de quoi il
 * s'agit*, les destinataires *à qui l'application le montre*. Une annonce est
 * visible de toute la Communauté — c'est la rubrique qui filtre (le syndic et
 * les mandataires en sont exclus, `_deny_communaute_for_statut`), pas l'annonce.
 * Restreindre le public d'une petite annonce n'aurait pas de sens : on n'annonce
 * pas un lave-linge à trois voisins choisis.
 *
 * ## Qui consomme cette déclaration
 *
 *   • `FormulaireAnnonce.svelte` — dépôt ET correction (`sectionPresente`)
 */

import type { EntiteDeclaree } from './types';

export const ANNONCE: EntiteDeclaree = {
	id: 'annonce',
	libelle: 'Petite annonce',
	sections: [
		{
			id: 'titre',
			objet: 'Titre',
			requis: true,
			absente: {
				evolution: {
					motif: 'hérité',
					explication: "Une réponse se rattache à l'annonce ; elle ne la renomme pas.",
				},
			},
		},
		{
			id: 'specifiques',
			objet: 'Type · Catégorie · Prix · Négociable',
			titreEcran: "L'objet",
			absente: {
				evolution: {
					motif: 'hérité',
					explication:
						"Le type, la catégorie et le prix qualifient l'annonce entière. Une réponse " +
						'de voisin ne rebaptise pas un don en vente, et ne fixe pas le prix.',
				},
			},
		},
		{
			//  🔴 UNE ANNONCE N'A PAS DE WORKFLOW — et ce n'est pas la même absence que
			//  celle d'une actualité. L'annonce a bien un ÉTAT (Disponible · Réservé ·
			//  Vendu · Archivé), mais il n'a ni étapes ordonnées, ni acteur qui change
			//  d'une étape à l'autre, ni trace : c'est un attribut que l'auteur pose
			//  depuis sa carte, pas un cycle de vie suivi à plusieurs.
			//
			//  ⚠️ Le distinguer du ticket est ce qui empêche d'importer par réflexe un
			//  fil d'évolutions ici. La question de la section 3 est « où en est cet
			//  objet, et qui l'y a mis » — la seconde moitié n'a pas de réponse pour
			//  une annonce : il n'y a qu'un acteur, son auteur.
			id: 'workflow',
			sansObjet:
				"Une annonce n'a pas d'étapes de vie suivies à plusieurs : son statut " +
				'(Disponible · Réservé · Vendu · Archivé) est un attribut que son auteur pose ' +
				"depuis la carte, pas un cycle qui se trace. Il vit donc avec l'objet et non " +
				'dans un workflow.',
		},
		{
			//  ✅ OUVERT le 18/08/2026 (migration 0151) — voir l'en-tête de ce fichier
			//  pour ce que l'écran avait décrété à la place du produit.
			id: 'perimetre',
			objet: 'PerimetrePicker — de quoi il s’agit',
			requis: true,
			absente: {
				evolution: {
					motif: 'hérité',
					explication: "Le périmètre est celui de l'annonce ; une réponse ne le redéfinit pas.",
				},
			},
		},
		{
			//  🔴 Vraie absence de NOTION, à ne pas confondre avec celle du périmètre
			//  juste au-dessus — la nuance est développée dans l'en-tête.
			id: 'destinataires',
			sansObjet:
				"Une annonce s'adresse à toute la Communauté : c'est la rubrique qui filtre qui " +
				'y entre (le syndic et les mandataires en sont exclus), pas l’annonce. On ' +
				'n’annonce pas un lave-linge à trois voisins choisis.',
		},
		{
			id: 'description',
			objet: 'RichEditor — l’objet, son état, les conditions de remise',
			requis: true,
		},
		{
			//  ⚠️ Les photos d'une annonce se gèrent depuis la CARTE, pas depuis le
			//  formulaire, et c'est une dette : l'endpoint `POST /annonces/{id}/photo`
			//  a besoin de l'identifiant, qui n'existe pas au dépôt. Les tickets, les
			//  actualités et les événements téléversent AVANT d'enregistrer, par
			//  l'endpoint générique — l'annonce est la dernière à ne pas le faire.
			//
			//  🔴 Motif `api`, donc DETTE : elle cite #441, qui porte la mise au cadre
			//  de la rubrique Communauté. Un motif `api` n'entérine jamais un choix.
			id: 'photos',
			objet: 'FichiersUpload mode photos (5 maximum)',
			absente: {
				creation: {
					motif: 'api',
					explication:
						"`POST /annonces/{id}/photo` exige l'identifiant de l'annonce, qui n'existe pas " +
						"encore au dépôt. Les photos s'ajoutent donc depuis la carte, une fois " +
						"l'annonce déposée — divergence subie, pas choisie.",
					ticket: '#441',
				},
				edition: {
					motif: 'api',
					explication:
						'Même endpoint, et la gestion des photos vit déjà dans la carte (« Gérer les ' +
						'photos »). La rouvrir ici donnerait DEUX chemins concurrents vers la même ' +
						'liste, sans que rien ne dise lequel fait foi.',
					ticket: '#441',
				},
				evolution: {
					motif: 'hérité',
					explication: "Les photos sont celles de l'annonce ; une réponse n'en ajoute pas.",
				},
			},
		},
		{
			id: 'documents',
			sansObjet:
				"Une petite annonce se décrit et se photographie ; elle n'a pas de pièce jointe " +
				'à télécharger. Aucun écran n’en a jamais proposé, et rien côté serveur n’en ' +
				'porte.',
		},
		{
			//  La seule chose qui PART d'une annonce est le fait de montrer, ou non, ses
			//  coordonnées aux autres résidents. Ce n'est pas un canal de notification —
			//  l'annonce ne prévient personne, elle se lit dans la rubrique — mais c'en
			//  est bien la décision de diffusion.
			id: 'diffusion',
			objet: 'Afficher mes coordonnées aux autres résidents',
			absente: {
				affichage: {
					motif: 'geste',
					explication:
						"On n'affiche pas une décision de diffusion : la carte montre le résultat " +
						'(l’adresse est là, ou elle ne l’est pas), pas la case qui l’a produit.',
				},
				evolution: {
					motif: 'hérité',
					explication:
						"La visibilité des coordonnées est celle de l'annonce ; une réponse ne la " +
						'rouvre pas au nom de son auteur.',
				},
			},
		},
	],
};
