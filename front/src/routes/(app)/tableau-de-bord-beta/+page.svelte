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
			else if (appt.etage === 1) parts.push('1er étage');
			else parts.push(`${appt.etage}ème étage`);
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

	// ── Urgences en cours (coupures, événements imminents, tickets urgents) ──
	$: urgentItems = data?.items.filter(i =>
		(i.type === 'evenement' && i.meta?.type === 'coupure') ||
		(i.type === 'ticket_ouvert' && i.badges?.includes('urgence')) ||
		(i.type === 'publication' && i.meta?.urgente)
	) ?? [];

	// ── Lien de destination par type de flux ───────────────────────────────
	function typeLink(item: FluxItem): string {
		if (item.type === 'sondage_ouvert' || item.type === 'sondage_clos') return '/sondages';
		if (item.type === 'ticket_ouvert' || item.type === 'ticket_resolu') return '/tickets';
		return item.lien ?? '#';
	}

	// ── Barre de progression temps (pour urgences avec debut/fin) ──────────
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

	// ── Format heure courte pour urgence ───────────────────────────────────
	function fmtHeure(iso: string): string {
		return new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
	}

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
			{#if lotLabel}<span class="header-lot">· {lotLabel}</span>{/if}
		</h1>
		<span class="badge badge-purple" style="font-size:.7rem">β</span>
	</div>
	{#if roleLabels}<p class="header-roles">{roleLabels}</p>{/if}
	<p class="page-subtitle">{@html safeHtml(_pc.descriptif)}</p>

	<!-- Alertes urgentes (style fieldset) -->
	{#if urgentItems.length > 0}
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
						href={typeLink(item)}
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
	/* ── Header lot & rôles ────────────────────────────────────────────── */
	.header-lot {
		font-size: .95rem; font-weight: 400; color: var(--color-text-muted); margin-left: .25rem;
	}
	.header-roles {
		font-size: .82rem; color: var(--color-text-muted); margin: -.35rem 0 .25rem;
	}

	/* ── Alertes urgentes (fieldset) ───────────────────────────────────── */
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
	.urgence-concerne {
		font-size: .82rem; color: var(--color-primary); font-weight: 500; margin: 0;
	}
	.urgence-progress-wrap { display: flex; align-items: center; gap: .6rem; margin-top: .15rem; }
	.urgence-progress-track {
		flex: 1; height: 6px; border-radius: 3px;
		background: var(--color-border); overflow: hidden;
	}
	.urgence-progress-bar {
		height: 100%; border-radius: 3px; background: var(--color-text-muted);
		transition: width .4s ease;
	}
	.urgence-progress-bar.urgence-active { background: #dc2626; }
	.urgence-progress-label { font-size: .75rem; color: var(--color-text-muted); white-space: nowrap; }

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
