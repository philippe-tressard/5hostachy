<script context="module" lang="ts">
	/**  Combien de modales tiennent actuellement le défilement. Vit dans le MODULE :
	 *   c'est un état du document, pas d'une instance. */
	let compteurVerrous = 0;
</script>

<!--
  Modale.svelte — le fond, le rôle, `Échap` et le verrou de défilement, UNE fois.

  ## Pourquoi (#561, 28/08/2026)

  Le fond de modale était écrit **vingt-deux fois** dans **treize** fichiers. Le
  relevé de #561 les classait « rien à faire », au motif que *« la fermeture
  clavier est `Échap`, et le rôle est déjà posé »*.

  🔴 **C'était vrai de quatre fichiers sur treize.** Vérifié en comptant, pas en
  lisant : `admin` (5 modales), `mon-lot` (6), `residence` (7), `espace-cs`,
  `prestataires`, `delegations` et `ModaleOrdreService` **n'avaient aucune
  fermeture clavier**. Dix-neuf modales sur vingt-deux ne se fermaient qu'à la
  souris — l'avertissement n'était donc pas un faux positif pour elles.

  C'est `standards/04` §3 : *vérifier le fait, pas le symptôme attendu*. Le ticket
  avait raison sur le principe et tort sur le compte, et suivre son classement
  aurait laissé dix-neuf défauts derrière une case cochée.

  ## Ce que ce composant porte, et que chaque copie devait retenir

  | | |
  |---|---|
  | `role="dialog"` + `aria-modal` + `aria-label` | 22 fois, dont plusieurs sans `aria-label` |
  | **`Échap` ferme** | 4 fois sur 13 |
  | fermeture au clic sur le FOND seul (`\|self`) | oui, mais désactivable — voir plus bas |
  | **verrou de défilement** | épars, et c'est le plus piégeux |

  ⚠️ **Le verrou de défilement est un état GLOBAL** (`standards/11` §12). Il se
  pose sur `<body>`, donc une modale qui oublie de le rendre fige la page entière
  jusqu'au rechargement — y compris si l'utilisateur navigue ailleurs sans fermer.
  C'est l'incident du 04/08/2026. Il est donc rendu depuis `onDestroy` **et** à
  chaque sortie, et la fonction est idempotente.

  ⚠️ **Un COMPTEUR, pas un booléen.** Deux modales peuvent se superposer (une
  confirmation par-dessus un formulaire) : la première qui se ferme rendrait le
  défilement alors que la seconde est encore là. Le compteur est le seul moyen de
  ne le rendre qu'à la dernière.

  ## `fermetureAuFond` — pourquoi c'est une option et pas un défaut

  `OngletPerimetres` la refuse explicitement : *« on saisit ici un libellé et une
  description, et un clic à côté effaçait tout sans prévenir »*. Un formulaire
  long ne se ferme pas au clic ; une confirmation, si. C'est une décision d'écran,
  pas une valeur par défaut à imposer.

  Usage :

      <Modale titre="Ajouter un plan" ouverte={showPlanForm} on:fermer={() => (showPlanForm = false)}>
        … contenu …
      </Modale>
-->
<script lang="ts">
	import { createEventDispatcher, onDestroy } from 'svelte';

	/** Nomme la boîte pour un lecteur d'écran. Obligatoire : sans lui, elle est « dialogue ». */
	export let titre: string;
	/** Classes de la boîte — `modal`, `modal-box`, `modal-sm`… selon l'écran. */
	export let classeBoite = 'modal';
	/** Style de la boîte, pour une largeur propre à l'écran. */
	export let styleBoite = '';
	/**
	 * Fermer au clic sur le FOND. À mettre à `false` sur un formulaire long :
	 * un clic à côté effacerait une saisie sans prévenir.
	 */
	export let fermetureAuFond = true;

	const dispatch = createEventDispatcher<{ fermer: void }>();

	//  🔴 Compteur PARTAGÉ par toutes les modales du site, et non un booléen par
	//  instance : deux modales superposées, et la première fermée rendrait le
	//  défilement pendant que la seconde est encore ouverte.
	let verrouPose = false;

	function poserVerrou() {
		if (verrouPose) return;
		verrouPose = true;
		compteurVerrous += 1;
		document.body.style.overflow = 'hidden';
	}

	function rendreVerrou() {
		if (!verrouPose) return;
		verrouPose = false;
		compteurVerrous = Math.max(0, compteurVerrous - 1);
		if (compteurVerrous === 0) document.body.style.overflow = '';
	}

	function fermer() {
		rendreVerrou();
		dispatch('fermer');
	}

	function auClavier(e: KeyboardEvent) {
		if (e.key === 'Escape') fermer();
	}

	//  ⚠️ Rendu AUSSI depuis `onDestroy` : l'utilisateur peut naviguer ailleurs
	//  sans jamais fermer, et la page d'arrivée resterait figée.
	onDestroy(rendreVerrou);

	//  Le verrou se pose au montage — le composant n'existe que lorsque l'écran
	//  l'ouvre (`{#if}`), donc il n'y a pas d'état « ouverte » à surveiller.
	if (typeof document !== 'undefined') poserVerrou();
</script>

<svelte:window on:keydown={auClavier} />

<div class="modal-overlay" role="presentation" on:click|self={() => fermetureAuFond && fermer()}>
	<div
		class={classeBoite}
		style={styleBoite}
		role="dialog"
		aria-modal="true"
		aria-label={titre}
		tabindex="-1"
	>
		<slot {fermer} />
	</div>
</div>
