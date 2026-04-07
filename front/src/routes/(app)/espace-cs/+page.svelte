<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import { onMount, tick } from 'svelte';
	import { isCS } from '$lib/stores/auth';
	import { goto } from '$app/navigation';
	import { admin as adminApi, annuaireAdmin, lots as lotsApi, api, tickets as ticketsApi, prestataires as prestApi, calendrier as calApi, ApiError, type Ticket, type TicketEvolution } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { getPageConfig, configStore, siteNomStore } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';

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

	// -- Onglet -------------------------------------------------------------
	let onglet: 'validations' | 'tickets' | 'reporting' | 'annuaire' = 'validations';

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
	let reportView: 'kanban' | 'tickets' | 'devis' | 'prestataires' = 'kanban';
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

	function fmtDate(d: string) { return new Date(d).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' }); }
	function fmtDatetime(d: string) { return new Date(d).toLocaleString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }); }
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
	function csvCell(value: unknown) {
		const str = String(value ?? '').replace(/"/g, '""');
		return `"${str}"`;
	}
	function downloadCsv(filename: string, rows: Array<Record<string, unknown>>) {
		if (typeof window === 'undefined') return;
		if (!rows.length) {
			toast('info', 'Aucune donnée à exporter');
			return;
		}
		const headers = Object.keys(rows[0]);
		const csv = [headers.map(csvCell).join(';'), ...rows.map((row) => headers.map((h) => csvCell(row[h])).join(';'))].join('\n');
		const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
		const url = URL.createObjectURL(blob);
		const link = document.createElement('a');
		link.href = url;
		link.download = filename;
		link.click();
		URL.revokeObjectURL(url);
	}
	async function printReporting(title: string) {
		if (typeof window === 'undefined' || typeof document === 'undefined') return;
		reportPrintTitle = title;
		document.body.classList.add('print-reporting');
		await tick();
		window.print();
		setTimeout(() => document.body.classList.remove('print-reporting'), 250);
	}
	function exportCurrentReporting() {
		if (reportView === 'kanban') {
			downloadCsv('reporting-kanban-ag-cs-syndic.csv', reportKanbanEvents.map((ev) => ({
				Titre: ev.titre,
				Type: TYPE_LABELS[ev.type] ?? ev.type,
				Colonne: KANBAN_LABELS[ev.statut_kanban ?? ''] ?? ev.statut_kanban ?? '',
				Perimetre: ev.perimetre,
				Batiment: ev.batiment_id ? `Bât. ${ev.batiment_id}` : '',
				Prestataire: ev.prestataire_nom ?? '',
				Auteur: ev.auteur_nom ?? '',
				Cree_le: fmtDate(ev.cree_le),
				Anciennete_jours: daysSince(ev.cree_le),
				Derniere_maj: fmtDate(ev.mis_a_jour_le ?? ev.cree_le),
			})));
			return;
		}
		if (reportView === 'tickets') {
			downloadCsv('reporting-analyse-tickets.csv', reportTicketSource.map((t) => ({
				Numero: t.numero,
				Titre: t.titre,
				Categorie: t.categorie,
				Statut: t.statut,
				Priorite: t.priorite,
				Batiment: ticketScope(t),
				Demandeur: t.auteur_nom ?? '',
				Cree_le: fmtDate(t.cree_le),
				Anciennete_jours: daysSince(t.cree_le),
			})));
			return;
		}
		if (reportView === 'devis') {
			downloadCsv('reporting-devis-interventions.csv', reportDevisActifs.map((d) => ({
				Titre: d.titre,
				Prestataire: reportPrestataireName(d.prestataire_id),
				Perimetre: d.perimetre,
				Batiment: d.batiment_id ? `Bât. ${d.batiment_id}` : '',
				Date_prestation: d.date_prestation ? fmtDate(d.date_prestation) : 'Non planifiée',
				Montant: fmtMoney(d.montant_estime),
				Statut: REPORT_DEVIS_LABELS[d.statut] ?? d.statut,
				Recurrence: d.frequence_type && d.frequence_valeur ? `${d.frequence_valeur} ${d.frequence_type}` : '',
			})));
			return;
		}
		if (reportView === 'prestataires') {
			downloadCsv('reporting-prestataires.csv', reportPrestataires.map((p) => {
				const pDevis = reportDevisList.filter(d => d.prestataire_id === p.id);
				return {
					Nom: p.nom,
					Specialite: p.specialite ?? '',
					Type: p.type_prestataire ?? '',
					Devis_actifs: pDevis.filter(d => d.statut === 'en_attente' || d.statut === 'accepte').length,
					Realises: pDevis.filter(d => d.statut === 'realise').length,
				};
			}));
			return;
		}
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
		};
		void printReporting(titles[reportView]);
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

	async function loadTickets() {
		if (tkLoaded) return;
		tkLoading = true;
		try {
			tkList = await ticketsApi.list();
			tkLoaded = true;
		} catch { toast('error', 'Erreur chargement tickets'); }
		finally { tkLoading = false; }
	}

	async function loadReporting() {
		if (reportingLoaded) return;
		reportingLoading = true;
		try {
			await loadTickets();
			const [devis, prestataires, evenements] = await Promise.all([prestApi.devis(), prestApi.list(), calApi.list()]);
			reportDevisList = devis as ReportDevis[];
			reportPrestataires = prestataires as ReportPrestataire[];
			reportEvenements = evenements as ReportEvenement[];
			reportingLoaded = true;
		} catch (e: any) {
			toast('error', apiMessage(e, 'Erreur chargement reporting'));
		} finally {
			reportingLoading = false;
		}
	}

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
							<span class="text-muted-sm">{new Date(user.cree_le).toLocaleDateString('fr-FR')}</span>
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
							<span class="text-muted-sm">{new Date(cmd.cree_le).toLocaleDateString('fr-FR')}</span>
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
			</div>
			<div class="reporting-actions">
				<button class="btn btn-sm btn-outline" on:click={exportCurrentReporting}>
					&#x2B07; Exporter CSV
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
					<span>{agAnnee ? `AG ${agAnnee}` : 'Année AG non renseignée'}{agDate ? ` · ${new Date(agDate).toLocaleDateString('fr-FR')}` : ''}</span>
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
	}

	:global(body.print-reporting .page-header),
	:global(body.print-reporting .page-subtitle),
	:global(body.print-reporting .tabs),
	:global(body.print-reporting .tab-descriptif),
	:global(body.print-reporting .no-print) {
		display: none !important;
	}
	:global(body.print-reporting .reporting-print-header) {
		display: block !important;
	}
</style>
