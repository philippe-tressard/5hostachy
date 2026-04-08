<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { afterNavigate } from '$app/navigation';
	import Nav from '$lib/components/Nav.svelte';
	import { auth as authApi } from '$lib/api';
	import { setUser, currentUser } from '$lib/stores/auth';
	import { loadSiteConfig, configStore, siteNomStore } from '$lib/stores/pageConfig';
	import { initTelemetry, trackPageView, setTelemetryOptOut } from '$lib/telemetry';
	import pkg from '../../../package.json';

	onMount(async () => {
		initTelemetry();
		trackPageView(window.location.pathname);

		const [, meResult] = await Promise.allSettled([
			loadSiteConfig(),
			!$currentUser ? authApi.me() : Promise.resolve(null),
		]);
		if (!$currentUser) {
			if (meResult.status === 'fulfilled' && meResult.value) {
				setUser(meResult.value);
			} else {
				goto('/auth/connexion');
			}
		}
		// Appliquer l'opt-out télémétrie si l'utilisateur l'a activé
		if ($currentUser?.opt_out_telemetrie) {
			setTelemetryOptOut(true);
		}
	});

	afterNavigate(() => {
		trackPageView(window.location.pathname);
	});

	$: siteNom  = $siteNomStore;
	$: siteUrl  = $configStore['site_url'] ?? '';
	$: buildVerShort = `v${pkg.version}-${import.meta.env.VITE_GIT_HASH ?? 'dev'}`;
	$: buildVer = `${buildVerShort}-${import.meta.env.VITE_BUILD_DATE ?? ''}`;
	$: year     = new Date().getFullYear();
</script>

<div class="app-shell">
	<Nav />
	<div class="app-content">
		<main class="app-main">
			<div class="container page">
				<slot />
			</div>
		</main>
		<footer class="app-footer">
			© {year} &nbsp;·&nbsp;
			<a href={siteUrl} target="_blank" rel="noopener noreferrer">{siteNom}</a>
			&nbsp;·&nbsp; {buildVer}
			&nbsp;·&nbsp; <a href="https://github.com/philippe-tressard/5hostachy" target="_blank" rel="noopener noreferrer">GitHub</a>
			&nbsp;·&nbsp; <a href="/mentions-legales">Mentions légales</a>
			&nbsp;·&nbsp; <a href="/politique-de-confidentialite">Politique de confidentialité</a>
		</footer>
	</div>
</div>

<style>
	.app-shell {
		display: flex;
		min-height: 100vh;
		min-height: 100svh;
		overflow-x: hidden;
	}

	.app-content {
		flex: 1;
		margin-left: 185px;
		display: flex;
		flex-direction: column;
		min-height: 100vh;
		min-height: 100svh;
		max-width: calc(100vw - 185px);
	}

	.app-main {
		flex: 1;
	}

	.app-footer {
		text-align: center;
		padding: 0.75rem 1rem;
		font-size: 0.7rem;
		color: var(--color-text-muted);
		border-top: 1px solid var(--color-border);
		letter-spacing: 0.02em;
	}

	@media (max-width: 767px) {
		.app-content {
			margin-left: 0;
			padding-top: 3.25rem;
			max-width: 100vw;
		}
		.app-main {
			overflow-x: hidden;
		}
	}
</style>
