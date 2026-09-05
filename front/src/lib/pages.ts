/**
 * Source unique des pages de l'application : identifiant de configuration, route,
 * libellés, icône, descriptif et onglets.
 *
 * Posé le 17/08/2026 (#401). Ces informations vivaient dans DEUX tables qui ne se
 * connaissaient pas — `NAV_DEFAULTS` + `DEFAULT_HREFS` dans `Nav.svelte`, et
 * `pagesDefaults` dans l'écran `admin` — et elles avaient déjà divergé de trois
 * façons, chacune invisible :
 *
 *  1. **Les deux ordres par défaut n'étaient pas le même.** Le menu commençait par
 *     Résidence, Mes lots, Accès & badges ; l'écran d'administration par Actualités,
 *     Tickets, Mes lots. Deux listes décrivaient le même ordre sans dire la même chose.
 *  2. **`profil` et `notifications` étaient réordonnables sans être dans le menu.**
 *     L'écran proposait le geste, `Nav` écartait ces identifiants en silence : le
 *     déplacement n'avait aucun effet, et rien ne le disait.
 *  3. **`delegations` était dans le menu sans être dans l'écran.** On ne pouvait donc
 *     ni la positionner ni la renommer, et elle atterrissait toujours en dernier —
 *     après Admin — par le jeu du repli sur l'ordre par défaut.
 *
 * `href: null` = page atteignable sans entrée de menu (profil, notifications). C'est
 * la même distinction qui décide des flèches d'ordre dans l'écran d'administration :
 * on n'ordonne que ce qui apparaît dans le menu.
 *
 * ⚠️ Ne jamais recopier cette table, même partiellement : `npm run lint:pages` refuse
 * tout identifiant ou route de page écrit ailleurs, **et tout titre, descriptif,
 * libellé de menu, icône ou onglet passé en dur à `getPageConfig`** — les pages
 * prennent leurs valeurs par défaut de `defautsDePage()` (#420). Une table recopiée
 * finit toujours par diverger de celle qu'elle copie — c'est exactement ce qui s'est
 * produit ici, et c'est déjà arrivé aux périmètres (#316) et aux canaux de
 * notification.
 */

import { TITRE_ARCHIVES } from '$lib/archives';
import type { PageConfig } from '$lib/stores/pageConfig';

export interface OngletDef {
	id: string;
	label: string;
	descriptif: string;
	/**
	 * L'URL dédiée de cet onglet — celle qu'on copie dans la barre d'adresse et
	 * qu'on envoie à un voisin. Elle est ABSOLUE (elle commence par `/`) et non
	 * relative à la page : les trois rubriques de la Communauté vivent à la racine
	 * (`/annonces`), les vues d'un même objet sous leur page (`/calendrier/kanban`).
	 *
	 * La règle, arbitrée le 05/09/2026 : **plate quand l'onglet est un CONTENU,
	 * imbriquée quand il est une VUE**. `/kanban` ou `/archives` seuls ne disent
	 * pas de quoi ils parlent ; `/annonces` si.
	 *
	 * ⚠️ La route de l'onglet par défaut est celle de la page (`href`) : sans quoi
	 * l'entrée de menu et le premier onglet seraient deux adresses pour le même
	 * écran, et `test_liens_front.py` refuse.
	 */
	route: string;
	/** Les sous-onglets, quand l'onglet en porte une rangée (un seul cas : les
	    baux de la gestion locative). Ils ont une URL, pas d'entrée dans la
	    configuration éditable — l'administration n'ordonne et ne renomme que les
	    onglets de premier niveau. */
	sous?: SousOngletDef[];
}

/** Un sous-onglet : une URL et rien d'autre. Son libellé vit dans l'écran, qui
    est le seul à savoir ce qu'il compte (« Baux actifs (3) »). */
export interface SousOngletDef {
	id: string;
	route: string;
}

