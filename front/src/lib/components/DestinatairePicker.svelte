<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import Pastille from '$lib/components/Pastille.svelte';
	import { DESTINATAIRES, TOUS_LES_RESIDENTS, concerneTousLesResidents } from '$lib/destinataires';

	/** Valeurs sélectionnées — tableau de strings. Ex: ['résidents'] ou ['copropriétaires','locataires'] */
	export let value: string[] = ['résidents'];

	/** Intitulé du champ — porté par l'objet, comme pour le périmètre. Les pages
	    l'écrivaient chacune de leur côté. */
	export let titre = 'Destinataires';

	/** Astérisque des champs requis. */
	export let requis = true;

	const dispatch = createEventDispatcher<{ change: string[] }>();

	//  ⚠️ La table des profils n'est PLUS ici : elle vit dans `$lib/destinataires.ts`.
	//  Écrite dans le sélecteur, elle n'était disponible que pour SÉLECTIONNER —
	//  et la liste des sondages affichait donc les valeurs brutes de la base dans
	//  ses badges, faute de pouvoir les traduire. Même partage que
	//  `$lib/perimetres.ts` pour l'axe géographique.
	//
	//  « Bailleurs » (13/08/2026) et « Copropriétaires occupants » (16/08/2026)
	//  sont symétriques : « Copropriétaires » couvre les DEUX statuts
	//  `copropriétaire_*`, si bien qu'on ne savait s'adresser ni aux uns ni aux
	//  autres seuls — alors que des pans entiers du produit leur sont propres.
	//  Les deux ajouts sont purement additifs côté serveur : une valeur inconnue
	//  tombait déjà sur un refus, donc aucune publication existante ne change de
	//  public.

	$: isTous = concerneTousLesResidents(value);
	$: selected = new Set(value);

	function selectTous() {
		value = [TOUS_LES_RESIDENTS];
		dispatch('change', value);
	}

	function toggleItem(val: string) {
		const s = new Set(value.filter(v => v !== TOUS_LES_RESIDENTS));
		if (s.has(val)) s.delete(val);
		else s.add(val);
		value = s.size > 0 ? [...s] : [TOUS_LES_RESIDENTS];
		dispatch('change', value);
	}
</script>

{#if titre}
	<!--  Badge d'état : « Tous les résidents » se lit sans dépiler les pastilles.
	      Même règle que le périmètre (skill `ux-patterns` §9 quater). -->
	<div class="destinataire-titre">
		{titre}{#if requis} *{/if}
		{#if isTous}<span class="badge badge-green destinataire-badge">Tous les résidents</span>{/if}
	</div>
{/if}
<div class="destinataire-pills">
	<Pastille active={isTous} icone="users-round" on:click={selectTous}>Tous les résidents</Pastille>
	{#each DESTINATAIRES as o (o.code)}
		<Pastille active={!isTous && selected.has(o.code)} icone={o.icone}
			on:click={() => toggleItem(o.code)}>{o.libelle}</Pastille>
	{/each}
</div>

<style>
	.destinataire-pills { display: flex; flex-wrap: wrap; gap: .4rem; }
	.destinataire-titre { font-size: .875rem; font-weight: 500; color: var(--color-text); margin-bottom: .3rem; }
	.destinataire-badge { font-size: .72rem; margin-left: .4rem; }
</style>
