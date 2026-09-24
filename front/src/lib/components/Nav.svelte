<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { currentUser, isCS, isAdmin, hasResidentRole, isAdminOnly } from '$lib/stores/auth';
	import { locale, NAV_LABELS } from '$lib/stores/locale';
	import { auth as authApi } from '$lib/api';
	import { setUser } from '$lib/stores/auth';
	import { CHEMIN_CONNEXION } from '$lib/redirection';
	import { configStore, siteNomStore, getPageConfig } from '$lib/stores/pageConfig';
	import Icon from '$lib/components/Icon.svelte';
	import LiensGuide from '$lib/components/LiensGuide.svelte';
	import BandeauDelegation from '$lib/components/BandeauDelegation.svelte';
	import {
		HREFS_DEFAUT,
		HREF_VERS_PAGE,
		ID_VERS_HREF,
		PAGES_MENU,
		identifiantsRepetes,
		ordonnerPages,
	} from '$lib/pages';

	// Les valeurs par défaut, l'ordre et la correspondance identifiant → route
	// viennent tous de `$lib/pages.ts` — voir l'en-tête de ce fichier pour les trois
	// divergences qu'entretenaient les deux tables d'avant (#401).

	function navItem(href: string, raw: Record<string, string>) {
		const def = HREF_VERS_PAGE[href];
		if (!def) return { href, icon: 'help-circle', label: href };
		const cfg = getPageConfig(raw, def.id, {
			titre: def.titre,
			descriptif: def.descriptif,
			navLabel: def.navLabel,
			icone: def.icone,
		});
		return { href, icon: cfg.icone ?? def.icone, label: cfg.navLabel ?? def.navLabel };
	}

	let menuOpen = false;

	function toggleMenu() {
		menuOpen = !menuOpen;
	}
	function closeMenu() {
		menuOpen = false;
	}

	function logout() {
		setUser(null);
		//  Rien à conserver : on vient de se déconnecter volontairement. Mais
		//  l'adresse vient de `lib/redirection`, comme les cinq autres portes.
		goto(CHEMIN_CONNEXION);
		authApi.logout().catch(() => {}); // révocation token en arrière-plan
	}

	$: t = NAV_LABELS[$locale];
	$: brandIcon = $configStore['site_icone'] ?? 'building-2';
	$: siteNom = $siteNomStore;

	function computeOrderedHrefs(orderJson: string | undefined): string[] {
		if (!orderJson) return HREFS_DEFAUT;
		try {
			const ids: string[] = JSON.parse(orderJson);
			// Un identifiant sans route est une INCOHÉRENCE DE DONNÉES, pas un cas
			// normal : l'ordre enregistré nomme une page que le menu ne connaît pas.
			// L'ancien `.filter()` les jetait sans un mot — il masquait précisément le
			// défaut qu'on cherchait quand l'ordre ne semblait pas appliqué (#401).
			const inconnus = ids.filter((id) => !(id in ID_VERS_HREF));
			if (inconnus.length)
				console.warn(
					`[Nav] pages_order contient ${inconnus.length} identifiant(s) sans entrée de menu, ignoré(s) : ${inconnus.join(', ')}`,
				);
			//  Même raison, autre incohérence : un identifiant RÉPÉTÉ affichait la page
			//  deux fois dans le menu, et faisait bien pire dans « Descriptif pages »
			//  (`each_key_duplicate`, erreur fatale de Svelte — cf. `ordonnerPages`).
			const repetes = identifiantsRepetes(ids);
			if (repetes.length)
				console.warn(
					`[Nav] pages_order répète ${repetes.length} identifiant(s), dédoublonné(s) : ${repetes.join(', ')}`,
				);
			//  🔴 L'ordre se calcule à UN seul endroit. Ces quatre lignes réimplémentaient
			//  `ordonnerPages` — même notion, deux écritures — et elles ont divergé sur le
			//  cas limite qui compte : celle-ci dédoublonnait par accident (`remaining`
			//  filtre sur `ordered`), l'autre non, et c'est l'autre qui rendait l'écran.
			return ordonnerPages(PAGES_MENU, ids).map((p) => p.href as string);
		} catch {
			console.warn('[Nav] pages_order illisible (JSON invalide) — ordre par défaut appliqué');
			return HREFS_DEFAUT;
		}
	}

	// Ordre lu depuis le backend (pages_order), repli sur l'ordre par défaut
	$: _pagesOrderJson = $configStore['pages_order'];
	$: orderedHrefs = computeOrderedHrefs(_pagesOrderJson);

	$: allNav = orderedHrefs
		.filter((href) => {
			const statut = $currentUser?.statut;
			if (
				href === '/sondages' &&
				(statut === 'syndic' || statut === 'mandataire' || statut === 'aidant')
			)
				return false;
			if (href === '/prestataires') return $isCS;
			if (href === '/espace-cs') return $isCS && !$isAdminOnly;
			if (href === '/delegations')
				return $isCS || ($currentUser?.delegations_aidant?.length ?? 0) > 0 || statut === 'aidant';
			if (href === '/admin') return $isAdmin;
			return $hasResidentRole;
		})
		.map((href) => navItem(href, $configStore));

	function isActive(href: string) {
		return $page.url.pathname.startsWith(href);
	}

	//  Fermer le menu lors d'un changement de page.
	//
	//  ⚠️ La dépendance passe en ARGUMENT plutôt qu'en expression séquentielle
	//  (`$: $page.url.pathname, closeMenu()`). Les deux formes ont le même effet,
	//  mais la seconde se lit comme une valeur calculée puis jetée — ce qui est
	//  presque toujours un `=` oublié, et ce qu'ESLint signale à raison. Ici
	//  l'argument DIT ce qui déclenche : le chemin change, le menu se ferme.
	function fermerAuChangementDePage(_chemin: string) {
		closeMenu();
	}
	$: fermerAuChangementDePage($page.url.pathname);
