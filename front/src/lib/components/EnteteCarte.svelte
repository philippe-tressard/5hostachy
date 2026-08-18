<!--
  EnteteCarte.svelte — LE haut d'une carte de liste, écrit une fois.

  ## La règle, posée le 18/08/2026 et valable pour TOUT le site

  Une carte de liste se lit dans cet ordre, et il ne se discute pas :

      ┌─────────────────────────────────────────────┐
      │ Titre — sur 1 ou 2 lignes si nécessaire     │
      │ tags ················ date  actions  ›      │
      │ quatre lignes d'aperçu                      │
      └─────────────────────────────────────────────┘

  • le **titre** occupe sa ou ses propres lignes, rien ne le pousse — et
    **c'est LUI qui plie et déplie**, avec un survol qui le dit ;
  • en dessous, une ligne unique : **tags à gauche** (workflow, périmètre,
    confidentiel, auteur), **date puis actions puis chevron à droite** ;
  • puis l'aperçu, **quatre lignes**.

  ## Pourquoi (signalé à l'écran, capture à l'appui)

  Le titre partageait sa ligne avec les tags, la date et les icônes d'action.
  Sur un téléphone, **il disparaissait purement et simplement** : la ligne étant
  en `flex` avec `text-overflow: ellipsis`, les badges de largeur fixe gagnaient
  et le titre se réduisait à trois points. On lisait une liste d'actualités sans
  savoir de quoi elles parlaient.

  C'est **R1** au sens propre : la responsivité appartient au squelette, une
  seule fois pour toutes les pages. Chaque carte qui recomposait son en-tête
  avait sa propre façon de mal se replier.

  ## Le geste : le TITRE, et lui seul (18/08/2026)

  Trois gestes coexistaient : la carte entière (actualités, tickets,
  événements), le seul chevron (annonces), rien du tout ailleurs. Signalé à
  l'écran, unifié ici — le squelette porte le geste, comme il porte le repli.

  ⚠️ **La carte entière était le pire des trois**, malgré sa grande cible : elle
  interceptait la sélection de texte, et imposait un `stopPropagation` sur
  chaque bouton d'action — sans quoi un clic sur ✏️ dépliait la carte au même
  instant. Le titre supprime les deux à la fois.

  Un vrai `<button>` remplace `role="button" tabindex="0" on:keydown` : le
  clavier vient avec, sans rien réimplémenter.

  ⚠️ Le composant porte son balisage **et** son style. C'est la leçon de
  `Pastille.svelte` (v2.67.11) : un style laissé dans la page hôte n'atteint pas
  le balisage d'un enfant, et le composant part nu en production.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	/** Le titre, sur une ou deux lignes. Au-delà, il est coupé — pas la carte. */
	export let titre: string;
	/** La date affichée à droite. Déjà formatée : ce composant ne connaît pas
	    `$lib/date`, et n'a donc aucun moyen d'en réinventer un format. */
	export let date = '';
	/**  Le titre plie-t-il la carte ? `false` laisse un simple texte — une fiche
	 *   qui n'a rien à replier ne doit pas proposer un bouton qui ne fait rien.
	 *   Explicite, et non déduit d'un écouteur : Svelte ne sait pas dire si le
	 *   parent écoute `on:toggle`, et la déduction serait donc muette. */
	export let basculable = false;

	const dispatch = createEventDispatcher<{ toggle: void }>();
	const basculer = () => dispatch('toggle');
</script>

<div class="entete">
	<!--  Un `<button>` quand il plie, un `<div>` sinon. Pas de `role="button"`
	      sur un div : l'élément natif apporte le clavier, le focus visible et
	      l'annonce par les lecteurs d'écran, gratuitement et sans divergence. -->
	{#if basculable}
		<button type="button" class="ec-titre ec-titre-btn" on:click={basculer}>{titre}<slot name="titre-suffixe" /></button>
	{:else}
		<div class="ec-titre">{titre}<slot name="titre-suffixe" /></div>
	{/if}
	<div class="ec-meta">
		<div class="ec-tags"><slot name="tags" /></div>
		<div class="ec-droite">
			{#if date}<span class="ec-date">{date}</span>{/if}
			<slot name="actions" />
			<!--  Le chevron désigne le même geste que le titre : il doit donc l'exécuter.
			      Il reste un slot — chaque carte dessine le sien — mais c'est ce
			      composant qui lui donne son comportement, une fois. -->
			{#if basculable}
				<button type="button" class="ec-chevron-btn" on:click={basculer}
					aria-label="Déplier ou replier"><slot name="chevron" /></button>
			{:else}
				<slot name="chevron" />
			{/if}
		</div>
	</div>
</div>

<style>
	.entete { display: flex; flex-direction: column; gap: .3rem; padding: .6rem .9rem; }

	/*  Deux lignes au maximum : un titre long est coupé, il ne déforme pas la
	    carte et ne repousse pas ce qui suit. */
	.ec-titre {
		font-size: .9rem;
		font-weight: 500;
		line-height: 1.35;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	/*  Tags à gauche, date + actions à droite. `flex-wrap` : sur un écran étroit
	    la moitié droite passe à la ligne PLUTÔT QUE d'écraser les tags — c'est
	    exactement ce que l'ancienne disposition faisait au titre. */
	.ec-meta {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: .4rem .6rem;
		flex-wrap: wrap;
	}
	/*  🔴 LE GESTE. Le survol change la couleur ET souligne : la couleur seule
	    ne se voit pas d'un daltonien, et un site dont on ne sait pas où cliquer
	    se parcourt au hasard. Le `<button>` est remis à plat — il hérite du
	    titre, il ne se déguise pas en contrôle de formulaire. */
	.ec-titre-btn {
		appearance: none; background: none; border: 0; padding: 0; margin: 0;
		font: inherit; color: inherit; text-align: left; width: 100%;
		cursor: pointer;
	}
	.ec-titre-btn:hover { color: var(--color-primary); text-decoration: underline; }
	.ec-titre-btn:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px; border-radius: 3px; }

	/*  Le chevron : même geste, même curseur, aucune décoration propre. */
	.ec-chevron-btn {
		appearance: none; background: none; border: 0; padding: 0; margin: 0;
		font: inherit; color: inherit; cursor: pointer; display: inline-flex;
		align-items: center;
	}
	.ec-chevron-btn:hover { color: var(--color-primary); }
	.ec-chevron-btn:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px; border-radius: 3px; }

	.ec-tags { display: flex; align-items: center; gap: .35rem; flex-wrap: wrap; min-width: 0; }
	.ec-droite { display: flex; align-items: center; gap: .3rem; margin-left: auto; flex-shrink: 0; }
	.ec-date { font-size: .78rem; color: var(--color-text-muted); white-space: nowrap; }

	/*  Cible tactile sur les actions (socle 11 §10) : sous 480 px, les icônes
	    d'une carte étaient hautes de 26 px. */
	@media (max-width: 480px) {
		.entete { padding: .55rem .7rem; }
		.ec-droite :global(button) { min-height: 32px; min-width: 32px; }
	}
</style>
