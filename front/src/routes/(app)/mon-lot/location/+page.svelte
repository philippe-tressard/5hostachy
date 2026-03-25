<script lang="ts">
import { goto } from '$app/navigation';
import { onMount } from 'svelte';
onMount(() => goto('/mon-lot', { replaceState: true }));
</script>

<p style="color:var(--color-text-muted)">Redirection…</p>
