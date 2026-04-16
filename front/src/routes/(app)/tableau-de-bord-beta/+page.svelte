<script lang="ts">
	import { onMount } from 'svelte';
	import { currentUser, isCS, isAdmin } from '$lib/stores/auth';
	import { flux, lots, type FluxItem, type FluxResponse } from '$lib/api';
	import { getPageConfig, configStore, siteNomStore } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';
	import { fmtDate, fmtDateLong, fmtDatetimeShort } from '$lib/date';
	import Icon from '$lib/components/Icon.svelte';
	import { toast } from '$lib/components/Toast.svelte';

	$: _pc = getPageConfig($configStore, 'tableau-de-bord-beta', { titre: 'Tableau de bord', navLabel: 'Accueil β', descriptif: "Le pouls de votre résidence — tous les mouvements en un seul flux." });
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
			locataire: 'Locataire',
			syndic: 'Syndic',
			mandataire: 'Mandataire',
			aidant: 'Aidant (proche)',
		};
		const SPECIAL: Record<string, string> = {
			conseil_syndical: 'Conseil syndical',
			admin: 'Admin',
		};
		const labels: string[] = [];
		const statut = $currentUser?.statut ?? '';
		if (STATUT[statut]) labels.push(STATUT[statut]);
		const allRoles = new Set([...($currentUser?.roles ?? []), $currentUser?.role ?? '']);
		for (const r of ['conseil_syndical', 'admin']) {
			if (allRoles.has(r)) labels.push(SPECIAL[r]);
		}
		return labels.join(' · ');
	})();

	// ── Résumé lot utilisateur ─────────────────────────────────────────────
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

	$: dayGroups = data ? groupByDay(data.items) : [];

	// ── Urgences en cours ──────────────────────────────────────────────────
	$: urgentItems = data?.items.filter(i =>
		(i.type === 'evenement' && i.meta?.type === 'coupure') ||
		(i.type === 'ticket_ouvert' && i.badges?.includes('urgence')) ||
		(i.type === 'publication' && i.meta?.urgente)
	) ?? [];

	// ── Compteurs rapides ──────────────────────────────────────────────────
	$: countByType = (() => {
		const c: Record<string, number> = {};
		for (const item of data?.items ?? []) c[item.type] = (c[item.type] ?? 0) + 1;
		return c;
	})();

	// ── Lien par type ──────────────────────────────────────────────────────
	function typeLink(item: FluxItem): string {
		if (item.type === 'sondage_ouvert' || item.type === 'sondage_clos') return '/sondages';
		if (item.type === 'ticket_ouvert' || item.type === 'ticket_resolu') return '/tickets';
		return item.lien ?? '#';
	}

	// ── Labels français ────────────────────────────────────────────────────
	const TYPE_LABELS: Record<string, string> = {
		ticket_resolu: 'Ticket résolu',
		ticket_ouvert: 'Nouveau ticket',
		publication: 'Actualité',
		evenement: 'Événement',
		devis: 'Devis',
		sondage_clos: 'Sondage clos',
		sondage_ouvert: 'Sondage',
	};

	// ── Progression urgence ────────────────────────────────────────────────
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
		return new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
	}

	function barWidth(val: number, max: number): string {
		return `${Math.min(Math.round((val / Math.max(max, 1)) * 100), 100)}%`;
	}

	const TYPE_COLORS: Record<string, string> = {
		ticket_resolu: 'var(--color-success)',
		ticket_ouvert: 'var(--color-info)',
		publication: 'var(--color-primary)',
		evenement: 'var(--color-warning)',
		devis: 'var(--color-accent)',
		sondage_clos: 'var(--color-text-muted)',
		sondage_ouvert: '#6B21A8',
	};

	const TYPE_BG: Record<string, string> = {
		ticket_resolu: '#E6F4EE',
		ticket_ouvert: '#EEF2F7',
		publication: '#EEF2F7',
		evenement: '#FDF3E0',
		devis: '#FDF8EE',
		sondage_clos: '#EAEDF1',
		sondage_ouvert: '#F3E8FF',
	};
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

