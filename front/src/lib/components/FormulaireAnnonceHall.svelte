<!--
  FormulaireAnnonceHall.svelte — la saisie d'une affiche de hall.

  ## Pourquoi ce composant (18/08/2026)

  Extrait d'`espace-cs/+page.svelte` — 3 341 lignes, le pire cas du dépôt (#453).
  Le garde-fou de modularité a refusé que le fichier grossisse pour recevoir deux
  commentaires d'exception, et il avait raison : **tous les autres formulaires du
  site sont des composants** (`FormulaireTicket`, `FormulaireEvenement`,
  `FormulaireSondage`, `FormulaireIdee`, `FormulaireAnnonce`). Celui-ci était le
  dernier écrit à même une page.

  ⚠️ La tentation était de raccourcir les commentaires jusqu'à repasser sous le
  seuil. C'est ce que la règle interdit explicitement — *raboter : ❌ jamais*. Le
  refus disait où le code devait aller, pas combien de lignes il pouvait faire.

  ## Ce qu'il décide, et ce qu'il ne décide pas

  Il rend la saisie et rien d'autre. La page garde l'état (`ahTitre`, `ahMessage`…),
  les appels d'API et la décision d'envoyer — c'est le **pattern A**, celui de
  `FormulaireEvenement` : l'état vit dans la page, le composant rend.

  ## L'ordre des sections, et sa seule exception

  Le cadre #430 : 1 titre · 2 format · 4 périmètre · 6 message · 7 photos. Cet
  écran rendait *titre → message → périmètre → format*, soit 1 → 6 → 4 → 2.

  🔴 **Une exception, demandée à l'écran** : « Pré-remplir depuis une actualité »
  reste **avant** le titre. Ce n'est pas une section du cadre — c'est un raccourci
  qui **remplit** le formulaire. Le placer après le titre reviendrait à proposer de
  réécrire ce qu'on vient de saisir.
-->
<script lang="ts">
	import RichEditor from '$lib/components/RichEditor.svelte';
	import Pastille from '$lib/components/Pastille.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import PerimetrePicker from '$lib/components/PerimetrePicker.svelte';
	import FichiersUpload from '$lib/components/FichiersUpload.svelte';
	import { fmtDateShort } from '$lib/date';
	import type { Publication } from '$lib/api';

	type AhFormat = 'auto' | 'a4' | 'a5' | 'a6' | 'a7' | 'a8';

	//  Liés en deux sens : la page porte leur cycle de vie.
	export let titre = '';
	export let message = '';
	export let perimetre: string[] = [];
	export let format: AhFormat = 'auto';
	export let photos: string[] = [];

	/** Actualités proposées au pré-remplissage. Vide : le bloc ne s'affiche pas. */
	export let pubs: Publication[] = [];
	export let sourceId: number | '' = '';
	export let formats: { val: AhFormat; label: string }[] = [];
	export let maxPhotos = 2;

	//  ⚠️ Calculs de PRÉSENTATION, remontés de la page (18/08/2026) : combien de
	//  caractères, et quel format en découle. Ils ne servent qu'à l'aide affichée
	//  sous les pastilles — la page, elle, garde la VALIDITÉ, qui commande son
	//  bouton. Le format retenu reste celui que l'API calcule ; ceci n'est qu'une
	//  prévision, et c'est écrit dans l'aide.
	const SEUILS: [string, number][] = [
		['A8', 70],
		['A7', 140],
		['A6', 300],
		['A5', 600],
	];
	const ORDRE = ['A4', 'A5', 'A6', 'A7', 'A8'];
	const formatMinPhotos = 'A5';

	$: longueur = message.replace(/<[^>]*>/g, '').length + titre.trim().length;
	$: formatPrevu = (() => {
		if (format !== 'auto') return format.toUpperCase();
		const trouve = SEUILS.find(([, seuil]) => longueur <= seuil);
		const fmt = trouve ? trouve[0] : 'A4';
		return photos.length && ORDRE.indexOf(fmt) > ORDRE.indexOf(formatMinPhotos)
			? formatMinPhotos
			: fmt;
	})();

	/**  9. DIFFUSION — l'envoi de l'affiche au conseil syndical.
	 *
	 *   ⚠️ Décoché par défaut, et le SERVEUR le consomme (`envoyer_cs`) : le cadre
	 *   interdit d'ouvrir un champ que le serveur ignorerait — la case promettrait
	 *   un envoi qui n'a pas lieu, ce qui est pire qu'une case absente. */
	export let envoyerCs = false;

	export let valide = false;
	export let saving = false;
	export let apercuLoading = false;

	/** La page garde les appels d'API : le composant ne fait que les déclencher. */
	export let onPrefill: (pubId: number | '') => void;
	export let onApercu: () => void;
	export let onCreer: () => void;
	export let onUpload: (f: File) => Promise<string>;
	export let onPhotosChange: () => void;
</script>

