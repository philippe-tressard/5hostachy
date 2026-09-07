<script lang="ts">
	import { onMount } from 'svelte';
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
			const r = await fetch('/api/config/legal');
			if (r.ok) {
				const d = await r.json();
				customHtml = d['mentions_legales'] ?? '';
			}
		} catch {
			/* silencieux */
		}
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

	<!--  ⚠️ « Code source accessible » et NON « logiciel libre » : depuis le
	      07/09/2026, la licence porte une clause commerciale, ce que ni l'OSI ni
	      la FSF n'admettent dans une licence libre. Écrire « open source » ici
	      serait inexact, et un utilisateur qui s'y fierait pour un usage
	      professionnel serait induit en erreur — c'est `standards/14`. -->
	<section class="oss-section">
		<h2>Code source accessible</h2>
		<p>
			Ce site est propulsé par <strong>5Hostachy</strong>, une application de gestion de copropriété
			dont le <strong>code source est accessible</strong>, sous
			<a
				href="https://github.com/philippe-tressard/5hostachy/blob/main/LICENSE-5Hostachy.md"
				target="_blank"
				rel="noopener noreferrer">Licence 5Hostachy</a
			>&nbsp;: copyleft fondé sur les principes de l’AGPLv3, avec clauses commerciales.
		</p>
		<p>
			Les particuliers, associations et copropriétés peuvent l’utiliser <strong>gratuitement</strong
			>. Tout usage commercial requiert un accord préalable de l’auteur. Le code est disponible sur
			<a
				href="https://github.com/philippe-tressard/5hostachy"
				target="_blank"
				rel="noopener noreferrer">GitHub&nbsp;→</a
			>
		</p>
	</section>
</main>

<footer class="legal-footer">
	© {year}
	&nbsp;·&nbsp; <a href={siteUrl} target="_blank" rel="noopener noreferrer">{siteNom}</a>
	&nbsp;·&nbsp;
	<a href="https://github.com/philippe-tressard/5hostachy" target="_blank" rel="noopener noreferrer"
		>GitHub</a
	>
</footer>

<style>
	/*  Ce qui est PROPRE aux mentions légales : la section « Logiciel libre »
	    et ses intertitres. Le reste vit dans `styles/legal.css` (#583). */
	.legal-page section {
		margin-bottom: 1.5rem;
	}
	.legal-page h2 {
		font-size: 1rem;
		font-weight: 600;
		margin-bottom: 0.5rem;
	}
	.oss-section {
		margin-top: 2rem;
		padding-top: 1.25rem;
		border-top: 1px solid var(--color-border);
	}
	.oss-section a {
		color: var(--color-primary);
	}
</style>
