<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { currentUser, isCS, isAdmin, hasResidentRole, isAdminOnly } from '$lib/stores/auth';
	import { locale, NAV_LABELS } from '$lib/stores/locale';
	import { auth as authApi } from '$lib/api';
	import { setUser } from '$lib/stores/auth';
	import { configStore, siteNomStore, getPageConfig } from '$lib/stores/pageConfig';
	import Icon from '$lib/components/Icon.svelte';

	// ── Valeurs par défaut de chaque entrée de menu ────────────────────────
	const NAV_DEFAULTS: Record<string, { configId: string; icon: string; navLabel: string }> = {
		'/tableau-de-bord': { configId: 'tableau-de-bord', icon: 'layout-dashboard',    navLabel: 'Accueil' },
		'/actualites':      { configId: 'actualites',       icon: 'newspaper',           navLabel: 'Actualités' },
		'/calendrier':      { configId: 'calendrier',       icon: 'calendar-days',       navLabel: 'Calendrier' },
		'/tickets':         { configId: 'mes-demandes',     icon: 'message-square-text', navLabel: 'Tickets' },
		'/annuaire':        { configId: 'annuaire',         icon: 'users',               navLabel: 'Annuaire' },
		'/residence':       { configId: 'residence',        icon: 'building-2',          navLabel: 'Résidence' },
		'/mon-lot':         { configId: 'mon-lot',          icon: 'door-closed',         navLabel: 'Mes lots' },
		'/acces-securite':  { configId: 'acces-badges',    icon: 'key-round',           navLabel: 'Accès & badges' },
		'/prestataires':    { configId: 'prestataires',     icon: 'hard-hat',            navLabel: 'Prestataires' },
		'/sondages':        { configId: 'communaute',       icon: 'users-round',         navLabel: 'Communauté' },
		'/faq':             { configId: 'faq',              icon: 'help-circle',         navLabel: 'FAQ' },
		'/espace-cs':       { configId: 'espace-cs',        icon: 'shield-half',         navLabel: 'Espace CS' },
		'/admin':           { configId: 'admin',            icon: 'sliders-horizontal',  navLabel: 'Admin' },
	};

	function navItem(href: string, raw: Record<string, string>) {
		const def = NAV_DEFAULTS[href] ?? { configId: '', icon: 'help-circle', navLabel: href };
		const cfg = def.configId
			? getPageConfig(raw, def.configId, { titre: def.navLabel, descriptif: '', navLabel: def.navLabel, icone: def.icon })
			: { navLabel: def.navLabel, icone: def.icon };
		return { href, icon: cfg.icone ?? def.icon, label: cfg.navLabel ?? def.navLabel };
	}

	// Ordre par défaut complet (toutes les entrées, filtrage par rôle ensuite)
	const DEFAULT_HREFS = [
		'/tableau-de-bord', '/residence', '/mon-lot', '/acces-securite',
		'/annuaire', '/prestataires', '/calendrier', '/actualites',
		'/tickets', '/sondages', '/faq', '/espace-cs', '/admin',
	];

	// Correspondance configId → href pour lire l'ordre stocké en backend
	const idToHref: Record<string, string> = Object.fromEntries(
		Object.entries(NAV_DEFAULTS).map(([href, def]) => [def.configId, href])
	);

	let menuOpen = false;

	function toggleMenu() { menuOpen = !menuOpen; }
	function closeMenu() { menuOpen = false; }

	function logout() {
		setUser(null);
		goto('/auth/connexion');
		authApi.logout().catch(() => {}); // révocation token en arrière-plan
	}

	$: t = NAV_LABELS[$locale];
	$: brandIcon = $configStore['site_icone'] ?? 'building-2';
	$: siteNom = $siteNomStore;

	function computeOrderedHrefs(orderJson: string | undefined): string[] {
		if (!orderJson) return DEFAULT_HREFS;
		try {
			const ids: string[] = JSON.parse(orderJson);
			const ordered = ids.map(id => idToHref[id]).filter((h): h is string => !!h && h in NAV_DEFAULTS);
			const remaining = DEFAULT_HREFS.filter(h => !ordered.includes(h));
			return [...ordered, ...remaining];
		} catch { return DEFAULT_HREFS; }
	}

	// Ordre lu depuis le backend (pages_order), fallback sur DEFAULT_HREFS
	$: _pagesOrderJson = $configStore['pages_order'];
	$: orderedHrefs = computeOrderedHrefs(_pagesOrderJson);

	$: allNav = orderedHrefs
		.filter(href => {
			const statut = $currentUser?.statut;
			if (href === '/sondages' && (statut === 'syndic' || statut === 'mandataire')) return false;
			if (href === '/prestataires') return $isCS;
			if (href === '/espace-cs')   return $isCS && !$isAdminOnly;
			if (href === '/admin')       return $isAdmin;
			return $hasResidentRole;
		})
		.map(href => navItem(href, $configStore));

	function isActive(href: string) {
		return $page.url.pathname.startsWith(href);
	}

	// Fermer le menu lors d'un changement de page
	$: $page.url.pathname, closeMenu();
