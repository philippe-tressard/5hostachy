/**
 * La PUBLICATION (une actualité), déclarée une fois — les neuf sections, ce
 * qu'elles portent, et **chaque divergence entre états avec son motif** (R4).
 *
 * Troisième entité mise au cadre #430, et **la plus éloignée des trois** : c'est
 * délibérément qu'elle vient en dernier (#433). La traiter en premier aurait fait
 * porter au mécanisme naissant le poids de ses cas particuliers.
 *
 * ## Ce que la déclaration a trouvé, et qui n'était écrit nulle part
 *
 * L'édition d'une publication était rendue **à la main, 31 lignes**, dans
 * `actualites/+page.svelte`. Elle **perdait** cinq notions que la création
 * propose — périmètre, destinataires, photos, documents, canaux — et **gagnait**
 * un `<select>` « État » que la création n'avait pas. Une publication naissait
 * donc sans état visible et n'en acquérait un qu'à la modification.
 *
 * Aucun de ces écarts n'était une contrainte serveur : `PublicationUpdate`
 * accepte **quinze** champs, le formulaire en proposait sept. Sous le cadre,
 * chacun devait montrer sa raison — et cinq n'en avaient aucune.
 *
 * ## La question tranchée ici : où vivent Épinglage, Urgence, Brouillon et Confidentiel
 *
 * Le cadre pose que **les sections 1 à 8 décrivent l'entité, et que la 9 est un
 * acte** — d'où la seule différence création/édition : la Diffusion tombe, parce
 * qu'*une correction n'est pas une nouvelle*.
 *
 * Ces quatre options-là vivaient dans la Diffusion (`OptionsPublication`, rendu
 * dans la section 9). Les y laisser les aurait fait **disparaître de l'édition**
 * — et publier un brouillon serait devenu impossible : le crayon ✏️ est le seul
 * chemin qui le permette. Or aucune des quatre n'est un acte :
 *
 *   • **Épinglage**, **Urgence** — des qualificatifs durables, que l'affichage
 *     rend en badges ; on les corrige comme on corrige un titre ;
 *   • **Confidentiel** — une règle d'accès, explicitement « modifiable après
 *     publication » côté serveur (arbitrage #347) ;
 *   • **Brouillon** — l'état de mise à disposition. Il reste **hors du workflow**
 *     (arbitrage du 16/08/2026 : *son Publié/Brouillon est une décision de
 *     diffusion, pas une étape de vie*), mais il décrit la publication, il ne
 *     l'envoie pas.
 *
 * Elles sont donc **section 2** — les champs spécifiques de l'actualité —, et la
 * section 9 ne garde que ce qui **part** : WhatsApp, syndic, conseil syndical,
 * affiche de hall. C'est la lecture littérale de *un champ n'est pas un geste* ;
 * c'est aussi ce qui fait que la déclaration se transporte sans rien perdre.
 *
 * ⚠️ Publier un brouillon depuis l'édition **déclenche** les envois retenus
 * (`crud.py`, `was_brouillon_published`). Ce n'est pas un renvoi : c'est l'envoi
 * initial, différé au moment où l'actualité devient publique. Le triple envoi
 * WhatsApp du 14/08/2026 venait de canaux **rejoués**, pas de celui-là.
 *
 * ## Qui consomme cette déclaration
 *
 *   • `FormulaireActualite.svelte` — création ET édition (`sectionPresente`)
 *
 * ⚠️ **Ce que personne ne consomme encore.** L'affichage d'une publication passe
 * par `CarteActualite`, qui ne traverse pas `FicheLecture` : ses documents sont
 * des entités `Document` téléchargeables, pas des URLs, et le squelette de
 * lecture ne sait rendre que les secondes. L'ordre y est déjà celui du cadre
 * (description → photos → documents), mais **rien ne le tient** — c'est le
 * travail que #390 rendra possible en unifiant les pièces jointes.
 */

import type { EntiteDeclaree } from './types';

/**
 * ⚠️ **Le ticket de dette du motif `api`.** Les documents d'une publication sont
 * des entités `Document` rattachées à `publication_id` : il n'existe aucun
 * endpoint qui en remplace la liste, donc rien à ouvrir en édition tant que #390
 * n'a pas unifié les pièces jointes.
 */
const DETTE_API = '#390';

