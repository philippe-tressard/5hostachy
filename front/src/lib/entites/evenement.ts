/**
 * L'ÉVÉNEMENT de calendrier, déclaré une fois — les neuf sections, ce qu'elles
 * portent, et **chaque divergence entre états avec son motif** (R4).
 *
 * Cinquième entité mise au cadre #430, et le lot **#432**.
 *
 * ## Pourquoi cet écran arrive maintenant, alors qu'il paraissait déjà conforme
 *
 * Le calendrier est le seul couple menu/entité du site à atteindre **100 % de
 * recouvrement entre création et édition** : un seul `form`, un seul `save()`,
 * `editId` pour seul discriminant, et `FormulaireEvenement` qui n'écrit aucun
 * champ commun à la main. Sa carte a rejoint la norme le 18/08/2026
 * (`EnteteCarte`, `ApercuCarte`, `HistoriqueEvenement`).
 *
 * 🔴 **Et pourtant le garde-fou y était vert par absence de sujet.**
 * `FormulaireEvenement` posait `avecPerimetre avecDescription avecPhotos
 * avecDocuments avecDiffusion` **en dur** — exactement ce que `lint:etats`
 * refuse — sans que rien n'échoue : le contrôle ignore tout fichier qui
 * n'importe aucune entité (`if (importe.length === 0) continue`). Un écran sans
 * déclaration n'est pas un écran conforme, c'est un écran **hors de portée du
 * contrôle**.
 *
 * C'est le cas zéro de `standards/04` §2 sous une autre forme : le contrôle
 * n'échouait pas, il n'avait simplement rien à regarder. Écrire ce fichier
 * l'allume.
 *
 * ## Qui consomme cette déclaration
 *
 *   • `FormulaireEvenement.svelte` — création ET édition (`sectionPresente`)
 *   • `CarteEvenement.svelte`      — l'affichage, via `FicheLecture`
 *   • `HistoriqueEvenement.svelte` → `EvolForm` — **pas encore** : voir la note
 *     en fin de fichier.
 */

import type { EntiteDeclaree } from './types';

