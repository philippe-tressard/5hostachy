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

  ⚠️ Le composant porte son balisage **et** son style. C'est la leçon de
  `Pastille.svelte` (v2.67.11) : un style laissé dans la page hôte n'atteint pas
  le balisage d'un enfant, et le composant part nu en production.
-->
<script lang="ts">
	/** Le titre, sur une ou deux lignes. Au-delà, il est coupé — pas la carte. */
	export let titre: string;
	/** La date affichée à droite. Déjà formatée : ce composant ne connaît pas
	    `$lib/date`, et n'a donc aucun moyen d'en réinventer un format. */
	export let date = '';
</script>

<div class="entete">
	<div class="ec-titre">{titre}<slot name="titre-suffixe" /></div>
	<div class="ec-meta">
		<div class="ec-tags"><slot name="tags" /></div>
		<div class="ec-droite">
			{#if date}<span class="ec-date">{date}</span>{/if}
			<slot name="actions" />
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
