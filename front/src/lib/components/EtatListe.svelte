<!--
  **Les trois états d'une liste** : en cours de chargement · **échec** · vide.

  ## Pourquoi ce composant (#519)

  Le 19/08/2026, l'utilisateur signale : *« J'avais un sondage non terminé qui a
  disparu ! »* et *« Il y avait 3 annonces non vendues ! à récupérer »*. Rien
  n'était perdu — deux sondages et trois annonces dormaient en base pendant que
  l'écran affichait « Aucun sondage » et « Aucune annonce ».

  La cause tenait en trois caractères : `.catch(() => [])`. Toute erreur — session
  expirée, 500, réseau — devenait un tableau vide, et l'écran rendait alors
  **exactement la même chose** que s'il n'y avait rien.

  🔴 **Une sortie vide n'est pas un constat** (`standards/04`). Cette règle était
  écrite pour les contrôles d'infrastructure ; elle vaut mot pour mot pour une
  liste. Un écran qui affirme une absence qu'il n'a pas constatée provoque la
  réaction qu'une perte réelle provoquerait — ici, une demande de restauration,
  avec au bout le risque d'écraser des données saines.

  ## Ce qu'il impose

  L'ordre : **l'échec passe AVANT le vide**. Et l'appelant doit fournir `erreur`,
  donc se poser la question — c'est le composant qui rend l'oubli visible.

  ## Pourquoi il vit ici et non dans une page

  Extrait de `sondages/+page.svelte` quand le garde-fou de modularité a refusé de
  la laisser grossir (494 → 534 lignes). Le refus disait vrai : ces trois états
  n'appartiennent pas à un écran, **tout écran qui charge une liste en a besoin**
  — et #515 va en demander sur sept pages. Le refus signalait un problème de
  placement, pas de taille (#453).
-->
<script lang="ts">
	/** Vrai tant que la donnée n'est pas arrivée. */
	export let chargement = false;
	/**  Non vide = on n'a PAS pu regarder. Distinct de « on a regardé, il n'y a
	 *   rien » — c'est toute la raison d'être de ce composant. */
	export let erreur = '';
	/** Vrai quand la liste est chargée ET réellement vide. */
	export let vide = false;
	export let titreErreur = 'Impossible d’afficher cette liste';
	export let titreVide = 'Aucun élément';
	export let messageVide = '';
	export let messageChargement = 'Chargement…';
	/**  Rendu d'une SEULE ligne au lieu du bloc `.empty-state` (#522).
	 *
	 *   ⚠️ Ce n'est pas un second pattern, c'est une **variante déclarée du
	 *   même** : mêmes trois états, même ordre, même obligation de fournir
	 *   `erreur`. Ce qui change est la place occupée.
	 *
	 *   Elle existe parce que la page Résidence porte CINQ sections courtes
	 *   (plans, règlements, comptes-rendus, règles, diagnostics) qui annoncent
	 *   leur vide en une ligne discrète. Cinq blocs `.empty-state` à la place
	 *   auraient transformé une page de références en une page d'avertissements
	 *   — et un écran qui crie partout ne se lit plus nulle part.
	 *
	 *   🔴 En mode compact, l'ÉCHEC reste visuellement distinct du vide (couleur
	 *   d'alerte) : c'est toute la raison d'être du composant, et l'économie de
	 *   place ne doit jamais la reprendre. */
	export let compact = false;
</script>

{#if chargement}
	<p class="etat-chargement">{messageChargement}</p>
{:else if erreur}
	<!--  🔴 AVANT le vide : dire « aucun » quand on n'a pas pu regarder, c'est
	      affirmer une absence qu'on n'a pas constatée. -->
	{#if compact}
		<p class="etat-erreur">{erreur}</p>
	{:else}
		<div class="empty-state">
			<h3>{titreErreur}</h3>
			<p>{erreur}</p>
		</div>
	{/if}
{:else if vide}
	{#if compact}
		<p class="etat-vide">{messageVide || titreVide}</p>
	{:else}
		<div class="empty-state">
			<h3>{titreVide}</h3>
			{#if messageVide}<p>{messageVide}</p>{/if}
		</div>
	{/if}
{:else}
	<slot />
{/if}

<style>
	.etat-chargement {
		color: var(--color-text-muted);
	}
	/*  Reprend `.empty-msg` de la page Résidence, d'où la variante est née : le
	    vide y était déjà rendu ainsi, et le convertir aurait changé l'aspect de
	    cinq sections pour un lot qui ne parle pas d'aspect. */
	.etat-vide {
		font-size: 0.875rem;
		color: var(--color-text-muted);
		padding: 0.5rem 0;
	}
	/*  🔴 L'échec ne ressemble PAS au vide, même en compact. Couleur d'alerte du
	    site — la même que `.alert-warning`, sans le cadre qui ferait un bloc. */
	.etat-erreur {
		font-size: 0.875rem;
		color: #b07d1e;
		padding: 0.5rem 0;
		font-weight: 500;
	}
</style>