export const EVENEMENT: EntiteDeclaree = {
	id: 'evenement',
	libelle: 'Événement',
	sections: [
		{
			id: 'titre',
			objet: 'Titre',
			requis: true,
			absente: {
				evolution: {
					motif: 'hérité',
					explication:
						"Une entrée de l'Historique se rattache à l'événement ; elle ne le renomme pas.",
				},
			},
		},
		{
			//  SEPT champs sous un titre de groupe — d'où « Détails » plutôt qu'une
			//  liste d'intitulés : une section à plusieurs champs garde son titre de
			//  groupe ET les libellés de ses champs, ce n'est pas une redite mais une
			//  hiérarchie (ux-patterns §9 septies).
			//
			//  ⚠️ La fréquence n'apparaît qu'avec un prestataire choisi, et sa valeur
			//  qu'avec une fréquence. C'est une divergence de CHAMP à l'intérieur
			//  d'une section, que R4 ne sait pas déclarer (#436) — elle est ici en
			//  commentaire, donc invisible au contrôle, et c'est dit.
			id: 'specifiques',
			objet: 'Type · Date de début · Heure · Fin · Lieu · Prestataire · Fréquence',
			titreEcran: 'Détails',
			absente: {
				evolution: {
					motif: 'hérité',
					explication:
						"Le type, les dates, le lieu et le prestataire appartiennent à l'événement. " +
						'Une entrée du fil raconte ce qui lui arrive, elle ne le reprogramme pas.',
				},
			},
		},
		{
			//  🔴 LE KANBAN *EST* LE WORKFLOW (arbitré le 18/08/2026). Ses colonnes —
			//  AG · CS · Syndic · Prestataire · Terminé · Annulé — répondent exactement
			//  à la question de la section 3, « où en est cet objet ? ». La section
			//  s'appelait « Suivi Kanban », ce qui nommait l'écran où on le voit plutôt
			//  que la notion ; et avant cela elle était rangée dans la DIFFUSION, qui
			//  dit qui voit l'objet et non où il en est.
			//
			//  ⚠️ **Aucun second champ d'état n'existe** : `statut_kanban` et rien
			//  d'autre. Deux notions de suivi sur le même objet se contredisent au
			//  premier écart, et rien ne dirait laquelle fait foi.
			//
			//  Il est **présent en évolution**, et c'est ce qui a changé le 18/08 : le
			//  calendrier était le dernier écran du site à faire avancer un suivi en
			//  silence. Un changement de colonne est désormais une transition tracée,
			//  avec son avant et son après.
			//
			//  ⚠️ **Non requis**, à la différence de l'état d'un ticket : « — Pas de
			//  suivi » est une pastille comme les autres, active par défaut. Un
			//  événement peut légitimement n'avoir aucun suivi — une AG a une date,
			//  pas un dossier.
			id: 'workflow',
			objet: 'Kanban — AG · CS · Syndic · Prestataire · Terminé · Annulé (ou aucun suivi)',
		},
		{
			id: 'perimetre',
			objet: 'PerimetrePicker — de quoi il s’agit',
			requis: true,
			absente: {
				evolution: {
					motif: 'hérité',
					explication:
						"Le périmètre est celui de l'événement ; une entrée ne le redéfinit pas.",
				},
			},
		},
		{
			id: 'destinataires',
			sansObjet:
				"Un événement n'adresse personne nommément dans l'application : il est vu par qui " +
				'son périmètre concerne, et le Kanban filtre déjà ses colonnes selon le statut du ' +
				"lecteur. `envoyer_syndic` et `envoyer_cs` ne sont PAS des destinataires au sens " +
				'de la section 5 — ce sont deux canaux, et ils vivent en Diffusion (section 9), ' +
				'comme sur les tickets.',
		},
		{
			//  ⚠️ **Non requise**, et c'est la seule des cinq entités déclarées dans ce
			//  cas. Un ticket sans description ne dit pas quel est le problème ; un
			//  événement dont on connaît le type, la date et le lieu se comprend sans
			//  une ligne de plus — « Coupure d'eau · bâtiment C · mardi » est complet.
			//  L'écran ne l'a jamais exigée : la déclaration le constate, elle ne le
			//  change pas.
			id: 'description',
			objet: 'RichEditor — de quoi il retourne',
		},
		{
			id: 'photos',
			objet: 'FichiersUpload mode photos',
		},
		{
			id: 'documents',
			objet: 'FichiersUpload mode documents',
		},
		{
			//  ⚠️ Le TÉLÉVERSEMENT est **immédiat** sur cet écran, et ce n'est pas un
			//  détail d'implémentation : c'est ce qui permet à l'e-mail de notification
			//  de partir AVEC les photos. Rien ici ne doit le déplacer — et cela ne se
			//  voit pas à l'écran (#432).
			id: 'diffusion',
			objet:
				'CanauxNotification — WhatsApp, syndic, conseil syndical — et l’affichage au fil ' +
				'du tableau de bord (affichable, épinglé)',
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
 * L'état `evolution` est déclaré ici, mais `EvolForm.svelte` ne le consomme
 * pas : ce composant sert **quatre écrans** — tickets, fiche de ticket,
 * actualités, espace CS — auxquels le calendrier s'est ajouté le 18/08/2026 via
 * `HistoriqueEvenement`. L'y brancher les changerait tous **avant** qu'on les
 * ait regardés, et c'est très exactement ce que R5 interdit : *l'enrichissement
 * se propose sur UN écran, se fait constater, puis se généralise*.
 *
 * La divergence connue et non gouvernée est la même que côté tickets, et le
 * calendrier est du mauvais côté : `HistoriqueEvenement` passe `showFiles`, et
 * `EvolForm` rend alors les pièces jointes **unifiées**
 * (`separatePhotosAndDocs = false`) — ce qui fusionne les sections 7 et 8, que
 * le cadre interdit. La remise en conformité est le travail de **#433**, pas de
 * celui-ci : *une variante ajoutée pour accueillir un écart existant ne
 * factorise pas, elle entérine* — mais la retirer d'ici toucherait trois écrans
 * que ce lot n'a pas mesurés.
 */
