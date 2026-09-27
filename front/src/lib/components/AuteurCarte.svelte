<!--
  L'AUTEUR sur la dernière ligne d'une carte : « ✍️ Nom », en texte discret.

  Arbitré à l'écran le 27/09/2026 : le fil l'écrivait « ✍️ Nom », la carte
  d'affaire et celle d'actualité « Nom » sans icône — trois classes locales
  (`flux-auteur`, `tk-auteur`, `pub-auteur`) pour une notion. La forme du fil
  est retenue, et elle ne s'écrit plus qu'ici. 🔒 `npm run lint:pastilles`.

  Ce n'est PAS un badge : un nom n'est pas une étiquette de catégorie.
-->
<script lang="ts">
	/** Rien n'est rendu sans nom : l'appelant n'a pas à tester. */
	export let nom: string | null | undefined = null;
</script>

{#if nom}<span class="auteur-carte">✍️ {nom}</span>{/if}

<style>
	.auteur-carte {
		color: var(--color-text-muted);
		align-self: center;
	}
</style>
