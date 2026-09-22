<!--
  Une SECTION de formulaire : un intitulé, une séparation, et son contenu.

  POURQUOI CE COMPOSANT (16/08/2026). L'ordre des champs avait été fixé — Titre,
  champs spécifiques, Workflow, Périmètre, Destinataires, Description, Photos,
  Documents, Diffusion — mais **rien ne le montrait à l'écran** : les champs se
  suivaient sans respiration, et l'utilisateur a demandé le sous-titre manquant
  avant de constater qu'aucune section n'était nommée nulle part.

  « Sépare bien chaque section, il y a peut-être l'UX à revoir pour cela. »

  Ordonner ne suffit pas : une suite de dix champs sans repère se lit comme une
  liste, pas comme des groupes de décisions. Le titre dit CE QU'ON DÉCIDE ici
  (à qui ça s'adresse, comment ça se diffuse), le filet le sépare de ce qui suit.

  DEUX NIVEAUX DE MARQUAGE, volontairement discrets :
    • un intitulé en petites capitales — il structure sans concurrencer les
      libellés de champs, qui restent l'information principale ;
    • un filet fin au-dessus, sauf pour la première section : un trait avant le
      premier groupe séparerait la section de son propre titre de formulaire.

  ## Le titre EST le libellé quand la section n'a qu'un champ (16/08/2026)

  Première livraison, l'écran affichait :

      PÉRIMÈTRE
      Périmètre *                      [Copropriété entière]

  Le nom deux fois de suite, en deux typographies. Signalé par l'utilisateur,
  capture à l'appui, dès la mise en production. La redondance venait de ce que le
  champ portait déjà son intitulé (`PerimetrePicker`, `DestinatairePicker`,
  `FichiersUpload` le portent tous) et que la section en ajoutait un second.

  **Règle** : une section qui ne contient qu'UN champ ne répète pas son nom. Le
  titre de section devient le libellé — il porte l'astérisque du requis (`requis`)
  et le badge d'état (`badge`) —, et le champ n'écrit plus rien (`titre=""`).
  Les sections à PLUSIEURS champs (Détails, Clôture, Diffusion) gardent leur
  titre de groupe **et** les libellés de leurs champs : là, il n'y a pas
  redondance mais hiérarchie.

  ## L'accessibilité y gagne, et ce n'est pas un effet de bord

  `Périmètre *` était un `<div>` : décoratif pour un lecteur d'écran, qui
  annonçait donc un groupe de boutons sans nom. Le titre de section est
  désormais :
    • un vrai `<label for>` quand la section porte un contrôle labelable
      (`<select>`, `<input>`) — l'association est alors native ;
    • un `<h4 id>` sinon, l'appelant reliant son groupe par `aria-labelledby`.
      C'est le cas des pastilles et de l'éditeur riche, qui ne sont PAS des
      contrôles labelables : `for` n'y produirait aucune association, en silence.
-->
<script lang="ts">
	import Icon from './Icon.svelte';
	import EtoileRequis from './EtoileRequis.svelte';

	/** Intitulé de la section — ex. « Diffusion ». Vide : aucun titre, mais la
	    séparation reste, ce qui sert aux groupes évidents (le titre d'un objet). */
	export let titre = '';

	/** Icône du catalogue partagé (`$lib/icones-svg.json`), devant l’intitulé.
	    Les titres portaient des ÉMOJI ; l’en-tête de page, lui, prenait déjà ses
	    tracés dans le catalogue. Deux façons de désigner une section, dont une
	    qui dépend de la police du système (19/08/2026). */
	export let icone = '';

	/** Première section du formulaire : pas de filet au-dessus. */
	export let premiere = false;

	/** Ajoute l'astérisque des champs requis au titre. */
	export let requis = false;

	/**
	 *  Le champ de cette section est-il RENSEIGNÉ ? (#1121, 22/09/2026)
	 *
	 *  🔴 L'astérisque est rouge tant que le champ est vide : c'est l'état du
	 *  champ, plus une décoration. La section ne peut pas le deviner — « vide »
	 *  n'a pas le même sens pour un texte, une liste ou une date —, donc
	 *  l'appelant le dit.
	 *
	 *  ⚠️ Non renseigné **par défaut**, et c'est le choix prudent : une section
	 *  obligatoire dont personne ne dit l'état s'affiche comme un travail qui
	 *  reste à faire, jamais comme un travail fait.
	 */
	export let rempli = false;

	/** État résumé, à droite du titre — « Copropriété entière », « Tous les
	    résidents ». On lit ce qui est retenu sans dépiler les pastilles
	    (`ux-patterns` §9 quater). Vide : aucun badge. */
	export let badge = '';

	/** `id` du contrôle labelable unique de la section : le titre devient alors
	    un `<label for>`. Ne l'utiliser QUE pour `<select>`, `<input>`, `<textarea>` —
	    sur un `contenteditable` ou un groupe de boutons, `for` n'associe rien. */
	export let pour = '';

	/** `id` posé sur le titre, pour qu'un groupe s'y relie par `aria-labelledby`. */
	export let idTitre = '';

	/**
	 * **Repliée par défaut** — la section se réduit à son intitulé et à un
	 * résumé d'une ligne, cliquables (#1095).
	 *
	 * 🔴 La valeur vient de la DÉCLARATION (`section(ENTITE, id).pliee`), jamais
	 * d'un choix d'écran : la règle est *obligatoire → déplié · facultatif →
	 * plié*, et `lint:etats` la vérifie. Un écran qui plierait de son côté
	 * rouvrirait la divergence que le cadre existe pour fermer.
	 */
	export let pliable = false;

	/**
	 * Ce qu'on lit quand elle est pliée — « sans date », « en mon nom », « rien
	 * ne part à l'extérieur ».
	 *
	 * ⚠️ Il doit dire l'ÉTAT, jamais l'invitation : « sans date » et non
	 * « ajouter une date ». Une section pliée se lit comme une ligne de résumé,
	 * pas comme un bouton de plus.
	 */
	export let resume = '';

	/**
	 * 🔴 **La valeur diffère-t-elle du défaut ?** Elle gouverne TROIS choses.
	 *
	 * C'est la moitié non déclarative du cadre : elle dépend de ce que l'objet
	 * PORTE, pas de ce que la table dit.
	 *
	 * | | valeur par défaut | valeur modifiée |
	 * |---|---|---|
	 * | la section | peut être pliée | s'ouvre, et **ne se replie plus** |
	 * | sa pastille | verte | bleue |
	 *
	 * ⚠️ Elle s'appelait `valeurModifiee` — un nom qui décrivait son
	 * EFFET d'alors, quand elle n'en avait qu'un. Renommée le 22/09/2026 : un
	 * nom qui dit le geste n'est appelé que par ce geste, et les deux autres
	 * usages auraient été réécrits à côté (c'est ce qui est arrivé à
	 * `peut_commander`, #1028, vingt-six fois).
	 *
	 * 🔴 **Pliée ⟺ valeur par défaut**, et c'est un invariant, pas un effet :
	 * une section pliée qui cacherait une valeur saisie serait pire que pas de
	 * pliage du tout — on corrigerait un objet sans voir ce qu'il contient.
	 * C'est ce qui rend la vignette de droite TOUJOURS verte.
	 */
	export let valeurModifiee = false;

	let ouverteParLUtilisateur = false;
	/**  Se replier est possible — tant que la valeur est celle du défaut.
	 *
	 *   ⚠️ Arbitré à l'écran le 22/09/2026 : *« pour une section pliée qui est
	 *   dépliée, si on reclique sur le titre on la replie uniquement si on n'a
	 *   pas changé la valeur par défaut »*. En création comme en édition. */
	$: ouverte = !pliable || valeurModifiee || ouverteParLUtilisateur;
	$: replialbe = pliable && ouverte && !valeurModifiee;
	const idContenu = `sect-${Math.random().toString(36).slice(2, 9)}`;
</script>

<section class="section-formulaire" class:premiere>
	{#if pliable && !ouverte}
		<!--  🔴 Un vrai `<button>`, et non un `<div role="button">` : il faut le
		      clavier, le focus et l'annonce d'état sans rien réécrire. La cible
		      fait 44 px de haut (`standards/11` §10). -->
		<button
			type="button"
			class="section-pliee"
			aria-expanded="false"
			aria-controls={idContenu}
			on:click={() => (ouverteParLUtilisateur = true)}
		>
			<span class="section-titre section-titre-plie">
				{#if icone}<Icon name={icone} size={15} />{/if}<span class="section-titre-texte"
					>{titre}{#if requis}<EtoileRequis vide={!rempli} />{/if}</span
				>
			</span>
			<span class="badge badge-green section-resume">{resume || badge}</span>
			<svg
				class="section-chev"
				width="12"
				height="8"
				viewBox="0 0 12 8"
				fill="none"
				stroke="currentColor"
				stroke-width="1.6"
				aria-hidden="true"><path d="M1 1l5 5 5-5" /></svg
			>
		</button>
	{/if}
	{#if titre && ouverte}
		{#if pour}
			<label class="section-titre" for={pour} id={idTitre || undefined}>
				{#if icone}<Icon name={icone} size={15} />{/if}<span class="section-titre-texte"
					>{titre}{#if requis}<EtoileRequis vide={!rempli} />{/if}</span
				>
				{#if badge}<span
						class="badge section-badge"
						class:badge-green={!valeurModifiee}
						class:badge-bleu={valeurModifiee}>{badge}</span
					>{/if}
			</label>
		{:else}
			<h4 class="section-titre" id={idTitre || undefined}>
				{#if icone}<Icon name={icone} size={15} />{/if}<span class="section-titre-texte"
					>{titre}{#if requis}<EtoileRequis vide={!rempli} />{/if}</span
				>
				{#if badge}<span
						class="badge section-badge"
						class:badge-green={!valeurModifiee}
						class:badge-bleu={valeurModifiee}>{badge}</span
					>{/if}
				<!--  🔴 Replier est un GESTE, donc un `<button>` — et il n'existe que
				      quand il est permis. Une commande visible qui ne ferait rien dit
				      au doigt que le geste a échoué, jamais qu'il était interdit.

				      ⚠️ Il est absent d'un `<label for>` : un bouton à l'intérieur
				      d'un label vole le clic destiné au champ. Ces sections-là se
				      replient par leur résumé, comme avant. -->
				{#if replialbe}
					<button
						type="button"
						class="section-replier"
						aria-expanded="true"
						aria-controls={idContenu}
						aria-label="Replier la section {titre}"
						on:click={() => (ouverteParLUtilisateur = false)}
					>
						<svg
							width="12"
							height="8"
							viewBox="0 0 12 8"
							fill="none"
							stroke="currentColor"
							stroke-width="1.6"
							aria-hidden="true"><path d="M11 7L6 2 1 7" /></svg
						>
					</button>
				{/if}
			</h4>
		{/if}
	{/if}
	<div id={idContenu} hidden={!ouverte}>
		<!--  🔴 CACHÉ, jamais démonté. Un `{#if}` détruirait les champs, et avec
		      eux l'état interne des composants qu'ils portent — un éditeur riche,
		      une liste de pièces jointes en cours de téléversement. `hidden` les
		      retire aussi de l'ordre de tabulation, ce qu'un simple `display:none`
		      appliqué plus loin ne garantirait pas. -->
		<slot />
	</div>
</section>

<style>
	/*  ⚠️ L'écart sous le filet vaut la MOITIÉ de celui du dessus, et c'est
	    voulu : le trait appartient à la section qui commence, pas à celle qui
	    finit. À 0.9rem des deux côtés, le titre flottait au milieu et l'œil ne
	    savait plus à quel groupe il se rattachait — signalé à l'écran le
	    22/09/2026, capture à l'appui. */
	.section-formulaire {
		border-top: 1px solid var(--color-border);
		padding-top: 0.45rem;
		margin-top: 0.9rem;
	}
	/*  La première section n'est séparée de rien : le titre de la boîte
	    (`FormulaireCreation`) joue déjà ce rôle au-dessus d'elle. */
	.premiere {
		border-top: none;
		padding-top: 0;
		margin-top: 0;
	}
	/*  Petites capitales : l'intitulé de section se lit comme un repère de
	    structure. Il était gris ; il reprend la couleur du texte depuis qu'il
	    porte AUSSI le libellé du champ, l'astérisque du requis et le badge —
	    un intitulé de champ en gris clair se lit moins bien que ce qu'il nomme. */
	.section-titre {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		flex-wrap: wrap;
		margin: 0 0 0.6rem;
		font-size: 0.72rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--color-text);
	}
	/*  🔴 L'astérisque appartient au TEXTE, pas à la rangée (22/09/2026).

	    `.section-titre` est un conteneur flex avec `gap: .4rem` — l'écart qui
	    sépare proprement l'icône du libellé. Un nœud de texte nu y est un enfant
	    anonyme : l'astérisque, posée à côté de `{titre}`, recevait donc le même
	    écart et s'affichait « PÉRIMÈTRE * ». Le code l'écrivait collée, et le
	    composant la rendait collée : c'est la MISE EN PAGE qui les séparait.

	    ⚠️ Signalé à l'écran, capture à l'appui, le lendemain de sa livraison.
	    Aucune relecture de code ne pouvait le montrer — il fallait regarder. */
	.section-titre-texte {
		display: inline;
	}

	/*  Un `<label>` de section désigne un contrôle : il doit se cliquer. */
	label.section-titre {
		cursor: pointer;
	}
	/*  ── La section PLIÉE (#1095) ─────────────────────────────────────────
	    Une ligne : l'intitulé à gauche, ce qu'elle contient à droite, le chevron
	    au bout. Elle remplace le titre ET le contenu, et se lit d'un coup d'œil.

	    ⚠️ 44 px de haut : c'est une cible tactile, et c'est la seule commande de
	    la section quand elle est pliée (`standards/11` §10). */
	.section-pliee {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		width: 100%;
		min-height: 44px;
		box-sizing: border-box;
		padding: 0.35rem 0;
		border: none;
		background: none;
		font-family: inherit;
		text-align: left;
		cursor: pointer;
		color: var(--color-text);
	}
	/*  Le titre d'une section pliée ne porte pas sa marge du bas : il n'a rien
	    en dessous de lui. */
	.section-titre-plie {
		margin: 0;
		flex-shrink: 0;
	}
	/*  Le résumé pousse le chevron au bout et se coupe avant lui.

	    🔴 VIGNETTE VERTE, et non plus du texte gris (22/09/2026). Une section
	    pliée porte forcément la valeur par défaut — c'est l'invariant du cadre,
	    puisqu'une valeur modifiée l'ouvre et l'empêche de se refermer. Le vert
	    dit donc exactement ce qu'il y a à savoir : *rien n'a été touché ici*.
	    Il n'y a jamais de vignette bleue à droite, pour la même raison.

	    ⚠️ `max-width` plutôt qu'une largeur libre : un résumé long
	    (« rien ne part à l'extérieur ») doit se couper avant le chevron, et un
	    badge ne se coupe pas tout seul. */
	.section-resume {
		margin-left: auto;
		min-width: 0;
		max-width: 60%;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: 0.72rem;
		text-transform: none;
		letter-spacing: normal;
		font-weight: 600;
	}
	.section-chev {
		flex-shrink: 0;
		color: var(--color-text-muted);
	}
	/*  Le badge ne suit PAS les petites capitales du titre : c'est une valeur,
	    pas un intitulé — la lire en majuscules espacées la rendrait illisible. */
	.section-badge {
		font-size: 0.72rem;
		text-transform: none;
		letter-spacing: normal;
		font-weight: 600;
	}
	/*  🔴 Le bleu de la valeur MODIFIÉE (22/09/2026, arbitré à l'écran).

	    `--color-info` de la charte : il dit « ce n'est plus le défaut » sans
	    juger. L'ambre aurait dit « attention », l'or est déjà pris par le
	    repère du carnet d'entretien — deux sens sur le même écran.

	    ⚠️ Il n'existe qu'à côté du TITRE, jamais à droite : une valeur
	    modifiée ouvre la section, donc il n'y a plus de ligne pliée à décorer. */
	.badge-bleu {
		background: #e6f1fb;
		color: var(--color-info);
	}
	/*  Le chevron de repli : même poids visuel que celui du dépliage, et une
	    cible tactile qui tient (`standards/11` §10). */
	.section-replier {
		margin-left: auto;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-width: 44px;
		min-height: 44px;
		margin-top: -0.5rem;
		margin-bottom: -0.5rem;
		padding: 0;
		border: none;
		background: none;
		cursor: pointer;
		color: var(--color-text-muted);
	}
	.section-replier:hover {
		color: var(--color-text);
	}
</style>
