<!--
  La DERNIÈRE LIGNE d'une carte d'affaire — la même partout (27/09/2026).

  Arbitré à l'écran : la ligne de la carte d'AFFAIRE fait la norme, et le fil
  d'activité comme la carte d'actualité la rendent à l'identique — même
  pastilles, même couleur, même nom, même place. Elles différaient sur neuf
  points (catégorie en texte ou en emoji, état absent du fil, périmètre en tête
  ou après l'état, « urgent » rouge contre « ⚡ Urgente » orange, numéro en
  badge ou en texte, auteur avec ou sans ✍️, lecteurs et ✨ absents du fil…).

  L'ORDRE, qui ne se discute plus :
    catégorie (emoji, libellé au survol) · état · 🔹 périmètre · qui la lit ·
    ⚡ urgence · marqueurs · #numéro · ✍️ auteur · ✨ IA

  Deux différences, et deux seulement, DÉCLARÉES :
    • une ACTUALITÉ n'a pas d'état — elle n'a pas de suivi (#1091) ;
    • dans le FIL (`dansLeFil`), pas de 📌 : le fil a son bandeau « Épinglé »
      (arbitré le 27/09/2026).

  🔴 PAS DE BADGE 📍 DU DEMANDEUR — arbitré à l'écran le 30/08/2026 (#653) :
  *« se restreindre uniquement au périmètre »*. Il disait où habite la personne,
  pas où est le problème ; le 🔹 répond à la seule question du lecteur de liste.
  Ce qui manque vraiment est le LOT, suivi dans #653 — ne pas remettre de badge
  de bâtiment en attendant.

  🔒 `npm run lint:pastilles` exige que les trois cartes passent par ici.
-->
<script lang="ts">
	import BadgePerimetre from '$lib/components/BadgePerimetre.svelte';
	import PastilleLecture from '$lib/components/PastilleLecture.svelte';
	import AuteurCarte from '$lib/components/AuteurCarte.svelte';
	import MarqueIA from '$lib/components/MarqueIA.svelte';
	import {
		BADGE_PRIORITE,
		PRIORITE_BREVE,
		STATUT_TICKET_BADGE,
		STATUT_TICKET_LABELS,
		categorieTicketEmoji,
		categorieTicketLabel,
		estActualite,
		optionsEnBadge,
		ticketUrgent,
	} from '$lib/tickets';
	import type { Ticket } from '$lib/api';

	/** L'affaire — une carte la passe entière, le fil ses seuls champs de ligne. */
	export let affaire: Ticket;
	/** Le PROPRIÉTAIRE à nommer (`nomProprietaire`, ou le nom que le fil reçoit). */
	export let auteur: string | null | undefined = null;
	/** Le fil a son bandeau « Épinglé » : pas de 📌 sur la ligne. */
	export let dansLeFil = false;

	$: marqueurs = optionsEnBadge(affaire).filter((o) => !(dansLeFil && o.cle === 'epingle'));
</script>

<!--  `display: contents` : les pastilles restent les enfants de la ligne qui les
      reçoit (`.ec-tags`, `.flux-badges`) — c'est elle qui les range et les fait
      passer à la ligne. L'enveloppe ne sert qu'à borner l'habillage ci-dessous. -->
<span class="pa">
	<span class="pa-cat" title={categorieTicketLabel(affaire.categorie)}
		>{categorieTicketEmoji(affaire.categorie)}</span
	>
	{#if !estActualite(affaire)}
		<span class="badge {STATUT_TICKET_BADGE[affaire.statut] ?? 'badge-gray'}">
			{STATUT_TICKET_LABELS[affaire.statut] ?? affaire.statut}
		</span>
	{/if}
	<BadgePerimetre perimetre={affaire.perimetre_cible} />
	<PastilleLecture ticket={affaire} />
	{#if ticketUrgent(affaire)}
		<span class="badge {BADGE_PRIORITE[affaire.priorite] ?? 'badge-gray'}"
			>{PRIORITE_BREVE[affaire.priorite]}</span
		>
	{/if}
	{#each marqueurs as opt (opt.cle)}
		<span class="badge badge-gray" title={opt.aide}>{opt.glyphe} {opt.etat}</span>
	{/each}
	<span>#{affaire.numero}</span>
	<AuteurCarte nom={auteur} />
	<MarqueIA assiste={affaire.assiste_ia} />
</span>

<style>
	.pa {
		display: contents;
	}
	/*  Les pastilles ne se compriment pas — la règle de `.ec-tags`, qui ne les
	    atteint plus à travers l'enveloppe. */
	.pa > :global(*) {
		flex-shrink: 0;
	}
	/*  🔴 UN HABILLAGE, et la couleur seulement où elle DISTINGUE (maquette B,
	    10/10/2026 : « visuellement brouillon »). La ligne portait cinq
	    habillages — fond jaune, gris, contour, rose, texte nu — et la couleur
	    n'y hiérarchisait plus rien. Désormais : des CAPSULES (coins de 6 px, et
	    non la pilule), NEUTRES sur le pierre de la charte pour ce qui décrit
	    sans alerter — périmètre, marqueurs ; seuls l'ÉTAT, « qui la lit » et
	    l'URGENCE gardent leur teinte, parce qu'ils changent d'une affaire à
	    l'autre et qu'on les cherche. Le numéro, l'auteur et ✨ restent du texte.
	    Ici et non sur la carte : le fil d'accueil rend cette ligne à l'identique
	    (arbitrage n° 13), il prend l'habillage avec elle. */
	.pa :global(.badge) {
		border-radius: 0.375rem;
	}
	.pa :global(.badge-gray) {
		background: var(--color-bg);
		color: var(--color-text-muted);
		font-weight: 500;
	}
	.pa-cat {
		flex-shrink: 0;
		font-size: var(--fs-lg);
	}
</style>
