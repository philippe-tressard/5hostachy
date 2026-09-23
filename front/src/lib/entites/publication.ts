/**
 * La PUBLICATION (une actualité), déclarée une fois — les treize sections, ce
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
import { DIFFUSION_NE_SE_LIT_PAS } from './types';

/**
 * ⚠️ **Plus aucun motif `api` ici** depuis le 18/08/2026 : les documents ont
 * rouvert à l'édition. Un motif `api` est une **dette, jamais un choix** — sa
 * disparition est la preuve qu'elle a été payée.
 */

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
	libelle: 'Actualité',
	motDeCode: 'publication',
	libelleNouveau: 'Nouvelle actualité',
	libelleModifier: "Modifier l'actualité",
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
			//  🔴 SANS OBJET, et c'est une question ouverte du chantier (#1091) :
			//  « L'Actualité n'a aucune catégorie — est-ce voulu, ou un manque qu'on
			//  n'a jamais vu parce que le filtre n'existe que sur les affaires ? »
			//  Tant qu'elle n'est pas tranchée, rien ne se pose ici : un champ que
			//  le serveur ne porte pas est ce que le cadre interdit.
			id: 'nature',
			sansObjet:
				'`Publication` ne porte aucune catégorie. La question de lui en donner ' +
				'une est ouverte (#1091) ; elle se tranchera avant d’ouvrir un champ.',
		},
		{
			id: 'equipement',
			sansObjet:
				'Une actualité informe, elle n’entretient rien. L’équipement qualifie ce ' +
				'qui se répare, et c’est l’affaire qui le porte.',
		},
		{
			//  🔴 UNE ACTUALITÉ N'A PAS DE WORKFLOW — arbitré le 18/08/2026, après
			//  l'avoir ouvert la veille. Elle n'a pas d'étapes de vie : elle est
			//  publiée, puis elle vieillit et bascule dans l'Historique toute seule.
			//  « En cours », « Résolu », « Annulé » sont le vocabulaire d'un TICKET,
			//  et les emprunter faisait ressembler une annonce à un dossier suivi.
			//
			//  Ce qui reste et qui n'est PAS un workflow : le Brouillon, qui décide
			//  de la mise à disposition — il est en section 2, avec l'épinglage,
			//  l'urgence et la confidentialité (« Publié/Brouillon est une décision
			//  de diffusion », arbitrage du 16/08).
			//
			//  ⚠️ La colonne `statut` existe toujours en base et d'anciennes
			//  publications en portent un : la carte l'affiche encore en badge, en
			//  LECTURE. Rien ne permet plus d'en poser un — et l'archivage manuel,
			//  qui exigeait « Résolu », a disparu avec lui.
			id: 'suivi',
			sansObjet:
				"Une actualité n'a pas d'étapes de vie : elle est publiée, puis elle " +
				"bascule dans l'Historique au bout de son délai. Le Brouillon, lui, n'est " +
				'pas un workflow mais une décision de diffusion — il vit en section 2.',
		},
		{
			id: 'quand',
			objet: 'SectionQuand — début et fin, ce qui fait paraître au calendrier',
			//  Pas d'échéance : une actualité ne se suit pas. Renseigner un début
			//  rend la description facultative — « Coupure d'eau jeudi 9h-12h » se
			//  suffit —, et c'est le serveur qui tranche (`utils/quand.py`), pas
			//  cet écran : l'astérisque ne vivait QUE dans le formulaire (#1092).
			pliee: true,
		},
		{
			id: 'intervenant',
			sansObjet:
				'Personne n’intervient sur une actualité : elle se lit, elle ne se traite ' +
				'pas. Le jour où elle demande un suivi, elle devient une affaire (#1094).',
		},
		{
			id: 'perimetre',
			objet: 'PerimetrePicker — de quoi il s’agit',
			requis: true,
			//  Ouvert à l'évolution le 05/09/2026 (voir la section 2 ci-dessus) :
			//  le champ part rempli du périmètre en vigueur, et ce qu'on enregistre
			//  devient le périmètre de la publication. C'est un geste de CORRECTION,
			//  pas de précision — d'où une aide différente de celle du ticket.
		},
		{
			id: 'description',
			objet: 'RichEditor — le contenu de l’actualité',
			requis: true,
		},
		{
			//  ✅ Les DOCUMENTS ont été ouverts à l'édition le 18/08/2026. La dette
			//  `api` qui les fermait citait #390 — « aucun endpoint n'en remplace la
			//  liste » — mais la demande était plus simple que la refonte : la
			//  publication EXISTE au moment où on la corrige, donc on téléverse à
			//  l'unité (`POST /documents`) et on retire à l'unité
			//  (`DELETE /documents/{id}`). Il n'y a jamais eu besoin de remplacer une
			//  liste.
			//
			//  🔴 #390 visait précisément ce que ce lot-ci fait : unifier les pièces
			//  jointes derrière `FichiersUpload`. Une section, deux réservoirs —
			//  `photos_urls` (des URLs) et les `Document` (des entités avec un
			//  identifiant) —, parce que le SERVEUR les distingue et que ce lot ne
			//  touche pas au modèle.
			id: 'pieces_jointes',
			objet: 'FichiersUpload mode mixte — photos (URLs) et documents (entités `Document`)',
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
			//  L'actualité porte « Saisi pour » depuis le 15/09/2026, comme l'affaire
			//  et l'événement — c'est le mixin `SaisiPourMixin` côté serveur.
			//  🔴 Obligatoire, donc DEPLIEE — et plus d'exception (22/09/2026).
			//
			//  Elle etait pliee, au motif que « en mon nom » est juste dans la
			//  quasi-totalite des cas. Signale a l'ecran le jour de sa livraison :
			//  une section marquee d'une asterisque qui arrive fermee demande de
			//  l'ouvrir pour voir qu'il n'y a rien a y faire, ce qui est exactement
			//  le contraire de ce que l'asterisque annonce.
			//
			//  ⚠️ C'etait la SEULE exception de pliage du cadre. La regle
			//  « obligatoire -> deplie, facultatif -> plie » n'en a plus aucune, et
			//  c'est ce que l'utilisateur a demande : « pour eviter toute exception ».
			id: 'au_nom_de',
			objet: 'Saisi pour — en mon nom · un résident inscrit · une personne extérieure',
			requis: true,
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
			objet: 'DestinatairePicker — qui est concerné dans l’application',
			//  Ouvert à l'évolution le 05/09/2026, comme les deux sections
			//  ci-dessus. La réserve d'origine — « une entrée qui élargirait le
			//  public montrerait un suivi à des résidents qui n'ont jamais vu ce
			//  qu'il suit » — vaut pour un ciblage propre à l'ENTRÉE. Ici il n'y en
			//  a pas : on modifie celui de la publication, donc le suivi et ce qu'il
			//  suit restent visibles des mêmes personnes, par construction.
		},
		{
			//  Extraite de l'ancienne section « Options de publication » (#1095). Le
			//  pourquoi de CES quatre options-là — et pas d'autres — est en tête de
			//  ce fichier : ce sont des qualificatifs durables, pas des actes.
			id: 'mise_en_avant',
			objet: 'Épinglage · Urgence · Brouillon · Confidentiel',
			titreEcran: 'Mise en avant',
			pliee: true,
		},
		{
			//  ✅ ROUVERTE à l'édition le 18/08/2026, comme sur les tickets — signalé
			//  à l'écran : « il manque la section notification en Diffusion, en mode
			//  Édition ». Les boutons ✉️ et 💬 de renvoi avaient disparu de la carte
			//  le matin même : sans cette section, plus AUCUN chemin ne permettait de
			//  prévenir le syndic d'une actualité déjà publiée.
			//
			//  🔴 Ce qui rend la réouverture sûre vit côté serveur : seule la
			//  transition décoché → coché envoie. Un canal déjà coché ne repart pas à
			//  chaque enregistrement — sinon corriger une faute de frappe rejouerait
			//  l'envoi, et c'est l'incident du triple envoi WhatsApp du 14/08/2026.
			id: 'diffusion',
			objet: 'CanauxNotification — WhatsApp, syndic, conseil syndical — et affiche de hall',
			absente: {
				affichage: DIFFUSION_NE_SE_LIT_PAS,
			},
			pliee: true,
		},
	],
};
