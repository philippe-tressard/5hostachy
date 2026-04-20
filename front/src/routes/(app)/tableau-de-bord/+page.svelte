<script lang="ts">
	import { onMount } from 'svelte';
	import { currentUser, isCS, isAdmin, isProprio } from '$lib/stores/auth';
	import { flux, lots, type FluxItem, type FluxProchain, type FluxResponse } from '$lib/api';
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

	onMount(async () => {
		try {
			const [fluxRes, lotsRes] = await Promise.allSettled([flux.get(), lots.mesList()]);
			if (fluxRes.status === 'fulfilled') data = fluxRes.value;
			else toast('error', 'Erreur chargement du flux');
			if (lotsRes.status === 'fulfilled') userLots = lotsRes.value;
		} catch (e: any) {
			toast('error', 'Erreur chargement : ' + (e?.message ?? String(e)));
		} finally {
			loading = false;
			setTimeout(() => { ready = true; }, 50);
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

	// ── Prochaines échéances filtrées par rôle ─────────────────────────────
	$: visibleProchains = (data?.sante.prochains ?? []).filter(p => {
		if (p.ev_type === 'ag' && !canSeeAG) return false;
		return true;
	});

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
		if (item.type === 'ticket_ouvert' || item.type === 'ticket_resolu') return '/tickets';
		return item.lien ?? '#';
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
		const cree = item.cree_le || item.date;
		return Date.now() - new Date(cree).getTime() < 48 * 3600 * 1000;
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
	</nav>

	<!-- ═══ ALERTES URGENTES ══════════════════════════════════════════════ -->
	{#if urgentItems.length > 0}
		<div class="section-reveal" class:section-visible={ready} style="--delay:.1s">
			{#each urgentItems.slice(0, 3) as u}
				{@const progress = urgencyProgress(u)}
				<fieldset class="urgence-fieldset">
					<legend class="urgence-legend">🔴 URGENCE</legend>
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

	<!-- ═══ PROCHAINES ÉCHÉANCES (expandables) ════════════════════════════ -->
	{#if visibleProchains.length > 0}
		<div class="section-reveal" class:section-visible={ready} style="--delay:.2s">
			<div class="prochains-card card">
				<h3 class="prochains-header"><Icon name="calendar-days" size={15} /> Prochaines échéances</h3>
				{#each visibleProchains as p, i}
					{@const isExpanded = expandedItem === `proch_${p.id}`}
					<div
						class="prochain-expand"
						class:expanded={isExpanded}
						class:prochain-first={i === 0}
						style="--type-color:{p.ev_type ? (TYPE_COLORS['evenement'] ?? 'var(--color-border)') : (p.type === 'contrat' ? '#10B981' : 'var(--color-border)')}"
					>
						<div
							class="prochain-row"
							role="button"
							tabindex="0"
							on:click={() => toggleItem(`proch_${p.id}`)}
							on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && toggleItem(`proch_${p.id}`)}
						>
							<span class="prochain-icon">{p.icon}</span>
							<span class="prochain-date">{fmtDate(p.date)}</span>
							<span class="prochain-titre">{p.titre}</span>
							{#if p.ev_type}
								<span class="prochain-type-chip" style="background:{TYPE_BG['evenement']};color:{TYPE_COLORS['evenement']}">{p.ev_type}</span>
							{/if}
							{#if p.perimetre && p.perimetre !== 'Copropriété entière'}
								<span class="badge badge-blue" style="font-size:.7rem;flex-shrink:0">🔹 {p.perimetre}</span>
							{/if}
							{#if isNew(p)}
								<span class="new-badge">NOUVEAU</span>
							{/if}
							<span class="chevron" class:open={isExpanded}>›</span>
						</div>
						{#if isExpanded}
							<!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
							<div class="prochain-body" on:click|stopPropagation>
								{#if p.lieu}<p class="prochain-meta">📍 {p.lieu}</p>{/if}
								{#if p.perimetre}<p class="prochain-meta">🔹 {p.perimetre}</p>{/if}
								{#if p.prestataire}<p class="prochain-meta">🔧 {p.prestataire}</p>{/if}
								{#if p.fin}<p class="prochain-meta">🕐 {fmtDate(p.date)} → {fmtDate(p.fin)}</p>{/if}
								{#if p.description}
									<div class="prochain-desc rich-content">{@html safeHtml(p.description)}</div>
								{/if}
								{#if p.statut_kanban}
									<span class="badge badge-blue" style="margin-top:.5rem">{p.statut_kanban}</span>
								{/if}
								<a href={p.type === 'contrat' ? '/prestataires' : '/calendrier'} class="prochain-link">Voir la page complète →</a>
							</div>
						{/if}
					</div>
				{/each}
			</div>
		</div>
	{/if}

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
	}
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
	.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: .75rem; margin-bottom: 1.25rem; }
	.kpi-card { display: flex; align-items: stretch; text-decoration: none; color: inherit; overflow: hidden; padding: 0; transition: box-shadow .15s, transform .1s; }
	.kpi-card:hover { box-shadow: var(--shadow); transform: translateY(-1px); }
	.kpi-icon-zone { width: 3.5rem; flex-shrink: 0; display: flex; align-items: center; justify-content: center; }
	.kpi-text-zone { flex: 1; padding: .65rem .75rem; display: flex; flex-direction: column; gap: .1rem; }
	.kpi-value { font-size: 1.4rem; font-weight: 700; color: var(--color-primary); line-height: 1.1; }
	.kpi-label { font-size: .78rem; color: var(--color-text-muted); }
	.kpi-badge { font-size: .62rem; width: fit-content; margin-top: .15rem; }
	.kpi-link { font-size: .72rem; color: var(--color-primary); font-weight: 500; margin-top: auto; }

	/* ═══ PROCHAINES ÉCHÉANCES (expandable) ═════════════════════════════ */
	.prochains-card { padding: 1rem 1.15rem; margin-bottom: 1.25rem; }
	.prochains-header { font-size: .82rem; font-weight: 600; color: var(--color-text-muted); text-transform: uppercase; letter-spacing: .05em; margin: 0 0 .6rem; display: flex; align-items: center; gap: .35rem; }
	.prochain-expand {
		border-top: 1px solid var(--color-border);
		border-left: 4px solid var(--type-color, var(--color-border));
		border-radius: 0 var(--radius) var(--radius) 0;
		margin-bottom: .15rem;
		transition: border-left-color .15s, background .15s, box-shadow .15s;
	}
	.prochain-expand.prochain-first { border-top: none; }
	.prochain-expand:hover { background: var(--color-surface); }
	.prochain-expand.expanded { background: var(--color-surface); box-shadow: var(--shadow-sm); }
	.prochain-row {
		display: flex; align-items: center; gap: .5rem;
		padding: .5rem .6rem; font-size: .85rem; cursor: pointer;
	}
	.prochain-icon { flex-shrink: 0; font-size: .9rem; }
	.prochain-date { font-size: .78rem; color: var(--color-text-muted); min-width: 5.5rem; white-space: nowrap; }
	.prochain-titre { flex: 1; color: var(--color-text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.prochain-type-chip { font-size: .6rem; font-weight: 600; text-transform: uppercase; letter-spacing: .03em; padding: .1rem .4rem; border-radius: 1rem; flex-shrink: 0; }
	.prochain-body { padding: .5rem 1rem 1rem 2.5rem; border-top: 1px solid var(--color-border); }
	.prochain-meta { font-size: .82rem; color: var(--color-text-muted); margin: .2rem 0; }
	.prochain-desc { font-size: .85rem; margin: .5rem 0; line-height: 1.5; }
	.prochain-link { font-size: .78rem; color: var(--color-primary); font-weight: 500; text-decoration: none; display: inline-block; margin-top: .5rem; }
	.prochain-link:hover { text-decoration: underline; }

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
	}
</style>
