/**
 * Les pages réservées à un RÔLE — conseil syndical, délégations, administration.
 *
 * ## Pourquoi un second fichier (12/09/2026, #928)
 *
 * `pages.ts` a franchi son plafond de modularité en recevant l'onglet
 * « Badges & télécommandes ». C'est une TABLE : elle grossit légitimement quand
 * le produit gagne un écran, et la faire maigrir en raccourcissant des
 * descriptifs serait raboter — ce qu'`ux-patterns` §0 interdit.
 *
 * La coupe suit donc ce que les pages SONT : d'un côté celles que tout résident
 * ouvre, de l'autre celles qu'un rôle ouvre. Même geste que `routes-onglets.ts`,
 * qui a quitté `pages.ts` le 05/09 pour la même raison.
 *
 * ⚠️ La table reste UNE : `PAGES` les concatène, et `lint:pages` continue de
 * refuser une route écrite ailleurs. Deux fichiers, une source.
 *
 * ⚠️ `import type` et non `import` : le type vit dans `pages.ts`, qui importe ce
 * fichier-ci. Un import de VALEUR serait circulaire ; un import de TYPE est
 * effacé à la compilation, donc il n'existe pas à l'exécution.
 */
import type { PageDef } from './pages';

export const PAGES_ROLES: PageDef[] = [
	{
		id: 'espace-cs',
		href: '/espace-cs',
		nom: 'Espace CS',
		titre: 'Espace Conseil Syndical (CS)',
		navLabel: 'Espace CS',
		icone: 'shield-half',
		descriptif:
			'Tableau de bord des membres du Conseil Syndical (CS) : suivi des comptes, reporting, relance syndic et demandes d\'accès — réservé au Conseil Syndical. Les tickets de la résidence se traitent depuis la page <a href="/tickets">Tickets</a>.',
		onglets: [
			{
				id: 'validations',
				route: '/espace-cs',
				label: '✅ Comptes & accès',
				descriptif: "Comptes en attente, demandes d'accès et validations à traiter.",
			},
			{
				//  🔴 Onglet DÉDIÉ (12/09/2026) : « Comptes & accès » est une FILE DE
				//  TRAVAIL, dont la valeur est d'être courte ; le parc de badges est un
				//  RÉFÉRENTIEL qu'on consulte. Les mêler ferait cesser de lire la file.
				id: 'badges',
				route: '/espace-cs/badges',
				label: '\u{1F3F7}\uFE0F Badges & télécommandes',
				descriptif:
					'Tous les badges Vigik et télécommandes de la copropriété, avec leur porteur et leur lot. Vue de consultation : un badge s’enregistre par l’import du syndic, ou par son porteur.',
			},
			{
				id: 'reporting',
				route: '/espace-cs/reporting',
				label: '\u{1F4CA} Reporting',
				descriptif:
					'Synthèses et indicateurs : kanban, tableau des tickets, prestataires, renouvellements de contrats et relance syndic.',
			},
			{
				id: 'annonces-hall',
				route: '/espace-cs/annonces-hall',
				label: '\u{1F4C4} Annonces Hall',
				descriptif:
					"Créez une annonce à afficher dans le hall des bâtiments : PDF à la charte de la résidence, envoyé par mail aux membres du CS concernés, puis conservé dans l'historique.",
			},
			{
				id: 'annuaire',
				route: '/espace-cs/annuaire',
				label: '\u{1F4D2} Annuaire CS & Syndic',
				descriptif: 'Coordonnées des membres du CS et du syndic.',
			},
		],
	},
	{
		id: 'delegations',
		href: '/delegations',
		nom: 'Délégations',
		titre: 'Délégations aidant',
		navLabel: 'Délégations',
		icone: 'heart-handshake',
		descriptif:
			"Gestion des accès délégués pour les proches aidants : un proche peut consulter et agir à votre place, sans que cela constitue une procuration d'assemblée générale.",
	},
	{
		id: 'admin',
		href: '/admin',
		nom: 'Paramétrage',
		titre: 'Paramétrage',
		navLabel: 'Admin',
		icone: 'sliders-horizontal',
		descriptif:
			'Administration de la plateforme : comptes, utilisateurs, rôles, modèles e-mail, paramétrage et référentiels — réservés aux admins.',
	},
];
