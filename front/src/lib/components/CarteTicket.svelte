<!--
  CarteTicket.svelte — la carte d'un ticket dans une liste, dépliable, et ses
  trois modes : lecture, correction (édition), nouvelle entrée (évolution).

  ## Pourquoi ce composant (17/08/2026, #431)

  `tickets/+page.svelte` rendait cette carte DEUX FOIS — une fois pour la liste
  active, une fois pour la section des tickets clos —, soit **115 lignes
  recopiées**, fil de suivi compris. Les deux copies avaient déjà divergé de trois
  façons, toutes invisibles à la relecture :

    • le badge NEW n'existait que sur la première ;
    • le bouton ✏️ *Modifier* n'existait que sur la première, sans qu'aucun commit
      ni aucune issue ne dise pourquoi un administrateur perdrait ce geste au bout
      de sept jours ;
    • le fil de suivi y était réécrit intégralement, deux fois.

  Une carte, un fichier. La seule différence retenue est l'**allure d'archive**
  (`archive`), qui se voit : filet à gauche, fond atténué. Elle est portée ici, en
  prop — une classe posée par la page sur le balisage d'un composant enfant ne
  serait **pas atteinte** par le `<style>` de la page (panne des pastilles nues,
  v2.67.11).

  ## Les formulaires vivent ICI, et pas dans un slot

  Première écriture, la carte exposait un slot `formulaire` et la page y branchait
  `FormulaireTicket` et `EvolForm`. Ce câblage-là aurait été recopié deux fois —
  la duplication supprimée d'un côté serait revenue de l'autre, en plus discret.
  La carte porte donc ses trois modes ; la page ne garde que la décision (*quel
  ticket, quel mode*) et les appels d'API.

  ## L'affichage passe par le squelette de lecture

  Le corps déplié n'écrit plus l'ordre de ses notions : `FicheLecture` le lit dans
  la déclaration `TICKET` (`$lib/entites/ticket`). La carte affichait
  *description → photos → périmètre* ; les deux formulaires demandent
  *périmètre → description → photos → documents*. C'est R2, et elle vaut aussi
  pour l'affichage.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import ApercuCarte from './ApercuCarte.svelte';
	import EnteteCarte from './EnteteCarte.svelte';
	import FicheLecture from './FicheLecture.svelte';
	import RubriqueHistorique from './RubriqueHistorique.svelte';
	import FormulaireTicket from './FormulaireTicket.svelte';
	import EvolForm from './EvolForm.svelte';
	import { TICKET } from '$lib/entites/ticket';
	import { fmtDate, isNouveau } from '$lib/date';
	import type { Ticket, TicketEvolution } from '$lib/api';
	import {
		STATUT_TICKET_BADGE,
		STATUT_TICKET_LABELS,
		STATUT_TICKET_OPTIONS,
		categorieTicketEmoji,
	} from '$lib/tickets';

	export let ticket: Ticket;
	export let evolutions: TicketEvolution[] = [];
	export let expanded = false;
	/** Allure d'archive : le ticket est clos depuis plus du délai de grâce. */
	export let archive = false;
	/** Le lecteur peut-il commenter / changer l'état ? (conseil syndical) */
	export let peutCommenter = false;
	/** Le lecteur peut-il corriger ou supprimer ? (administrateur) */
	export let peutAdministrer = false;
	/**  Ce que le corps de la carte montre. La page en est propriétaire : elle
	     seule sait qu'un seul formulaire doit être ouvert à la fois.
	     ⚠️ UN seul mode d'évolution (#426) : le geste ne se déclare plus au clic,
	     il se lit dans les pastilles de la section Workflow, celle de l'état
	     courant étant active. */
	export let mode: 'lecture' | 'edition' | 'evolution' = 'lecture';
	/** Enregistrement d'une évolution en cours — porté par la page (appel d'API). */
	export let evolutionEnCours = false;

	const dispatch = createEventDispatcher<{
		basculer: void;
		evoluer_ouvrir: void;
		modifier: void;
		supprimer: void;
		annuler: void;
		evoluer: unknown;
	}>();

	$: dateAffichee = ticket.mis_a_jour_le ?? ticket.cree_le;
</script>

<div
	id="ticket-{ticket.id}"
	class:carte-liste={!archive}
	class:history-item={archive}
	class:expanded
	class:urgent={ticket.categorie === 'urgence'}
	role="button"
	tabindex="0"
	on:click={() => dispatch('basculer')}
	on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && dispatch('basculer')}
