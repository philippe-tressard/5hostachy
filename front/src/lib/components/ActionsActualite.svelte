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
	import { SUITE } from '$lib/gestes';
	import { isCS, isAdmin } from '$lib/stores/auth';
	import BoutonOptions from './BoutonOptions.svelte';

	export let pub: any;
	/** La publication dont le formulaire de commentaire est ouvert, ou `null`. */
	export let commentaireOuvertId: number | null = null;
	/** Celle dont le formulaire de correction est ouvert, ou `null`. */
	export let editionOuverteId: number | null = null;
	/** Celle dont le panneau d'options est ouvert, ou `null`. */
	export let optionsOuvertesId: number | null = null;

	export let onCommenter: (pub: any) => void;
	/**
	 * **Cette information demande un suivi** — promouvoir l'actualité en
	 * affaire (#1094).
	 *
	 * ⚠️ Le geste est irréversible et l'actualité DISPARAÎT du fil : l'écran
	 * qui le branche doit donc demander confirmation avant d'appeler.
	 */
	export let onPromouvoir: (pub: any) => void;
	export let onModifier: (pub: any) => void;
	export let onOptions: (pub: any) => void;
	export let onSupprimer: (pub: any) => void;
</script>

{#if $isCS}
	<button
		class="btn-icon"
		aria-pressed={commentaireOuvertId === pub.id}
		aria-label={SUITE.libelle}
		title={SUITE.libelle}
		on:click|stopPropagation={() => onCommenter(pub)}>&#x1F504;</button
	>
	<button
		class="btn-icon-edit"
		aria-pressed={editionOuverteId === pub.id}
		aria-label="Modifier"
		title="Modifier"
		on:click|stopPropagation={() => onModifier(pub)}>✏️</button
	>
	<!--  🔴 « Suivre cette affaire » (#1094) — le geste qui évite de TOUT
	      RETAPER quand une actualité dérape. Titre, description, pièces jointes
	      et périmètre suivent ; on ajoute un statut.

	      ⚠️ Il n'apparaît pas sur une actualité déjà close : promouvoir ce qui
	      est terminé n'ouvrirait un suivi sur rien. -->
	{#if pub.statut !== 'resolu' && pub.statut !== 'annule'}
		<!--  🔴 « cette ACTUALITÉ », pas « cette affaire » : le bouton agit SUR une
		      actualité pour en faire une affaire. Le renommage mécanique du 21/09
		      avait remplacé le mot des deux côtés de la phrase, qui disait alors
		      « Suivre cette affaire — en faire une affaire ». -->
		<button
			class="btn-icon"
			aria-label="Suivre cette actualité — en faire une affaire"
			title="Suivre cette actualité"
			on:click|stopPropagation={() => onPromouvoir(pub)}>&#x1F3AF;</button
		>
	{/if}
	<!--  Le bouton vit dans `BoutonOptions` depuis le 12/09/2026 : tickets et
	      événements portent les mêmes options, et le recopier chez eux aurait
	      recopié aussi ses règles d'accessibilité et sa cible tactile. -->
	<BoutonOptions
		objet={pub}
		ouvert={optionsOuvertesId === pub.id}
		onOuvrir={() => onOptions(pub)}
	/>
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
</style>
