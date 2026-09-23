<!--
  ChampFrequence.svelte — le rythme d'un passage : « toutes les X semaines »,
  « mensuelle », « X fois par an », « tous les X ans ».

  Extrait le 23/09/2026 (#1092, lot 5). La fréquence s'écrivait DEUX fois, et
  différemment : le contrat proposait quatre unités dont « mensuelle » sans
  nombre, l'événement trois dont « tous les N mois ». L'affaire Entretien, qui
  reçoit les maintenances du calendrier, en aurait été la troisième. Le contrat
  fait référence — c'est lui qui fixe le rythme d'un prestataire — et ses unités
  se lisent dans `FREQUENCES` (`$lib/prestataires`), jamais dans l'écran.

  Forme standard d'un champ de section : `.field` puis `<label for>` — la même
  que « Début » et « Fin » juste au-dessus, en deux colonnes qui repassent en
  une sur téléphone (`.form-grid-2`).

  « Mensuelle » ne demande pas de nombre : il vaut 1, posé ici pour que le
  serveur reçoive toujours une paire complète.
-->
<script lang="ts">
	import { FREQUENCES } from '$lib/prestataires';

	export let frequenceType: string | null | undefined = '';
	export let frequenceValeur: number | string | null | undefined = null;
	export let idPrefixe = 'frequence';

	$: unite = FREQUENCES.find((f) => f.val === frequenceType);
	$: if (unite && !unite.nombre) frequenceValeur = 1;
</script>

<div class="form-grid form-grid-2 frequence">
	<div class="field">
		<label for="{idPrefixe}-type">Fréquence</label>
		<select id="{idPrefixe}-type" bind:value={frequenceType}>
			<option value="">— Aucune —</option>
			{#each FREQUENCES as f (f.val)}<option value={f.val}>{f.label}</option>{/each}
		</select>
	</div>
	{#if unite?.nombre}
		<div class="field">
			<label for="{idPrefixe}-valeur">{unite.nombre}</label>
			<input id="{idPrefixe}-valeur" type="number" min="1" bind:value={frequenceValeur} />
		</div>
	{/if}
</div>

<style>
	/*  Seul l'écart : la disposition vient de `.form-grid-2` (`champs.css`). */
	.frequence {
		margin-top: 0.75rem;
	}
</style>
