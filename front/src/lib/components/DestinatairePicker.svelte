<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import Pastille from '$lib/components/Pastille.svelte';

	/** Valeurs sélectionnées — tableau de strings. Ex: ['résidents'] ou ['copropriétaires','locataires'] */
	export let value: string[] = ['résidents'];

	/** Intitulé du champ — porté par l'objet, comme pour le périmètre. Les pages
	    l'écrivaient chacune de leur côté. */
	export let titre = 'Destinataires';

	/** Astérisque des champs requis. */
	export let requis = true;

	const dispatch = createEventDispatcher<{ change: string[] }>();

	//  `code`, libellé, icône. Les icônes sont celles d'`Icon.svelte` ; un nom
	//  absent de sa table s'afficherait avec le point d'interrogation du repli.
	//
	//  « Bailleurs » est ajouté le 13/08/2026 : « Copropriétaires » couvre les DEUX
	//  statuts `copropriétaire_*`, si bien que rien ne permettait de s'adresser aux
	//  bailleurs sans toucher les copropriétaires occupants — alors que tout un pan
	//  du produit leur est propre (baux, remise d'objets, accès confiés aux
	//  locataires). L'ajout est purement additif côté serveur : une valeur inconnue
	//  tombait déjà sur un refus, donc aucune publication existante ne change de
	//  public.
	const options: { code: string; libelle: string; icone: string }[] = [
		{ code: 'copropriétaires', libelle: 'Copropriétaires', icone: 'key-round' },
		{ code: 'bailleurs', libelle: 'Bailleurs', icone: 'home' },
		{ code: 'locataires', libelle: 'Locataires', icone: 'user' },
		{ code: 'conseil_syndical', libelle: 'Conseil syndical', icone: 'shield-check' },
	];

	$: isTous = value.length === 0 || (value.length === 1 && value[0] === 'résidents');
	$: selected = new Set(value);

	function selectTous() {
		value = ['résidents'];
		dispatch('change', value);
	}

	function toggleItem(val: string) {
		const s = new Set(value.filter(v => v !== 'résidents'));
		if (s.has(val)) s.delete(val);
		else s.add(val);
		value = s.size > 0 ? [...s] : ['résidents'];
		dispatch('change', value);
	}
</script>

{#if titre}
	<!--  Badge d'état : « Tous les résidents » se lit sans dépiler les pastilles.
	      Même règle que le périmètre (skill `ux-patterns` §9 quater). -->
	<div class="destinataire-titre">
		{titre}{#if requis} *{/if}
		{#if isTous}<span class="badge badge-green destinataire-badge">Tous les résidents</span>{/if}
	</div>
{/if}
<div class="destinataire-pills">
	<Pastille active={isTous} icone="users-round" on:click={selectTous}>Tous les résidents</Pastille>
	{#each options as o (o.code)}
		<Pastille active={!isTous && selected.has(o.code)} icone={o.icone}
			on:click={() => toggleItem(o.code)}>{o.libelle}</Pastille>
	{/each}
</div>

<style>
	.destinataire-pills { display: flex; flex-wrap: wrap; gap: .4rem; }
	.destinataire-titre { font-size: .875rem; font-weight: 500; color: var(--color-text); margin-bottom: .3rem; }
	.destinataire-badge { font-size: .72rem; margin-left: .4rem; }
</style>
