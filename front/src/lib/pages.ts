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
 * tout identifiant ou route de page écrit ailleurs. Une table recopiée finit toujours
 * par diverger de celle qu'elle copie — c'est exactement ce qui s'est produit ici, et
 * c'est déjà arrivé aux périmètres (#316) et aux canaux de notification.
 */

export interface OngletDef {
	id: string;
	label: string;
	descriptif: string;
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
	{ id: 'tableau-de-bord', href: '/tableau-de-bord', nom: 'Tableau de bord',      titre: 'Tableau de bord',           navLabel: 'Accueil',        icone: 'layout-dashboard',    descriptif: "Votre espace numérique de résidence : actualités, demandes, accès et gouvernance de votre copropriété en un seul endroit." },
	{ id: 'residence', href: '/residence',       nom: 'Ma résidence',         titre: 'Ma résidence',              navLabel: 'Résidence',      icone: 'building-2',          descriptif: "Documents et informations de la copropriété." },
	{ id: 'mon-lot', href: '/mon-lot',         nom: 'Mes lots',             titre: 'Mes lots',                  navLabel: 'Mes lots',       icone: 'door-closed',         descriptif: "Informations sur votre bien : situation de vos lots (appartement, cave & parkings) dans la résidence et gestion locative pour les copropriétaires mandataires.",
    onglets: [{ id: 'lots', label: '\u{1F3E0} Mes lots', descriptif: 'Situation de vos lots dans la résidence : appartements, caves et parkings.' }, { id: 'location', label: '\u{1F4CB} Gestion locative', descriptif: 'Suivi de vos baux, locataires et documents de gestion locative.' }] },
	{ id: 'acces-badges', href: '/acces-securite',    nom: 'Accès & badges',       titre: 'Accès & badges',            navLabel: 'Accès & badges', icone: 'key-round',           descriptif: "Gestion de vos télécommandes parkings & Vigiks." },
	{ id: 'annuaire', href: '/annuaire',        nom: 'Annuaire',             titre: 'Annuaire',                  navLabel: 'Annuaire',       icone: 'users',               descriptif: "Coordonnées des membres du Conseil Syndical et du Syndic. En cas d'urgence, contactez le syndic directement par téléphone. Sinon, faites une demande depuis la plateforme." },
	{ id: 'prestataires', href: '/prestataires',    nom: 'Prestataires',         titre: 'Prestataires',              navLabel: 'Prestataires',   icone: 'hard-hat',            descriptif: "Intervenants de la résidence et leurs contrats de maintenance (avec synthèse IA du contrat) et documents contractuels.",
    onglets: [{ id: 'prestataires', label: '\u{1F527} Prestataires', descriptif: 'Intervenants et contrats d\'entretien de la résidence.' }, { id: 'consommations', label: '\u{1F4A7} Consommations', descriptif: 'Suivi des relevés de compteurs et abonnements de la résidence.' }, { id: 'devis', label: '\u{1F4CB} Prestations', descriptif: 'Demandes de devis, prestations ponctuelles et suivi des interventions.' }] },
	{ id: 'calendrier', href: '/calendrier',      nom: 'Calendrier',           titre: 'Calendrier',                navLabel: 'Calendrier',     icone: 'calendar-days',       descriptif: "Agenda des événements et interventions de la résidence.",
    onglets: [{ id: 'liste', label: '\u{1F4CB} Liste', descriptif: 'Vue chronologique des événements à venir.' }, { id: 'kanban', label: '\u{1F5C3}️ Kanban', descriptif: 'Organisation visuelle des événements par statut.' }, { id: 'archives', label: '\u{1F4C1} Archives', descriptif: 'Événements passés classés par année.' }] },
	{ id: 'actualites', href: '/actualites',      nom: 'Actualités',           titre: 'Actualités',                navLabel: 'Actualités',     icone: 'newspaper',           descriptif: "Publications officielles du conseil syndical : informations importantes, travaux et actualités de la résidence." },
	{ id: 'mes-demandes', href: '/tickets',    nom: 'Tickets',              titre: 'Mes Tickets',               navLabel: 'Tickets',        icone: 'message-square-text', descriptif: "Signalez un problème, une nuisance ou posez une question au conseil syndical. Suivez l'avancement de vos tickets." },
	{ id: 'communaute', href: '/sondages',      nom: 'Communauté',           titre: 'Communauté',                navLabel: 'Communauté',     icone: 'users-round',         descriptif: "Sondages et boîte à idées pour contribuer à la vie de la résidence.",
    onglets: [{ id: 'sondages', label: '\u{1F4CA} Sondages', descriptif: 'Participez aux votes et consultations de la copropriété.' }, { id: 'idees', label: '\u{1F4A1} Boîte à idées', descriptif: 'Proposez et soutenez des idées pour améliorer la vie en résidence.' }] },
	{ id: 'faq', href: '/faq',             nom: 'FAQ',                  titre: 'FAQ',                       navLabel: 'FAQ',            icone: 'help-circle',         descriptif: "Réponses aux questions fréquentes sur la vie en résidence, les services et la réglementation de la copropriété." },
	{ id: 'espace-cs', href: '/espace-cs',       nom: 'Espace CS',            titre: 'Espace Conseil Syndical (CS)', navLabel: 'Espace CS',      icone: 'shield-half',         descriptif: "Tableau de bord des membres du Conseil Syndical (CS) : suivi des comptes, tickets résidence, reporting, relance syndic et demandes d'accès — réservé au Conseil Syndical.",
    onglets: [{ id: 'validations', label: '✅ Comptes & accès', descriptif: 'Comptes en attente, demandes d\'accès et validations à traiter.' }, { id: 'tickets', label: '\u{1F3AB} Tickets résidence', descriptif: 'Tous les tickets de la résidence, avec le demandeur, son bâtiment et le suivi de traitement.' }, { id: 'reporting', label: '\u{1F4CA} Reporting', descriptif: 'Synthèses et indicateurs : kanban, tableau des tickets, devis, prestataires, renouvellements de contrats et relance syndic.' }, { id: 'annuaire', label: '\u{1F4D2} Annuaire CS & Syndic', descriptif: 'Coordonnées des membres du CS et du syndic.' }] },
	{ id: 'delegations', href: '/delegations', nom: 'Délégations', titre: 'Délégations aidant', navLabel: 'Délégations', icone: 'heart-handshake', descriptif: "Gestion des accès délégués pour les proches aidants : un proche peut consulter et agir à votre place, sans que cela constitue une procuration d'assemblée générale." },
	{ id: 'admin', href: '/admin',           nom: 'Paramétrage',          titre: 'Paramétrage',               navLabel: 'Admin',          icone: 'sliders-horizontal',  descriptif: "Administration de la plateforme : comptes, utilisateurs, rôles, modèles e-mail, paramétrage et référentiels — réservés aux admins." },
	{ id: 'profil', href: null,          nom: 'Mon profil',           titre: 'Mon profil',                navLabel: 'Profil',         icone: 'user',                descriptif: "Vos informations personnelles (mot de passe, lots...), sécurité du compte et préférences de notifications." },
	{ id: 'notifications', href: null,   nom: 'Notifications',        titre: 'Notifications',             navLabel: 'Notifications',  icone: 'bell',                descriptif: "Vos alertes et messages." },];

/** Les pages qui ont une entrée de menu — les seules qui s'ordonnent. */
export const PAGES_MENU: PageDef[] = PAGES.filter((p): p is PageDef & { href: string } => p.href !== null);

/** Ordre de navigation par défaut, quand aucun ordre n'a été enregistré. */
export const HREFS_DEFAUT: string[] = PAGES_MENU.map((p) => p.href as string);

/** Identifiant de configuration → route. Sert à relire `pages_order`. */
export const ID_VERS_HREF: Record<string, string> = Object.fromEntries(
	PAGES_MENU.map((p) => [p.id, p.href as string])
);

/** Route → page. */
export const HREF_VERS_PAGE: Record<string, PageDef> = Object.fromEntries(
	PAGES_MENU.map((p) => [p.href as string, p])
);
