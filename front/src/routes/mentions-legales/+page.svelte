<script lang="ts">
	import PageLegale from '$lib/components/PageLegale.svelte';
	import { LICENCE_NOM, LICENCE_URL, NOM_PLATEFORME, lienSource } from '$lib/plateforme';

	//  La version qui TOURNE (AGPLv3 §13) — le pied de page de l'application
	//  pointe au même endroit, par la même fonction (#1725).
	const sourceEnService = lienSource(import.meta.env.VITE_GIT_HASH);
</script>

<PageLegale titre="Mentions légales" cle="mentions_legales">
	<!--  ⚠️ « Code source accessible » et NON « logiciel libre » : depuis le
	      07/09/2026, la licence porte une clause commerciale, ce que ni l'OSI ni
	      la FSF n'admettent dans une licence libre. Écrire « open source » ici
	      serait inexact, et un utilisateur qui s'y fierait pour un usage
	      professionnel serait induit en erreur — c'est `standards/14`. -->
	<section class="oss-section">
		<h2>Code source accessible</h2>
		<p>
			Ce site est propulsé par <strong>{NOM_PLATEFORME}</strong>, une application de gestion de
			copropriété dont le <strong>code source est accessible</strong>, sous
			<a href={LICENCE_URL} target="_blank" rel="noopener noreferrer">{LICENCE_NOM}</a>&nbsp;:
			copyleft fondé sur les principes de l’AGPLv3, avec clauses commerciales.
		</p>
		<p>
			Les particuliers, associations et copropriétés peuvent l’utiliser <strong>gratuitement</strong
			>. Tout usage commercial requiert un accord préalable de l’auteur. Le code de la version en
			service est disponible sur
			<a href={sourceEnService} target="_blank" rel="noopener noreferrer">GitHub&nbsp;→</a>
		</p>
	</section>

	<svelte:fragment slot="pied">
		&nbsp;·&nbsp;
		<a href={sourceEnService} target="_blank" rel="noopener noreferrer">{NOM_PLATEFORME}</a>
	</svelte:fragment>
</PageLegale>

<style>
	/*  Ce qui est PROPRE aux mentions légales : la section « Code source
	    accessible ». Le squelette vit dans `$lib/components/PageLegale.svelte`,
	    le reste dans `styles/legal.css` (#583).

	    🔴 Les sélecteurs ne peuvent PAS partir de `.legal-page` : cette classe
	    appartient au composant, et Svelte ne pose sa marque de portée que sur les
	    éléments écrits ICI. Un `.legal-page h2` ne correspondrait à rien, en
	    silence — c'est la section qui sert d'ancre. */
	.oss-section {
		margin-top: 2rem;
		margin-bottom: 1.5rem;
		padding-top: 1.25rem;
		border-top: 1px solid var(--color-border);
	}
	.oss-section h2 {
		font-size: 1rem;
		font-weight: 600;
		margin-bottom: 0.5rem;
	}
	.oss-section a {
		color: var(--color-primary);
	}
</style>
