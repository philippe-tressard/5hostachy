<!--
  Le cadre d'un formulaire de création ou de modification : la boîte, sa largeur,
  son titre. UNE seule écriture pour tout le site (#367).

  Avant, le produit offrait **trois paradigmes** pour la même intention — créer un
  objet :

    • une boîte dans la page       (actualités, sondages)
    • une modale                    (calendrier, prestataires — et deux largeurs)
    • une page dédiée               (nouveau ticket)

  Le paradigme retenu est **la boîte dans la page**, sur désignation de
  l'utilisateur : les actualités sont le modèle de référence. C'est aussi le seul
  qui n'escamote pas l'écran pendant la saisie, et celui que suivaient déjà les
  rubriques les plus utilisées.

  ⚠️ CE QUE CE COMPOSANT NE PORTE PAS : la commande d'annulation. Elle reste dans
  l'en-tête de page, où le bouton d'ouverture bascule en « ✕ Annuler » — c'est le
  modèle des actualités, et il est conservé tel quel. Le défaut signalé n'était
  pas son emplacement mais son **alignement** : il se posait au bord droit de
  l'ÉCRAN alors que la boîte s'arrête à 720 px. C'est `EntetePage` qui le corrige,
  via `alignerSaisie`.

  Ne pas ajouter de second bouton d'annulation ici : deux commandes pour un seul
  formulaire, c'est précisément ce que la modale du calendrier faisait — sa croix
  ET le bouton d'en-tête, ce dernier sous l'overlay, visible et inutilisable.
-->
<script lang="ts">
	import { onMount } from 'svelte';

	export let titre: string;
	/**  Le cadre visible — une carte blanche avec sa bordure.
	 *
	 *   `false` quand le formulaire s'ouvre DÉJÀ dans une carte : celle d'un
	 *   ticket, d'une actualité, d'un événement. Une carte dans une carte, c'est
	 *   deux bordures imbriquées pour un seul objet — signalé à l'écran (#425).
	 *
	 *   ⚠️ **Le TITRE suit le cadre** (corrigé le 18/08/2026, le soir même où il
	 *   avait été rendu systématique). Un formulaire encadré EST une carte : son
	 *   titre en est l'en-tête. Un formulaire qui s'ouvre dans la carte d'un objet
	 *   n'a pas à en poser un second — signalé à l'écran : « ce pseudo état
	 *   éloigne du titre ».
	 *
	 *   Le mode se lit alors sur **l'icône qui a ouvert le formulaire**, qui
	 *   s'inverse (`aria-pressed`, style dans `app.css`). C'est le bon endroit :
	 *   elle est déjà là, déjà regardée, et son inversion se lit sans être lue.
	 *   `titre` reste requis — il sert d'`aria-label` au formulaire, donc le mode
	 *   reste annoncé à qui ne voit pas l'icône. */
	export let encadre = true;

	/**  Le formulaire s'amène LUI-MÊME à l'écran quand il s'ouvre hors du champ
	 *   de vision.
	 *
	 *   🔴 Signalé à l'écran le 29/08/2026 : « le bouton Modifier ne marche pas…
	 *   ah non, je ne l'avais pas vu car tout en haut ». Le formulaire s'ouvrait
	 *   bien — en haut de la page, alors que le geste avait été fait sur une carte
	 *   plus bas. Rien ne bougeait sous les yeux : la commande semblait morte.
	 *
	 *   ⚠️ Le correctif vit ICI et non dans la page qui l'a révélé, parce que la
	 *   cause n'a rien de propre aux contrats : DOUZE écrans ouvrent leur
	 *   formulaire par ce composant, et le geste vient d'une liste dans presque
	 *   tous. Corriger `prestataires/+page.svelte` aurait laissé onze écrans avec
	 *   le même défaut — et la treizième ouverture l'aurait réintroduit.
	 *
	 *   ⚠️ On ne défile QUE si le formulaire n'est pas déjà visible. Un
	 *   formulaire qui s'ouvre sous les yeux (`encadre={false}`, dans la carte
	 *   d'un ticket) n'a pas à faire sauter la page : un défilement non demandé
	 *   sur un écran qui montrait déjà la bonne chose est lui-même un défaut.
	 *
	 *   ⚠️ Et `behavior: 'smooth'` est écarté quand l'utilisateur a demandé moins
	 *   d'animation (`prefers-reduced-motion`) — la destination est la même, seul
	 *   le trajet disparaît. */
	/**  Optionnel : ce qui identifie l'objet en cours d'édition.
	 *
	 *   Le montage ne couvre qu'un cas — le formulaire était fermé. Cliquer
	 *   « Modifier » sur une SECONDE carte alors que le formulaire est déjà
	 *   ouvert plus haut ne remonte rien, et le geste redevient muet. Les écrans
	 *   qui offrent ce geste depuis une liste passent donc l'identifiant : il
	 *   change, le formulaire se ramène à nouveau.
	 *
	 *   Ne pas le passer est légitime pour un formulaire qui ne s'ouvre que
	 *   depuis l'en-tête de page — il n'y a alors rien à distinguer. */
	export let cle: unknown = undefined;

	let cadre: HTMLElement;
	let monte = false;

	//  ⚠️ `monte` garde ce bloc muet AVANT le montage : sans lui, la réactivité
	//  s'exécuterait une première fois côté serveur, où `cadre` n'existe pas.
	$: if (monte && cle !== undefined) ramener(cle);

	function ramener(_cle: unknown) {
		if (!cadre || typeof window === 'undefined') return;
		const r = cadre.getBoundingClientRect();
		//  « Visible » = le HAUT du formulaire est dans la fenêtre. Exiger qu'il
		//  tienne en entier ferait défiler sur tout formulaire long, y compris
		//  celui qu'on regarde déjà.
		if (r.top >= 0 && r.top <= window.innerHeight - 80) return;
		const doux = !window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
		cadre.scrollIntoView({ behavior: doux ? 'smooth' : 'auto', block: 'start' });
	}

	onMount(() => {
		monte = true;
		ramener(cle);
	});
</script>

<!--  `aria-label` porte le titre dans TOUS les cas : ce qui disparaît est le
      titre VISIBLE, pas l'information. Un lecteur d'écran continue d'annoncer
      « Modifier le commentaire » en entrant dans le formulaire. -->
<div class="formulaire-creation largeur-saisie" class:card={encadre}
	bind:this={cadre} role="group" aria-label={titre}>
	{#if encadre}<h2>{titre}</h2>{/if}
	<slot />
</div>

<style>
	.formulaire-creation { margin-bottom: 1.5rem; scroll-margin-top: 5rem; }
	.formulaire-creation h2 { font-size: 1rem; font-weight: 600; margin: 0 0 1rem; }
</style>
