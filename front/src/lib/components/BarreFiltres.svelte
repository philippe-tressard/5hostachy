<!--
  BarreFiltres.svelte — une rangée de pastilles de filtrage, avec son « Tous ».

  ## Pourquoi ce composant (29/08/2026, #491)

  `prestataires` portait DEUX fois le même motif — une pastille « Tous » suivie
  d'une pastille par entrée d'une table — pour les types et pour les équipements.
  Le second était la copie du premier, à trois mots près.

  C'est la duplication la plus discrète : elle vit dans un seul fichier, donc
  aucun contrôle inter-fichiers ne la voit, et elle se recopie une troisième fois
  au premier filtre ajouté.

  ⚠️ Il ne remplace PAS `Pastille` : il l'emploie. Ce qu'il porte, c'est le
  MOTIF — l'entrée « Tous » qui vide la sélection, l'égalité entre la valeur
  courante et chaque option, et le défilement horizontal quand la rangée déborde.

  UTILISATION :
    <BarreFiltres options={TYPES} bind:valeur={filtreType} tous="Tous" />
    <BarreFiltres options={TYPES} bind:valeur={filtreType} avecDetail />
-->
<script lang="ts">
	import Pastille from '$lib/components/Pastille.svelte';

	/** Les entrées. `desc` n'est lue que si `avecDetail` est vrai. */
	export let options: readonly { val: string; label: string; desc?: string }[] = [];

	/** La valeur retenue. Chaîne vide = « Tous ». */
	export let valeur = '';

	/** Le libellé de l'entrée qui vide la sélection. */
	export let tous = 'Tous';

	/**  Rendre la description sous le libellé ?
	 *
	 *   ⚠️ À réserver aux listes COURTES qui en portent une : au-delà du seuil de
	 *   6 (`ux-patterns`), des pastilles à deux lignes remplissent l'écran. Faux
	 *   par défaut — un enrichissement ne s'impose pas à ses appelants. */
	export let avecDetail = false;

	/** Décrit ce que la rangée filtre, pour le lecteur d'écran. */
	export let libelle = 'Filtres';
</script>

<div class="filters filters--defilante" role="group" aria-label={libelle}>
	<Pastille active={valeur === ''} on:click={() => (valeur = '')}>{tous}</Pastille>
	<!--  ⚠️ DEUX branches, et non un `{#if}` autour du `slot=` : Svelte exige
	      qu'un attribut `slot` soit enfant DIRECT du composant. Enveloppé dans une
	      condition, il devient une erreur de compilation — pas un rendu dégradé.
	      C'est aussi ce qui garde `$$slots.detail` faux quand il n'y a rien à
	      montrer, donc la pastille sur une seule ligne. -->
	{#each options as o (o.val)}
		{#if avecDetail && o.desc}
			<Pastille active={valeur === o.val} on:click={() => (valeur = o.val)}>
				{o.label}<span slot="detail">{o.desc}</span>
			</Pastille>
		{:else}
			<Pastille active={valeur === o.val} on:click={() => (valeur = o.val)}>{o.label}</Pastille>
		{/if}
	{/each}
</div>
