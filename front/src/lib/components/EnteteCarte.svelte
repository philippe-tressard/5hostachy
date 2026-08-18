<!--
  EnteteCarte.svelte — LE haut d'une carte de liste, écrit une fois.

  ## La règle, posée le 18/08/2026 et valable pour TOUT le site

  Une carte de liste se lit dans cet ordre, et il ne se discute pas :

      ┌─────────────────────────────────────────────┐
      │ Titre — sur 1 ou 2 lignes si nécessaire     │
      │ tags ················ date  actions  ›      │
      │ quatre lignes d'aperçu                      │
      └─────────────────────────────────────────────┘

  • le **titre** occupe sa ou ses propres lignes, et rien ne le pousse ;
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

  ## Le geste est ASYMÉTRIQUE (18/08/2026)

  **Repliée**, toute la carte se clique pour déplier, avec un changement de fond
  au survol — la logique du fil d'activité, désignée comme référence.

  **Dépliée**, seul le TITRE replie : le corps doit pouvoir se lire, se
  sélectionner et se copier sans se refermer. C'est ce composant qui porte cette
  seconde moitié — d'où le `<button>` sur le titre.

  🔴 L'asymétrie **résout** le conflit que j'avais cru insoluble : une grande
  cible pour ouvrir (au doigt), aucune cible parasite une fois ouvert. Les deux
  exigences ne se contredisent pas, elles ne portent pas sur le même état.

  Le titre est un vrai `<button>` : il porte le clavier dans les deux sens. Le
  conteneur n'est donc pas interactif, et rien n'est imbriqué.

  ⚠️ J'ai d'abord fait l'inverse, dans ce fichier même, en lisant « tout le titre
  est sélectable » comme « le titre, et lui seul ». L'argument avancé — la carte
  entière intercepte la sélection de texte — était réel mais hors sujet : le
  CORPS déplié arrête déjà la propagation, et la zone repliée n'a rien à
  sélectionner. Une objection juste dans l'absolu peut être fausse ici.
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
	/**  Le titre bascule-t-il la carte ? `false` laisse un simple texte — une
	 *   fiche qui n'a rien à replier ne propose pas un bouton inerte.
	 *   Explicite, et non déduit d'un écouteur : Svelte ne sait pas dire si le
	 *   parent écoute `on:toggle`, et la déduction serait muette. */
	export let basculable = false;

	const dispatch = createEventDispatcher<{ toggle: void }>();
</script>

<div class="entete">
	<!--  Un vrai `<button>` : il porte le clavier dans les deux sens, et c'est la
	      SEULE cible quand la carte est dépliée. `stopPropagation` l'isole du
	      conteneur, qui ne déplie que depuis l'état replié. -->
	{#if basculable}
		<button type="button" class="ec-titre ec-titre-btn"
			on:click|stopPropagation={() => dispatch('toggle')}>{titre}<slot name="titre-suffixe" /></button>
	{:else}
		<div class="ec-titre">{titre}<slot name="titre-suffixe" /></div>
	{/if}
	<div class="ec-meta">
		<div class="ec-tags"><slot name="tags" /></div>
		<div class="ec-droite">
			{#if date}<span class="ec-date">{date}</span>{/if}
			<slot name="actions" />
			<!--  Le chevron n'est qu'un INDICATEUR : c'est la carte entière qui reçoit
			      le clic. Lui donner son propre bouton ferait un élément interactif
			      imbriqué dans un autre — invalide, et le clavier s'y perdrait. -->
			<slot name="chevron" />
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

	/*  Tags à gauche, date + actions à droite — sur UNE seule ligne.

	    ⚠️ `flex-wrap: wrap` a été retiré le 18/08/2026 : signalé à l'écran, « sur
	    smartphone l'état est en 2 lignes ». Le repli protégeait les tags d'un
	    écrasement — un souci hérité de l'époque où le titre partageait cette
	    ligne. Le titre ayant la sienne, il ne reste plus rien à protéger, et deux
	    lignes de méta sous une carte repliée coûtent plus qu'elles ne rapportent.

	    Les tags DÉFILENT horizontalement plutôt que de se replier : rien n'est
	    perdu, la date et les actions restent ancrées à droite, et la carte garde
	    sa hauteur. Même parti que la barre de filtres de /prestataires. */
	.ec-meta {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: .4rem .6rem;
		flex-wrap: nowrap;
	}
	/*  Le titre est un bouton, remis à plat : il hérite de son propre style et ne
	    se déguise pas en contrôle de formulaire. Le survol le souligne — c'est le
	    seul repère qui dise « ceci referme », une fois la carte ouverte. */
	.ec-titre-btn {
		appearance: none; background: none; border: 0; padding: 0; margin: 0;
		font: inherit; color: inherit; text-align: left; width: 100%;
		cursor: pointer;
	}
	.ec-titre-btn:hover { text-decoration: underline; }
	.ec-titre-btn:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px; border-radius: 3px; }

	.ec-tags {
		display: flex; align-items: center; gap: .35rem;
		flex-wrap: nowrap; min-width: 0;
		/*  Barre de défilement masquée : elle apparaîtrait sous chaque carte et
		    ferait du bruit pour trois badges. */
		overflow-x: auto; scrollbar-width: none;
	}
	.ec-tags::-webkit-scrollbar { display: none; }
	/*  Les badges ne se compriment pas : un « Confidentiel » réduit à « Confid… »
	    ne dit plus rien, alors qu'un badge sorti du cadre se ramène d'un geste. */
	.ec-tags :global(> *) { flex-shrink: 0; }
	.ec-droite { display: flex; align-items: center; gap: .3rem; margin-left: auto; flex-shrink: 0; }
	.ec-date { font-size: .78rem; color: var(--color-text-muted); white-space: nowrap; }

	/*  Cible tactile sur les actions (socle 11 §10) : sous 480 px, les icônes
	    d'une carte étaient hautes de 26 px. */
	@media (max-width: 480px) {
		.entete { padding: .55rem .7rem; }
		.ec-droite :global(button) { min-height: 32px; min-width: 32px; }
	}
</style>
