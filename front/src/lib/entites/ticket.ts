/**
 * Le TICKET, déclaré une fois — les neuf sections, ce qu'elles portent, et
 * **chaque divergence entre états avec son motif** (R4).
 *
 * Première entité mise au cadre #430, parce qu'elle en était déjà la plus proche :
 * #425 avait rendu `FormulaireTicket` paramétrable, et c'était le **seul endroit
 * du produit** où chaque écart entre création et édition portait une raison
 * écrite. Elles vivaient en commentaires, donc invisibles à tout contrôle ; elles
 * vivent ici, et `npm run lint:etats` les vérifie.
 *
 * ## Qui consomme cette déclaration
 *
 *   • `FormulaireTicket.svelte`  — création ET édition (`sectionPresente`)
 *   • `FicheLecture.svelte`      — affichage, via `sectionsDe(TICKET, 'affichage')`
 *   • `EvolForm.svelte`          — évolution *(pas encore : composant partagé par
 *     quatre écrans, il rejoindra le cadre avec #463 — cf. la note en fin de
 *     fichier)*
 *
 * ⚠️ **Rien de spécifique au ticket ne doit s'écrire ailleurs.** Si un écran a
 * besoin de savoir qu'une section du ticket est absente quelque part, il appelle
 * `sectionPresente` — il ne réécrit pas la condition.
 */

import type { EntiteDeclaree } from './types';

/**
 * ⚠️ **Plus aucun motif `api` ici, et c'est un événement.** Deux divergences en
 * portaient un, citant #431 : les **photos** fermées en édition, et « Saisi
 * pour » qu'on ne pouvait pas effacer. Un motif `api` est une **dette, jamais un
 * choix** — il tombe le jour où l'API sait faire, et sa disparition est la preuve
 * qu'elle a été payée. Les deux ont été soldées le 18/08/2026.
 *
 * `lint:etats` garde encore un cas vivant, côté publications (#390) : le contrôle
 * du motif `api` n'est donc pas devenu aveugle faute de sujet.
 */

