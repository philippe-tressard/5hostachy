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

  ## Ce que ce composant N'EST PAS — et la nuance de #1357

  Il ne s'ouvre sur rien, ne propose pas WhatsApp et ne demande aucune
  permission : le clic COPIE une chaîne, comme avant. La diffusion vers
  l'extérieur reste une **décision** de l'auteur (section 9 du cadre #430).

  🔴 Une nuance depuis le 26/09/2026 (#1357, option E des maquettes) : pour une
  AFFAIRE (`partage`), le message « Lien copié » propose ensuite « L'envoyer par
  courriel » (`PartageCourriel`). Le copier reste à un clic ; l'envoi est un
  second geste, choisi. Cette phrase disait « ni WhatsApp ni e-mail » : elle est
  réécrite dans le lot qui change la décision.

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
	import PartageCourriel from '$lib/components/PartageCourriel.svelte';

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
	/**  L'affaire dont le lien peut aussi partir par courriel (#1357) — son `id` ;
	 *   `null` : on copie, rien de plus. */
	export let partage: number | null = null;
	let bouton: HTMLButtonElement;

	/** « Lien copié », et pour une affaire la proposition de l'envoyer. */
	function annoncerCopie(copie: boolean) {
		if (!copie) return toast('error', 'Copie impossible');
		if (partage === null) return toast('success', 'Lien copié');
		toast('success', 'Lien copié', 8000, {
			composant: PartageCourriel,
			props: { ticketId: partage, retour: bouton },
		});
	}

	$: base = chemin ?? $page.url.pathname;
	$: lien = ancre ? `${base}#${ancre}` : base;

	async function copier() {
		//  Absolue : un lien relatif collé dans un SMS ou un e-mail ne mène nulle part.
		const url = new URL(lien, window.location.origin).href;
		try {
			await navigator.clipboard.writeText(url);
			annoncerCopie(true);
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
			annoncerCopie(copie);
		}
	}
</script>

<button
	bind:this={bouton}
	class="btn-icon"
	type="button"
	title="Copier le lien"
	aria-label="Copier le lien de {quoi}"
	on:click|stopPropagation={copier}>&#x1F517;</button
>
