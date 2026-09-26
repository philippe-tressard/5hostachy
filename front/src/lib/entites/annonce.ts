/**
 * La PETITE ANNONCE, déclarée une fois — les treize sections, ce qu'elles portent,
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
 *   • `AnnonceCard.svelte` — l'affichage, et le raccourci de workflow
 *
 * ## ⚠️ Un revirement, et ce qu'il enseigne
 *
 * La section 3 portait `sansObjet` le 18/08 au matin — « une annonce n'a pas
 * d'étapes de vie suivies à plusieurs » — et un workflow le soir même, sur
 * arbitrage de l'utilisateur. Le raisonnement d'origine regardait **qui agit**
 * quand la question de la section 3 est d'abord **où en est l'objet**.
 *
 * C'est la deuxième fois en deux jours que l'écran réfute le papier (la
 * première : « une actualité n'a pas de workflow », dans l'autre sens). La
 * leçon n'est pas qu'il faut moins déclarer — c'est que **la déclaration
 * rend le désaccord visible et corrigeable en un endroit**. Sans elle, les
 * deux raisonnements auraient coexisté dans deux écrans.
 */

import type { EntiteDeclaree } from './types';

export const ANNONCE: EntiteDeclaree = {
	id: 'annonce',
	libelle: 'Petite annonce',
	libelleNouveau: 'Déposer une annonce',
	libelleModifier: "Modifier l'annonce",
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
			id: 'nature',
			objet: 'Type · Catégorie · Prix · Négociable',
			titreEcran: "L'objet",
			//  🔴 OBLIGATOIRE, donc DÉPLIÉE (#1186, 24/09/2026, signalé à l'écran). Une
			//  annonce sans type ni catégorie ne se range ni ne se filtre : c'est ce
			//  qui la qualifie. Elle était pliée, sans astérisque.
			requis: true,
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
			id: 'equipement',
			sansObjet:
				'Une petite annonce ne porte sur aucun élément du bâti : elle parle d’un objet qui appartient à un résident.',
		},
		{
			//  🔴 REVIREMENT ASSUMÉ — l'utilisateur a tranché le 18/08/2026 :
			//  « Ajouter une section workflow (En cours ; vendu, annuler) ».
			//
			//  Ce fichier disait le contraire la veille, et le disait avec assurance :
			//  « une annonce n'a pas d'étapes de vie suivies à plusieurs ». Le
			//  raisonnement — un seul acteur, donc rien à tracer — était cohérent et
			//  faux : il regardait QUI agit, alors que la question de la section 3 est
			//  d'abord « où en est cet objet ? ». Un vendeur qui a réservé, vendu, ou
			//  renoncé a bien un cycle — et ses voisins ont besoin de le lire.
			//
			//  ⚠️ Ce que le revirement NE remet pas en cause : il n'y a toujours pas de
			//  fil d'évolutions ici. Un workflow se déclare parce que l'objet a des
			//  états ordonnés ; le TRACER est une autre décision, et personne ne l'a
			//  demandée. Les deux notions restent distinctes.
			//
			//  ⚠️ `archive` n'est PAS un de ces états : l'archivage est une conséquence
			//  du temps (un mois), pas une étape qu'on choisit. Il se calcule côté
			//  serveur (`est_archivee`). En faire une sixième pastille aurait donné deux
			//  notions pour la même chose — celle qu'on pose et celle qui arrive.
			id: 'suivi',
			objet: 'En cours · Réservé · Vendu · Donné · Annulé',
			absente: {
				creation: {
					motif: 'geste',
					explication:
						"Une annonce qu'on dépose est en cours, par construction : proposer l'état " +
						"au dépôt reviendrait à demander si l'objet est déjà vendu avant de " +
						"l'avoir annoncé.",
				},
				evolution: {
					motif: 'hérité',
					explication:
						"L'état est celui de l'annonce. Une réponse de voisin ne la déclare ni " +
						'vendue ni annulée — seul son auteur le peut.',
				},
			},
			pliee: true,
		},
		{
			id: 'quand',
			sansObjet:
				"une petite annonce n'a pas de date d'événement : elle vit jusqu'à ce que l'objet soit vendu ou donné, et c'est sa péremption qui la retire — pas un passage au calendrier",
		},
		{
			id: 'intervenant',
			sansObjet: 'Une annonce se règle entre voisins ; aucune entreprise n’intervient.',
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
			//
			//  ⚠️ La section ne porte que des PHOTOS : une petite annonce se décrit et
			//  se photographie, elle n'a pas de pièce jointe à télécharger. C'est un
			//  fait sur l'objet, pas une divergence entre états.
			id: 'pieces_jointes',
			objet: 'FichiersUpload mode photos (5 maximum) — pas de document',
			absente: {
				//  ✅ PRÉSENTE au dépôt depuis le 24/09/2026 (#1186, signalé à l'écran).
				//  La dette `api` de #441 est soldée SANS toucher à l'API : les photos
				//  attendent dans le formulaire (mode différé) et partent par
				//  `POST /annonces/{id}/photo` une fois l'annonce créée.
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
			//  🔴 PLIÉE, comme toute section facultative (21/09/2026, demandé à
			//  l'écran). Elle était l'exception inverse — « dépliée parce que joindre
			//  une photo est le premier geste sur téléphone ». C'est l'ARBITRAGE qui a
			//  changé, pas la règle : un formulaire de treize sections toutes ouvertes
			//  n'est pas lisible au pouce.
			//  ⚠️ `valeurModifiee` la rouvre dès qu'un fichier y est joint : en
			//  édition, un objet qui porte des pièces jointes ne les cache pas.
			pliee: true,
		},
		{
			id: 'affaires_liees',
			sansObjet:
				'Une petite annonce se passe entre résidents ; elle ne renvoie à aucune ' +
				'affaire, et `Annonce` ne porte aucun lien (#1342).',
		},
		{
			id: 'au_nom_de',
			sansObjet:
				'Une annonce est déposée par celui qui la publie, jamais pour un tiers — c’est son bien.',
		},
		{
			//  🔴 REVIREMENT ASSUMÉ — l'utilisateur a tranché le 06/09/2026 : « ajoute
			//  la section Destinataires ; en nouveau et en édition », et le ciblage
			//  filtre la VISIBILITÉ, pas seulement les notifications.
			//
			//  Ce fichier disait l'inverse la veille, et le disait avec assurance :
			//  « on n'annonce pas un lave-linge à trois voisins choisis ». Le
			//  raisonnement n'était pas absurde — il supposait qu'une annonce
			//  s'adresse par nature à tous, alors que vendre à son seul bâtiment, ou
			//  réserver un don aux locataires, sont des gestes réels.
			//
			//  C'est la DEUXIÈME fois que l'écran réfute le papier sur cette entité
			//  (la première : le workflow, absent puis ajouté le 18/08). La leçon
			//  n'est pas qu'il faut moins déclarer, c'est que la déclaration rend le
			//  désaccord visible et corrigeable en UN endroit.
			//
			//  ⚠️ Le périmètre (section 4) dit DE QUOI il s'agit, celle-ci À QUI on
			//  s'adresse. Les deux axes sont indépendants et se combinent : c'est
			//  `cible_visible` côté serveur qui les pose, la même fonction que pour
			//  la publication et le sondage.
			id: 'destinataires',
			//  🔴 OBLIGATOIRE, donc DÉPLIÉE (22/09/2026, signé à l'écran deux fois).
			//
			//  L'astérisque était écrite en dur par `SectionDestinataires` : la
			//  déclaration ne savait donc pas que la section était obligatoire, et
			//  `lint:etats` — qui CALCULE le pliage à partir d'elle — ne voyait
			//  aucune contradiction à la déclarer pliée. L'écran affichait donc
			//  « DESTINATAIRES* » sur une ligne fermée, ce que la règle interdit.
			requis: true,
			objet: 'DestinatairePicker — à qui cette annonce s’adresse',
			absente: {
				evolution: {
					motif: 'hérité',
					explication:
						"Le public visé est celui de l'annonce. Une réponse de voisin ne l'élargit " +
						'ni ne le restreint — sinon répondre suffirait à faire entrer des tiers.',
				},
			},
		},
		{
			id: 'mise_en_avant',
			sansObjet:
				'Une annonce ne s’épingle pas et ne se marque pas urgente : le fil de la Communauté est chronologique.',
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
			pliee: true,
		},
	],
};