</script>

<!-- ─── Sidebar desktop ─────────────────────────────────────────────────── -->
<nav class="sidebar">
	<a href="/tableau-de-bord" class="brand brand-link">
		<span class="brand-icon"><Icon name={brandIcon} size={22} /></span>
		<span class="brand-name">{siteNom}</span>
	</a>

	<div class="nav-section">
		{#each allNav as item (item.href)}
			<a href={item.href} class="nav-item" class:active={isActive(item.href)}>
				<span class="nav-icon"><Icon name={item.icon} size={18} /></span>
				<span class="nav-label">{item.label}</span>
			</a>
		{/each}
	</div>

	<div class="nav-footer">
		<BandeauDelegation />
		<a href="/profil" class="nav-item" class:active={isActive('/profil')}>
			<span class="nav-icon"><Icon name="user" size={18} /></span>
			<span class="nav-label">{$currentUser?.prenom ?? t['/profil']}</span>
		</a>
		<!--  ⚠️ Le menu principal ne porte QUE le guide en ligne (04/09/2026,
		      arbitré à l'écran). Le PDF reste atteignable depuis le manuel et
		      depuis la FAQ : deux entrées « Guide » côte à côte encombraient un
		      menu déjà long, pour un document qu'on télécharge une fois. -->
		<div class="enveloppe-guide">
			<LiensGuide classe="nav-item" taille={18} avecPdf={false} />
		</div>
		<button class="nav-item nav-logout" on:click={logout} type="button">
			<span class="nav-icon"><Icon name="log-out" size={18} /></span>
			<span class="nav-label">{t['deconnexion']}</span>
		</button>
	</div>
</nav>

<!-- ─── Topbar mobile (hamburger) ──────────────────────────────────────── -->
<header class="mobile-topbar">
	<a
		href="/tableau-de-bord"
		class="brand-link"
		style="display:flex;align-items:center;gap:.4rem;text-decoration:none;color:inherit"
	>
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
	<!--  Le fond de `Modale` : `role="presentation"`, rien à activer au clavier —
	      le menu se ferme par le bouton ☰, qui porte `aria-expanded` (#1045). -->
	<div class="overlay-backdrop" role="presentation" on:click={closeMenu}></div>
	<div class="overlay-menu">
		<div class="overlay-nav">
			{#each allNav as item (item.href)}
				<a href={item.href} class="overlay-item" class:active={isActive(item.href)}>
					<span class="nav-icon"><Icon name={item.icon} size={20} /></span>
					<span>{item.label}</span>
				</a>
			{/each}
		</div>
		<div class="overlay-footer">
			<BandeauDelegation compact />
			<a href="/profil" class="overlay-item" class:active={isActive('/profil')}>
				<span class="nav-icon"><Icon name="user" size={20} /></span>
				<span>{$currentUser?.prenom ?? t['/profil']}</span>
			</a>
			<div class="enveloppe-guide">
				<LiensGuide classe="overlay-item" taille={20} />
			</div>
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

	.brand,
	.brand-link {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0.5rem 1.25rem 1.25rem;
		border-bottom: 1px solid var(--color-border);
		margin-bottom: 0.5rem;
		text-decoration: none;
		color: inherit;
	}
	.brand-link:hover {
		opacity: 0.8;
	}

	.brand-icon {
		display: flex;
		align-items: center;
		color: var(--color-primary);
	}
	.brand-name {
		font-weight: 700;
		font-size: 1.1rem;
		color: var(--color-primary);
	}

	.nav-section {
		flex: 1;
		overflow-y: auto;
		-webkit-overflow-scrolling: touch;
		padding: 0 0.5rem;
	}

	.nav-item {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0.55rem 0.75rem;
		border-radius: var(--radius);
		color: var(--color-text);
		font-size: 0.9rem;
		text-decoration: none;
		transition: background 0.12s;
		border: none;
		background: transparent;
		width: 100%;
		cursor: pointer;
		margin-bottom: 0.15rem;
		touch-action: manipulation;
		-webkit-tap-highlight-color: transparent;
	}

	.nav-item:hover {
		background: var(--color-bg);
	}
	.nav-item.active {
		background: var(--color-primary-light);
		color: var(--color-primary);
		font-weight: 600;
	}

	.nav-footer {
		padding: 0.5rem;
		border-top: 1px solid var(--color-border);
		margin-top: 0.5rem;
	}

	.nav-logout {
		color: var(--color-text-muted);
	}
	.nav-logout:hover {
		color: var(--color-danger);
		background: #fdedec;
	}
	/* ── Mobile topbar ─────────────────────────────────────────────────────── */
	.mobile-topbar {
		display: none;
	}

	/* ── Overlay menu ──────────────────────────────────────────────────────── */
	.overlay-backdrop {
		display: none;
		position: fixed;
		top: 0;
		right: 0;
		bottom: 0;
		left: 0;
		background: rgba(0, 0, 0, 0.35);
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
		padding: 0.5rem;
		overflow-y: auto;
	}

	.overlay-item {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.75rem 1rem;
		border-radius: var(--radius);
		color: var(--color-text);
		font-size: 1rem;
		text-decoration: none;
		border: none;
		background: transparent;
		width: 100%;
		cursor: pointer;
		margin-bottom: 0.1rem;
		touch-action: manipulation;
		-webkit-tap-highlight-color: transparent;
	}

	.overlay-item:hover {
		background: var(--color-bg);
	}
	.overlay-item.active {
		background: var(--color-primary-light);
		color: var(--color-primary);
		font-weight: 600;
	}

	.overlay-footer {
		padding: 0.5rem;
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
		padding: 0.3rem;
		border-radius: var(--radius);
	}

	.hamburger:hover {
		background: var(--color-bg);
	}

	.hb-line {
		display: block;
		width: 100%;
		height: 2px;
		background: var(--color-text);
		border-radius: 2px;
		transition:
			transform 0.2s,
			opacity 0.2s;
	}

	.hb-close-1 {
		transform: translateY(7px) rotate(45deg);
	}

	.hb-close-2 {
		transform: translateY(-7px) rotate(-45deg);
	}

	/* ── Responsive ────────────────────────────────────────────────────────── */
	@media (max-width: 767px) {
		.sidebar {
			display: none;
		}

		.mobile-topbar {
			display: flex;
			align-items: center;
			gap: 0.6rem;
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

		.overlay-backdrop {
			display: block;
		}
		.overlay-menu {
			display: flex;
		}
	}

	/*  Les règles `.aidant-*` sont parties avec leur balisage dans
	    `BandeauDelegation` (14/09/2026, #779) : Svelte scope le style au
	    composant qui REND le balisage, les laisser ici les aurait rendues
	    inertes — c'est la panne des pastilles nues de la v2.67.11. */
	/*  Les deux règles ci-dessous ne sont PAS des redéfinitions : elles rendent
	    applicables au composant enfant celles que la page porte déjà. Bornées à
	    l'enveloppe, elles ne fuient nulle part. */
	.enveloppe-guide :global(.nav-item),
	.enveloppe-guide :global(.overlay-item) {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0.55rem 0.7rem;
		border-radius: var(--radius);
		color: var(--color-text);
		text-decoration: none;
	}
</style>
