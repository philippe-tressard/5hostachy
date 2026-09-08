<!--
  **La note d'un prestataire**, avec sa teinte — écriture unique.

  ## Pourquoi ce composant (08/09/2026)

  Le rendu d'une note était écrit **quatre fois**, et les quatre ne disaient pas
  la même chose :

  | Où | Teinte | Nombre d'avis |
  |---|---|---|
  | `VueRenouvellementsContrats` ×1 | les trois seuils | en infobulle |
  | `VueRenouvellementsContrats` ×2 | les trois seuils | absent |
  | `VuePrestataires` (tableau) | **orange, toujours** | absent |

  🔴 La dernière ligne est un défaut visible : un prestataire noté **1/5 y
  apparaît en orange**, exactement comme un 3,5. La teinte est censée dire d'un
  coup d'œil si l'on est content de quelqu'un — là, elle ment.

  ⚠️ `starsDisplay` était DÉJÀ dans `$lib/utils` : la règle était factorisée,
  son **emploi** non. C'est le même motif que la validation des téléversements
  (#825) — et c'est l'emploi qui porte les seuils, donc la décision.

  ## Les seuils sont une règle, pas une présentation

  `< 3` mécontent · `< 4` correct · `>= 4` satisfait. Recopiés, ils se
  déplaceraient à trois endroits sur quatre le jour où l'on décide qu'un 3,5
  n'est plus « correct ».
-->
<script lang="ts">
	import { starsDisplay } from '$lib/utils';

	/** La note sur 5. `null` : rien n'est rendu — l'appelant n'a pas à le tester. */
	export let note: number | null | undefined = null;
	/** Le nombre d'avis, quand on le connaît : il devient l'infobulle. */
	export let nbAvis: number | null | undefined = null;
	/**  Affiche « /5 » après la note.
	 *
	 *   ⚠️ Divergence conservée et déclarée : la frise des contrats montre
	 *   « ★★★★ 4.2 » (la colonne est déjà titrée « Note »), le tableau des
	 *   notations « ★★★★ 4.2/5 » au milieu d'autres chiffres. Les aligner
	 *   retirerait une information à l'un ou du bruit à l'autre. */
	export let surCinq = false;

	//  🔴 LES SEUILS, à UN endroit. Ils décident d'une teinte que le lecteur
	//  interprète comme un jugement : les recopier, c'est accepter que le même
	//  prestataire paraisse « correct » sur un écran et « mécontent » sur l'autre.
	$: teinte = note == null ? '' : note < 3 ? 'bad' : note < 4 ? 'ok' : 'good';
</script>

{#if note != null}
	<!--  ⚠️ `class:` et non `class="note-etoiles {teinte}"` (#810) : devant un
	      ternaire INTERPOLÉ, Svelte cesse de déclarer les sélecteurs inutilisés
	      pour TOUT le fichier, et `lint:css-orphelin` y devient aveugle sans le
	      dire. Le plafond décroissant l'a refusé tout de suite.

	      ⚠️ Les SEUILS restent au-dessus, dans `teinte` : ce sont eux la règle.
	      Les remettre ici, dans trois `class:`, les recopierait — c'est
	      exactement ce que ce composant retire. -->
	<span
		class="note-etoiles"
		class:note-bad={teinte === 'bad'}
		class:note-ok={teinte === 'ok'}
		class:note-good={teinte === 'good'}
		title={nbAvis != null ? `${note}/5 (${nbAvis} avis)` : undefined}
		>{starsDisplay(note)} {note}{surCinq ? '/5' : ''}</span
	>
{/if}

<style>
	/*  Taille et césure reprises de `.frise-stars`, d'où ce composant est né. */
	.note-etoiles {
		font-size: 0.78rem;
		white-space: nowrap;
		letter-spacing: -0.02em;
	}
	/*  Les trois teintes viennent de `VueRenouvellementsContrats`, seul des trois
	    rendus à les porter — les deux autres l'ont donc GAGNÉE, et c'est le but. */
	.note-bad {
		color: #dc2626;
	}
	.note-ok {
		color: #f59e0b;
	}
	.note-good {
		color: #16a34a;
	}
</style>
