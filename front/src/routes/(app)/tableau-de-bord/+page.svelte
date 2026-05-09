<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { currentUser, isCS, isAdmin, isProprio } from '$lib/stores/auth';
	import { flux, lots, tickets as ticketsApi, calendrier as calApi, prestataires as prestApi, type FluxItem, type FluxProchain, type FluxResponse } from '$lib/api';
	import { getPageConfig, configStore, siteNomStore } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';
	import { fmtDate, fmtDateLong, fmtDatetimeShort, fmtTime } from '$lib/date';
	import Icon from '$lib/components/Icon.svelte';
	import { toast } from '$lib/components/Toast.svelte';

	$: _pc = getPageConfig($configStore, 'tableau-de-bord', { titre: 'Tableau de bord', navLabel: 'Accueil', descriptif: "Le pouls de votre résidence — tous les mouvements en un seul flux." });
	$: _siteNom = $siteNomStore;

	let data: FluxResponse | null = null;
	let userLots: any[] = [];
	let loading = true;
	let ready = false;
	let relanceSyndicCount = 0;
	let kanbanRawEvs: any[] = [];
	let dashDevis: any[] = [];
	let mobileKanbanIdx = 0;

	onMount(async () => {
		try {
			const [fluxRes, lotsRes, calRes, devisRes] = await Promise.allSettled([flux.get(), lots.mesList(), calApi.list(), prestApi.devis()]);
			if (fluxRes.status === 'fulfilled') data = fluxRes.value;
			else toast('error', 'Erreur chargement du flux');
			if (lotsRes.status === 'fulfilled') userLots = lotsRes.value;
			if (calRes.status === 'fulfilled') kanbanRawEvs = calRes.value;
			if (devisRes.status === 'fulfilled') dashDevis = devisRes.value;
		} catch (e: any) {
			toast('error', 'Erreur chargement : ' + (e?.message ?? String(e)));
		} finally {
			loading = false;
			setTimeout(() => { ready = true; }, 50);
		}
		// Relance syndic — uniquement pour CS/Admin
		if ($isCS || $isAdmin) {
			try {
				const relanceList = await ticketsApi.relanceSyndicList();
				relanceSyndicCount = relanceList.length;
			} catch { /* silencieux */ }
		}
	});

	// ── Rôles & filtrage ───────────────────────────────────────────────────
	$: canSeeAG = ($currentUser?.roles ?? []).some((r: string) =>
		['propriétaire', 'conseil_syndical', 'admin'].includes(r)
	);
	$: isLocataire = $currentUser?.statut === 'locataire';
	$: userBatimentId = $currentUser?.batiment_id ?? null;
	$: isSyndicUser = $currentUser?.statut === 'syndic' || ($currentUser?.roles ?? []).includes('syndic');

	function parseBatimentCodes(values: string[]): number[] {
		return values.map(v => { const m = v.trim().match(/^bat:(\d+)$/i); return m ? Number(m[1]) : null; }).filter((v): v is number => Number.isFinite(v));
	}
	function hasResidenceScope(values: string[]): boolean {
		return values.some(v => ['résidence', 'parking', 'cave', 'aful'].includes(v.trim().toLowerCase()));
	}
	function isInUserPerimeter(perimetres: string[] | null | undefined): boolean {
		if ($isAdmin || $isCS || isSyndicUser) return true;
		const perims = perimetres ?? ['résidence'];
		if (hasResidenceScope(perims)) return true;
		if (userBatimentId == null) return true;
		return parseBatimentCodes(perims).includes(userBatimentId);
	}
	function parseItemPerimetres(item: FluxItem): string[] {
		const m = item.meta;
		if (m.perimetre_cible && Array.isArray(m.perimetre_cible)) return m.perimetre_cible as string[];
		if (typeof m.perimetre === 'string' && m.perimetre) return (m.perimetre as string).split(',').map(s => s.trim());
		return ['résidence'];
	}

	// ── Salutation contextuelle ────────────────────────────────────────────
	$: greeting = (() => {
		const h = new Date().getHours();
		if (h < 6) return 'Bonne nuit';
		if (h < 12) return 'Bonjour';
		if (h < 18) return 'Bon après-midi';
		return 'Bonsoir';
	})();

	$: roleLabels = (() => {
		const STATUT: Record<string, string> = {
			'copropriétaire_résident': 'Copropriétaire résident',
			'copropriétaire_bailleur': 'Copropriétaire bailleur',
			locataire: 'Locataire', syndic: 'Syndic',
			mandataire: 'Mandataire', aidant: 'Aidant (proche)',
		};
		const SPECIAL: Record<string, string> = { conseil_syndical: 'Conseil syndical', admin: 'Admin' };
		const labels: string[] = [];
		const statut = $currentUser?.statut ?? '';
		if (STATUT[statut]) labels.push(STATUT[statut]);
		const allRoles = new Set([...($currentUser?.roles ?? []), $currentUser?.role ?? '']);
		for (const r of ['conseil_syndical', 'admin']) { if (allRoles.has(r)) labels.push(SPECIAL[r]); }
		return labels.join(' · ');
	})();

	$: lotLabel = (() => {
		if (userLots.length === 0) return '';
		const appt = userLots.find((l: any) => l.type === 'appartement');
		if (!appt) return '';
		const parts: string[] = [];
		if (appt.batiment_nom) parts.push(appt.batiment_nom);
		else if ($currentUser?.batiment_nom) parts.push($currentUser.batiment_nom);
		if (appt.type_appartement) parts.push(appt.type_appartement);
		if (appt.etage != null) {
			if (appt.etage === 0) parts.push('RDC');
			else if (appt.etage === 1) parts.push('1er');
			else parts.push(`${appt.etage}ème`);
		}
		return parts.join(', ');
	})();

	// ── Expand state (unique entre prochaines échéances et fil d'activité) ─
	let expandedItem: string | null = null;
	function toggleItem(id: string) { expandedItem = expandedItem === id ? null : id; }

	// ── Filtrage rôle/périmètre sur items ──────────────────────────────────
	$: filteredItems = (data?.items ?? []).filter(item => {
		// AG invisible pour les locataires / non-proprios
		if (item.type === 'evenement' && (item.meta?.type === 'ag') && !canSeeAG) return false;
		// Filtrage périmètre (backend le fait déjà, mais sécurité côté client)
		return true;
	});

	// ── Déduplication : événements futurs avec date → prochaines échéances seulement ─
	$: prochainsIds = new Set((data?.sante.prochains ?? []).filter(p => p.id).map(p => p.id));
	$: filItems = filteredItems.filter(item => {
		// Les événements calendrier avec date future → prochaines échéances uniquement
		if (item.type === 'evenement') {
			if (item.id && prochainsIds.has(item.id)) return false;
			const debut = item.meta?.debut as string | undefined;
			if (debut && new Date(debut) > new Date()) return false;
		}
		return true;
	});

	// ── Classement du fil : récent / ancien / masqué ───────────────────────
	const THIRTY_DAYS = 30 * 86400000;
	const YEAR_PLUS = 377 * 86400000;

	function getRelevantDate(item: FluxItem): number {
		const cloture = (item.meta?.cloture_le || item.meta?.ferme_le) as string | undefined;
		if (cloture) return new Date(cloture).getTime();
		return new Date(item.cree_le || item.date).getTime();
	}
	function isUnresolved(item: FluxItem): boolean {
		if (item.type === 'ticket_ouvert') {
			const s = (item.meta?.statut as string) ?? '';
			return !['résolu', 'fermé'].includes(s);
		}
		if (item.type === 'evenement') {
			const k = (item.meta?.statut_kanban as string) ?? '';
			return !['termine', 'annule'].includes(k);
		}
		return false;
	}

	let recentItems: FluxItem[] = [];
	let olderItems: FluxItem[] = [];
	$: {
		const _recent: FluxItem[] = [];
		const _older: FluxItem[] = [];
		const now = Date.now();
		for (const item of filItems) {
			const age = now - getRelevantDate(item);
			if (isUnresolved(item)) { _recent.push(item); continue; }
			if (age > YEAR_PLUS) continue;
			if (age < THIRTY_DAYS) _recent.push(item);
			else _older.push(item);
		}
		recentItems = _recent;
		olderItems = _older;
	}

	// ── Groupement par jour ────────────────────────────────────────────────
	interface DayGroup { label: string; items: FluxItem[] }

	function groupByDay(items: FluxItem[]): DayGroup[] {
		const groups: Map<string, FluxItem[]> = new Map();
		const today = new Date(); today.setHours(0, 0, 0, 0);
		const yesterday = new Date(today); yesterday.setDate(yesterday.getDate() - 1);
		for (const item of items) {
			const d = new Date(item.date); d.setHours(0, 0, 0, 0);
			let label: string;
			if (d.getTime() === today.getTime()) label = "Aujourd'hui";
			else if (d.getTime() === yesterday.getTime()) label = 'Hier';
			else label = fmtDateLong(item.date);
			if (!groups.has(label)) groups.set(label, []);
			groups.get(label)!.push(item);
		}
		return Array.from(groups, ([label, items]) => ({ label, items }));
	}

	$: recentDayGroups = groupByDay(recentItems);
	$: olderDayGroups = groupByDay(olderItems);
	let olderOpen = false;

	// ── Kanban widget ──────────────────────────────────────────────────────
	const _kanbanYear = new Date().getMonth() < 1 ? new Date().getFullYear() - 1 : new Date().getFullYear();

	function kanbanStatutPourDevis(statut: string | null | undefined): string {
		const map: Record<string, string> = { en_attente: 'syndic', accepte: 'fournisseur', realise: 'termine', refuse: 'annule' };
		return map[statut ?? ''] ?? 'syndic';
	}

	$: dashDevisPonctuels = dashDevis
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
				affichable: true,
			};
		});

	const DASH_KANBAN_COLS = [
		{ id: 'ag',          label: 'AG',          color: '#8b5cf6' },
		{ id: 'cs',          label: 'CS',           color: '#3b82f6' },
		{ id: 'syndic',      label: 'Syndic',       color: '#f59e0b' },
		{ id: 'fournisseur', label: 'Prestataire',  color: '#f97316' },
		{ id: 'termine',     label: 'Terminé', color: '#22c55e' },
	];

	const EV_ICONS: Record<string, string> = {
		travaux: '\u{1F528}', coupure: '⚡', ag: '\u{1F3DB}️',
		maintenance: '\u{1F527}', maintenance_recurrente: '\u{1F504}', autre: '\u{1F4CC}',
	};

	function dashKanbanPerimLabel(p: string): string {
		const map: Record<string, string> = {
			'résidence': '', 'bat:1': 'Bât. 1', 'bat:2': 'Bât. 2',
			'bat:3': 'Bât. 3', 'bat:4': 'Bât. 4',
			parking: 'Parking', cave: 'Cave',
		};
		return p.split(',').map(s => map[s.trim()] ?? s.trim()).filter(Boolean).join(' · ');
	}

	$: dashKanbanEvs = [...kanbanRawEvs, ...dashDevisPonctuels].filter(ev => {
		if (!ev.statut_kanban || ev.statut_kanban === 'annule') return false;
		if (!$isCS && !$isAdmin && !ev.affichable && ev.type !== 'maintenance_recurrente') return false;
		if (ev.archivee && ev.statut_kanban !== 'annule' && !(ev.type === 'maintenance_recurrente' && ev.statut_kanban === 'fournisseur')) return false;
		const refDate = ev.statut_kanban === 'termine' && ev.fin ? ev.fin : ev.debut;
		const evYear = new Date(refDate).getFullYear();
		const isOverdue = ev.type !== 'maintenance_recurrente' && evYear < _kanbanYear && ev.statut_kanban !== 'termine';
		if (!isOverdue && evYear !== _kanbanYear) return false;
		return true;
	});

	$: dashKanbanCols = DASH_KANBAN_COLS
		.filter(col => (col.id === 'ag' || col.id === 'cs') ? canSeeAG : true)
		.map(col => {
			let items: any[] = dashKanbanEvs.filter((ev: any) => {
				if (ev.archivee && ev.type === 'maintenance_recurrente' && ev.statut_kanban === 'fournisseur') return col.id === 'termine';
				return ev.statut_kanban === col.id;
			});
			if (col.id === 'termine') {
				items = [...items].sort((a: any, b: any) =>
					new Date(b.fin ?? b.debut).getTime() - new Date(a.fin ?? a.debut).getTime()
				);
			}
			return { ...col, total: items.length, items: items.slice(0, 5) };
		});

	$: mobileKanbanCols = dashKanbanCols.filter(col => col.items.length > 0);
	$: { if (mobileKanbanIdx >= mobileKanbanCols.length) mobileKanbanIdx = Math.max(0, mobileKanbanCols.length - 1); }
	$: mobileKanbanCurrent = mobileKanbanCols[mobileKanbanIdx] ?? null;

	// ── Urgences en cours ──────────────────────────────────────────────────
	$: urgentItems = filteredItems.filter(i =>
		(i.type === 'evenement' && i.meta?.type === 'coupure') ||
		(i.type === 'ticket_ouvert' && i.badges?.includes('urgence')) ||
		(i.type === 'publication' && i.meta?.urgente)
	);

	// ── Compteurs rapides ──────────────────────────────────────────────────
	$: countByType = (() => {
		const c: Record<string, number> = {};
		for (const item of filteredItems) c[item.type] = (c[item.type] ?? 0) + 1;
		return c;
	})();

	// ── Helpers ────────────────────────────────────────────────────────────
	function typeLink(item: FluxItem): string {
		if (item.type === 'sondage_ouvert' || item.type === 'sondage_clos') return '/sondages';
		if (['ticket_ouvert', 'ticket_resolu', 'ticket_mis_a_jour'].includes(item.type)) {
			const numero = item.meta?.numero as string | undefined;
			return numero ? `/tickets?open=${numero}` : '/tickets';
		}
		return item.lien ?? '#';
	}

	function typeVoirLabel(item: FluxItem): string {
		if (['ticket_ouvert', 'ticket_resolu', 'ticket_mis_a_jour'].includes(item.type)) return 'Voir le ticket →';
		if (item.type === 'publication') return "Voir l'actualité →";
		if (item.type === 'evenement') return "Voir l'événement →";
		if (item.type === 'devis') return 'Voir le devis →';
		if (item.type === 'sondage_ouvert' || item.type === 'sondage_clos') return 'Voir le sondage →';
		return 'Voir →';
	}

	const TYPE_LABELS: Record<string, string> = {
		ticket_resolu: 'Ticket résolu', ticket_ouvert: 'Ticket', ticket_mis_a_jour: 'Ticket mis à jour',
		publication: 'Actualité', evenement: 'Événement',
		devis: 'Devis', sondage_clos: 'Sondage clos', sondage_ouvert: 'Sondage',
	};

	const TYPE_COLORS: Record<string, string> = {
		ticket_resolu: '#DC2626',
		ticket_ouvert: '#DC2626',
		ticket_mis_a_jour: '#DC2626',
		publication: 'var(--color-primary)',
		evenement: '#F59E0B',
		devis: '#10B981',
		sondage_clos: '#8B5CF6',
		sondage_ouvert: '#8B5CF6',
	};

	const TYPE_BG: Record<string, string> = {
		ticket_resolu: '#FEF2F2',
		ticket_ouvert: '#FEF2F2',
		ticket_mis_a_jour: '#FEF2F2',
		publication: '#EEF2F7',
		evenement: '#FFFBEB',
		devis: '#ECFDF5',
		sondage_clos: '#F5F3FF',
		sondage_ouvert: '#F5F3FF',
	};

	function isNew(item: { cree_le?: string; date: string }): boolean {
		const dateTs = new Date(item.date).getTime();
		const creeTs = item.cree_le ? new Date(item.cree_le).getTime() : dateTs;
		const ref = Math.max(dateTs, creeTs);
		const diff = Date.now() - ref;
		return diff >= 0 && diff < 48 * 3600 * 1000;
	}

	function urgencyProgress(item: FluxItem): { pct: number; label: string; active: boolean } | null {
		const debut = item.meta?.debut as string | undefined;
		const fin = item.meta?.fin as string | undefined;
		if (!debut || !fin) return null;
		const dStart = new Date(debut).getTime();
		const dEnd = new Date(fin).getTime();
		const now = Date.now();
		if (now < dStart) return { pct: 0, label: 'À venir', active: false };
		if (now > dEnd) return { pct: 100, label: 'Terminé', active: false };
		const pct = Math.round(((now - dStart) / (dEnd - dStart)) * 100);
		const hStart = new Date(dStart).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
		const hEnd = new Date(dEnd).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
		return { pct, label: `En cours (${hStart}–${hEnd})`, active: true };
	}

	function fmtHeure(iso: string): string {
		return fmtTime(iso);
	}
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

