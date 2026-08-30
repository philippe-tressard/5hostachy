<!--
  **Les Archives du fil d'activité** — ce qui a plus de trente jours, replié,
  groupé par JOUR.

  ## Pourquoi ce composant (#516)

  Extrait de `tableau-de-bord/+page.svelte` quand le garde-fou de modularité a
  refusé qu'elle grossisse (#453). Ce bloc est aussi celui que #516 touche :
  autant qu'il vive à l'endroit dont il porte le nom.

  ## 🔴 Le mot est commun, le rendu ne l'est PAS — et c'est déclaré

  Cinq écrans ont adopté `ArchivesParAnnee` le 20/08 (Actualités, Tickets,
  Espace CS, Petites annonces, Accès & sécurité). Celui-ci non, et le calendrier
  non plus : ils groupent autrement.

  | Écran | Groupement | Pourquoi |
  |---|---|---|
  | les cinq | par **année** | des objets qu'on retrouve par millésime |
  | Calendrier | année ▸ **mois** | trois types mêlés sur une échelle longue |
  | **ici** | par **jour** | un fil d'activité SE LIT par jour — l'année y masquerait ce qui fait tout son intérêt |

  ⚠️ Ce qui est commun, et doit le rester : le **mot**, qui vient de
  `TITRE_ARCHIVES`. Le ticket demandait d'unifier le vocabulaire ; le rendu suit
  la nature de ce qu'il montre, à condition de le DIRE — c'est ce que fait ce
  commentaire, et ce qui distingue une divergence assumée d'un oubli.

  ## Les styles voyagent avec le balisage

  `.flux-timeline` et `.flux-day-label` sont **recopiées** depuis la page, qui
  les emploie encore pour le fil récent. Deux portées Svelte distinctes ne
  peuvent pas partager une règle scopée ; les remonter dans `app.css` en ferait
  des règles globales pour deux usages sans raison de rester identiques.
-->
<script lang="ts">
	import SectionRepliee from '$lib/components/SectionRepliee.svelte';
	import FluxCard from '$lib/components/FluxCard.svelte';
	import { TITRE_ARCHIVES } from '$lib/archives';

	/** Les éléments archivés, déjà groupés par jour par la page. */
	export let groupesParJour: { label: string; items: any[] }[] = [];
	/** Combien d'éléments au total — affiché sur le bandeau. */
	export let compte = 0;
	/** Lié : la page anime la section selon son ordre d'apparition. */
	export let ouvert = false;
	/**  ⚠️ L'identifiant d'un élément du fil est une CHAÎNE, pas un nombre : il
	 *   préfixe le type (`pub-12`, `ticket-7`) parce que le fil mêle plusieurs
	 *   entités et que leurs identifiants numériques se recouvrent. Je l'avais
	 *   typé `number` par réflexe — `svelte-check` l'a refusé. */
	export let itemDeplie: string | null = null;
	export let onBasculer: (id: string) => void;
</script>

<SectionRepliee titre={TITRE_ARCHIVES} {compte} bind:ouvert />
{#if ouvert}
	<div class="flux-timeline older-timeline">
		{#each groupesParJour as groupe (groupe.label)}
			<div class="flux-day-label">{groupe.label}</div>
			{#each groupe.items as item (item.id)}
				<FluxCard
					{item}
					expanded={itemDeplie === item.id}
					on:toggle={(e) => onBasculer(e.detail)}
				/>
			{/each}
		{/each}
	</div>
{/if}

<style>
	.flux-timeline {
		position: relative;
		padding-left: 1.5rem;
	}
	.flux-timeline::before {
		content: '';
		position: absolute;
		left: 0.45rem;
		top: 1.5rem;
		bottom: 0.5rem;
		width: 2px;
		background: var(--color-border);
		border-radius: 1px;
	}
	.flux-day-label {
		position: relative;
		font-size: 0.72rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--color-text-muted);
		padding: 0.9rem 0 0.35rem;
		margin-left: -0.15rem;
	}
	/*  L'atténuation qui distingue l'archive du fil vivant. */
	.older-timeline {
		opacity: 0.85;
	}

	@media (max-width: 767px) {
		.flux-timeline {
			padding-left: 1.25rem;
		}
		.flux-timeline::before {
			left: 0.35rem;
		}
	}
</style>