export interface PageDef {
	/** Identifiant de configuration : clé `page_config_<id>` et entrée de `pages_order`. */
	id: string;
	/** Route du menu, ou `null` pour une page sans entrée de navigation. */
	href: string | null;
	/** Nom de la page dans l'écran « Descriptif pages ». */
	nom: string;
	/** Titre affiché en tête de la page. */
	titre: string;
	/** Libellé dans le menu de navigation. */
	navLabel: string;
	icone: string;
	descriptif: string;
	onglets?: OngletDef[];
}

/** Toutes les pages, dans l'ordre de navigation par défaut. */
export const PAGES: PageDef[] = [
	{
		id: 'tableau-de-bord',
		href: '/tableau-de-bord',
		nom: 'Tableau de bord',
		titre: 'Tableau de bord',
		navLabel: 'Accueil',
		icone: 'layout-dashboard',
		descriptif:
			'Votre espace numérique de résidence : actualités, demandes, accès et gouvernance de votre copropriété en un seul endroit.',
	},
	{
		id: 'residence',
		href: '/residence',
		nom: 'Ma résidence',
		titre: 'Ma résidence',
		navLabel: 'Résidence',
		icone: 'building-2',
		descriptif: 'Informations, plans et documents de la copropriété.',
	},
	{
		id: 'mon-lot',
		href: '/mon-lot',
		nom: 'Mes lots',
		titre: 'Mes lots',
		navLabel: 'Mes lots',
		icone: 'door-closed',
		descriptif:
			'Informations sur votre bien : situation de vos lots (appartement, cave & parkings) dans la résidence et gestion locative pour les copropriétaires mandataires.',
		onglets: [
			{
				id: 'lots',
				route: '/mon-lot',
				label: '\u{1F3E0} Mes lots',
				descriptif: 'Situation de vos lots dans la résidence : appartements, caves et parkings.',
			},
			{
				id: 'location',
				route: '/mon-lot/location',
				sous: [
					{ id: 'actif', route: '/mon-lot/location' },
					{ id: 'archives', route: '/mon-lot/location/archives' },
				],
				label: '\u{1F4CB} Gestion locative',
				descriptif: 'Suivi de vos baux, locataires et documents de gestion locative.',
			},
		],
	},
	{
		id: 'acces-badges',
		href: '/acces-securite',
		nom: 'Accès & badges',
		titre: 'Accès & badges',
		navLabel: 'Accès & badges',
		icone: 'key-round',
		descriptif:
			'Gestion de vos télécommandes parkings & Vigiks. <a href="/faq#badge-prix" style="font-size:.85rem">Quel prix pour un badge ?</a>',
	},
	{
		id: 'annuaire',
		href: '/annuaire',
		nom: 'Annuaire',
		titre: 'Annuaire',
		navLabel: 'Annuaire',
		icone: 'users',
		descriptif:
			"Coordonnées des membres du Conseil Syndical et du Syndic. En cas d'urgence, contactez le syndic directement par téléphone. Sinon, faites une demande depuis la plateforme.",
	},
	{
		id: 'prestataires',
		href: '/prestataires',
		nom: 'Prestataires',
		titre: 'Prestataires',
		navLabel: 'Prestataires',
		icone: 'hard-hat',
		descriptif:
			'Intervenants de la résidence et leurs contrats de maintenance (avec synthèse IA du contrat) et documents contractuels.',
		onglets: [
			{
				id: 'prestataires',
				route: '/prestataires',
				label: '\u{1F527} Prestataires',
				descriptif: "Intervenants et contrats d'entretien de la résidence.",
			},
			{
				id: 'contrats',
				route: '/prestataires/contrats',
				label: '\u{1F4C4} Contrats',
				descriptif: "Contrats d'entretien en cours, leur échéance et leurs documents.",
			},
			{
				id: 'consommations',
				route: '/prestataires/consommations',
				label: '\u{1F4A7} Consommations',
				descriptif: 'Suivi des relevés de compteurs et abonnements de la résidence.',
			},
		],
	},
	{
		id: 'calendrier',
		href: '/calendrier',
		nom: 'Calendrier',
		titre: 'Calendrier',
		navLabel: 'Calendrier',
		icone: 'calendar-days',
		descriptif: 'Agenda des événements et interventions de la résidence.',
		onglets: [
			{
				id: 'liste',
				route: '/calendrier',
				label: '\u{1F4CB} Liste',
				descriptif: 'Les événements, du plus lointain au plus ancien.',
			},
			{
				id: 'kanban',
				route: '/calendrier/kanban',
				label: '\u{1F5C3}️ Kanban',
				descriptif: 'Organisation visuelle des événements par statut.',
			},
			{
				id: 'archives',
				route: '/calendrier/archives',
				//  Le mot ET son icône viennent de `$lib/archives` : ils étaient recopiés
				//  ici, et #516 existe précisément pour qu'« Archives » ne s'écrive qu'une
				//  fois — la recopie concordait, à l'instant où on l'avait posée.
				label: TITRE_ARCHIVES,
				descriptif: 'Actualités et événements archivés.',
			},
		],
	},
	{
		id: 'actualites',
		href: '/actualites',
		nom: 'Actualités',
		titre: 'Actualités',
		navLabel: 'Actualités',
		icone: 'newspaper',
		descriptif:
			'Publications officielles du conseil syndical : informations importantes, travaux et actualités de la résidence.',
	},
	{
		id: 'mes-demandes',
		href: '/tickets',
		nom: 'Tickets',
		titre: 'Mes Tickets',
		navLabel: 'Tickets',
		icone: 'message-square-text',
		descriptif:
			'Signalez un problème, une nuisance ou posez une question au conseil syndical. Suivez l’avancement de vos tickets.',
	},
	{
		id: 'communaute',
		href: '/sondages',
		nom: 'Communauté',
		titre: 'Communauté',
		navLabel: 'Communauté',
		icone: 'users-round',
		descriptif: 'Sondages, boîte à idées et petites annonces entre résidents.',
		onglets: [
			{
				id: 'sondages',
				route: '/sondages',
				label: '\u{1F4CA} Sondages',
				descriptif: 'Participez aux votes et consultations de la copropriété.',
			},
			{
				id: 'idees',
				route: '/idees',
				label: '\u{1F4A1} Boîte à idées',
				descriptif: 'Proposez et soutenez des idées pour améliorer la vie en résidence.',
			},
			{
				id: 'annonces',
				route: '/annonces',
				label: '\u{1F3F7}️ Petites annonces',
				descriptif: 'Achetez, vendez ou donnez des objets entre résidents.',
			},
		],
	},
	{
		id: 'faq',
		href: '/faq',
		nom: 'FAQ',
		titre: 'FAQ',
		navLabel: 'FAQ',
		icone: 'help-circle',
		descriptif:
			'Réponses aux questions fréquentes sur la vie en résidence, les services et la réglementation de la copropriété.',
	},
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
	{
		id: 'profil',
		href: null,
		nom: 'Mon profil',
		titre: 'Mon profil',
		navLabel: 'Profil',
		icone: 'user',
		descriptif:
			'Vos informations personnelles (mot de passe, lots...), sécurité du compte et préférences de notifications.',
	},
	{
		id: 'notifications',
		href: null,
		nom: 'Notifications',
		titre: 'Notifications',
		navLabel: 'Notifications',
		icone: 'bell',
		descriptif: 'Vos alertes et messages.',
	},
];

