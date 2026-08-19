<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { currentUser, isCS, isAdmin, isProprio } from '$lib/stores/auth';
	import { flux, lots, calendrier as calApi, prestataires as prestApi, type FluxItem, type FluxProchain, type FluxResponse } from '$lib/api';
	import { kanbanEvVisible, kanbanColVisible, kanbanEvMatchesYear, devisPonctuelToKanban } from '$lib/kanban';
	import { getPageConfig, configStore, siteNomStore, defautsDePage } from '$lib/stores/pageConfig';
	import { fmtDateLong, fmtTime } from '$lib/date';
	import { perimetreLabel, concerneTous, batimentsCibles, estPerimetreParDefaut } from '$lib/utils';
	import Icon from '$lib/components/Icon.svelte';
	import SectionRepliee from '$lib/components/SectionRepliee.svelte';
	import Avatar from '$lib/components/Avatar.svelte';
	import FluxCard from '$lib/components/FluxCard.svelte';
	import RaccourcisRapides from '$lib/components/RaccourcisRapides.svelte';
	import { toast } from '$lib/components/Toast.svelte';
	// Toutes les règles du fil (apparence, liens, appartenance aux trois
	// registres) vivent dans ce module — cf. `$lib/flux.ts`.
	import {
		dateDeReference, estEpingle, estNonResolu, estUrgent,
		typeCouleur, typeFond, typeLibelle, typeLink,
	} from '$lib/flux';

	$: _pc = getPageConfig($configStore, 'tableau-de-bord', defautsDePage('tableau-de-bord'));
	$: _siteNom = $siteNomStore;

	let data: FluxResponse | null = null;
	let userLots: any[] = [];
	let loading = true;
	let ready = false;
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
	});

	// ── Rôles & filtrage ───────────────────────────────────────────────────
	$: canSeeAG = ($currentUser?.roles ?? []).some((r: string) =>
		['propriétaire', 'conseil_syndical', 'admin'].includes(r)
	);
	$: isLocataire = $currentUser?.statut === 'locataire';
	$: userBatimentId = $currentUser?.batiment_id ?? null;
	$: isSyndicUser = $currentUser?.statut === 'syndic' || ($currentUser?.roles ?? []).includes('syndic');

	//  Ce filtre réimplémentait la règle du serveur : un motif `bat:(\d+)` analysé à
	//  la main et la liste des périmètres transverses écrite en dur — troisième
	//  copie de la même énumération. Il s'appuie désormais sur l'arborescence, comme
	//  `api/app/utils/visibility.py`. Ce n'est qu'un filtre d'AFFICHAGE : le serveur
	//  a déjà écarté ce que l'utilisateur n'a pas le droit de voir.
	function isInUserPerimeter(perimetres: string[] | null | undefined): boolean {
		if ($isAdmin || $isCS || isSyndicUser) return true;
		const perims = perimetres ?? [];
		if (perims.length === 0) return true;
		if (concerneTous(perims)) return true;
		if (userBatimentId == null) return true;
		return batimentsCibles(perims).includes(userBatimentId);
	}
	function parseItemPerimetres(item: FluxItem): string[] {
		const m = item.meta;
		if (m.perimetre_cible && Array.isArray(m.perimetre_cible)) return m.perimetre_cible as string[];
		if (typeof m.perimetre === 'string' && m.perimetre) return (m.perimetre as string).split(',').map(s => s.trim());
		return [];
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

	// ── Fil et agenda ne racontent pas la même chose ───────────────────────
	// Un événement à venir était écarté du fil deux fois : parce qu'il figurait
	// déjà dans « Prochaines échéances », et parce que sa date était future. Un
	// nettoyage programmé restait donc introuvable dans le fil (01/08/2026),
	// alors qu'il venait d'être créé — c'est-à-dire qu'il s'était bien passé
	// quelque chose.
	// Le fil répond à « quoi de neuf ? » et date la ligne à l'ANNONCE (le
	// backend renvoie `date = cree_le`) ; l'agenda répond à « quoi ensuite ? »
	// et affiche la date de tenue. Les deux vues coexistent sans doublon de
	// sens : ce n'est pas la même information.
	$: filItems = filteredItems;

	// ── Classement du fil : récent / ancien / masqué ───────────────────────
	const THIRTY_DAYS = 30 * 86400000;
	const YEAR_PLUS = 377 * 86400000;

	let recentItems: FluxItem[] = [];
	let olderItems: FluxItem[] = [];
	$: {
		const _recent: FluxItem[] = [];
		const _older: FluxItem[] = [];
		const now = Date.now();
		for (const item of filItems) {
			// Un élément épinglé a son propre bandeau : le laisser aussi dans la
			// chronologie le ferait lire deux fois. C'est également ce qui le rend
			// insensible au vieillissement — un élément qu'on a explicitement voulu
			// garder en vue ne doit pas s'effacer au bout de 30 jours.
			if (estEpingle(item)) continue;
			const age = now - dateDeReference(item);
			if (estNonResolu(item)) { _recent.push(item); continue; }
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

	$: dashDevisPonctuels = dashDevis
		.filter((d: any) => !d.frequence_type && !d.frequence_valeur)
		.map((d: any) => devisPonctuelToKanban(d));

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

	//  Réimplémentait PERIMETRE_LABELS, et avait divergé deux fois sans que
	//  personne le voie : `aful` manquant, et une espace INSÉCABLE dans « Bât. 1 »
	//  (#316, détail dans scripts/check-perimetres.mjs). « résidence » reste masqué
	//  — c'est le cas par défaut, l'afficher n'apprend rien.
	const dashKanbanPerimLabel = (p: string): string =>
		perimetreLabel(p ?? '');

	$: _dashKanbanCtx = { isCS: $isCS, isAdmin: $isAdmin, canSeeAG, statut: $currentUser?.statut ?? '' };

	$: dashKanbanEvs = [...kanbanRawEvs, ...dashDevisPonctuels].filter(ev => {
		if (!ev.statut_kanban || ev.statut_kanban === 'annule') return false;
		if (!kanbanEvVisible(ev, _dashKanbanCtx)) return false;
		if (!kanbanEvMatchesYear(ev, _kanbanYear)) return false;
		return true;
	});

	$: dashKanbanCols = DASH_KANBAN_COLS
		.filter(col => kanbanColVisible(col.id, _dashKanbanCtx))
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

	// ── Les trois registres du fil ─────────────────────────────────────────
	// 1. 🔴 Urgences  — « qu'est-ce qui brûle ? »        (plafonné à 3, s'auto-périme)
	// 2. 📌 Épinglé   — « qu'est-ce qu'il ne faut pas perdre de vue ? »
	// 3. Chronologie  — « quoi de neuf ? »               (recentItems / olderItems)
	// Les filtres sont dans `$lib/flux.ts` et sont mutuellement exclusifs : un
	// élément urgent ET épinglé ne paraît qu'en urgence, la gravité primant.
	$: urgentItems = filteredItems.filter(estUrgent);
	$: pinnedItems = filteredItems.filter(estEpingle);

	//  `countByType` vivait ici et n'alimentait qu'une chose : la pastille
	//  Tickets. Elle comptait donc les tickets ouverts **du fil affiché**, après
	//  les filtres de l'utilisateur — la seule de la rangée à bouger avec eux,
	//  sans que rien à l'écran ne le laisse deviner. Le nombre vient désormais du
	//  serveur, comme ses voisines (#399).

	// ── Helpers ────────────────────────────────────────────────────────────
	function ouvrir(item: FluxItem) {
		const lien = typeLink(item);
		if (lien) goto(lien);
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
		// `fmtTime` épingle Europe/Paris ; les `toLocaleTimeString` qui étaient ici
		// n'indiquaient aucun fuseau et suivaient donc celui du navigateur — juste
		// par coïncidence pour un résident en France, faux en déplacement.
		const hStart = fmtTime(debut);
		const hEnd = fmtTime(fin);
		return { pct, label: `En cours (${hStart}–${hEnd})`, active: true };
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
				<!-- Raccourci vers le profil. Sans photo, la pastille porte un
				     crayon : c'est l'invitation à en déposer une, sans texte ni
				     bandeau qui encombrerait l'en-tête. -->
				<a
					class="hero-avatar"
					href="/profil"
					title={$currentUser?.photo_url ? 'Mon profil' : 'Mon profil — ajouter une photo'}
					aria-label={$currentUser?.photo_url ? 'Mon profil' : 'Mon profil — ajouter une photo de profil'}
				>
					<Avatar photoUrl={$currentUser?.photo_url} prenom={$currentUser?.prenom} nom={$currentUser?.nom} />
					{#if !$currentUser?.photo_url}
						<span class="hero-avatar-badge" aria-hidden="true"><Icon name="pencil" size={9} /></span>
					{/if}
				</a>
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

	<!-- La relance syndic est annoncée UNE fois, par « ALERTES URGENTES » plus
	     bas, à partir de `data.sante.tickets_relance_syndic` que le backend
	     calcule déjà. Une seconde carte vivait ici, alimentée par un appel API
	     distinct dont elle lisait `.length` sur un objet `{delai_jours, tickets}`
	     — donc `undefined`, donc jamais affichée. Le doublon était invisible
	     précisément parce qu'il était cassé. -->

	<!-- ═══ RACCOURCIS RAPIDES ═════════════════════════════════════════════ -->
	<!-- Qui voit quelle pastille, et d'où vient chaque nombre : `$lib/raccourcis.ts`,
	     et nulle part ailleurs. La page recomposait ici la règle d'accès à
	     l'Espace CS, que le serveur écrivait déjà de son côté (#399). -->
	<RaccourcisRapides sante={data.sante} {ready} />

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
					on:click={() => ouvrir(u)}
					on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && ouvrir(u)}
				>
					<legend class="urgence-legend">🔴 URGENCE
						<span class="flux-type-chip" style="background:{typeFond(u.type)};color:{typeCouleur(u.type)}">
							{typeLibelle(u.type)}
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
								Aujourd'hui {fmtTime(String(u.meta.debut))} → {fmtTime(String(u.meta.fin))}
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

	<!-- ═══ ÉPINGLÉ ═══════════════════════════════════════════════════════
	     Registre volontairement CALME : ni rouge ni alerte. Les urgences
	     au-dessus signalent ce qui brûle ; ce bandeau-ci répond à « qu'est-ce
	     qu'il ne faut pas perdre de vue ? ». Le fondre dans les urgences les
	     userait : un épinglé ne s'auto-périme pas, il resterait indéfiniment
	     dans un bandeau d'alerte, et le plafond de 3 des urgences finirait par
	     évincer une urgence réelle. -->
	{#if pinnedItems.length > 0}
		<div class="section-reveal" class:section-visible={ready} style="--delay:.15s">
			<div class="epingle-bloc">
				<h2 class="epingle-titre">📌 Épinglé</h2>
				<div class="flux-timeline epingle-timeline">
					{#each pinnedItems as item (item.id)}
						<FluxCard
							{item}
							expanded={expandedItem === item.id}
							on:toggle={(e) => toggleItem(e.detail)}
						/>
					{/each}
				</div>
			</div>
		</div>
	{/if}

	<!-- ═══ KANBAN (masqué pour les locataires) ═════════════════════════════ -->
	{#if !isLocataire}
	<div class="section-reveal" class:section-visible={ready} style="--delay:.2s">
		<div class="kb-header">
			<h2 class="section-title" style="margin:0">&#x1F4CB; Kanban</h2>
			<a href="/calendrier?onglet=kanban" class="kb-voir-lien">Voir le Kanban complet →</a>
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
										{#if !estPerimetreParDefaut(item.perimetre)}
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
										{#if !estPerimetreParDefaut(item.perimetre)}
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
					<a href="/calendrier?onglet=kanban" class="kb-mobile-lien">Voir le Kanban complet →</a>
				</div>
			{/if}
		{/if}
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
				{#each group.items as item (item.id)}
					<FluxCard
						{item}
						expanded={expandedItem === item.id}
						on:toggle={(e) => toggleItem(e.detail)}
					/>
				{/each}
			{/each}
		</div>

		<!-- Accordéon : anciens (>30 jours) -->
		{#if olderItems.length > 0}
			<div class="section-reveal" class:section-visible={ready} style="--delay:.35s">
				<!--  Le bandeau était réimplémenté ici (`.older-toggle`, `.older-count`,
				      chevron à GAUCHE) — troisième écriture d'une même notion, avec un
				      troisième aspect (#516). Il passe sur `SectionRepliee`, comme les
				      Archives des Actualités et des Petites annonces.

				      ⚠️ Le libellé, lui, ne devient PAS « Archives » : ceci n'est pas une
				      pile d'objets rangés, c'est la SUITE du fil d'activité. Le look
				      s'unifie, la notion reste distincte. -->
				<SectionRepliee titre="&#x1F553; Activité plus ancienne" compte={olderItems.length}
					bind:ouvert={olderOpen} />
				{#if olderOpen}
					<div class="flux-timeline older-timeline">
						{#each olderDayGroups as group}
							<div class="flux-day-label">{group.label}</div>
							{#each group.items as item (item.id)}
								<FluxCard
									{item}
									expanded={expandedItem === item.id}
									on:toggle={(e) => toggleItem(e.detail)}
								/>
							{/each}
						{/each}
					</div>
				{/if}
			</div>
		{/if}
	{/if}
{/if}

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
	.hero-top { display: flex; justify-content: space-between; align-items: flex-start; gap: .75rem; }
	/* L'anneau clair détache la pastille du dégradé bleu ; le fond de repli des
	   initiales reste translucide pour ne pas concurrencer la salutation. */
	.hero-avatar {
		position: relative; flex-shrink: 0;
		/* Cible tactile ≥ 44 px (2,6 rem + l'anneau) — atteignable au pouce. */
		display: flex; align-items: center; justify-content: center;
		min-width: 44px; min-height: 44px;
		padding: 2px; border-radius: 50%;
		background: rgba(255, 255, 255, .3);
		text-decoration: none;
		transition: background .2s ease, transform .2s ease;
		--avatar-size: 2.6rem;
		--avatar-bg: rgba(255, 255, 255, .18);
		--avatar-color: #fff;
	}
	.hero-avatar:hover { background: rgba(255, 255, 255, .6); transform: scale(1.04); }
	.hero-avatar:focus-visible { outline: 2px solid var(--color-accent, #C9983A); outline-offset: 3px; }
	.hero-avatar-badge {
		position: absolute; right: -1px; bottom: -1px;
		width: 1.05rem; height: 1.05rem; border-radius: 50%;
		background: var(--color-accent, #C9983A); color: #fff;
		display: flex; align-items: center; justify-content: center;
		box-shadow: 0 0 0 2px var(--color-primary);
	}
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

	/* Les styles de la rangée de raccourcis sont partis avec leur balisage dans
	   `RaccourcisRapides.svelte` — Svelte scope les styles au composant. */

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
	/* ═══ ÉPINGLÉ ═══════════════════════════════════════════════════════
	   Délibérément sobre : gris et bleu de la charte, aucun rouge, aucune
	   animation. Ce bandeau doit se distinguer de la chronologie sans entrer
	   en concurrence avec les urgences au-dessus — c'est un pense-bête, pas
	   une alerte. */
	.epingle-bloc {
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-left: 4px solid var(--color-primary);
		border-radius: var(--radius);
		padding: .75rem 1rem 1rem;
		margin-bottom: 1rem;
	}
	.epingle-titre {
		font-size: .72rem; font-weight: 700; text-transform: uppercase;
		letter-spacing: .06em; color: var(--color-text-muted);
		margin: 0 0 .25rem;
	}
	/* La carte est la même que dans le fil : seule la ligne de temps est
	   inutile ici, l'ordre chronologique n'étant pas le sujet. */
	.epingle-timeline { padding-left: 1.5rem; }
	.epingle-timeline::before { display: none; }

	/* ═══ ACCORDÉON ANCIENS ═════════════════════════════════════════════ */
	.older-timeline { opacity: .85; }

	/* ═══ RESPONSIVE ════════════════════════════════════════════════════ */
	@media (min-width: 768px) {
		.kb-mobile { display: none !important; }
	}
	@media (max-width: 767px) {
		.hero { margin: -.75rem -.75rem 0; padding: 1.25rem 1rem 1rem; }
		.kpi-grid { grid-template-columns: 1fr; }
		.flux-timeline { padding-left: 1.25rem; }
		.flux-timeline::before { left: .35rem; }
		.consignes-card { gap: .5rem; padding: .6rem .75rem; }
		.consignes-icon { font-size: 1.2rem; }
		.relance-alerte-card { padding: .55rem .75rem; gap: .5rem; }
		.relance-alerte-text strong { font-size: .82rem; }
		.kb-desktop { display: none !important; }
		.kb-mobile { display: block; }
	}
</style>