{#if loading}
	<div class="skeleton-wrap">
		<div class="skel skel-header"></div>
		<div class="skel skel-subtitle"></div>
		<div class="skel-row"><div class="skel skel-kpi"></div><div class="skel skel-kpi"></div><div class="skel skel-kpi"></div></div>
		<div class="skel skel-card"></div>
		<div class="skel skel-card"></div>
		<div class="skel skel-card short"></div>
	</div>
{:else if !data}
	<div class="empty-state">
		<Icon name="wifi-off" size={32} />
		<h3>Impossible de charger le flux</h3>
		<p>Vérifiez votre connexion et réessayez.</p>
	</div>
{:else}
	<!-- ═══ HÉRO EN-TÊTE ═══════════════════════════════════════════════════ -->
	<div class="hero" class:hero-visible={ready}>
		<div class="hero-accent"></div>
		<div class="hero-content">
			<div class="hero-top">
				<div>
					<h1 class="hero-greeting">{greeting} {$currentUser?.prenom}{#if lotLabel} <span class="hero-lot-inline">— {lotLabel}</span>{/if}{#if roleLabels} <span class="hero-role-inline">· {roleLabels}</span>{/if}</h1>
				</div>
			</div>
		</div>
	</div>

	<!-- ═══ CONSIGNES DE LA COPROPRIÉTÉ ═══════════════════════════════════ -->
	<a href="/api/admin/fiche-arrivant" target="_blank" class="consignes-card section-reveal" class:section-visible={ready} class:consignes-prominent={isLocataire} style="--delay:.05s">
		<div class="consignes-icon">📋</div>
		<div class="consignes-text">
			<strong class="consignes-titre">Consignes de la copropriété</strong>
			<span class="consignes-sub">Règlement intérieur, tri sélectif, accès, stationnement et contacts utiles</span>
		</div>
		<span class="consignes-arrow"><Icon name="chevron-right" size={18} /></span>
	</a>

	<!-- ═══ RAPPEL RELANCE SYNDIC (CS / Admin seulement) ═════════════════ -->
	{#if ($isCS || $isAdmin) && relanceSyndicCount > 0}
	<a href="/espace-cs#reporting-relance" class="consignes-card section-reveal" class:section-visible={ready} style="--delay:.07s;background:linear-gradient(135deg,#FEF3C7 0%,#FDE68A 100%);border-color:#F59E0B;border-left-color:#F59E0B">
		<div class="consignes-icon">🔔</div>
		<div class="consignes-text">
			<strong class="consignes-titre" style="color:#92400E">{relanceSyndicCount} ticket{relanceSyndicCount > 1 ? 's' : ''} syndic sans avancées depuis +1 mois</strong>
			<span class="consignes-sub" style="color:#78350F">Cliquer pour accéder à la relance dans l'Espace CS</span>
		</div>
		<span class="consignes-arrow" style="color:#92400E"><Icon name="chevron-right" size={18} /></span>
	</a>
	{/if}

	<!-- ═══ RACCOURCIS RAPIDES ═════════════════════════════════════════════ -->
	<nav class="quick-nav" class:section-visible={ready}>
		<a href="/tickets" class="quick-pill">
			<Icon name="ticket" size={14} /> Tickets
			{#if (countByType['ticket_ouvert'] ?? 0) > 0}<span class="quick-count">{countByType['ticket_ouvert']}</span>{/if}
		</a>
		<a href="/calendrier" class="quick-pill">
			<Icon name="calendar" size={14} /> Calendrier
		</a>
		<a href="/sondages" class="quick-pill">
			<Icon name="bar-chart-3" size={14} /> Sondages
			{#if (data.sante.sondages_actifs ?? 0) > 0}<span class="quick-count">{data.sante.sondages_actifs}</span>{/if}
		</a>
		<a href="/actualites" class="quick-pill">
			<Icon name="megaphone" size={14} /> Actualités
		</a>
		{#if $isCS || $isAdmin}
		<a href="/espace-cs" class="quick-pill quick-pill-cs">
			<Icon name="shield-check" size={14} /> Espace CS
			{#if (data.sante.validations_cs ?? 0) > 0}<span class="quick-count quick-count-urgent">{data.sante.validations_cs}</span>{/if}
			{#if (data.sante.tickets_relance_syndic ?? 0) > 0}<span class="quick-count quick-count-orange">{data.sante.tickets_relance_syndic} relance{(data.sante.tickets_relance_syndic ?? 0) > 1 ? 's' : ''}</span>{/if}
		</a>
		{/if}
	</nav>

	<!-- ═══ ALERTES URGENTES ══════════════════════════════════════════════ -->
	{#if ($isCS || $isAdmin) && (data.sante.tickets_relance_syndic ?? 0) > 0}
		<div class="section-reveal" class:section-visible={ready} style="--delay:.08s">
			<a href="/espace-cs?onglet=reporting&vue=relance" class="relance-alerte-card">
				<span class="relance-alerte-icon">🔔</span>
				<div class="relance-alerte-text">
					<strong>{data.sante.tickets_relance_syndic} ticket{(data.sante.tickets_relance_syndic ?? 0) > 1 ? 's' : ''} syndic à relancer</strong>
					<span>Sans avancée depuis plus d'1 mois — cliquez pour voir et envoyer la relance</span>
				</div>
				<span class="relance-alerte-arrow">→</span>
			</a>
		</div>
	{/if}
	{#if urgentItems.length > 0}
		<div class="section-reveal" class:section-visible={ready} style="--delay:.1s">
			{#each urgentItems.slice(0, 3) as u}
				{@const progress = urgencyProgress(u)}
				<fieldset class="urgence-fieldset"
					role="link" tabindex="0"
					on:click={() => goto(typeLink(u))}
					on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && goto(typeLink(u))}
				>
					<legend class="urgence-legend">🔴 URGENCE
						<span class="flux-type-chip" style="background:{TYPE_BG[u.type] ?? '#EAEDF1'};color:{TYPE_COLORS[u.type] ?? 'var(--color-border)'}">
							{TYPE_LABELS[u.type] ?? u.type}
						</span>
					</legend>
					<div class="urgence-content">
						<div class="urgence-title-row">
							<span class="urgence-icon">{u.icon}</span>
							<div class="urgence-title-col">
								<strong class="urgence-titre">{u.titre}</strong>
								{#if u.meta?.perimetre}<span class="urgence-perimetre">— {u.meta.perimetre}</span>{/if}
							</div>
						</div>
						{#if u.meta?.debut && u.meta?.fin}
							<p class="urgence-horaire">
								Aujourd'hui {fmtHeure(String(u.meta.debut))} → {fmtHeure(String(u.meta.fin))}
								{#if u.meta?.prestataire} · {u.meta.prestataire}{/if}
							</p>
						{:else if u.detail}
							<p class="urgence-horaire">{u.detail}</p>
						{/if}
						{#if u.meta?.concerne_mon_batiment}
							<p class="urgence-concerne">📍 Concerne votre bâtiment</p>
						{/if}
						{#if progress}
							<div class="urgence-progress-wrap">
								<div class="urgence-progress-track">
									<div class="urgence-progress-bar" class:urgence-active={progress.active} style="width:{progress.pct}%"></div>
								</div>
								<span class="urgence-progress-label">{progress.label}</span>
							</div>
						{/if}
					</div>
				</fieldset>
			{/each}
		</div>
	{/if}

	<!-- ═══ KPI SANTÉ RÉSIDENCE ═══════════════════════════════════════════ -->
	<div class="section-reveal" class:section-visible={ready} style="--delay:.15s">
		<h2 class="section-title"><Icon name="activity" size={16} /> Santé résidence</h2>
		<div class="kpi-grid">
			<a href="/tickets" class="kpi-card card">
				<div class="kpi-icon-zone" style="background:#EFF6FF;color:#3B82F6">
					<Icon name="ticket" size={22} />
				</div>
				<div class="kpi-text-zone">
					<span class="kpi-value">{data.sante.tickets_ouverts}</span>
					<span class="kpi-label">Tickets ouverts</span>
					{#if data.sante.tickets_urgents > 0}
						<span class="badge badge-red kpi-badge">dont {data.sante.tickets_urgents} urgent{data.sante.tickets_urgents > 1 ? 's' : ''}</span>
					{/if}
					<span class="kpi-link">Voir →</span>
				</div>
			</a>
			<div class="kpi-card card">
				<div class="kpi-icon-zone" style="background:#FFFBEB;color:#F59E0B">
					<Icon name="clock" size={22} />
				</div>
				<div class="kpi-text-zone">
					<span class="kpi-value">{data.sante.resolution_moyenne_heures != null ? `${data.sante.resolution_moyenne_heures}h` : '—'}</span>
					<span class="kpi-label">Résolution moy.</span>
				</div>
			</div>
			<a href="/sondages" class="kpi-card card">
				<div class="kpi-icon-zone" style="background:#F5F3FF;color:#8B5CF6">
					<Icon name="bar-chart-3" size={22} />
				</div>
				<div class="kpi-text-zone">
					<span class="kpi-value">{data.sante.sondages_actifs}</span>
					<span class="kpi-label">Sondages actifs</span>
					{#if data.sante.sondages_actifs > 0}<span class="kpi-link">Voter →</span>{/if}
				</div>
			</a>
		</div>
	</div>

	<!-- ═══ KANBAN ══════════════════════════════════════════════════════════ -->
	<div class="section-reveal" class:section-visible={ready} style="--delay:.2s">
		<div class="kb-header">
			<h2 class="section-title" style="margin:0">&#x1F4CB; Kanban</h2>
			<a href="/calendrier" class="kb-voir-lien">Voir le Kanban complet →</a>
		</div>

		{#if dashKanbanEvs.length === 0 && !loading}
			<p class="kb-vide">Aucun dossier actif pour {_kanbanYear}.</p>
		{:else}
			<!-- Desktop : grille de colonnes -->
			<div class="kb-grid kb-desktop">
				{#each dashKanbanCols as col}
					<div class="kb-col" class:kb-col-vide={col.items.length === 0}>
						<div class="kb-col-head" style="border-top-color:{col.color}">
							<span class="kb-col-label" style="color:{col.color}">{col.label}</span>
							{#if col.total > 0}
								<span class="kb-col-count" style="background:{col.color}1a;color:{col.color}">
									{col.total > 5 ? `+${col.total - 5} / ${col.total}` : col.total}
								</span>
							{/if}
						</div>
						{#if col.items.length === 0}
							<p class="kb-vide-col">—</p>
						{:else}
							{#each col.items as item (item.id)}
								<div class="kb-item"
									role="button" tabindex="0"
									on:click={() => goto(`/calendrier#ev-${item.id}`)}
									on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && goto(`/calendrier#ev-${item.id}`)}>
									<span class="kb-item-icon">{EV_ICONS[item.type] ?? '\u{1F4CC}'}</span>
									<div class="kb-item-text">
										<span class="kb-item-titre">{item.titre}</span>
										{#if item.perimetre && item.perimetre !== 'résidence'}
											<span class="kb-item-perim">&#x1F539; {dashKanbanPerimLabel(item.perimetre)}</span>
										{/if}
									</div>
								</div>
							{/each}
						{/if}
					</div>
				{/each}
			</div>

			<!-- Mobile : une colonne à la fois (colonnes vides masquées) -->
			{#if mobileKanbanCols.length > 0}
				<div class="kb-mobile">
					<div class="kb-mobile-nav">
						<button class="kb-nav-btn"
							disabled={mobileKanbanIdx === 0}
							on:click={() => mobileKanbanIdx--}
							aria-label="Colonne précédente">‹</button>
						<div class="kb-mobile-nav-center">
							<span class="kb-mobile-col-label" style="color:{mobileKanbanCurrent?.color}">
								{mobileKanbanCurrent?.label}
							</span>
							<span class="kb-mobile-pos">{mobileKanbanIdx + 1} / {mobileKanbanCols.length}</span>
						</div>
						<button class="kb-nav-btn"
							disabled={mobileKanbanIdx >= mobileKanbanCols.length - 1}
							on:click={() => mobileKanbanIdx++}
							aria-label="Colonne suivante">›</button>
					</div>
					{#if mobileKanbanCurrent}
						<div class="kb-mobile-items">
							{#each mobileKanbanCurrent.items as item (item.id)}
								<div class="kb-item"
									role="button" tabindex="0"
									on:click={() => goto(`/calendrier#ev-${item.id}`)}
									on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && goto(`/calendrier#ev-${item.id}`)}>
									<span class="kb-item-icon">{EV_ICONS[item.type] ?? '\u{1F4CC}'}</span>
									<div class="kb-item-text">
										<span class="kb-item-titre">{item.titre}</span>
										{#if item.perimetre && item.perimetre !== 'résidence'}
											<span class="kb-item-perim">&#x1F539; {dashKanbanPerimLabel(item.perimetre)}</span>
										{/if}
									</div>
								</div>
							{/each}
							{#if mobileKanbanCurrent.total > 5}
								<p class="kb-mobile-plus">
									+{mobileKanbanCurrent.total - 5} élément{mobileKanbanCurrent.total - 5 > 1 ? 's' : ''} — <a href="/calendrier" class="kb-mobile-plus-lien">voir tout</a>
								</p>
							{/if}
						</div>
					{/if}
					<a href="/calendrier" class="kb-mobile-lien">Voir le Kanban complet →</a>
				</div>
			{/if}
		{/if}
	</div>

	<!-- ═══ FIL D'ACTIVITÉ ════════════════════════════════════════════════ -->
	<div class="section-reveal" class:section-visible={ready} style="--delay:.25s">
		<h2 class="section-title" style="margin-top:1.5rem"><Icon name="newspaper" size={16} /> Fil d'activité</h2>
	</div>

	{#if recentItems.length === 0 && olderItems.length === 0}
		<div class="empty-state">
			<Icon name="inbox" size={32} />
			<h3>Aucune activité récente</h3>
			<p>Les mouvements de la résidence apparaîtront ici.</p>
		</div>
	{:else}
		<!-- Fil récent (<30 jours) -->
		<div class="flux-timeline section-reveal" class:section-visible={ready} style="--delay:.3s">
			{#each recentDayGroups as group}
				<div class="flux-day-label">{group.label}</div>
				{#each group.items as item}
					{@const isExpanded = expandedItem === item.id}
					{@const typeColor = TYPE_COLORS[item.type] ?? 'var(--color-border)'}
					<div
						class="flux-item"
						class:flux-urgent={item.type === 'ticket_ouvert' && item.badges?.includes('urgence')}
						class:flux-expanded={isExpanded}
					>
						<div class="flux-dot" style="background:{typeColor}"></div>
						{#if isNew(item)}<div class="flux-new-dot"></div>{/if}
						<div
							class="flux-card card"
							style="border-left-color:{typeColor}"
							role="button"
							tabindex="0"
							on:click={() => toggleItem(item.id)}
							on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && toggleItem(item.id)}
						>
							<div class="flux-card-top">
								<div class="flux-card-top-left">
									<span class="flux-type-chip" style="background:{TYPE_BG[item.type] ?? '#EAEDF1'};color:{typeColor}">{TYPE_LABELS[item.type] ?? item.type}</span>
									{#if isNew(item)}<span class="new-badge">NEW</span>{/if}
								</div>
								<div class="flux-card-top-right">
									<span class="flux-heure">{fmtDatetimeShort(item.date)}</span>
									<span class="chevron" class:open={isExpanded}>›</span>
								</div>
							</div>
							<div class="flux-card-body">
								<span class="flux-icon">{item.icon}</span>
								<div class="flux-card-text">
									<span class="flux-titre">{item.titre}</span>
									{#if !isExpanded && item.detail}
										<p class="flux-detail clamp-2">{item.detail}</p>
									{/if}
								</div>
							</div>
							{#if item.badges.length > 0 || (item.meta?.perimetre && item.meta.perimetre !== 'Copropriété entière')}
								<div class="flux-badges">
									{#if item.meta?.perimetre && item.meta.perimetre !== 'Copropriété entière'}
										<span class="badge badge-blue" style="font-size:.7rem">🔹 {item.meta.perimetre}</span>
									{/if}
									{#each item.badges as b}
										<span class="badge {badgeClass(item.type, b)}">{b}</span>
									{/each}
								</div>
							{/if}
							{#if isExpanded}
								<!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
								<div class="flux-body" on:click|stopPropagation>
									{#if item.meta?.lieu}<p class="flux-meta-line">📍 {item.meta.lieu}</p>{/if}
									{#if item.meta?.perimetre && item.meta.perimetre !== 'Copropriété entière'}<p class="flux-meta-line">🔹 {item.meta.perimetre}</p>{/if}
									{#if item.meta?.prestataire}<p class="flux-meta-line">🔧 {item.meta.prestataire}</p>{/if}
									{#if item.meta?.debut && item.meta?.fin}
										<p class="flux-meta-line">🕐 {fmtDatetimeShort(String(item.meta.debut))} → {fmtDatetimeShort(String(item.meta.fin))}</p>
									{/if}
									{#if item.meta?.auteur}<p class="flux-meta-line">✍️ {item.meta.auteur}</p>{/if}
									{#if item.meta?.statut}
										<p class="flux-meta-line">
											État :
											<span class="badge {item.meta.statut === 'résolu' || item.meta.statut === 'réalisé' ? 'badge-green' : item.meta.statut === 'en_cours' || item.meta.statut === 'ouvert' ? 'badge-orange' : 'badge-gray'}">{item.meta.statut}</span>
										</p>
									{/if}
									{#if item.meta?.full_html}
										<div class="flux-full-content rich-content">{@html safeHtml(String(item.meta.full_html))}</div>
									{:else if item.meta?.description}
										<p class="flux-full-content">{item.meta.description}</p>
									{:else if item.detail}
										<p class="flux-full-content">{item.detail}</p>
									{/if}
									{#if item.type === 'ticket_mis_a_jour' && item.meta?.evol_contenu}
										<div class="flux-reaction">
											<span class="flux-reaction-icon">💬</span>
											<div class="flux-reaction-body">
												{#if item.meta?.evol_auteur}<span class="flux-reaction-auteur">{item.meta.evol_auteur}</span>{/if}
												<p class="flux-reaction-text">{item.meta.evol_contenu}</p>
											</div>
										</div>
									{/if}
									{#if item.meta?.image_url}
										<img src={String(item.meta.image_url)} alt="" class="flux-image" loading="lazy" />
									{/if}
									{#if (item.meta?.photos_urls as string[] | undefined)?.length}
										<div class="flux-photos" style="margin:.5rem 0;display:flex;gap:.5rem;flex-wrap:wrap">
											{#each (item.meta.photos_urls as string[]) as photoUrl}
												<a href={photoUrl} target="_blank" rel="noopener">
													<img src={photoUrl} alt="Photo" style="max-width:120px;max-height:90px;border-radius:6px;object-fit:cover;border:1px solid var(--color-border)" loading="lazy" />
												</a>
											{/each}
										</div>
									{/if}
									{#if (item.meta?.fichiers_urls as string[] | undefined)?.length}
										<div class="flux-photos" style="margin:.5rem 0;display:flex;gap:.5rem;flex-wrap:wrap">
											{#each (item.meta.fichiers_urls as string[]) as fichierUrl}
												<a href={fichierUrl} target="_blank" rel="noopener">
													<img src={fichierUrl} alt="Pièce jointe" style="max-width:120px;max-height:90px;border-radius:6px;object-fit:cover;border:1px solid var(--color-border)" loading="lazy" />
												</a>
											{/each}
										</div>
									{/if}
									<a href={typeLink(item)} class="flux-link">{typeVoirLabel(item)}</a>
								</div>
							{/if}
						</div>
					</div>
				{/each}
			{/each}
		</div>

		<!-- Accordéon : anciens (>30 jours) -->
		{#if olderItems.length > 0}
			<div class="section-reveal" class:section-visible={ready} style="--delay:.35s">
				<button
					class="older-toggle"
					on:click={() => olderOpen = !olderOpen}
					aria-expanded={olderOpen}
				>
					<Icon name={olderOpen ? 'chevron-down' : 'chevron-right'} size={16} />
					<span>Activité plus ancienne</span>
					<span class="older-count">{olderItems.length}</span>
				</button>
				{#if olderOpen}
					<div class="flux-timeline older-timeline">
						{#each olderDayGroups as group}
							<div class="flux-day-label">{group.label}</div>
							{#each group.items as item}
								{@const isExpanded = expandedItem === item.id}
								{@const typeColor = TYPE_COLORS[item.type] ?? 'var(--color-border)'}
								<div class="flux-item" class:flux-expanded={isExpanded}>
									<div class="flux-dot" style="background:{typeColor}"></div>
									<div
										class="flux-card card"
										style="border-left-color:{typeColor}"
										role="button"
										tabindex="0"
										on:click={() => toggleItem(item.id)}
										on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && toggleItem(item.id)}
									>
										<div class="flux-card-top">
											<span class="flux-type-chip" style="background:{TYPE_BG[item.type] ?? '#EAEDF1'};color:{typeColor}">{TYPE_LABELS[item.type] ?? item.type}</span>
											<div class="flux-card-top-right">
												<span class="flux-heure">{fmtDatetimeShort(item.date)}</span>
												<span class="chevron" class:open={isExpanded}>›</span>
											</div>
										</div>
										<div class="flux-card-body">
											<span class="flux-icon">{item.icon}</span>
											<div class="flux-card-text">
												<span class="flux-titre">{item.titre}</span>
												{#if !isExpanded && item.detail}
													<p class="flux-detail clamp-2">{item.detail}</p>
												{/if}
											</div>
										</div>
										{#if item.meta?.perimetre && item.meta.perimetre !== 'Copropriété entière'}
											<div class="flux-badges">
												<span class="badge badge-blue" style="font-size:.7rem">🔹 {item.meta.perimetre}</span>
											</div>
										{/if}
										{#if isExpanded}										<!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->											<div class="flux-body" on:click|stopPropagation>
												{#if item.meta?.lieu}<p class="flux-meta-line">📍 {item.meta.lieu}</p>{/if}
												{#if item.meta?.perimetre && item.meta.perimetre !== 'Copropriété entière'}<p class="flux-meta-line">🔹 {item.meta.perimetre}</p>{/if}
												{#if item.meta?.prestataire}<p class="flux-meta-line">🔧 {item.meta.prestataire}</p>{/if}
												{#if item.meta?.full_html}
													<div class="flux-full-content rich-content">{@html safeHtml(String(item.meta.full_html))}</div>
												{:else if item.detail}
													<p class="flux-full-content">{item.detail}</p>
												{/if}
												{#if item.meta?.image_url}
													<img src={String(item.meta.image_url)} alt="" class="flux-image" loading="lazy" />
												{/if}
												{#if (item.meta?.photos_urls as string[] | undefined)?.length}
													<div class="flux-photos" style="margin:.5rem 0;display:flex;gap:.5rem;flex-wrap:wrap">
														{#each (item.meta.photos_urls as string[]) as photoUrl}
															<a href={photoUrl} target="_blank" rel="noopener">
																<img src={photoUrl} alt="Photo" style="max-width:120px;max-height:90px;border-radius:6px;object-fit:cover;border:1px solid var(--color-border)" loading="lazy" />
															</a>
														{/each}
													</div>
												{/if}
												{#if (item.meta?.fichiers_urls as string[] | undefined)?.length}
													<div class="flux-photos" style="margin:.5rem 0;display:flex;gap:.5rem;flex-wrap:wrap">
														{#each (item.meta.fichiers_urls as string[]) as fichierUrl}
															<a href={fichierUrl} target="_blank" rel="noopener">
																<img src={fichierUrl} alt="Pièce jointe" style="max-width:120px;max-height:90px;border-radius:6px;object-fit:cover;border:1px solid var(--color-border)" loading="lazy" />
															</a>
														{/each}
													</div>
												{/if}
												<a href={typeLink(item)} class="flux-link">Voir la page complète →</a>
											</div>
										{/if}
									</div>
								</div>
							{/each}
						{/each}
					</div>
				{/if}
			</div>
		{/if}
	{/if}
{/if}

<script lang="ts" context="module">
	function badgeClass(type: string, badge: string): string {
		const b = badge.toLowerCase();
		if (b.includes('résolu') || b.includes('réalisé') || b.includes('accepté')) return 'badge-green';
		if (b.includes('urgent') || b.includes('refusé')) return 'badge-red';
		if (b.includes('en cours') || b.includes('en attente') || b === 'panne') return 'badge-orange';
		if (b.includes('clôturé')) return 'badge-gray';
		if (b.startsWith('#')) return 'badge-gray';
		if (type === 'sondage_ouvert') return 'badge-purple';
		return 'badge-blue';
	}
</script>

<style>
	/* ═══ SKELETON LOADING ═══════════════════════════════════════════════ */
	@keyframes shimmer {
		0% { background-position: -400px 0; }
		100% { background-position: 400px 0; }
	}
	.skeleton-wrap { display: flex; flex-direction: column; gap: .75rem; }
	.skel {
		border-radius: var(--radius);
		background: linear-gradient(90deg, var(--color-border) 25%, #e8edf3 37%, var(--color-border) 63%);
		background-size: 800px 100%; animation: shimmer 1.4s ease infinite;
	}
	.skel-header { height: 2rem; width: 60%; }
	.skel-subtitle { height: 1rem; width: 40%; }
	.skel-row { display: flex; gap: .75rem; }
	.skel-kpi { height: 5rem; flex: 1; }
	.skel-card { height: 4.5rem; }
	.skel-card.short { width: 70%; }

	/* ═══ HERO EN-TÊTE ═══════════════════════════════════════════════════ */
	.hero {
		margin: -1rem -1rem 0; padding: 1.5rem 1.25rem 1.25rem;
		background: linear-gradient(135deg, var(--color-primary) 0%, #2a4f7a 100%);
		border-radius: 0 0 var(--radius) var(--radius);
		position: relative; overflow: hidden;
		opacity: 0; transform: translateY(-10px);
		transition: opacity .35s ease, transform .35s ease;
	}
	.hero.hero-visible { opacity: 1; transform: translateY(0); }
	.hero-accent {
		position: absolute; top: 0; left: 0; right: 0; height: 4px;
		background: linear-gradient(90deg, var(--color-accent) 0%, var(--color-secondary) 50%, var(--color-accent) 100%);
	}
	.hero-content { position: relative; z-index: 1; }
	.hero-top { display: flex; justify-content: space-between; align-items: flex-start; }
	.hero-greeting { font-size: 1.35rem; font-weight: 700; color: var(--color-text-inverse); margin: 0; line-height: 1.3; }
	.hero-lot-inline { font-size: .85rem; font-weight: 400; color: rgba(255,255,255,.75); }
	.hero-role-inline { font-size: .75rem; font-weight: 400; color: rgba(255,255,255,.55); letter-spacing: .02em; }

	/* ═══ CONSIGNES DE LA COPROPRIÉTÉ ═══════════════════════════════════ */
	.consignes-card {
		display: flex; align-items: center; gap: .75rem;
		margin: .75rem 0; padding: .75rem 1rem;
		border-radius: var(--radius);
		background: linear-gradient(135deg, #f0f7ff 0%, #e8f4f8 100%);
		border: 1px solid var(--color-primary);
		border-left: 4px solid var(--color-primary);
		text-decoration: none; color: inherit;
		transition: box-shadow .15s, transform .1s;
		opacity: 0; transform: translateY(8px);
		transition: opacity .3s ease var(--delay, 0s), transform .3s ease var(--delay, 0s), box-shadow .15s;
	}
	.consignes-card.section-visible { opacity: 1; transform: translateY(0); }
	.consignes-card:hover { box-shadow: var(--shadow); transform: translateY(-1px); }
	.consignes-card.consignes-prominent {
		background: linear-gradient(135deg, #FEF3C7 0%, #FDE68A 100%);
		border-color: #F59E0B;
		border-left-color: #F59E0B;
		animation: consignes-pulse 3s ease-in-out infinite;
	}
	@keyframes consignes-pulse {
		0%, 100% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0); }
		50% { box-shadow: 0 0 0 4px rgba(245, 158, 11, .15); }
	}
	.consignes-icon { font-size: 1.5rem; flex-shrink: 0; }
	.consignes-text { flex: 1; min-width: 0; }
	.consignes-titre { font-size: .88rem; font-weight: 600; color: var(--color-primary); display: block; }
	.consignes-prominent .consignes-titre { color: #92400E; }
	.consignes-sub { font-size: .75rem; color: var(--color-text-muted); line-height: 1.3; }
	.consignes-prominent .consignes-sub { color: #78350F; }
	.consignes-arrow { flex-shrink: 0; color: var(--color-primary); opacity: .6; }
	.consignes-prominent .consignes-arrow { color: #92400E; }

	/* ═══ RACCOURCIS RAPIDES ═════════════════════════════════════════════ */
	.quick-nav {
		display: flex; gap: .5rem; flex-wrap: wrap; margin: .75rem 0; padding: 0;
		opacity: 0; transform: translateY(8px);
		transition: opacity .3s ease .08s, transform .3s ease .08s;
	}
	.quick-nav.section-visible { opacity: 1; transform: translateY(0); }
	.quick-pill {
		display: inline-flex; align-items: center; gap: .35rem;
		padding: .4rem .8rem; border-radius: 2rem;
		background: var(--color-surface); border: 1px solid var(--color-border);
		font-size: .78rem; font-weight: 500; color: var(--color-text); text-decoration: none;
		transition: border-color .15s, box-shadow .15s, background .15s; white-space: nowrap;
	}
	.quick-pill:hover { border-color: var(--color-primary); box-shadow: var(--shadow-sm); background: var(--color-primary-light); }
	.quick-count {
		background: var(--color-primary); color: #fff;
		font-size: .65rem; font-weight: 700;
		padding: .05rem .4rem; border-radius: 1rem; line-height: 1.3; min-width: 1.1rem; text-align: center;
	}
	.quick-pill-cs { border-color: #F59E0B; }
	.quick-pill-cs:hover { border-color: #D97706; background: #FFFBEB; }
	.quick-count-urgent { background: #DC2626; }
	.quick-count-orange { background: #D97706; }

	/* ═══ ALERTE RELANCE SYNDIC ══════════════════════════════════════════ */
	.relance-alerte-card {
		display: flex; align-items: center; gap: .75rem;
		padding: .75rem 1rem; border-radius: var(--radius);
		background: #FFF7ED; border: 1.5px solid #F59E0B;
		color: #92400E; text-decoration: none;
		transition: background .15s, border-color .15s;
		margin-bottom: .5rem;
	}
	.relance-alerte-card:hover { background: #FEF3C7; border-color: #D97706; }
	.relance-alerte-icon { font-size: 1.3rem; flex-shrink: 0; }
	.relance-alerte-text { display: flex; flex-direction: column; gap: .1rem; flex: 1; }
	.relance-alerte-text strong { font-size: .9rem; }
	.relance-alerte-text span { font-size: .78rem; color: #B45309; }
	.relance-alerte-arrow { font-size: 1.1rem; flex-shrink: 0; opacity: .7; }

	/* ═══ RÉACTION INLINE (ticket_mis_a_jour) ═══════════════════════════ */
	.flux-reaction {
		display: flex; gap: .5rem; align-items: flex-start;
		margin: .6rem 0 .3rem;
		padding: .5rem .75rem; border-radius: 6px;
		background: #EEF2F7; border-left: 3px solid var(--color-primary);
		font-size: .82rem;
	}
	.flux-reaction-icon { flex-shrink: 0; font-size: .85rem; margin-top: .1rem; }
	.flux-reaction-body { display: flex; flex-direction: column; gap: .15rem; min-width: 0; }
	.flux-reaction-auteur { font-size: .75rem; font-weight: 600; color: var(--color-primary); }
	.flux-reaction-text { margin: 0; color: var(--color-text); line-height: 1.45; }

	/* ═══ ANIMATIONS SECTIONS ═══════════════════════════════════════════ */
	.section-reveal {
		opacity: 0; transform: translateY(12px);
		transition: opacity .35s ease var(--delay, 0s), transform .35s ease var(--delay, 0s);
	}
	.section-reveal.section-visible { opacity: 1; transform: translateY(0); }

	/* ═══ ALERTES URGENTES ═════════════════════════════════════════════ */
	.urgence-fieldset {
		border: 2px solid var(--color-danger, #dc2626);
		border-radius: var(--radius); padding: 1rem 1.15rem .9rem;
		margin-bottom: 1rem; background: #fef2f2; position: relative;
		cursor: pointer; transition: box-shadow .15s, background .12s;
	}
	.urgence-fieldset:hover { background: #fee2e2; box-shadow: 0 2px 8px rgba(220,38,38,.15); }
	.urgence-fieldset:focus-visible { outline: 2px solid #dc2626; outline-offset: 2px; }
	.urgence-legend { font-size: .72rem; font-weight: 700; letter-spacing: .06em; color: #dc2626; background: #fef2f2; padding: 0 .5rem; text-transform: uppercase; }
	.urgence-content { display: flex; flex-direction: column; gap: .45rem; }
	.urgence-title-row { display: flex; align-items: center; gap: .6rem; }
	.urgence-icon { font-size: 1.15rem; flex-shrink: 0; }
	.urgence-title-col { display: flex; align-items: baseline; gap: .35rem; flex-wrap: wrap; }
	.urgence-titre { font-size: .92rem; color: var(--color-text); }
	.urgence-perimetre { font-size: .82rem; color: var(--color-text-muted); }
	.urgence-horaire { font-size: .82rem; color: var(--color-text-muted); margin: 0; }
	.urgence-concerne { font-size: .82rem; color: var(--color-primary); font-weight: 500; margin: 0; }
	.urgence-progress-wrap { display: flex; align-items: center; gap: .6rem; margin-top: .15rem; }
	.urgence-progress-track { flex: 1; height: 6px; border-radius: 3px; background: var(--color-border); overflow: hidden; }
	.urgence-progress-bar { height: 100%; border-radius: 3px; background: var(--color-text-muted); transition: width .4s ease; }
	.urgence-progress-bar.urgence-active { background: #dc2626; }
	.urgence-progress-label { font-size: .75rem; color: var(--color-text-muted); white-space: nowrap; }

	/* ═══ KPI CARDS ═════════════════════════════════════════════════════ */
	.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(160px, 100%), 1fr)); gap: .75rem; margin-bottom: 1.25rem; }
	.kpi-card { display: flex; align-items: stretch; text-decoration: none; color: inherit; overflow: hidden; padding: 0; transition: box-shadow .15s, transform .1s; }
	.kpi-card:hover { box-shadow: var(--shadow); transform: translateY(-1px); }
	.kpi-icon-zone { width: 3.5rem; flex-shrink: 0; display: flex; align-items: center; justify-content: center; }
	.kpi-text-zone { flex: 1; padding: .65rem .75rem; display: flex; flex-direction: column; gap: .1rem; }
	.kpi-value { font-size: 1.4rem; font-weight: 700; color: var(--color-primary); line-height: 1.1; }
	.kpi-label { font-size: .78rem; color: var(--color-text-muted); }
	.kpi-badge { font-size: .62rem; width: fit-content; margin-top: .15rem; }
	.kpi-link { font-size: .72rem; color: var(--color-primary); font-weight: 500; margin-top: auto; }

	/* ═══ KANBAN WIDGET ═════════════════════════════════════════════════ */
	.kb-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: .6rem; }
	.kb-voir-lien { font-size: .78rem; color: var(--color-primary); font-weight: 500; text-decoration: none; white-space: nowrap; }
	.kb-voir-lien:hover { text-decoration: underline; }
	.kb-vide { font-size: .85rem; color: var(--color-text-muted); text-align: center; padding: 1rem 0; margin: 0; }

	/* Grille desktop */
	.kb-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(130px, 100%), 1fr));
		gap: .45rem;
		margin-bottom: 1.25rem;
	}
	.kb-col {
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		overflow: hidden;
		transition: opacity .15s;
	}
	.kb-col-vide { opacity: .4; }
	.kb-col-head {
		display: flex; align-items: center; justify-content: space-between;
		padding: .35rem .6rem;
		background: var(--color-bg);
		border-top: 3px solid transparent;
		border-bottom: 1px solid var(--color-border);
	}
	.kb-col-label { font-size: .68rem; font-weight: 700; text-transform: uppercase; letter-spacing: .05em; }
	.kb-col-count { font-size: .62rem; font-weight: 700; padding: .1rem .4rem; border-radius: 1rem; }
	.kb-vide-col { font-size: .78rem; color: var(--color-text-muted); text-align: center; padding: .65rem .5rem; margin: 0; }

	/* Item commun desktop + mobile */
	.kb-item {
		display: flex; align-items: flex-start; gap: .4rem;
		padding: .45rem .6rem;
		border-top: 1px solid var(--color-border);
		cursor: pointer;
		transition: background .12s;
	}
	.kb-item:first-of-type { border-top: none; }
	.kb-item:hover { background: var(--color-bg); }
	.kb-item:focus-visible { outline: 2px solid var(--color-primary); outline-offset: -2px; }
	.kb-item-icon { flex-shrink: 0; font-size: .85rem; line-height: 1.3; }
	.kb-item-text { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: .1rem; }
	.kb-item-titre { font-size: .8rem; color: var(--color-text); line-height: 1.3; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
	.kb-item-perim { font-size: .68rem; color: var(--color-text-muted); }

	/* Mobile */
	.kb-mobile { display: none; }
	.kb-mobile-nav {
		display: flex; align-items: center; justify-content: space-between; gap: .5rem;
		padding: .5rem .75rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: var(--radius) var(--radius) 0 0;
		border-bottom: none;
	}
	.kb-mobile-nav-center { display: flex; flex-direction: column; align-items: center; gap: .08rem; flex: 1; }
	.kb-mobile-col-label { font-size: .82rem; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; }
	.kb-mobile-pos { font-size: .66rem; color: var(--color-text-muted); }
	.kb-nav-btn {
		background: none; border: 1px solid var(--color-border); border-radius: var(--radius);
		width: 2rem; height: 2rem; flex-shrink: 0;
		font-size: 1.25rem; font-weight: 700; color: var(--color-text);
		cursor: pointer; display: flex; align-items: center; justify-content: center;
		transition: background .12s, border-color .12s; line-height: 1;
	}
	.kb-nav-btn:hover:not(:disabled) { background: var(--color-bg); border-color: var(--color-primary); }
	.kb-nav-btn:disabled { opacity: .3; cursor: default; }
	.kb-mobile-items {
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0 0 var(--radius) var(--radius);
		overflow: hidden;
	}
	.kb-mobile-plus {
		font-size: .74rem; color: var(--color-text-muted);
		text-align: center; padding: .4rem .75rem; margin: 0;
		border-top: 1px solid var(--color-border);
	}
	.kb-mobile-plus-lien { color: var(--color-primary); text-decoration: none; font-weight: 500; }
	.kb-mobile-plus-lien:hover { text-decoration: underline; }
	.kb-mobile-lien {
		display: block; text-align: center; padding: .55rem 1rem; margin-top: .45rem;
		font-size: .8rem; color: var(--color-primary); font-weight: 500; text-decoration: none;
		background: var(--color-surface); border: 1px solid var(--color-border);
		border-radius: var(--radius); transition: background .12s;
	}
	.kb-mobile-lien:hover { background: var(--color-primary-light); }

	/* ═══ NEW BADGE ═════════════════════════════════════════════════════ */
	@keyframes new-pulse {
		0%, 100% { opacity: 1; }
		50% { opacity: .7; }
	}
	.new-badge {
		font-size: .55rem; font-weight: 700; letter-spacing: .06em;
		background: #EF4444; color: #fff;
		padding: .1rem .35rem; border-radius: .2rem;
		animation: new-pulse 2s ease-in-out infinite;
		flex-shrink: 0; text-transform: uppercase;
	}

	/* ═══ CHEVRON ═══════════════════════════════════════════════════════ */
	.chevron {
		font-size: 1.1rem; font-weight: 700; color: var(--color-text-muted);
		transition: transform .2s ease; display: inline-block; flex-shrink: 0;
		line-height: 1; user-select: none;
	}
	.chevron.open { transform: rotate(90deg); }

	/* ═══ FLUX TIMELINE ═════════════════════════════════════════════════ */
	.flux-timeline { position: relative; padding-left: 1.5rem; }
	.flux-timeline::before {
		content: ''; position: absolute; left: .45rem; top: 1.5rem; bottom: .5rem;
		width: 2px; background: var(--color-border); border-radius: 1px;
	}
	.flux-day-label {
		position: relative; font-size: .72rem; font-weight: 700; text-transform: uppercase;
		letter-spacing: .06em; color: var(--color-text-muted); padding: .9rem 0 .35rem; margin-left: -.15rem;
	}
	.flux-item {
		display: flex; align-items: flex-start; gap: .75rem;
		color: inherit; position: relative; margin-bottom: .5rem;
	}
	.flux-dot {
		width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; margin-top: .85rem;
		position: absolute; left: -1.35rem;
		border: 2px solid var(--color-surface); box-shadow: 0 0 0 2px var(--color-border); z-index: 1;
	}
	.flux-new-dot {
		position: absolute; left: -1.7rem; top: .55rem;
		width: 18px; height: 18px; border-radius: 50%;
		background: rgba(239, 68, 68, .15);
		animation: new-dot-pulse 2s ease-in-out infinite; z-index: 0;
	}
	@keyframes new-dot-pulse {
		0%, 100% { transform: scale(1); opacity: .6; }
		50% { transform: scale(1.6); opacity: 0; }
	}
	.flux-card {
		flex: 1; padding: .7rem .9rem;
		transition: box-shadow .15s, border-left-color .15s;
		border-left: 4px solid var(--color-border);
		cursor: pointer;
	}
	.flux-card:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px; }
	.flux-item:hover .flux-card { box-shadow: var(--shadow); }
	.flux-item.flux-urgent .flux-card { border-left-color: var(--color-danger) !important; }
	.flux-item.flux-expanded .flux-card { box-shadow: var(--shadow); }

	.flux-card-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: .35rem; }
	.flux-card-top-left { display: flex; align-items: center; gap: .4rem; }
	.flux-card-top-right { display: flex; align-items: center; gap: .5rem; }
	.flux-type-chip {
		font-size: .65rem; font-weight: 600; text-transform: uppercase; letter-spacing: .04em;
		padding: .12rem .5rem; border-radius: 1rem;
	}
	.flux-heure { font-size: .72rem; color: var(--color-text-muted); white-space: nowrap; }
	.flux-card-body { display: flex; align-items: flex-start; gap: .5rem; }
	.flux-icon { font-size: 1.05rem; flex-shrink: 0; line-height: 1; margin-top: .1rem; }
	.flux-card-text { flex: 1; min-width: 0; }
	.flux-titre { font-size: .88rem; font-weight: 500; line-height: 1.35; display: block; }
	.flux-detail { font-size: .8rem; color: var(--color-text-muted); margin: .15rem 0 0; line-height: 1.4; }
	.clamp-2 { display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
	.flux-badges { display: flex; gap: .3rem; flex-wrap: wrap; margin-top: .35rem; }

	/* ═══ FLUX BODY (expanded) ══════════════════════════════════════════ */
	.flux-body {
		border-top: 1px solid var(--color-border);
		padding: .75rem .5rem .75rem 1.7rem;
		margin-top: .5rem;
	}
	.flux-meta-line { font-size: .82rem; color: var(--color-text-muted); margin: .15rem 0; }
	.flux-full-content { font-size: .85rem; line-height: 1.55; margin: .5rem 0; }
	.flux-image { max-width: 100%; max-height: 200px; border-radius: var(--radius); margin-top: .5rem; object-fit: cover; }
	.flux-link { font-size: .78rem; color: var(--color-primary); font-weight: 500; text-decoration: none; display: inline-block; margin-top: .5rem; }
	.flux-link:hover { text-decoration: underline; }

	/* ═══ ACCORDÉON ANCIENS ═════════════════════════════════════════════ */
	.older-toggle {
		display: flex; align-items: center; gap: .5rem;
		width: 100%; padding: .7rem 1rem;
		background: var(--color-surface); border: 1px solid var(--color-border);
		border-radius: var(--radius); cursor: pointer;
		font-size: .82rem; font-weight: 500; color: var(--color-text-muted);
		transition: background .15s, border-color .15s;
		margin-bottom: .75rem;
	}
	.older-toggle:hover { background: var(--color-bg); border-color: var(--color-primary); }
	.older-count {
		background: var(--color-border); color: var(--color-text-muted);
		font-size: .65rem; font-weight: 700; padding: .1rem .4rem; border-radius: 1rem;
	}
	.older-timeline { opacity: .85; }

	/* ═══ RESPONSIVE ════════════════════════════════════════════════════ */
	@media (min-width: 768px) {
		.kb-mobile { display: none !important; }
	}
	@media (max-width: 767px) {
		.hero { margin: -.75rem -.75rem 0; padding: 1.25rem 1rem 1rem; }
		.kpi-grid { grid-template-columns: 1fr; }
		.quick-nav { gap: .35rem; }
		.quick-pill { font-size: .72rem; padding: .35rem .65rem; }
		.flux-timeline { padding-left: 1.25rem; }
		.flux-timeline::before { left: .35rem; }
		.flux-dot { left: -1.1rem; width: 8px; height: 8px; }
		.flux-new-dot { left: -1.4rem; width: 14px; height: 14px; }
		.consignes-card { gap: .5rem; padding: .6rem .75rem; }
		.consignes-icon { font-size: 1.2rem; }
		.relance-alerte-card { padding: .55rem .75rem; gap: .5rem; }
		.relance-alerte-text strong { font-size: .82rem; }
		.kb-desktop { display: none !important; }
		.kb-mobile { display: block; }
	}
</style>
