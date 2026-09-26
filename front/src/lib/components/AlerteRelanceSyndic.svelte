<!--
  L'alerte « N affaires syndic à relancer » du tableau de bord (conseil syndical).

  Sortie de `tableau-de-bord/+page.svelte` le 26/09/2026, au fil de l'eau : la
  page dépassait 500 lignes, et ranger ses survols sous le média souris (#1329)
  la faisait grossir. Une notion autonome — un compte, un lien, sa couleur
  d'alerte —, que la page ne fait qu'afficher.
-->
<script lang="ts">
	import { HREF_RELANCE_SYNDIC } from '$lib/raccourcis';

	/** Le nombre d'affaires transmises au syndic sans avancée depuis plus d'un mois. */
	export let nombre: number;
</script>

<a href={HREF_RELANCE_SYNDIC} class="relance-alerte-card">
	<span class="relance-alerte-icon">🔔</span>
	<div class="relance-alerte-text">
		<strong>{nombre} affaire{nombre > 1 ? 's' : ''} syndic à relancer</strong>
		<span>Sans avancée depuis plus d'1 mois — cliquez pour voir et envoyer la relance</span>
	</div>
	<span class="relance-alerte-arrow">→</span>
</a>

<style>
	.relance-alerte-card {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.75rem 1rem;
		border-radius: var(--radius);
		background: #fff7ed;
		border: 1.5px solid #f59e0b;
		color: #92400e;
		text-decoration: none;
		transition:
			background 0.15s,
			border-color 0.15s;
		margin-bottom: 0.5rem;
	}
	@media (hover: hover) and (pointer: fine) {
		.relance-alerte-card:hover {
			background: #fef3c7;
			border-color: #d97706;
		}
	}
	.relance-alerte-icon {
		font-size: 1.3rem;
		flex-shrink: 0;
	}
	.relance-alerte-text {
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
		flex: 1;
	}
	.relance-alerte-text strong {
		font-size: 0.9rem;
	}
	.relance-alerte-text span {
		font-size: 0.78rem;
		color: #b45309;
	}
	.relance-alerte-arrow {
		font-size: 1.1rem;
		flex-shrink: 0;
		opacity: 0.7;
	}

	@media (max-width: 767px) {
		.relance-alerte-card {
			padding: 0.55rem 0.75rem;
			gap: 0.5rem;
		}
		.relance-alerte-text strong {
			font-size: 0.82rem;
		}
	}
</style>