/** Les pages qui ont une entrée de menu — les seules qui s'ordonnent. */
export const PAGES_MENU: PageDef[] = PAGES.filter(
	(p): p is PageDef & { href: string } => p.href !== null,
);

/** Ordre de navigation par défaut, quand aucun ordre n'a été enregistré. */
export const HREFS_DEFAUT: string[] = PAGES_MENU.map((p) => p.href as string);

/** Identifiant de configuration → route. Sert à relire `pages_order`. */
export const ID_VERS_HREF: Record<string, string> = Object.fromEntries(
	PAGES_MENU.map((p) => [p.id, p.href as string]),
);

/** Route → page. */
export const HREF_VERS_PAGE: Record<string, PageDef> = Object.fromEntries(
	PAGES_MENU.map((p) => [p.href as string, p]),
);

/**
 * Valeurs par défaut d'une page, dans la forme attendue par `getPageConfig`.
 *
 * Posé le 17/08/2026 (#420) : la table n'était pas encore la seule source. Chaque
 * page recopiait à la main, dans le troisième argument de `getPageConfig`, les
 * valeurs déjà écrites ici — et DIX pages sur seize avaient déjà divergé (huit sur
 * un texte, deux sur une icône, deux sur leurs onglets), chacune cohérente de son
 * côté. La plus visible : `espace-cs` affichait un onglet
 * « Annonces Hall » que la table ignorait, donc que l'administrateur ne pouvait ni
 * renommer ni décrire dans « Descriptif pages » ; et son descriptif de page taisait
 * la relance syndic, que la table annonçait.
 *
 * La conversion liste → dictionnaire vit ICI et nulle part ailleurs : la table
 * décrit les onglets comme une LISTE — ils sont ordonnés, c'est l'ordre de l'écran —
 * quand la configuration enregistrée les indexe par identifiant, parce qu'elle est
 * partielle et éditable onglet par onglet.
 *
 * Lève si l'identifiant est absent de la table : une page configurée sous un
 * identifiant que la table ignore n'est ni ordonnable ni renommable, et rien ne le
 * dit — c'est la divergence n° 3 de #401. `npm run lint:pages` attrape le cas en CI,
 * avant que l'exécution n'ait la moindre chance de le rencontrer.
 */
