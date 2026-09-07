<!--
  L'avertissement légal des tickets de type « Urgence ».

  POURQUOI CE COMPOSANT EXISTE. Extrait de `tickets/+page.svelte` le 16/08/2026,
  quand cette page a franchi les 500 lignes du rang 1 en accueillant la boîte de
  création (`standards/02` §6). Le découpage se fait « au fil de l'eau » : on sort
  du fichier ce qui s'en détache le plus proprement, et c'est ce bloc-ci.

  C'est un gain de STRUCTURE, pas un artifice pour faire baisser un compteur
  (`standards/02` §6, règle du 16/08/2026) : ce bloc a sa propre responsabilité —
  un texte juridique — son propre état d'ouverture, et aucune dépendance à la
  logique des tickets. Il ne partage avec la page ni donnée ni comportement. Son
  nom se justifie seul, et sa raison de changer lui est propre : elle est
  réglementaire, pas fonctionnelle. C'est le critère du §6 pour qu'un découpage
  vaille quelque chose.

  ⚠️ AUCUN mot de ce texte n'a été modifié en le déplaçant, et son état
  d'ouverture reste replié par défaut : le comportement est identique à l'octet
  près. Ce qui disparaît en premier dans une extraction, ce sont les choses qui ne
  se voient pas au rendu nominal — ici, il n'y a ni gestion d'erreur ni appel, mais
  la règle de relecture côte à côte s'applique quand même (`standards/02` §6).

  Le contenu engage la responsabilité du syndicat des copropriétaires : toute
  reformulation est une décision juridique, pas une retouche de style.
-->
<script lang="ts">
	//  Replié par défaut : l'avertissement doit être accessible en permanence sans
	//  occuper l'écran de quelqu'un qui vient consulter ses tickets.
	let disclaimerOpen = false;
</script>

<div class="urgence-disclaimer" role="note" aria-label="Avertissement tickets urgence">
	<button
		class="urgence-disclaimer-toggle"
		on:click={() => (disclaimerOpen = !disclaimerOpen)}
		aria-expanded={disclaimerOpen}
	>
		<span class="urgence-disclaimer-title"
			>&#x1F6A8; Tickets de type Urgence — Avertissement légal</span
		>
		<span class="urgence-disclaimer-chevron">{disclaimerOpen ? '▲' : '▼'}</span>
	</button>
	{#if disclaimerOpen}
		<p>
			Le dépôt d'un ticket <strong>Urgence</strong> dans cette application a pour seul objet la
			<strong>traçabilité de votre signalement</strong>. Il ne constitue ni un moyen d'alerte des
			secours, ni un engagement de prise en charge dans un délai déterminé, ni une garantie de
			résultat de la part du conseil syndical ou du syndicat des copropriétaires.
		</p>
		<p class="urgence-disclaimer-steps">
			<strong
				>En cas de danger pour les personnes ou de sinistre, vous devez impérativement :</strong
			>
		</p>
		<ul>
			<li>
				&#x1F4DE; <strong>Alerter les secours</strong> — 15 (SAMU) · 17 (Police secours) · 18 (Sapeurs-pompiers)
				· 112 (urgences européennes)
			</li>
			<li>
				&#x1F3E2; <strong>Prévenir le syndic</strong> via ses coordonnées d'urgence (voir
				<a href="/annuaire">Annuaire</a>)
			</li>
			<li>
				&#x1F4CB; <strong>Déclarer le sinistre à votre assureur</strong> dans les délais prévus au contrat
				(généralement 5 jours ouvrés à compter de la connaissance du sinistre — art. L113-2 Code des Assurances)
			</li>
		</ul>
		<p class="urgence-disclaimer-legal">
			La responsabilité du syndicat des copropriétaires, du conseil syndical et de l'administrateur
			de la plateforme ne saurait être engagée en cas de préjudice résultant de l'absence de
			signalement par les voies officielles ci-dessus.
		</p>
	{/if}
</div>

<style>
	/*  Ces règles suivent le balisage : Svelte scope les styles au composant, et
	    les laisser dans la page en aurait fait des sélecteurs orphelins — c'est
	    exactement la régression #344 (balisage parti, règles restées derrière). */
	.urgence-disclaimer {
		background: #fff7ed;
		border: 1.5px solid #fed7aa;
		border-left: 5px solid #ea580c;
		border-radius: var(--radius);
		padding: 0;
		margin-bottom: 1.25rem;
		font-size: 0.85rem;
		line-height: 1.6;
		color: #431407;
		overflow: hidden;
	}
	.urgence-disclaimer-toggle {
		display: flex;
		justify-content: space-between;
		align-items: center;
		width: 100%;
		background: none;
		border: none;
		padding: 0.7rem 1.1rem;
		cursor: pointer;
		text-align: left;
		gap: 0.5rem;
	}
	.urgence-disclaimer-toggle:hover {
		background: #fed7aa44;
	}
	.urgence-disclaimer-title {
		font-weight: 700;
		font-size: 0.95rem;
		color: #9a3412;
	}
	.urgence-disclaimer-chevron {
		font-size: 0.7rem;
		color: #9a3412;
		flex-shrink: 0;
	}
	.urgence-disclaimer p {
		margin: 0 0 0.45rem;
		padding: 0 1.1rem;
	}
	.urgence-disclaimer p:first-of-type {
		padding-top: 0.2rem;
	}
	.urgence-disclaimer ul {
		margin: 0.3rem 0 0.45rem 1.1rem;
		padding: 0 1.1rem 0 0;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}
	.urgence-disclaimer li {
		list-style: none;
	}
	.urgence-disclaimer a {
		color: #9a3412;
		text-decoration: underline;
	}
	.urgence-disclaimer-steps {
		margin-top: 0.45rem !important;
	}
	.urgence-disclaimer-legal {
		font-size: 0.78rem;
		color: #7c2d12;
		font-style: italic;
		margin-top: 0.3rem !important;
		border-top: 1px solid #fed7aa;
		padding: 0.45rem 1.1rem 0.85rem !important;
	}
</style>
