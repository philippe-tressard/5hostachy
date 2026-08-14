<!--
  Les préférences personnelles du profil : ce que je VOIS, ce que je REÇOIS.

  Extrait de `routes/(app)/profil/+page.svelte` le 14/08/2026 (#339). La page
  dépassait 838 lignes — le contrôle de modularité refuse qu'un fichier déjà
  au-dessus de 500 grossisse.

  Les notifications sont passées de HUIT cases (quatre rubriques × appli/e-mail)
  à DEUX. Le résident devait comprendre une matrice pour dire une chose simple :
  « je veux les e-mails de chez moi, pas ceux d'à côté ». Ce que la simplification
  coûte est assumé et documenté dans `api/app/utils/preferences_mail.py` — le
  réglage par rubrique disparaît, et les notifications dans l'application restent
  actives sans être réglables, ce qui était déjà leur valeur par défaut.

  ⚠️ La case de visibilité est une préférence d'AFFICHAGE, jamais une mesure de
  confidentialité : le résident se restreint lui-même et peut se déverrouiller
  quand il veut. Ce qui protège reste le public cible d'une publication et les
  profils d'accès aux documents. L'interface ne doit pas laisser croire l'inverse.
-->
<script lang="ts">
	import { AUTRES_BATIMENTS, MON_BATIMENT } from '$lib/preferences';

	export let valeurs: Record<string, boolean>;
	export let restreindre = false;
	export let onSave: (valeurs: Record<string, boolean>, restreindre: boolean) => void;
</script>

<section class="card" style="margin-bottom:1.5rem">
	<h2 class="section-title">Ce que j'affiche</h2>
	<label class="checkbox-field">
		<input type="checkbox" bind:checked={restreindre} />
		<span>N'afficher que les contenus de mon ou mes bâtiments</span>
	</label>
	<p class="aide">
		Décochée, vous voyez les actualités de toute la copropriété ; cochée, vous ne voyez
		que celles de votre bâtiment.
	</p>

	<h2 class="section-title" style="margin-top:1.5rem">Notifications par e-mail</h2>
	<label class="checkbox-field">
		<input type="checkbox" bind:checked={valeurs[MON_BATIMENT]} />
		<span>De mon ou mes bâtiments</span>
	</label>
	<label class="checkbox-field" style="margin-top:.5rem">
		<input type="checkbox" bind:checked={valeurs[AUTRES_BATIMENTS]} />
		<span>Des autres bâtiments</span>
	</label>
	<p class="aide">
		Les notifications dans l'application ne sont pas concernées : elles restent actives.
	</p>

	<div class="form-actions">
		<button type="button" class="btn btn-primary" on:click={() => onSave(valeurs, restreindre)}>Enregistrer</button>
	</div>
</section>

<style>
	.section-title { font-size: 1rem; font-weight: 600; margin-bottom: 1rem; }
	.form-actions { display: flex; justify-content: flex-end; margin-top: 1rem; gap: .5rem; flex-wrap: wrap; }
	.checkbox-field { display: flex; align-items: center; gap: .5rem; font-size: .9rem; cursor: pointer; }
	.checkbox-field input { margin: 0; flex-shrink: 0; }
	/*  L'aide s'aligne sur le LIBELLÉ, pas sur le bord de la carte : largeur de la
	    case (~1rem) plus l'écart (.5rem). */
	.aide {
		font-size: .82rem;
		color: var(--color-text-muted);
		margin: .35rem 0 0;
		padding-left: 1.5rem;
		line-height: 1.45;
	}
</style>
