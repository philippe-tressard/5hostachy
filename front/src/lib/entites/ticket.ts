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
 *     quatre écrans, il rejoindra le cadre avec #433 — cf. la note en fin de
 *     fichier)*
 *
 * ⚠️ **Rien de spécifique au ticket ne doit s'écrire ailleurs.** Si un écran a
 * besoin de savoir qu'une section du ticket est absente quelque part, il appelle
 * `sectionPresente` — il ne réécrit pas la condition.
 */

import type { EntiteDeclaree } from './types';

/**
 * ⚠️ **Le ticket de dette des motifs `api`.** Écrit une fois : les deux
 * divergences ci-dessous tombent le jour où l'API sait faire, et elles doivent
 * tomber ENSEMBLE — sinon la seconde survit à l'oubli de la première.
 */
const DETTE_API = '#431';

export const TICKET: EntiteDeclaree = {
	id: 'ticket',
	libelle: 'Ticket',
	sections: [
		{
			id: 'titre',
			objet: 'Catégorie + Titre',
			requis: true,
			absente: {
				evolution: {
					motif: 'hérité',
					explication:
						"Une entrée de l'Historique se rattache au ticket ; elle ne le renomme pas.",
				},
			},
		},
		{
			id: 'specifiques',
			objet: 'Saisi pour (en mon nom / résident inscrit / personne extérieure)',
			titreEcran: 'Saisi pour',
			absente: {
				edition: {
					motif: 'api',
					ticket: DETTE_API,
					explication:
						"`TicketUpdate` accepte bien les trois champs `saisi_pour_*`, mais ne sait pas " +
						"les EFFACER : un `None` y est indistinguable d'un champ non envoyé. Rouvrir la " +
						"section proposerait « En mon nom » comme un choix qui ne fait rien, en silence — " +
						'un contrôle qui ment est pire que son absence. À corriger côté API.',
				},
				evolution: {
					motif: 'hérité',
					explication:
						"La personne pour qui le ticket a été saisi appartient au ticket, pas à l'entrée.",
				},
			},
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
			id: 'perimetre',
			objet: 'PerimetrePicker — de quoi il s’agit',
			requis: true,
			absente: {
				evolution: {
					motif: 'hérité',
					explication: 'Le périmètre est celui du ticket ; une entrée ne le redéfinit pas.',
				},
			},
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
			id: 'photos',
			objet: 'FichiersUpload mode photos',
			absente: {
				edition: {
					motif: 'api',
					ticket: DETTE_API,
					explication:
						"`TicketUpdate` n'accepte pas `photos_urls`. Proposer le champ ferait " +
						"disparaître la sélection à l'enregistrement, sans un mot. C'est un défaut à " +
						'corriger côté API, pas un choix à entériner.',
				},
			},
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
				edition: {
					motif: 'geste',
					explication:
						"Une correction n'est pas une nouvelle. Rouvrir les canaux renverrait un " +
						'message à chaque faute de frappe rattrapée — incident du triple envoi ' +
						'WhatsApp du 14/08/2026, où « Encombrants » est parti trois fois.',
				},
			},
		},
	],
};

/**
 * ⚠️ **Ce que cette déclaration ne gouverne PAS encore, et pourquoi.**
 *
 * L'état `evolution` est déclaré ici, mais `EvolForm.svelte` ne le consomme pas :
 * ce composant sert **quatre écrans** (tickets, fiche de ticket, actualités,
 * espace CS) et l'y brancher changerait les trois autres avant qu'on les ait
 * regardés. C'est très exactement ce que R5 interdit : *l'enrichissement se
 * propose sur UN écran, se fait constater, puis se généralise*.
 *
 * Il reste donc une divergence connue et non gouvernée : `EvolForm` sait rendre
 * les pièces jointes **unifiées** (`separatePhotosAndDocs = false`), ce qui
 * fusionne les sections 7 et 8 — interdit par le cadre. Les tickets ne l'utilisent
 * pas (`separatePhotosAndDocs = true`) ; les actualités et l'espace CS, si. La
 * remise en conformité est le travail de **#433**, pas de celui-ci : *une variante
 * ajoutée pour accueillir un écart existant ne factorise pas, elle entérine* — mais
 * la retirer d'ici toucherait deux écrans que ce lot n'a pas mesurés.
 */