export const TICKET: EntiteDeclaree = {
	id: 'ticket',
	libelle: 'Ticket',
	sections: [
		{
			//  🔴 Le TITRE, et lui seul. La catégorie a longtemps partagé cette
			//  section — elle y était même rendue AVANT le titre, si bien que le
			//  premier champ de la première section n'était pas le titre. Arbitré
			//  par l'utilisateur le 18/08/2026 : *« dans Tickets, le titre est en
			//  second, il devrait être en premier ; la catégorie fait partie des
			//  champs spécifiques »*. La catégorie qualifie le ticket comme
			//  « Saisi pour » : elle est en section 2.
			id: 'titre',
			objet: 'Titre',
			requis: true,
			absente: {
				evolution: {
					motif: 'hérité',
					explication: "Une entrée de l'Historique se rattache au ticket ; elle ne le renomme pas.",
				},
			},
		},
		{
			//  DEUX champs nommés, d'où la liste d'intitulés : « Catégorie » et
			//  « Saisi pour ». Tous deux **requis**, tous deux rendus aux mêmes
			//  états — la section n'a plus de champ à géométrie variable.
			//
			//  ✅ « Saisi pour » est OUVERT à l'édition depuis le 18/08/2026. Il en
			//  était absent parce que `TicketUpdate` ne savait pas EFFACER les
			//  `saisi_pour_*` — un `None` y était indistinguable d'un champ non
			//  envoyé, et « En mon nom » aurait été un choix sans effet, en silence.
			//  Le serveur lit désormais la PRÉSENCE du champ (`model_fields_set`)
			//  et non sa non-nullité : effacer efface.
			//
			//  C'est ce qui referme, pour cette entité, la limite décrite en #436 —
			//  R4 ne déclarant qu'une divergence de SECTION, un champ fermé au sein
			//  d'une section ouverte n'était déclarable nulle part.
			id: 'specifiques',
			objet:
				'Catégorie + Saisi pour (en mon nom / résident inscrit / personne extérieure) ' +
				'+ Options de publication',
			titreEcran: ['Catégorie', 'Saisi pour', 'Options de publication'],
			//  🔴 OUVERTE À L'ÉVOLUTION (05/09/2026), constaté à l'écran :
			//  *« Options de publications n'apparaît pas sur un commentaire sur un
			//  ticket existant »*.
			//
			//  Elle était déclarée ABSENTE, motif `hérité`, et le motif restait juste
			//  pour ce qu'il nommait : la catégorie et « Saisi pour » appartiennent au
			//  ticket, pas à l'entrée du fil. Mais la section a reçu une troisième
			//  chose le même jour — les OPTIONS DE PUBLICATION —, et celles-là se
			//  corrigent en commentant, exactement comme sur une actualité : le
			//  formulaire montre le dernier état, ce qu'on enregistre devient l'état.
			//
			//  Une section absente pour l'un de ses champs fermait la porte aux deux
			//  autres. C'est la limite connue de R4, qui ne déclare que des SECTIONS
			//  et jamais des champs (#436) : la divergence de champ vit donc ici, en
			//  commentaire — `OptionsEvolutionTicket` ne rend QUE les options, et
			//  `EvolForm` n'a jamais proposé ni catégorie ni « Saisi pour ».
		},
		{
			//  🔴 Aucune divergence, et c'est la correction due au cadre. L'édition
			//  CORRIGE — une erreur, un oubli, un complément — et l'état s'y corrige
			//  comme les autres champs. Jusqu'au 17/08/2026 l'édition ne montrait
			//  qu'un badge en lecture, avec une mention « l'état se change depuis le
			//  fil » : le motif invoqué (`trace`) n'existe pas dans le cadre.
			//  La traçabilité, elle, ne tombe pas : c'est le `PATCH` qui a changé —
			//  il écrit désormais une CORRECTION, pas une transition de workflow
			//  (`api/app/routers/tickets/crud.py`).
			id: 'workflow',
			objet: 'Ouvert · En cours · Résolu · Annulé',
		},
		{
			//  🔴 LA DIVERGENCE A ÉTÉ RETIRÉE LE 19/08/2026, et c'est un revirement.
			//
			//  Elle disait : *« Le périmètre est celui du ticket ; une entrée ne le
			//  redéfinit pas »* — motif `hérité`. C'était juste tant qu'un périmètre
			//  était acquis à l'ouverture. L'usage a réfuté la prémisse (#497) :
			//
			//  > *« le périmètre de la fuite pourrait être précisé et évolue »*
			//
			//  Un ticket se signale avec ce qu'on sait au moment où on le signale,
			//  donc souvent avec le périmètre le plus large. Puis on cherche, et
			//  « bâtiment 2 » devient « bât. 2, 3ᵉ étage, cage B ». Une entrée du fil
			//  PEUT donc déclarer un périmètre — il devient alors celui du ticket.
			//
			//  ⚠️ Le champ reste **facultatif** dans ce seul état : y toucher est un
			//  geste rare et volontaire, et ne rien dire ne change rien. C'est une
			//  nuance que R4 ne sait pas déclarer (elle ne parle que de SECTIONS,
			//  #436) — elle est portée par `EvolForm.avecPerimetre`, dont le nom dit
			//  qu'elle est optionnelle, et par le test `test_evolution_perimetre.py`
			//  qui vérifie qu'une entrée muette laisse le ticket tranquille.
			id: 'perimetre',
			objet: 'PerimetrePicker — de quoi il s’agit',
			requis: true,
		},
		{
			id: 'destinataires',
			sansObjet:
				"Un ticket n'adresse personne nommément dans l'application : il est vu par son " +
				'auteur et par le conseil syndical, et son périmètre dit déjà de quoi il parle. ' +
				'`destinataire_syndic` et `destinataire_cs` ne sont PAS des destinataires au sens ' +
				'de la section 5 — ce sont deux canaux, et ils vivent en Diffusion (section 9).',
		},
		{
			id: 'description',
			objet: 'RichEditor — le problème, en détail',
			requis: true,
		},
		{
			//  ✅ OUVERTES à l'édition le 18/08/2026. La dette `api` qui les fermait
			//  est soldée : `TicketUpdate` accepte `photos_urls`, et une liste vide
			//  efface sans ambiguïté — exactement ce que la déclaration annonçait.
			//  Un motif `api` est une DETTE, jamais un choix : il tombe quand elle est
			//  payée, et sa disparition d'ici est la preuve qu'elle l'a été.
			id: 'photos',
			objet: 'FichiersUpload mode photos',
		},
		{
			//  Ouverts à l'édition depuis le cadre : `fichiers_urls` EST accepté par
			//  `TicketUpdate`, et une liste vide efface sans ambiguïté — la dette qui
			//  ferme les photos n'a donc aucune raison de fermer les documents.
			id: 'documents',
			objet: 'FichiersUpload mode documents',
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
 * ⚠️ **Ce que cette déclaration ne gouverne PAS encore, et pourquoi.**
 *
 * L'état `evolution` est déclaré ici, mais `EvolForm.svelte` ne le consomme pas :
 * ce composant sert **cinq écrans** — tickets, fiche de ticket, actualités,
 * espace CS, et le **calendrier** depuis le 18/08/2026 (`HistoriqueEvenement`) —
 * et l'y brancher changerait les quatre autres avant qu'on les ait regardés.
 * C'est très exactement ce que R5 interdit : *l'enrichissement se propose sur UN
 * écran, se fait constater, puis se généralise*.
 *
 * ⚠️ Le compte était resté à « quatre » après l'arrivée du cinquième : un nombre
 * écrit dans un commentaire ne se met pas à jour tout seul, et c'est précisément
 * ce nombre qui justifie de ne pas brancher.
 *
 * ✅ **La divergence que cette note décrivait est SOLDÉE.** Elle disait qu'`EvolForm`
 * savait rendre les pièces jointes « unifiées » (`separatePhotosAndDocs = false`),
 * fusionnant les sections 7 et 8, et que les actualités et l'espace CS s'en
 * servaient. Le mode a disparu le **18/08/2026**, quand son dernier appelant l'a
 * quitté — mais la note, elle, est restée, et a été **recopiée telle quelle dans
 * `evenement.ts`** le lendemain. Une affirmation périmée ne dort pas : elle se
 * propage au fichier suivant.
 *
 * Ce qui subsiste réellement : `EvolForm` n'est gouverné par aucune déclaration,
 * il sert **cinq** écrans, et l'intitulé de sa description bascule
 * « Commentaire » / « Contenu » là où **R3** demande le même libellé partout.
 * C'est **#463** — et non plus #433, fermé le 18/08 après constat en production.
 */
