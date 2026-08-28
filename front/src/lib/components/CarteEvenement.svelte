<!--
  CarteEvenement.svelte — un événement dans la liste du calendrier.

  ## Pourquoi ce composant (18/08/2026)

  La page faisait 1 174 lignes et le garde-fou de modularité (rang 1) refusait
  qu'elle grossisse pour recevoir trois correctifs signalés à l'écran : le point
  d'entrée du suivi qui manquait, l'aperçu replié absent, et l'alignement de
  l'en-tête.

  ⚠️ **Ce découpage avait été écarté la veille**, et pour une bonne raison :
  `.event-row` est un `flex` partagé avec les blocs **Archives** et
  **Maintenances récurrentes** de la même page, et déplacer ses règles les aurait
  laissés nus — la panne des pastilles (v2.67.11). Ce qui l'a rendu possible est
  le modificateur `.ev-norme` : la carte de la liste ne dépend plus de la
  disposition de `.event-row`, seulement de `.card` (global). Les deux autres
  blocs gardent la leur, intacte.

  ## Ce qu'il décide, et ce qu'il ne décide pas

  Il rend une carte et signale les gestes ; la **page** garde ce qu'elle seule
  sait — quel événement est déplié, lequel attend une entrée de suivi, et les
  appels d'API. L'en-tête vient d'`EnteteCarte` (la norme du site), l'aperçu
  d'`ApercuCarte`, le fil d'`HistoriqueEvenement`.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import EnteteCarte from './EnteteCarte.svelte';
	import ApercuCarte from './ApercuCarte.svelte';
	import FicheLecture from './FicheLecture.svelte';
	import HistoriqueEvenement from './HistoriqueEvenement.svelte';
	import { EVENEMENT } from '$lib/entites/evenement';
	import { apercuAvecRepli } from '$lib/fichiers';
	import { estPerimetreParDefaut, perimetreLabel } from '$lib/utils';

	export let ev: any;
	export let expanded = false;
	/** Les colonnes du Kanban — la source unique reste `$lib/kanban`. */
	export let colonnes: { id: string; label: string }[] = [];
	/** Le lecteur peut-il agir sur l'événement ? (CS/admin) */
	export let peutAgir = false;
	/** Le formulaire de suivi est-il ouvert ? La page le porte. */
	export let suiviOuvert = false;
	/**  L'événement est-il en cours de MODIFICATION ? Sert à inverser son ✏️ :
	 *   le mode se lit sur l'icône qui l'a ouvert, plus sur un titre au-dessus
	 *   du formulaire (18/08/2026). Le formulaire du calendrier vit dans la
	 *   page, pas dans la carte — la carte ne peut donc pas le deviner. */
	export let editionOuverte = false;
	/** Libellés — la page les calcule déjà pour ses autres vues. */
	export let typeLabel: (t: string) => string;
	export let formatDate: (d: string) => string;

	const dispatch = createEventDispatcher<{
		basculer: void; suivre: void; modifier: void; archiver: void; evolue: void; fermer: void;
	}>();
</script>

	<div
		class="carte-liste carte-evenement"
		id="ev-{ev.id}"
		role="presentation"
		class:event-urgent={ev.type === 'coupure'}
		class:expanded
		on:click={() => { if (!expanded) dispatch('basculer'); }}
	>
		<!--  La NORME de toutes les cartes du site (`EnteteCarte`, 18/08/2026) :
		      titre sur sa propre ligne, puis tags à gauche / date et actions à
		      droite. Cette carte les mettait sur UNE ligne, en trois colonnes —
		      et sur téléphone le titre se réduisait à trois points.
		      Le chevron dit que la carte s'ouvre (#362) ; sur tactile c'est LUI
		      qui porte l'information, `:hover` ne s'y déclenchant pas. -->
		<!--  Le geste de dépliage vit dans `EnteteCarte` : le TITRE plie, avec un
		      survol qui le dit (18/08/2026). Le conteneur ne porte plus
		      `role="button"` — il interceptait la sélection de texte, et obligeait
		      chaque bouton d'action à un `stopPropagation` pour qu'un clic sur ✏️ ne
		      déplie pas la carte au même instant. -->
		<EnteteCarte titre={ev.titre} date={formatDate(ev.debut)}
			basculable on:toggle={() => dispatch('basculer')}
