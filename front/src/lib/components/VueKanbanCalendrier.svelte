<!--
  **La vue Kanban du calendrier** — les affaires en cours, par colonne.

  ## Pourquoi ce composant (#833, 08/09/2026)

  Extrait de `calendrier/+page.svelte` quand le garde-fou de modularité a refusé
  de le laisser grossir (1 045 → 1 120 lignes) en y faisant entrer les tickets
  « Étude & travaux ». Le refus disait vrai : cent cinquante-trois lignes de
  gabarit et soixante-treize de style, qui ne servent qu'à une des deux vues de
  la page.

  ## ⚠️ L'interface est LARGE, et c'est un constat, pas un choix

  Dix-huit props. C'est beaucoup, et c'est le symptôme que la page porte encore
  trop : l'état du kanban (exercice, bâtiment, carte dépliée), ses gestes
  (glisser-déposer, éditer, supprimer) et ses fonctions d'affichage y vivent
  tous. Les descendre ici demanderait de descendre aussi le chargement des
  événements, que la vue Liste partage.

  Le découpage utile suivant est donc **l'état du kanban**, pas ce gabarit — et
  il se fera quand la page sera reprise, pas en le devinant aujourd'hui.
  L'important est que le refus a désigné le bon fichier ; ce qu'il n'a pas dit,
  c'est où s'arrêter.
-->
<script lang="ts">
	import { isAdmin, isCS } from '$lib/stores/auth';
	//  🔴 L'assainisseur vient de sa SOURCE, jamais d'une prop. `lint:html` a
	//  refusé la version qui le recevait de la page : une prop homonyme pourrait
	//  ne rien assainir, et le contrôle ne peut pas le savoir. Il exige donc que
	//  le nom vienne de l'IMPORT — c'est ce qui a démasqué `renderContent` (#429).
	import { safeHtml } from '$lib/sanitize';

	/** Les colonnes déjà rangées — `items` (événements) et `tickets` (#833). */
	export let kanbanCols: any[] = [];
	/** Tous les événements suivis, pour peupler la liste des bâtiments. */
	export let kanbanEvs: any[] = [];

	export let kanbanExercice: number;
	export let kanbanExerciceOptions: number[] = [];
	export let kanbanBatiment = '';
	export let expandedKanbanId: number | null = null;
	/** Non vide = les tickets n'ont pas pu être chargés : le tableau est amputé. */
	export let erreurTicketsKanban = '';
	/** Les bâtiments proposés au filtre — la page les tient déjà. */
	export let batimentOptions: { val: string; label: string }[] = [];
	/** Amorçage des prestataires (CS) — un geste de la page, pas de la vue. */
	export let initPrestataires: () => void;
	export let initLoading = false;

	//  Les gestes et les formats viennent de la page : ils touchent à des données
	//  qu'elle seule détient (la liste des événements, les appels d'API).
	export let onDragOver: (e: DragEvent) => void;
	export let onDrop: (e: DragEvent, colId: string) => void;
	export let onDragStart: (e: DragEvent, id: number) => void;
	export let startEdit: (ev: any) => void;
	export let deleteEv: (id: number) => void;
	//  ⚠️ Signature volontairement LARGE : le type de retour vit dans la page
	//  (`PastillePerimetre`), et le redéclarer ici en ferait une seconde écriture
	//  libre de diverger. Ce composant n'en lit que trois champs.
	export let perimetreTags: (p: any) => any[];
	export let yearColor: (annee: number) => string;
	export let typeLabel: (t: string) => string;
	export let formatDate: (d: string) => string;
</script>

