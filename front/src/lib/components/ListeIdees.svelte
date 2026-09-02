<!--
  La liste des idées — le `{#each}` et la carte, écrits **une seule fois**.

  ## Pourquoi ce composant existe (#515, 02/09/2026)

  L'onglet en rend maintenant **deux** : les idées courantes, et les Archives
  repliées — 30 jours après la décision (retenue, réalisée ou rejetée), règle du
  site portée par `app/utils/archivage.py`.

  🔴 Le premier réflexe est de recopier le bloc `{#each}` sous la section
  repliée : soixante-dix lignes de carte. C'est exactement ce que le rang 1
  interdit, et l'histoire du projet dit pourquoi — le fil des tickets a été rendu
  à la main six fois, et les copies avaient divergé sur les pièces jointes, la
  marge et jusqu'au libellé des boutons (#431).

  Même patron que `ListeAnnonces`, extrait le 18/08 pour la même raison, sur la
  rubrique voisine du même écran.

  ## Ce qui reste chez le parent

  **Le rendu part, les gestes restent.** Voter, changer un état, supprimer,
  répondre : tout cela touche l'API et l'état partagé de la page. Les passer en
  callbacks garde un seul endroit qui parle au serveur.

  ⚠️ Ce composant ne décide PAS de ce qui est archivé : `idee.archivee` est
  calculé par le serveur. Refaire la règle ici en ferait une seconde, et les deux
  trancheraient différemment le jour où le délai change — c'est le bug du
  17/07/2026 sur les actualités, un élément visible dans une vue et pas dans
  l'autre.
-->
<script lang="ts">
	import EnteteCarte from '$lib/components/EnteteCarte.svelte';
	import WorkflowPastilles from '$lib/components/WorkflowPastilles.svelte';
	import Reponses from '$lib/components/Reponses.svelte';
	import { safeHtml } from '$lib/sanitize';
	import { fmtDateShort, isNouveau } from '$lib/date';
	import { estPerimetreParDefaut, perimetreLabel } from '$lib/perimetres';
	import { STATUTS_IDEE, STATUT_IDEE_LABELS } from '$lib/idees';

	/** Les idées à rendre, déjà filtrées et triées par l'appelant. */
	export let idees: any[] = [];
	export let currentUserId: number | undefined = undefined;
	export let estCS = false;
	export let estAdmin = false;
	export let statutClass: (s: string) => string;

	export let onVoter: (id: number) => void;
	export let onChangerStatut: (id: number, statut: string) => void;
	export let onSupprimer: (id: number) => void;
	export let onSignaler: (cibleType: string, cibleId: number) => void;
	export let onRepondre: (id: number, contenu: string) => Promise<void> | void;
	export let onSupprimerReponse: (id: number, reponseId: number) => void;
</script>