>
			<svelte:fragment slot="tags">
				<span class="badge badge-gray">{typeLabel(ev.type)}</span>
				{#if ev.statut_kanban}<span class="badge badge-blue">{colonnes.find((c) => c.id === ev.statut_kanban)?.label ?? ev.statut_kanban}</span>{/if}
				{#if !estPerimetreParDefaut(ev.perimetre)}<span class="badge badge-gray">&#x1F539; {perimetreLabel(ev.perimetre)}</span>{/if}
				{#if ev.prestataire_nom}<span class="event-meta">&#x1F3AF; {ev.prestataire_nom}</span>{/if}
				{#if ev.lieu}<span class="event-meta">&#x1F4CD; {ev.lieu}</span>{/if}
				{#if ev.fin}<span class="event-meta">→ {formatDate(ev.fin)}</span>{/if}
				{#if ev.auteur_nom}<span class="event-meta">{ev.auteur_nom}</span>{/if}
			</svelte:fragment>
			<svelte:fragment slot="actions">
				<!--  🔴 La garde `_source !== 'devis_ponctuel'` a disparu avec les
				      prestations ponctuelles (#602). Elle privait d'actions les cartes
				      fabriquées à la volée depuis un devis : identifiant négatif, aucune
				      ligne derrière, donc aucun geste possible. Toutes les cartes
				      correspondent désormais à un événement réel. -->
				{#if peutAgir}
					<span class="event-actions" on:click|stopPropagation on:keydown|stopPropagation role="presentation">
						<!--  L'ordre du site : 🔄 commenter · ✏️ modifier · 🗑️/📦. Le 🔄
						      manquait ici — le suivi n'avait aucun point d'entrée. -->
						<button class="btn-icon" aria-pressed={suiviOuvert} aria-label="Commenter ou changer l’état"
							title="Commenter ou changer l’état" on:click={() => dispatch('suivre')}>&#x1F504;</button>
						<button class="btn-icon-edit" aria-pressed={editionOuverte} aria-label="Modifier" title="Modifier" on:click={() => dispatch('modifier')}>✏️</button>
						{#if ev.statut_kanban === 'termine' || ev.statut_kanban === 'annule'}
							<button class="btn-icon" aria-label="Archiver" title="Archiver" on:click={() => dispatch('archiver')}>&#x1F4E6;</button>
						{/if}
					</span>
				{/if}
			</svelte:fragment>
			<svelte:fragment slot="chevron"><span class="chevron" class:open={expanded}>›</span></svelte:fragment>
		</EnteteCarte>
		{#if !expanded}
			<!--  L'aperçu replié — quatre lignes de texte et la vignette, comme
			      sur Actualités et Tickets. La carte ne montrait que son titre. -->
			<!--  ⚠️ Photos et documents SÉPARÉS : la vignette pose `photos[0]` dans un
			      `<img>`. Les verser ensemble faisait sortir un devis PDF en image
			      cassée ; séparés, il devient une tuile 📎. -->
			<!--  🔴 REPLI SUR L'HISTORIQUE (18/08/2026, constaté à l'écran). Un
			      événement n'a le plus souvent aucune photo propre : c'est le suivi
			      qui en apporte — « le technicien est intervenu ce matin, voici les
			      anomalies ». La carte restait donc nue là où un ticket illustré
			      montre sa vignette. Gratuit ici : l'API livre l'Historique AVEC
			      l'événement (`EvenementRead.evolutions`), aucune requête de plus. -->
			{@const apercu = apercuAvecRepli(ev.photos_urls, ev.fichiers_urls, ev.evolutions)}
			<ApercuCarte contenu={ev.description ?? ''}
				photos={apercu.photos} fichiers={apercu.fichiers} />
		{/if}
		{#if expanded}
			<div class="ev-expanded-body" role="presentation" on:click|stopPropagation on:keydown|stopPropagation>
				<!--  🔴 Le corps n'écrit plus l'ordre de ses notions : `FicheLecture` le
				      lit dans la déclaration `EVENEMENT` (#432). Il rendait
				      `[...photos_urls, ...fichiers_urls]` dans UN seul bloc — la fusion
				      des sections 7 et 8, que le cadre interdit. Elle avait déjà dû être
				      défaite trois lignes plus haut, dans l'aperçu, parce qu'un devis PDF
				      versé avec les photos sortait en image cassée ; elle survivait ici.

				      ⚠️ Le PÉRIMÈTRE n'est pas passé à `FicheLecture`, et ce n'est pas un
				      oubli : il est déjà rendu en tag d'`EnteteCarte`, au-dessus, où il
				      reste lisible carte repliée (« la méta est toujours visible en mode
				      collapsé »). Le lui redonner ici l'afficherait deux fois sur le même
				      écran. C'est un choix de PLACEMENT dans un même état — la section 4
				      est bien rendue en affichage —, et non une divergence entre états :
				      R4 n'a rien à en dire, et rien n'est inventé pour le déclarer. -->
				<FicheLecture entite={EVENEMENT}
					description={ev.description ?? ''}
					photos={ev.photos_urls ?? []}
					documents={ev.fichiers_urls ?? []} />
				<!--  L'HISTORIQUE — dernier écran à faire avancer un suivi en silence.
				      Il n'est pas une des neuf sections : il vient après elles, comme le
				      fil d'un ticket après sa fiche. -->
				<HistoriqueEvenement evenement={ev} colonnes={colonnes} peutAgir={peutAgir}
					ouvert={suiviOuvert} on:evolue on:fermer />
			</div>
		{/if}
	</div>

<style>
	/*  Ce qui est PROPRE à la carte de la liste. `.event-row`, `.event-type`,
	    `.event-body` et `.event-date` restent dans la page : les blocs Archives et
	    Maintenances récurrentes les utilisent, et un style de page n'atteint pas le
	    balisage d'un composant enfant (v2.67.11). */
	/*  🔴 La carte du calendrier a REJOINT `.carte-liste` le 18/08/2026 : c'est
	    elle qui porte le liseré gauche passant au bleu au survol — « plus chouette
	    et discret », et désormais la référence UX du site.

	    Fond, rayon, ombre, marge et transitions viennent donc de `app.css`. Ne
	    reste ici que ce qui est PROPRE à un événement — sinon on redéclare la
	    norme, et la copie diverge au premier ajustement. */
	.carte-evenement {
		display: block;
		padding: 0;
	}
	.carte-evenement.expanded {
		border-color: var(--color-primary, #2563eb);
		box-shadow: 0 0 0 2px color-mix(in srgb, var(--color-primary, #2563eb) 18%, transparent);
	}
	.event-urgent { border-left: 3px solid var(--color-danger); }
	.event-meta { font-size: .8rem; color: var(--color-text-muted); }
	.event-actions { display: flex; gap: .3rem; }
	.ev-expanded-body {
		padding: .6rem .75rem .25rem;
		margin: 0 .9rem;
		font-size: .875rem;
		line-height: 1.6;
		border-top: 1px solid var(--color-border);
	}
</style>