</script>

<!-- ─── Sidebar desktop ─────────────────────────────────────────────────── -->
<nav class="sidebar">
	<a href="/tableau-de-bord" class="brand brand-link">
		<span class="brand-icon"><Icon name={brandIcon} size={22} /></span>
		<span class="brand-name">{siteNom}</span>
	</a>

	<div class="nav-section">
		{#each allNav as item}
			<a href={item.href} class="nav-item" class:active={isActive(item.href)}>
				<span class="nav-icon"><Icon name={item.icon} size={18} /></span>
				<span class="nav-label">{item.label}</span>
			</a>
		{/each}
	</div>

	<div class="nav-footer">
		<a href="/profil" class="nav-item" class:active={isActive('/profil')}>
			<span class="nav-icon"><Icon name="user" size={18} /></span>
			<span class="nav-label">{$currentUser?.prenom ?? t['/profil']}</span>
		</a>
		<a href="/manuel-utilisateur.html" target="_blank" rel="noopener" class="nav-item nav-guide">
			<span class="nav-icon"><Icon name="book-open" size={18} /></span>
			<span class="nav-label">Guide</span>
		</a>
		<button class="nav-item nav-logout" on:click={logout} type="button">
			<span class="nav-icon"><Icon name="log-out" size={18} /></span>
			<span class="nav-label">{t['deconnexion']}</span>
		</button>
	</div>
</nav>

<!-- ─── Topbar mobile (hamburger) ──────────────────────────────────────── -->
<header class="mobile-topbar">
	<a href="/tableau-de-bord" class="brand-link" style="display:flex;align-items:center;gap:.4rem;text-decoration:none;color:inherit">
		<span class="brand-icon"><Icon name={brandIcon} size={22} /></span>
		<span class="brand-name">{siteNom}</span>
	</a>
	<button class="hamburger" on:click={toggleMenu} aria-label="Menu" aria-expanded={menuOpen}>
		{#if menuOpen}
			<span class="hb-line hb-close-1"></span>
			<span class="hb-line hb-close-2"></span>
		{:else}
			<span class="hb-line"></span>
			<span class="hb-line"></span>
			<span class="hb-line"></span>
		{/if}
	</button>
</header>

<!-- ─── Overlay menu mobile ────────────────────────────────────────────── -->
{#if menuOpen}
	<!-- svelte-ignore a11y-click-events-have-key-events -->
	<!-- svelte-ignore a11y-no-static-element-interactions -->
	<div class="overlay-backdrop" on:click={closeMenu}></div>
	<div class="overlay-menu">
		<div class="overlay-nav">
			{#each allNav as item}
				<a href={item.href} class="overlay-item" class:active={isActive(item.href)}>
					<span class="nav-icon"><Icon name={item.icon} size={20} /></span>
					<span>{item.label}</span>
				</a>
			{/each}
		</div>
		<div class="overlay-footer">
			<a href="/profil" class="overlay-item" class:active={isActive('/profil')}>
				<span class="nav-icon"><Icon name="user" size={20} /></span>
				<span>{$currentUser?.prenom ?? t['/profil']}</span>
			</a>
			<a href="/manuel-utilisateur.html" target="_blank" rel="noopener" class="overlay-item nav-guide">
				<span class="nav-icon"><Icon name="book-open" size={20} /></span>
				<span>Guide</span>
			</a>
			<button class="overlay-item nav-logout" on:click={logout} type="button">
				<span class="nav-icon"><Icon name="log-out" size={20} /></span>
				<span>{t['deconnexion']}</span>
			</button>
		</div>
	</div>
{/if}

<style>
	/* ── Desktop sidebar ───────────────────────────────────────────────────── */
	.sidebar {
		position: fixed;
		top: 0;
		left: 0;
		width: 185px;
		height: 100vh;
		background: #fff;
		border-right: 1px solid var(--color-border);
		display: flex;
		flex-direction: column;
		padding: 1rem 0;
		z-index: 100;
	}

	.brand, .brand-link {
		display: flex;
		align-items: center;
		gap: .6rem;
		padding: .5rem 1.25rem 1.25rem;
		border-bottom: 1px solid var(--color-border);
		margin-bottom: .5rem;
		text-decoration: none;
		color: inherit;
	}
	.brand-link:hover { opacity: .8; }

	.brand-icon { display: flex; align-items: center; color: var(--color-primary); }
	.brand-name { font-weight: 700; font-size: 1.1rem; color: var(--color-primary); }

	.nav-section { flex: 1; overflow-y: auto; -webkit-overflow-scrolling: touch; padding: 0 .5rem; }

	.nav-item {
		display: flex;
		align-items: center;
		gap: .6rem;
		padding: .55rem .75rem;
		border-radius: var(--radius);
		color: var(--color-text);
		font-size: .9rem;
		text-decoration: none;
		transition: background .12s;
		border: none;
		background: transparent;
		width: 100%;
		cursor: pointer;
		margin-bottom: .15rem;
		touch-action: manipulation;
		-webkit-tap-highlight-color: transparent;
	}

	.nav-item:hover { background: var(--color-bg); }
	.nav-item.active { background: var(--color-primary-light); color: var(--color-primary); font-weight: 600; }

	.nav-icon { display: flex; align-items: center; justify-content: center; width: 1.25rem; flex-shrink: 0; font-size: 1.1rem; }

	.nav-footer {
		padding: .5rem;
		border-top: 1px solid var(--color-border);
		margin-top: .5rem;
	}

	.nav-logout { color: var(--color-text-muted); }
	.nav-logout:hover { color: var(--color-danger); background: #FDEDEC; }
	.nav-guide { color: var(--color-text-muted); font-size: .85rem; }



	/* ── Mobile topbar ─────────────────────────────────────────────────────── */
	.mobile-topbar { display: none; }

	/* ── Overlay menu ──────────────────────────────────────────────────────── */
	.overlay-backdrop {
		display: none;
		position: fixed;
		top: 0; right: 0; bottom: 0; left: 0;
		background: rgba(0,0,0,.35);
		z-index: 199;
	}

	.overlay-menu {
		display: none;
		position: fixed;
		top: 3.25rem;
		left: 0;
		right: 0;
		bottom: 0;
		background: #fff;
		z-index: 200;
		flex-direction: column;
		overflow-y: auto;
	}

	.overlay-nav {
		flex: 1;
		padding: .5rem;
		overflow-y: auto;
	}

	.overlay-item {
		display: flex;
		align-items: center;
		gap: .75rem;
		padding: .75rem 1rem;
		border-radius: var(--radius);
		color: var(--color-text);
		font-size: 1rem;
		text-decoration: none;
		border: none;
		background: transparent;
		width: 100%;
		cursor: pointer;
		margin-bottom: .1rem;
		touch-action: manipulation;
		-webkit-tap-highlight-color: transparent;
	}

	.overlay-item:hover { background: var(--color-bg); }
	.overlay-item.active { background: var(--color-primary-light); color: var(--color-primary); font-weight: 600; }

	.overlay-footer {
		padding: .5rem;
		border-top: 1px solid var(--color-border);
	}

	/* ── Hamburger button ──────────────────────────────────────────────────── */
	.hamburger {
		display: flex;
		flex-direction: column;
		justify-content: center;
		gap: 5px;
		width: 2.25rem;
		height: 2.25rem;
		background: transparent;
		border: none;
		cursor: pointer;
		padding: .3rem;
		border-radius: var(--radius);
	}

	.hamburger:hover { background: var(--color-bg); }

	.hb-line {
		display: block;
		width: 100%;
		height: 2px;
		background: var(--color-text);
		border-radius: 2px;
		transition: transform .2s, opacity .2s;
	}

	.hb-close-1 {
		transform: translateY(7px) rotate(45deg);
	}

	.hb-close-2 {
		transform: translateY(-7px) rotate(-45deg);
	}

	/* ── Responsive ────────────────────────────────────────────────────────── */
	@media (max-width: 767px) {
		.sidebar { display: none; }

		.mobile-topbar {
			display: flex;
			align-items: center;
			gap: .6rem;
			position: fixed;
			top: 0;
			left: 0;
			right: 0;
			height: 3.25rem;
			background: #fff;
			border-bottom: 1px solid var(--color-border);
			padding: 0 1rem;
			z-index: 100;
		}

		.mobile-topbar .brand-name {
			flex: 1;
			font-weight: 700;
			font-size: 1.05rem;
			color: var(--color-primary);
		}

		.overlay-backdrop { display: block; }
		.overlay-menu { display: flex; }
	}
</style>
