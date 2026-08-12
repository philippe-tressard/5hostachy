<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { afterNavigate } from '$app/navigation';
	import Nav from '$lib/components/Nav.svelte';
	import { auth as authApi } from '$lib/api';
	import { setUser, currentUser, marquerAuthResolue } from '$lib/stores/auth';
	import { urlDeConnexion } from '$lib/redirection';
	import { loadSiteConfig, configStore, siteNomStore } from '$lib/stores/pageConfig';
	import { chargerPerimetres } from '$lib/stores/perimetres';
	import { initTelemetry, trackPageView, setTelemetryOptOut } from '$lib/telemetry';
	import pkg from '../../../package.json';

	onMount(async () => {
		initTelemetry();

		const [, meResult] = await Promise.allSettled([
			loadSiteConfig(),
			!$currentUser ? authApi.me() : Promise.resolve(null),
		]);
		if (!$currentUser) {
			if (meResult.status === 'fulfilled' && meResult.value) {
				setUser(meResult.value);
			} else {
				// Emporte la page demandée (fragment compris) pour y revenir après
				// la connexion — un lien partagé ne doit pas être perdu au login.
				marquerAuthResolue();
				goto(urlDeConnexion());
			}
		} else {
			//  Utilisateur déjà en mémoire (navigation interne) : l'état est résolu
			//  d'emblée. Sans cette branche, un garde d'accès attendrait indéfiniment.
			marquerAuthResolue();
		}
		//  L'arborescence des périmètres alimente `perimetreLabel()`. Chargée APRÈS
		//  l'authentification — l'endpoint exige une session — et sans `await` : les
		//  listes de contenus arrivent elles aussi en asynchrone, et un libellé
		//  manquant retombe sur son rendu calculé plutôt que de retarder la page.
		if ($currentUser) chargerPerimetres();

		// Appliquer l'opt-out télémétrie AVANT le premier tracking
		if ($currentUser?.opt_out_telemetrie) {
			setTelemetryOptOut(true);
		}
		trackPageView(window.location.pathname);
	});

	afterNavigate(() => {
		trackPageView(window.location.pathname);
	});

	$: siteNom  = $siteNomStore;
	$: siteUrl  = $configStore['site_url'] ?? '';
	$: buildVerShort = `v${pkg.version}-${import.meta.env.VITE_GIT_HASH ?? 'dev'}`;
	$: instanceId = import.meta.env.VITE_INSTANCE_ID || '';
	$: buildVer = `${buildVerShort}-${import.meta.env.VITE_BUILD_DATE ?? ''}${instanceId ? ` · RPi${instanceId}` : ''}`;
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
			overflow-x: clip; /* clip sans créer de scroll-context → position:sticky fonctionne */
		}
	}
</style>
