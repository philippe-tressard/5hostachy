<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	/** Valeurs sélectionnées — tableau de strings. Ex: ['résidents'] ou ['copropriétaires','locataires'] */
	export let value: string[] = ['résidents'];

	const dispatch = createEventDispatcher<{ change: string[] }>();

	const options: [string, string][] = [
		['copropriétaires', 'Copropriétaires'],
		['locataires', 'Locataires'],
		['conseil_syndical', 'Conseil syndical'],
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
		👥 Tous les résidents
	</button>
	{#each options as [val, lbl]}
		<button type="button" class="pill" class:pill-active={!isTous && selected.has(val)}
			on:click={() => toggleItem(val)}>
			{lbl}
		</button>
	{/each}
</div>

<style>
	.destinataire-pills { display: flex; flex-wrap: wrap; gap: .4rem; }
	.pill { padding: .35rem .7rem; border: 1px solid var(--color-border); border-radius: 999px; background: var(--color-surface); font-size: .82rem; cursor: pointer; color: var(--color-text-muted); transition: all .12s; white-space: nowrap; }
	.pill:hover { border-color: var(--color-primary); color: var(--color-text); }
	.pill-active { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
</style>
