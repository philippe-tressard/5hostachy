<!--
  La section **6. Description** du cadre — l'éditeur riche et son intitulé.

  Elle était écrite deux fois : `ChampsCommuns` (« Description ») et `EvolForm`
  (« Commentaire » / « Contenu »). Même structure, mêmes classes, même liaison
  d'accessibilité — seuls l'intitulé, le suffixe d'identifiant et la hauteur
  changeaient. Extraite le 01/09/2026, sur refus de modularité.

  🔴 **L'éditeur riche est un `contenteditable`, donc PAS labelable.** Le titre
  reste un `<h4>` et l'éditeur s'y relie par `aria-labelledby` — un
  `<label for>` n'aurait rien associé, et l'aurait fait en silence. C'est la
  raison d'être de `idTitre`, et elle ne se devine pas : ne pas la « simplifier »
  en `pour=`.

  ## L'assistant IA vit ICI, sous l'éditeur (#985, 17/09/2026)

  C'est la section qui le porte, pas l'écran : elle est rendue par
  `ChampsCommuns` (six formulaires) et par `EvolForm` (le fil), et l'y poser
  une fois le donne à tous — avec la même tête. Il ne s'affiche que si le
  formulaire lui passe un `assistant` (le contexte de l'objet), et le composant
  décide seul de sa visibilité (CS, usage disponible).

  ⚠️ `titreObjet` n'est PAS `titre` : le second est l'intitulé de la section
  (« Description »), le premier est le titre de l'OBJET, prêté par le
  formulaire pour que l'assistant puisse le retravailler aussi.
-->
<script lang="ts">
	import RichEditor from '$lib/components/RichEditor.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import AssistantDescription from '$lib/components/AssistantDescription.svelte';
	import type { ContexteAssistant } from '$lib/assistant';

	/** Préfixe des identifiants — l'écran en ouvre parfois plusieurs à la fois. */
	export let idPrefixe: string;
	/**  Le suffixe : `description` sur un objet, `contenu` sur une entrée de fil.
	 *   ⚠️ Il diffère entre les deux appelants, et le figer casserait la liaison
	 *   `aria-labelledby` d'un formulaire déjà ouvert. */
	export let idChamp = 'description';

	/** L'intitulé de la section — c'est LUI qui sert de libellé au champ. */
	export let titre = 'Description';
	export let requis = false;
	export let placeholder = '';
	/**  Elle valait 60, 80, 90, 100 ou 120 px selon l'écran, sans qu'aucune de ces
	 *   valeurs ait de raison. 120 px est le défaut — celui des deux écrans les
	 *   plus utilisés. Ne la surcharger que pour une vraie contrainte de place. */
	export let hauteur = '120px';
	/** Première section rendue : elle ne porte pas de filet au-dessus. */
	export let premiere = false;

	export let valeur = '';

	//  ── L'assistant IA (#985) ─────────────────────────────────────────────────
	/** L'entité et son contexte ; `null` = pas d'assistant sur ce formulaire. */
	export let assistant: ContexteAssistant | null = null;
	/** Le titre de l'objet, LIÉ : l'assistant le lit et peut le corriger. */
	export let titreObjet = '';
	/** Faux sur une entrée de fil : pas de titre à proposer. */
	export let assistantAvecTitre = true;
	/** Vrai dès qu'une proposition a été appliquée — le formulaire l'envoie en `assiste_ia`. */
	export let assisteIA = false;
</script>

<SectionFormulaire {premiere} {titre} {requis} idTitre="{idPrefixe}-{idChamp}-titre">
	<div class="field champ-large">
		<RichEditor
			id="{idPrefixe}-{idChamp}"
			bind:value={valeur}
			ariaLabelledby="{idPrefixe}-{idChamp}-titre"
			{placeholder}
			minHeight={hauteur}
		/>
		{#if assistant}
			<AssistantDescription
				contexte={assistant}
				idPrefixe="{idPrefixe}-{idChamp}"
				avecTitre={assistantAvecTitre}
				bind:titre={titreObjet}
				bind:description={valeur}
				bind:assiste={assisteIA}
			/>
		{/if}
	</div>
</SectionFormulaire>
