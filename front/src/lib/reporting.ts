//  Le vocabulaire du **reporting CS** — écrit une fois pour les six vues qui le
//  partagent (`$lib/components/reporting/`).
//
//  Il vivait dans `espace-cs/+page.svelte`, mêlé à l'état de quatre autres
//  onglets. En sortant la rubrique de la page (#453), ces types et ces calculs
//  ont dû se poser quelque part : les recopier dans chaque vue aurait ouvert
//  exactement la divergence que #415 et #413 ont fermée ailleurs.
//
//  ⚠️ Aucune fonction d'ici ne touche au réseau ni au DOM. Les chargements
//  vivent dans `OngletReporting.svelte`, la mise en forme dans les vues.

export interface ReportEvenement {
	id: number;
	titre: string;
	description?: string | null;
	type: string;
	debut: string;
	fin?: string | null;
	perimetre: string;
	batiment_id?: number | null;
	auteur_nom?: string | null;
	cree_le: string;
	mis_a_jour_le?: string | null;
	statut_kanban?: string | null;
	prestataire_nom?: string | null;
}
export interface ReportPrestataire {
	id: number;
	nom: string;
	specialite?: string | null;
	type_prestataire?: string | null;
}
export interface ReportDevis {
	id: number;
	prestataire_id: number;
	batiment_id?: number | null;
	perimetre: string;
	titre: string;
	date_prestation?: string | null;
	montant_estime?: number | null;
	statut: string;
	frequence_type?: string | null;
	frequence_valeur?: number | null;
	notes?: string | null;
	actif: boolean;
	affichable: boolean;
}
export interface ReportContrat {
	id: number;
	prestataire_id: number;
	type_equipement: string;
	libelle: string;
	numero_contrat?: string | null;
	date_debut: string;
	duree_initiale_valeur?: number | null;
	duree_initiale_unite?: string | null;
	frequence_type?: string | null;
	frequence_valeur?: number | null;
	prochaine_visite?: string | null;
	actif: boolean;
}
export interface DiagRapport {
	id: number;
	titre: string;
	date_rapport?: string | null;
}
export interface DiagType {
	id: number;
	code: string;
	nom: string;
	texte_legislatif: string;
	frequence?: string | null;
	non_applicable: boolean;
	rapports: DiagRapport[];
}

/**  Les cinq vues du reporting — la liste sert aussi à valider un `?vue=` d'URL,
 *   et c'est ce qui fait retomber sans bruit un lien `?vue=devis` d'avant le
 *   28/08/2026 : « Devis & interventions » a été retirée, redondante avec
 *   l'onglet « Prestations » de la page Prestataires. */
export const REPORT_VUES = ['kanban', 'tickets', 'prestataires', 'renouvellements', 'relance'] as const;
export type ReportVue = (typeof REPORT_VUES)[number];

export const KANBAN_LABELS: Record<string, string> = { ag: 'AG', cs: 'CS (en cours)', syndic: 'Syndic (en cours)', annule: 'Annulé' };
export const KANBAN_COLORS: Record<string, string> = { ag: 'badge-purple', cs: 'badge-blue', syndic: 'badge-orange', annule: 'badge-gray' };
export const TYPE_LABELS: Record<string, string> = { travaux: 'Travaux', coupure: 'Coupure', ag: 'AG', maintenance: 'Maintenance', maintenance_recurrente: 'Maintenance récurrente', autre: 'Autre' };
export const REPORT_DEVIS_LABELS: Record<string, string> = { en_attente: 'En attente', accepte: 'Accepté', realise: 'Réalisé', refuse: 'Refusé' };
export const REPORT_DEVIS_BADGES: Record<string, string> = { en_attente: 'badge-blue', accepte: 'badge-orange', realise: 'badge-green', refuse: 'badge-gray' };

/* ── Renouvellements : calculs ────────────────────────────────────────────
   L'année de référence est une FONCTION, pas une constante. Elle était figée au
   chargement de la page, qui ne vivait que le temps d'un onglet ; ce module-ci
   est chargé une fois pour toute la session — un onglet laissé ouvert la nuit du
   réveillon aurait continué d'annoncer les échéances de l'année passée. */
export const PREAVIS_MOIS = 3;
export function anneeCourante(): number {
	return new Date().getFullYear();
}
export const MOIS_LABELS = ['Janv.', 'Fév.', 'Mars', 'Avr.', 'Mai', 'Juin', 'Juil.', 'Août', 'Sept.', 'Oct.', 'Nov.', 'Déc.'];

export function contratDateFin(c: ReportContrat): { date: Date; reconduit: boolean } | null {
	if (!c.date_debut) return null;
	const d = new Date(c.date_debut);
	if (c.duree_initiale_valeur && c.duree_initiale_unite) {
		if (c.duree_initiale_unite === 'ans') d.setFullYear(d.getFullYear() + c.duree_initiale_valeur);
		else if (c.duree_initiale_unite === 'mois') d.setMonth(d.getMonth() + c.duree_initiale_valeur);
	} else {
		// Durée inconnue → reconduction annuelle par défaut
		d.setFullYear(d.getFullYear() + 1);
	}
	const now = new Date();
	let reconduit = false;
	while (d <= now) { d.setFullYear(d.getFullYear() + 1); reconduit = true; }
	return { date: d, reconduit };
}

export function contratDatePreavis(dateFin: Date): Date {
	const d = new Date(dateFin);
	d.setMonth(d.getMonth() - PREAVIS_MOIS);
	return d;
}

