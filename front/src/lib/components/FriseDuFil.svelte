<!--
  **La frise du fil d'activité** — des cartes `FluxCard` sur la ligne de temps,
  groupées sous l'intitulé de leur jour.

  ## Pourquoi ce composant (#779, 01/10/2026)

  La boucle « intitulé du jour, puis ses cartes, chacune dépliable et
  retirable » était écrite deux fois — le fil récent de l'accueil et
  `ArchivesDuFil` —, et une troisième fois sans intitulé pour le bandeau
  Épinglé. Trois copies du même câblage de `FluxCard` (clé, dépliage, retrait)
  qui devaient rester d'accord sans rien pour le vérifier.

  ## Trois variantes, une frise

  | `variante` | Où | Ce qui diffère |
  |---|---|---|
  | `fil` | le fil récent de l'accueil | rien : c'est la frise de la charte |
  | `archives` | `ArchivesDuFil` | atténuée — on distingue l'archive du fil vivant |
  | `epingle` | le bandeau Épinglé | sans ligne de temps : l'ordre n'y est pas le sujet |

  Un groupe sans intitulé (`label: null`) n'en affiche pas : c'est le cas du
  bandeau Épinglé, qui n'a qu'un groupe.

  La frise elle-même (`.flux-timeline`, `.flux-day-label`) vit dans la charte
  (`composants.css`) ; la clé d'une carte, dans `cleFluxItem` (`$lib/flux`).
-->
<script lang="ts">
	import FluxCard from '$lib/components/FluxCard.svelte';
	import { cleFluxItem, type GroupeDuFil } from '$lib/flux';

	export let groupes: GroupeDuFil[] = [];
	export let variante: 'fil' | 'archives' | 'epingle' = 'fil';
	/**  ⚠️ Une CHAÎNE (`pub-12`, `ticket-7`) : le fil mêle plusieurs tables, dont
	 *   les identifiants numériques se recouvrent. */
	export let itemDeplie: string | null = null;
	export let onBasculer: (id: string) => void;
	/**  Retirer une carte du fil. La frise ne le fait pas elle-même : elle n'a
	 *   ni la liste ni le droit d'écrire. */
	export let onMasquer: (id: string) => void = () => {};
</script>

<div
	class="flux-timeline"
	class:frise-archives={variante === 'archives'}
	class:frise-epingle={variante === 'epingle'}
>
	{#each groupes as groupe (groupe.label)}
		{#if groupe.label}<div class="flux-day-label">{groupe.label}</div>{/if}
		{#each groupe.items as item (cleFluxItem(item))}
			<FluxCard
				{item}
				expanded={itemDeplie === item.id}
				on:toggle={(e) => onBasculer(e.detail)}
				on:masquer={(e) => onMasquer(e.detail)}
			/>
		{/each}
	{/each}
</div>

<style>
	.frise-archives {
		opacity: 0.85;
	}
	/*  La carte est la même que dans le fil : seule la ligne de temps est
	    inutile ici. Le retrait reste celui du bureau, même au téléphone. */
	.frise-epingle {
		padding-left: 1.5rem;
	}
	.frise-epingle::before {
		display: none;
	}
</style>
