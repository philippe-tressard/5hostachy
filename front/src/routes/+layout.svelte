<script lang="ts">
	import '../app.css';
	import Toast from '$lib/components/Toast.svelte';
	import MajDisponible from '$lib/components/MajDisponible.svelte';
	import { configStore } from '$lib/stores/pageConfig';

	export let data;

	// Peuple le store depuis les données SSR → zéro flash au premier rendu
	$: if (data?.siteConfig && Object.keys(data.siteConfig).length > 0) {
		configStore.set(data.siteConfig);
	}
</script>

<slot />

<!--  🔴 APRÈS le contenu dans le DOM, et pas avant (#778, 06/09/2026).

      Les deux sont en `position: fixed` : leur place à l'écran ne dépend pas de
      leur place ici. Leur place dans le DOM, elle, décide de l'ordre du CLAVIER —
      et `MajDisponible` porte DEUX boutons.

      Montés avant, ils précédaient le lien d'évitement « Aller au contenu », qui
      vit dans le squelette `(app)`. Le premier Tab atteignait alors le bandeau de
      mise à jour au lieu du lien — **seulement quand une version était
      disponible**, donc un défaut intermittent, celui qu'on ne reproduit jamais
      au moment où on le cherche.

      ⚠️ Le lien ne peut PAS remonter ici : son ancre `#contenu` est le `<main>`
      du squelette `(app)`, qui n'existe pas sur les écrans de connexion. Un lien
      d'évitement qui pointe vers une ancre absente est pire qu'aucun lien — il
      apparaît au Tab et ne fait rien. -->
<Toast />
<MajDisponible />
