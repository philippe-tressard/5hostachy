<script lang="ts">
	import '../app.css';
	import Toast from '$lib/components/Toast.svelte';
	import MajDisponible from '$lib/components/MajDisponible.svelte';
	import { configStore } from '$lib/stores/pageConfig';

	export let data;

	// Peuple le store depuis les données SSR → zéro flash au premier rendu
	$: if (data?.siteConfig && Object.keys(data.siteConfig).length > 0) {
		configStore.set(data.siteConfig);
	}
</script>

<Toast />
<MajDisponible />
<slot />
