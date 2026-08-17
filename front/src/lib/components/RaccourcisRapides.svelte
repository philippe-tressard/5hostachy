<script lang="ts">
	//  La rangée de raccourcis du tableau de bord. Le balisage part avec ses
	//  règles CSS (Svelte les scope au composant), et la page passe de 947 à un
	//  peu moins — le découpage se fait au fil de l'eau, sur ce qu'on touche.
	//
	//  Ce composant ne décide de RIEN : qui voit quoi et d'où vient chaque nombre
	//  sont déclarés dans `$lib/raccourcis.ts`. Il ne fait que rendre la table.
	import Icon from '$lib/components/Icon.svelte';
	import { currentUser } from '$lib/stores/auth';
	import { raccourcisVisibles } from '$lib/raccourcis';
	import type { FluxSante } from '$lib/api';

	export let sante: FluxSante;
	/** Anime l'apparition, comme les autres sections de la page. */
	export let ready = false;

	$: visibles = raccourcisVisibles($currentUser);
</script>

<nav class="quick-nav" class:section-visible={ready} aria-label="Raccourcis">
	{#each visibles as r (r.id)}
		<a
			href={r.href}
			class="quick-pill"
			class:quick-pill-cs={r.variante === 'cs'}
			class:quick-pill-admin={r.variante === 'admin'}
		>
			<Icon name={r.icone} size={14} /> {r.libelle}
			{#each r.compteurs(sante) as c}
				{#if c.valeur > 0}
					<span
						class="quick-count"
						class:quick-count-urgent={c.ton === 'urgent'}
						class:quick-count-orange={c.ton === 'orange'}
					>{c.libelle ? c.libelle(c.valeur) : c.valeur}</span>
				{/if}
			{/each}
		</a>
	{/each}
</nav>

<style>
	.quick-nav {
		display: flex; gap: .5rem; flex-wrap: wrap; margin: .75rem 0; padding: 0;
		opacity: 0; transform: translateY(8px);
		transition: opacity .3s ease .08s, transform .3s ease .08s;
	}
	.quick-nav.section-visible { opacity: 1; transform: translateY(0); }
	.quick-pill {
		display: inline-flex; align-items: center; gap: .35rem;
		padding: .4rem .8rem; border-radius: 2rem;
		background: var(--color-surface); border: 1px solid var(--color-border);
		font-size: .78rem; font-weight: 500; color: var(--color-text); text-decoration: none;
		transition: border-color .15s, box-shadow .15s, background .15s; white-space: nowrap;
	}
	.quick-pill:hover { border-color: var(--color-primary); box-shadow: var(--shadow-sm); background: var(--color-primary-light); }
	.quick-count {
		background: var(--color-primary); color: #fff;
		font-size: .65rem; font-weight: 700;
		padding: .05rem .4rem; border-radius: 1rem; line-height: 1.3; min-width: 1.1rem; text-align: center;
	}
	.quick-pill-cs { border-color: #F59E0B; }
	.quick-pill-cs:hover { border-color: #D97706; background: #FFFBEB; }
	/*  L'Admin se distingue du CS : deux pastilles orange côte à côte se liraient
	    comme une seule zone, alors que ce sont deux destinations différentes. */
	.quick-pill-admin { border-color: #7C3AED; }
	.quick-pill-admin:hover { border-color: #6D28D9; background: #F5F3FF; }
	.quick-count-urgent { background: #DC2626; }
	.quick-count-orange { background: #D97706; }

	@media (max-width: 767px) {
		.quick-nav { gap: .35rem; }
		.quick-pill { font-size: .72rem; padding: .35rem .65rem; }
	}
</style>
