<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
import { onMount } from 'svelte';
	import PerimetrePicker from '$lib/components/PerimetrePicker.svelte';
	import { calendrier as calApi, publications as pubsApi, prestataires as prestApi, ApiError, type Publication } from '$lib/api';
	import { isCS, isAdmin, currentUser } from '$lib/stores/auth';
	import RichEditor from '$lib/components/RichEditor.svelte';
	import { toast } from '$lib/components/Toast.svelte';
	import { getPageConfig, configStore, siteNomStore } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';

	$: _pc = getPageConfig($configStore, 'calendrier', { titre: 'Calendrier', navLabel: 'Calendrier', icone: 'calendar-days', descriptif: 'Agenda des événements et interventions de la résidence.', onglets: { liste: { label: '\u{1F4CB} Liste', descriptif: 'Vue chronologique des événements à venir.' }, kanban: { label: '\u{1F5C3}️ Kanban', descriptif: 'Organisation visuelle des événements par statut.' }, archives: { label: '\u{1F4C1} Archives', descriptif: 'Actualités et événements archivés.' } } });
	$: _siteNom = $siteNomStore;

	let evenements: any[] = [];
	let prestataires: any[] = [];
	let loading = true;
	let onglet: 'liste' | 'kanban' | 'archives' = 'liste';
	let filtreType = '';

	let archivedPubs: Publication[] = [];
	let archivedPubsLoaded = false;
	let archivedDevis: any[] = [];
	let archivedDevisLoaded = false;
	let calDevis: any[] = [];

	const _now = new Date();
	let expandedArchiveYears = new Set<number>();

	// Délai en ms avant qu'un événement expiré bascule en Archives (configurable en admin, défaut 48 h)
	$: archivageDelaiMs = (parseInt($configStore?.['archivage_delai_heures'] ?? '48') || 48) * 3600000;

	function isExpired(ev: any, delaiMs: number = 48 * 3600000): boolean {
		const endDate = new Date(ev.fin ?? ev.debut);
		return endDate.getTime() + delaiMs < Date.now();
	}

	let showForm = false;
	let editId: number | null = null;
	let expandedEvId: number | null = null;
	let expandedKanbanId: number | null = null;

	let form = {
		titre: '',
		description: '',
		type: 'autre',
		lieu: '',
		debut: '',
		debut_heure: '',
		fin: '',
		statut_kanban: '',
		prestataire_id: '',
		frequence_type: '',
		frequence_valeur: '',
		affichable: false,
	};
	let formPerimetreCible: string[] = ['résidence'];
	let submitting = false;

	const types = [
		{ val: 'travaux', label: '\u{1F528} Travaux' },
		{ val: 'coupure', label: '⚡ Coupure' },
		{ val: 'ag', label: '\u{1F3DB}️ AG' },
		{ val: 'maintenance', label: '\u{1F527} Maintenance' },
		{ val: 'maintenance_recurrente', label: '\u{1F504} Maintenance récurrente' },
		{ val: 'autre', label: '\u{1F4CC} Autre' },
	];

	function typeLabel(t: string) {
		return types.find(x => x.val === t)?.label ?? t;
	}

	function prestataireNom(prestataireId: number | null | undefined) {
		return prestataires.find(p => p.id === prestataireId)?.nom ?? '';
	}

	function kanbanStatutPourDevis(statut: string | null | undefined) {
		const map: Record<string, string> = {
			en_attente: 'syndic',
			accepte: 'fournisseur',
			realise: 'termine',
			refuse: 'annule',
		};
		return map[statut ?? ''] ?? 'syndic';
	}

	function perimètreLabel(p: string) {
		const map: Record<string, string> = {
			'résidence': 'Copropriété entière',
			'bat:1': 'Bât. 1', 'bat:2': 'Bât. 2', 'bat:3': 'Bât. 3', 'bat:4': 'Bât. 4',
			parking: 'Parking', cave: 'Cave', aful: 'AFUL',
		};
		return p.split(',').map(s => map[s.trim()] ?? s).join(' · ');
	}

	onMount(async () => {
		try {
			evenements = await calApi.list();
			const expiredYears = [...new Set(evenements.filter(e => isExpired(e, archivageDelaiMs)).map(e => new Date(e.fin ?? e.debut).getFullYear()))].sort((a, b) => b - a);
			if (expiredYears.length > 0) expandedArchiveYears = new Set([expiredYears[0]]);
		} catch {
			toast('error', 'Erreur de chargement');
		} finally {
			loading = false;
		}
	});

	// Chargement des données prestataires après que le store utilisateur soit disponible
	// (évite les appels 403 pour les non-CS/admin, et corrige la course entre onMount et le chargement du store)
	let _prestLoaded = false;
	$: if ($currentUser && !_prestLoaded) {
		_prestLoaded = true;
		// prestApi.list() restreint CS/admin ; prestApi.devis() ouvert à tous (backend filtre sur affichable pour non-CS)
		const prestListPromise = ($isCS || $isAdmin) ? prestApi.list() : Promise.resolve([]);
		Promise.all([prestListPromise, prestApi.devis()])
			.then(([p, d]) => { prestataires = p; calDevis = d; })
			.catch(() => {});
	}

	// AG visibles uniquement par propriétaires, CS et admin
	$: canSeeAG = ($currentUser?.roles ?? []).some((r: string) => ['propriétaire', 'conseil_syndical', 'admin'].includes(r));
	$: visibleTypes = (canSeeAG ? types : types.filter(t => t.val !== 'ag')).filter(t => t.val !== 'maintenance_recurrente');
	$: filtered = (() => {
		let evs = canSeeAG ? evenements : evenements.filter(e => e.type !== 'ag');
		// Un événement avec suivi kanban actif (non terminé / non annulé) reste visible en Liste
		// même si sa date de début est passée — il disparaîtra seulement à la clôture du kanban.
		evs = evs.filter(e => {
			if (e.archivee) return false;
			const kanbanActif = e.statut_kanban && !['termine', 'annule'].includes(e.statut_kanban);
			return !isExpired(e, archivageDelaiMs) || kanbanActif;
		});
		// Les maintenances récurrentes restent hors vue Liste.
		// Exception métier: les prestations ponctuelles (non récurrentes) avec workflow restent visibles en Liste ET Kanban.
		evs = evs.filter(e => {
			if (e.type === 'maintenance_recurrente') return false;
			if (!e.statut_kanban) return true;
			// Tout événement marqué affichable est visible en liste (cohérence avec "Événements récents" du tableau de bord)
			if (e.affichable === true) return true;
			// CS/admin : les événements kanban avec prestataire (workflow non-public) restent visibles en liste
			if ($isCS || $isAdmin) return !!e.prestataire_id;
			return false;
		});
		return filtreType ? evs.filter(e => e.type === filtreType) : evs;
	})();
	$: prestationsPonctuellesListe = calDevis
		.filter((d: any) => !['realise', 'refuse'].includes(d.statut) && !d.frequence_type && !d.frequence_valeur)
		.map((d: any) => {
			const rawDate = d.date_prestation ?? d.cree_le ?? new Date().toISOString();
			const debut = typeof rawDate === 'string' && rawDate.includes('T') ? rawDate : `${rawDate}T09:00`;
			const perimetre = d.perimetre ?? (d.batiment_id ? `bat:${d.batiment_id}` : 'résidence');
			return {
				id: -(100000 + Number(d.id)),
				_source: 'devis_ponctuel',
				type: 'maintenance',
				titre: d.titre,
				debut,
				fin: null,
				statut_kanban: kanbanStatutPourDevis(d.statut),
				archivee: false,
				perimetre,
				prestataire_id: d.prestataire_id ?? null,
				prestataire_nom: prestataireNom(d.prestataire_id),
				description: d.notes ?? null,
				cree_le: d.cree_le ?? debut,
				mis_a_jour_le: d.mis_a_jour_le ?? null,
				auteur_nom: d.auteur_nom ?? null,
			};
		});
	$: prestationsPonctuellesKanban = calDevis
		.filter((d: any) => !d.frequence_type && !d.frequence_valeur)
		.map((d: any) => {
			const rawDate = d.date_prestation ?? d.cree_le ?? new Date().toISOString();
			const debut = typeof rawDate === 'string' && rawDate.includes('T') ? rawDate : `${rawDate}T09:00`;
			const perimetre = d.perimetre ?? (d.batiment_id ? `bat:${d.batiment_id}` : 'résidence');
			return {
				id: -(100000 + Number(d.id)),
				_source: 'devis_ponctuel',
				type: 'maintenance',
				titre: d.titre,
				debut,
				fin: null,
				statut_kanban: kanbanStatutPourDevis(d.statut),
				archivee: false,
				perimetre,
				prestataire_id: d.prestataire_id ?? null,
				prestataire_nom: prestataireNom(d.prestataire_id),
				description: d.notes ?? null,
				cree_le: d.cree_le ?? debut,
				mis_a_jour_le: d.mis_a_jour_le ?? null,
				auteur_nom: d.auteur_nom ?? null,
			};
		});

	$: allArchiveEvs = (() => {
		let evs = canSeeAG ? evenements : evenements.filter(e => e.type !== 'ag');
		evs = evs.filter(e => isExpired(e, archivageDelaiMs) || e.archivee);
		// Règle métier : un événement avec suivi kanban ne peut figurer en archives
		// que s'il est Terminé ou Annulé. Les statuts actifs (ag, cs, syndic, fournisseur)
		// restent dans la vue Kanban jusqu'à leur clôture.
		evs = evs.filter(e => !e.statut_kanban || ['termine', 'annule'].includes(e.statut_kanban));
		// Maintenances récurrentes : uniquement les terminées (pas les annulées)
		evs = evs.filter(e => e.type !== 'maintenance_recurrente' || e.statut_kanban === 'termine');
		return filtreType ? evs.filter(e => e.type === filtreType) : evs;
	})();

	// Fusion événements + publications + prestations archivés en une seule liste
	$: allArchiveItems = (() => {
		const items: any[] = [
			...allArchiveEvs.map(ev => ({ ...ev, _kind: 'ev', _date: ev.fin ?? ev.debut })),
			...archivedPubs.map(pub => ({ ...pub, _kind: 'pub', _date: pub.mis_a_jour_le ?? pub.cree_le })),
			...archivedDevis.map(d => ({ ...d, _kind: 'devis', _date: d.date_prestation ?? d.cree_le ?? new Date().toISOString() })),
		];
		items.sort((a, b) => new Date(b._date).getTime() - new Date(a._date).getTime());
		return items;
	})();

	$: archiveByYear = (() => {
		const map = new Map<number, any[]>();
		for (const item of allArchiveItems) {
			const y = new Date(item._date).getFullYear();
			if (!map.has(y)) map.set(y, []);
			map.get(y)!.push(item);
		}
		return [...map.entries()].sort((a, b) => b[0] - a[0]).map(([year, items]) => {
			const monthMap = new Map<string, any[]>();
			for (const item of items) {
				const key = new Date(item._date).toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' });
				if (!monthMap.has(key)) monthMap.set(key, []);
				monthMap.get(key)!.push(item);
			}
			return [year, [...monthMap.entries()]] as [number, [string, any[]][]];
		});
	})();

	function resetForm() {
		form = { titre: '', description: '', type: 'autre', lieu: '', debut: _now.toISOString().slice(0, 10), debut_heure: '', fin: '', statut_kanban: '', prestataire_id: '', frequence_type: '', frequence_valeur: '', affichable: false };
		formPerimetreCible = ['résidence'];
		editId = null;
	}

	function startEdit(ev: any) {
		form = {
			titre: ev.titre, description: ev.description ?? '', type: ev.type,
			lieu: ev.lieu ?? '', debut: ev.debut?.slice(0, 10) ?? '',
			debut_heure: ev.debut?.slice(11, 16) ?? '',
			fin: ev.fin?.slice(0, 16) ?? '',
			statut_kanban: ev.statut_kanban ?? '',
			prestataire_id: ev.prestataire_id ? String(ev.prestataire_id) : '',
			frequence_type: ev.frequence_type ?? '',
			frequence_valeur: ev.frequence_valeur ? String(ev.frequence_valeur) : '',
			affichable: ev.affichable ?? true,
		};
		const p = ev.perimetre ?? 'résidence';
		formPerimetreCible = p === 'résidence' ? ['résidence'] : p.split(',').filter(Boolean);
		editId = ev.id;
		showForm = true;
	}

	async function save() {
		if (!form.titre || !form.debut) { toast('error', 'Titre et date de début obligatoires'); return; }
		submitting = true;
		const perimetre = formPerimetreCible.length === 1 && formPerimetreCible[0] === 'résidence' ? 'résidence' : formPerimetreCible.join(',');
		const { debut_heure, frequence_type: ft, frequence_valeur: fv, ...formData } = form;
		const payload = {
			...formData,
			perimetre,
			batiment_id: null,
			debut: form.debut + (form.debut_heure ? 'T' + form.debut_heure : 'T00:00'),
			fin: form.fin || null,
			lieu: form.lieu.trim() || null,
			description: form.description || null,
			statut_kanban: form.statut_kanban || null,
			prestataire_id: form.prestataire_id ? Number(form.prestataire_id) : null,
			frequence_type: ft || null,
			frequence_valeur: fv ? Number(fv) : null,
			affichable: form.affichable,
		};
		try {
			if (editId) {
				await calApi.update(editId, payload);
			} else {
				await calApi.create(payload);
			}
			evenements = await calApi.list();
			showForm = false;
			resetForm();
			toast('success', editId ? 'Événement modifié' : 'Événement créé');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			submitting = false;
		}
	}

	async function archiveEv(id: number) {
		if (!confirm('Archiver cet événement ?')) return;
		try {
			await calApi.archive(id);
			evenements = evenements.map(e => e.id === id ? { ...e, archivee: true } : e);
			toast('success', 'Événement archivé');
		} catch { toast('error', 'Erreur'); }
	}

	async function deleteEv(id: number) {
		if (!confirm('Supprimer définitivement cet événement ? Cette action est irréversible.')) return;
		try {
			await calApi.delete(id);
			evenements = evenements.filter(e => e.id !== id);
			toast('success', 'Événement supprimé définitivement');
		} catch { toast('error', 'Erreur'); }
	}

	async function loadArchivedPubs() {
		if (archivedPubsLoaded) return;
		try {
			archivedPubs = await pubsApi.list(true);
		} catch { /* silencieux */ }
		archivedPubsLoaded = true;
	}

	async function deleteArchivedPub(pub: Publication) {
		if (!confirm(`Supprimer définitivement « ${pub.titre} » ? Cette action est irréversible.`)) return;
		try {
			await pubsApi.delete(pub.id);
			archivedPubs = archivedPubs.filter(p => p.id !== pub.id);
			toast('success', 'Publication supprimée définitivement');
		} catch { toast('error', 'Erreur'); }
	}

	async function loadArchivedDevis() {
		if (archivedDevisLoaded) return;
		archivedDevisLoaded = true;
		try {
			const all = await prestApi.devis();
			archivedDevis = all.filter((d: any) => d.statut === 'realise');
		} catch { /* silencieux */ }
	}

	$: if (onglet === 'archives') { loadArchivedPubs(); loadArchivedDevis(); }

	function formatDate(d: string) {
		return new Date(d).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' });
	}

	// Regroupement pour la vue liste :
	// - années passées → clé "2025" (regroupement annuel)
	// - année courante → clé "mars 2026" (regroupement mensuel, comme avant)
	function groupByYear(evs: any[]) {
		const currentYear = new Date().getFullYear();
		const result: [string, any[]][] = [];
		const indexMap = new Map<string, number>();
		const sorted = [...evs].sort((a, b) => new Date(a.debut).getTime() - new Date(b.debut).getTime());
		for (const ev of sorted) {
			const d = new Date(ev.debut);
			const year = d.getFullYear();
			const key = year < currentYear
				? String(year)
				: d.toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' });
			if (!indexMap.has(key)) { indexMap.set(key, result.length); result.push([key, []]); }
			result[indexMap.get(key)!][1].push(ev);
		}
		return result;
	}

	$: listItems = (() => {
		const ponctuelles = prestationsPonctuellesListe.filter((p: any) => !filtreType || p.type === filtreType);
		return [...filtered, ...ponctuelles].sort((a, b) => new Date(a.debut).getTime() - new Date(b.debut).getTime());
	})();
	$: groups = groupByYear(listItems);
	// Maintenances récurrentes trackées dans le workflow Kanban (statut_kanban actif, non archivées, non périmées)
	$: recurringMaintenances = (() => {
		if (filtreType && filtreType !== 'maintenance_recurrente') return [];
		return evenements.filter((e: any) =>
			e.type === 'maintenance_recurrente'
			&& e.statut_kanban && e.statut_kanban !== 'annule'
			&& !e.archivee && !isExpired(e, archivageDelaiMs));
	})();
	let showPeriodicSection = false;
	let openEvIds = new Set<number>();
	function toggleEvRow(id: number) {
		if (openEvIds.has(id)) openEvIds.delete(id); else openEvIds.add(id);
		openEvIds = openEvIds;
	}
	$: archivedMaintenances = evenements
		.filter((e: any) => e.type === 'maintenance_recurrente' && e.archivee)
		.sort((a: any, b: any) => new Date(b.debut).getTime() - new Date(a.debut).getTime());
	let showArchivedMaintenances = false;

	// ── Kanban ────────────────────────────────────────────────
	const KANBAN_COLS = [
		{ id: 'ag',           label: 'AG',                    color: '#8b5cf6' },
		{ id: 'cs',           label: 'CS (en cours)',         color: '#3b82f6' },
		{ id: 'syndic',       label: 'Syndic (en cours)',     color: '#f59e0b' },
		{ id: 'fournisseur',  label: 'Prestataire (en cours)', color: '#f97316' },
		{ id: 'termine',      label: 'Terminé',              color: '#22c55e' },
		{ id: 'annule',       label: 'Annulé',               color: '#9ca3af' },
	];

	const PERIMETRE_COLORS: Record<string, string> = {
		'bat:1': '#ef4444', 'bat:2': '#3b82f6', 'bat:3': '#22c55e', 'bat:4': '#f59e0b',
		parking: '#f97316', cave: '#8b5cf6', 'partie commune': '#ec4899', 'partie privative': '#6b7280',
		aful: '#0ea5e9',
	};

	const PERIMETRE_SHORT: Record<string, string> = {
		'bat:1': 'bât. 1', 'bat:2': 'bât. 2', 'bat:3': 'bât. 3', 'bat:4': 'bât. 4',
		parking: 'Parking', cave: 'Cave', 'partie commune': 'partie commune', 'partie privative': 'privatif',
		aful: 'AFUL',
	};

	// Exercice = année. Par défaut : année courante, sauf si < février → N-1
	const defaultExercice = _now.getMonth() < 1 ? _now.getFullYear() - 1 : _now.getFullYear();
	let kanbanExercice = defaultExercice;
	let kanbanBatiment = '';

	const BATIMENT_OPTIONS = [
		{ val: '', label: 'Tous les bâtiments' },
		{ val: 'bat:1', label: 'Bât. 1' },
		{ val: 'bat:2', label: 'Bât. 2' },
		{ val: 'bat:3', label: 'Bât. 3' },
		{ val: 'bat:4', label: 'Bât. 4' },
	];

	$: kanbanEvs = (() => {
		const baseEvents = evenements.filter(ev => {
			if (!ev.statut_kanban) return false;
			// Pour les non-CS/admin : masquer les événements internes (non affichables)
			// Exception : les maintenances récurrentes restent visibles (prestations planifiées)
			if (!$isCS && !$isAdmin && !ev.affichable && ev.type !== 'maintenance_recurrente') return false;
			// Maintenances prestataires archivées restent dans kanban (=> Terminé)
			if (ev.archivee && !(ev.type === 'maintenance_recurrente' && ev.statut_kanban === 'fournisseur')) return false;
			return true;
		});
		const merged = [...baseEvents, ...prestationsPonctuellesKanban];
		return merged.filter(ev => {
			const evYear = new Date(ev.debut).getFullYear();
			// Événements ponctuels d'années antérieures non clôturés : toujours affichés
			const isOverdue = ev.type !== 'maintenance_recurrente'
				&& evYear < kanbanExercice
				&& ev.statut_kanban !== 'termine'
				&& ev.statut_kanban !== 'annule';
			if (!isOverdue && evYear !== kanbanExercice) return false;
			if (kanbanBatiment) {
				const p = ev.perimetre ?? 'résidence';
				if (p !== 'résidence' && !p.split(',').some((s: string) => s.trim() === kanbanBatiment)) return false;
			}
			return true;
		});
	})();

	$: kanbanCols = KANBAN_COLS
		.filter(col => {
			// Colonne CS : réservée aux CS/admin
			if (col.id === 'cs') return $isCS || $isAdmin;
			// Colonne AG : réservée aux propriétaires, CS et admin (locataires exclus)
			if (col.id === 'ag') return canSeeAG;
			return true;
		})
		.map(col => ({
		...col,
		items: kanbanEvs.filter(ev => {
			if (ev.archivee && ev.type === 'maintenance_recurrente' && ev.statut_kanban === 'fournisseur') {
				return col.id === 'termine';
			}
			return ev.statut_kanban === col.id;
		}),
	}));

	$: kanbanExerciceOptions = (() => {
		const years = new Set<number>();
		evenements.forEach(ev => { if (ev.statut_kanban) years.add(new Date(ev.debut).getFullYear()); });
		prestationsPonctuellesKanban.forEach((p: any) => years.add(new Date(p.debut).getFullYear()));
		years.add(defaultExercice);
		return [...years].sort((a, b) => b - a);
	})();

	// Drag & drop
	let dragEvId: number | null = null;

	function onDragStart(ev: DragEvent, id: number) {
		dragEvId = id;
		if (ev.dataTransfer) {
			ev.dataTransfer.effectAllowed = 'move';
			ev.dataTransfer.setData('text/plain', String(id));
		}
	}

	function onDragOver(ev: DragEvent) {
		ev.preventDefault();
		if (ev.dataTransfer) ev.dataTransfer.dropEffect = 'move';
	}

	async function onDrop(ev: DragEvent, colId: string) {
		ev.preventDefault();
		if (dragEvId == null) return;
		const id = dragEvId;
		dragEvId = null;
		if (id <= 0) return;
		const item = evenements.find(e => e.id === id);
		if (!item || item.statut_kanban === colId) return;
		const old = item.statut_kanban;
		const shouldArchive = colId === 'termine' || colId === 'annule';
		evenements = evenements.map(e => e.id === id ? { ...e, statut_kanban: colId, archivee: shouldArchive ? true : e.archivee } : e);
		try {
			await calApi.update(id, shouldArchive ? { statut_kanban: colId, archivee: true } : { statut_kanban: colId });
		} catch {
			evenements = evenements.map(e => e.id === id ? { ...e, statut_kanban: old } : e);
			toast('error', 'Erreur lors du déplacement');
		}
	}

	function perimetreTags(p: string): { label: string; color: string }[] {
		if (!p || p === 'résidence') return [{ label: '\u{1F3D8}️ Résidence', color: '#6b7280' }];
		return p.split(',').map(s => s.trim()).filter(Boolean).map(s => ({
			label: PERIMETRE_SHORT[s] ?? s,
			color: PERIMETRE_COLORS[s] ?? '#6b7280',
		}));
	}

	function kanbanYear(ev: any): string {
		return String(new Date(ev.debut).getFullYear());
	}

	// Couleur dégradée par année : teinte HSL qui tourne de 52° par an à partir de 2024
	function yearColor(year: number): string {
		const hue = ((year - 2024) * 52 + 220) % 360;
		return `hsl(${hue},55%,32%)`;
	}

	// ── Init prestataires ────────────────────────────────────
	let initLoading = false;

	function annualFreq(type: string, val: number): number {
		if (type === 'fois_par_an') return val;
		if (type === 'mois') return Math.floor(12 / val);
		if (type === 'semaines') return Math.floor(52 / val);
		return 0;
	}

	function spreadMonth(total: number, index: number): number {
		const interval = Math.floor(12 / total);
		return 1 + index * interval;
	}

	async function initPrestataires() {
		initLoading = true;
		try {
			const [contrats, prests, tousDevis] = await Promise.all([prestApi.contrats(), prestApi.list(), prestApi.devis()]);
			const prestMap = new Map(prests.map((p: any) => [p.id, p.nom]));

			const qualifying = contrats.filter((c: any) => {
				if (!c.frequence_type || !c.frequence_valeur) return false;
				const n = annualFreq(c.frequence_type, c.frequence_valeur);
				return n > 0 && n <= 4;
			});

			const qualifyingDevis = tousDevis.filter((d: any) => {
				if (!d.frequence_type || !d.frequence_valeur) return false;
				const n = annualFreq(d.frequence_type, d.frequence_valeur);
				return n > 0 && n <= 4;
			});

			const eventsWithFreq = evenements.filter((ev: any) =>
				ev.type === 'maintenance' && ev.frequence_type && ev.frequence_valeur && ev.prestataire_id && !ev.archivee
			);

			const existingTitles = new Set(
				evenements
					.filter(ev => ev.type === 'maintenance_recurrente' && !ev.archivee && new Date(ev.debut).getFullYear() === kanbanExercice)
					.map(ev => `${ev.titre}||${new Date(ev.debut).getMonth()}`)
			);

			const toCreate: any[] = [];
			let skipped = 0;
			for (const c of qualifying) {
				const n = annualFreq(c.frequence_type, c.frequence_valeur);
				const prestNom = prestMap.get(c.prestataire_id) ?? 'Prestataire';
				const perimetre = c.batiment_id ? `bat:${c.batiment_id}` : 'résidence';
				const titre = `${prestNom} — ${c.libelle}`;
				for (let i = 0; i < n; i++) {
					const month = spreadMonth(n, i);
					const key = `${titre}||${month - 1}`;
					if (existingTitles.has(key)) { skipped++; continue; }
					toCreate.push({
						titre,
						type: 'maintenance_recurrente',
						perimetre,
						batiment_id: null,
						statut_kanban: 'fournisseur',
						prestataire_id: c.prestataire_id || null,
						debut: `${kanbanExercice}-${String(month).padStart(2, '0')}-15T09:00`,
						description: c.notes || null,
						affichable: false,
					});
				}
			}

			for (const ev of eventsWithFreq) {
				const n = annualFreq(ev.frequence_type, ev.frequence_valeur);
				if (n <= 0 || n > 4) continue;
				for (let i = 0; i < n; i++) {
					const month = spreadMonth(n, i);
					const key = `${ev.titre}||${month - 1}`;
					if (existingTitles.has(key)) { skipped++; continue; }
					toCreate.push({
						titre: ev.titre,
						type: 'maintenance_recurrente',
						perimetre: ev.perimetre ?? 'résidence',
						batiment_id: null,
						statut_kanban: 'fournisseur',
						prestataire_id: ev.prestataire_id || null,
						debut: `${kanbanExercice}-${String(month).padStart(2, '0')}-15T09:00`,
						description: ev.description || null,
						affichable: false,
					});
				}
			}

			// Source 3 : Prestations (devis) avec fréquence
			for (const d of qualifyingDevis) {
				const n = annualFreq(d.frequence_type, d.frequence_valeur);
				if (n <= 0 || n > 4) continue;
				const prestNom = prestMap.get(d.prestataire_id) ?? 'Prestataire';
				const titre = d.titre ?? `${prestNom} — Prestation`;
				for (let i = 0; i < n; i++) {
					const month = spreadMonth(n, i);
					const key = `${titre}||${month - 1}`;
					if (existingTitles.has(key)) { skipped++; continue; }
					toCreate.push({
						titre,
						type: 'maintenance_recurrente',
						perimetre: 'résidence',
						batiment_id: null,
						statut_kanban: 'fournisseur',
						prestataire_id: d.prestataire_id || null,
						debut: `${kanbanExercice}-${String(month).padStart(2, '0')}-15T09:00`,
						description: d.notes || null,
						affichable: false,
					});
				}
			}

			if (toCreate.length === 0) {
				const total = qualifying.length + eventsWithFreq.length + qualifyingDevis.length;
				toast('info', total === 0
					? 'Aucune source éligible (contrats/prestations/événements avec fréquence ≤ 4/an)'
					: `Tous les événements prestataires ${kanbanExercice} existent déjà (${skipped} trouvés)`);
				return;
			}

			const msg = skipped > 0
				? `Créer ${toCreate.length} événement(s) pour ${kanbanExercice} ?\n(${skipped} existant(s) ignorés)`
				: `Créer ${toCreate.length} événement(s) prestataire pour ${kanbanExercice} ?`;
			if (!confirm(msg)) return;

			for (const ev of toCreate) await calApi.create(ev);
			evenements = await calApi.list();
			toast('success', `${toCreate.length} événement(s) créé(s)`);
		} catch {
			toast('error', "Erreur lors de l'initialisation");
		} finally {
			initLoading = false;
		}
	}
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<div class="page-header">
	<h1 style="display:flex;align-items:center;gap:.4rem;font-size:1.4rem;font-weight:700"><Icon name={_pc.icone || 'calendar-days'} size={20} />{_pc.titre}</h1>
	{#if $isCS}
		<button class="btn btn-primary page-header-btn" on:click={() => { showForm = !showForm; if (!showForm) resetForm(); }}>
			{showForm ? '✕ Annuler' : '+ Nouvel événement'}
		</button>
	{/if}
</div>
<div class="page-subtitle">{@html safeHtml(_pc.descriptif)}</div>

<!-- Onglets -->
<div class="tabs" role="tablist" style="margin-bottom:1.5rem">
	<button role="tab" class:active={onglet === 'liste'} on:click={() => onglet = 'liste'}>{_pc.onglets?.liste?.label ?? '\u{1F4CB} Liste'}</button>
	<button role="tab" class:active={onglet === 'kanban'} on:click={() => onglet = 'kanban'}>{_pc.onglets?.kanban?.label ?? '\u{1F5C3}️ Kanban'}</button>
	<button role="tab" class:active={onglet === 'archives'} on:click={() => onglet = 'archives'}>{_pc.onglets?.archives?.label ?? '\u{1F4C1} Archives'}</button>
</div>
{#if _pc.onglets?.[onglet]?.descriptif}
<p class="tab-descriptif">{@html safeHtml(_pc.onglets[onglet].descriptif)}</p>
{/if}

<!-- Filtres -->
<div class="filters">
	<button class="btn btn-sm" class:btn-primary={filtreType === ''} on:click={() => filtreType = ''}>Tous</button>
	{#each visibleTypes as t}
		<button class="btn btn-sm" class:btn-primary={filtreType === t.val} on:click={() => filtreType = t.val}>
			{t.label}
		</button>
	{/each}
</div>

<!-- Formulaire création/édition -->
{#if showForm && $isCS}
	<div class="modal-overlay" on:click|self={() => { showForm = false; resetForm(); }}>
		<div class="modal" style="max-width:640px" on:click|stopPropagation>
			<div class="modal-header">
				<h2>{editId ? 'Modifier' : 'Nouvel événement'}</h2>
				<button class="modal-close" on:click={() => { showForm = false; resetForm(); }}>×</button>
			</div>
			<form on:submit|preventDefault={save}>
				<div class="modal-body">
					<div class="form-grid">
						<label>Titre *<input bind:value={form.titre} required /></label>
						<label>Type
							<select bind:value={form.type}>
								{#each types as t}<option value={t.val}>{t.label}</option>{/each}
							</select>
						</label>
						<label>Date de début *<input type="date" bind:value={form.debut} required /></label>
						<label>Heure (optionnelle)<input type="time" bind:value={form.debut_heure} /></label>
						<label>Fin<input type="datetime-local" bind:value={form.fin} /></label>
						<label>Lieu<input bind:value={form.lieu} /></label>
						<label>Prestataire
							<select bind:value={form.prestataire_id}>
								<option value=''>— Aucun —</option>
								{#each prestataires.filter(p => p.actif !== false) as p}
									<option value={String(p.id)}>{p.nom}</option>
								{/each}
							</select>
						</label>
					</div>
					{#if form.prestataire_id && form.type !== 'maintenance_recurrente'}
					<div class="field" style="margin-top:.75rem;display:grid;grid-template-columns:1fr 1fr;gap:.5rem">
						<label>Fréquence (optionnelle)
							<select bind:value={form.frequence_type}>
								<option value=''>— Pas de récurrence —</option>
								<option value='fois_par_an'>× / an</option>
								<option value='mois'>Tous les N mois</option>
								<option value='semaines'>Toutes les N semaines</option>
							</select>
						</label>
						{#if form.frequence_type}
						<label>Valeur
							<input type="number" min="1" bind:value={form.frequence_valeur} placeholder="ex: 2" />
						</label>
						{/if}
					</div>
					{/if}
					<div class="field" style="margin-top:.75rem">
						<label>Périmètre *</label>
						<PerimetrePicker bind:value={formPerimetreCible} />
					</div>
					<div class="field" style="margin-top:.75rem">
						<label>Suivi Kanban</label>
						<select bind:value={form.statut_kanban} style="max-width:280px;padding:.4rem .6rem;border:1px solid var(--color-border);border-radius:var(--radius);font-size:.875rem;background:var(--color-bg)">
							<option value="">— Pas de suivi Kanban —</option>
							{#each KANBAN_COLS as col}
								<option value={col.id}>{col.label}</option>
							{/each}
						</select>
					</div>
					<div class="field" style="margin-top:.75rem">
						<label style="display:flex;align-items:center;gap:.5rem;cursor:pointer">
							<input type="checkbox" bind:checked={form.affichable} style="width:auto;margin:0" />
							<span>Afficher dans le tableau de bord (événements récents)</span>
						</label>
					</div>
					<div class="field" style="margin-top:.75rem">
						<label>Description</label>
						<RichEditor bind:value={form.description} placeholder="Description de l'événement…" minHeight="80px" />
					</div>
				</div>
				<div class="modal-footer">
					<button type="button" class="btn btn-outline" on:click={() => { showForm = false; resetForm(); }}>Annuler</button>
					<button class="btn btn-primary" disabled={submitting}>{submitting ? 'Enregistrement…' : 'Enregistrer'}</button>
				</div>
			</form>
		</div>
	</div>
{/if}

<!-- Contenu -->
{#if loading}
	<p style="color:var(--color-text-muted)">Chargement…</p>
{:else if onglet === 'archives'}
	{#if allArchiveItems.length === 0}
		<div class="empty-state">
			<h3>Aucune archive</h3>
			<p>Les éléments archivés apparaîtront ici.</p>
		</div>
	{:else}
		{#each archiveByYear as [year, monthGroups]}
			<div class="archive-year-section">
				<button class="archive-year-header" on:click={() => { if (expandedArchiveYears.has(year)) expandedArchiveYears.delete(year); else expandedArchiveYears.add(year); expandedArchiveYears = expandedArchiveYears; }}>
					<span class="archive-year-label">&#x1F4C5; {year}</span>
					<span class="archive-year-count">{monthGroups.reduce((s, [, items]) => s + items.length, 0)} élément{monthGroups.reduce((s, [, items]) => s + items.length, 0) > 1 ? 's' : ''}</span>
					<span class="chevron" class:open={expandedArchiveYears.has(year)}>›</span>
				</button>
				{#if expandedArchiveYears.has(year)}
					{#each monthGroups as [mois, items]}
						<div class="month-group" style="padding-left:.75rem">
							<div class="month-label">{mois}</div>
							{#each items as item}
								{#if item._kind === 'pub'}
									<!-- Publication archivée -->
									<div class="event-row archive-row card" style="opacity:.85;border-left:3px solid #0ea5e9">
									<div class="event-type archive-type">
										&#x1F4F0;
										<span class="badge" style="background:#0ea5e9;color:white;font-size:.65rem;white-space:nowrap">Actualité</span>
									</div>
									<div class="event-body">
										<strong class="event-titre">{item.titre}</strong>
											{#if item.contenu}<div class="event-desc rich-content clamp-5">{@html safeHtml(item.contenu)}</div>{/if}
										</div>
										<div class="event-date">
											<div>{new Date(item._date).toLocaleDateString('fr-FR', { dateStyle: 'short' })}</div>
											{#if item.auteur_nom}<small style="color:var(--color-text-muted)">{item.auteur_nom}</small>{/if}
										</div>
										{#if $isAdmin}
											<div class="event-actions">
												<button class="btn-icon-danger" aria-label="Supprimer définitivement" title="Supprimer définitivement" on:click={() => deleteArchivedPub(item)}>&#x1F5D1;️</button>
											</div>
										{/if}
									</div>
								{:else if item._kind === 'devis'}
									<!-- Prestation réalisée -->
									<div class="event-row archive-row card" style="opacity:.85;border-left:3px solid #7c3aed">
										<div class="event-type archive-type">
											&#x1F3C1;
											<span class="badge" style="background:#7c3aed;color:white;font-size:.65rem;white-space:nowrap">Prestation</span>
										</div>
										<div class="event-body">
											<strong class="event-titre">{item.titre}</strong>
											{#if prestataireNom(item.prestataire_id)}<span class="event-meta">&#x1F3AF; {prestataireNom(item.prestataire_id)}</span>{/if}
											{#if item.notes}<div class="event-desc rich-content clamp-5">{@html safeHtml(item.notes)}</div>{/if}
										</div>
										<div class="event-date">
											{#if item.date_prestation}<div>{new Date(item.date_prestation).toLocaleDateString('fr-FR', { dateStyle: 'short' })}</div>{/if}
											{#if item.montant_estime}<div style="font-size:.8rem;color:var(--color-text-muted)">{item.montant_estime.toLocaleString('fr-FR')} €</div>{/if}
										</div>
									</div>
								{:else}
									<!-- Événement archivé -->
									<div class="event-row archive-row card" class:event-urgent={item.type === 'coupure'} style="opacity:.85;border-left:3px solid #10b981">
										<div class="event-type archive-type">
											{typeLabel(item.type)}
											<span class="badge" style="background:#10b981;color:white;font-size:.65rem;white-space:nowrap">Événement</span>
										</div>
										<div class="event-body">
											<strong class="event-titre">{item.titre}</strong>
											{#if item.lieu}<span class="event-meta">&#x1F4CD; {item.lieu}</span>{/if}
											{#if item.description}<div class="event-desc rich-content clamp-5">{@html safeHtml(item.description)}</div>{/if}
										</div>
										<div class="event-date">
											<div>{formatDate(item.debut)}</div>
											{#if item.fin}<div style="color:var(--color-text-muted);font-size:.8rem">→ {formatDate(item.fin)}</div>{/if}
											{#if item.perimetre && item.perimetre !== 'résidence'}
												<span class="badge badge-blue" style="margin-top:.3rem">&#x1F539; {perimètreLabel(item.perimetre)}</span>
											{/if}
											<small class="ev-updated">
											{#if item.mis_a_jour_le}Mise à jour le {new Date(item.mis_a_jour_le).toLocaleDateString('fr-FR', { year: 'numeric', month: 'long', day: 'numeric' })}{:else}Publié le {new Date(item.cree_le).toLocaleDateString('fr-FR', { year: 'numeric', month: 'long', day: 'numeric' })}{/if}{#if item.auteur_nom} · {item.auteur_nom}{/if}
											</small>
										</div>
										{#if $isAdmin}
											<div class="event-actions">
												<button class="btn-icon-danger" aria-label="Supprimer définitivement" title="Supprimer définitivement" on:click={() => deleteEv(item.id)}>&#x1F5D1;️</button>
											</div>
										{/if}
									</div>
								{/if}
							{/each}
						</div>
					{/each}
				{/if}
			</div>
		{/each}
	{/if}
{:else if listItems.length === 0 && !recurringMaintenances.length && !kanbanEvs.length}
	<div class="empty-state">
		<h3>Aucun événement</h3>
		<p>Le calendrier de la résidence apparaîtra ici.</p>
	</div>
{:else if onglet === 'liste'}
	{#each groups as [annee, evs]}
		<div class="month-group">
			<div class="month-label">&#x1F4C5; {annee}</div>
			{#each evs as ev}
				{@const expanded = expandedEvId === ev.id}
				<div
					class="event-row card"
					class:event-urgent={ev.type === 'coupure'}
					class:expanded
					style="cursor:pointer"
					role="button"
					tabindex="0"
					on:click={() => expandedEvId = expanded ? null : ev.id}
					on:keydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); expandedEvId = expanded ? null : ev.id; } }}
				>
					<div class="event-type">{typeLabel(ev.type)}</div>
					<div class="event-body">
						<strong class="event-titre">{ev.titre}</strong>
						{#if ev.prestataire_nom}<span class="event-meta">&#x1F3AF; {ev.prestataire_nom}</span>{/if}
						{#if ev.lieu}<span class="event-meta">&#x1F4CD; {ev.lieu}</span>{/if}
					</div>
					<div class="event-date">
						<div>{formatDate(ev.debut)}</div>
						{#if ev.fin}<div style="color:var(--color-text-muted);font-size:.8rem">→ {formatDate(ev.fin)}</div>{/if}
						{#if ev.perimetre && ev.perimetre !== 'résidence'}
							<span class="badge badge-blue" style="margin-top:.3rem">&#x1F539; {perimètreLabel(ev.perimetre)}</span>
						{/if}
						<small class="ev-updated">
							{#if ev.mis_a_jour_le}
								Mise à jour le {new Date(ev.mis_a_jour_le).toLocaleDateString('fr-FR', { year: 'numeric', month: 'long', day: 'numeric' })}
							{:else}
								Publié le {new Date(ev.cree_le).toLocaleDateString('fr-FR', { year: 'numeric', month: 'long', day: 'numeric' })}
							{/if}{#if ev.auteur_nom} · {ev.auteur_nom}{/if}
						</small>
					</div>
					{#if $isCS && ev._source !== 'devis_ponctuel'}
						<div class="event-actions" on:click|stopPropagation on:keydown|stopPropagation>
							<button class="btn-icon-edit" aria-label="Modifier" title="Modifier" on:click={() => startEdit(ev)}>✏️</button>
							{#if ev.statut_kanban === 'termine' || ev.statut_kanban === 'annule'}
								<button class="btn-icon" aria-label="Archiver" title="Archiver" on:click={() => archiveEv(ev.id)}>&#x1F4E6;</button>
							{/if}
						</div>
					{/if}
					{#if expanded && ev.description}
						<div class="ev-expanded-body rich-content" on:click|stopPropagation on:keydown|stopPropagation>
							{@html safeHtml(ev.description)}
						</div>
					{/if}
				</div>
			{/each}
		</div>
	{/each}
	{#if recurringMaintenances.length > 0}
		<div class="recurring-section">
			<button class="recurring-toggle" on:click={() => showPeriodicSection = !showPeriodicSection}>
				🔄 Maintenances récurrentes
				<span style="font-size:.8rem;font-weight:400;color:var(--color-text-muted)">({recurringMaintenances.length})</span>
				<span class="chevron" class:open={showPeriodicSection} style="margin-left:auto">›</span>
			</button>
			{#if showPeriodicSection}
				{#each recurringMaintenances as ev}
					<div class="event-row card">
						<div class="event-type">{typeLabel(ev.type)}</div>
						<div class="event-body">
							<strong class="event-titre">{ev.titre}</strong>
							{#if ev.prestataire_nom}<span class="event-meta">&#x1F3AF; {ev.prestataire_nom}</span>{/if}
							{#if ev.lieu}<span class="event-meta">&#x1F4CD; {ev.lieu}</span>{/if}
						</div>
						<div class="event-date">
							<div>{formatDate(ev.debut)}</div>
							{#if ev.fin}<div style="color:var(--color-text-muted);font-size:.8rem">→ {formatDate(ev.fin)}</div>{/if}
							{#if ev.statut_kanban}
								{@const col = KANBAN_COLS.find(c => c.id === ev.statut_kanban)}
								{#if col}<span class="badge" style="background:{col.color};color:white;font-size:.73rem;margin-top:.3rem">{col.label}</span>{/if}
							{/if}
						</div>
						{#if $isCS}
							<div class="event-actions">
								<button class="btn-icon-edit" aria-label="Modifier" title="Modifier" on:click={() => startEdit(ev)}>✏️</button>
							</div>
						{/if}
					</div>
				{/each}
			{/if}
		</div>
	{/if}
{:else}
	<!-- ── Kanban Trello-like ────────────────────────────────── -->
	<div class="kanban-toolbar">
		<label class="kanban-exercice-label">
			Exercice :
			<select bind:value={kanbanExercice} class="kanban-exercice-select">
				{#each kanbanExerciceOptions as y}<option value={y}>{y}</option>{/each}
			</select>
		</label>
		<label class="kanban-exercice-label">
			Bâtiment :
			<select bind:value={kanbanBatiment} class="kanban-exercice-select">
				{#each BATIMENT_OPTIONS as b}<option value={b.val}>{b.label}</option>{/each}
			</select>
		</label>
		<span class="kanban-count-total">{kanbanEvs.length} affaire{kanbanEvs.length > 1 ? 's' : ''}</span>
		{#if $isCS}
			<button class="btn btn-sm kanban-init-btn" on:click={initPrestataires} disabled={initLoading}>
				{initLoading ? '⏳ Création…' : '⚙️ Init. prestataires'}
			</button>
		{/if}
	</div>
	<div class="kanban">
		{#each kanbanCols as col}
			{@const items = col.items}
			<div class="kanban-col"
				on:dragover={onDragOver}
				on:drop={(e) => onDrop(e, col.id)}
				role="list">
				<div class="kanban-col-header" style="border-top-color:{col.color}">
					<span>{col.label}</span>
					<span class="kanban-count">{items.length}</span>
				</div>
				{#if items.length === 0}
					<p class="kanban-empty">Aucune affaire</p>
				{:else}
					{#each items as ev (ev.id)}
						<div class="kanban-card card"
							class:event-urgent={ev.type === 'coupure'}
							class:kanban-card-expanded={expandedKanbanId === ev.id}
							draggable={$isCS && ev._source !== 'devis_ponctuel' && expandedKanbanId !== ev.id ? 'true' : 'false'}
							on:dragstart={(e) => onDragStart(e, ev.id)}
							on:click={() => expandedKanbanId = expandedKanbanId === ev.id ? null : ev.id}
							on:keydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); expandedKanbanId = expandedKanbanId === ev.id ? null : ev.id; } }}
							role="button"
							tabindex="0">
							<!-- Tags périmètre + année (uniquement si année ≠ exercice sélectionné) -->
							<div class="kanban-card-tags">
								{#each perimetreTags(ev.perimetre) as tag}
									<span class="kb-tag" style="background:{tag.color}">{tag.label}</span>
								{/each}
								<span class="kb-tag" style="background:{yearColor(new Date(ev.debut).getFullYear())}" title="Événement de {new Date(ev.debut).getFullYear()}">{new Date(ev.debut).getFullYear()}</span>
							</div>
							{#if ev.prestataire_nom}<span class="kanban-card-prest">{ev.prestataire_nom}</span>{/if}
							<strong class="kanban-card-titre">{ev.titre}</strong>
							<div class="kanban-card-footer">
								<span class="kanban-card-type">{typeLabel(ev.type)}</span>
								{#if $isCS && ev._source !== 'devis_ponctuel'}
									<div class="kanban-card-actions" on:click|stopPropagation on:keydown|stopPropagation>
										<button class="btn-icon-edit" aria-label="Modifier" title="Modifier" on:click={() => startEdit(ev)}>✏️</button>
									{#if $isAdmin}
										<button class="btn-icon-danger" aria-label="Supprimer définitivement" title="Supprimer définitivement" on:click={() => deleteEv(ev.id)}>&#x1F5D1;️</button>
									{/if}
									</div>
								{/if}
							</div>
							{#if expandedKanbanId === ev.id}
								<div class="kanban-card-detail" on:click|stopPropagation on:keydown|stopPropagation>
									<div class="kanban-card-detail-row">📅 {formatDate(ev.debut)}{#if ev.fin} → {formatDate(ev.fin)}{/if}</div>
									{#if ev.lieu}<div class="kanban-card-detail-row">📍 {ev.lieu}</div>{/if}
									{#if ev.description}
										<div class="kanban-card-detail-desc rich-content">{@html safeHtml(ev.description)}</div>
									{/if}
								</div>
							{/if}
						</div>
					{/each}
				{/if}
			</div>
		{/each}
	</div>
{/if}

<style>
	.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; padding-left: 1.25rem; }
	.filters { display: flex; gap: .4rem; flex-wrap: wrap; margin-bottom: 1.25rem; }
	.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: .75rem; }
	.checkbox-field { display: flex; align-items: center; gap: .4rem; font-size: .875rem; cursor: pointer; }

	.form-actions { display: flex; justify-content: flex-end; gap: .5rem; margin-top: .75rem; }
	.form-grid label, .form-grid select, .form-grid input { display: flex; flex-direction: column; gap: .3rem; font-size: .9rem; }
	.form-grid input, .form-grid select,
	form textarea { padding: .45rem .6rem; border: 1px solid var(--color-border); border-radius: var(--radius); font-size: .9rem; background: var(--color-bg); width: 100%; }
	.month-group { margin-bottom: 1.5rem; }
	.month-label { font-size: .8rem; font-weight: 600; text-transform: uppercase; letter-spacing: .06em; color: var(--color-text-muted); margin-bottom: .5rem; }
	.event-row { display: flex; gap: 1rem; align-items: flex-start; padding: .85rem 1rem; margin-bottom: .4rem; }
	.ev-expandable { cursor: pointer; }
	.ev-expandable:hover { background: var(--color-bg); }
	.event-urgent { border-left: 3px solid var(--color-danger); }
	.event-type { min-width: 7rem; font-size: .8rem; font-weight: 600; padding-top: .1rem; }
	.event-body { flex: 1; }
	.archive-row {
		display: grid;
		grid-template-columns: 7.75rem minmax(0, 1fr) 8.5rem auto;
		column-gap: 1rem;
		align-items: start;
	}
	.archive-row .event-body { min-width: 0; }
	.archive-type {
		min-width: 0;
		width: 7.75rem;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: .35rem;
		text-align: center;
		padding: .15rem .35rem;
	}
	.archive-type :global(.badge) {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-width: 6.5rem;
	}
	.event-titre { font-size: .95rem; }
	.event-meta { font-size: .8rem; color: var(--color-text-muted); margin-left: .5rem; }
	.event-desc { font-size: .85rem; color: var(--color-text-muted); margin: .2rem 0 0; }
	.event-date { text-align: right; font-size: .85rem; min-width: 110px; }
	.ev-updated { display: block; font-size: .75rem; color: var(--color-text-muted); margin-top: .3rem; }
	.ev-expanded-body { grid-column: 1 / -1; padding: .6rem .75rem .25rem; font-size: .875rem; line-height: 1.6; border-top: 1px solid var(--color-border); margin-top: .4rem; }
	.event-row.card.expanded { border-color: var(--color-primary, #2563eb); box-shadow: 0 0 0 2px color-mix(in srgb, var(--color-primary, #2563eb) 18%, transparent); }
	.event-actions { display: flex; gap: .3rem; }
	@media (max-width: 760px) {
		.archive-row {
			grid-template-columns: 1fr;
			row-gap: .6rem;
		}
		.archive-type {
			width: auto;
			align-items: flex-start;
			text-align: left;
			padding: 0;
		}
		.archive-row .event-date {
			text-align: left;
			min-width: 0;
		}
		.archive-row .event-actions {
			justify-content: flex-start;
		}
	}

	.back-link { display: inline-flex; align-items: center; gap: .3rem; font-size: .85rem; color: var(--color-text-muted); text-decoration: none; margin-bottom: .75rem; }
	.back-link:hover { color: var(--color-primary); }
	.danger:hover { color: var(--color-danger); border-color: var(--color-danger); }

	.tabs { display: flex; gap: .4rem; border-bottom: 2px solid var(--color-border); padding-bottom: .1rem; }
	.tabs button { padding: .45rem 1rem; border: none; background: none; cursor: pointer; font-size: .9rem; color: var(--color-text-muted); border-bottom: 2px solid transparent; margin-bottom: -2px; border-radius: var(--radius) var(--radius) 0 0; }
	.tabs button:hover { color: var(--color-text); background: var(--color-bg); }
	.tabs button.active { color: var(--color-primary); font-weight: 600; border-bottom-color: var(--color-primary); }

	.kanban { display: flex; gap: .6rem; align-items: flex-start; margin-bottom: 1.5rem; overflow-x: auto; padding-bottom: .5rem; }
	.kanban-col { min-width: 220px; flex: 1; border-radius: var(--radius); background: var(--color-bg); border: 1px solid var(--color-border); overflow: hidden; }
	@media (max-width: 900px) { .kanban { flex-direction: column; } .kanban-col { min-width: 100%; } }
	.kanban-toolbar { display: flex; align-items: center; gap: 1rem; margin-bottom: .75rem; flex-wrap: wrap; }
	.kanban-exercice-label { font-size: .85rem; font-weight: 600; display: flex; align-items: center; gap: .4rem; }
	.kanban-exercice-select { padding: .25rem .5rem; border: 1px solid var(--color-border); border-radius: var(--radius); background: var(--color-surface); font-size: .85rem; }
	.kanban-count-total { font-size: .8rem; color: var(--color-text-muted); }
	.kanban-init-btn { margin-left: auto; font-size: .8rem; padding: .3rem .75rem; border: 1px solid var(--color-border); border-radius: var(--radius); background: var(--color-surface); cursor: pointer; white-space: nowrap; }
	.kanban-init-btn:hover:not(:disabled) { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
	.kanban-init-btn:disabled { opacity: .5; cursor: not-allowed; }
	.archive-year-section { margin-bottom: .5rem; border: 1px solid var(--color-border); border-radius: var(--radius); overflow: hidden; }
	.archive-year-header { width: 100%; display: flex; align-items: center; gap: .75rem; padding: .65rem 1rem; background: var(--color-surface); border: none; cursor: pointer; font-size: .95rem; font-weight: 600; text-align: left; }
	.archive-year-header:hover { background: var(--color-bg); }
	.archive-year-label { flex: 1; }
	.archive-year-count { font-size: .8rem; font-weight: 400; color: var(--color-text-muted); }
	.chevron { font-size: 1.1rem; color: var(--color-text-muted); transition: transform .15s; display: inline-block; line-height: 1; }
	.chevron.open { transform: rotate(90deg); }
	.kanban-col { border-radius: var(--radius); background: var(--color-bg); border: 1px solid var(--color-border); overflow: hidden; }
	.kanban-col-header { display: flex; justify-content: space-between; align-items: center; padding: .6rem .9rem; border-top: 3px solid; font-weight: 600; font-size: .8rem; text-transform: uppercase; letter-spacing: .06em; }
	.kanban-count { background: var(--color-border); border-radius: 999px; padding: .1rem .45rem; font-size: .72rem; font-weight: 700; }
	.kanban-empty { padding: 1rem; font-size: .85rem; color: var(--color-text-muted); text-align: center; }
	.kanban-card { margin: .3rem; padding: .35rem .55rem; display: flex; flex-direction: column; gap: .15rem; cursor: pointer; transition: box-shadow .15s, opacity .15s; }
	.kanban-card-expanded { cursor: default; box-shadow: 0 2px 8px rgba(0,0,0,.12); }
	.kanban-card-detail { border-top: 1px solid var(--color-border); margin-top: .3rem; padding-top: .35rem; }
	.kanban-card-detail-row { font-size: .72rem; color: var(--color-text-muted); line-height: 1.5; }
	.kanban-card-detail-desc { font-size: .72rem; line-height: 1.5; margin-top: .25rem; }
	.kanban-card:active { cursor: grabbing; }
	.kanban-card[draggable="true"]:hover { box-shadow: 0 2px 8px rgba(0,0,0,.12); }
	.kanban-card-tags { display: flex; flex-wrap: wrap; gap: .25rem; margin-bottom: .15rem; }
	.kb-tag { font-size: .65rem; font-weight: 600; padding: .1rem .4rem; border-radius: 3px; color: #fff; line-height: 1.4; text-transform: lowercase; }
	.kanban-card-titre { font-size: .75rem; line-height: 1.25; }
	.kanban-card-prest { font-size: .68rem; color: var(--color-text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
	.kanban-card-desc { font-size: .78rem; color: var(--color-text-muted); margin-top: .1rem; }
	.kanban-card-footer { display: flex; justify-content: space-between; align-items: center; margin-top: .2rem; }
	.kanban-card-type { font-size: .72rem; font-weight: 600; color: var(--color-text-muted); }
	.kanban-card-actions { display: flex; gap: .3rem; }
	.recurring-section { margin-top: 1.5rem; padding: .5rem 0; }
	.recurring-toggle {
		background: #f0f9ff; border: 1px solid #bae6fd; border-radius: var(--radius);
		cursor: pointer; font-size: .875rem; font-weight: 600;
		color: #0369a1; padding: .5rem .9rem;
		width: 100%; text-align: left;
		display: flex; align-items: center; gap: .5rem;
	}
	.recurring-toggle:hover { background: #e0f2fe; }
	.maintenance-archive-section { margin-top: 1.5rem; padding: .5rem 0; }
	.maintenance-archive-toggle {
		background: none; border: none; cursor: pointer;
		font-size: .875rem; font-weight: 600;
		color: var(--color-text-muted); padding: .25rem 0;
		width: 100%; text-align: left;
	}
	.maintenance-archive-toggle:hover { color: var(--color-text); }
</style>
