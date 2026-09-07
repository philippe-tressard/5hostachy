<!--
  La barre d'actions d'un membre — conseil syndical ET syndic (#816).

  ## Pourquoi ce composant

  Le trio « Enregistrer · Modifier · Supprimer » était écrit **deux fois** dans
  `espace-cs/+page.svelte`, à cent lignes d'écart et à l'identique : mêmes
  classes, mêmes icônes, même bascule `édition ? disquette : crayon`. Seules
  changeaient la variable d'état (`cs` / `syndic`) et les trois fonctions
  appelées. C'est la duplication au sens strict — deux écritures d'une même
  règle, qui divergent au premier ajustement.

  Le crayon du bandeau de l'onglet (`.header-summary`) en était une **troisième**
  écriture, sans barre autour. Il passe par ici avec `barre={false}`.

  ## Les gestes propres à un écran

  La liste du syndic porte trois gestes de plus — monter, descendre, désigner
  l'interlocuteur principal — que celle du CS n'a pas. Ils sont passés en
  **données** (`gestes`) et non en slot : le balisage d'un slot est stylé par la
  portée du PARENT, ce qui aurait laissé `.btn-icon` et ses variantes écrites des
  deux côtés. En données, tout le style habite ici, une seule fois.

  ⚠️ La `variante` est un mot du métier, pas un nom de classe : une classe
  interpolée (`class="btn-icon {g.classe}"`) fait taire l'analyse des sélecteurs
  orphelins de Svelte **pour le fichier entier** — la panne exacte de #813.
-->
<script context="module" lang="ts">
	/**
	 *  Un geste propre à l'écran, rendu AVANT le trio commun.
	 *
	 *  🔴 Exporté depuis le module : l'appelant qui construit la liste s'en sert
	 *  pour se typer. Recopier la forme chez lui aurait donné deux définitions
	 *  d'une même chose, qui divergent au premier champ ajouté.
	 */
	export type Geste = {
		variante: 'deplacer' | 'designer';
		libelle: string;
		glyphe: string;
		desactive?: boolean;
		onClic: () => void;
	};
</script>

<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';

	export let gestes: Geste[] = [];
	/** Le membre est en cours d'édition : la disquette remplace le crayon. */
	export let enEdition = false;
	/** L'enregistrement est en cours : la disquette devient des points de suspension. */
	export let enregistrement = false;
	export let onEnregistrer: (() => void) | null = null;
	export let onModifier: (() => void) | null = null;
	export let onSupprimer: (() => void) | null = null;
	/**
	 *  Barre d'actions d'une carte (défaut), ou bouton seul dans une rangée qui a
	 *  déjà sa propre disposition — `display: contents` laisse alors le bouton
	 *  devenir l'enfant direct du conteneur d'accueil.
	 */
	export let barre = true;
</script>

<div
	class="membre-card-actions"
	class:sans-barre={!barre}
	role="presentation"
	on:click|stopPropagation
>
	{#each gestes as g (g.libelle)}
		<button
			type="button"
			class="btn-icon"
			class:btn-icon-move={g.variante === 'deplacer'}
			class:btn-icon-star={g.variante === 'designer'}
			aria-label={g.libelle}
			title={g.libelle}
			disabled={g.desactive}
			on:click={g.onClic}>{g.glyphe}</button
		>
	{/each}
	{#if onEnregistrer && enEdition}
		<button
			type="button"
			class="btn-icon btn-icon-save"
			aria-label="Enregistrer ce membre"
			title="Enregistrer ce membre"
			disabled={enregistrement}
			on:click={onEnregistrer}
		>
			{#if enregistrement}…{:else}&#x1F4BE;{/if}
		</button>
	{:else if onModifier}
		<button
			type="button"
			class="btn-icon btn-icon-edit"
			aria-label="Modifier"
			title="Modifier"
			on:click={onModifier}><Icon name="pencil" size={13} /></button
		>
	{/if}
	{#if onSupprimer}
		<button
			type="button"
			class="btn-icon btn-icon-remove"
			aria-label="Supprimer"
			title="Supprimer"
			on:click={onSupprimer}><Icon name="trash-2" size={14} /></button
		>
	{/if}
</div>

<style>
	/*  🔴 Ces règles VOYAGENT avec le balisage qu'elles habillent. Laissées dans
	    la page, elles y seraient devenues orphelines — c'est la leçon de #796,
	    et `lint:css-orphelin` le dit à la compilation suivante. */
	.membre-card-actions {
		display: flex;
		gap: 0.3rem;
		align-items: center;
	}
	/*  Le crayon seul du bandeau : la barre s'efface, le bouton devient l'enfant
	    direct de la rangée d'accueil, qui a déjà son `gap`. */
	.sans-barre {
		display: contents;
	}

	/*  Ces boutons-icônes sont CERCLÉS et carrés (2 rem) : ils forment une barre
	    d'actions, là où la charte habille une icône nue. Bordure, fond, taille et
	    remplissage sont donc propres à cette barre ; le reste vient d'elle (#607).
	    Déclaré dans `check-charte-recomposee.regles.mjs`. */
	.btn-icon {
		width: 2rem;
		height: 2rem;
		border: 1px solid var(--color-border);
		background: var(--color-bg);
		font-size: 1rem;
		display: flex;
		align-items: center;
		justify-content: center;
		transition:
			background 0.15s,
			border-color 0.15s;
		padding: 0;
	}
	.btn-icon:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.btn-icon-save:hover:not(:disabled) {
		background: #dbeafe;
		border-color: #3b82f6;
	}
	/*  Le crayon est en couleur primaire — il est l'action principale de la rangée. */
	.btn-icon-edit {
		border-color: var(--color-primary);
		color: var(--color-primary);
	}
	.btn-icon-edit:hover {
		background: var(--color-primary);
		color: #fff;
	}
	.btn-icon-remove {
		border-color: var(--color-danger);
		color: var(--color-danger);
	}
	.btn-icon-remove:hover {
		background: var(--color-danger);
		color: #fff;
	}
	.btn-icon-move {
		border-color: var(--color-border);
		color: var(--color-text-muted);
		font-size: 0.85rem;
	}
	.btn-icon-move:hover:not(:disabled) {
		background: var(--color-bg-secondary, #f8f9fa);
		color: var(--color-text);
	}
	.btn-icon-move:disabled {
		opacity: 0.25;
		cursor: not-allowed;
	}
	.btn-icon-star {
		border-color: var(--color-accent, #c9983a);
		color: var(--color-accent, #c9983a);
		font-size: 0.875rem;
	}
	.btn-icon-star:hover {
		background: var(--color-accent, #c9983a);
		color: #fff;
	}
</style>
