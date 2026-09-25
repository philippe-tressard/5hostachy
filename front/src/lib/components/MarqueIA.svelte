<!--
  La marque « Rédigé avec l'assistant IA » — un ✨ discret à côté de l'auteur.

  Arbitré le 17/09/2026 (#985) : *« l'auteur reste ; l'icône IA peut être
  juxtaposée pour dire que l'IA a modifié la réponse manuelle, mais rester très
  discrète »*. Elle se rend partout où un objet porte `assiste_ia` — carte de
  ticket, d'actualité, d'événement, entrée d'Historique, sondage, idée,
  annonce — et nulle part ailleurs : un composant, une allure.

  Ce n'est PAS un encart dans le texte (celui de la synthèse de contrat répond
  à une autre exigence, réglementaire). Le texte est celui de l'auteur, qui l'a
  relu et enregistré ; la marque dit seulement que l'assistant y a contribué.
-->
<script lang="ts">
	/** Rendu seulement quand c'est vrai : l'appelant n'a pas à tester. */
	export let assiste: boolean | null | undefined = false;

	const LIBELLE = 'Rédigé avec l’assistant IA';
</script>

{#if assiste}
	<span class="marque-ia" role="img" aria-label={LIBELLE} title={LIBELLE}>✨</span>
{/if}

<style>
	/*  Discrète : la taille d'un badge, estompée, sans fond. Elle se lit en
	    passant, elle ne concurrence ni le nom ni la date. */
	.marque-ia {
		font-size: 0.75rem;
		opacity: 0.6;
		cursor: help;
		line-height: 1;
	}
</style>
