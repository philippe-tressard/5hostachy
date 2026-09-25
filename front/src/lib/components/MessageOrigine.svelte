<!--
  Le texte REÇU d'une réponse par courriel, quand l'assistant l'a mis en forme
  (#1322, 25/09/2026). La Suite affiche la version mise en forme ; celle-ci
  reste consultable, pour qu'une déformation par le modèle se voie.

  En texte brut, jamais en `{@html}` : c'est un courriel reçu, pas un contenu
  saisi dans le site. Rien quand il n'y a pas d'original.
-->
<script lang="ts">
	export let texte: string | null | undefined = null;
</script>

{#if texte}
	<details class="message-origine">
		<summary>Message d'origine</summary>
		{texte}
	</details>
{/if}

<style>
	.message-origine {
		margin-top: 0.25rem;
		font-size: 0.78rem;
		color: var(--color-text-muted);
		white-space: pre-wrap;
	}
	.message-origine summary {
		cursor: pointer;
	}
</style>
