<!--
  **Les caractéristiques d'un lot** — type, étage, superficie — en liste de
  définitions.

  ## Pourquoi ce composant (#779, 01/10/2026)

  « Mes lots » écrivait cette liste TROIS fois : le lot loué d'un locataire, les
  lots qu'il possède en propre, le lot choisi d'un copropriétaire. Les copies
  avaient divergé sur les cas limites : le type affiché sous condition dans
  l'une, sans dans les deux autres ; l'étage testé contre `undefined` dans
  l'une seulement — un lot sans étage connu y affichait « Étage » vide.

  Les lignes propres à chaque usage (le numéro, le bâtiment, les dates du bail)
  passent par les slots `avant` et `apres` : la liste reste une seule liste, et
  son ordre — l'identité, puis les caractéristiques, puis le reste — ne se
  recompose pas.

  🔒 `npm run lint:caracteristiques-lot` refuse un `<dt>Étage</dt>` ou un
  `<dt>Superficie</dt>` écrit ailleurs.
-->
<script lang="ts">
	import { etageLabel, lotTypeComplet } from '$lib/utils';

	export let type: string | null | undefined = null;
	export let typeAppartement: string | null | undefined = null;
	export let etage: number | null | undefined = null;
	export let superficie: number | null | undefined = null;
</script>

<dl class="caracteristiques-lot">
	<slot name="avant" />
	{#if type}
		<dt>Type</dt>
		<dd class="type-lot">{lotTypeComplet(type, typeAppartement)}</dd>
	{/if}
	{#if etage !== null && etage !== undefined}
		<dt>Étage</dt>
		<dd>{etageLabel(etage)}</dd>
	{/if}
	{#if superficie}
		<dt>Superficie</dt>
		<dd>{superficie} m²</dd>
	{/if}
	<slot name="apres" />
</dl>

<style>
	.caracteristiques-lot {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.4rem 0.8rem;
		font-size: var(--fs-base);
	}
	/*  `:global` : les lignes des slots sont rendues par l'appelant, et doivent
	    avoir le même aspect que celles du composant. */
	.caracteristiques-lot :global(dt) {
		font-weight: 500;
		color: var(--color-text-muted);
	}
	.caracteristiques-lot :global(dd) {
		margin: 0;
	}
	.type-lot {
		text-transform: capitalize;
	}
</style>