{#each idees as idee (idee.id)}
	<div class="idee-card card" id="idee-{idee.id}">
		<button
			class="vote-btn"
			class:voted={idee.mon_vote}
			on:click={() => onVoter(idee.id)}
			title={idee.mon_vote ? 'Retirer mon vote' : 'Voter pour cette idée'}
		>
			<span class="vote-icon">{idee.mon_vote ? '❤️' : '\u{1F90D}'}</span>
			<span class="vote-count">{idee.nb_votes}</span>
		</button>
		<div class="idee-body">
			<!--  🔴 L'EN-TÊTE DU SITE (18/08/2026, signalé à l'écran : « l'état sur une
				      2nde ligne après le titre »). Le titre et le badge d'état partageaient une
				      ligne en `space-between`, seule carte du produit dans ce cas — les quatre
				      autres passent par `EnteteCarte`.

				      ⚠️ L'en-tête vit DANS `.idee-body`, pas au-dessus : le bouton de vote reste
				      à gauche de l'ensemble, il n'est pas un tag. `basculable` reste faux — une
				      idée ne se déplie pas, elle montre tout. -->
			<EnteteCarte titre={idee.titre} date={fmtDateShort(idee.cree_le)}>
				<svelte:fragment slot="titre-suffixe">
					{#if isNouveau(idee.cree_le)}<span class="badge badge-gray idee-neuf">New</span>{/if}
				</svelte:fragment>
				<svelte:fragment slot="tags">
					<span class="badge {statutClass(idee.statut)}"
						>{STATUT_IDEE_LABELS[idee.statut] ?? idee.statut}</span
					>
					{#if !estPerimetreParDefaut(idee.perimetre_cible)}<span class="badge badge-gray"
							>&#x1F539; {perimetreLabel(idee.perimetre_cible)}</span
						>{/if}
				</svelte:fragment>
			</EnteteCarte>
			<div class="idee-desc rich-content clamp-5">{@html safeHtml(idee.description)}</div>
			{#if idee.auteur_id !== currentUserId}
				<button
					class="signaler-inline"
					title="Signaler cette idée au conseil syndical"
					aria-label="Signaler cette idée"
					on:click={() => onSignaler('idee', idee.id)}>🚩</button
				>
			{/if}

			<Reponses
				reponses={idee.reponses ?? []}
				{currentUserId}
				isCS={estCS}
				placeholder="Votre réponse à cette idée…"
				onSubmit={(c) => onRepondre(idee.id, c)}
				onDelete={(rid) => onSupprimerReponse(idee.id, rid)}
				onReport={(rid) => onSignaler('reponse', rid)}
			/>
		</div>
		{#if estCS}
			<div class="idee-actions">
				<!--  Workflow en PASTILLES, jamais un `<select>` nu (R3, #423). -->
				<WorkflowPastilles
					options={STATUTS_IDEE}
					valeur={idee.statut}
					on:choisir={(e) => onChangerStatut(idee.id, e.detail)}
				/>
				{#if estAdmin}
					<button
						class="btn-icon-danger"
						title="Supprimer cette idée"
						on:click={() => onSupprimer(idee.id)}>🗑️</button
					>
				{/if}
			</div>
		{/if}
	</div>
{/each}

<style>
	/*  🔴 Ces règles VOYAGENT avec le balisage qu'elles habillent. Svelte scope
	    les styles au composant qui rend l'élément : les laisser dans la page
	    aurait livré les cartes NUES en production — c'est la panne des pastilles
	    de la v2.67.11, refaite deux fois depuis.

	    `.filters` n'est pas ici : elle vient d'`app.css`, partagée par plusieurs
	    écrans. Trois orphelines sont restées derrière (`.idee-header`,
	    `.idee-titre`, `.idee-actions select`) : leur balisage avait disparu avec
	    `EnteteCarte` et `WorkflowPastilles`, elles n'habillaient plus rien.

	    ⚠️ 29/08/2026 — ce commentaire était FAUX pour `.idee-actions` : son
	    balisage n'avait pas disparu (l. 110), seule la règle `.idee-actions select`
	    l'avait. La rangée sortait donc nue, les pastilles de workflow empilées
	    au-dessus du bouton de suppression au lieu d'être alignées avec.

	    🔴 Personne ne l'a vu parce que `lint:classes-nues` lisait les COMMENTAIRES
	    comme des définitions : cette phrase-ci, qui cite `.idee-actions` pour
	    expliquer son retrait, la faisait passer pour définie. Le contrôle était
	    aveuglé par la documentation de son propre sujet. */
	.idee-actions {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.idee-card {
		display: flex;
		gap: 1rem;
		align-items: flex-start;
		padding: 1rem 1.25rem;
		margin-bottom: 0.5rem;
	}
	.vote-btn {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.2rem;
		background: none;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: 0.5rem 0.6rem;
		cursor: pointer;
		transition: border-color 0.12s;
		min-width: 3.5rem;
	}
	.vote-btn:hover {
		border-color: var(--color-primary);
	}
	.vote-btn.voted {
		border-color: var(--color-primary);
		background: var(--color-primary-light);
	}
	.vote-icon {
		font-size: 1.1rem;
	}
	.vote-count {
		font-size: 0.85rem;
		font-weight: 700;
		color: var(--color-primary);
	}
	.idee-body {
		flex: 1;
	}
	.idee-neuf {
		margin-left: 0.5em;
		font-size: 0.82em;
		font-weight: 500;
		vertical-align: middle;
	}
	.idee-desc {
		font-size: 0.85rem;
		color: var(--color-text-muted);
		margin: 0.2rem 0 0.3rem;
	}
	/*  `:hover` vient de `styles/composants.css` — la redéfinir à l'identique
	    ne servait à rien (29/08/2026). */
</style>
