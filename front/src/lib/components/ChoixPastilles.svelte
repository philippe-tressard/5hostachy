<!--
  ChoixPastilles.svelte — choisir UNE entrée d'une liste courte, en pastilles.

  ## Pourquoi ce composant (29 puis 30/08/2026, #491)

  Il s'appelait `BarreFiltres` et ne servait qu'aux filtres. Son propre en-tête
  annonçait ce qui allait arriver :

  > « C'est la duplication la plus discrète : elle vit dans un seul fichier, donc
  >   aucun contrôle inter-fichiers ne la voit, et **elle se recopie une troisième
  >   fois au premier filtre ajouté**. »

  🔴 **La troisième recopie a eu lieu le lendemain**, et pas sur un filtre : en
  convertissant le `<select>` « Type de prestataire » du FORMULAIRE, dans le
  même écran. Le garde-fou de modularité l'a refusée — et il disait vrai, au
  sens de #453 : *le refus signale que le code est au mauvais endroit, pas
  qu'il est trop long.*

  Le motif n'était donc pas « une barre de filtres » mais **« choisir une entrée
  d'une liste courte »**. Le filtre en est un cas : celui qui accepte de ne rien
  choisir.

  | | Filtre | Champ de formulaire |
  |---|---|---|
  | entrée « Tous » | oui | `tous={false}` — un champ requis n'a pas de vide |
  | libellé | invisible (`aria-label`) | visible, avec son `*` |
  | conteneur | rangée défilante | `.field champ-large` |

  ⚠️ Il ne remplace PAS `Pastille` : il l'emploie. Ce qu'il porte, c'est le
  MOTIF — l'entrée qui vide la sélection, l'égalité entre la valeur courante et
  chaque option, le défilement horizontal, et le libellé de groupe.

  🔴 **Le libellé visible est un `libelle-groupe`, pas un `<label>`.** Une rangée
  de `<button>` n'est pas labelable : un `for` posé dessus n'associe rien, **et
  le fait en silence** (`ux-patterns` §9 septies). D'où le couple
  `<span class="libelle-groupe" id>` + `role="group" aria-labelledby`.

  UTILISATION :
    <ChoixPastilles options={TYPES} bind:valeur={filtre} avecDetail />
    <ChoixPastilles options={TYPES} bind:valeur={form.type} tous={false}
                    libelle="Type" requis avecDetail />
-->
<script context="module" lang="ts">
	/** Compte les instances, pour donner un identifiant stable a chaque libelle. */
	let compteur = 0;
</script>

<script lang="ts">
	import Pastille from '$lib/components/Pastille.svelte';

	/** Les entrées. `desc` n'est lue que si `avecDetail` est vrai. */
	export let options: readonly { val: string; label: string; desc?: string }[] = [];

	/** La valeur retenue. Chaîne vide = rien de choisi. */
	export let valeur = '';

	/**
	 * Le libellé de l'entrée qui vide la sélection — ou `false` pour ne pas
	 * l'offrir.
	 *
	 * ⚠️ `false` sur un champ **requis** : proposer « Tous » y donnerait un moyen
	 * de vider une valeur que le formulaire exige, donc un choix qui ne peut pas
	 * être soumis.
	 */
	export let tous: string | false = 'Tous';

	/**  Rendre la description sous le libellé ?
	 *
	 *   ⚠️ À réserver aux listes COURTES qui en portent une : au-delà du seuil de
	 *   6 (`ux-patterns`), des pastilles à deux lignes remplissent l'écran. Faux
	 *   par défaut — un enrichissement ne s'impose pas à ses appelants. */
	export let avecDetail = false;

	/** Ce que la rangée choisit. Toujours annoncé ; affiché si `libelleVisible`. */
	export let libelle = 'Filtres';

	/** Afficher le libellé au-dessus de la rangée — le cas du formulaire. */
	export let libelleVisible = false;

	/** Ajoute le ` *` de la charte au libellé visible. */
	export let requis = false;

	//  Un identifiant par instance : deux rangées sur le même écran ne doivent pas
	//  se renvoyer au même libellé.
	//
	//  ⚠️ Un compteur de MODULE, et non `Math.random()` ni `performance.now()` :
	//  ceux-là donnent une valeur au rendu serveur et une autre à l'hydratation,
	//  d'où un `aria-labelledby` qui ne pointe sur rien pendant un instant — et
	//  rien ne le signale.
	const idTitre = `choix-pastilles-${++compteur}`;
</script>

<div class={libelleVisible ? 'field champ-large' : ''}>
	{#if libelleVisible}
		<span class="libelle-groupe" id={idTitre}>{libelle}{requis ? ' *' : ''}</span>
	{/if}
	<div
		class="filters filters--defilante"
		role="group"
		aria-label={libelleVisible ? undefined : libelle}
		aria-labelledby={libelleVisible ? idTitre : undefined}
	>
		{#if tous !== false}
			<Pastille active={valeur === ''} on:click={() => (valeur = '')}>{tous}</Pastille>
		{/if}
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
</div>
