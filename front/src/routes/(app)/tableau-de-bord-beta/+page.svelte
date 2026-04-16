<script lang="ts">
	import { onMount } from 'svelte';
	import { currentUser, isCS, isAdmin } from '$lib/stores/auth';
	import { flux, type FluxItem, type FluxResponse } from '$lib/api';
	import { getPageConfig, configStore, siteNomStore } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';
	import { fmtDate, fmtDateLong, fmtDatetimeShort } from '$lib/date';
	import Icon from '$lib/components/Icon.svelte';
	import { toast } from '$lib/components/Toast.svelte';

	$: _pc = getPageConfig($configStore, 'tableau-de-bord-beta', { titre: 'Tableau de bord', navLabel: 'Accueil β', descriptif: "Le pouls de votre résidence — tous les mouvements en un seul flux." });
	$: _siteNom = $siteNomStore;

	let data: FluxResponse | null = null;
	let loading = true;

	onMount(async () => {
		try {
			data = await flux.get();
		} catch (e: any) {
			toast('error', 'Erreur chargement du flux : ' + (e?.message ?? String(e)));
		} finally {
			loading = false;
		}
	});

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
		return labels.join(', ');
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

	// ── Urgences en cours (coupures, événements imminents) ─────────────────
	$: urgentItems = data?.items.filter(i =>
		(i.type === 'evenement' && i.meta?.type === 'coupure') ||
		(i.type === 'ticket_ouvert' && i.badges?.includes('urgence'))
	) ?? [];

	// ── Barre de santé : calcul largeur relative ───────────────────────────
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
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

