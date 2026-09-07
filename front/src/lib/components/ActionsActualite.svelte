<!--
  Les icônes d'action d'une carte d'actualité — extraites de la page le
  06/09/2026 (#796).

  ## Pourquoi ici, et pourquoi maintenant

  Le garde-fou de modularité a refusé que `actualites/+page.svelte` (571 lignes)
  grossisse de la conversion à `EtatListe`. La règle est « on découpe le fichier
  QUAND on y touche », et le refus dit **où** est le code : pas qu'il est trop
  long, mais qu'il est au mauvais endroit (#453).

  Ce bloc est le premier candidat évident — quarante lignes de balisage et de
  commentaires qui ne parlent que d'une chose : quelles icônes, dans quel ordre,
  pour qui.

  ## L'ORDRE DES ICÔNES

  Celui de la carte de ticket, désigné comme référence le 18/08/2026 :

      🔄 commenter · ✏️ modifier · ⚙️ options · 🗑️ supprimer

  Il était inversé ici, et deux cartes du même site ne se lisaient pas pareil.

  ⚠️ TROIS GESTES ONT ÉTÉ RETIRÉS le 18/08/2026, sur arbitrage :
    • ✉️ renvoyer l'e-mail au syndic/CS ;
    • 💬 renvoyer l'annonce sur le groupe WhatsApp ;
    • 📦 archiver.
  Les deux premiers rejouaient un envoi ; l'archivage devient sans objet, la
  publication n'ayant plus d'état « Résolu » à atteindre. L'archivage
  automatique, lui, reste : une publication bascule dans l'Historique au bout de
  son délai.

  ⚠️ Le bouton d'options n'existe QUE si la publication en porte au moins une :
  sur une actualité ordinaire il n'y a rien à faire évoluer, et **un bouton
  inerte se lit comme une panne**. Il montre les glyphes des options ACTIVES,
  dans l'ordre de la table — c'est ce qui le rend lisible sans l'ouvrir.
-->
<script lang="ts">
	import { isCS, isAdmin } from '$lib/stores/auth';
	import { optionsActives, libelleOptionsActives } from '$lib/options-publication';

	export let pub: any;
	/** La publication dont le formulaire de commentaire est ouvert, ou `null`. */
	export let commentaireOuvertId: number | null = null;
	/** Celle dont le formulaire de correction est ouvert, ou `null`. */
	export let editionOuverteId: number | null = null;
	/** Celle dont le panneau d'options est ouvert, ou `null`. */
	export let optionsOuvertesId: number | null = null;

	export let onCommenter: (pub: any) => void;
	export let onModifier: (pub: any) => void;
	export let onOptions: (pub: any) => void;
	export let onSupprimer: (pub: any) => void;
</script>

{#if $isCS}
	<button
		class="btn-icon"
		aria-pressed={commentaireOuvertId === pub.id}
		aria-label="Commenter"
		title="Commenter"
		on:click|stopPropagation={() => onCommenter(pub)}>&#x1F504;</button
	>
	<button
		class="btn-icon-edit"
		aria-pressed={editionOuverteId === pub.id}
		aria-label="Modifier"
		title="Modifier"
		on:click|stopPropagation={() => onModifier(pub)}>✏️</button
	>
	{#if optionsActives(pub).length > 0}
		{@const actives = optionsActives(pub)}
		<button
			class="btn-icon btn-icon-options"
			aria-pressed={optionsOuvertesId === pub.id}
			aria-label={libelleOptionsActives(pub)}
			title="{libelleOptionsActives(pub)} — cliquer pour les modifier"
			on:click|stopPropagation={() => onOptions(pub)}
			>{#each actives as o (o.cle)}<span class="opt-glyphe">{o.glyphe}</span>{/each}</button
		>
	{/if}
{/if}
{#if $isAdmin}
	<button
		class="btn-icon-danger"
		aria-label="Supprimer"
		title="Supprimer définitivement"
		on:click|stopPropagation={() => onSupprimer(pub)}>🗑️</button
	>
{/if}

<style>
	/*  🔴 Ces règles VOYAGENT avec le balisage qu'elles habillent (#796).
	    Laissées dans la page, elles y devenaient orphelines — svelte-check l'a
	    dit à la compilation suivante, et c'est la bonne façon d'échouer.

	    ⚠️ `min-width`/`min-height` à 44 px : c'est la cible tactile minimale,
	    et un bouton qui porte plusieurs glyphes doit s'élargir sans jamais
	    passer sous ce seuil. */
	.btn-icon-options {
		display: inline-flex;
		align-items: center;
		gap: 0.1rem;
		width: auto;
		min-width: 44px;
		min-height: 44px;
		padding: 0 0.35rem;
	}
	/*  Les glyphes se serrent quand ils sont quatre : à taille pleine, le bouton
	    dépasserait la rangée d'actions sur téléphone. */
	.btn-icon-options .opt-glyphe {
		font-size: 0.8em;
		line-height: 1;
	}
</style>
