<!--
  IconeAction.svelte — ce qu'un bouton d'action AFFICHE : son émoji, ou son
  pictogramme au trait quand la liste l'a demandé (`$lib/actions-au-trait`).

  Le bouton reste celui de son composant — libellé, `aria-pressed`, geste — :
  seul le dessin change. Au trait, il est gris au repos (`--color-text-muted`,
  6,3:1 sur le blanc : la discrétion ne passe pas sous le seuil de contraste),
  Bleu Seine au survol, et prend la couleur du bouton quand celui-ci est
  ACTIF (blanc sur l'aplat bleu) ou de DANGER (la corbeille).
-->
<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import { actionsAuTrait } from '$lib/actions-au-trait';

	/** L'émoji, tel que le site l'affiche hors des listes d'affaires. */
	export let glyphe: string;
	/** Le même au trait, nommé dans `$lib/icones-svg.json`. */
	export let icone: string;

	const trait = actionsAuTrait();
</script>

{#if trait}<span class="icone-action"><Icon name={icone} size={16} /></span>{:else}{glyphe}{/if}

<style>
	.icone-action {
		display: inline-flex;
		color: var(--color-text-muted);
		transition: color var(--duree-geste);
	}
	:global(.btn-icon-danger) .icone-action,
	:global([aria-pressed='true']) .icone-action {
		color: inherit;
	}
	@media (hover: hover) and (pointer: fine) {
		:global(button:hover) .icone-action {
			color: var(--color-primary);
		}
		:global(.btn-icon-danger:hover) .icone-action,
		:global([aria-pressed='true']:hover) .icone-action {
			color: inherit;
		}
	}
</style>
