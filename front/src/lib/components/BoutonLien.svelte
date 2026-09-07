<!--
  BoutonLien.svelte — copier l'adresse d'UNE publication, pour l'envoyer.

  ## Pourquoi (05/09/2026)

  Demandé par l'utilisateur, en même temps que les URL dédiées des onglets :
  *« toutes les publications du site : une nouvelle icône pour récupérer le lien
  de la publication, à côté de l'icône Modifier »*.

  Une publication a toujours eu une adresse — `/annonces#annonce-42` — mais elle
  n'était écrite nulle part : seuls l'API la fabriquait, pour ses e-mails et son
  fil. Un résident qui voulait montrer une annonce à un voisin ne pouvait envoyer
  que l'adresse de la page, à charge pour l'autre de chercher.

  ## Ce que ce composant N'EST PAS

  Ce n'est pas un bouton de partage : il ne s'ouvre sur rien, ne propose ni
  WhatsApp ni e-mail, et ne demande aucune permission. Il copie une chaîne. La
  diffusion vers l'extérieur existe déjà, et c'est une **décision** de l'auteur
  (section 9 du cadre #430) — pas un geste de lecture.

  ## Le droit

  Aucun. Tout ce qui est affiché à quelqu'un peut lui être copié : l'adresse ne
  donne pas plus d'accès que l'écran d'où elle vient, puisque la page vérifie les
  droits du visiteur, pas ceux de l'expéditeur. C'est ce que demandait
  l'utilisateur — *« accessible à tous ceux qui ont accès »*.

  ⚠️ L'icône est un ÉMOJI, comme ✏️ et 🗑️ dans la même rangée. Le catalogue
  `$lib/icones-svg.json` aurait donné un tracé plus net, mais mélanger un SVG et
  deux émojis sur une même ligne se voit tout de suite : ils n'ont ni la même
  hauteur d'œil ni la même graisse. Le jour où la rangée passera au catalogue,
  elle y passera en entier.
-->
<script lang="ts">
	import { page } from '$app/stores';
	import { toast } from '$lib/components/Toast.svelte';

	/**  L'ancre de l'élément, sans le `#` — `annonce-42`. C'est l'`id` que la carte
	 *   pose déjà sur son conteneur pour les liens profonds : les deux ne peuvent
	 *   pas diverger, ils désignent le même élément. */
	export let ancre: string | null = null;
	/**  Le chemin de la publication quand elle a une page à elle (`/tickets/12`).
	 *   Par défaut, celui de la page courante — une carte de liste vit sur la route
	 *   de sa rubrique, qui est justement l'adresse qu'on veut envoyer. */
	export let chemin: string | null = null;
	/** Ce dont on copie le lien, pour l'annonce vocale : « Copier le lien de … ». */
	export let quoi = 'la publication';

	$: base = chemin ?? $page.url.pathname;
	$: lien = ancre ? `${base}#${ancre}` : base;

	async function copier() {
		//  Absolue : un lien relatif collé dans un SMS ou un e-mail ne mène nulle part.
		const url = new URL(lien, window.location.origin).href;
		try {
			await navigator.clipboard.writeText(url);
			toast('success', 'Lien copié');
		} catch {
			//  Le presse-papiers est refusé hors contexte sécurisé et par certains
			//  navigateurs embarqués (celui d'une application de messagerie, par
			//  exemple — exactement là où l'on veut coller un lien). Le repli n'est pas
			//  décoratif : sans lui, le geste échoue en silence là où il sert le plus.
			const zone = document.createElement('textarea');
			zone.value = url;
			zone.setAttribute('readonly', '');
			zone.style.position = 'fixed';
			zone.style.opacity = '0';
			document.body.appendChild(zone);
			zone.select();
			const copie = document.execCommand('copy');
			document.body.removeChild(zone);
			toast(copie ? 'success' : 'error', copie ? 'Lien copié' : 'Copie impossible');
		}
	}
</script>

<button
	class="btn-icon"
	type="button"
	title="Copier le lien"
	aria-label="Copier le lien de {quoi}"
	on:click|stopPropagation={copier}>&#x1F517;</button
>
