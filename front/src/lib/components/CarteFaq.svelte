<!--
  CarteFaq.svelte — UNE question de la FAQ, avec sa réponse dépliable.

  ## Pourquoi ce fichier existe (05/09/2026)

  Le contrôle de modularité a refusé que `faq/+page.svelte` grossisse de cinq
  lignes : il faisait déjà 772 lignes. Les trois réponses possibles sont écrites
  dans `ux-patterns` — découper, remonter la règle d'un cran, ou raboter — et
  seule la dernière est mauvaise. Ici, l'ajout (l'icône de lien) est propre à la
  carte : c'est donc la carte qu'on sort.

  Le balisage part **avec ses règles CSS**, sans exception : Svelte scope les
  styles au composant, et une règle laissée dans la page n'habillerait plus rien
  (leçon de `Pastille.svelte`, v2.67.11, et de `CarteActualite` avant elle).

  ⚠️ La rangée d'actions n'est plus conditionnée au droit d'édition : elle porte
  désormais l'icône de lien, que **tout le monde** doit voir. Seuls les trois
  gestes d'édition restent réservés.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import BoutonLien from '$lib/components/BoutonLien.svelte';
	import { safeHtml } from '$lib/sanitize';

	/** La question, telle que l'API la rend. */
	export let item: { id: number; question: string; reponse: string; actif: boolean };
	/** La réponse est-elle dépliée ? L'état vit dans la page : une seule ouverte. */
	export let ouvert = false;
	/** L'utilisateur peut-il modifier, masquer et supprimer ? */
	export let canEdit = false;
	/**  Cette question mène-t-elle à la demande d'accès ? La reconnaissance vit dans
	 *   la page, qui sait ce qu'est « la question du prix d'un badge ». */
	export let avecCta = false;

	const dispatch = createEventDispatcher<{
		basculer: void;
		modifier: void;
		basculerActif: void;
		supprimer: void;
	}>();
</script>

<div
	id="faq-{item.id}"
	class="faq-item card"
	class:item-inactive={!item.actif}
	role="button"
	tabindex="0"
	on:click={() => dispatch('basculer')}
	on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && dispatch('basculer')}
>
	<div class="faq-header">
		<button class="faq-q" tabindex="-1" aria-expanded={ouvert}>
			<span>{item.question}</span>
			<span class="chevron" class:open={ouvert}>›</span>
		</button>
		<div class="faq-actions">
			<BoutonLien ancre="faq-{item.id}" quoi="la question" />
			{#if canEdit}
				<button
					class="btn-icon-edit"
					aria-label="Modifier"
					title="Modifier"
					on:click|stopPropagation={() => dispatch('modifier')}>✏️</button
				>
				<button
					class={item.actif ? 'btn-icon-warn' : 'btn-icon-edit'}
					aria-label={item.actif ? 'Masquer' : 'Afficher'}
					title={item.actif ? 'Masquer' : 'Afficher'}
					on:click|stopPropagation={() => dispatch('basculerActif')}
				>
					{item.actif ? '\u{1F648}' : '\u{1F441}️'}
				</button>
				<button
					class="btn-icon-danger"
					aria-label="Supprimer"
					title="Supprimer"
					on:click|stopPropagation={() => dispatch('supprimer')}>&#x1F5D1;️</button
				>
			{/if}
		</div>
	</div>
	{#if ouvert}
		<!--  Le corps ne referme pas la carte : on lit, on sélectionne, on copie. -->
		<div class="faq-a rich-content" role="presentation" on:click|stopPropagation>
			{@html safeHtml(item.reponse)}
			{#if avecCta}
				<div class="faq-cta-row">
					<a class="btn btn-primary btn-sm" href="/acces-securite#nouvelle-demande"
						>Faire une nouvelle demande d'accès</a
					>
					<a class="btn btn-outline btn-sm" href="/acces-securite">Voir Accès &amp; badges</a>
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.faq-item {
		cursor: pointer;
		margin-bottom: 0.35rem;
		overflow: visible;
		padding: 0;
	}
	.item-inactive {
		opacity: 0.55;
	}
	.faq-header {
		display: flex;
		align-items: center;
	}
	.faq-q {
		user-select: none;
		flex: 1;
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.875rem 1rem;
		background: none;
		border: none;
		cursor: pointer;
		font-size: 0.925rem;
		font-weight: 500;
		text-align: left;
		gap: 1rem;
		color: var(--color-text);
	}
	.faq-q:hover {
		background: var(--color-bg-subtle);
	}
	/*  Écart assumé : il HÉRITE la couleur de sa question, et vit dans un flex. */
	.chevron {
		color: inherit;
		flex-shrink: 0;
	}
	.faq-a {
		padding: 0.5rem 1rem 0.9rem;
		font-size: 0.875rem;
		color: var(--color-text-muted);
		line-height: 1.55;
		border-top: 1px solid var(--color-border);
	}
	.faq-cta-row {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
		margin-top: 0.8rem;
		padding-top: 0.75rem;
		border-top: 1px dashed var(--color-border);
	}
	.faq-actions {
		display: flex;
		gap: 0.15rem;
		padding-right: 0.5rem;
	}
</style>
