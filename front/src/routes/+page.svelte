<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { auth } from '$lib/api';
	import { setUser } from '$lib/stores/auth';
	import { CHEMIN_CONNEXION } from '$lib/redirection';

	onMount(async () => {
		try {
			const user = await auth.me();
			setUser(user);
			goto('/tableau-de-bord');
		} catch {
			goto(CHEMIN_CONNEXION);
		}
	});
</script>

<div style="display:flex;align-items:center;justify-content:center;height:100vh;">
	<p style="color:var(--color-text-muted)">Chargement…</p>
</div>
