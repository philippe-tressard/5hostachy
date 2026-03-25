<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { isAdmin } from '$lib/stores/auth';

	onMount(() => {
		if (!$isAdmin) {
			goto('/tableau-de-bord');
		}
	});
</script>

{#if $isAdmin}
	<slot />
{/if}
