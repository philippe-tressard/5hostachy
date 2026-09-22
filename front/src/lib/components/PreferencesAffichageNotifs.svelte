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

	/**  Les clés JAMAIS réglées par ce compte (#1147, 22/09/2026).
	 *
	 *   🔴 « De mon ou mes bâtiments » est cochée PAR DÉFAUT. Sans cette
	 *   distinction, l'écran montre une case cochée qui laisse croire que le
	 *   résident l'a cochée — et l'on parle alors de « ce qu'il a choisi » pour
	 *   décrire ce que personne n'a décidé.
	 *
	 *   Le défaut ne change pas : c'est lui qui garantit qu'un signalement
	 *   atteint quelqu'un. L'écran le dit, voilà tout. */
	export let heritees: Set<string> = new Set();
</script>

<section class="card" style="margin-bottom:1.5rem">
	<h2 class="section-title">Ce que j'affiche</h2>
	<label class="checkbox-field">
		<input type="checkbox" bind:checked={restreindre} />
		<span>N'afficher que les contenus de mon ou mes bâtiments</span>
	</label>
	<!--  L'exception n'est pas un détail : sans elle, ce texte promet de voir « toute
	      la copropriété » alors qu'une actualité confidentielle restera invisible
	      (v2.64.0). Un réglage qui annonce plus que ce qu'il fait se lit comme une
	      panne. -->
	<p class="aide sous-case">
		Décochée, vous voyez les actualités de toute la copropriété, sauf celles marquées
		confidentielles ; cochée, vous ne voyez que celles de votre bâtiment.
	</p>

	<h2 class="section-title" style="margin-top:1.5rem">Notifications par e-mail</h2>
	<label class="checkbox-field">
		<input type="checkbox" bind:checked={valeurs[MON_BATIMENT]} />
		<span
			>De mon ou mes bâtiments{#if heritees.has(MON_BATIMENT)}<span class="herite"
					>réglage par défaut</span
				>{/if}</span
		>
	</label>
	<label class="checkbox-field" style="margin-top:.5rem">
		<input type="checkbox" bind:checked={valeurs[AUTRES_BATIMENTS]} />
		<span
			>Des autres bâtiments{#if heritees.has(AUTRES_BATIMENTS)}<span class="herite"
					>réglage par défaut</span
				>{/if}</span
		>
	</label>
	<p class="aide sous-case">
		Les notifications dans l'application ne sont pas concernées : elles restent actives.
		{#if heritees.size > 0}
			Les réglages marqués « par défaut » n'ont jamais été modifiés : enregistrez pour en faire
			votre choix.
		{/if}
	</p>

	<div class="form-actions">
		<button type="button" class="btn btn-primary" on:click={() => onSave(valeurs, restreindre)}
			>Enregistrer</button
		>
	</div>
</section>

<style>
	/*  `.section-title` : la charte porte tout (composants.css). Retiree le 28/08/2026 (#607). */
	/*  Seul `flex-wrap` differe de la charte (#607, 28/08/2026). */
	.form-actions {
		flex-wrap: wrap;
	}

	/*  Une étiquette, pas un badge d'état : elle dit d'où vient la valeur, ce qui
	    est une information de second plan. Plus petite que le libellé, en gris de
	    la charte, et jamais colorée — un réglage hérité n'est ni une alerte ni
	    une réussite. */
	.herite {
		margin-left: 0.4rem;
		font-size: 0.7rem;
		color: var(--color-text-muted);
		white-space: nowrap;
	}

	.checkbox-field input {
		margin: 0;
		flex-shrink: 0;
	}
	/*  L'aide s'aligne sur le LIBELLÉ, pas sur le bord de la carte : largeur de la
	    case (~1rem) plus l'écart (.5rem). Seuls le décalage et la marge restent
	    ici — la typographie vient de la charte depuis le 09/09/2026. */
</style>
