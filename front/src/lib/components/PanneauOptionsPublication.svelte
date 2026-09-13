<!--
  PanneauOptionsPublication.svelte — les options d'une actualité, modifiables
  seules, sans passer par l'édition ni par un commentaire.

  Sorti d'`actualites/+page.svelte` le 05/09/2026, sur refus du contrôle de
  modularité : la page accueillait les mêmes options DANS le formulaire de
  commentaire (demande de l'utilisateur), et dépassait son plafond.

  ⚠️ **Deux chemins mènent désormais aux mêmes quatre options** : ce panneau, et
  la section 2 du formulaire de commentaire. C'est un écart connu au principe
  « un geste, un endroit » (`ux-patterns` §10 bis) — ils ne répondent pas tout à
  fait à la même question (« je corrige une option » contre « je commente, et
  j'en profite pour revalider le ciblage »), mais s'il faut n'en garder qu'un,
  c'est celui-ci qui part : le formulaire de commentaire fait les deux.

  Le composant ne décide de rien : la page tient la copie de travail et appelle
  le serveur. Il montre, et dit ce qu'on a cliqué.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import OptionsPublication from '$lib/components/OptionsPublication.svelte';
	import PiedFormulaire from '$lib/components/PiedFormulaire.svelte';
	import type { CleOptionPublication } from '$lib/options-publication';

	/**  Le nom de l'objet décrit — il entre dans les libellés qui le nomment
	 *   (« Visibilité du **ticket** au seul conseil syndical »). */
	export let objet = 'publication';
	/**  Les options RENDUES : un événement n'a que l'épinglage, un ticket en a
	 *   quatre dont une verrouillée. C'est l'appelant qui sait. */
	export let optionsRendues: CleOptionPublication[] = [
		'epingle',
		'urgente',
		'brouillon',
		'confidentiel',
	];
	/** Le périmètre visé, qui décide si « Confidentiel » a un sens. */
	export let perimetreCible: string[] = [];
	/** L'objet était-il DÉJÀ épinglé ? (évite un double comptage) */
	export let dejaEpingle = false;
	/** 🔒 Motif pour lequel l'objet est TOUJOURS restreint — relayé tel quel. */
	export let confidentielAcquis = '';
	/** 🔒 Motif pour lequel l'épinglage est impossible — relayé tel quel. */
	export let epingleInterdit = '';
	/** La copie de travail, tenue par la page : on n'écrit qu'après le serveur. */
	export let options: {
		epingle: boolean;
		urgente: boolean;
		brouillon: boolean;
		confidentiel: boolean;
	};
	export let enregistrement = false;

	const dispatch = createEventDispatcher<{ enregistrer: void; annuler: void }>();
</script>

<!--  ── Options de publication ──
      LE MÊME composant qu'à la création et à l'édition
      (`OptionsPublication`, section 2 du cadre #430) : ni copie, ni
      variante. Il porte déjà la règle « Confidentiel exige un
      périmètre restreint », qu'un panneau réécrit n'aurait pas eue.
      `role="presentation"` : ce conteneur n'est qu'un relais, il
      arrête la propagation pour que cocher ne referme pas la carte. -->
<div class="options-form" role="presentation" on:click|stopPropagation on:keydown|stopPropagation>
	<h4 class="options-titre">Options de publication</h4>
	<OptionsPublication
		{objet}
		options={optionsRendues}
		{perimetreCible}
		{dejaEpingle}
		{confidentielAcquis}
		{epingleInterdit}
		bind:epingle={options.epingle}
		bind:urgente={options.urgente}
		bind:brouillon={options.brouillon}
		bind:confidentiel={options.confidentiel}
	/>
	<!--  🔴 `PiedFormulaire`, et non deux boutons écrits ici (12/09/2026, signalé
	      à l'écran). Cette rangée était une **dixième copie** du pied que #822 a
	      supprimé neuf fois — et elle avait déjà divergé sur les deux points qui
	      se voient : « Enregistrer » AVANT « Annuler », et un alignement à GAUCHE
	      faute de porter `.form-actions`.

	      ⚠️ C'est précisément parce qu'elle portait sa propre classe
	      (`.options-actions`) qu'aucun contrôle ne l'a vue. `lint:pied-formulaire`
	      cherche désormais la paire quelle que soit la classe de la rangée. -->
	<PiedFormulaire
		enCours={enregistrement}
		soumission={false}
		petit
		on:enregistre={() => dispatch('enregistrer')}
		on:annule={() => dispatch('annuler')}
	/>
</div>

<style>
	.options-form {
		padding: 0.5rem 0;
	}
	.options-titre {
		margin: 0 0 0.6rem;
		font-size: 0.9rem;
		font-weight: 600;
	}
	/*  ⚠️ `.options-actions` et sa règle mobile sont MONTÉES dans `.form-actions`
	    (`styles/normes.css`, 12/09/2026) : elles ne servaient qu'ici, ce qui
	    faisait de ce panneau la seule rangée d'actions correcte au doigt. La
	    règle la plus utile était la moins déployée. */
</style>
