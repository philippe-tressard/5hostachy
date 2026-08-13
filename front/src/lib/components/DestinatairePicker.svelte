<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import Icon from '$lib/components/Icon.svelte';

	/** Valeurs sélectionnées — tableau de strings. Ex: ['résidents'] ou ['copropriétaires','locataires'] */
	export let value: string[] = ['résidents'];

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

<div class="destinataire-pills">
	<button type="button" class="pill" class:pill-active={isTous}
		on:click={selectTous}>
		<Icon name="users-round" size={15} />Tous les résidents
	</button>
	{#each options as o (o.code)}
		<button type="button" class="pill" class:pill-active={!isTous && selected.has(o.code)}
			on:click={() => toggleItem(o.code)}>
			<Icon name={o.icone} size={15} />{o.libelle}
		</button>
	{/each}
</div>

<style>
	.destinataire-pills { display: flex; flex-wrap: wrap; gap: .4rem; }
	.pill { display: inline-flex; align-items: center; gap: .35rem; padding: .35rem .7rem; border: 1px solid var(--color-border); border-radius: 999px; background: var(--color-surface); font-size: .82rem; cursor: pointer; color: var(--color-text-muted); transition: all .12s; white-space: nowrap; }
	.pill:hover { border-color: var(--color-primary); color: var(--color-text); }
	.pill-active { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
</style>
