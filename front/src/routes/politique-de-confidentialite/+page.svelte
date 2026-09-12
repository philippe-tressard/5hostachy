<script lang="ts">
	import { onMount } from 'svelte';
	import { config as configApi } from '$lib/api';
	import { loadSiteConfig, getSiteNom, siteNomStore, configStore } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';
	const _siteNom = getSiteNom();
	$: siteNom = $siteNomStore;
	$: siteUrl = $configStore['site_url'] ?? '/';
	const year = new Date().getFullYear();
	let customHtml = '';
	onMount(async () => {
		loadSiteConfig();
		try {
			customHtml = (await configApi.legal())['politique_confidentialite'] ?? '';
		} catch {
			//  Silencieux : la page a son texte par défaut (cf. mentions légales).
		}
	});
</script>

<svelte:head><title>Politique de confidentialité — {_siteNom}</title></svelte:head>

<main class="legal-page">
	<a href="/" class="back-link">← Retour</a>
	<h1>Politique de confidentialité</h1>

	{#if customHtml}
		<div class="custom-content">{@html safeHtml(customHtml)}</div>
	{:else}
		<p class="muted">Contenu en cours de rédaction.</p>
	{/if}
</main>

<footer class="legal-footer">
	© {year}
	&nbsp;·&nbsp; <a href={siteUrl} target="_blank" rel="noopener noreferrer">{siteNom}</a>
</footer>
