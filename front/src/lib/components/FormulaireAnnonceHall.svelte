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
	import SectionDiffusion from '$lib/components/SectionDiffusion.svelte';
	import { annoncesHall as annoncesHallApi } from '$lib/api';
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

	/**  9. DIFFUSION — les TROIS canaux, comme partout ailleurs (#480).
	 *
	 *   🔴 Cet écran portait UNE case, au motif écrit ici même que « WhatsApp et le
	 *   syndic n'ont pas d'objet : une affiche s'imprime et se pose, le conseil
	 *   syndical est le seul destinataire qui en fasse quelque chose ».
	 *   L'arbitrage est renversé — *« Diffusion n'est pas standard : WhatsApp, CS,
	 *   syndic ⇒ utilise l'objet standard »*.
	 *
	 *   ⚠️ Le report était **légitime** : le cadre interdit d'ouvrir un champ que le
	 *   serveur ne consomme pas, et il n'en consommait qu'un sur trois. Les deux
	 *   autres sont consommés depuis le 01/09/2026 — c'est ce qui a permis de poser
	 *   l'objet.
	 *
	 *   Tous décochés par défaut : la valeur par défaut d'un envoi est « ne pas
	 *   envoyer ». */
	export let envoyerCs = false;
	export let envoyerSyndic = false;
	export let partagerWhatsapp = false;
	export let envoyerAuteur = false;
	/** Le nom de l'auteur de l'affiche — il nomme le destinataire de la copie. */
	export let auteurNom = '';

	//  L'APERÇU AVANT ENVOI (#498, branché ici le 01/09/2026).
	//
	//  🔴 Cet écran en était privé DÉLIBÉRÉMENT : tant que le serveur ne consommait
	//  qu'un canal sur trois, un aperçu y aurait montré un envoi qui n'a pas lieu —
	//  le mensonge même que #498 existe pour empêcher. Les trois canaux sont
	//  consommés depuis #480, et la condition est levée.
	//
	//  ⚠️ Brancher l'aperçu demande DEUX gestes, et le second est celui qu'on
	//  oublie : fournir `demanderApercu` NE SUFFIT PAS, il faut s'intercaler dans la
	//  soumission. Le 31/08, l'oubli du second a fait partir une actualité que
	//  personne n'a pu annuler — `npm run lint:apercu` le refuse depuis.
	let refDiffusion: any = null;
	$: aUneDiffusion = envoyerCs || envoyerSyndic || partagerWhatsapp;

	const brouillonApercu = () =>
		annoncesHallApi.apercuDiffusion({
			//  L'affiche pré-remplie depuis une actualité en garde le lien : c'est
			//  lui que le groupe WhatsApp reçoit, et l'aperçu doit le montrer.
			publication_id: typeof sourceId === 'number' ? sourceId : undefined,
			titre: titre.trim(),
			message,
			perimetre_cible: perimetre,
			format_demande: format,
			images: photos,
			envoyer_cs: envoyerCs,
			envoyer_syndic: envoyerSyndic,
			partager_whatsapp: partagerWhatsapp,
			envoyer_auteur: envoyerAuteur,
		});

	/**  Aperçu d'abord si un canal est coché — même patron que `FormulaireActualite`.
	 *   `onCreer` reste l'unique chemin d'écriture. */
	function soumettre() {
		if (!valide) return;
		if (refDiffusion?.ouvrirSiDiffusion(aUneDiffusion)) return;
		refDiffusion?.fermerApercu();
		onCreer();
	}

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
			{#each pubs as pub (pub.id)}
				<option value={pub.id}>{fmtDateShort(pub.cree_le)} · {pub.titre}</option>
			{/each}
		</select>
	</div>
	<p class="aide-bloc">
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
		{#each formats as f (f.val)}
			<Pastille petite active={format === f.val} on:click={() => (format = f.val)}
				>{f.label}</Pastille
			>
		{/each}
	</div>
	<p class="aide-bloc">
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
	<p class="aide-bloc">Imprimé sur l'affiche : il dit où elle doit être posée.</p>
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
	<p class="aide-bloc">
		Facultatives, {maxPhotos} au maximum, placées en pied d'affiche : le texte de l'annonce reste l'élément
		central. Une affiche avec photo ne descend jamais sous l'{formatMinPhotos}.
	</p>
</SectionFormulaire>

<SectionFormulaire titre="Diffusion">
	<!--  🔴 L'OBJET DIFFUSION, et non trois cases écrites ici (#480).

	      Cet écran portait UNE case. L'argument était réel — une affiche s'imprime
	      et se pose — mais il décidait à la place du CS : rien n'empêche de vouloir
	      prévenir le syndic, ou d'annoncer sur le groupe qu'une affiche est posée.

	      ⚠️ Le lien envoyé sur WhatsApp pointe l'ACTUALITÉ dont l'affiche est
	      tirée, quand il y en a une. Une affiche autonome part sans lien :
	      l'historique des affiches est un écran d'administration, et y envoyer les
	      résidents leur donnerait un 403. -->
	<SectionDiffusion
		avecCanaux
		compact
		idPrefixe="ah-diffusion"
		bind:this={refDiffusion}
		bind:whatsapp={partagerWhatsapp}
		bind:syndic={envoyerSyndic}
		bind:cs={envoyerCs}
		bind:auteur={envoyerAuteur}
		{auteurNom}
		aideWhatsapp="Le groupe reçoit le titre, le message et un lien vers l'actualité d'origine — jamais le PDF."
		demanderApercu={brouillonApercu}
		envoiEnCours={saving}
		on:envoyer={() => onCreer()}
	/>
	<p class="aide-bloc">
		Facultatif. L'affiche est générée dans tous les cas et reste téléchargeable depuis l'historique.
		Le conseil syndical reçoit le PDF en pièce jointe, pour impression — et seuls les conseillers du
		périmètre visé sont prévenus.
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
	<button type="button" class="btn btn-primary" disabled={!valide || saving} on:click={soumettre}>
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
