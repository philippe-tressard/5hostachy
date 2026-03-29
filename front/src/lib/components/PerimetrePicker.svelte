<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	/** Valeurs sélectionnées — tableau de strings. Ex: ['résidence'] ou ['bat:1','parking'] */
	export let value: string[] = ['résidence'];

	/** Mode mono-sélection (select dropdown) ou multi (pills). Par défaut: multi */
	export let mode: 'multi' | 'single' = 'multi';

	const dispatch = createEventDispatcher<{ change: string[] }>();

	const options: [string, string][] = [
		['bat:1', 'Bât. 1'],
		['bat:2', 'Bât. 2'],
		['bat:3', 'Bât. 3'],
		['bat:4', 'Bât. 4'],
		['parking', 'Parking'],
		['cave', 'Cave'],
		['aful', 'AFUL'],
	];

	$: isResidence = value.length === 0 || (value.length === 1 && value[0] === 'résidence');
	$: selected = new Set(value);

	function selectResidence() {
		value = ['résidence'];
		dispatch('change', value);
	}

	function toggleItem(val: string) {
		if (mode === 'single') {
			value = [val];
			dispatch('change', value);
			return;
		}
		const s = new Set(value.filter(v => v !== 'résidence'));
		if (s.has(val)) s.delete(val);
		else s.add(val);
		value = s.size > 0 ? [...s] : ['résidence'];
		dispatch('change', value);
	}

	function handleSingleChange(e: Event) {
		const v = (e.target as HTMLSelectElement).value;
		value = [v];
		dispatch('change', value);
	}
</script>

{#if mode === 'single'}
	<select value={value[0] ?? 'résidence'} on:change={handleSingleChange} class="perimetre-select">
		<option value="résidence">🏘️ Copropriété entière</option>
		{#each options as [val, lbl]}
			<option value={val}>{lbl}</option>
		{/each}
	</select>
{:else}
	<div class="perimetre-pills">
		<button type="button" class="pill" class:pill-active={isResidence}
			on:click={selectResidence}>
			🏘️ Copropriété entière
		</button>
		{#each options as [val, lbl]}
			<button type="button" class="pill" class:pill-active={!isResidence && selected.has(val)}
				on:click={() => toggleItem(val)}>
				{lbl}
			</button>
		{/each}
	</div>
{/if}

<style>
	.perimetre-pills { display: flex; flex-wrap: wrap; gap: .4rem; }
	.pill { padding: .35rem .7rem; border: 1px solid var(--color-border); border-radius: 999px; background: var(--color-surface); font-size: .82rem; cursor: pointer; color: var(--color-text-muted); transition: all .12s; white-space: nowrap; }
	.pill:hover { border-color: var(--color-primary); color: var(--color-text); }
	.pill-active { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
	.perimetre-select { padding: .4rem .55rem; border: 1px solid var(--color-border); border-radius: var(--radius); font-size: .875rem; background: var(--color-bg); width: 100%; }
</style>
