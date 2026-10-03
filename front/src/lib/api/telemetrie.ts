//  Les réponses du tableau de bord de télémétrie (#1631, #1628, #1632) — le
//  client qui les rend est `admin.telemetryDashboard` (`administration.ts`).
//  Rangées ici le 03/10/2026 : `administration.ts` passait au-dessus du plafond
//  de modularité, et ces types ne servent qu'à l'onglet Télémétrie.

/** Une erreur vue par les résidents (#1631) — `utils/erreurs_navigateur.synthese_erreurs`. */
export interface ErreurNavigateur {
	page: string;
	code: string;
	total: number;
	premiere_le: string;
	derniere_le: string;
}

/** Médiane et 75ᵉ centile d'un ensemble de durées, en millisecondes (#1632). */
export interface ResumeDurees {
	mesures: number;
	mediane: number;
	p75: number;
}

/** Les durées d'affichage (#1632) — `utils/mesures_affichage.synthese_mesures`. */
export interface SyntheseDurees {
	indicateurs: (ResumeDurees & { indicateur: 'chargement' | 'navigation' })[];
	pages: (ResumeDurees & { page: string; indicateur: 'chargement' | 'navigation' })[];
}

/** Une ligne de « Qui vient » : comptes venus sur comptes mesurés (#1628). */
export interface LigneAdoption {
	libelle: string;
	actifs: number;
	comptes: number;
	/** `null` quand la ligne n'a aucun compte. */
	taux: number | null;
}

/** Le taux d'adoption (#1628) — `utils/adoption.adoption`, sur la fenêtre de la vue. */
export interface Adoption {
	/** Ce que couvre la fenêtre : « aujourd’hui », « 30 derniers jours », « 12 derniers mois ». */
	periode: string;
	global: LigneAdoption;
	/** Comptes qui ont refusé la mesure d'audience, exclus du calcul. */
	refus: number;
	par_profil: LigneAdoption[];
	par_type: LigneAdoption[];
	par_batiment: LigneAdoption[];
}

/** Les quatre vues de l'onglet (03/10/2026) : le jour, 30 jours, 12 mois, 10 ans par année. */
export type PorteeTelemetrie = 'jour' | 'mois' | 'annee' | 'total';
/** Le filtre « avec / sans gestionnaire du site » (03/10/2026). */
export type FiltreGestionnaire = 'avec' | 'sans';

/** Ce que le serveur dit du filtre — `utils/telemetrie_tableau`. */
export interface EtatFiltreGestionnaire {
	/** Proposé seulement s'il changerait quelque chose : un gestionnaire qui a des vues, et d'autres aussi. */
	propose: boolean;
	/** Ce qui a été appliqué — « avec » quoi qu'on demande si le filtre n'est pas proposé. */
	applique: FiltreGestionnaire;
	/** Dernier jour dont l'agrégat ne sépare pas le gestionnaire (compté dans les deux lectures). */
	non_distingue_jusqu_au: string | null;
}

/** Un bâton du graphe : une heure, un jour, un mois ou une année selon la vue. */
export interface BatonTelemetrie {
	label: string;
	total: number;
	uniques: number | null;
}

/** Une page du palmarès. */
export interface PageTelemetrie {
	page: string;
	total: number;
	uniques: number;
}

/** Un utilisateur du palmarès (`telemetrie_calculs._palmares`). */
export interface UtilisateurActif {
	nom: string;
	statut: string | null;
	batiment_id: number | null;
	total: number;
	pages: number;
	derniere_connexion: string | null;
}

/**
 * Le tableau de bord de télémétrie. `kpi` reste libre : ses clés changent avec
 * la vue, et l'écran les lit une à une.
 */
export interface TableauTelemetrie {
	scope: PorteeTelemetrie;
	kpi: Record<string, any>;
	chart: BatonTelemetrie[];
	chart_label: string;
	top_pages: PageTelemetrie[];
	top_users: UtilisateurActif[];
	erreurs: ErreurNavigateur[];
	performance: SyntheseDurees;
	/** `null` : la vue ne sait pas qui est venu (Total). */
	adoption: Adoption | null;
	filtre_gestionnaire: EtatFiltreGestionnaire;
}
