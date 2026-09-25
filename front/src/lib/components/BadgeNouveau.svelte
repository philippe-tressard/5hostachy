<!--
  Le badge « Nouveau » d'une carte de liste, à côté de son titre.

  🔴 Il était écrit CINQ fois (#1329) — affaire, actualité, annonce, idée,
  sondage —, chacune avec sa classe locale aux mêmes quatre propriétés, et deux
  écarts : la marge (0.4em ou 0.5em) et le mot (« NEW » sur l'affaire, « New »
  ailleurs). Le produit est en français : c'est « Nouveau », partout.

  La règle de fraîcheur reste `isNouveau` (`$lib/date`), lue ici et nulle part
  ailleurs sur une carte.
-->
<script lang="ts">
	import { isNouveau } from '$lib/date';

	/** La date de création de l'objet. */
	export let le: string | null | undefined;
	/** Une condition de plus, propre à l'écran (une annonce archivée n'est plus nouvelle). */
	export let si = true;
</script>

{#if si && le && isNouveau(le)}<span class="badge badge-gray badge-nouveau">Nouveau</span>{/if}

<style>
	.badge-nouveau {
		margin-left: 0.45em;
		font-size: 0.82em;
		font-weight: 500;
		vertical-align: middle;
	}
</style>