export function defautsDePage(id: string): PageConfig {
	const def = PAGES.find((p) => p.id === id);
	if (!def) {
		throw new Error(
			`Page « ${id} » absente de PAGES (src/lib/pages.ts) : lui ajouter une entrée dans ` +
				'la table, plutôt que de recopier ses valeurs par défaut sur place.',
		);
	}
	return configDepuisPage(def);
}

/**
 * Passe d'une page — telle que la décrit la table ou telle que l'administration
 * vient de l'éditer — à la forme configuration : c'est ce que sérialise
 * `page_config_<id>` et ce qu'attend `getPageConfig`.
 *
 * Prend une page en paramètre plutôt qu'un identifiant, parce que l'écran
 * d'administration enregistre des valeurs MODIFIÉES, qui ne sont plus celles de la
 * table : il partage la conversion, pas la source.
 */
export function configDepuisPage(def: PageDef): PageConfig {
	return {
		titre: def.titre,
		descriptif: def.descriptif,
		navLabel: def.navLabel,
		icone: def.icone,
		onglets: def.onglets
			? Object.fromEntries(
					def.onglets.map((o) => [o.id, { label: o.label, descriptif: o.descriptif }]),
				)
			: undefined,
	};
}

/**
 * Range des pages selon un ordre enregistré (`pages_order`), en reléguant toujours
 * en fin celles qui n'ont pas d'entrée de menu.
 *
 * Sans cette dernière règle, un ordre enregistré AVANT #401 — qui nommait encore
 * `profil` et `notifications` — les replaçait à leur position stockée, tandis que
 * `delegations`, absente de cet ordre puisqu'elle n'était pas proposée, tombait en
 * dernier : une page ordonnable s'affichait sous deux pages qui ne le sont pas
 * (constaté en production le 17/08/2026). Le premier déplacement réécrivait l'ordre
 * et corrigeait l'affichage — donc cela se serait résorbé exactement quand personne
 * n'en aurait plus eu besoin.
 *
 * Écrit ici plutôt que dans l'écran d'administration : c'est la table qui sait
 * qu'une page sans route ne s'ordonne pas, et `admin/+page.svelte` est au-dessus du
 * plafond de modularité — le contrôle a refusé qu'il grossisse, et il avait raison.
 */
export function ordonnerPages<T extends { id: string; href: string | null }>(
	pages: T[],
	idsEnregistres: string[],
): T[] {
	const parId = new Map(pages.map((p) => [p.id, p]));
	const ordonnees = idsEnregistres
		.map((id) => parId.get(id))
		.filter((p): p is T => !!p && p.href !== null);
	const placees = new Set(ordonnees);
	return [
		...ordonnees,
		...pages.filter((p) => p.href !== null && !placees.has(p)),
		...pages.filter((p) => p.href === null),
	];
}