<!--  L'EXCEPTION : le pré-remplissage vient avant le titre. Voir l'en-tête. -->
{#if pubs.length}
	<div class="field">
		<label for="ah-source">Pré-remplir depuis une actualité</label>
		<select
			id="ah-source"
			value={sourceId}
			on:change={(e) =>
				onPrefill(
					(e.currentTarget as HTMLSelectElement).value === ''
						? ''
						: Number((e.currentTarget as HTMLSelectElement).value),
				)}
		>
			<option value="">— Saisie libre —</option>
			{#each pubs as pub}
				<option value={pub.id}>{fmtDateShort(pub.cree_le)} · {pub.titre}</option>
			{/each}
		</select>
	</div>
	<p class="ah-aide">
		Reprend le titre, le contenu, le périmètre et l'image de l'actualité. Tout reste modifiable
		ci-dessous : l'affiche est indépendante de l'actualité d'origine.
	</p>
	<hr class="ah-separateur" />
{/if}

<!--  1. Titre. `SectionFormulaire` porte le filet discret qui sépare les
      sections — celui de Tickets, demandé à l'écran le 18/08/2026. La section
      n'ayant qu'UN champ, son titre EST le libellé du champ (R3). -->
<SectionFormulaire premiere titre="Titre" requis pour="ah-titre">
	<div class="field champ-large">
		<input
			id="ah-titre"
			type="text"
			bind:value={titre}
			maxlength="120"
			placeholder="Ex : Coupure d'eau — mardi 4 août"
		/>
	</div>
</SectionFormulaire>

<!--  2. Champs spécifiques : le format de l'affiche. -->
<SectionFormulaire titre="Format">
	<!--  🔴 `Pastille`, PAS `<button class="pill">` (18/08/2026, signalé à l'écran :
	      « le format est illisible »). En sortant ce balisage de la page, j'y ai laissé
	      `.pill` et `.pill-active` : les pastilles sont parties NUES en production —
	      des rectangles collés, « Auto|A4|A5|A6 ».
	
	      C'est mot pour mot la régression v2.67.11, celle que ce dépôt cite dans une
	      dizaine de commentaires, et je l'ai commise en déplaçant du balisage. Écrire
	      la règle ne suffit pas : seul un composant qui porte son style AVEC son
	      balisage l'empêche, et c'est très exactement la raison d'être de `Pastille`. -->
	<div class="perimetre-pills">
		{#each formats as f}
			<Pastille petite active={format === f.val} on:click={() => (format = f.val)}
				>{f.label}</Pastille
			>
		{/each}
	</div>
	<p class="ah-aide">
		{#if format === 'auto'}
			Le plus petit format qui accueille le texte est retenu, pour occuper le moins de place
			possible dans l'afficheur du hall. Sous l'A4, des pointillés de découpe sont tracés sur
			l'affiche.
		{:else}
			Format imposé — le message sera mis en page en {format.toUpperCase()}.
		{/if}
		<strong>Prévu : {formatPrevu}</strong> ({longueur} caractère{longueur > 1 ? 's' : ''} — titre et message)
	</p>
</SectionFormulaire>

<SectionFormulaire>
	<!--  4. Périmètre. -->
	<PerimetrePicker titre="Périmètre d'affichage" bind:value={perimetre} />
	<!--  ⚠️ CETTE AIDE A MENTI DEUX FOIS EN UN JOUR, dans les deux sens, et c'est
	      instructif : elle annonçait d'abord un envoi automatique (vrai jusqu'au matin
	      du 18/08), puis « aucun message n'est envoyé » — écrit quand l'envoi a été
	      retiré, et devenu faux **quelques heures plus tard** avec la section
	      Diffusion.
	
	      Une aide qui décrit le COMPORTEMENT d'un autre champ vieillit à chaque fois
	      que ce champ bouge, sans que rien ne le signale. Elle ne dit donc plus que ce
	      dont elle répond : à quoi sert le périmètre. L'envoi se lit là où il se
	      décide — dans la section Diffusion, qui porte sa propre aide. -->
	<p class="ah-aide">Imprimé sur l'affiche : il dit où elle doit être posée.</p>
</SectionFormulaire>

<!--  6. Description — ici, le message affiché. -->
<SectionFormulaire titre="Message" requis idTitre="ah-message-titre">
	<RichEditor bind:value={message} placeholder="Rédigez l'annonce telle qu'elle sera affichée…" />
</SectionFormulaire>

<SectionFormulaire titre="Photos" pour="ah-photos">
	<!--  7. Photos. Le champ n'écrit PAS son intitulé : la section le porte déjà,
	     et `FichiersUpload` en pose un par défaut (« Photos ») — on lisait donc le
	     mot deux fois, en deux typographies. C'est la règle que `SectionFormulaire`
	     écrit noir sur blanc depuis le 16/08 (une section à UN champ ne répète pas
	     son nom) ; seul cet écran l'avait manquée. Signalé par l'utilisateur. -->
	<FichiersUpload
		id="ah-photos"
		bind:urls={photos}
		max={maxPhotos}
		mode="photos"
		titre=""
		upload={onUpload}
		on:change={onPhotosChange}
	/>
	<p class="ah-aide">
		Facultatives, {maxPhotos} au maximum, placées en pied d'affiche : le texte de l'annonce reste l'élément
		central. Une affiche avec photo ne descend jamais sous l'{formatMinPhotos}.
	</p>
</SectionFormulaire>

<SectionFormulaire titre="Diffusion">
	<!--  9. Diffusion — le seul ACTE du formulaire, et le dernier, comme partout.
	
	      🔴 L'envoi au CS était AUTOMATIQUE le matin du 18/08 : il partait au moindre
	      essai de mise en page, pièce jointe comprise. Retiré dans la foulée, il revient
	      ici sous sa forme juste — une case, décochée par défaut.
	
	      ⚠️ Décochée, et c'est le point : la valeur par défaut d'un envoi est « ne pas
	      envoyer ». Un défaut à coché reproduirait l'automatisme qu'on vient de retirer,
	      en donnant l'illusion du choix.
	
	      ⚠️ UNE seule case, pas `CanauxNotification` : WhatsApp et le syndic n'ont pas
	      d'objet ici. Une affiche de hall s'imprime et se pose — le conseil syndical est
	      le seul destinataire qui en fasse quelque chose. -->
	<label class="case">
		<input id="ah-diffusion" type="checkbox" bind:checked={envoyerCs} />
		<span>Envoyer l'affiche au conseil syndical du périmètre, pour impression</span>
	</label>
	<p class="ah-aide">
		Facultatif. L'affiche est générée dans tous les cas et reste téléchargeable depuis l'historique
		— cocher ajoute un envoi par courriel, avec le PDF en pièce jointe.
	</p>
</SectionFormulaire>

<div class="form-actions">
	<button
		type="button"
		class="btn btn-outline"
		disabled={!valide || apercuLoading}
		on:click={onApercu}
	>
		{apercuLoading ? 'Génération…' : 'Aperçu'}
	</button>
	<!--  🔴 « Générer une affiche » (18/08/2026, demandé à l'écran : « Créer et
	      envoyer au CS me semble bizarre »). Le bouton nommait le DESTINATAIRE et le
	      transport ; ce qu'on fait ici, c'est PRODUIRE une affiche — l'envoi au CS
	      en est la conséquence, et l'aide du périmètre le dit déjà.

	      ⚠️ Exception assumée à « le bouton dit Enregistrer, partout »
	      (ux-patterns §9 quinquies bis) : cet écran ne crée pas un objet qu'on
	      retrouvera dans une liste, il FABRIQUE un document à imprimer. Même
	      famille que les imports, déjà hors périmètre de la règle. -->
	<button type="button" class="btn btn-primary" disabled={!valide || saving} on:click={onCreer}>
		{saving ? 'Génération…' : 'Générer une affiche'}
	</button>
</div>

<style>
	/*  Le balisage part avec ses styles : une classe posée ici et définie dans la
	    page ne serait pas atteinte (panne des pastilles nues, v2.67.11). */
	/*  ⚠️ Ces deux règles vivaient dans la page, sous `.ah-form label` et
	    `.ah-form input`. Elles sont parties avec le balisage qu'elles habillent :
	    `svelte-check` les a signalées orphelines dès l'extraction, ce qui a dit
	    exactement ce qui appartenait à ce composant. Sans ce déplacement, les
	    libellés seraient partis nus en production (v2.67.11).

	    ⚠️ NOMMÉES, jamais nues : `label { … }` a été refusé par `lint:styles`, et à
	    raison — il aurait atteint TOUS les `<label>` du composant, y compris ceux
	    d'un champ ajouté plus tard par quelqu'un qui ne lit pas ce bloc. C'est le
	    défaut qui avait étiré les cases à cocher du sondage (16/08/2026). */
	.ah-aide {
		font-size: 0.8rem;
		color: var(--color-text-muted);
		margin: 0.35rem 0 0;
		line-height: 1.5;
	}
	/*  `.ah-label-espace` a disparu : l'espacement entre sections est celui de
	    `SectionFormulaire`, une seule fois pour tout le site. */
	/*  Une case et son libellé. Le `width:auto` annule le `width:100%` des champs
	    de saisie — sans lui, la case s'étire et repousse son texte à l'autre bout
	    de la ligne (défaut signalé sur le sondage ET l'annonce, 16/08/2026). */
	/*  Le filet qui sépare le raccourci de pré-remplissage du formulaire lui-même.
	    Il était posé en `style=` en ligne — nommé ici, il cesse d'être à réécrire. */
	.ah-separateur {
		border: none;
		border-top: 1px solid var(--color-border);
		margin: 0.9rem 0;
	}
</style>