{#if loading}
	<p style="color:var(--color-text-muted)">Chargement…</p>
{:else if !data}
	<div class="empty-state">
		<h3>Impossible de charger le flux</h3>
		<p>Réessayez dans quelques instants.</p>
	</div>
{:else}
	<!-- En-tête -->
	<div class="page-header">
		<h1 style="font-size:1.4rem;font-weight:700">
			Bonjour {$currentUser?.prenom} {($currentUser?.nom ?? '').toUpperCase()} &#x1F44B;
			{#if roleLabels}<span style="font-size:.95rem;font-weight:400;color:var(--color-text-muted);margin-left:.25rem">({roleLabels})</span>{/if}
		</h1>
		<span class="badge badge-purple" style="font-size:.7rem">β</span>
	</div>
	<p class="page-subtitle">{@html safeHtml(_pc.descriptif)}</p>

	<!-- Alertes urgentes -->
	{#if urgentItems.length > 0}
		{#each urgentItems.slice(0, 3) as u}
			<div class="alert alert-error" style="margin-bottom:.75rem">
				<div class="urgent-row">
					<span class="urgent-icon">{u.icon}</span>
					<div class="urgent-body">
						<strong>{u.titre}</strong>
						{#if u.detail}<span class="urgent-detail">{u.detail}</span>{/if}
					</div>
					{#if u.lien}<a href={u.lien} class="btn btn-outline btn-sm">Voir</a>{/if}
				</div>
			</div>
		{/each}
	{/if}

	<!-- KPI santé résidence -->
	<div class="sante-card card">
		<div class="sante-header">
			<h2 class="section-title" style="margin:0"><Icon name="layout-dashboard" size={16} /> Santé résidence</h2>
		</div>
		<div class="sante-grid">
			<div class="sante-metric">
				<div class="sante-metric-top">
					<span class="sante-value">{data.sante.tickets_ouverts}</span>
					<span class="sante-label">Tickets ouverts</span>
				</div>
				<div class="sante-bar-track">
					<div class="sante-bar sante-bar-tickets" style="width:{barWidth(data.sante.tickets_ouverts, 20)}"></div>
				</div>
				{#if data.sante.tickets_urgents > 0}
					<span class="badge badge-red" style="margin-top:.25rem">dont {data.sante.tickets_urgents} urgent{data.sante.tickets_urgents > 1 ? 's' : ''}</span>
				{/if}
			</div>
			<div class="sante-metric">
				<div class="sante-metric-top">
					<span class="sante-value">{data.sante.resolution_moyenne_heures != null ? `${data.sante.resolution_moyenne_heures}h` : '—'}</span>
					<span class="sante-label">Résolution moy.</span>
				</div>
				<div class="sante-bar-track">
					<div class="sante-bar sante-bar-resolution" style="width:{barWidth(data.sante.resolution_moyenne_heures ?? 0, 72)}"></div>
				</div>
			</div>
			<div class="sante-metric">
				<div class="sante-metric-top">
					<span class="sante-value">{data.sante.sondages_actifs}</span>
					<span class="sante-label">Sondages actifs</span>
				</div>
			</div>
		</div>

		<!-- Prochaines échéances -->
		{#if data.sante.prochains.length > 0}
			<div class="sante-prochains">
				<h3 class="sante-prochains-title"><Icon name="calendar-days" size={14} /> À venir</h3>
				{#each data.sante.prochains as p}
					<div class="prochain-row">
						<span class="prochain-icon">{p.icon}</span>
						<span class="prochain-date">{fmtDate(p.date)}</span>
						<span class="prochain-titre">{p.titre}</span>
					</div>
				{/each}
			</div>
		{/if}
	</div>

	<!-- Flux d'activité -->
	<h2 class="section-title" style="margin-top:2rem"><Icon name="newspaper" size={16} /> Fil d'activité</h2>

	{#if data.items.length === 0}
		<div class="empty-state">
			<h3>Aucune activité récente</h3>
			<p>Les mouvements de la résidence apparaîtront ici.</p>
		</div>
	{:else}
		<div class="flux-timeline">
			{#each dayGroups as group}
				<div class="flux-day-label">{group.label}</div>
				{#each group.items as item}
					<a
						href={item.lien ?? '#'}
						class="flux-item card"
						class:flux-urgent={item.type === 'ticket_ouvert' && item.badges?.includes('urgence')}
					>
						<div class="flux-item-left" style="border-color:{TYPE_COLORS[item.type] ?? 'var(--color-border)'}">
							<span class="flux-icon">{item.icon}</span>
						</div>
						<div class="flux-item-body">
							<div class="flux-item-top">
								<span class="flux-titre">{item.titre}</span>
								<span class="flux-heure">{fmtDatetimeShort(item.date)}</span>
							</div>
							{#if item.detail}
								<p class="flux-detail">{item.detail}</p>
							{/if}
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
	/* ── Alertes urgentes ──────────────────────────────────────────────── */
	.urgent-row { display: flex; align-items: center; gap: .75rem; }
	.urgent-icon { font-size: 1.2rem; flex-shrink: 0; }
	.urgent-body { flex: 1; display: flex; flex-direction: column; gap: .15rem; }
	.urgent-body strong { font-size: .9rem; }
	.urgent-detail { font-size: .8rem; color: var(--color-text-muted); }

	/* ── Carte santé ───────────────────────────────────────────────────── */
	.sante-card { padding: 1.25rem; margin-bottom: 1.5rem; }
	.sante-header { margin-bottom: 1rem; }
	.sante-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
		gap: 1rem;
	}
	.sante-metric { display: flex; flex-direction: column; gap: .35rem; }
	.sante-metric-top { display: flex; align-items: baseline; gap: .4rem; }
	.sante-value { font-size: 1.5rem; font-weight: 700; color: var(--color-primary); line-height: 1; }
	.sante-label { font-size: .82rem; color: var(--color-text-muted); }
	.sante-bar-track {
		height: 6px; border-radius: 3px; background: var(--color-border);
		overflow: hidden; width: 100%;
	}
	.sante-bar { height: 100%; border-radius: 3px; transition: width .4s ease; min-width: 4px; }
	.sante-bar-tickets { background: var(--color-info); }
	.sante-bar-resolution { background: var(--color-warning); }

	.sante-prochains { margin-top: 1.25rem; border-top: 1px solid var(--color-border); padding-top: 1rem; }
	.sante-prochains-title { font-size: .8rem; font-weight: 600; color: var(--color-text-muted); text-transform: uppercase; letter-spacing: .05em; margin-bottom: .5rem; display: flex; align-items: center; gap: .35rem; }
	.prochain-row { display: flex; align-items: center; gap: .5rem; padding: .3rem 0; font-size: .85rem; }
	.prochain-icon { flex-shrink: 0; font-size: .9rem; }
	.prochain-date { font-size: .78rem; color: var(--color-text-muted); min-width: 5.5rem; white-space: nowrap; }
	.prochain-titre { flex: 1; color: var(--color-text); }

	/* ── Flux timeline ─────────────────────────────────────────────────── */
	.flux-timeline { display: flex; flex-direction: column; gap: .35rem; }
	.flux-day-label {
		font-size: .78rem; font-weight: 600; text-transform: uppercase;
		letter-spacing: .05em; color: var(--color-text-muted);
		padding: .75rem 0 .25rem; border-bottom: 1px solid var(--color-border);
		margin-bottom: .25rem;
	}

	.flux-item {
		display: flex; gap: 0; padding: 0; overflow: hidden;
		text-decoration: none; color: inherit;
		transition: border-left-color .12s, box-shadow .12s;
		border-left: 4px solid var(--color-border);
	}
	.flux-item:hover { border-left-color: var(--color-primary); box-shadow: var(--shadow); }
	.flux-item.flux-urgent { border-left-color: var(--color-danger); }

	.flux-item-left {
		display: flex; align-items: center; justify-content: center;
		width: 3rem; flex-shrink: 0; font-size: 1.15rem;
		background: var(--color-bg);
	}
	.flux-icon { line-height: 1; }

	.flux-item-body { flex: 1; padding: .7rem .9rem; display: flex; flex-direction: column; gap: .25rem; min-width: 0; }
	.flux-item-top { display: flex; align-items: flex-start; gap: .5rem; }
	.flux-titre { font-size: .9rem; font-weight: 500; flex: 1; line-height: 1.35; }
	.flux-heure { font-size: .75rem; color: var(--color-text-muted); white-space: nowrap; flex-shrink: 0; }
	.flux-detail { font-size: .82rem; color: var(--color-text-muted); margin: 0; line-height: 1.4; }
	.flux-badges { display: flex; gap: .3rem; flex-wrap: wrap; }

	/* ── Responsive ────────────────────────────────────────────────────── */
	@media (max-width: 767px) {
		.sante-grid { grid-template-columns: 1fr 1fr; }
		.flux-item-left { width: 2.5rem; }
		.prochain-date { min-width: 4.5rem; }
	}
</style>
