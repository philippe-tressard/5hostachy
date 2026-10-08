<!--
  La marque de la résidence — son logo téléversé, sinon l'icône du catalogue (#1728).

  Arbitré le 08/10/2026 : un logo téléversé REMPLACE l'icône choisie dans le
  catalogue (`site_icone`) partout où celle-ci s'affichait — la barre de
  navigation et l'écran de connexion. Sans logo, rien ne change.

  L'icône était lue à trois endroits (deux dans `Nav`, un à la connexion), chacun
  avec son repli `'building-2'` recopié : la règle « logo, sinon icône » s'y
  serait recopiée trois fois à son tour.

  `alt` est vide : le nom de la résidence est toujours écrit à côté.
-->
<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import { config as configApi } from '$lib/api';
	import { configStore } from '$lib/stores/pageConfig';

	/** Côté affiché, en pixels. */
	export let taille: number;

	$: logo = $configStore['site_logo'] ?? '';
	$: icone = $configStore['site_icone'] ?? 'building-2';
</script>

{#if logo}
	<!--  Demandé en double densité : net sur un écran de téléphone. -->
	<img
		class="logo-residence"
		src={configApi.logoUrl(taille * 2, logo)}
		width={taille}
		height={taille}
		alt=""
	/>
{:else}
	<Icon name={icone} size={taille} />
{/if}

<style>
	.logo-residence {
		display: block;
		object-fit: contain;
	}
</style>
