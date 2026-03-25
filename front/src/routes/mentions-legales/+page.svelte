<script lang="ts">
	import { onMount } from 'svelte';
	import { loadSiteConfig, getSiteNom, siteNomStore, configStore } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';
	const _siteNom = getSiteNom();
	$: siteNom = $siteNomStore;
	$: siteUrl = $configStore['site_url'] ?? '/';
	$: year = new Date().getFullYear();
	let customHtml = '';
	onMount(async () => {
		loadSiteConfig();
		try {
			const r = await fetch('/api/config/legal');
			if (r.ok) { const d = await r.json(); customHtml = d['mentions_legales'] ?? ''; }
		} catch { /* silencieux */ }
	});
</script>
<svelte:head><title>Mentions légales — {_siteNom}</title></svelte:head>

<main class="legal-page">
	<a href="/" class="back-link">← Retour</a>
	<h1>Mentions légales</h1>

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

<style>
	.legal-page {
		max-width: 720px;
		margin: 2rem auto;
		padding: 0 1.5rem 1.5rem;
		font-family: inherit;
	}
	.back-link {
		display: inline-block;
		font-size: .875rem;
		color: var(--color-primary, #3b82f6);
		text-decoration: none;
		margin-bottom: 1.5rem;
	}
	.back-link:hover { text-decoration: underline; }
	h1 { font-size: 1.6rem; font-weight: 700; margin-bottom: 1rem; }
	section { margin-bottom: 1.5rem; }
	h2 { font-size: 1rem; font-weight: 600; margin-bottom: .5rem; }
	p { font-size: .875rem; line-height: 1.7; color: var(--color-text); }
	.custom-content { font-size: .875rem; line-height: 1.7; color: var(--color-text); }
	:global(.custom-content ul), :global(.custom-content ol) { padding-left: 1.4rem; margin: .25rem 0; }
	:global(.custom-content li) { font-size: .875rem; line-height: 1.7; color: var(--color-text); margin-bottom: .25rem; }
	:global(.custom-content p) { margin-bottom: .5rem; }
	:global(.custom-content h2) { font-size: 1rem; font-weight: 600; margin: 1.25rem 0 .4rem; }
	:global(.custom-content h3) { font-size: .9rem; font-weight: 600; margin: 1rem 0 .3rem; }
	:global(.custom-content code) { font-size: .78rem; background: var(--color-primary-light); padding: .1em .3em; border-radius: 3px; }
	:global(.custom-content a) { color: var(--color-primary); }
	.legal-footer {
		text-align: center;
		padding: 1rem;
		font-size: 0.7rem;
		color: var(--color-text-muted);
		border-top: 1px solid var(--color-border);
		letter-spacing: 0.02em;
		max-width: 720px;
		margin: 0 auto;
		padding-left: 1.5rem;
		padding-right: 1.5rem;
	}
	.legal-footer a { color: var(--color-text-muted); }
	.legal-footer a:hover { color: var(--color-primary); }
</style>
