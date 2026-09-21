<!--
  **Tout / Seulement les avancées** — le filtre d'un fil (#1094).

  ## Ce qu'il trie, et ce qu'il ne trie pas

  Une **avancée** est un changement d'état, et lui seul. Un commentaire peut
  être décisif et une relance peut ne rien changer : ce filtre ne sépare pas
  l'important de l'anecdotique, il sépare ce qui a fait **bouger** le dossier de
  ce qui l'a commenté. Le libellé le dit ainsi — « les avancées », jamais
  « l'essentiel ».

  🔴 Il ne s'affiche que s'il a de quoi trier : un fil sans aucune avancée, ou
  qui n'en contient QUE, le rendrait inutile — et une commande qui ne change
  rien apprend à ignorer les commandes.

  ⚠️ Les pastilles viennent de `ChoixPastilles`, jamais réécrites : il porte
  déjà l'accessibilité, la cible tactile et le défilement au pouce.
-->
<script lang="ts">
	import ChoixPastilles from './ChoixPastilles.svelte';

	/** Les types qui comptent comme une avancée — déclarés par l'appelant. */
	export let avancees: readonly string[] = ['etat'];
	/** Les types présents dans le fil, pour savoir s'il y a matière à trier. */
	export let types: readonly string[] = [];
	/** `'tout'` ou `'avancees'` — lié par l'appelant, qui filtre sa liste. */
	export let valeur = 'tout';

	$: utile = types.some((t) => avancees.includes(t)) && types.some((t) => !avancees.includes(t));
</script>

{#if utile}
	<div class="fil-filtre">
		<ChoixPastilles
			bind:valeur
			tous={false}
			libelle="Filtrer le fil"
			options={[
				{ val: 'tout', label: 'Tout' },
				{ val: 'avancees', label: 'Seulement les avancées' },
			]}
		/>
	</div>
{/if}

<style>
	/*  Le filtre appartient à la LISTE, pas au titre de la rubrique
	    (`ux-patterns` §0 ter) : il se pose au-dessus du fil. */
	.fil-filtre {
		margin-bottom: 0.6rem;
	}
</style>