<!-- ── Kanban Trello-like ────────────────────────────────── -->
<div class="kanban-toolbar">
	<label class="kanban-exercice-label">
		Exercice :
		<select bind:value={kanbanExercice} class="kanban-exercice-select">
			{#each kanbanExerciceOptions as y (y)}<option value={y}>{y}</option>{/each}
		</select>
	</label>
	<label class="kanban-exercice-label">
		Bâtiment :
		<select bind:value={kanbanBatiment} class="kanban-exercice-select">
			{#each batimentOptions as b (b.val)}<option value={b.val}>{b.label}</option>{/each}
		</select>
	</label>
	<span class="kanban-count-total">{kanbanEvs.length} affaire{kanbanEvs.length > 1 ? 's' : ''}</span
	>
	{#if $isCS}
		<button class="btn btn-sm kanban-init-btn" on:click={initPrestataires} disabled={initLoading}>
			{initLoading ? '⏳ Création…' : '⚙️ Init. prestataires'}
		</button>
	{/if}
</div>
<div class="kanban">
	{#each kanbanCols as col (col.id)}
		{@const items = col.items}
		<div class="kanban-col" on:dragover={onDragOver} on:drop={(e) => onDrop(e, col.id)} role="list">
			<div class="kanban-col-header" style="border-top-color:{col.color}">
				<span>{col.label}</span>
				<span class="kanban-count">{items.length + col.tickets.length}</span>
			</div>
			{#if items.length === 0 && col.tickets.length === 0}
				<p class="kanban-empty">Aucune affaire</p>
			{:else}
				{#each items as ev (ev.id)}
					<div
						class="kanban-card card"
						class:event-urgent={ev.type === 'coupure'}
						class:kanban-card-expanded={expandedKanbanId === ev.id}
						draggable={$isCS && expandedKanbanId !== ev.id ? 'true' : 'false'}
						on:dragstart={(e) => onDragStart(e, ev.id)}
						on:click={() => (expandedKanbanId = expandedKanbanId === ev.id ? null : ev.id)}
						on:keydown={(e) => {
							if (e.key === 'Enter' || e.key === ' ') {
								e.preventDefault();
								expandedKanbanId = expandedKanbanId === ev.id ? null : ev.id;
							}
						}}
						role="button"
						tabindex="0"
					>
						<!-- Tags périmètre + année (uniquement si année ≠ exercice sélectionné) -->
						<div class="kanban-card-tags">
							{#each perimetreTags(ev.perimetre) as tag (tag.code)}
								<span class="kb-tag" style="background:{tag.color}">{tag.label}</span>
							{/each}
							<span
								class="kb-tag"
								style="background:{yearColor(new Date(ev.debut).getFullYear())}"
								title="Événement de {new Date(ev.debut).getFullYear()}"
								>{new Date(ev.debut).getFullYear()}</span
							>
						</div>
						{#if ev.prestataire_nom}<span class="kanban-card-prest">{ev.prestataire_nom}</span>{/if}
						<strong class="kanban-card-titre">{ev.titre}</strong>
						<div class="kanban-card-footer">
							<span class="kanban-card-type">{typeLabel(ev.type)}</span>
							{#if $isCS}
								<div
									class="kanban-card-actions"
									role="presentation"
									on:click|stopPropagation
									on:keydown|stopPropagation
								>
									<button
										class="btn-icon-edit"
										aria-label="Modifier"
										title="Modifier"
										on:click={() => startEdit(ev)}>✏️</button
									>
									{#if $isAdmin}
										<button
											class="btn-icon-danger"
											aria-label="Supprimer définitivement"
											title="Supprimer définitivement"
											on:click={() => deleteEv(ev.id)}>&#x1F5D1;️</button
										>
									{/if}
								</div>
							{/if}
						</div>
						{#if expandedKanbanId === ev.id}
							<div
								class="kanban-card-detail"
								role="presentation"
								on:click|stopPropagation
								on:keydown|stopPropagation
							>
								<div class="kanban-card-detail-row">
									📅 {formatDate(ev.debut)}{#if ev.fin}
										→ {formatDate(ev.fin)}{/if}
								</div>
								{#if ev.lieu}<div class="kanban-card-detail-row">📍 {ev.lieu}</div>{/if}
								{#if ev.description}
									<div class="kanban-card-detail-desc rich-content">
										{@html safeHtml(ev.description)}
									</div>
								{/if}
							</div>
						{/if}
					</div>
				{/each}
			{/if}

			<!--  🔴 LES TICKETS « ÉTUDE & TRAVAUX » (#833) — lus, jamais copiés.
			      Leur statut EST leur colonne : aucun second champ d'état, sinon
			      deux notions de suivi sur le même objet se contrediraient.

			      ⚠️ **Non déplaçables à la souris**, et c'est déclaré, pas oublié.
			      Faire glisser une carte devrait changer le STATUT du ticket —
			      donc écrire une évolution, prévenir son auteur, et respecter la
			      liste blanche du serveur. Ce chemin d'écriture existe déjà sur la
			      fiche du ticket, avec son historique ; le doubler ici en
			      raccourci serait une seconde façon de faire avancer un ticket,
			      et c'est exactement ce que ce lot retire ailleurs. Le lien mène
			      donc là où le geste est complet. -->
			{#each col.tickets as ticket (ticket.id)}
				<a class="kanban-card card kanban-card-ticket" href="/tickets/{ticket.id}">
					<div class="kanban-card-tags">
						<span class="kb-tag kb-tag-ticket">🎫 Ticket</span>
					</div>
					<strong class="kanban-card-titre">{ticket.titre}</strong>
					<div class="kanban-card-footer">
						<span class="kanban-card-type">#{ticket.numero}</span>
					</div>
				</a>
			{/each}
		</div>
	{/each}
</div>
{#if erreurTicketsKanban}
	<!--  L'échec se DIT : un tableau amputé des tickets ressemble trait pour
	      trait à un tableau où il n'y en a aucun. -->
	<p class="kanban-erreur-tickets">
		Les tickets suivis n’ont pas pu être chargés — le tableau est incomplet. {erreurTicketsKanban}
	</p>
{/if}

<style>
	.kanban-toolbar {
		display: flex;
		align-items: center;
		gap: 1rem;
		margin-bottom: 0.75rem;
		flex-wrap: wrap;
	}
	.kanban-exercice-label {
		font-size: 0.85rem;
		font-weight: 600;
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}
	.kanban-exercice-select {
		padding: 0.25rem 0.5rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
		font-size: 0.85rem;
	}
	.kanban-init-btn {
		margin-left: auto;
		font-size: 0.8rem;
		padding: 0.3rem 0.75rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
		cursor: pointer;
		white-space: nowrap;
	}
	.kanban-init-btn:hover:not(:disabled) {
		background: var(--color-primary);
		color: #fff;
		border-color: var(--color-primary);
	}
	.kanban-init-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.kb-tag {
		text-transform: lowercase;
	}
	.kanban-card-expanded {
		cursor: default;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
	}
	.kanban-card-detail {
		border-top: 1px solid var(--color-border);
		margin-top: 0.3rem;
		padding-top: 0.35rem;
	}
	.kanban-card-detail-row {
		font-size: 0.72rem;
		color: var(--color-text-muted);
		line-height: 1.5;
	}
	.kanban-card-detail-desc {
		font-size: 0.72rem;
		line-height: 1.5;
		margin-top: 0.25rem;
	}
	.kanban-card:active {
		cursor: grabbing;
	}
	.kanban-card[draggable='true']:hover {
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
	}
	.kanban-card-type {
		font-size: 0.72rem;
		font-weight: 600;
		color: var(--color-text-muted);
	}
	/*  La carte d'un TICKET au kanban (#833) — même gabarit que celle d'un
	    événement, un liseré de plus pour dire que ce n'en est pas un, et pas de
	    curseur de déplacement puisqu'elle ne se déplace pas. */
	.kanban-card-ticket {
		display: block;
		border-left: 3px solid var(--color-primary);
		text-decoration: none;
		color: inherit;
	}
	.kb-tag-ticket {
		background: var(--color-primary);
	}
	.kanban-erreur-tickets {
		font-size: 0.875rem;
		color: #b07d1e;
		font-weight: 500;
		padding: 0.5rem 0;
	}
</style>
