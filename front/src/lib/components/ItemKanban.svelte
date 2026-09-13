<script lang="ts">
	/**
	 * Une **carte du kanban condensé** du tableau de bord — icône, titre, périmètre.
	 *
	 * 🔴 Écrite DEUX fois dans `tableau-de-bord/+page.svelte` jusqu'au 13/09/2026 :
	 * une fois pour les colonnes larges, une fois pour la vue étroite qui n'en
	 * montre qu'une à la fois. Dix-sept lignes identiques à cinquante lignes
	 * d'écart, dans un fichier de plus de mille — c'est-à-dire à un endroit où
	 * personne ne les voit toutes les deux.
	 *
	 * Le plafond de modularité l'a désignée en refusant onze lignes de plus : comme
	 * les refus précédents, il pointait une duplication que la longueur cachait.
	 *
	 * ⚠️ Les classes `kb-*` sont **globales** (`styles/composants.css`), pas
	 * scopées à la page : le balisage peut donc déménager sans emporter de style.
	 * C'est ce qui rend cette extraction sûre, là où celle de `RangeeCalendrier`
	 * avait dû reprendre les deux blocs ensemble.
	 */
	import { goto } from '$app/navigation';
	import { estPerimetreParDefaut, perimetreLabel } from '$lib/perimetres';
	import { perimetresStore } from '$lib/stores/perimetres';
	import { relire } from '$lib/utils';

	/** L'événement rendu — on n'en lit que l'identifiant, le type, le titre, le périmètre. */
	export let item: { id: number; type: string; titre: string; perimetre: string };
	/** Les icônes par type, décidées par l'écran appelant — jamais recopiées ici. */
	export let icones: Record<string, string> = {};

	$: lien = `/calendrier#ev-${item.id}`;

	//  ⚠️ `$perimetresStore` n'est pas lu : il dit à Svelte que ce calcul dépend de
	//  l'arbre, que les deux fonctions lisent dans un état de MODULE. Sans lui, un
	//  tableau de bord affiché avant l'arrivée de l'arbre gardait le code brut, et
	//  rien ne revenait le corriger (#947).
	$: textePerimetre = relire($perimetresStore, () =>
		item.perimetre && !estPerimetreParDefaut(item.perimetre) ? perimetreLabel(item.perimetre) : '',
	);
</script>

<div
	class="kb-item"
	role="button"
	tabindex="0"
	on:click={() => goto(lien)}
	on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && goto(lien)}
>
	<span class="kb-item-icon">{icones[item.type] ?? '\u{1F4CC}'}</span>
	<div class="kb-item-text">
		<span class="kb-item-titre clamp-2">{item.titre}</span>
		{#if textePerimetre}
			<span class="kb-item-perim">&#x1F539; {textePerimetre}</span>
		{/if}
	</div>
</div>