/**
 * ⚠️ **Ne pas factoriser les explications derrière une fonction.** Les cinq
 * divergences `hérité` ci-dessous se ressemblent, et le réflexe est d'en faire un
 * gabarit — `HERITE('Le titre')`. `lint:etats` le refuse, et c'est justifié : il
 * ÉVALUE le littéral tel qu'il est écrit, sans exécuter le module, précisément
 * pour qu'une déclaration reste lisible telle quelle. Un gabarit ferait d'ailleurs
 * dire la même phrase à cinq sections qui n'ont pas la même raison — et une
 * explication est faite pour être lue, pas pour être comptée.
 */
export const PUBLICATION: EntiteDeclaree = {
	id: 'publication',
	libelle: 'Publication',
	sections: [
		{
			id: 'titre',
			objet: 'Titre',
			requis: true,
			absente: {
				evolution: {
					motif: 'hérité',
					explication:
						"Une entrée de l'Historique se rattache à la publication ; elle ne la renomme pas.",
				},
			},
		},
		{
			//  Les quatre options qui DÉCRIVENT la publication — voir l'en-tête de
			//  ce fichier pour la raison qui les sort de la Diffusion.
			id: 'specifiques',
			objet: 'Épinglage · Urgence · Brouillon · Confidentiel',
			titreEcran: 'Options de publication',
			absente: {
				evolution: {
					motif: 'hérité',
					explication:
						"Épinglage, urgence et confidentialité qualifient la publication entière. Une " +
						'entrée du fil ne réépingle pas ce à quoi elle se rattache, et ne peut pas ' +
						"restreindre une lecture que la publication a déjà ouverte.",
				},
			},
		},
		{
			//  🔴 Présente aux QUATRE rendus, et c'est la correction due au cadre.
			//  L'état n'existait qu'en édition : une publication naissait sans état
			//  visible, alors que la création en envoyait un en silence
			//  (`statut: statut || 'publie'`). Il est désormais proposé dès la
			//  création, et son défaut reste `publie` — ce que le formulaire faisait
			//  déjà, mais sans le dire.
			//
			//  La traçabilité ne se perd pas en le rouvrant à l'édition : c'est le
			//  `PATCH` qui a changé de nature côté serveur — il écrit une
			//  **correction**, pas une transition (`publications/crud.py`, #433).
			id: 'workflow',
			objet: 'Publié · En cours · Résolu · Annulé',
		},
		{
			id: 'perimetre',
			objet: 'PerimetrePicker — de quoi il s’agit',
			requis: true,
			absente: {
				evolution: {
					motif: 'hérité',
					explication:
						'Le périmètre est celui de la publication ; une entrée ne le redéfinit pas.',
				},
			},
		},
		{
			id: 'destinataires',
			objet: 'DestinatairePicker — qui est concerné dans l’application',
			absente: {
				evolution: {
					motif: 'hérité',
					explication:
						"Le public visé est celui de la publication. Une entrée qui l'élargirait " +
						'montrerait un suivi à des résidents qui n’ont jamais vu ce qu’il suit.',
				},
			},
		},
		{
			id: 'description',
			objet: 'RichEditor — le contenu de l’actualité',
			requis: true,
		},
		{
			id: 'photos',
			objet: 'FichiersUpload mode photos',
		},
		{
			id: 'documents',
			objet: 'FichiersUpload mode documents (entités `Document` liées)',
			absente: {
				edition: {
					motif: 'api',
					ticket: DETTE_API,
					explication:
						"Les documents d'une publication ne sont pas une liste d'URLs mais des entités " +
						'`Document` rattachées à `publication_id` : `PublicationUpdate` ne les porte pas, ' +
						"et aucun endpoint n'en remplace la liste. Ouvrir la section laisserait ajouter " +
						'des fichiers sans jamais pouvoir en retirer un — la moitié d’un geste. À ' +
						'corriger côté API en unifiant les pièces jointes.',
				},
			},
		},
		{
			id: 'diffusion',
			objet: 'CanauxNotification — WhatsApp, syndic, conseil syndical — et affiche de hall',
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
						'WhatsApp du 14/08/2026, où « Encombrants » est parti trois fois. Le renvoi ' +
						"délibéré garde son chemin : les boutons ✉️ et 💬 de la carte, réservés à l'admin.",
				},
			},
		},
	],
};
