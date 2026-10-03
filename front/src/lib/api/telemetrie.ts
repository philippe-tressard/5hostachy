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

/** Le taux d'adoption (#1628) — `utils/adoption.adoption`. */
export interface Adoption {
	jours: number;
	global: LigneAdoption;
	/** Comptes qui ont refusé la mesure d'audience, exclus du calcul. */
	refus: number;
	par_profil: LigneAdoption[];
	par_type: LigneAdoption[];
	par_batiment: LigneAdoption[];
}

/**
 * Le tableau de bord de télémétrie. Seuls les panneaux ajoutés depuis #1631 sont
 * typés ; le reste (`kpi`, `chart`, `top_pages`, `top_users`) l'est par l'écran
 * qui les lit, en attendant qu'un lot qui y touche le déclare ici.
 */
export interface TableauTelemetrie {
	erreurs: ErreurNavigateur[];
	performance: SyntheseDurees;
	adoption: Adoption;
	[cle: string]: any;
}
