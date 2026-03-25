<script lang="ts">
	import { onMount } from 'svelte';
	import { afterNavigate } from '$app/navigation';
	import { currentUser, isCS, isAdmin, setUser } from '$lib/stores/auth';
	import { tickets, publications, notifications as notifApi, admin as adminApi, calendrier as calApi, prestataires as prestApi, ApiError, type Ticket, type TicketEvolution, type Publication, type Notification, auth as authApi } from '$lib/api';
	import { getPageConfig, configStore, siteNomStore } from '$lib/stores/pageConfig';
	import { safeHtml, safeRichContent } from '$lib/sanitize';

	import { toast } from '$lib/components/Toast.svelte';

	$: _pc = getPageConfig($configStore, 'tableau-de-bord', { titre: 'Tableau de bord', navLabel: 'Accueil', descriptif: "Votre espace numérique de résidence : actualités, demandes, accès et gouvernance de votre copropriété en un seul endroit." });
	$: _siteNom = $siteNomStore;

	let ticketList: Ticket[] = [];
	let pubList: Publication[] = [];
  $: compactPubs = pubList.length > 7;
	let notifList: Notification[] = [];
	let evenementList: any[] = [];
	let devisList: any[] = [];
  $: compactEvs = evenementList.length > 7;
	let pendingCount = 0;
	let loading = true;
	let notifOpen = false;
	let lastSeenActualites: string | null = null;

	onMount(async () => {
		try {
			const pending = $isCS ? adminApi.pendingAccounts() : Promise.resolve(null);
			const [ticketsRes, pubsRes, notifsRes, evsRes, devisRes, pendingRes] = await Promise.allSettled([
				tickets.list(),
				publications.list(),
				notifApi.list(),
				calApi.list(),
				prestApi.devis(),
				pending,
			]);

			if (ticketsRes.status === 'fulfilled') {
				ticketList = ticketsRes.value;
				if (ticketList.length > 0) loadEvolutions(ticketList[0].id);
			}
			else toast('error', 'Erreur chargement des demandes : ' + (ticketsRes.reason?.message ?? String(ticketsRes.reason)));

			if (pubsRes.status === 'fulfilled') pubList = pubsRes.value;
			else toast('error', 'Erreur chargement des actualités : ' + (pubsRes.reason?.message ?? String(pubsRes.reason)));

			if (notifsRes.status === 'fulfilled') notifList = notifsRes.value;
			// notifications : pas de toast bloquant

			if (evsRes.status === 'fulfilled') evenementList = evsRes.value;
			else toast('error', 'Erreur chargement des événements : ' + (evsRes.reason?.message ?? String(evsRes.reason)));

			if (devisRes.status === 'fulfilled') devisList = devisRes.value;

			lastSeenActualites = $currentUser?.last_seen_actualites ?? null;
			if (pendingRes.status === 'fulfilled' && pendingRes.value) {
				pendingCount = (pendingRes.value as unknown[]).length;
			}
		} finally {
			loading = false;
		}
	});

	async function marquerLue(id: number) {
		try {
			await notifApi.markRead(id);
			notifList = notifList.map((n) => n.id === id ? { ...n, lue: true } : n);
		} catch { /* ignore */ }
	}

	async function toutMarquerLu() {
		const unread = notifList.filter((n) => !n.lue);
		await Promise.all(unread.map((n) => notifApi.markRead(n.id)));
		notifList = notifList.map((n) => ({ ...n, lue: true }));
	}

	afterNavigate(() => {
		lastSeenActualites = $currentUser?.last_seen_actualites ?? null;
	});

	async function markActualitesVues() {
		const now = new Date().toISOString();
		try {
			const updated = await authApi.updateMe({ last_seen_actualites: now });
			setUser(updated);
		} catch { /* ignore */ }
		lastSeenActualites = now;
	}

	$: openTickets = ticketList.filter((t) => t.statut === 'ouvert' || t.statut === 'en_cours');
	$: urgentTickets = ticketList.filter((t) => t.categorie === 'urgence' && !['résolu', 'annulé', 'fermé'].includes(t.statut));
	$: unreadNotifs = notifList.filter((n) => !n.lue);
	$: pinnedPubs = pubList.filter((p) => p.epingle);
	$: recentPubs = pubList.slice(0, 5);
	$: newPubsCount = lastSeenActualites
		? pubList.filter((p) => new Date(p.cree_le) > new Date(lastSeenActualites!)).length
		: pubList.length;

	$: canSeeAG = ($currentUser?.roles ?? []).some((r: string) => ['propriétaire', 'conseil_syndical', 'admin'].includes(r));
	// Menus résidentiels : visibles si l'utilisateur a au moins un rôle résidentiel
	// (règle README « Visibilité des menus » : admin seul = pas de menus résidentiels)
	$: hasResidentAccess = ($currentUser?.roles ?? []).some((r: string) => ['propriétaire', 'résident', 'externe', 'conseil_syndical'].includes(r));
	// Tickets : E (externe) n’a pas accès
	$: canSeeTickets = ($currentUser?.roles ?? []).some((r: string) => ['propriétaire', 'résident', 'conseil_syndical', 'admin'].includes(r));
	function isEvExpired(ev: any): boolean {
		const end = new Date(ev.fin ?? ev.debut); end.setHours(0, 0, 0, 0);
		const today = new Date(); today.setHours(0, 0, 0, 0);
		return end < today;
	}

	function kanbanStatutPourDevis(statut: string): string {
		switch (statut) {
			case 'en_attente': return 'syndic';
			case 'accepte': return 'fournisseur';
			case 'realise': return 'termine';
			case 'refuse': return 'annule';
			default: return 'syndic';
		}
	}

	$: prestationsPonctuellesActives = devisList
		.filter((d: any) => !d.frequence_type && !d.frequence_valeur && d.statut !== 'realise' && d.statut !== 'refuse')
		.map((d: any) => {
			const rawDate = d.date_prestation ?? d.cree_le ?? new Date().toISOString();
			const debut = typeof rawDate === 'string' && rawDate.includes('T') ? rawDate : `${rawDate}T09:00`;
			return {
				id: -(100000 + Number(d.id)),
				_source: 'devis_ponctuel',
				type: 'maintenance',
				titre: d.titre,
				lieu: null,
				debut,
				fin: null,
				statut_kanban: kanbanStatutPourDevis(d.statut),
				archivee: false,
				perimetre: d.perimetre ?? (d.batiment_id ? `bat:${d.batiment_id}` : 'résidence'),
				description: d.notes ?? null,
			};
		});

	$: recentEvenements = [
		...evenementList,
		...devisList
			.filter((d: any) => d.affichable && !d.frequence_type && !d.frequence_valeur && d.statut !== 'realise' && d.statut !== 'refuse')
			.map((d: any) => {
				const rawDate = d.date_prestation ?? d.cree_le ?? new Date().toISOString();
				const debut = typeof rawDate === 'string' && rawDate.includes('T') ? rawDate : `${rawDate}T09:00`;
				return { id: -(100000 + Number(d.id)), type: 'maintenance', titre: d.titre, lieu: null, debut, fin: null, affichable: true, statut_kanban: null, perimetre: d.perimetre ?? 'résidence', description: d.notes ?? null };
			}),
	]
		.filter((e: any) => e.affichable && !e.archivee && (canSeeAG || e.type !== 'ag'))
		.sort((a, b) => new Date(a.debut).getTime() - new Date(b.debut).getTime())
		.slice(0, 5);

	const TYPE_EMOJI: Record<string, string> = { travaux: '\u{1F528}', coupure: '⚡', ag: '\u{1F3DB}️', maintenance: '\u{1F527}', autre: '\u{1F4CC}' };
	function typeEmoji(t: string) { return TYPE_EMOJI[t] ?? '\u{1F4CC}'; }
	function formatDate(d: string) { return new Date(d).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' }); }

	let expandedPubs = new Set<number>();
	let pubsAutoExpanded = false;
	$: if (recentPubs.length > 0 && !pubsAutoExpanded) { expandedPubs = new Set([recentPubs[0].id]); pubsAutoExpanded = true; }
	function togglePub(id: number) {
		expandedPubs = expandedPubs.has(id) ? new Set() : new Set([id]);
	}

	let expandedEvs = new Set<number>();
	let evsAutoExpanded = false;
	$: if (recentEvenements.length > 0 && !evsAutoExpanded) { expandedEvs = new Set([recentEvenements[0].id]); evsAutoExpanded = true; }
	function toggleEv(id: number) {
		expandedEvs = expandedEvs.has(id) ? new Set() : new Set([id]);
	}

	const STATUT_BADGE: Record<string, string> = {
		ouvert: 'badge-blue', en_cours: 'badge-orange', résolu: 'badge-green', annulé: 'badge-gray', fermé: 'badge-gray',
	};

	$: roleLabels = (() => {
		const STATUT: Record<string, string> = {
			'copropriétaire_résident': 'Copropriétaire résident',
			'copropriétaire_bailleur': 'Copropriétaire bailleur',
			locataire: 'Locataire',
			syndic: 'Syndic',
			mandataire: 'Mandataire',
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

	const STATUT_LABELS: Record<string, string> = {
		ouvert: 'Ouvert', en_cours: 'En cours', résolu: 'Résolu', annulé: 'Annulé', fermé: 'Fermé',
	};
	const PUB_STATUT_LABELS: Record<string, string> = { en_cours: 'En cours', resolu: 'Résolu', annule: 'Annulé' };
	const PUB_STATUT_BADGE: Record<string, string> = { en_cours: 'badge-orange', resolu: 'badge-green', annule: 'badge-gray' };
	const PERIMETRE_LABELS: Record<string, string> = {
		'résidence': 'Copropriété entière',
		'bat:1': 'Bât. 1',
		'bat:2': 'Bât. 2',
		'bat:3': 'Bât. 3',
		'bat:4': 'Bât. 4',
		parking: 'Parking',
		cave: 'Cave',
		aful: 'AFUL',
	};
	function perimètreLabel(items: string[]) {
		const map: Record<string, string> = { 'résidence': 'Copropriété entière', 'bat:1': 'Bât. 1', 'bat:2': 'Bât. 2', 'bat:3': 'Bât. 3', 'bat:4': 'Bât. 4', parking: 'Parking', cave: 'Cave' };
		return items.map(i => map[i] ?? i).join(' · ');
	}
	function evPerimetreLabel(perimetre: string) {
		return perimetre.split(',').map((s: string) => PERIMETRE_LABELS[s.trim()] ?? s.trim()).join(' · ');
	}
	function fmtDateLong(d: string) { return new Date(d).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' }); }
	function fmtDatetime(d: string) { return new Date(d).toLocaleString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }); }
	let expandedEvols = new Set<number>();
	const CAT_ICON: Record<string, string> = {
		panne: '\u{1F6E0}️', nuisance: '\u{1F4E2}', question: '❓', urgence: '\u{1F6A8}', bug: '\u{1F41B}',
	};

	let expandedTickets = new Set<number>();
	let evolsMap: Record<number, TicketEvolution[]> = {};
	let evolsLoaded = new Set<number>();
	let showEvolForm: number | null = null;
	let evolType: 'commentaire' | 'etat' = 'commentaire';
	let evolContenu = '';
	let evolNouveauStatut = '';
	let evolSaving = false;
	let expandedTicketEvols = new Set<number>();

	function isOldResolvedTicket(t: Ticket): boolean {
		if (!['résolu', 'annulé', 'fermé'].includes(t.statut)) return false;
		const lastUpdate = new Date(t.mis_a_jour_le ?? t.cree_le);
		const now = new Date();
		const hoursAgo = (now.getTime() - lastUpdate.getTime()) / (1000 * 60 * 60);
		return hoursAgo > 48;
	}

	let ticketsAutoExpanded = false;
	$: recentTickets = ticketList.filter((t) => !isOldResolvedTicket(t));
	$: if (recentTickets.length > 0 && !ticketsAutoExpanded) { expandedTickets = new Set([recentTickets[0].id]); ticketsAutoExpanded = true; }

	async function toggleTicket(id: number) {
		if (expandedTickets.has(id)) {
			expandedTickets = new Set();
			if (showEvolForm === id) showEvolForm = null;
		} else {
			expandedTickets = new Set([id]);
			showEvolForm = null;
			if (!evolsLoaded.has(id)) await loadEvolutions(id);
		}
	}

	async function loadEvolutions(id: number) {
		try {
			evolsMap[id] = await tickets.evolutions(id);
			evolsLoaded = new Set([...evolsLoaded, id]);
			evolsMap = { ...evolsMap };
		} catch { /* silencieux */ }
	}

	function openEvolForm(id: number) {
		showEvolForm = id;
		evolType = 'commentaire';
		evolContenu = '';
		evolNouveauStatut = '';
		expandedTickets = new Set([id]);
	}

	async function addEvolution(t: Ticket) {
		if (evolType === 'etat' && !evolNouveauStatut) return;
		if (evolType === 'commentaire' && !evolContenu.trim()) return;
		evolSaving = true;
		try {
			await tickets.addEvolution(t.id, {
				type: evolType,
				contenu: evolContenu.trim() || undefined,
				nouveau_statut: evolType === 'etat' ? evolNouveauStatut : undefined,
			});
			if (evolType === 'etat') {
				ticketList = ticketList.map(x => x.id === t.id ? { ...x, statut: evolNouveauStatut } : x);
			}
			await loadEvolutions(t.id);
			showEvolForm = null;
			toast('success', evolType === 'etat' ? 'Statut mis à jour' : 'Commentaire ajouté');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally { evolSaving = false; }
	}

	async function deleteTicket(t: Ticket) {
		if (!confirm(`Supprimer définitivement le ticket #${t.numero} ? Cette action est irréversible.`)) return;
		try {
			await tickets.delete(t.id);
			ticketList = ticketList.filter(x => x.id !== t.id);
			toast('success', 'Ticket supprimé');
		} catch (e) { toast('error', e instanceof ApiError ? e.message : 'Erreur'); }
	}

	function fmtDate(d: string) {
		return new Date(d).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' });
	}

	function renderDesc(c: string) {
		const t = c.trimStart();
		return safeHtml(t.startsWith('<') ? c : `<p>${c.replace(/\n/g, '<br>')}</p>`);
	}
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

{#if loading}
	<p style="color:var(--color-text-muted)">Chargement…</p>
{:else}
	<div class="page-header">
		<h1 style="font-size:1.4rem;font-weight:700">
			Bonjour {$currentUser?.prenom} {($currentUser?.nom ?? '').toUpperCase()} &#x1F44B;
			{#if roleLabels}<span style="font-size:.95rem;font-weight:400;color:var(--color-text-muted);margin-left:.25rem">({roleLabels})</span>{/if}
		</h1>
	</div>
	<div class="page-subtitle">{@html safeHtml(_pc.descriptif)}</div>

	<!-- Alertes urgentes -->
	{#if urgentTickets.length > 0}
		<div class="alert alert-error" style="margin-bottom:1.5rem">
			&#x1F6A8; <strong>{urgentTickets.length} ticket(s) urgent(s)</strong> en cours —
			<a href="/tickets">Voir les demandes</a>
		</div>
	{/if}

	{#if $isCS && pendingCount > 0}
		<div class="alert alert-warning" style="margin-bottom:1.5rem">
			⏳ <strong>{pendingCount} compte(s)</strong> en attente de validation —
			<a href="/espace-cs">Traiter</a>
		</div>
	{/if}

	<!-- KPIs -->
	<div class="kpi-grid">
		<div class="kpi-card card">
			<div class="kpi-value">{openTickets.length}</div>
			<div class="kpi-label">Tickets ouverts</div>
			<a href="/tickets" class="kpi-link">Voir →</a>
		</div>
		<div class="kpi-card card" class:kpi-notif-active={unreadNotifs.length > 0}>
			<div class="kpi-value">{unreadNotifs.length}</div>
			<div class="kpi-label">Notifications non lues</div>
			{#if unreadNotifs.length > 0}
				<button class="kpi-link btn-link" on:click={() => (notifOpen = !notifOpen)}>
					{notifOpen ? 'Masquer' : 'Voir'} →
				</button>
			{:else}
				<a href="/notifications" class="kpi-link">Voir →</a>
			{/if}
		</div>
		<div class="kpi-card card">
			<div class="kpi-value">{newPubsCount}</div>
			<div class="kpi-label">Nouvelles actualités</div>
			<a href="/actualites" class="kpi-link" on:click={markActualitesVues}>Voir →</a>
		</div>
	</div>

	<!-- Panneau notifications non lues -->
	{#if notifOpen && unreadNotifs.length > 0}
		<div class="notif-panel card" style="margin-bottom:1.5rem">
			<div class="notif-panel-header">
				<h2 class="section-title" style="margin:0">&#x1F514; Notifications non lues</h2>
				<button class="btn btn-outline btn-sm" on:click={toutMarquerLu}>Tout marquer comme lu</button>
			</div>
			{#each unreadNotifs as n}
				<div class="notif-item" class:notif-urgente={n.urgente}>
					<div class="notif-content">
						<strong class="notif-titre">{n.titre}</strong>
						<p class="notif-corps">{@html safeRichContent(n.corps)}</p>
						<small class="notif-date">{new Date(n.cree_le).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })}</small>
					</div>
					<button class="btn btn-outline btn-sm" on:click={() => marquerLue(n.id)}>Lu ✓</button>
				</div>
			{/each}
		</div>
	{/if}

	<div class="dashboard-grid">
		<!-- Actualités récentes (menus résidentiels) -->
		{#if hasResidentAccess}
		<div>
			<h2 class="section-title">&#x1F4E2; Actualités récentes</h2>
			{#if recentPubs.length === 0}
				<div class="empty-state">
					<h3>Aucune actualité</h3>
					<p>Les annonces du conseil syndical apparaîtront ici.</p>
				</div>
			{:else}
				{#each recentPubs as pub}
					{@const expanded = expandedPubs.has(pub.id)}
					<div class="pub-expand" class:expanded class:urgent={pub.urgente} class:brouillon={pub.brouillon} class:epingle={pub.epingle}
						role="button" tabindex="0"
						on:click={() => togglePub(pub.id)}
						on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && togglePub(pub.id)}>
						{#if pub.epingle}<span class="pin-badge">&#x1F4CC;</span>{/if}
						<div class="pub-row">
						<div class="pub-row-top">
							<span class="pub-row-titre">{pub.titre}</span>
							<span class="chevron" class:open={expanded}>›</span>
						</div>
						<div class="pub-row-meta">
							{#if pub.brouillon}<span class="badge badge-gray">✏️ Brouillon</span>{/if}
							{#if pub.statut}<span class="badge {PUB_STATUT_BADGE[pub.statut] ?? 'badge-gray'}">{PUB_STATUT_LABELS[pub.statut] ?? pub.statut}</span>{/if}
							{#if pub.perimetre_cible && !(pub.perimetre_cible.length === 1 && pub.perimetre_cible[0] === 'résidence')}<span class="badge badge-gray">&#x1F539; {perimètreLabel(pub.perimetre_cible)}</span>{/if}
							<span class="pub-row-date">{new Date(pub.mis_a_jour_le ?? pub.cree_le).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' })}</span>
						</div>
						</div>
						{#if !expanded && !compactPubs}
							<div class="pub-preview rich-content clamp-5">{@html safeHtml(pub.contenu)}</div>
						{/if}
						{#if expanded}
							<div class="pub-body">
								{#if pub.image_url}
									<img class="pub-img" src={pub.image_url} alt={pub.titre} />
								{/if}
								<div class="rich-content" style="font-size:.875rem;line-height:1.6;margin-bottom:.5rem">{@html safeHtml(pub.contenu)}</div>
								<small style="color:var(--color-text-muted);font-size:.78rem">
								{pub.mis_a_jour_le ? `Mise à jour le ${fmtDateLong(pub.mis_a_jour_le)}` : `Publié le ${fmtDateLong(pub.cree_le)}`}{pub.auteur_nom ? ` par ${pub.auteur_nom}` : ''}

								{#if pub.evolutions && pub.evolutions.length > 0}
									{@const evolsSorted = [...pub.evolutions].sort((a, b) => new Date(b.cree_le).getTime() - new Date(a.cree_le).getTime())}
									{@const evolCompact = evolsSorted.length > 7 && !expandedEvols.has(pub.id)}
									{@const evolsVisible = evolCompact ? evolsSorted.slice(0, 5) : evolsSorted}
									<div class="evol-list">
										{#each evolsVisible as evol, i (evol.id)}
											{#if i > 0}<hr class="evol-sep" />{/if}
											<div class="evol-item evol-{evol.type}">
												<span class="evol-icon">
													{#if evol.type === 'etat'}&#x1F504;{:else if evol.type === 'correction'}✏️{:else}&#x1F4AC;{/if}
												</span>
												<div class="evol-body">
													<span class="evol-meta">{fmtDatetime(evol.cree_le)}{#if evol.auteur_nom} · {evol.auteur_nom}{/if}</span>
													{#if evol.type === 'etat'}
														<span class="evol-text">Statut : <strong>{PUB_STATUT_LABELS[evol.ancien_statut ?? ''] || 'Aucun'}</strong> → <strong>{PUB_STATUT_LABELS[evol.nouveau_statut ?? ''] || evol.nouveau_statut}</strong></span>
													{/if}
													{#if evol.contenu}
														<span class="evol-text">{evol.contenu}</span>
													{/if}
												</div>
											</div>
										{/each}
										{#if evolCompact}
											<hr class="evol-sep" />
											<button class="evol-more" on:click|stopPropagation={() => { expandedEvols.add(pub.id); expandedEvols = expandedEvols; }}>
												Voir les {evolsSorted.length - 5} commentaires plus anciens
											</button>
										{/if}
									</div>
								{/if}
							</div>
						{/if}
					</div>
				{/each}
			{/if}
		</div>
		{/if}

		<!-- Événements récents (menus résidentiels — AG filtrés selon rôle) -->
		{#if hasResidentAccess}
		<div>
			<h2 class="section-title">&#x1F4C5; Événements récents</h2>
			{#if recentEvenements.length === 0}
				<div class="empty-state">
					<h3>Aucun événement</h3>
					<p>Les prochains événements apparaîtront ici.</p>
				</div>
			{:else}
				{#each recentEvenements as ev (ev.id)}
					{@const expanded = expandedEvs.has(ev.id)}
					<div class="ev-expand" class:expanded class:ev-urgent={ev.type === 'coupure'}
						role="button" tabindex="0"
						on:click={() => toggleEv(ev.id)}
						on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && toggleEv(ev.id)}>
						<div class="ev-row">
							<div class="ev-row-inner">
								<div class="ev-row-main">
									<span class="ev-type-icon">{typeEmoji(ev.type)}</span>
									<span class="ev-row-titre">{ev.titre}</span>
									{#if ev._source === 'devis_ponctuel'}
										<span class="badge badge-blue" style="flex-shrink:0">Prestation ponctuelle</span>
									{/if}
								</div>
								{#if ev.lieu || (ev.perimetre && ev.perimetre !== 'résidence')}
								<div class="ev-row-meta">
									{#if ev.lieu}<span class="ev-meta-item">&#x1F4CD; {ev.lieu}</span>{/if}
									{#if ev.perimetre && ev.perimetre !== 'résidence'}<span class="badge badge-blue ev-meta-badge">&#x1F539; {evPerimetreLabel(ev.perimetre)}</span>{/if}

								</div>
								{/if}
							</div>
							<div class="ev-row-right">
								<span class="ev-row-date">{formatDate(ev.debut)}{#if ev.fin} → {formatDate(ev.fin)}{/if}</span>
								<span class="chevron" class:open={expanded}>›</span>
							</div>
						</div>
						{#if !expanded}
							{#if ev.description}
								<div class="ev-preview clamp-5">{@html safeHtml(ev.description)}</div>
							{/if}
						{/if}
						{#if expanded}
							<div class="ev-body" on:click|stopPropagation on:keydown|stopPropagation>
								{#if ev.description}
									<div class="rich-content">{@html safeHtml(ev.description)}</div>
								{/if}
								<small style="color:var(--color-text-muted);font-size:.78rem;display:block;margin-top:.5rem">
								Publié le {fmtDateLong(ev.debut)}{#if ev.fin} → {fmtDateLong(ev.fin)}{/if}{#if ev.auteur_nom}{` par ${ev.auteur_nom}`}{/if}
								</small>
							</div>
						{/if}
					</div>
				{/each}
			{/if}
		</div>
		{/if}

		<!-- Mes tickets récents (P, R, CS, A — pas E) -->
		{#if canSeeTickets}
		<div class="section-demandes">
			<h2 class="section-title">&#x1F3AB; Mes tickets récents</h2>
			{#if recentTickets.length === 0}
				<div class="empty-state">
					<h3>Aucun ticket</h3>
					<a href="/tickets/nouveau" class="btn btn-primary" style="margin-top:.5rem">Nouveau ticket</a>
				</div>
			{:else}
				{#each recentTickets.slice(0, 4) as t (t.id)}
					{@const expanded = expandedTickets.has(t.id)}
					{@const evols = evolsMap[t.id] ?? []}
					<div class="tk-expand" class:expanded class:urgent={t.categorie === 'urgence'}
						role="button" tabindex="0"
						on:click={() => toggleTicket(t.id)}
						on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && toggleTicket(t.id)}>
						<div class="tk-row">
							<div class="tk-row-inner">
								<span class="tk-cat" title={t.categorie}>{CAT_ICON[t.categorie] ?? '\u{1F4CB}'}</span>
								<span class="tk-row-titre">{t.titre}</span>
								<span class="badge {STATUT_BADGE[t.statut] ?? 'badge-gray'}" style="flex-shrink:0">{STATUT_LABELS[t.statut] ?? t.statut}</span>
								{#if t.priorite === 'haute'}
									<span class="badge badge-orange" style="flex-shrink:0">⚡ Urgente</span>
								{/if}
							</div>
							<div class="tk-row-right">
								<span class="tk-row-date">{fmtDate(t.mis_a_jour_le ?? t.cree_le)}</span>
								{#if $isCS}
									<button class="btn-icon" aria-label="Commenter / changer état" title="Commenter / état"
										on:click|stopPropagation={() => openEvolForm(t.id)}>&#x1F4AC;</button>
								{/if}
								{#if $isAdmin}
									<button class="btn-icon-danger" aria-label="Supprimer" title="Supprimer définitivement"
										on:click|stopPropagation={() => deleteTicket(t)}>&#x1F5D1;️</button>
								{/if}
								<span class="chevron" class:open={expanded}>›</span>
							</div>
						</div>
						{#if !expanded}
							<div class="tk-preview clamp-5">{@html renderDesc(t.description)}</div>
						{/if}
						{#if expanded}
							<div class="tk-body" on:click|stopPropagation on:keydown|stopPropagation>
								{#if showEvolForm === t.id}
									<!-- Formulaire d'évolution -->
									<div class="evol-form">
										<div style="display:flex;gap:.5rem;margin-bottom:.6rem;flex-wrap:wrap">
											<button type="button" class="pill" class:pill-active={evolType === 'commentaire'}
												on:click={() => (evolType = 'commentaire')}>&#x1F4AC; Commentaire</button>
											<button type="button" class="pill" class:pill-active={evolType === 'etat'}
												on:click={() => (evolType = 'etat')}>&#x1F504; Changement d'état</button>
										</div>
										{#if evolType === 'etat'}
											<div class="field">
												<label for="evol-statut-{t.id}">Nouvel état *</label>
												<select id="evol-statut-{t.id}" bind:value={evolNouveauStatut}>
													<option value="">— Choisir —</option>
													<option value="ouvert">&#x1F535; Ouvert</option>
													<option value="en_cours">&#x1F7E1; En cours</option>
													<option value="résolu">&#x1F7E2; Résolu</option>
													<option value="annulé">⚫ Annulé</option>
												</select>
											</div>
										{/if}
										<div class="field">
											<label for="evol-contenu-{t.id}">{evolType === 'etat' ? 'Commentaire (optionnel)' : 'Commentaire *'}</label>
											<textarea id="evol-contenu-{t.id}" bind:value={evolContenu} rows="3"
												placeholder={evolType === 'etat' ? 'Précisions sur ce changement…' : 'Ajoutez un commentaire de suivi…'}
												style="width:100%;padding:.4rem .6rem;border:1px solid var(--color-border);border-radius:6px;font-size:.875rem;resize:vertical"
											></textarea>
										</div>
										<div class="form-actions" style="gap:.5rem">
											<button type="button" class="btn btn-outline" on:click={() => (showEvolForm = null)}>Annuler</button>
											<button type="button" class="btn btn-primary"
												disabled={evolSaving || (evolType === 'etat' && !evolNouveauStatut) || (evolType === 'commentaire' && !evolContenu.trim())}
												on:click={() => addEvolution(t)}>
												{evolSaving ? 'Envoi…' : 'Valider'}
											</button>
										</div>
									</div>
								{:else}
									<!-- Corps normal -->
									<div class="rich-content" style="font-size:.875rem;line-height:1.6;margin-bottom:.5rem">{@html renderDesc(t.description)}</div>
									<small style="color:var(--color-text-muted);font-size:.78rem">
										Créé le {fmtDate(t.cree_le)}
										<span style="font-family:monospace"> · #{t.numero}</span>
									</small>

									<!-- Fil de suivi -->
									{#if evols.length > 0}
										{@const evolsSorted = [...evols].sort((a, b) => new Date(b.cree_le).getTime() - new Date(a.cree_le).getTime())}
										{@const evolCompact = evolsSorted.length > 7 && !expandedTicketEvols.has(t.id)}
										{@const evolsVisible = evolCompact ? evolsSorted.slice(0, 5) : evolsSorted}
										<div class="evol-list">
											{#each evolsVisible as evol, i (evol.id)}
												{#if i > 0}<hr class="evol-sep" />{/if}
												<div class="evol-item evol-{evol.type}">
													<span class="evol-icon">
														{#if evol.type === 'etat'}&#x1F504;{:else if evol.type === 'reponse'}&#x1F4AC;{:else}&#x1F4DD;{/if}
													</span>
													<div class="evol-body">
														<span class="evol-meta">{fmtDatetime(evol.cree_le)}{#if evol.auteur_nom} · {evol.auteur_nom}{/if}</span>
														{#if evol.type === 'etat'}
															<span class="evol-text">
																Statut : <strong>{STATUT_LABELS[evol.ancien_statut ?? ''] || 'Aucun'}</strong> → <strong>{STATUT_LABELS[evol.nouveau_statut ?? ''] || evol.nouveau_statut}</strong>
															</span>
															{#if evol.contenu}
																<div class="evol-content rich-content">{@html renderDesc(evol.contenu)}</div>
															{/if}
														{:else if evol.type === 'reponse' || evol.type === 'commentaire'}
															{#if evol.contenu}
																<div class="evol-content rich-content">{@html renderDesc(evol.contenu)}</div>
															{/if}
														{/if}
													</div>
												</div>
											{/each}
											{#if evolCompact}
												<hr class="evol-sep" />
												<button class="evol-more" on:click|stopPropagation={() => { expandedTicketEvols.add(t.id); expandedTicketEvols = expandedTicketEvols; }}>
													Voir les {evolsSorted.length - 5} entrées plus anciennes
												</button>
											{/if}
										</div>
									{/if}
								{/if}
							</div>
						{/if}
					</div>
				{/each}
			{/if}
		</div>
		{/if}
	</div>
{/if}

<style>
	.kpi-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
		gap: 1rem;
		margin-bottom: 2rem;
	}

	.kpi-card { text-align: center; padding: 1.25rem; }
	.kpi-value { font-size: 2rem; font-weight: 700; color: var(--color-primary); }
	.kpi-label { font-size: .8rem; color: var(--color-text-muted); margin-top: .25rem; }
	.kpi-link { display: block; font-size: .8rem; margin-top: .5rem; text-align: center; width: 100%; }
	.kpi-notif-active { border-color: var(--color-primary); }
	.btn-link { background: none; border: none; color: var(--color-primary); cursor: pointer; padding: 0; font-size: .8rem; }

	.notif-panel { padding: 1rem; }
	.notif-panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: .75rem; }
	.notif-item {
		display: flex; justify-content: space-between; align-items: flex-start;
		padding: .65rem 0; border-top: 1px solid var(--color-border); gap: .75rem;
	}
	.notif-item.notif-urgente .notif-titre { color: var(--color-danger); }
	.notif-content { flex: 1; }
	.notif-titre { font-size: .9rem; font-weight: 600; display: block; margin-bottom: .2rem; }
	.notif-corps { font-size: .85rem; color: var(--color-text-muted); margin: 0 0 .2rem; }
	.notif-date { font-size: .75rem; color: var(--color-text-muted); }

	.dashboard-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1.5rem;
	}
	.dashboard-grid > div, .dashboard-grid > .section-demandes { min-width: 0; overflow: hidden; }
	.section-demandes { grid-column: 1 / -1; }

	.section-title {
		font-size: 1rem;
		font-weight: 600;
		margin-bottom: .75rem;
		color: var(--color-text-muted);
		text-transform: uppercase;
		letter-spacing: .05em;
		font-size: .8rem;
	}

	/* Publication expansible (style page actualités) */
	.pub-expand { margin-bottom: .5rem; border-left: 4px solid var(--color-border); border-radius: var(--radius); overflow: visible; position: relative; background: var(--color-surface); transition: border-left-color .12s; box-shadow: 0 1px 2px rgba(30,58,95,.04); }
	.pub-expand:hover, .pub-expand.expanded { border-left-color: var(--color-primary); }
	.pub-expand.urgent { border-left-color: var(--color-danger); }
	.pub-expand.brouillon { opacity: .7; border-left-style: dashed; }
	.pub-expand.epingle { margin-top: 10px; }
	.pin-badge { position: absolute; top: -9px; left: 8px; display: inline-flex; align-items: center; background: var(--color-primary); color: #fff; font-size: .65rem; padding: .1rem .35rem; border-radius: 8px; line-height: 1.6; z-index: 1; pointer-events: none; }
	.pub-row { display: flex; flex-direction: column; gap: .25rem; padding: .7rem .9rem; cursor: pointer; user-select: none; transition: background .12s; }
	.pub-row:hover { background: var(--color-bg); }
	.pub-row-top { display: flex; align-items: flex-start; gap: .5rem; }
	.pub-row-titre { font-size: .9rem; font-weight: 500; flex: 1; line-height: 1.35; }
	.pub-row-meta { display: flex; align-items: center; gap: .35rem; flex-wrap: wrap; }
	.pub-row-date { font-size: .75rem; color: var(--color-text-muted); margin-left: auto; white-space: nowrap; }
	.pub-preview { padding: .4rem 1rem .6rem; font-size: .875rem; line-height: 1.6; color: var(--color-text-muted); }
	.pub-preview :global(p) { margin: 0 0 .4em; }
	.pub-body { padding: .75rem 1rem 1rem; border-top: 1px solid var(--color-border); }
	.pub-img { width: 100%; max-height: 280px; object-fit: cover; display: block; border-radius: calc(var(--radius) - 2px); margin-bottom: .75rem; }
	.chevron { font-size: 1.1rem; color: var(--color-text-muted); transition: transform .15s; display: inline-block; line-height: 1; }
	.chevron.open { transform: rotate(90deg); }

	/* Évolutions */
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
	.evol-correction { background: #fefce8; }
	.evol-content { margin-top: .2rem; color: var(--color-text); line-height: 1.6; font-size: .85rem; }
	.evol-content :global(p) { margin: 0 0 .3em; }
	.evol-form { padding: .25rem 0 .25rem; }
	.evol-more { width: 100%; background: none; border: none; padding: .45rem; font-size: .8rem; color: var(--color-primary); cursor: pointer; text-align: center; }
	.evol-more:hover { background: var(--color-bg); }
	.pill { padding: .3rem .85rem; border-radius: 999px; border: 1.5px solid var(--color-border); background: var(--color-bg); font-size: .85rem; cursor: pointer; transition: background .15s, border-color .15s, color .15s; white-space: nowrap; line-height: 1.6; }
	.pill:hover { border-color: var(--color-primary); color: var(--color-primary); }
	.pill-active { background: var(--color-primary); border-color: var(--color-primary); color: #fff; }

	.rich-content { font-size: .85rem; line-height: 1.6; color: var(--color-text); margin-bottom: .5rem; }
	.rich-content :global(p) { margin: 0 0 .5em; }
	.rich-content :global(ul), .rich-content :global(ol) { padding-left: 1.4em; margin: 0 0 .5em; }
	.rich-content :global(strong) { font-weight: 600; }
	.rich-content :global(em) { font-style: italic; }

	/* Carte ticket expansible (style page tickets) */
	.tk-expand { margin-bottom: .5rem; border-left: 4px solid var(--color-border); border-radius: var(--radius); overflow: visible; position: relative; background: var(--color-surface); transition: border-left-color .12s; box-shadow: 0 1px 2px rgba(30,58,95,.04); }
	.tk-expand:hover, .tk-expand.expanded { border-left-color: var(--color-primary); }
	.tk-expand.urgent { border-left-color: var(--color-danger); }
	.tk-row { display: flex; align-items: center; gap: .6rem; padding: .7rem .9rem; cursor: pointer; user-select: none; transition: background .12s; }
	.tk-row:hover { background: var(--color-bg); }
	.tk-row-inner { display: flex; align-items: center; gap: .4rem; flex: 1; min-width: 0; overflow: hidden; }
	.tk-cat { flex-shrink: 0; font-size: .95rem; }
	.tk-row-titre { font-size: .9rem; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.tk-row-right { display: flex; align-items: center; gap: .3rem; flex-shrink: 0; }
	.tk-row-date { font-size: .78rem; color: var(--color-text-muted); margin-right: .3rem; white-space: nowrap; }
	.tk-preview { padding: .4rem 1rem .6rem; font-size: .875rem; line-height: 1.6; color: var(--color-text-muted); }
	.tk-preview :global(p) { margin: 0 0 .4em; }
	.tk-body { padding: .75rem 1rem 1rem; border-top: 1px solid var(--color-border); }
	.tk-body :global(p) { margin: 0 0 .5em; }

	/* Événements (accordéon) */
	.ev-expand { margin-bottom: .5rem; border-left: 4px solid var(--color-border); border-radius: var(--radius); overflow: visible; position: relative; background: var(--color-surface); transition: border-left-color .12s; box-shadow: 0 1px 2px rgba(30,58,95,.04); }
	.ev-expand:hover, .ev-expand.expanded { border-left-color: var(--color-primary); }
	.ev-expand.ev-urgent { border-left-color: var(--color-danger); }
	.ev-row { display: flex; align-items: center; gap: .6rem; padding: .7rem .9rem; cursor: pointer; user-select: none; transition: background .12s; }
	.ev-row:hover { background: var(--color-bg); }
	.ev-row-inner { display: flex; flex-direction: column; align-items: flex-start; gap: .2rem; flex: 1; min-width: 0; }
	.ev-row-main { display: flex; align-items: center; gap: .4rem; min-width: 0; width: 100%; }
	.ev-row-meta { display: flex; align-items: center; gap: .35rem; flex-wrap: wrap; }
	.ev-meta-item { font-size: .74rem; color: var(--color-text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 220px; }
	.ev-meta-badge { font-size: .7rem !important; padding: .1rem .4rem !important; line-height: 1.4 !important; }
	.ev-type-icon { flex-shrink: 0; font-size: .95rem; }
	.ev-row-titre { font-size: .9rem; font-weight: 500; flex: 1; line-height: 1.35; }
	.ev-row-right { display: flex; align-items: center; gap: .3rem; flex-shrink: 0; }
	.ev-row-date { font-size: .75rem; color: var(--color-text-muted); margin-right: .3rem; white-space: nowrap; }
	.ev-preview { padding: .35rem 1rem .55rem; font-size: .875rem; line-height: 1.6; color: var(--color-text-muted); }
	.ev-body { padding: .75rem 1rem 1rem; border-top: 1px solid var(--color-border); }
	.event-meta { font-size: .8rem; color: var(--color-text-muted); display: block; }
	.event-desc { font-size: .85rem; color: var(--color-text-muted); margin: .2rem 0 0; }
	.clamp-2 { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }

	@media (max-width: 1023px) {
		.dashboard-grid { grid-template-columns: 1fr 1fr; }
	}
	@media (max-width: 767px) {
		.dashboard-grid { grid-template-columns: 1fr; }
		.section-demandes { grid-column: 1; }
	}
</style>