export function contratUrgence(dateFin: Date): 'preavis' | 'annee' | 'futur' {
	const now = new Date();
	const preavis = contratDatePreavis(dateFin);
	if (preavis <= now) return 'preavis';
	if (dateFin.getFullYear() === anneeCourante()) return 'annee';
	// Préavis dans l'année courante même si fin l'année suivante
	if (preavis.getFullYear() === anneeCourante()) return 'annee';
	return 'futur';
}

export function diagNextDate(dt: DiagType): Date | null {
	if (!dt.frequence || dt.non_applicable) return null;
	const match = dt.frequence.match(/(\d+)/);
	if (!match) return null;
	const freqAns = parseInt(match[1]);
	const lastRapport = dt.rapports.find(r => r.date_rapport);
	if (!lastRapport || !lastRapport.date_rapport) return null;
	const d = new Date(lastRapport.date_rapport);
	d.setFullYear(d.getFullYear() + freqAns);
	return d;
}

export function diagUrgence(nextDate: Date): 'depasse' | 'annee' | 'futur' {
	const now = new Date();
	if (nextDate <= now) return 'depasse';
	if (nextDate.getFullYear() === anneeCourante()) return 'annee';
	return 'futur';
}


// ── Dérivations partagées (#453, 27/08/2026) ─────────────────────────────────
//
// Ces deux fonctions vivaient en `$:` dans `VueRenouvellements.svelte`. Le
// découpage de ce fichier en trois — les compteurs, la frise, les audits — les
// aurait fait recopier DEUX fois : le parent en a besoin pour ses compteurs,
// chaque enfant pour son tableau.
//
// ⚠️ Un découpage qui duplique n'est pas un découpage. Elles montent donc ici,
// avec le reste des calculs purs : lisibles et testables sans écran, comme le
// dit l'en-tête de ce module.

/** Un contrat enrichi de son échéance, de son préavis et de sa note. */
export interface ContratAvecEcheance extends ReportContrat {
	dateFin: Date | null;
	datePreavis: Date | null;
	urgence: 'preavis' | 'annee' | 'futur' | 'inconnu';
	reconduit: boolean;
	prestataireNom: string;
	noteMoy: number | null;
	nbNotations: number;
}

/**
 * Les contrats, enrichis et TRIÉS — la pire note d'abord, puis par date de fin.
 *
 * Le tri par note est délibéré et vient avant la date : un contrat mal noté qui
 * arrive à échéance est la décision la plus urgente à prendre, pas la plus
 * proche. Une note absente vaut 6, donc passe en dernier — jamais devant un
 * prestataire réellement mal noté.
 */
export function contratsAvecEcheance(
	contrats: ReportContrat[],
	prestataires: ReportPrestataire[],
	notes: Map<number, { moy: number; nb: number }>,
): ContratAvecEcheance[] {
	return contrats
		.map((c) => {
			const result = contratDateFin(c);
			const fin = result?.date ?? null;
			const reconduit = result?.reconduit ?? false;
			const preavis = fin ? contratDatePreavis(fin) : null;
			const urgence: 'preavis' | 'annee' | 'futur' | 'inconnu' = fin
				? contratUrgence(fin)
				: 'inconnu';
			const prest = prestataires.find((p) => p.id === c.prestataire_id);
			const noteInfo = notes.get(c.prestataire_id) ?? null;
			return {
				...c,
				dateFin: fin as Date | null,
				datePreavis: preavis,
				urgence,
				reconduit,
				prestataireNom: prest?.nom ?? `#${c.prestataire_id}`,
				noteMoy: noteInfo?.moy ?? (null as number | null),
				nbNotations: noteInfo?.nb ?? 0,
			};
		})
		.sort((a, b) => {
			//  Pire note en premier ; `null` = pas de note = en dernier.
			const noteA = a.noteMoy ?? 6;
			const noteB = b.noteMoy ?? 6;
			if (noteA !== noteB) return noteA - noteB;
			if (!a.dateFin && !b.dateFin) return 0;
			if (!a.dateFin) return 1;
			if (!b.dateFin) return -1;
			return a.dateFin.getTime() - b.dateFin.getTime();
		});
}

/** Un diagnostic enrichi de sa prochaine échéance. */
export interface DiagAvecEcheance extends DiagType {
	nextDate: Date | null;
	urgence: 'depasse' | 'annee' | 'futur' | 'inconnu';
	lastRapportDate: string | null;
	isPermanent: boolean;
}

/**
 * Les diagnostics APPLICABLES, enrichis et triés par prochaine échéance.
 *
 * ⚠️ Un diagnostic « permanent » n'a pas d'échéance : il est marqué comme tel
 * plutôt qu'écarté, sinon il disparaîtrait de l'écran sans que rien ne dise
 * pourquoi. Les non applicables, eux, sont bien exclus — c'est une décision de
 * la copropriété, pas une absence de donnée.
 */
export function diagnosticsAvecEcheance(types: DiagType[]): DiagAvecEcheance[] {
	return types
		.filter((dt) => !dt.non_applicable)
		.map((dt) => {
			const isPermanent = dt.frequence
				? dt.frequence.toLowerCase().includes('permanent')
				: false;
			const next = isPermanent ? null : diagNextDate(dt);
			const urgence: 'depasse' | 'annee' | 'futur' | 'inconnu' = next
				? diagUrgence(next)
				: 'inconnu';
			const lastRapport = dt.rapports.find((r) => r.date_rapport);
			return {
				...dt,
				nextDate: next as Date | null,
				urgence,
				lastRapportDate: lastRapport?.date_rapport ?? null,
				isPermanent,
			};
		})
		.sort((a, b) => {
			if (!a.nextDate && !b.nextDate) return 0;
			if (!a.nextDate) return 1;
			if (!b.nextDate) return -1;
			return a.nextDate.getTime() - b.nextDate.getTime();
		});
}

