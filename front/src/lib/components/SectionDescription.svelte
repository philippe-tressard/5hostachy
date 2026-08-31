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
-->
<script lang="ts">
	import RichEditor from '$lib/components/RichEditor.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';

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
	</div>
</SectionFormulaire>
