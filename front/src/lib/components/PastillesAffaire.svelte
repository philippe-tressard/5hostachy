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

<style>
	.pa-cat {
		flex-shrink: 0;
		font-size: 0.95rem;
	}
</style>