{#if loading}
	<!-- Skeleton loading -->
	<div class="skeleton-wrap">
		<div class="skel skel-header"></div>
		<div class="skel skel-subtitle"></div>
		<div class="skel-row">
			<div class="skel skel-kpi"></div>
			<div class="skel skel-kpi"></div>
			<div class="skel skel-kpi"></div>
		</div>
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
					<h1 class="hero-greeting">
						{greeting} {$currentUser?.prenom} &#x1F44B;
					</h1>
					{#if lotLabel}
						<p class="hero-lot"><Icon name="home" size={13} /> {lotLabel}</p>
					{/if}
					{#if roleLabels}
						<p class="hero-role">{roleLabels}</p>
					{/if}
				</div>
				<span class="badge badge-purple hero-badge">β</span>
			</div>
		</div>
	</div>

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
				<div class="kpi-icon-zone" style="background:#EEF2F7;color:var(--color-info)">
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
				<div class="kpi-icon-zone" style="background:#FDF3E0;color:var(--color-warning)">
					<Icon name="clock" size={22} />
				</div>
				<div class="kpi-text-zone">
					<span class="kpi-value">{data.sante.resolution_moyenne_heures != null ? `${data.sante.resolution_moyenne_heures}h` : '—'}</span>
					<span class="kpi-label">Résolution moy.</span>
				</div>
			</div>
			<a href="/sondages" class="kpi-card card">
				<div class="kpi-icon-zone" style="background:#F3E8FF;color:#6B21A8">
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

	<!-- ═══ PROCHAINES ÉCHÉANCES ══════════════════════════════════════════ -->
	{#if data.sante.prochains.length > 0}
		<div class="section-reveal" class:section-visible={ready} style="--delay:.2s">
			<div class="prochains-card card">
				<h3 class="prochains-header"><Icon name="calendar-days" size={15} /> Prochaines échéances</h3>
				{#each data.sante.prochains as p, i}
					<div class="prochain-row" class:prochain-first={i === 0}>
						<span class="prochain-icon">{p.icon}</span>
						<span class="prochain-date">{fmtDate(p.date)}</span>
						<span class="prochain-titre">{p.titre}</span>
					</div>
				{/each}
			</div>
		</div>
	{/if}

	<!-- ═══ FIL D'ACTIVITÉ (TIMELINE) ════════════════════════════════════ -->
	<div class="section-reveal" class:section-visible={ready} style="--delay:.25s">
		<h2 class="section-title" style="margin-top:1.5rem"><Icon name="newspaper" size={16} /> Fil d'activité</h2>
	</div>

	{#if data.items.length === 0}
		<div class="empty-state">
			<Icon name="inbox" size={32} />
			<h3>Aucune activité récente</h3>
			<p>Les mouvements de la résidence apparaîtront ici.</p>
		</div>
	{:else}
		<div class="flux-timeline section-reveal" class:section-visible={ready} style="--delay:.3s">
			{#each dayGroups as group}
				<div class="flux-day-label">{group.label}</div>
				{#each group.items as item}
					<a href={typeLink(item)} class="flux-item" class:flux-urgent={item.type === 'ticket_ouvert' && item.badges?.includes('urgence')}>
						<div class="flux-dot" style="background:{TYPE_COLORS[item.type] ?? 'var(--color-border)'}"></div>
						<div class="flux-card card">
							<div class="flux-card-top">
								<span class="flux-type-chip" style="background:{TYPE_BG[item.type] ?? '#EAEDF1'};color:{TYPE_COLORS[item.type] ?? 'var(--color-text-muted)'}">{TYPE_LABELS[item.type] ?? item.type}</span>
								<span class="flux-heure">{fmtDatetimeShort(item.date)}</span>
							</div>
							<div class="flux-card-body">
								<span class="flux-icon">{item.icon}</span>
								<div class="flux-card-text">
									<span class="flux-titre">{item.titre}</span>
									{#if item.detail}
										<p class="flux-detail">{item.detail}</p>
									{/if}
								</div>
							</div>
							{#if item.badges.length > 0}
								<div class="flux-badges">
									{#each item.badges as b}
										<span class="badge {badgeClass(item.type, b)}">{b}</span>
									{/each}
								</div>
							{/if}
						</div>
					</a>
				{/each}
			{/each}
		</div>
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
		background-size: 800px 100%;
		animation: shimmer 1.4s ease infinite;
	}
	.skel-header { height: 2rem; width: 60%; }
	.skel-subtitle { height: 1rem; width: 40%; }
	.skel-row { display: flex; gap: .75rem; }
	.skel-kpi { height: 5rem; flex: 1; }
	.skel-card { height: 4.5rem; }
	.skel-card.short { width: 70%; }

	/* ═══ HERO EN-TÊTE ═══════════════════════════════════════════════════ */
	.hero {
		margin: -1rem -1rem 0;
		padding: 1.5rem 1.25rem 1.25rem;
		background: linear-gradient(135deg, var(--color-primary) 0%, #2a4f7a 100%);
		border-radius: 0 0 var(--radius) var(--radius);
		position: relative;
		overflow: hidden;
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
	.hero-greeting {
		font-size: 1.35rem; font-weight: 700;
		color: var(--color-text-inverse); margin: 0;
		line-height: 1.3;
	}
	.hero-lot {
		font-size: .82rem; color: rgba(255,255,255,.75); margin: .25rem 0 0;
		display: flex; align-items: center; gap: .3rem;
	}
	.hero-lot :global(svg) { opacity: .7; }
	.hero-role {
		font-size: .75rem; color: rgba(255,255,255,.55); margin: .15rem 0 0;
		letter-spacing: .02em;
	}
	.hero-badge { font-size: .65rem; margin-top: .15rem; }

	/* ═══ RACCOURCIS RAPIDES ═════════════════════════════════════════════ */
	.quick-nav {
		display: flex; gap: .5rem; flex-wrap: wrap;
		margin: 1rem 0; padding: 0;
		opacity: 0; transform: translateY(8px);
		transition: opacity .3s ease .08s, transform .3s ease .08s;
	}
	.quick-nav.section-visible { opacity: 1; transform: translateY(0); }
	.quick-pill {
		display: inline-flex; align-items: center; gap: .35rem;
		padding: .4rem .8rem;
		border-radius: 2rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		font-size: .78rem; font-weight: 500;
		color: var(--color-text); text-decoration: none;
		transition: border-color .15s, box-shadow .15s, background .15s;
		white-space: nowrap;
	}
	.quick-pill:hover {
		border-color: var(--color-primary);
		box-shadow: var(--shadow-sm);
		background: var(--color-primary-light);
	}
	.quick-count {
		background: var(--color-primary); color: #fff;
		font-size: .65rem; font-weight: 700;
		padding: .05rem .4rem; border-radius: 1rem;
		line-height: 1.3; min-width: 1.1rem; text-align: center;
	}

	/* ═══ ANIMATIONS SECTIONS ═══════════════════════════════════════════ */
	.section-reveal {
		opacity: 0; transform: translateY(12px);
		transition: opacity .35s ease var(--delay, 0s), transform .35s ease var(--delay, 0s);
	}
	.section-reveal.section-visible { opacity: 1; transform: translateY(0); }

	/* ═══ ALERTES URGENTES (fieldset) ═══════════════════════════════════ */
	.urgence-fieldset {
		border: 2px solid var(--color-danger, #dc2626);
		border-radius: var(--radius);
		padding: 1rem 1.15rem .9rem;
		margin-bottom: 1rem;
		background: #fef2f2;
		position: relative;
	}
	.urgence-legend {
		font-size: .72rem; font-weight: 700; letter-spacing: .06em;
		color: #dc2626; background: #fef2f2;
		padding: 0 .5rem; text-transform: uppercase;
	}
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
	.kpi-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
		gap: .75rem;
		margin-bottom: 1.25rem;
	}
	.kpi-card {
		display: flex; align-items: stretch;
		text-decoration: none; color: inherit;
		overflow: hidden; padding: 0;
		transition: box-shadow .15s, transform .1s;
	}
	.kpi-card:hover { box-shadow: var(--shadow); transform: translateY(-1px); }
	.kpi-icon-zone {
		width: 3.5rem; flex-shrink: 0;
		display: flex; align-items: center; justify-content: center;
	}
	.kpi-text-zone {
		flex: 1; padding: .65rem .75rem;
		display: flex; flex-direction: column; gap: .1rem;
	}
	.kpi-value { font-size: 1.4rem; font-weight: 700; color: var(--color-primary); line-height: 1.1; }
	.kpi-label { font-size: .78rem; color: var(--color-text-muted); }
	.kpi-badge { font-size: .62rem; width: fit-content; margin-top: .15rem; }
	.kpi-link { font-size: .72rem; color: var(--color-primary); font-weight: 500; margin-top: auto; }

	/* ═══ PROCHAINES ÉCHÉANCES ═══════════════════════════════════════════ */
	.prochains-card { padding: 1rem 1.15rem; margin-bottom: 1.25rem; }
	.prochains-header {
		font-size: .82rem; font-weight: 600; color: var(--color-text-muted);
		text-transform: uppercase; letter-spacing: .05em;
		margin: 0 0 .6rem; display: flex; align-items: center; gap: .35rem;
	}
	.prochain-row {
		display: flex; align-items: center; gap: .5rem;
		padding: .4rem 0; font-size: .85rem;
		border-top: 1px solid var(--color-border);
	}
	.prochain-row.prochain-first { border-top: none; }
	.prochain-icon { flex-shrink: 0; font-size: .9rem; }
	.prochain-date { font-size: .78rem; color: var(--color-text-muted); min-width: 5.5rem; white-space: nowrap; }
	.prochain-titre { flex: 1; color: var(--color-text); }

	/* ═══ FLUX TIMELINE ═════════════════════════════════════════════════ */
	.flux-timeline {
		position: relative;
		padding-left: 1.5rem;
	}
	.flux-timeline::before {
		content: ''; position: absolute; left: .45rem; top: 1.5rem; bottom: .5rem;
		width: 2px; background: var(--color-border); border-radius: 1px;
	}
	.flux-day-label {
		position: relative;
		font-size: .72rem; font-weight: 700; text-transform: uppercase;
		letter-spacing: .06em; color: var(--color-text-muted);
		padding: .9rem 0 .35rem;
		margin-left: -.15rem;
	}
	.flux-item {
		display: flex; align-items: flex-start; gap: .75rem;
		text-decoration: none; color: inherit;
		position: relative;
		margin-bottom: .5rem;
	}
	.flux-dot {
		width: 10px; height: 10px; border-radius: 50%;
		flex-shrink: 0; margin-top: .85rem;
		position: absolute; left: -1.35rem;
		border: 2px solid var(--color-surface);
		box-shadow: 0 0 0 2px var(--color-border);
		z-index: 1;
	}
	.flux-card {
		flex: 1; padding: .7rem .9rem;
		transition: box-shadow .12s, border-left-color .12s;
		border-left: 3px solid transparent;
	}
	.flux-item:hover .flux-card {
		box-shadow: var(--shadow);
		border-left-color: var(--color-primary);
	}
	.flux-item.flux-urgent .flux-card { border-left-color: var(--color-danger); }

	.flux-card-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: .35rem; }
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
	.flux-badges { display: flex; gap: .3rem; flex-wrap: wrap; margin-top: .35rem; }

	/* ═══ RESPONSIVE ════════════════════════════════════════════════════ */
	@media (max-width: 767px) {
		.hero { margin: -.75rem -.75rem 0; padding: 1.25rem 1rem 1rem; }
		.kpi-grid { grid-template-columns: 1fr; }
		.quick-nav { gap: .35rem; }
		.quick-pill { font-size: .72rem; padding: .35rem .65rem; }
		.flux-timeline { padding-left: 1.25rem; }
		.flux-timeline::before { left: .35rem; }
		.flux-dot { left: -1.1rem; width: 8px; height: 8px; }
	}
</style>