>
	<!--  Titre sur sa propre ligne, puis tags à gauche / date + actions à droite :
	      la norme de toutes les cartes du site (`EnteteCarte`, 18/08/2026). -->
	<EnteteCarte titre={ticket.titre} date={fmtDate(dateAffichee)}>
		<svelte:fragment slot="titre-suffixe">
			{#if isNouveau(ticket.cree_le, ticket.mis_a_jour_le)}
				<span class="badge badge-gray tk-neuf">NEW</span>
			{/if}
		</svelte:fragment>
		<svelte:fragment slot="tags">
			<span class="tk-cat" title={ticket.categorie}>{categorieTicketEmoji(ticket.categorie)}</span>
			<span class="badge {STATUT_TICKET_BADGE[ticket.statut] ?? 'badge-gray'}">
				{STATUT_TICKET_LABELS[ticket.statut] ?? ticket.statut}
			</span>
			{#if ticket.priorite === 'haute'}<span class="badge badge-orange">⚡ Urgente</span>{/if}
			{#if ticket.auteur_nom}<span class="tk-auteur">{ticket.auteur_nom}</span>{/if}
		</svelte:fragment>
		<svelte:fragment slot="actions">
			<!--  UN point d'entrée (#426) : le formulaire porte les deux gestes.
			      L'ordre des icônes — 🔄 puis ✏️ puis 🗑️ — est celui de toutes les
			      cartes du site, arbitré le 18/08/2026 sur celle-ci. -->
			{#if peutCommenter}
				<button class="btn-icon" aria-label="Commenter ou changer l’état"
					title="Commenter ou changer l’état"
					on:click|stopPropagation={() => dispatch('evoluer_ouvrir')}>&#x1F504;</button>
			{/if}
			{#if peutAdministrer}
				<button class="btn-icon" aria-label="Modifier" title="Modifier le ticket"
					on:click|stopPropagation={() => dispatch('modifier')}>✏️</button>
				<button class="btn-icon-danger" aria-label="Supprimer" title="Supprimer définitivement"
					on:click|stopPropagation={() => dispatch('supprimer')}>&#x1F5D1;️</button>
			{/if}
		</svelte:fragment>
		<svelte:fragment slot="chevron"><span class="chevron" class:open={expanded}>›</span></svelte:fragment>
	</EnteteCarte>

	{#if !expanded}
		<ApercuCarte contenu={ticket.description} photos={ticket.photos_urls ?? []} />
	{/if}

	{#if expanded}
		<!--  Le corps ne replie pas la carte : on y saisit, on y clique des
		      vignettes. `role="presentation"` dit que ce conteneur n'est qu'un
		      relais — l'élément interactif, c'est la carte. -->
		<div class="tk-body" role="presentation" on:click|stopPropagation on:keydown|stopPropagation>
			{#if mode === 'edition'}
				<div class="tk-formulaire">
					<FormulaireTicket {ticket} on:modifie on:annule={() => dispatch('annuler')} />
				</div>
			{:else if mode === 'evolution'}
				<div class="tk-formulaire">
					<EvolForm idPrefixe="tk-evol-{ticket.id}"
						statutOptions={STATUT_TICKET_OPTIONS}
						statutLabels={STATUT_TICKET_LABELS}
						currentStatut={ticket.statut}
						showNotifs={peutCommenter}
						showFiles={true}
						saving={evolutionEnCours}
						on:submit={(e) => dispatch('evoluer', e.detail)}
						on:cancel={() => dispatch('annuler')}
					/>
				</div>
			{:else}
				<FicheLecture
					entite={TICKET}
					perimetre={ticket.perimetre_cible ?? []}
					description={ticket.description}
					photos={ticket.photos_urls ?? []}
					documents={ticket.fichiers_urls ?? []}
				>
					<svelte:fragment slot="pied">
						<small class="tk-meta">
							Créé le {fmtDate(ticket.cree_le)}
							<span class="tk-numero"> · #{ticket.numero}</span>
						</small>
					</svelte:fragment>
				</FicheLecture>

				{#if evolutions.length > 0}
					<div class="tk-fil">
						<RubriqueHistorique {evolutions} statutLabels={STATUT_TICKET_LABELS} />
					</div>
				{/if}
			{/if}
		</div>
	{/if}
</div>

<style>
	/*  Conteneur, survol, `expanded` et `urgent` viennent de `.carte-liste`
	    (app.css) : ne vivent ici que ce qui est propre à la carte d'un ticket.

	    ⚠️ `tk-expand` a été RETIRÉE du balisage (#431). Elle y était depuis
	    toujours, sur les deux cartes, et n'était définie NULLE PART qui l'atteigne :
	    sa seule définition vit dans le `<style>` d'`espace-cs`, donc scopée à cet
	    écran-là. Une classe utilisée et jamais définie n'échoue à aucun contrôle —
	    `svelte-check` sait dire qu'un sélecteur défini n'est pas utilisé, pas
	    l'inverse. La retirer ne change rien à l'écran : c'est bien la preuve
	    qu'elle ne faisait rien. */
	/*  L'en-tête vit dans `EnteteCarte` — titre, tags, date, actions et leur repli.
	    Ne reste ici que ce qui est propre à un ticket. */
	.tk-cat { flex-shrink: 0; font-size: .95rem; }
	.tk-auteur { font-size: .78rem; color: var(--color-text-muted); }
	.tk-neuf { margin-left: .5em; font-size: .82em; font-weight: 500; vertical-align: middle; }

	.tk-body { padding: .75rem 1rem 1rem; border-top: 1px solid var(--color-border); }
	.tk-formulaire { padding: .25rem 0; }
	.tk-meta { color: var(--color-text-muted); font-size: .78rem; }
	.tk-numero { font-family: monospace; }
	/*  La marge haute du fil appartient à son hôte : la rubrique ne sait pas ce
	    qu'elle suit. C'est cette marge que la fiche du ticket avait perdue. */
	.tk-fil { margin-top: .9rem; }

	/*  Allure d'archive — portée ici et non par la page hôte : le `<style>` d'une
	    page n'atteint pas le balisage d'un composant enfant. */
	.history-item {
		border-left: 4px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
		opacity: .8;
		transition: opacity .15s, border-left-color .15s;
	}
	.history-item:hover { opacity: 1; }
	.history-item.expanded { opacity: 1; }
</style>
