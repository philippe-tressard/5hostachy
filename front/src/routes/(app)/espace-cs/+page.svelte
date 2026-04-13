<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import { onMount, tick } from 'svelte';
	import { isCS } from '$lib/stores/auth';
	import { goto } from '$app/navigation';
	import { admin as adminApi, annuaireAdmin, lots as lotsApi, api, tickets as ticketsApi, prestataires as prestApi, calendrier as calApi, diagnostics as diagnosticsApi, ApiError, type Ticket, type TicketEvolution } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { getPageConfig, configStore, siteNomStore } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';
	import { fmtDate, fmtDatetime, fmtDateShort } from '$lib/date';
	import { trackTabView } from '$lib/telemetry';

	$: _pc = getPageConfig($configStore, 'espace-cs', { titre: 'Espace Conseil Syndical (CS)', navLabel: 'Espace CS', icone: 'shield-half', descriptif: "Tableau de bord des membres du Conseil Syndical (CS) : suivi des comptes, tickets résidence, reporting et demandes d'accès — réservé au Conseil Syndical.", onglets: { validations: { label: '✅ Comptes & accès', descriptif: 'Comptes en attente, demandes d\'accès et validations à traiter.' }, tickets: { label: '\u{1F3AB} Tickets résidence', descriptif: 'Tous les tickets de la résidence, avec le demandeur, son bâtiment et le suivi de traitement.' }, reporting: { label: '\u{1F4CA} Reporting', descriptif: 'Reportings prêts pour l’AG, les réunions CS et les échanges avec le syndic : dossiers en cours, analyse tickets, devis & interventions.' }, annuaire: { label: '\u{1F4D2} Annuaire CS & Syndic', descriptif: 'Coordonnées des membres du CS et du syndic.' } } });
	$: _siteNom = $siteNomStore;

	interface PendingUser {
		id: number; prenom: string; nom: string;
		statut: string; batiment_id: number | null; cree_le: string;
		nom_aide?: string | null; prenom_aide?: string | null;
	}
	interface PendingAcces {
		id: number;
		lot: { reference: string; batiment: { nom: string } };
		proprietaire: { prenom: string; nom: string };
		type_acces: string; quantite: number; cree_le: string;
	}
	interface MembreCSForm {
		genre: string; prenom: string; nom: string;
		batiment_id: number | null; batiment_nom: string | null;
		etage: number | null; user_id: number | null;
		est_gestionnaire_site: boolean;
		est_president: boolean;
	}
	interface MembreSyndicForm {
		genre: string; prenom: string; nom: string;
		fonction: string; email: string; telephones: string[];
		est_principal: boolean; user_id: number | null;
	}
	interface SimpleUser {
		id: number; prenom: string; nom: string;
		email: string; telephone: string | null; batiment_id: number | null;
	}
	interface LotRow {
		id: number; numero: string; type: string;
		etage: number | null; batiment_id: number | null; batiment_nom: string | null;
	}
	interface ReportEvenement {
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
	interface ReportPrestataire {
		id: number;
		nom: string;
		specialite?: string | null;
		type_prestataire?: string | null;
	}
	interface ReportDevis {
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
	interface ReportContrat {
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
	interface DiagRapport {
		id: number;
		titre: string;
		date_rapport?: string | null;
	}
	interface DiagType {
		id: number;
		code: string;
		nom: string;
		texte_legislatif: string;
		frequence?: string | null;
		non_applicable: boolean;
		rapports: DiagRapport[];
	}

	// -- Onglet -------------------------------------------------------------
	let onglet: 'validations' | 'tickets' | 'reporting' | 'annuaire' = 'validations';
	$: trackTabView(onglet);

	// -- Tickets ------------------------------------------------------------
	let tkList: Ticket[] = [];
	let tkLoading = false;
	let tkLoaded = false;
	let tkFilter: '' | 'ouvert' | 'en_cours' | 'résolu' | 'annulé' = '';
	let tkExpandedId: number | null = null;
	let tkEvolsMap: Record<number, TicketEvolution[]> = {};
	let tkEvolsLoaded = new Set<number>();
	let tkShowForm: number | null = null;
	let tkEvolType: 'commentaire' | 'etat' = 'commentaire';
	let tkEvolContenu = '';
	let tkEvolStatut = '';
	let tkEvolSaving = false;
	let reportView: 'kanban' | 'tickets' | 'devis' | 'prestataires' | 'renouvellements' = 'kanban';
	let reportPeriodDays: 30 | 90 | 365 = 90;
	let reportingLoading = false;
	let reportingLoaded = false;
	let reportDevisList: ReportDevis[] = [];
	let reportPrestataires: ReportPrestataire[] = [];
	let reportEvenements: ReportEvenement[] = [];
	let reportPrintTitle = '';
	let reportPrestSynth: any = null;
	let reportPrestSynthLoading = false;
	let reportPrestSynthId: number | null = null;
	let reportContrats: ReportContrat[] = [];
	let reportDiagTypes: DiagType[] = [];
	let reportNoteMoyParPrest: Map<number, { moy: number; nb: number }> = new Map();

	const KANBAN_LABELS: Record<string, string> = { ag: 'AG', cs: 'CS (en cours)', syndic: 'Syndic (en cours)' };
	const KANBAN_COLORS: Record<string, string> = { ag: 'badge-purple', cs: 'badge-blue', syndic: 'badge-orange' };
	const TYPE_LABELS: Record<string, string> = { travaux: 'Travaux', coupure: 'Coupure', ag: 'AG', maintenance: 'Maintenance', maintenance_recurrente: 'Maintenance récurrente', autre: 'Autre' };

	const TK_STATUT_BADGE: Record<string, string> = { ouvert: 'badge-blue', en_cours: 'badge-orange', résolu: 'badge-green', annulé: 'badge-gray', fermé: 'badge-gray' };
	const TK_STATUT_LABELS: Record<string, string> = { ouvert: 'Ouvert', en_cours: 'En cours', résolu: 'Résolu', annulé: 'Annulé', fermé: 'Fermé' };
	const TK_CAT_ICON: Record<string, string> = { panne: '\u{1F6E0}️', nuisance: '\u{1F4E2}', question: '❓', urgence: '\u{1F6A8}', bug: '\u{1F41B}' };
	const REPORT_DEVIS_LABELS: Record<string, string> = { en_attente: 'En attente', accepte: 'Accepté', realise: 'Réalisé', refuse: 'Refusé' };
	const REPORT_DEVIS_BADGES: Record<string, string> = { en_attente: 'badge-blue', accepte: 'badge-orange', realise: 'badge-green', refuse: 'badge-gray' };

	$: tkFiltered = tkList.filter(t => !tkFilter || t.statut === tkFilter);
	$: tkPendingCount = tkList.filter(t => t.statut === 'ouvert').length;

	function renderDesc(c: string) { const t = c.trimStart(); return safeHtml(t.startsWith('<') ? c : `<p>${c.replace(/\n/g, '<br>')}</p>`); }
	function apiMessage(e: unknown, fallback = 'Erreur') {
		if (e && typeof e === 'object' && 'message' in e) return String((e as { message?: unknown }).message ?? fallback);
		return fallback;
	}
	function fmtMoney(v: number | null | undefined) {
		if (v == null) return '—';
		return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(v);
	}
	function daysSince(d: string | null | undefined) {
		if (!d) return 0;
		const ts = new Date(d).getTime();
		if (Number.isNaN(ts)) return 0;
		return Math.max(0, Math.floor((Date.now() - ts) / 86400000));
	}
	function ticketScope(t: Ticket) {
		return t.auteur_batiment_nom ?? (t.batiment_id ? `Bât. ${t.batiment_id}` : 'Résidence');
	}
	function reportPrestataireName(prestataireId: number) {
		return reportPrestataires.find((p) => p.id === prestataireId)?.nom ?? `Prestataire #${prestataireId}`;
	}

	async function printReporting(title: string) {
		if (typeof window === 'undefined' || typeof document === 'undefined') return;
		reportPrintTitle = title;
		document.body.classList.add('print-reporting');
		const prevTitle = document.title;
		const dateStr = new Date().toISOString().slice(0, 10);
		const slug = title.replace(/^Reporting CS — /, '').replace(/[^\w\dÀ-ÿ]+/g, '-').replace(/-+$/, '');
		document.title = `CS-${slug}-${dateStr}`;
		await tick();
		window.print();
		setTimeout(() => { document.body.classList.remove('print-reporting'); document.title = prevTitle; }, 250);
	}

	async function loadPrestSynthese(prestId: number) {
		reportPrestSynthId = prestId;
		reportPrestSynthLoading = true;
		try {
			reportPrestSynth = await prestApi.synthese(prestId);
		} catch { toast('error', 'Erreur chargement synthèse'); reportPrestSynth = null; }
		finally { reportPrestSynthLoading = false; }
	}
	function starsDisplay(note: number): string {
		const full = Math.round(note);
		return '★'.repeat(full) + '☆'.repeat(5 - full);
	}
	function printCurrentReporting() {
		const titles: Record<typeof reportView, string> = {
			kanban: 'Reporting CS — Dossiers AG / CS / Syndic',
			tickets: 'Reporting CS — Analyse tickets',
			devis: 'Reporting CS — Devis & interventions',
			prestataires: 'Reporting CS — Synthèse prestataires',
			renouvellements: 'Reporting CS — Renouvellement contrats & audits',
		};
		void printReporting(titles[reportView]);
	}

	/* ── Renouvellements : calculs ──────────────────────────────────────── */
	const PREAVIS_MOIS = 3;
	const ANNEE_COURANTE = new Date().getFullYear();
	const MOIS_LABELS = ['Janv.', 'Fév.', 'Mars', 'Avr.', 'Mai', 'Juin', 'Juil.', 'Août', 'Sept.', 'Oct.', 'Nov.', 'Déc.'];

	function contratDateFin(c: ReportContrat): { date: Date; reconduit: boolean } | null {
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

	function contratDatePreavis(dateFin: Date): Date {
		const d = new Date(dateFin);
		d.setMonth(d.getMonth() - PREAVIS_MOIS);
		return d;
	}

	function contratUrgence(dateFin: Date): 'preavis' | 'annee' | 'futur' {
		const now = new Date();
		const preavis = contratDatePreavis(dateFin);
		if (preavis <= now) return 'preavis';
		if (dateFin.getFullYear() === ANNEE_COURANTE) return 'annee';
		// Préavis dans l'année courante même si fin l'année suivante
		if (preavis.getFullYear() === ANNEE_COURANTE) return 'annee';
		return 'futur';
	}

	function diagNextDate(dt: DiagType): Date | null {
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

	function diagUrgence(nextDate: Date): 'depasse' | 'annee' | 'futur' {
		const now = new Date();
		if (nextDate <= now) return 'depasse';
		if (nextDate.getFullYear() === ANNEE_COURANTE) return 'annee';
		return 'futur';
	}

	$: reportKanbanEvents = reportEvenements
		.filter((ev) => ev.statut_kanban === 'ag' || ev.statut_kanban === 'cs' || ev.statut_kanban === 'syndic')
		.sort((a, b) => daysSince(b.cree_le) - daysSince(a.cree_le));
	$: reportKanbanByCol = (['ag', 'cs', 'syndic'] as const).map((col) => ({
		col,
		label: KANBAN_LABELS[col],
		badge: KANBAN_COLORS[col],
		items: reportKanbanEvents.filter((ev) => ev.statut_kanban === col),
	}));
	$: reportTicketSource = tkList.filter((t) => daysSince(t.cree_le) <= reportPeriodDays);
	$: reportTicketCategories = Object.entries(reportTicketSource.reduce((acc: Record<string, { total: number; ouverts: number }>, t) => {
		const key = t.categorie || 'autre';
		if (!acc[key]) acc[key] = { total: 0, ouverts: 0 };
		acc[key].total += 1;
		if (t.statut === 'ouvert' || t.statut === 'en_cours') acc[key].ouverts += 1;
		return acc;
	}, {})).map(([categorie, data]) => ({ categorie, ...data })).sort((a, b) => b.total - a.total);
	$: reportTicketBuildings = Object.entries(reportTicketSource.reduce((acc: Record<string, { total: number; ouverts: number }>, t) => {
		const key = ticketScope(t);
		if (!acc[key]) acc[key] = { total: 0, ouverts: 0 };
		acc[key].total += 1;
		if (t.statut === 'ouvert' || t.statut === 'en_cours') acc[key].ouverts += 1;
		return acc;
	}, {})).map(([batiment, data]) => ({ batiment, ...data })).sort((a, b) => b.total - a.total);
	$: reportDevisActifs = reportDevisList.filter((d) => d.statut === 'en_attente' || d.statut === 'accepte');
	$: reportDevisSummary = Object.entries(reportDevisList.reduce((acc: Record<string, number>, d) => {
		acc[d.statut] = (acc[d.statut] ?? 0) + 1;
		return acc;
	}, {})).map(([statut, total]) => ({ statut, total })).sort((a, b) => b.total - a.total);

	/* ── Reactives renouvellements ───────────────────────────────────── */
	$: contratsAvecFin = reportContrats
		.map(c => {
			const result = contratDateFin(c);
			const fin = result?.date ?? null;
			const reconduit = result?.reconduit ?? false;
			const preavis = fin ? contratDatePreavis(fin) : null;
			const urgence: 'preavis' | 'annee' | 'futur' | 'inconnu' = fin ? contratUrgence(fin) : 'inconnu';
			const prest = reportPrestataires.find(p => p.id === c.prestataire_id);
			const noteInfo = reportNoteMoyParPrest.get(c.prestataire_id) ?? null;
			return { ...c, dateFin: fin as Date | null, datePreavis: preavis, urgence, reconduit, prestataireNom: prest?.nom ?? `#${c.prestataire_id}`, noteMoy: noteInfo?.moy ?? null as number | null, nbNotations: noteInfo?.nb ?? 0 };
		})
		.sort((a, b) => {
			// Tri prioritaire : pire note en premier (null = pas de note = en dernier)
			const noteA = a.noteMoy ?? 6;
			const noteB = b.noteMoy ?? 6;
			if (noteA !== noteB) return noteA - noteB;
			// Puis par date de fin
			if (!a.dateFin && !b.dateFin) return 0;
			if (!a.dateFin) return 1;
			if (!b.dateFin) return -1;
			return a.dateFin.getTime() - b.dateFin.getTime();
		});

	$: contratsAnneeCourante = contratsAvecFin.filter(c => {
		if (!c.dateFin) return false;
		// Inclure si la fin OU le préavis tombe dans l'année courante
		if (c.dateFin.getFullYear() === ANNEE_COURANTE) return true;
		if (c.datePreavis && c.datePreavis.getFullYear() === ANNEE_COURANTE) return true;
		return false;
	});

	$: contratsFuturs = contratsAvecFin.filter(c => c.dateFin && c.urgence === 'futur' && !contratsAnneeCourante.includes(c));
	$: contratsInconnus = contratsAvecFin.filter(c => c.urgence === 'inconnu');

	$: diagsAvecNext = reportDiagTypes
		.filter(dt => !dt.non_applicable)
		.map(dt => {
			const isPermanent = dt.frequence ? dt.frequence.toLowerCase().includes('permanent') : false;
			const next = isPermanent ? null : diagNextDate(dt);
			const urgence: 'depasse' | 'annee' | 'futur' | 'inconnu' = next ? diagUrgence(next) : 'inconnu';
			const lastRapport = dt.rapports.find(r => r.date_rapport);
			return { ...dt, nextDate: next as Date | null, urgence, lastRapportDate: lastRapport?.date_rapport ?? null, isPermanent };
		})
		.sort((a, b) => {
			if (!a.nextDate && !b.nextDate) return 0;
			if (!a.nextDate) return 1;
			if (!b.nextDate) return -1;
			return a.nextDate.getTime() - b.nextDate.getTime();
		});

	$: diagsAvecEcheance = diagsAvecNext.filter(d => d.nextDate !== null);
	$: diagsSansEcheance = diagsAvecNext.filter(d => d.nextDate === null && !d.isPermanent);
	$: diagsPermanents = diagsAvecNext.filter(d => d.isPermanent);

	$: diagsParAnnee = (() => {
		const map = new Map<number, typeof diagsAvecEcheance>();
		for (const d of diagsAvecEcheance) {
			const y = d.nextDate!.getFullYear();
			if (y < ANNEE_COURANTE || y > ANNEE_COURANTE + 10) continue;
			if (!map.has(y)) map.set(y, []);
			map.get(y)!.push(d);
		}
		return [...map.entries()].sort((a, b) => a[0] - b[0]);
	})();

	$: renKpiContrats = contratsAnneeCourante.length;
	$: renKpiPreavis = contratsAvecFin.filter(c => c.urgence === 'preavis' || c.urgence === 'inconnu').length;
	$: renKpiDiags = diagsAvecNext.filter(d => d.urgence === 'depasse' || d.urgence === 'annee' || d.urgence === 'inconnu').length;

	async function loadTickets() {
		if (tkLoaded) return;
		tkLoading = true;
		try {
			tkList = await ticketsApi.list();
			tkLoaded = true;
		} catch { toast('error', 'Erreur chargement tickets'); }
		finally { tkLoading = false; }
	}

	async function loadReporting(force = false) {
		if (reportingLoaded && !force) return;
		reportingLoading = true;
		try {
			await loadTickets();
			const [devis, prestataires, evenements, contrats, diagTypes, notations] = await Promise.all([
				prestApi.devis(), prestApi.list(), calApi.list(),
				prestApi.contrats(), diagnosticsApi.listTypes(),
				prestApi.notations()
			]);
			reportDevisList = devis as ReportDevis[];
			reportPrestataires = prestataires as ReportPrestataire[];
			reportEvenements = evenements as ReportEvenement[];
			reportContrats = contrats as ReportContrat[];
			reportDiagTypes = diagTypes as DiagType[];
			// Calcul note moyenne par prestataire
			const noteMap = new Map<number, number[]>();
			for (const n of notations as { prestataire_id: number; note: number }[]) {
				if (!noteMap.has(n.prestataire_id)) noteMap.set(n.prestataire_id, []);
				noteMap.get(n.prestataire_id)!.push(n.note);
			}
			reportNoteMoyParPrest = new Map();
			for (const [pid, notes] of noteMap) {
				reportNoteMoyParPrest.set(pid, { moy: Math.round(notes.reduce((a, b) => a + b, 0) / notes.length * 10) / 10, nb: notes.length });
			}
			reportingLoaded = true;
		} catch (e: any) {
			toast('error', apiMessage(e, 'Erreur chargement reporting'));
		} finally {
			reportingLoading = false;
		}
	}
	function refreshReporting() { loadReporting(true); }

	async function tkToggle(id: number) {
		if (tkExpandedId === id) { tkExpandedId = null; return; }
		tkExpandedId = id;
		tkShowForm = null;
		if (!tkEvolsLoaded.has(id)) await tkLoadEvols(id);
	}

	async function tkLoadEvols(id: number) {
		try {
			tkEvolsMap[id] = await ticketsApi.evolutions(id);
			tkEvolsLoaded = new Set([...tkEvolsLoaded, id]);
			tkEvolsMap = { ...tkEvolsMap };
		} catch { /* silencieux */ }
	}

	function tkOpenForm(id: number) {
		tkShowForm = id;
		tkEvolType = 'etat';
		tkEvolContenu = '';
		tkEvolStatut = '';
		tkExpandedId = id;
	}

	async function tkSubmitEvol(t: Ticket) {
		if (tkEvolType === 'etat' && !tkEvolStatut) return;
		if (tkEvolType === 'commentaire' && !tkEvolContenu.trim()) return;
		tkEvolSaving = true;
		try {
			await ticketsApi.addEvolution(t.id, {
				type: tkEvolType,
				contenu: tkEvolContenu.trim() || undefined,
				nouveau_statut: tkEvolType === 'etat' ? tkEvolStatut : undefined,
			});
			if (tkEvolType === 'etat') {
				tkList = tkList.map(x => x.id === t.id ? { ...x, statut: tkEvolStatut } : x);
			}
			await tkLoadEvols(t.id);
			tkShowForm = null;
			tkEvolContenu = '';
			tkEvolStatut = '';
			toast('success', tkEvolType === 'etat' ? 'Statut mis à jour' : 'Commentaire ajouté');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally { tkEvolSaving = false; }
	}

	// -- Validations --------------------------------------------------------
	let batimentsMap: Record<number, string> = {};
	let comptesEnAttente: PendingUser[] = [];
	let commandesEnAttente: PendingAcces[] = [];
	let loading = true;
	$: nbComptes = comptesEnAttente.length;
	$: nbCommandes = commandesEnAttente.length;

	// -- Annuaire -----------------------------------------------------------
	let batimentsList: { id: number; numero: string }[] = [];
	let allUsers: SimpleUser[] = [];
	let allLots: LotRow[] = [];
	let annuaireLoading = false;

	// CS
	let agAnnee: number | null = null;
	let agDate = '';
	let membresCS: MembreCSForm[] = [];
	let savingCS = false;
	let savingCSIdx: number | null = null;
	let csOpenIdx: number | null = null;
	let csEditIdx: number | null = null;

	// Syndic
	let nomSyndic = '';
	let adresseSyndic = '';
	let siteWebSyndic = '';
	let membresSyndic: MembreSyndicForm[] = [];
	let savingSyndic = false;
	let savingSyndicIdx: number | null = null;
	let syndicOpenIdx: number | null = null;
	let syndicEditIdx: number | null = null;

	// WhatsApp
	let whatsappUrl = '';

	// -- Header inline-edit flags -----------------------------------------
	let csHeaderEditing = false;
	let syndicHeaderEditing = false;

	// -- Normalisation : minuscules sans accents (NFD) -----------------------
	function normalizeStr(s: string): string {
		return s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
	}

	// -- Liaison inscrit via NOM ------------------------------------------
	function findUserByNom(nom: string): SimpleUser | null {
		if (!nom || nom.length < 2) return null;
		const q = normalizeStr(nom);
		return allUsers.find(u => normalizeStr(u.nom) === q) ?? null;
	}

	// Cherche dans les LotImport (via lots.listImports) pour trouver bâtiment/étage
	let lotImports: any[] = [];
	// Conversion etage_raw brut → entier (même logique que le backend)
	function etageFromRaw(raw: string | null | undefined): number | null {
		if (raw == null) return null;
		const s = raw.trim().toUpperCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\s+/g, ' ');
		const map: Record<string, number> = {
			'RDC': 0, '0': 0,
			'1ER': 1, '1': 1,
			'2EME': 2, '2': 2,
			'3EME': 3, '3': 3,
			'4EME': 4, '4': 4,
			'5EME': 5, '5': 5,
			'6EME': 6, '6': 6,
			'7EME': 7, '7': 7,
			'1SS': -1, '-1': -1,
			'2SS': -2, '-2': -2,
		};
		return map[s] ?? null;
	}

	function findImportForNom(nom: string): { batiment_id: number | null; batiment_nom: string | null; etage: number | null } | null {
		if (!nom || nom.length < 2) return null;
		const q = normalizeStr(nom);
		// Préférer le lot de type appartement pour la localisation (pas le parking ni la cave)
		const hits = lotImports.filter(imp =>
			imp.nom_coproprietaire && normalizeStr(imp.nom_coproprietaire).includes(q)
		);
		if (!hits.length) return null;
		// Exclure CA (cave) et PS (parking) via type_raw — fiable même si lot_id non résolu
		const hitsAppt = hits.filter(imp => {
			const raw = (imp.type_raw ?? '').toUpperCase().trim();
			if (raw.startsWith('CA') || raw.startsWith('PS')) return false;
			if (imp.lot_id) {
				const lot = allLots.find(l => l.id === imp.lot_id);
				if (lot && lot.type !== 'appartement') return false;
			}
			return true;
		});
		// Priorité : appartement résolu > non résolu > rien (parking/cave écarté)
		const hit = hitsAppt.find(imp => imp.lot_id && allLots.find(l => l.id === imp.lot_id)?.type === 'appartement')
			?? hitsAppt.find(imp => imp.lot_id)
			?? hitsAppt[0]
			?? null;
		if (!hit) return null;
		// Étage : source primaire = etage_raw de la ligne import (colonne Etage)
		const etage: number | null = etageFromRaw(hit.etage_raw);
		// Bâtiment : allLots (si lot résolu) puis batimentsMap, sinon batiment_id de la ligne import
		let batiment_id: number | null = null;
		let batiment_nom: string | null = null;
		if (hit.lot_id) {
			const lot = allLots.find(l => l.id === hit.lot_id);
			if (lot) {
				batiment_id = lot.batiment_id;
				const mapName = lot.batiment_id ? (batimentsMap[lot.batiment_id] ?? null) : null;
				batiment_nom = mapName
					? mapName.replace(/^Bât\. /i, '')
					: (lot.batiment_nom ? lot.batiment_nom.replace(/^Bât\. /i, '') : null);
			}
		}
		if (!batiment_id) batiment_id = hit.batiment_id ?? null;
		if (!batiment_nom && hit.batiment_nom)
			batiment_nom = hit.batiment_nom.replace(/^Bât\. /i, '');
		return { batiment_id, batiment_nom, etage };
	}

	onMount(async () => {
		if (!$isCS) { goto('/tableau-de-bord'); return; }
		try {
			const [comptes, commandes, batList, users, lotsData, importsData] = await Promise.all([
				adminApi.comptesEnAttente(),
				adminApi.commandesAccesEnAttente(),
				api.get<{ id: number; numero: string }[]>('/auth/batiments').catch(() => []),
				adminApi.utilisateurs().catch(() => []),
				lotsApi.tous().catch(() => []),
				lotsApi.listImports().catch(() => []),
			]);
			comptesEnAttente = comptes;
			commandesEnAttente = commandes;
			batimentsList = batList;
			batimentsMap = Object.fromEntries((batList as any[]).map((b) => [b.id, `Bât. ${b.numero}`]));
			allUsers = (users as any[]).map((u) => ({
				id: u.id, prenom: u.prenom, nom: u.nom,
				email: u.email, telephone: u.telephone, batiment_id: u.batiment_id,
			}));
			allLots = lotsData as LotRow[];
			lotImports = importsData as any[];
		} catch (e: any) {
			toast('error', 'Erreur de chargement');
		} finally {
			loading = false;
		}
		loadAnnuaire();
	});

	async function loadAnnuaire() {
		annuaireLoading = true;
		try {
			const [csData, syndicData] = await Promise.all([
				annuaireAdmin.getCS(),
				annuaireAdmin.getSyndic(),
			]);
			agAnnee = csData.ag_annee ?? null;
			agDate = csData.ag_date ?? '';
			whatsappUrl = csData.whatsapp_url ?? '';
			membresCS = (csData.membres ?? []).map((m: any): MembreCSForm => ({
				genre: m.genre ?? 'Mme',
				prenom: m.prenom ?? '', nom: m.nom ?? '',
				batiment_id: m.batiment_id ?? null,
				batiment_nom: m.batiment_nom ?? null,
				etage: m.etage ?? null,
				user_id: m.user_id ?? null,
				est_gestionnaire_site: m.est_gestionnaire_site ?? false,
				est_president: m.est_president ?? false,
			}));
			membresCS.sort((a, b) => {
				const bat = (a.batiment_nom ?? 'zzz').localeCompare(b.batiment_nom ?? 'zzz', 'fr');
				if (bat !== 0) return bat;
				return (a.nom ?? '').localeCompare(b.nom ?? '', 'fr');
			});
			membresCS = [...membresCS];
			csOpenIdx = null; csEditIdx = null;
			csHeaderEditing = false;
			nomSyndic = syndicData.nom_syndic ?? '';
			adresseSyndic = syndicData.adresse ?? '';
			siteWebSyndic = syndicData.site_web ?? '';
			membresSyndic = (syndicData.membres ?? []).map((m: any): MembreSyndicForm => ({
				genre: m.genre ?? 'Mme',
				prenom: m.prenom ?? '', nom: m.nom ?? '',
				fonction: m.fonction ?? '', email: m.email ?? '',
				telephones: m.telephone
					? m.telephone.split(',').map((t: string) => t.trim()).filter(Boolean)
					: [''],
				est_principal: m.est_principal ?? false,
				user_id: m.user_id ?? null,
			}));
			syndicOpenIdx = null; syndicEditIdx = null;
			syndicHeaderEditing = false;
		} catch {
			toast('error', 'Erreur chargement annuaire');
		} finally {
			annuaireLoading = false;
		}
	}

	// -- CS handlers --------------------------------------------------------
	function addMembreCS() {
		membresCS = [...membresCS, { genre: 'Mme', prenom: '', nom: '', batiment_id: null, batiment_nom: null, etage: null, user_id: null, est_gestionnaire_site: false, est_president: false }];
		csOpenIdx = membresCS.length - 1;
		csEditIdx = membresCS.length - 1;
	}
	function removeMembreCS(i: number) {
		membresCS = membresCS.filter((_, j) => j !== i);
		if (csOpenIdx === i) { csOpenIdx = null; csEditIdx = null; }
		else if (csOpenIdx !== null && csOpenIdx > i) csOpenIdx--;
		if (csEditIdx !== null && csEditIdx !== i && csEditIdx > i) csEditIdx--;
	}

	function onCSNomInput(i: number) {
		const nom = membresCS[i].nom;
		const imp = findImportForNom(nom);
		if (imp) {
			membresCS[i] = { ...membresCS[i], batiment_id: imp.batiment_id, batiment_nom: imp.batiment_nom, etage: imp.etage };
		}
		if (!membresCS[i].user_id) {
			const matchedUser = findUserByNom(nom);
			if (matchedUser) membresCS[i] = { ...membresCS[i], user_id: matchedUser.id };
		}
		membresCS = [...membresCS];
	}

	function clearUserCS(i: number) {
		membresCS[i] = { ...membresCS[i], user_id: null };
		membresCS = [...membresCS];
	}

	async function onPresidentChange(i: number) {
		// Si on décoche, c'est OK
		if (!membresCS[i].est_president) {
			membresCS[i] = { ...membresCS[i], est_president: false };
			membresCS = [...membresCS];
			return;
		}

		// Si on coche, vérifier s'il y a déjà un président
		const currentPresident = membresCS.findIndex(m => m.est_president && membresCS.indexOf(m) !== i);
		if (currentPresident !== -1) {
			// Demander confirmation
			const oldName = `${membresCS[currentPresident].prenom} ${membresCS[currentPresident].nom}`;
			const newName = `${membresCS[i].prenom} ${membresCS[i].nom}`;
			const confirmed = confirm(`Un président existe déjà (${oldName}).\n\nVoulez-vous remplacer par ${newName} ?`);
			
			if (confirmed) {
				// Désélectionner l'ancien
				membresCS[currentPresident] = { ...membresCS[currentPresident], est_president: false };
				// Sélectionner le nouveau
				membresCS[i] = { ...membresCS[i], est_president: true };
				membresCS = [...membresCS];
				toast('info', `${newName} est maintenant président du CS`);
			} else {
				// Annuler la sélection
				membresCS[i] = { ...membresCS[i], est_president: false };
				membresCS = [...membresCS];
			}
		} else {
			// Aucun président existant, on peut le cocher
			membresCS[i] = { ...membresCS[i], est_president: true };
			membresCS = [...membresCS];
			toast('info', `${membresCS[i].prenom} ${membresCS[i].nom} est maintenant président du CS`);
		}
	}

	async function saveCS() {
		savingCS = true;
		try {
			await annuaireAdmin.putCS({ ag_annee: agAnnee, ag_date: agDate || null, whatsapp_url: whatsappUrl || null, membres: membresCS });
			toast('success', 'Conseil Syndical enregistré');
			csHeaderEditing = false;
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally { savingCS = false; }
	}

	async function saveMembreCS(i: number) {
		savingCSIdx = i;
		try {
			await annuaireAdmin.putCS({ ag_annee: agAnnee, ag_date: agDate || null, whatsapp_url: whatsappUrl || null, membres: membresCS });
			csOpenIdx = null; csEditIdx = null;
			toast('success', `${membresCS[i].prenom} ${membresCS[i].nom} enregistré`);
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally { savingCSIdx = null; }
	}

	// -- Syndic handlers ----------------------------------------------------
	function addMembreSyndic() {
		membresSyndic = [...membresSyndic, { genre: 'Mme', prenom: '', nom: '', fonction: '', email: '', telephones: [''], est_principal: false, user_id: null }];
		syndicOpenIdx = membresSyndic.length - 1;
		syndicEditIdx = membresSyndic.length - 1;
	}
	function removeMembreSyndic(i: number) {
		membresSyndic = membresSyndic.filter((_, j) => j !== i);
		if (syndicOpenIdx === i) { syndicOpenIdx = null; syndicEditIdx = null; }
		else if (syndicOpenIdx !== null && syndicOpenIdx > i) syndicOpenIdx--;
		if (syndicEditIdx !== null && syndicEditIdx !== i && syndicEditIdx > i) syndicEditIdx--;
	}

	function clearUserSyndic(i: number) {
		membresSyndic[i] = { ...membresSyndic[i], user_id: null };
		membresSyndic = [...membresSyndic];
	}

	function onSyndicNomInput(i: number) {
		if (!membresSyndic[i].user_id) {
			const matchedUser = findUserByNom(membresSyndic[i].nom);
			if (matchedUser) {
				membresSyndic[i] = { ...membresSyndic[i], user_id: matchedUser.id };
				membresSyndic = [...membresSyndic];
			}
		}
	}

	function setPrincipal(i: number) {
		membresSyndic = membresSyndic.map((m, j) => ({ ...m, est_principal: j === i }));
	}

	async function moveMembreSyndic(i: number, dir: -1 | 1) {
		const j = i + dir;
		if (j < 0 || j >= membresSyndic.length) return;
		const arr = [...membresSyndic];
		[arr[i], arr[j]] = [arr[j], arr[i]];
		membresSyndic = arr;
		syndicOpenIdx = null; syndicEditIdx = null;
		// Sauvegarde silencieuse de l'ordre
		try {
			await annuaireAdmin.putSyndic({
				nom_syndic: nomSyndic, adresse: adresseSyndic, site_web: siteWebSyndic || null,
				membres: membresSyndic.map((m) => ({
					genre: m.genre, prenom: m.prenom, nom: m.nom,
					fonction: m.fonction || null, email: m.email || null,
					telephone: m.telephones.map((t) => t.trim()).filter(Boolean).join(',') || null,
					est_principal: m.est_principal, user_id: m.user_id,
				})),
			});
		} catch { /* silencieux */ }
	}

	async function saveSyndic() {
		for (const m of membresSyndic) {
			if (!m.telephones.some((t) => t.trim())) {
				toast('error', `Au moins un téléphone requis pour ${m.prenom || '…'} ${m.nom || ''}`);
				return;
			}
		}
		savingSyndic = true;
		try {
			await annuaireAdmin.putSyndic({
				nom_syndic: nomSyndic,
				adresse: adresseSyndic,
				site_web: siteWebSyndic || null,
				membres: membresSyndic.map((m) => ({
					genre: m.genre, prenom: m.prenom, nom: m.nom,
					fonction: m.fonction || null, email: m.email || null,
					telephone: m.telephones.map((t) => t.trim()).filter(Boolean).join(',') || null,
					est_principal: m.est_principal, user_id: m.user_id,
				})),
			});
			toast('success', 'Syndic enregistré');
			syndicHeaderEditing = false;
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally { savingSyndic = false; }
	}

	async function saveMembreSyndic(i: number) {
		if (!membresSyndic[i].telephones.some((t) => t.trim())) {
			toast('error', 'Au moins un téléphone requis');
			return;
		}
		savingSyndicIdx = i;
		try {
			await annuaireAdmin.putSyndic({
				nom_syndic: nomSyndic,
				adresse: adresseSyndic,
				site_web: siteWebSyndic || null,
				membres: membresSyndic.map((m) => ({
					genre: m.genre, prenom: m.prenom, nom: m.nom,
					fonction: m.fonction || null, email: m.email || null,
					telephone: m.telephones.map((t) => t.trim()).filter(Boolean).join(',') || null,
					est_principal: m.est_principal, user_id: m.user_id,
				})),
			});
			syndicOpenIdx = null; syndicEditIdx = null;
			toast('success', `${membresSyndic[i].prenom} ${membresSyndic[i].nom} enregistré`);
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally { savingSyndicIdx = null; }
	}

	// -- Validations handlers -----------------------------------------------
	// Validation + Nouvel Arrivant
	let cvModal: PendingUser | null = null;
	let cvNewArrivant = false;
	let cvBatiment = '';
	let cvAncienResident = '';
	let cvSubmitting = false;

	function openCSValidation(user: PendingUser) {
		cvModal = user;
		cvNewArrivant = false;
		cvBatiment = user.batiment_id ? (batimentsMap[user.batiment_id] ?? '') : '';
		cvAncienResident = '';
	}

	async function confirmerCSValidation() {
		if (!cvModal) return;
		const u = cvModal;
		cvSubmitting = true;
		try {
			await adminApi.traiterCompte(u.id, { action: 'valider' });
			comptesEnAttente = comptesEnAttente.filter((x) => x.id !== u.id);
			toast('success', 'Compte approuvé.');
			if (cvNewArrivant) {
				await api.post(`/admin/utilisateurs/${u.id}/accueil-arrivant`, {
					batiment: cvBatiment || null,
					ancien_resident: cvAncienResident || null,
				});
				toast('success', 'Actions d\'accueil envoyées.');
			}
			cvModal = null;
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			cvSubmitting = false;
		}
	}

	async function traiterCompte(id: number, decision: 'approuver' | 'rejeter') {
		try {
			await adminApi.traiterCompte(id, { action: decision === 'approuver' ? 'valider' : 'refuser' });
			comptesEnAttente = comptesEnAttente.filter((u) => u.id !== id);
			toast('success', decision === 'approuver' ? 'Compte approuvé' : 'Compte rejeté');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}
	async function traiterCommande(id: number, decision: 'approuver' | 'rejeter') {
		try {
			await adminApi.traiterCommandeAcces(id, { action: decision === 'approuver' ? 'accepter' : 'refuser' });
			commandesEnAttente = commandesEnAttente.filter((c) => c.id !== id);
			toast('success', decision === 'approuver' ? 'Commande approuvée' : 'Commande rejetée');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}
</script>

{#if cvModal}
<div class="modal-overlay" on:click|self={() => (cvModal = null)} role="dialog" aria-modal="true" tabindex="-1">
  <div class="modal-box card" style="max-width:460px">
    <h2 style="font-size:1rem;font-weight:700;margin-bottom:.75rem">Valider le compte de {cvModal.prenom} {cvModal.nom}</h2>
    <label style="display:flex;align-items:flex-start;gap:.6rem;cursor:pointer;border:1.5px solid var(--color-border);border-radius:var(--radius);padding:.75rem;margin-bottom:.75rem">
      <input type="checkbox" bind:checked={cvNewArrivant} style="margin-top:.2rem;flex-shrink:0" />
      <div>
        <strong style="font-size:.9rem">&#x1F3E0; Nouvel Arrivant</strong>
        <p style="font-size:.78rem;color:var(--color-text-muted);margin:.25rem 0 0">
          À cocher uniquement pour un <strong>nouveau résident</strong> qui emménage dans la copropriété.
          Déclenche automatiquement : message de bienvenue, consignes de copropriété,
          demande d'étiquette boîte aux lettres auprès du syndic, et demande d'ajout sur l'interphone.
          <em>Ne pas cocher pour un résident existant qui crée simplement son compte.</em>
        </p>
      </div>
    </label>
    {#if cvNewArrivant}
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:.6rem;margin-bottom:.75rem">
      <label>Bâtiment / logement<input bind:value={cvBatiment} placeholder="Ex: Bât. A, Apt. 12…" /></label>
      <label>Ancien résident (optionnel)<input bind:value={cvAncienResident} placeholder="Nom de l'ancien occupant…" /></label>
    </div>
    {/if}
    <div class="modal-actions">
      <button class="btn btn-outline" on:click={() => (cvModal = null)}>Annuler</button>
      <button class="btn btn-success" disabled={cvSubmitting} on:click={confirmerCSValidation}>
        {cvSubmitting ? 'En cours…' : '✓ Valider le compte'}
      </button>
    </div>
  </div>
</div>
{/if}

<svelte:head><title>{_pc.titre} · {_siteNom}</title></svelte:head>

<div class="page-header" style="margin-bottom:.5rem">
	<h1 style="display:flex;align-items:center;gap:.4rem;font-size:1.4rem;font-weight:700"><Icon name={_pc.icone || 'shield-half'} size={20} />{_pc.titre}</h1>
</div>
<div class="page-subtitle">{@html safeHtml(_pc.descriptif)}</div>

<!-- Onglets -->
<div class="tabs" style="margin-bottom:1.5rem">
	<button class="tab-btn" class:active={onglet === 'validations'} on:click={() => (onglet = 'validations')}>
		{_pc.onglets?.validations?.label ?? '✅ Comptes & accès'}
		{#if nbComptes + nbCommandes > 0}<span class="badge-count">{nbComptes + nbCommandes}</span>{/if}
	</button>
	<button class="tab-btn" class:active={onglet === 'tickets'} on:click={() => { onglet = 'tickets'; loadTickets(); }}>
		{_pc.onglets?.tickets?.label ?? '\u{1F3AB} Tickets résidence'}
		{#if tkPendingCount > 0}<span class="badge-count">{tkPendingCount}</span>{/if}
	</button>
	<button class="tab-btn" class:active={onglet === 'reporting'} on:click={() => { onglet = 'reporting'; loadReporting(); }}>
		{_pc.onglets?.reporting?.label ?? '\u{1F4CA} Reporting'}
	</button>
	<button class="tab-btn" class:active={onglet === 'annuaire'} on:click={() => (onglet = 'annuaire')}>
		{_pc.onglets?.annuaire?.label ?? '\u{1F4D2} Annuaire CS & Syndic'}
	</button>
</div>
{#if _pc.onglets?.[onglet]?.descriptif}
<p class="tab-descriptif">{@html safeHtml(_pc.onglets[onglet].descriptif)}</p>
{/if}

{#if onglet === 'validations'}
	{#if loading}
		<p style="color:var(--color-text-muted)">Chargement…</p>
	{:else}
		<!-- KPI Cards -->
		<div class="kpi-row" style="margin-bottom:1.5rem">
			<div class="kpi-card" class:kpi-alert={nbComptes > 0}>
				<div class="kpi-value">{nbComptes}</div>
				<div class="kpi-label">Compte(s) à valider</div>
			</div>
			<div class="kpi-card" class:kpi-alert={nbCommandes > 0}>
				<div class="kpi-value">{nbCommandes}</div>
				<div class="kpi-label">Demande(s) d'accès</div>
			</div>
		</div>

		<!-- Comptes en attente -->
		<section style="margin-bottom:2rem;max-width:720px">
			<h2 style="font-size:1rem;font-weight:600;margin-bottom:.75rem">
				Comptes en attente de validation
			</h2>
			{#if comptesEnAttente.length === 0}
				<p class="text-muted-sm">Aucun compte en attente.</p>
			{:else}
				{#each comptesEnAttente as user}
					<div class="pending-row card">
						<div class="pending-info">
							<strong>{user.prenom} {user.nom}</strong>
							<span class="text-muted-sm">
								{user.statut?.replace(/_/g, ' ') ?? '…'}{user.batiment_id ? ` — ${batimentsMap[user.batiment_id] ?? `Bât. #${user.batiment_id}`}` : ''}
							</span>
							{#if (user.statut === 'aidant' || user.statut === 'mandataire') && user.nom_aide}
								<span class="text-muted-sm">👤 Aidé : {user.prenom_aide} {user.nom_aide}</span>
							{/if}
							<span class="text-muted-sm">{fmtDateShort(user.cree_le)}</span>
						</div>
						<div class="pending-actions">
							<button class="btn btn-sm btn-success" on:click={() => openCSValidation(user)}>✓ Approuver</button>
							<button class="btn btn-sm btn-danger"  on:click={() => traiterCompte(user.id, 'rejeter')}>✗ Rejeter</button>
						</div>
					</div>
				{/each}
			{/if}
		</section>

		<!-- Commandes d'accès -->
		<section style="max-width:720px">
			<h2 style="font-size:1rem;font-weight:600;margin-bottom:.75rem">
				Demandes d'accès (badges / télécommandes)
			</h2>
			{#if commandesEnAttente.length === 0}
				<p class="text-muted-sm">Aucune demande en attente.</p>
			{:else}
				{#each commandesEnAttente as cmd}
					<div class="pending-row card">
						<div class="pending-info">
							<strong>{cmd.proprietaire.prenom} {cmd.proprietaire.nom}</strong>
							<span class="text-muted-sm">
								{cmd.lot.batiment.nom} · {cmd.lot.reference} ·
								{cmd.type_acces.replace('_', ' ')} · {cmd.quantite}
							</span>
							<span class="text-muted-sm">{fmtDateShort(cmd.cree_le)}</span>
						</div>
						<div class="pending-actions">
							<button class="btn btn-sm btn-success" on:click={() => traiterCommande(cmd.id, 'approuver')}>✓ Approuver</button>
							<button class="btn btn-sm btn-danger"  on:click={() => traiterCommande(cmd.id, 'rejeter')}>✗ Rejeter</button>
						</div>
					</div>
				{/each}
			{/if}
		</section>
	{/if}

{:else if onglet === 'tickets'}
	<div style="margin-bottom:1.25rem;display:flex;gap:.4rem;flex-wrap:wrap;align-items:center">
		<button class="btn btn-sm" class:btn-primary={tkFilter === ''} on:click={() => tkFilter = ''}>Tous</button>
		<button class="btn btn-sm" class:btn-primary={tkFilter === 'ouvert'} on:click={() => tkFilter = 'ouvert'}>&#x1F535; Ouvert</button>
		<button class="btn btn-sm" class:btn-primary={tkFilter === 'en_cours'} on:click={() => tkFilter = 'en_cours'}>&#x1F7E1; En cours</button>
		<button class="btn btn-sm" class:btn-primary={tkFilter === 'résolu'} on:click={() => tkFilter = 'résolu'}>&#x1F7E2; Résolu</button>
		<button class="btn btn-sm" class:btn-primary={tkFilter === 'annulé'} on:click={() => tkFilter = 'annulé'}>⚫ Annulé</button>
	</div>

	{#if tkLoading}
		<p style="color:var(--color-text-muted)">Chargement…</p>
	{:else if tkFiltered.length === 0}
		<div class="empty-state">
			<h3>Aucun ticket{tkFilter ? ' dans ce statut' : ''}</h3>
		</div>
	{:else}
		{#each tkFiltered as t (t.id)}
			{@const expanded = tkExpandedId === t.id}
			{@const evols = tkEvolsMap[t.id] ?? []}
			<div class="tk-expand" class:expanded class:urgent={t.categorie === 'urgence'}
				role="button" tabindex="0"
				on:click={() => tkToggle(t.id)}
				on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && tkToggle(t.id)}>
				<div class="tk-row">
					<div class="tk-main">
						<div class="tk-row-inner">
							<span class="tk-cat">{TK_CAT_ICON[t.categorie] ?? '\u{1F4CB}'}</span>
							<span class="tk-row-titre">{t.titre}</span>
							<span class="badge {TK_STATUT_BADGE[t.statut] ?? 'badge-gray'}" style="flex-shrink:0">{TK_STATUT_LABELS[t.statut] ?? t.statut}</span>
							{#if t.priorite === 'haute'}<span class="badge badge-orange" style="flex-shrink:0">⚡ Urgente</span>{/if}
						</div>
						{#if t.auteur_nom || t.auteur_batiment_nom}
							<div class="tk-ticket-meta">
								{#if t.auteur_nom}<span>&#x1F464; {t.auteur_nom}</span>{/if}
								{#if t.auteur_batiment_nom}<span>&#x1F4CD; {t.auteur_batiment_nom}</span>{/if}
							</div>
						{/if}
					</div>
					<div class="tk-row-right">
						<span class="tk-row-date">{fmtDate(t.mis_a_jour_le ?? t.cree_le)}</span>
						<button class="btn-icon" aria-label="Traiter" title="Changer état / commenter"
							on:click|stopPropagation={() => tkOpenForm(t.id)}>&#x1F4AC;</button>
						<span class="chevron" class:open={expanded}>›</span>
					</div>
				</div>

				{#if !expanded}
					<div class="tk-preview clamp-5">{@html renderDesc(t.description)}</div>
				{/if}

				{#if expanded}
					<div class="tk-body" on:click|stopPropagation on:keydown|stopPropagation>
						{#if tkShowForm === t.id}
							<div class="evol-form">
								<div style="display:flex;gap:.5rem;margin-bottom:.6rem;flex-wrap:wrap">
									<button type="button" class="pill" class:pill-active={tkEvolType === 'etat'}
										on:click={() => (tkEvolType = 'etat')}>&#x1F504; Changement d'état</button>
									<button type="button" class="pill" class:pill-active={tkEvolType === 'commentaire'}
										on:click={() => (tkEvolType = 'commentaire')}>&#x1F4AC; Commentaire</button>
								</div>
								{#if tkEvolType === 'etat'}
									<div class="field" style="margin-bottom:.6rem">
										<label for="tk-statut-{t.id}">Nouvel état *</label>
										<select id="tk-statut-{t.id}" bind:value={tkEvolStatut}>
											<option value="">— Choisir —</option>
											<option value="ouvert">&#x1F535; Ouvert</option>
											<option value="en_cours">&#x1F7E1; En cours</option>
											<option value="résolu">&#x1F7E2; Résolu</option>
											<option value="annulé">⚫ Annulé</option>
										</select>
									</div>
								{/if}
								<div class="field" style="margin-bottom:.6rem">
									<label for="tk-contenu-{t.id}">{tkEvolType === 'etat' ? 'Commentaire (optionnel)' : 'Commentaire *'}</label>
									<textarea id="tk-contenu-{t.id}" bind:value={tkEvolContenu} rows="3"
										placeholder={tkEvolType === 'etat' ? 'Précisions sur ce changement…' : 'Ajoutez une note de suivi…'}
										style="width:100%;padding:.4rem .6rem;border:1px solid var(--color-border);border-radius:6px;font-size:.875rem;resize:vertical"
									></textarea>
								</div>
								<div style="display:flex;justify-content:flex-end;gap:.5rem">
									<button class="btn btn-outline btn-sm" on:click={() => (tkShowForm = null)}>Annuler</button>
									<button class="btn btn-primary btn-sm"
										disabled={tkEvolSaving || (tkEvolType === 'etat' && !tkEvolStatut) || (tkEvolType === 'commentaire' && !tkEvolContenu.trim())}
										on:click={() => tkSubmitEvol(t)}>
										{tkEvolSaving ? 'Envoi…' : 'Valider'}
									</button>
								</div>
							</div>
						{:else}
							{#if t.auteur_nom || t.auteur_batiment_nom}
								<div class="tk-context-meta">
									{#if t.auteur_nom}<span class="context-chip">Demandeur : {t.auteur_nom}</span>{/if}
									{#if t.auteur_batiment_nom}<span class="context-chip">Bâtiment : {t.auteur_batiment_nom}</span>{/if}
								</div>
							{/if}
							<div class="rich-content" style="font-size:.875rem;line-height:1.6;margin-bottom:.5rem">{@html renderDesc(t.description)}</div>
							<small style="color:var(--color-text-muted);font-size:.78rem">
								Créé le {fmtDate(t.cree_le)} · <span style="font-family:monospace">#{t.numero}</span>
							</small>
							{#if evols.length > 0}
								{@const sorted = [...evols].sort((a, b) => new Date(b.cree_le).getTime() - new Date(a.cree_le).getTime())}
								<div class="evol-list">
									{#each sorted as evol, i (evol.id)}
										{#if i > 0}<hr class="evol-sep" />{/if}
										<div class="evol-item evol-{evol.type}">
											<span class="evol-icon">{#if evol.type === 'etat'}&#x1F504;{:else if evol.type === 'reponse'}&#x1F4AC;{:else}&#x1F4DD;{/if}</span>
											<div class="evol-body">
												<span class="evol-meta">{fmtDatetime(evol.cree_le)}{#if evol.auteur_nom} · {evol.auteur_nom}{/if}</span>
												{#if evol.type === 'etat'}
													<span class="evol-text">Statut : <strong>{TK_STATUT_LABELS[evol.ancien_statut ?? ''] || 'Aucun'}</strong> → <strong>{TK_STATUT_LABELS[evol.nouveau_statut ?? ''] || evol.nouveau_statut}</strong></span>
												{/if}
												{#if evol.contenu}<div class="evol-content rich-content">{@html renderDesc(evol.contenu)}</div>{/if}
											</div>
										</div>
									{/each}
								</div>
							{/if}
							<div style="margin-top:.75rem">
								<button class="btn btn-sm btn-outline" on:click|stopPropagation={() => tkOpenForm(t.id)}>&#x1F504; Changer état / commenter</button>
							</div>
						{/if}
					</div>
				{/if}
			</div>
		{/each}
	{/if}

{:else if onglet === 'reporting'}
	<div class="reporting-panel">
		<div class="reporting-toolbar no-print">
			<div class="reporting-switch">
				<button class="pill" class:pill-active={reportView === 'kanban'} on:click={() => (reportView = 'kanban')}>
					&#x1F4CC; AG / CS / Syndic
				</button>
				<button class="pill" class:pill-active={reportView === 'tickets'} on:click={() => (reportView = 'tickets')}>
					&#x1F4CA; Analyse tickets
				</button>
				<button class="pill" class:pill-active={reportView === 'devis'} on:click={() => (reportView = 'devis')}>
					&#x1F4CB; Devis & interventions
				</button>
				<button class="pill" class:pill-active={reportView === 'prestataires'} on:click={() => (reportView = 'prestataires')}>
					&#x1F3E2; Prestataires
				</button>
				<button class="pill" class:pill-active={reportView === 'renouvellements'} on:click={() => (reportView = 'renouvellements')}>
					&#x1F4C5; Renouvellements
				</button>
			</div>
			<div class="reporting-actions">
				<button class="btn btn-sm btn-outline" on:click={refreshReporting} disabled={reportingLoading} title="Rafraîchir les données">
					&#x1F504;{reportingLoading ? ' …' : ''}
				</button>
				<button class="btn btn-sm btn-outline" on:click={printCurrentReporting}>
					&#x1F4C4; Exporter PDF
				</button>
				<button class="btn btn-sm btn-primary" on:click={printCurrentReporting}>
					&#x1F5A8; Imprimer
				</button>
			</div>
		</div>

		<div class="reporting-print-header">
			<h2>{reportPrintTitle || (_pc.onglets?.reporting?.label ?? 'Reporting')}</h2>
			<p>Édité le {fmtDatetime(new Date().toISOString())}</p>
		</div>

		{#if reportingLoading}
			<p style="color:var(--color-text-muted)">Chargement des reportings…</p>
		{:else if reportView === 'kanban'}
			<div class="kpi-row" style="margin-bottom:1rem">
				<div class="kpi-card"><div class="kpi-value">{reportKanbanEvents.length}</div><div class="kpi-label">Dossiers en cours</div></div>
				{#each reportKanbanByCol as col}
					<div class="kpi-card"><div class="kpi-value">{col.items.length}</div><div class="kpi-label">{col.label}</div></div>
				{/each}
			</div>
			{#each reportKanbanByCol as col}
				<section class="report-card" style="margin-bottom:1.5rem">
					<h3><span class="badge {col.badge}">{col.label}</span> — {col.items.length} dossier{col.items.length > 1 ? 's' : ''}</h3>
					{#if col.items.length === 0}
						<div class="empty-state"><h3>Aucun dossier dans cette colonne</h3></div>
					{:else}
						<div class="report-table-wrap">
							<table class="report-table">
								<thead>
									<tr>
										<th>Événement</th>
										<th>Contexte</th>
										<th>Dates</th>
									</tr>
								</thead>
								<tbody>
									{#each col.items as ev (ev.id)}
										<tr>
											<td>
												<strong class="report-event-title">{ev.titre}</strong>
												{#if ev.description}
													<div class="report-event-desc rich-content">{@html renderDesc(ev.description)}</div>
												{/if}
											</td>
											<td>
												<div>{TYPE_LABELS[ev.type] ?? ev.type}</div>
												{#if ev.prestataire_nom}<div class="text-muted-sm">{ev.prestataire_nom}</div>{/if}
												<div class="text-muted-sm">{ev.perimetre}{#if ev.batiment_id} · Bât. {ev.batiment_id}{/if}</div>
												{#if ev.auteur_nom}<div class="text-muted-sm">Par {ev.auteur_nom}</div>{/if}
											</td>
											<td>
												<div>Créé le {fmtDate(ev.cree_le)}</div>
												<div>{daysSince(ev.cree_le)} jour(s)</div>
												<div class="text-muted-sm">MAJ : {fmtDate(ev.mis_a_jour_le ?? ev.cree_le)}</div>
											</td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					{/if}
				</section>
			{/each}

		{:else if reportView === 'tickets'}
			<div class="reporting-toolbar no-print" style="margin-top:0;margin-bottom:1rem">
				<div class="reporting-switch">
					<button class="pill" class:pill-active={reportPeriodDays === 30} on:click={() => (reportPeriodDays = 30)}>30 jours</button>
					<button class="pill" class:pill-active={reportPeriodDays === 90} on:click={() => (reportPeriodDays = 90)}>90 jours</button>
					<button class="pill" class:pill-active={reportPeriodDays === 365} on:click={() => (reportPeriodDays = 365)}>12 mois</button>
				</div>
			</div>

			<div class="kpi-row" style="margin-bottom:1rem">
				<div class="kpi-card"><div class="kpi-value">{reportTicketSource.length}</div><div class="kpi-label">Tickets sur la période</div></div>
				<div class="kpi-card"><div class="kpi-value">{reportTicketSource.filter((t) => t.categorie === 'urgence').length}</div><div class="kpi-label">Urgences</div></div>
				<div class="kpi-card"><div class="kpi-value">{reportTicketBuildings.length}</div><div class="kpi-label">Périmètres / bâtiments touchés</div></div>
			</div>

			<div class="report-grid-2">
				<section class="report-card">
					<h3>Répartition par catégorie</h3>
					<div class="report-table-wrap">
						<table class="report-table compact">
							<thead><tr><th>Catégorie</th><th>Total</th><th>Ouverts / en cours</th></tr></thead>
							<tbody>
								{#each reportTicketCategories as row}
									<tr><td>{row.categorie}</td><td>{row.total}</td><td>{row.ouverts}</td></tr>
								{/each}
							</tbody>
						</table>
					</div>
				</section>

				<section class="report-card">
					<h3>Répartition par bâtiment / périmètre</h3>
					<div class="report-table-wrap">
						<table class="report-table compact">
							<thead><tr><th>Bâtiment / périmètre</th><th>Total</th><th>Ouverts / en cours</th></tr></thead>
							<tbody>
								{#each reportTicketBuildings as row}
									<tr><td>{row.batiment}</td><td>{row.total}</td><td>{row.ouverts}</td></tr>
								{/each}
							</tbody>
						</table>
					</div>
				</section>
			</div>

		{:else if reportView === 'devis'}
			<div class="kpi-row" style="margin-bottom:1rem">
				<div class="kpi-card"><div class="kpi-value">{reportDevisActifs.length}</div><div class="kpi-label">Devis / interventions actifs</div></div>
				<div class="kpi-card"><div class="kpi-value">{reportDevisList.filter((d) => d.statut === 'en_attente').length}</div><div class="kpi-label">En attente</div></div>
				<div class="kpi-card"><div class="kpi-value">{reportDevisList.filter((d) => d.statut === 'accepte').length}</div><div class="kpi-label">Acceptés non clos</div></div>
			</div>

			<div class="report-grid-2 report-grid-2-wide">
				<section class="report-card">
					<h3>Suivi des devis et interventions</h3>
					{#if reportDevisActifs.length === 0}
						<div class="empty-state"><h3>Aucun devis actif</h3></div>
					{:else}
						<div class="report-table-wrap">
							<table class="report-table">
								<thead>
									<tr>
										<th>Objet</th>
										<th>Prestataire</th>
										<th>Périmètre</th>
										<th>Échéance</th>
										<th>Montant</th>
										<th>Statut</th>
									</tr>
								</thead>
								<tbody>
									{#each reportDevisActifs as d}
										<tr>
											<td><strong>{d.titre}</strong>{#if d.frequence_type && d.frequence_valeur}<br /><span class="text-muted-sm">Récurrent : {d.frequence_valeur} {d.frequence_type}</span>{/if}</td>
											<td>{reportPrestataireName(d.prestataire_id)}</td>
											<td>{d.perimetre}{#if d.batiment_id}<br /><span class="text-muted-sm">Bât. {d.batiment_id}</span>{/if}</td>
											<td>{d.date_prestation ? fmtDate(d.date_prestation) : 'Non planifiée'}</td>
											<td>{fmtMoney(d.montant_estime)}</td>
											<td><span class="badge {REPORT_DEVIS_BADGES[d.statut] ?? 'badge-gray'}">{REPORT_DEVIS_LABELS[d.statut] ?? d.statut}</span></td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					{/if}
				</section>

				<section class="report-card">
					<h3>Répartition par statut</h3>
					<div class="report-table-wrap">
						<table class="report-table compact">
							<thead><tr><th>Statut</th><th>Total</th></tr></thead>
							<tbody>
								{#each reportDevisSummary as row}
									<tr><td>{REPORT_DEVIS_LABELS[row.statut] ?? row.statut}</td><td>{row.total}</td></tr>
								{/each}
							</tbody>
						</table>
					</div>
				</section>
			</div>

		{:else if reportView === 'prestataires'}
			<!-- ── Synthèse prestataires ─────────────────────────────────────────── -->
			<div class="kpi-row" style="margin-bottom:1rem">
				<div class="kpi-card"><div class="kpi-value">{reportPrestataires.length}</div><div class="kpi-label">Prestataires actifs</div></div>
				<div class="kpi-card"><div class="kpi-value">{reportDevisList.filter(d => d.statut === 'realise').length}</div><div class="kpi-label">Prestations réalisées</div></div>
			</div>
			<div class="report-table-wrap" style="margin-bottom:1.5rem">
				<table class="report-table">
					<thead>
						<tr>
							<th>Prestataire</th>
							<th>Spécialité</th>
							<th>Type</th>
							<th>Devis actifs</th>
							<th>Réalisés</th>
							<th>Actions</th>
						</tr>
					</thead>
					<tbody>
						{#each reportPrestataires as p (p.id)}
							{@const pDevis = reportDevisList.filter(d => d.prestataire_id === p.id)}
							{@const pActifs = pDevis.filter(d => d.statut === 'en_attente' || d.statut === 'accepte').length}
							{@const pRealises = pDevis.filter(d => d.statut === 'realise').length}
							<tr>
								<td><strong>{p.nom}</strong></td>
								<td>{p.specialite ?? '—'}</td>
								<td>{p.type_prestataire ?? '—'}</td>
								<td>{pActifs}</td>
								<td>{pRealises}</td>
								<td><button class="btn btn-sm btn-outline" on:click={() => loadPrestSynthese(p.id)}>Fiche synthèse</button></td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>

			<!-- Fiche synthèse prestataire (modale inline) -->
			{#if reportPrestSynthLoading}
				<p style="color:var(--color-text-muted)">Chargement synthèse…</p>
			{:else if reportPrestSynth}
				<section class="report-card" style="margin-bottom:1.5rem">
					<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.75rem">
						<h3 style="margin:0">&#x1F4C4; Fiche — {reportPrestSynth.nom}</h3>
						<button class="btn btn-sm btn-outline" on:click={() => { reportPrestSynth = null; reportPrestSynthId = null; }}>✕ Fermer</button>
					</div>
					<div class="report-grid-2" style="margin-bottom:1rem">
						<div>
							<p><strong>Spécialité :</strong> {reportPrestSynth.specialite}</p>
							<p><strong>Type :</strong> {reportPrestSynth.type_prestataire}</p>
							{#if reportPrestSynth.email}<p><strong>Email :</strong> {reportPrestSynth.email}</p>{/if}
							{#if reportPrestSynth.contacts && reportPrestSynth.contacts.length > 0}
								<p><strong>Contacts :</strong></p>
								{#each reportPrestSynth.contacts as c}
									<p style="margin-left:1rem">📞 {c.telephone ?? '—'}{#if c.prenom || c.nom} — {c.prenom ?? ''} {c.nom ?? ''}{/if}{#if c.fonction} ({c.fonction}){/if}{#if c.email} · {c.email}{/if}</p>
								{/each}
							{/if}
						</div>
						<div>
							<p><strong>Contrats actifs :</strong> {reportPrestSynth.nb_contrats}</p>
							<p><strong>Devis / prestations :</strong> {reportPrestSynth.nb_devis}</p>
							<p><strong>Note moyenne :</strong> {reportPrestSynth.note_moyenne != null ? `${starsDisplay(reportPrestSynth.note_moyenne)} ${reportPrestSynth.note_moyenne}/5 (${reportPrestSynth.nb_notations} avis)` : 'Aucune notation'}</p>
							{#if reportPrestSynth.prochaines_visites && reportPrestSynth.prochaines_visites.length > 0}
								<p><strong>Prochaines visites :</strong></p>
								{#each reportPrestSynth.prochaines_visites as v}
									<p style="margin-left:1rem">📅 {fmtDate(v.date)} — {v.contrat}</p>
								{/each}
							{/if}
						</div>
					</div>
					{#if reportPrestSynth.notations && reportPrestSynth.notations.length > 0}
						<h4 style="font-size:.9rem;font-weight:600;margin:1rem 0 .5rem">Historique des notations</h4>
						<div class="report-table-wrap">
							<table class="report-table compact">
								<thead><tr><th>Date</th><th>Note</th><th>Commentaire</th><th>Par</th></tr></thead>
								<tbody>
									{#each reportPrestSynth.notations as n}
										<tr>
											<td>{fmtDate(n.cree_le)}</td>
											<td style="color:#f59e0b">{starsDisplay(n.note)} {n.note}/5</td>
											<td>{n.commentaire ?? '—'}</td>
											<td>{n.auteur_nom}</td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					{/if}
					{#if reportPrestSynth.devis && reportPrestSynth.devis.length > 0}
						<h4 style="font-size:.9rem;font-weight:600;margin:1rem 0 .5rem">Devis & prestations</h4>
						<div class="report-table-wrap">
							<table class="report-table compact">
								<thead><tr><th>Objet</th><th>Statut</th><th>Date</th><th>Montant</th></tr></thead>
								<tbody>
									{#each reportPrestSynth.devis as d}
										<tr>
											<td>{d.titre}</td>
											<td><span class="badge {REPORT_DEVIS_BADGES[d.statut] ?? 'badge-gray'}">{REPORT_DEVIS_LABELS[d.statut] ?? d.statut}</span></td>
											<td>{d.date_prestation ? fmtDate(d.date_prestation) : '—'}</td>
											<td>{fmtMoney(d.montant_estime)}</td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					{/if}
					{#if reportPrestSynth.contrats && reportPrestSynth.contrats.length > 0}
						<h4 style="font-size:.9rem;font-weight:600;margin:1rem 0 .5rem">Contrats</h4>
						<div class="report-table-wrap">
							<table class="report-table compact">
								<thead><tr><th>Libellé</th><th>Équipement</th><th>Début</th><th>Prochaine visite</th></tr></thead>
								<tbody>
									{#each reportPrestSynth.contrats as c}
										<tr>
											<td>{c.libelle}</td>
											<td>{c.type_equipement}</td>
											<td>{fmtDate(c.date_debut)}</td>
											<td>{c.prochaine_visite ? fmtDate(c.prochaine_visite) : '—'}</td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					{/if}
				</section>
			{/if}

		{:else if reportView === 'renouvellements'}
			<!-- ── Renouvellement contrats & audits ──────────────────────────── -->
			<div class="kpi-row" style="margin-bottom:1rem">
				<div class="kpi-card" class:kpi-alert={renKpiPreavis > 0}>
					<div class="kpi-value">{renKpiPreavis}</div>
					<div class="kpi-label">Contrats en préavis</div>
				</div>
				<div class="kpi-card">
					<div class="kpi-value">{renKpiContrats}</div>
					<div class="kpi-label">Échéances contrats en {ANNEE_COURANTE}</div>
				</div>
				<div class="kpi-card" class:kpi-alert={renKpiDiags > 0}>
					<div class="kpi-value">{renKpiDiags}</div>
					<div class="kpi-label">Audits à (re)planifier</div>
				</div>
			</div>

			<!-- Section 1 : Frise contrats -->
			<section class="report-card" style="margin-bottom:1.5rem">
				<h3>📋 Contrats prestataires — échéances {ANNEE_COURANTE}</h3>
				<p class="report-intro">Contrats dont la fin ou le préavis tombe en {ANNEE_COURANTE}. La zone hachurée indique la période de préavis ({PREAVIS_MOIS} mois).</p>

				{#if contratsAnneeCourante.length === 0}
					<div class="empty-state"><h3>Aucune échéance de contrat en {ANNEE_COURANTE}</h3></div>
				{:else}
					<div class="frise-container">
						<div class="frise-months">
							{#each MOIS_LABELS as m}<div class="frise-month-label">{m}</div>{/each}
						</div>
						{#each contratsAnneeCourante.filter((x): x is typeof x & { dateFin: Date } => !!x.dateFin) as c (c.id)}
							{@const finDansAnnee = c.dateFin.getFullYear() === ANNEE_COURANTE}
							{@const moisFin = finDansAnnee ? c.dateFin.getMonth() : 11.9}
							{@const moisPreavis = c.datePreavis && c.datePreavis.getFullYear() < ANNEE_COURANTE ? 0 : (c.datePreavis?.getMonth() ?? 0)}
							{@const barStart = Math.max(0, moisPreavis)}
							{@const barEnd = moisFin}
							{@const preavisWidth = ((barEnd - barStart) / 12) * 100}
							{@const finPos = finDansAnnee ? ((moisFin + 0.5) / 12) * 100 : 99}
							{@const friseStyle = c.reconduit ? 'reconduit' : c.urgence}
							<div class="frise-row-v2">
								<div class="frise-row-header">
									<div class="frise-row-title">
										<strong>{c.libelle}</strong>
										<span class="text-muted-sm">{c.prestataireNom}</span>
										<span class="text-muted-sm">· {c.type_equipement}</span>
										{#if c.numero_contrat}<span class="text-muted-sm">· N° {c.numero_contrat}</span>{/if}
										{#if c.noteMoy != null}
											<span class="frise-stars" class:frise-stars-bad={c.noteMoy < 3} class:frise-stars-ok={c.noteMoy >= 3 && c.noteMoy < 4} class:frise-stars-good={c.noteMoy >= 4} title="{c.noteMoy}/5 ({c.nbNotations} avis)">{starsDisplay(c.noteMoy)} {c.noteMoy}</span>
										{/if}
									</div>
									<div class="frise-row-badges">
										{#if c.urgence === 'preavis'}<span class="badge badge-orange">Préavis en cours</span>
										{:else}<span class="badge badge-blue">Actif</span>
										{/if}
										{#if c.reconduit}<span class="badge badge-purple">♻ Reconduit</span>{/if}
										<span class="frise-row-dates">
											{fmtDate(c.date_debut)} → {fmtDate(c.dateFin.toISOString())}
											{#if c.datePreavis}· préavis dès {fmtDate(c.datePreavis.toISOString())}{/if}
										</span>
									</div>
								</div>
								<div class="frise-bar-track">
									{#if preavisWidth > 0}
										<div class="frise-preavis-zone frise-urgence-{friseStyle}" style="left:{(barStart/12)*100}%;width:{preavisWidth}%"></div>
									{/if}
									{#if finDansAnnee}
										<div class="frise-marker frise-marker-{friseStyle}" style="left:{finPos}%" title="Fin : {fmtDate(c.dateFin.toISOString())}">
											<span class="frise-marker-label">{c.dateFin.getDate()}/{c.dateFin.getMonth()+1}</span>
										</div>
									{:else}
										<div class="frise-marker frise-marker-{friseStyle}" style="left:98%;opacity:.7" title="Fin : {fmtDate(c.dateFin.toISOString())} ({c.dateFin.getFullYear()})">
											<span class="frise-marker-label">→ {c.dateFin.getFullYear()}</span>
										</div>
									{/if}
								</div>
							</div>
						{/each}
						<div class="frise-legend">
							<span><span class="frise-legend-dot" style="background:#dc2626"></span> Préavis en cours</span>
							<span><span class="frise-legend-dot" style="background:#f59e0b"></span> Expire cette année</span>
							<span><span class="frise-legend-dot" style="background:#8b5cf6"></span> Reconduit tacitement</span>
							<span class="frise-legend-hatch">▧ Zone de préavis</span>
							<span style="font-size:.75rem;color:var(--color-text-muted)">→ Fin en {ANNEE_COURANTE + 1}</span>
						</div>
					</div>
				{/if}

				<!-- Contrats futurs (hors exercice courant) -->
				{#if contratsFuturs.length > 0}
					<div style="margin-top:1.2rem">
						<h4 style="font-size:.9rem;font-weight:600;margin:0 0 .5rem;color:var(--color-text-muted)">📅 Échéances futures ({contratsFuturs.length})</h4>
						<div class="frise-compact-list">
							{#each contratsFuturs as c (c.id)}
								<div class="frise-compact-item">
									<div class="frise-compact-info">
										<strong>{c.libelle}</strong>
										<span class="text-muted-sm">{c.prestataireNom} · {c.type_equipement}</span>
									</div>
									<div class="frise-compact-meta">
										{#if c.noteMoy != null}<span class="frise-stars" class:frise-stars-bad={c.noteMoy < 3} class:frise-stars-ok={c.noteMoy >= 3 && c.noteMoy < 4} class:frise-stars-good={c.noteMoy >= 4}>{starsDisplay(c.noteMoy)} {c.noteMoy}</span>{/if}
										<span>Fin : {c.dateFin ? fmtDate(c.dateFin.toISOString()) : 'N/A'}</span>
										<span>Préavis : {c.datePreavis ? fmtDate(c.datePreavis.toISOString()) : 'N/A'}</span>
										{#if c.reconduit}<span class="badge badge-purple">♻ Reconduit</span>{/if}
									</div>
								</div>
							{/each}
						</div>
					</div>
				{/if}

				<!-- Contrats sans dates -->
				{#if contratsInconnus.length > 0}
					<div style="margin-top:1.2rem">
						<h4 style="font-size:.9rem;font-weight:600;margin:0 0 .5rem;color:var(--color-text-muted)">⚠️ Dates manquantes ({contratsInconnus.length})</h4>
						<div class="frise-compact-list">
							{#each contratsInconnus as c (c.id)}
								<div class="frise-compact-item">
									<div class="frise-compact-info">
										<strong>{c.libelle}</strong>
										<span class="text-muted-sm">{c.prestataireNom} · {c.type_equipement}{#if c.numero_contrat} · N° {c.numero_contrat}{/if}</span>
									</div>
									<div class="frise-compact-meta">
										{#if c.noteMoy != null}<span class="frise-stars" class:frise-stars-bad={c.noteMoy < 3} class:frise-stars-ok={c.noteMoy >= 3 && c.noteMoy < 4} class:frise-stars-good={c.noteMoy >= 4}>{starsDisplay(c.noteMoy)} {c.noteMoy}</span>{/if}
										<span>Début : {c.date_debut ? fmtDate(c.date_debut) : 'N/A'}</span>
										<span class="badge badge-gray">Durée non renseignée</span>
									</div>
								</div>
							{/each}
						</div>
					</div>
				{/if}
			</section>

			<!-- Section 2 : Diagnostics et Contrôles Réglementaires -->
			<section class="report-card">
				<h3>🔍 Diagnostics et Contrôles Réglementaires — {ANNEE_COURANTE}–{ANNEE_COURANTE + 10}</h3>
				<p class="report-intro">Échéances issues de Résidence / Diagnostics et Contrôles Réglementaires, calculées depuis le dernier rapport + fréquence légale.</p>

				{#if diagsAvecNext.length === 0}
					<div class="empty-state"><h3>Aucun diagnostic applicable</h3><p>Tous les diagnostics sont non applicables.</p></div>
				{:else}
					<!-- Grille par année -->
					{#each diagsParAnnee as [annee, diags]}
						<div class="audit-year-group" class:audit-year-current={annee === ANNEE_COURANTE}>
							<h4 class="audit-year-title">
								{annee}
								<span class="badge {annee === ANNEE_COURANTE ? 'badge-orange' : 'badge-blue'}">{diags.length} audit{diags.length > 1 ? 's' : ''}</span>
							</h4>
							<div class="report-table-wrap">
								<table class="report-table compact">
									<thead>
										<tr><th>Diagnostic</th><th>Code</th><th>Fréquence</th><th>Dernier rapport</th><th>Prochaine échéance</th><th>Statut</th></tr>
									</thead>
									<tbody>
										{#each diags as d (d.id)}
											<tr>
												<td><strong>{d.nom}</strong></td>
												<td>{d.code}</td>
												<td>{d.frequence ?? 'N/A'}</td>
												<td>{d.lastRapportDate ? fmtDate(d.lastRapportDate) : 'N/A'}</td>
												<td>{d.nextDate ? fmtDate(d.nextDate.toISOString()) : 'N/A'}</td>
												<td>
													{#if d.urgence === 'depasse'}<span class="badge badge-red">Dépassé</span>
													{:else if d.urgence === 'annee'}<span class="badge badge-orange">À faire en {ANNEE_COURANTE}</span>
													{:else}<span class="badge badge-blue">{annee}</span>
													{/if}
												</td>
											</tr>
										{/each}
									</tbody>
								</table>
							</div>
						</div>
					{/each}

					<!-- Diagnostics permanents -->
					{#if diagsPermanents.length > 0}
						<div class="audit-year-group" style="margin-top:1rem">
							<h4 class="audit-year-title">
								Permanent
								<span class="badge badge-blue">{diagsPermanents.length}</span>
							</h4>
							<p class="report-intro">Diagnostics à validité permanente (sauf si révision nécessaire).</p>
							<div class="report-table-wrap">
								<table class="report-table compact">
									<thead>
										<tr><th>Diagnostic</th><th>Code</th><th>Fréquence</th><th>Dernier rapport</th><th>Statut</th></tr>
									</thead>
									<tbody>
										{#each diagsPermanents as d (d.id)}
											<tr>
												<td><strong>{d.nom}</strong></td>
												<td>{d.code}</td>
												<td>{d.frequence ?? 'N/A'}</td>
												<td>{d.lastRapportDate ? fmtDate(d.lastRapportDate) : 'N/A'}</td>
												<td><span class="badge badge-green">✓ Permanent</span></td>
											</tr>
										{/each}
									</tbody>
								</table>
							</div>
						</div>
					{/if}

					<!-- Diagnostics sans échéance calculable -->
					{#if diagsSansEcheance.length > 0}
						<div class="audit-year-group" style="margin-top:1rem">
							<h4 class="audit-year-title">
								Sans échéance calculable
								<span class="badge badge-gray">{diagsSansEcheance.length}</span>
							</h4>
							<p class="report-intro">Diagnostics sans rapport initial ou sans fréquence définie.</p>
							<div class="report-table-wrap">
								<table class="report-table compact">
									<thead>
										<tr><th>Diagnostic</th><th>Code</th><th>Fréquence</th><th>Dernier rapport</th><th>Statut</th></tr>
									</thead>
									<tbody>
										{#each diagsSansEcheance as d (d.id)}
											<tr>
												<td><strong>{d.nom}</strong></td>
												<td>{d.code}</td>
												<td>{d.frequence ?? 'N/A'}</td>
												<td>{d.lastRapportDate ? fmtDate(d.lastRapportDate) : 'N/A'}</td>
												<td>
													{#if d.rapports.length === 0}<span class="badge badge-gray">Aucun rapport</span>
													{:else}<span class="badge badge-gray">À planifier</span>
													{/if}
												</td>
											</tr>
										{/each}
									</tbody>
								</table>
							</div>
						</div>
					{/if}
				{/if}
			</section>
		{/if}
	</div>

{:else if onglet === 'annuaire'}
	{#if annuaireLoading}
		<p style="color:var(--color-text-muted)">Chargement…</p>
	{:else}

		<!-- ── Section Conseil Syndical ──────────────────────────────────────── -->
		<section class="annuaire-section">
			<div class="annuaire-section-header">
				<h2 class="section-title">Conseil Syndical</h2>
			</div>

			{#if csHeaderEditing}
				<div class="form-grid header-edit-form" style="max-width:460px;margin-bottom:1rem">
					<label>
						Voté en AG
						<input type="number" min="2000" max="2099" placeholder="ex. 2024" bind:value={agAnnee} />
					</label>
					<label>
						Date de l'AG
						<input type="date" bind:value={agDate} />
					</label>
					<label>
						URL communauté WhatsApp
						<input type="url" placeholder="https://chat.whatsapp.com/..." bind:value={whatsappUrl} />
					</label>
					<div class="header-edit-actions">
						<button class="btn btn-primary btn-sm" on:click={saveCS} disabled={savingCS}>{savingCS ? '…' : '\u{1F4BE} Enregistrer'}</button>
						<button class="btn btn-sm btn-outline" on:click={() => csHeaderEditing = false}>Annuler</button>
					</div>
				</div>
			{:else}
				<div class="header-summary">
					<span>{agAnnee ? `AG ${agAnnee}` : 'Année AG non renseignée'}{agDate ? ` · ${fmtDateShort(agDate)}` : ''}</span>
					{#if whatsappUrl}<span style="margin-left:.5rem">· <a href={whatsappUrl} target="_blank" rel="noopener">WhatsApp</a></span>{/if}
					<button type="button" class="btn-icon btn-icon-edit" title="Modifier" on:click={() => csHeaderEditing = true}><Icon name="pencil" size={13} /></button>
				</div>
			{/if}

			{#each membresCS as m, i}
				<div class="membre-card" class:membre-president={m.est_president} style="cursor:pointer"
					on:click={() => { if (csEditIdx !== i) csOpenIdx = csOpenIdx === i ? null : i; }}>
					<!-- Header fiche -->
					<div class="membre-card-header">
						<div style="display:flex;align-items:center;gap:.5rem;flex-wrap:wrap">
							{#if m.est_president}<span class="badge-president">👑 Président</span>{/if}
							<span class="membre-card-title">{m.genre} {m.prenom || '…'} <span class="nom-upper">{m.nom || ''}</span></span>
						</div>
						<div class="membre-card-actions" on:click|stopPropagation>
							{#if csEditIdx === i}
								<button type="button" class="btn-icon btn-icon-save" title="Enregistrer ce membre"
									disabled={savingCSIdx === i}
									on:click={() => saveMembreCS(i)}>
									{#if savingCSIdx === i}…{:else}&#x1F4BE;{/if}
								</button>
							{:else}
								<button type="button" class="btn-icon btn-icon-edit" title="Modifier" on:click={() => { csOpenIdx = i; csEditIdx = i; }}><Icon name="pencil" size={13} /></button>
							{/if}
							<button type="button" class="btn-icon btn-icon-remove" title="Supprimer" on:click={() => removeMembreCS(i)}><Icon name="trash-2" size={14} /></button>
						</div>
					</div>

					{#if csOpenIdx === i}
						{#if csEditIdx === i}
							<div class="form-grid">
								<label>
									Civilité
									<select bind:value={membresCS[i].genre} on:change={() => membresCS = [...membresCS]}>
										<option value="Mme">Mme</option>
										<option value="Mlle">Mlle</option>
										<option value="Mr">Mr</option>
									</select>
								</label>
								<label>
									Prénom
									<input type="text" bind:value={membresCS[i].prenom} placeholder="Prénom" />
								</label>
								<label>
									NOM
									<input type="text" bind:value={membresCS[i].nom} placeholder="NOM" class="input-nom"
										on:input={() => onCSNomInput(i)} />
								</label>
							</div>
							{#if m.batiment_nom || m.etage != null}
								<div class="localisation-info">
									&#x1F4CD; {m.batiment_nom ? `Bât. ${m.batiment_nom}` : ''}{m.batiment_nom && m.etage != null ? ' — ' : ''}{m.etage != null ? `Étage ${m.etage}` : ''}
								</div>
							{/if}
							<div class="user-link-indicator">
								{#if m.user_id}
									<span class="user-linked"><span>&#x1F517; Inscrit lié</span><button type="button" class="btn-unlink" on:click={() => clearUserCS(i)}>Délier</button></span>
								{:else if membresCS[i].nom.length >= 2}
									<span class="user-no-match">Aucun inscrit avec ce NOM</span>
								{/if}
							</div>
							<div class="cs-role-flags">
								<label class="cs-role-flag">
									<input type="checkbox" checked={membresCS[i].est_president} on:change={() => onPresidentChange(i)} />
									<span>Président du Conseil Syndical (optionnel)</span>
								</label>
							</div>
							<div class="header-edit-actions" style="margin-top:.75rem">
								<button class="btn btn-primary btn-sm" on:click={() => saveMembreCS(i)} disabled={savingCSIdx === i}>
									{savingCSIdx === i ? '…' : '💾 Enregistrer'}
								</button>
								<button class="btn btn-sm btn-outline" on:click={() => { csEditIdx = null; csOpenIdx = null; }}>Annuler</button>
							</div>
						{:else}
							<!-- Vue lecture seule (déplié, non édité) -->
							{#if m.batiment_nom || m.etage != null}
								<div class="localisation-info">
									&#x1F4CD; {m.batiment_nom ? `Bât. ${m.batiment_nom}` : ''}{m.batiment_nom && m.etage != null ? ' — ' : ''}{m.etage != null ? `Étage ${m.etage}` : ''}
								</div>
							{/if}
							<div class="user-link-indicator">
								{#if m.user_id}
									<span class="user-linked">&#x1F517; Inscrit lié</span>
								{/if}
							</div>
						{/if}
					{:else}
						<!-- Vue résumé (replié) -->
						<div class="membre-summary">
							{#if m.batiment_nom || m.etage != null}
								<span class="summary-loc">&#x1F4CD; {m.batiment_nom ? `Bât. ${m.batiment_nom}` : ''}{m.batiment_nom && m.etage != null ? ' – ' : ''}{m.etage != null ? `Étage ${m.etage}` : ''}</span>
							{/if}
							{#if m.est_gestionnaire_site}
								<span class="summary-role-badge" title="Gestionnaire du Site">🏢 Gestionnaire du Site</span>
							{/if}
							{#if m.est_president}
								<span class="summary-role-badge summary-role-badge-president" title="Président du Conseil Syndical">👑 Président</span>
							{/if}
							{#if m.user_id}
								<span class="user-linked" style="font-size:.75rem;padding:.15rem .45rem">&#x1F517; Inscrit lié</span>
							{/if}
						</div>
					{/if}
				</div>
			{/each}

			<button type="button" class="btn btn-sm btn-outline" style="margin-top:.5rem" on:click={addMembreCS}>
				+ Nouveau membre CS
			</button>
		</section>

		<!-- ── Section Syndic ────────────────────────────────────────────────── -->
		<section class="annuaire-section">
			<div class="annuaire-section-header">
				<h2 class="section-title">Syndic</h2>
			</div>

			{#if syndicHeaderEditing}
				<div class="form-grid header-edit-form" style="max-width:580px;margin-bottom:1rem">
					<label style="grid-column:1/-1">
						Nom du syndic
						<input type="text" bind:value={nomSyndic} placeholder="ex. Cabinet Bertrand" />
					</label>
					<label style="grid-column:1/-1">
						Adresse
						<textarea rows="2" bind:value={adresseSyndic} placeholder="ex. 12 rue des Lilas, 75015 Paris"></textarea>
					</label>
					<label style="grid-column:1/-1">
						Espace client (site web)
						<input type="url" bind:value={siteWebSyndic} placeholder="https://..." />
					</label>
					<div class="header-edit-actions" style="grid-column:1/-1">
						<button class="btn btn-primary btn-sm" on:click={saveSyndic} disabled={savingSyndic}>{savingSyndic ? '…' : '\u{1F4BE} Enregistrer'}</button>
						<button class="btn btn-sm btn-outline" on:click={() => syndicHeaderEditing = false}>Annuler</button>
					</div>
				</div>
			{:else}
				<div class="header-summary">
					<span>{nomSyndic || 'Nom du syndic non renseigné'}{adresseSyndic ? ` · ${adresseSyndic}` : ''}</span>
					{#if siteWebSyndic}<span style="margin-left:.5rem">· <a href={siteWebSyndic} target="_blank" rel="noopener">Espace client</a></span>{/if}
					<button type="button" class="btn-icon btn-icon-edit" title="Modifier" on:click={() => syndicHeaderEditing = true}><Icon name="pencil" size={13} /></button>
				</div>
			{/if}

			{#each membresSyndic as m, i}
				<div class="membre-card" class:membre-principal={m.est_principal} style="cursor:pointer"
					on:click={() => { if (syndicEditIdx !== i) syndicOpenIdx = syndicOpenIdx === i ? null : i; }}>
					<!-- Header avec badge principal + actions -->
					<div class="membre-card-header">
						<div style="display:flex;align-items:center;gap:.5rem;flex-wrap:wrap">
							{#if m.est_principal}<span class="badge-principal">Interlocuteur principal</span>{/if}
							<span class="membre-card-title">{m.genre} {m.prenom || '…'} <span class="nom-upper">{m.nom || ''}</span></span>
						</div>
						<div class="membre-card-actions" on:click|stopPropagation>
							{#if i > 0}
								<button type="button" class="btn-icon btn-icon-move" title="Monter" on:click={() => moveMembreSyndic(i, -1)}>↑</button>
							{/if}
							<button type="button" class="btn-icon btn-icon-move" title="Descendre" disabled={i === membresSyndic.length - 1} on:click={() => moveMembreSyndic(i, 1)}>↓</button>
							{#if !m.est_principal}
								<button type="button" class="btn-icon btn-icon-star" title="Définir interlocuteur principal" on:click={() => setPrincipal(i)}>★</button>
							{/if}
							{#if syndicEditIdx === i}
								<button type="button" class="btn-icon btn-icon-save" title="Enregistrer ce membre"
									disabled={savingSyndicIdx === i}
									on:click={() => saveMembreSyndic(i)}>
									{#if savingSyndicIdx === i}…{:else}&#x1F4BE;{/if}
								</button>
							{:else}
								<button type="button" class="btn-icon btn-icon-edit" title="Modifier" on:click={() => { syndicOpenIdx = i; syndicEditIdx = i; }}><Icon name="pencil" size={13} /></button>
							{/if}
							<button type="button" class="btn-icon btn-icon-remove" title="Supprimer" on:click={() => removeMembreSyndic(i)}><Icon name="trash-2" size={14} /></button>
						</div>
					</div>

					{#if syndicOpenIdx === i}
						{#if syndicEditIdx === i}
							<div class="form-grid">
								<label>
									Civilité
									<select bind:value={membresSyndic[i].genre} on:change={() => membresSyndic = [...membresSyndic]}>
										<option value="Mme">Mme</option>
										<option value="Mlle">Mlle</option>
										<option value="Mr">Mr</option>
									</select>
								</label>
								<label>
									Prénom
									<input type="text" bind:value={membresSyndic[i].prenom} placeholder="Prénom" />
								</label>
								<label>
									NOM
									<input type="text" bind:value={membresSyndic[i].nom} placeholder="NOM" class="input-nom" on:input={() => onSyndicNomInput(i)} />
								</label>
								<label>
									Fonction
									<input type="text" bind:value={membresSyndic[i].fonction} placeholder="ex. Directeur de gérance" />
								</label>
								<label>
									Email
									<input type="email" bind:value={membresSyndic[i].email} placeholder="Email" />
								</label>
							</div>
							<!-- Téléphones -->
							<div style="margin-top:.65rem">
								<div style="font-size:.85rem;font-weight:600;margin-bottom:.35rem">
									Téléphone{m.telephones.length > 1 ? 's' : ''}
								</div>
								{#each m.telephones as _tel, ti}
									<div style="display:flex;gap:.4rem;margin-bottom:.35rem">
										<input style="flex:1" bind:value={membresSyndic[i].telephones[ti]} placeholder="ex. 01 23 45 67 89" />
										{#if m.telephones.length > 1}
											<button type="button" class="btn btn-sm btn-outline"
												style="color:#dc2626;border-color:#dc2626"
												on:click={() => { membresSyndic[i].telephones = membresSyndic[i].telephones.filter((_, j) => j !== ti); membresSyndic = [...membresSyndic]; }}>
												-
											</button>
										{/if}
									</div>
								{/each}
								<button type="button" class="btn btn-sm btn-outline"
									on:click={() => { membresSyndic[i].telephones = [...membresSyndic[i].telephones, '']; membresSyndic = [...membresSyndic]; }}>
									+ N° de téléphone
								</button>
							</div>
							<!-- Liaison inscrit automatique via NOM -->
							<div class="user-link-indicator" style="margin-top:.65rem">
								{#if m.user_id}
									<span class="user-linked"><span>&#x1F517; Inscrit lié</span><button type="button" class="btn-unlink" on:click={() => clearUserSyndic(i)}>Délier</button></span>
								{:else if membresSyndic[i].nom.length >= 2}
									<span class="user-no-match">Aucun inscrit avec ce NOM</span>
								{/if}
							</div>
						{:else}
							<!-- Vue détail lecture seule (déplié, non édité) -->
							<div class="membre-summary" style="margin-top:.5rem">
								{#if m.fonction}<span class="summary-fonction">{m.fonction}</span>{/if}
								{#if m.email}<span class="summary-loc">{m.email}</span>{/if}
								{#if m.telephones[0]}<span class="summary-loc">{m.telephones.filter(t => t.trim()).join(' · ')}</span>{/if}
								{#if m.user_id}<span class="user-linked" style="font-size:.75rem;padding:.15rem .45rem">&#x1F517; Inscrit lié</span>{/if}
							</div>
						{/if}
					{:else}
						<!-- Vue résumé (replié) -->
						<div class="membre-summary">
							{#if m.fonction}
								<span class="summary-fonction">{m.fonction}</span>
							{/if}
							{#if m.email}
								<span class="summary-loc">{m.email}</span>
							{/if}
							{#if m.telephones[0]}
								<span class="summary-loc">{m.telephones.filter(t => t.trim()).join(' · ')}</span>
							{/if}
							{#if m.user_id}
								<span class="user-linked" style="font-size:.75rem;padding:.15rem .45rem">&#x1F517; Inscrit lié</span>
							{/if}
						</div>
					{/if}
				</div>
			{/each}

			<button type="button" class="btn btn-sm btn-outline" style="margin-top:.5rem" on:click={addMembreSyndic}>
				+ Nouveau membre Syndic
			</button>
		</section>
	{/if}
{/if}

<style>
	/* Tabs */
	.tabs { display: flex; flex-wrap: wrap; gap: .25rem; border-bottom: 2px solid var(--color-border); }
	.tab-btn {
		padding: .45rem .9rem; border: none; background: none; cursor: pointer;
		font-size: .875rem; color: var(--color-text-muted);
		border-bottom: 2px solid transparent; margin-bottom: -2px;
		font-weight: 500; display: flex; align-items: center; gap: .4rem;
		transition: color .15s, border-color .15s; white-space: nowrap;
	}
	.tab-btn:hover { color: var(--color-text); }
	.tab-btn.active { color: var(--color-primary); border-bottom-color: var(--color-primary); }
	.badge-count {
		background: var(--color-danger); color: #fff; border-radius: 999px;
		font-size: .7rem; padding: .1rem .45rem; font-weight: 700;
	}

	/* KPI */
	.kpi-row { display: flex; gap: 1rem; flex-wrap: wrap; }
	.kpi-card {
		flex: 1; min-width: 140px; background: var(--color-bg);
		border: 1px solid var(--color-border); border-radius: var(--radius);
		padding: 1rem 1.25rem; text-align: center;
	}
	.kpi-card.kpi-alert { border-color: var(--color-warning); background: #fffbeb; }
	.kpi-value { font-size: 2rem; font-weight: 700; color: var(--color-primary); }
	.kpi-card.kpi-alert .kpi-value { color: var(--color-warning); }
	.kpi-label { font-size: .8rem; color: var(--color-text-muted); margin-top: .2rem; }

	/* Validations */
	.pending-row {
		display: flex; justify-content: space-between; align-items: center;
		gap: 1rem; margin-bottom: .5rem; flex-wrap: wrap;
	}
	.pending-info { display: flex; flex-direction: column; gap: .15rem; }
	.pending-actions { display: flex; gap: .5rem; flex-shrink: 0; }
	.text-muted-sm { font-size: .8rem; color: var(--color-text-muted); }
	.btn-success { background: #22c55e; color: #fff; border: none; }
	.btn-success:hover:not(:disabled) { background: #16a34a; }
	.btn-danger { background: var(--color-danger); color: #fff; border: none; }
	.btn-danger:hover:not(:disabled) { background: #b91c1c; }

	/* Annuaire sections */
	.annuaire-section { margin-bottom: 2.5rem; max-width: 780px; }
	.annuaire-section-header {
		display: flex; align-items: center; justify-content: space-between;
		margin-bottom: .75rem;
	}
	.section-title {
		font-size: .85rem; font-weight: 700; text-transform: uppercase;
		letter-spacing: .06em; color: var(--color-text-muted); margin: 0;
	}

	/* Form grid */
	.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: .65rem; }
	.form-grid label { display: flex; flex-direction: column; gap: .25rem; font-size: .875rem; }
	.form-grid input, .form-grid select, .form-grid textarea {
		padding: .4rem .55rem; border: 1px solid var(--color-border);
		border-radius: var(--radius); font-size: .875rem;
		background: var(--color-bg); width: 100%; box-sizing: border-box;
	}
	.form-grid textarea { resize: vertical; }
	.input-nom { text-transform: uppercase; }

	/* Membre card */
	.membre-card {
		background: var(--color-bg-secondary, #f8f9fa);
		border: 1px solid var(--color-border);
		border-left: 3px solid var(--color-border);
		border-radius: var(--radius);
		padding: .85rem 1rem;
		margin-bottom: .6rem;
	}
	.membre-card.membre-principal { border-left-color: var(--color-accent, #C9983A); }
	.membre-card.membre-president { border-left-color: #fbbf24; }

	/* Membre card header */
	.membre-card-header {
		display: flex; justify-content: space-between; align-items: center;
		flex-wrap: wrap; gap: .4rem; margin-bottom: .55rem;
	}
	.membre-card-title { font-size: .875rem; font-weight: 600; }
	.nom-upper { text-transform: uppercase; }
	.membre-card-actions { display: flex; gap: .3rem; align-items: center; }

	/* Boutons icône */
	.btn-icon {
		width: 2rem; height: 2rem; border-radius: var(--radius);
		border: 1px solid var(--color-border); background: var(--color-bg);
		cursor: pointer; font-size: 1rem; display: flex; align-items: center;
		justify-content: center; transition: background .15s, border-color .15s;
		padding: 0;
	}
	.btn-icon:disabled { opacity: .5; cursor: not-allowed; }
	.btn-icon-save:hover:not(:disabled) { background: #dbeafe; border-color: #3b82f6; }
	.btn-icon-remove { border-color: var(--color-danger); color: var(--color-danger); }
	.btn-icon-remove:hover { background: var(--color-danger); color: #fff; }
	.btn-icon-star { border-color: var(--color-accent, #C9983A); color: var(--color-accent, #C9983A); font-size: .875rem; }
	.btn-icon-star:hover { background: var(--color-accent, #C9983A); color: #fff; }

	/* Badge principal */
	.badge-principal {
		display: inline-block; font-size: .72rem; font-weight: 700;
		background: var(--color-accent, #C9983A); color: #fff;
		border-radius: 999px; padding: .1rem .55rem;
		text-transform: uppercase; letter-spacing: .04em;
	}
	.badge-president {
		display: inline-block; font-size: .72rem; font-weight: 700;
		background: #fbbf24; color: #7c2d12;
		border-radius: 999px; padding: .1rem .55rem;
		text-transform: uppercase; letter-spacing: .04em;
	}

	/* Localisation auto */
	.localisation-info {
		font-size: .8rem; color: var(--color-primary); margin: .35rem 0 .5rem;
		padding: .25rem .5rem; background: #eff6ff;
		border-radius: var(--radius); display: inline-block;
	}

	/* Recherche inscrit */
	.user-search-wrap { margin-top: .65rem; position: relative; }
	.user-search-label { font-size: .8rem; color: var(--color-text-muted); display: flex; align-items: center; gap: .4rem; flex-wrap: wrap; }
	.user-search-input { font-size: .8rem; padding: .25rem .4rem; border: 1px solid var(--color-border); border-radius: var(--radius); background: var(--color-bg); min-width: 180px; }
	.user-suggestions {
		list-style: none; margin: .25rem 0 0; padding: 0;
		border: 1px solid var(--color-border); border-radius: var(--radius);
		background: var(--color-bg); box-shadow: 0 4px 12px rgba(0,0,0,.08);
		max-height: 220px; overflow-y: auto; z-index: 10; position: relative;
	}
	.user-suggestions li button {
		width: 100%; text-align: left; padding: .45rem .75rem;
		border: none; background: none; cursor: pointer; font-size: .85rem;
		display: flex; align-items: center; justify-content: space-between; gap: .5rem;
	}
	.user-suggestions li button:hover { background: var(--color-bg-secondary, #f8f9fa); }
	.sugg-bat { font-size: .75rem; color: var(--color-text-muted); }
	.user-no-result { font-size: .78rem; color: var(--color-text-muted); margin: .25rem 0 0; padding: .35rem .5rem; }
	.user-link-indicator { margin-top: .5rem; }
	.user-no-match { font-size: .78rem; color: var(--color-text-muted); font-style: italic; }
	.cs-role-flags {
		display: flex;
		flex-direction: column;
		gap: .35rem;
		margin-top: .65rem;
	}
	.cs-role-flag {
		display: inline-flex;
		align-items: center;
		gap: .45rem;
		font-size: .8rem;
		color: var(--color-text);
	}
	.cs-role-flag input { accent-color: var(--color-primary); }
	.user-linked {
		display: inline-flex; align-items: center; gap: .6rem; font-size: .8rem;
		color: #16a34a; background: #f0fdf4; border-radius: var(--radius);
		padding: .3rem .6rem; border: 1px solid #bbf7d0;
	}
	.btn-unlink {
		font-size: .75rem; background: none; border: none; cursor: pointer;
		color: var(--color-text-muted); text-decoration: underline; padding: 0;
	}
	.btn-unlink:hover { color: var(--color-danger); }

	/* Header inline-edit */
	.header-summary {
		display: flex; align-items: center; gap: .5rem; flex-wrap: wrap;
		font-size: .875rem; color: var(--color-text-muted);
		margin-bottom: 1rem; padding: .4rem 0;
	}
	.header-edit-actions { display: flex; gap: .5rem; align-items: center; padding-top: .25rem; }

	/* Mode replié */
	.membre-summary { display: flex; flex-wrap: wrap; align-items: center; gap: .4rem; margin-top: .25rem; }
	.summary-loc { font-size: .8rem; color: var(--color-text-muted); }
	.summary-fonction { font-size: .8rem; font-weight: 600; color: var(--color-text); }
	.summary-role-badge {
		font-size: .74rem;
		font-weight: 600;
		color: #0f766e;
		background: #ecfeff;
		border: 1px solid #99f6e4;
		border-radius: 999px;
		padding: .12rem .48rem;
	}
	.summary-role-badge-president {
		color: #7c2d12;
		background: #fffbeb;
		border-color: #fcd34d;
	}
	.btn-icon-edit { border-color: var(--color-primary); color: var(--color-primary); }
	.btn-icon-edit:hover { background: var(--color-primary); color: #fff; }
	.btn-icon-move { border-color: var(--color-border); color: var(--color-text-muted); font-size: .85rem; }
	.btn-icon-move:hover:not(:disabled) { background: var(--color-bg-secondary, #f8f9fa); color: var(--color-text); }
	.btn-icon-move:disabled { opacity: .25; cursor: not-allowed; }

	/* Tickets CS */
	.tk-expand { margin-bottom: .3rem; border-left: 4px solid var(--color-border); border-radius: var(--radius); overflow: visible; position: relative; background: var(--color-surface); transition: border-left-color .12s; }
	.tk-expand:hover, .tk-expand.expanded { border-left-color: var(--color-primary); }
	.tk-expand.urgent { border-left-color: var(--color-danger); }
	.tk-row { display: flex; align-items: center; gap: .6rem; padding: .6rem .9rem; cursor: pointer; user-select: none; transition: background .12s; }
	.tk-row:hover { background: var(--color-bg); }
	.tk-main { display: flex; flex-direction: column; gap: .25rem; flex: 1; min-width: 0; overflow: hidden; }
	.tk-row-inner { display: flex; align-items: center; gap: .4rem; flex: 1; min-width: 0; overflow: hidden; }
	.tk-cat { flex-shrink: 0; font-size: .95rem; }
	.tk-row-titre { font-size: .9rem; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.tk-row-right { display: flex; align-items: center; gap: .3rem; flex-shrink: 0; }
	.tk-row-date { font-size: .78rem; color: var(--color-text-muted); margin-right: .3rem; white-space: nowrap; }
	.tk-ticket-meta { display: flex; gap: .6rem; flex-wrap: wrap; font-size: .78rem; color: var(--color-text-muted); }
	.tk-preview { padding: .4rem 1rem .6rem; font-size: .875rem; line-height: 1.6; color: var(--color-text-muted); }
	.tk-preview :global(p) { margin: 0 0 .4em; }
	.tk-body { padding: .75rem 1rem 1rem; border-top: 1px solid var(--color-border); }
	.tk-context-meta { display: flex; gap: .5rem; flex-wrap: wrap; margin-bottom: .65rem; }
	.context-chip {
		display: inline-flex; align-items: center; gap: .25rem;
		padding: .2rem .55rem; border-radius: 999px;
		background: var(--color-bg); border: 1px solid var(--color-border);
		font-size: .78rem; color: var(--color-text-muted);
	}
	.chevron { font-size: 1.1rem; color: var(--color-text-muted); transition: transform .15s; display: inline-block; line-height: 1; }
	.chevron.open { transform: rotate(90deg); }
	.rich-content { font-size: .85rem; line-height: 1.6; color: var(--color-text); }
	.rich-content :global(p) { margin: 0 0 .5em; }
	.evol-list { margin-top: .9rem; border: 1px solid var(--color-border); border-radius: 6px; overflow: hidden; }
	.evol-sep { margin: 0; border: none; border-top: 1px solid var(--color-border); }
	.evol-item { display: flex; gap: .5rem; padding: .5rem .75rem; font-size: .82rem; }
	.evol-icon { flex-shrink: 0; font-size: .9rem; margin-top: .1rem; }
	.evol-body { display: flex; flex-direction: column; gap: .15rem; }
	.evol-meta { font-size: .75rem; color: var(--color-text-muted); }
	.evol-text { color: var(--color-text); line-height: 1.5; }
	.evol-etat { background: #f0f9ff; }
	.evol-reponse { background: #f0fdf4; }
	.evol-commentaire { background: #fafafa; }
	.evol-content { margin-top: .2rem; color: var(--color-text); line-height: 1.6; font-size: .85rem; }
	.evol-content :global(p) { margin: 0 0 .3em; }
	.evol-form { padding: .25rem 0; }
	.pill { padding: .3rem .85rem; border-radius: 999px; border: 1.5px solid var(--color-border); background: var(--color-bg); font-size: .85rem; cursor: pointer; transition: background .15s, border-color .15s, color .15s; white-space: nowrap; line-height: 1.6; }
	.pill:hover { border-color: var(--color-primary); color: var(--color-primary); }
	.pill-active { background: var(--color-primary); border-color: var(--color-primary); color: #fff; }
	.field { display: flex; flex-direction: column; gap: .25rem; font-size: .875rem; }
	.field label { font-weight: 500; font-size: .85rem; }
	.field select, .field textarea { padding: .4rem .55rem; border: 1px solid var(--color-border); border-radius: var(--radius); font-size: .875rem; background: var(--color-bg); }
	:global(.badge-orange) { background: #fef3c7; color: #92400e; }
	:global(.badge-red) { background: #fee2e2; color: #991b1b; }
	:global(.badge-purple) { background: #ede9fe; color: #5b21b6; }

	/* Reporting */
	.reporting-panel { display: flex; flex-direction: column; gap: 1rem; }
	.reporting-toolbar {
		display: flex; justify-content: space-between; gap: .75rem;
		align-items: center; flex-wrap: wrap;
	}
	.reporting-switch, .reporting-actions { display: flex; gap: .5rem; flex-wrap: wrap; }
	.reporting-print-header { display: none; }
	.report-card {
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: 1rem 1.1rem;
	}
	.report-card h3 { font-size: 1rem; font-weight: 700; margin: 0 0 .35rem; }
	.report-intro { font-size: .86rem; color: var(--color-text-muted); margin-bottom: .85rem; }
	.report-grid-2 { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }
	.report-grid-2-wide { grid-template-columns: minmax(0, 2fr) minmax(280px, 1fr); }
	.report-table-wrap { overflow-x: auto; }
	.report-table { width: 100%; border-collapse: collapse; font-size: .86rem; }
	.report-table th, .report-table td { padding: .65rem .7rem; border-bottom: 1px solid var(--color-border); vertical-align: top; text-align: left; }
	.report-table th { font-size: .76rem; text-transform: uppercase; letter-spacing: .05em; color: var(--color-text-muted); }
	.report-table.compact td, .report-table.compact th { padding: .55rem .6rem; }
	.report-event-title { display: block; margin-bottom: .25rem; }
	.report-event-desc { color: var(--color-text); }
	.report-event-desc :global(p:last-child) { margin-bottom: 0; }
	.clamp-5 { display: -webkit-box; line-clamp: 5; -webkit-line-clamp: 5; -webkit-box-orient: vertical; overflow: hidden; }

	@media (max-width: 900px) {
		.report-grid-2, .report-grid-2-wide { grid-template-columns: 1fr; }
	}

	@media print {
		.no-print { display: none !important; }
		.reporting-print-header { display: block; margin-bottom: 1rem; }
		.reporting-print-header h2 { font-size: 1.2rem; margin: 0 0 .2rem; }
		.reporting-print-header p { font-size: .82rem; color: #666; margin: 0; }
		.report-card { box-shadow: none; break-inside: avoid; }
		.report-table th, .report-table td { font-size: .78rem; }
		.reporting-panel { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
		.kpi-card { border: 1px solid #ccc !important; background: #fff !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
		.kpi-card.kpi-alert { border-color: #d97706 !important; background: #fffbeb !important; }
		.kpi-value { color: #1e3a5f !important; }
		.kpi-card.kpi-alert .kpi-value { color: #d97706 !important; }
		.frise-bar-track {
			-webkit-print-color-adjust: exact; print-color-adjust: exact;
			background: repeating-linear-gradient(90deg, transparent, transparent calc(100% / 12 - 1px), #ddd calc(100% / 12 - 1px), #ddd calc(100% / 12)) !important;
		}
		.frise-preavis-zone { -webkit-print-color-adjust: exact; print-color-adjust: exact; opacity: .5; }
		.frise-marker { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
		.frise-row-v2 { border-bottom-color: #ddd !important; }
		.frise-months { color: #666 !important; border-bottom-color: #ddd !important; }
		.frise-compact-item { background: #f8f9fa !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
		.frise-row-dates { color: #666 !important; }
		.frise-marker-label { color: #666 !important; }
		.frise-legend { color: #666 !important; }
		.frise-legend-dot { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
		.frise-stars { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
		.frise-stars-bad { color: #dc2626 !important; }
		.frise-stars-ok { color: #f59e0b !important; }
		.frise-stars-good { color: #16a34a !important; }
		.badge { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
		.report-card { background: #fff !important; border-color: #ddd !important; }
		.report-intro { color: #666 !important; }
	}

	:global(body.print-reporting .page-header),
	:global(body.print-reporting .page-subtitle),
	:global(body.print-reporting .tabs),
	:global(body.print-reporting .tab-descriptif),
	:global(body.print-reporting .no-print) {
		display: none !important;
	}
	:global(body.print-reporting .sidebar),
	:global(body.print-reporting .mobile-topbar),
	:global(body.print-reporting .app-footer) {
		display: none !important;
	}
	:global(body.print-reporting .app-content) {
		margin-left: 0 !important;
		max-width: 100% !important;
	}
	:global(body.print-reporting .reporting-print-header) {
		display: block !important;
	}

	/* ── Renouvellements : frise contrats ─────────────────────────── */
	.frise-container { margin-top: .5rem; }
	.frise-months {
		display: grid; grid-template-columns: repeat(12, 1fr);
		font-size: .7rem; color: var(--color-text-muted); text-transform: uppercase;
		letter-spacing: .03em; margin-bottom: .35rem; text-align: center;
		border-bottom: 1px solid var(--color-border); padding-bottom: .3rem;
	}
	.frise-row-v2 {
		padding: .5rem 0 1.2rem;
		border-bottom: 1px solid color-mix(in srgb, var(--color-border) 50%, transparent);
	}
	.frise-row-header {
		display: flex; justify-content: space-between; align-items: baseline;
		flex-wrap: wrap; gap: .15rem .8rem; margin-bottom: .3rem;
	}
	.frise-row-title {
		display: flex; align-items: baseline; gap: .4rem; font-size: .82rem;
		min-width: 0; flex-wrap: wrap;
	}
	.frise-row-badges {
		display: flex; align-items: center; gap: .4rem; flex-wrap: wrap;
	}
	.frise-row-dates {
		font-size: .72rem; color: var(--color-text-muted); white-space: nowrap;
	}
	.frise-bar-track {
		position: relative; height: 28px;
		background: repeating-linear-gradient(
			90deg,
			transparent, transparent calc(100% / 12 - 1px),
			var(--color-border) calc(100% / 12 - 1px), var(--color-border) calc(100% / 12)
		);
		border-radius: 4px;
	}

	/* Compact list for future/unknown contracts */
	.frise-compact-list { display: flex; flex-direction: column; gap: .4rem; }
	.frise-compact-item {
		display: flex; justify-content: space-between; align-items: center;
		gap: .5rem; padding: .4rem .6rem; border-radius: 6px; font-size: .82rem;
		background: color-mix(in srgb, var(--color-bg-card) 90%, var(--color-border));
		flex-wrap: wrap;
	}
	.frise-compact-info { display: flex; align-items: baseline; gap: .4rem; min-width: 0; flex-wrap: wrap; }
	.frise-compact-meta { display: flex; align-items: center; gap: .6rem; font-size: .75rem; color: var(--color-text-muted); flex-wrap: wrap; }

	/* Stars rating display */
	.frise-stars {
		font-size: .78rem; white-space: nowrap; letter-spacing: -.02em;
	}
	.frise-stars-bad { color: #dc2626; }
	.frise-stars-ok { color: #f59e0b; }
	.frise-stars-good { color: #16a34a; }
	.frise-preavis-zone {
		position: absolute; top: 2px; bottom: 2px; border-radius: 3px; opacity: .35;
		background: repeating-linear-gradient(
			-45deg, transparent, transparent 4px, currentColor 4px, currentColor 6px
		);
	}
	.frise-preavis-zone.frise-urgence-expire,
	.frise-preavis-zone.frise-urgence-preavis { color: #dc2626; }
	.frise-preavis-zone.frise-urgence-annee { color: #f59e0b; }
	.frise-preavis-zone.frise-urgence-futur { color: #3b82f6; }
	.frise-preavis-zone.frise-urgence-reconduit { color: #8b5cf6; }

	.frise-marker {
		position: absolute; top: 0; bottom: 0; width: 3px; transform: translateX(-50%);
		border-radius: 2px;
	}
	.frise-marker-expire, .frise-marker-preavis { background: #dc2626; }
	.frise-marker-annee { background: #f59e0b; }
	.frise-marker-futur { background: #3b82f6; }
	.frise-marker-reconduit { background: #8b5cf6; }

	.frise-marker-label {
		position: absolute; bottom: -16px; left: 50%; transform: translateX(-50%);
		font-size: .65rem; color: var(--color-text-muted); white-space: nowrap;
	}
	.frise-legend {
		display: flex; gap: 1.2rem; font-size: .78rem; color: var(--color-text-muted);
		margin-top: 1.2rem; flex-wrap: wrap;
	}
	.frise-legend span { display: flex; align-items: center; gap: .35rem; }
	.frise-legend-dot { display: inline-block; width: 10px; height: 10px; border-radius: 2px; }
	.frise-legend-hatch { font-style: italic; }

	/* ── Renouvellements : audits par année ───────────────────────── */
	.audit-year-group { margin-bottom: 1.2rem; }
	.audit-year-group:last-child { margin-bottom: 0; }
	.audit-year-title {
		font-size: .95rem; font-weight: 700; margin: 0 0 .5rem;
		display: flex; align-items: center; gap: .5rem;
	}
	.audit-year-current { border-left: 3px solid #f59e0b; padding-left: .75rem; }

	@media (max-width: 700px) {
		.frise-row-header { flex-direction: column; }
		.frise-bar-track { min-height: 24px; }
		.frise-months { font-size: .6rem; }
		.frise-compact-item { flex-direction: column; align-items: flex-start; }
	}

	@media print {
		.frise-container { break-inside: avoid; }
		.audit-year-group { break-inside: avoid; }
	}
</style>
