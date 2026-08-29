<!--
  L'onglet **Boîte à idées** de la Communauté — son formulaire de dépôt, ses
  filtres d'état et sa liste.

  ## Pourquoi il existe (#519)

  La page `sondages/+page.svelte` porte TROIS onglets et n'en avait extrait qu'un
  seul (`OngletAnnonces`). Le garde-fou de modularité a refusé de la laisser
  grossir en recevant les états d'erreur de #519 — et il disait vrai : une page
  de 500 lignes qui rend trois rubriques n'a pas un problème de taille, elle a un
  problème de découpage. Celui-ci rétablit la symétrie.

  ## Ce qui reste chez le parent, et pourquoi

  **Le rendu part, les gestes restent.** Voter, changer un état, supprimer,
  répondre : tout cela touche l'API et l'état partagé de la page (la liste est
  rechargée après chaque action). Les passer en callbacks garde un seul endroit
  qui parle au serveur — dupliquer les appels ici donnerait deux vérités sur
  l'état d'une idée.
-->
<script lang="ts">
	import FormulaireIdee from '$lib/components/FormulaireIdee.svelte';
	import EnteteCarte from '$lib/components/EnteteCarte.svelte';
	import WorkflowPastilles from '$lib/components/WorkflowPastilles.svelte';
	import Reponses from '$lib/components/Reponses.svelte';
	import EtatListe from '$lib/components/EtatListe.svelte';
	import { safeHtml } from '$lib/sanitize';
	import { fmtDateShort, isNouveau } from '$lib/date';
	import { estPerimetreParDefaut, perimetreLabel } from '$lib/perimetres';
	import { STATUTS_IDEE, STATUT_IDEE_LABELS, STATUTS_IDEE_FILTRE } from '$lib/idees';

	export let idees: any[] = [];
	export let chargement = false;
	/** Non vide = on n'a PAS pu charger. Distinct de « chargé et vide » (#519). */
	export let erreur = '';
	export let filtreStatut = '';
	export let showForm = false;
	export let currentUserId: number | undefined = undefined;
	export let estCS = false;
	export let estAdmin = false;
	export let statutClass: (s: string) => string;

	//  Les gestes vivent chez le parent : c'est lui qui parle à l'API et qui
	//  recharge la liste. Voir l'en-tête.
	export let onVoter: (id: number) => void;
	export let onChangerStatut: (id: number, statut: string) => void;
	export let onSupprimer: (id: number) => void;
	export let onSignaler: (cibleType: string, cibleId: number) => void;
	export let onRepondre: (id: number, contenu: string) => Promise<void> | void;
	export let onSupprimerReponse: (id: number, reponseId: number) => void;
</script>

{#if showForm}
	<FormulaireIdee on:cree on:annule />
{/if}

<div class="filters">
	{#each STATUTS_IDEE_FILTRE as s}
		<button class="btn btn-sm" class:btn-primary={filtreStatut === s.val}
			on:click={() => (filtreStatut = s.val)}>{s.label}</button>
	{/each}
</div>

<EtatListe {chargement} {erreur} vide={idees.length === 0}
	titreErreur="Impossible d'afficher les idées"
	titreVide="Aucune idée pour l'instant"
	messageVide="Soyez le premier à proposer une idée !">
	{#each idees as idee (idee.id)}
		<div class="idee-card card" id="idee-{idee.id}">
			<button class="vote-btn" class:voted={idee.mon_vote} on:click={() => onVoter(idee.id)}
				title={idee.mon_vote ? 'Retirer mon vote' : 'Voter pour cette idée'}>
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
						{#if isNouveau(idee.cree_le, idee.mis_a_jour_le)}<span class="badge badge-gray idee-neuf">New</span>{/if}
					</svelte:fragment>
					<svelte:fragment slot="tags">
						<span class="badge {statutClass(idee.statut)}">{STATUT_IDEE_LABELS[idee.statut] ?? idee.statut}</span>
						{#if !estPerimetreParDefaut(idee.perimetre_cible)}<span class="badge badge-gray">&#x1F539; {perimetreLabel(idee.perimetre_cible)}</span>{/if}
					</svelte:fragment>
				</EnteteCarte>
				<div class="idee-desc rich-content clamp-5">{@html safeHtml(idee.description)}</div>
				{#if idee.auteur_id !== currentUserId}
					<button class="signaler-inline" title="Signaler cette idée au conseil syndical"
						aria-label="Signaler cette idée" on:click={() => onSignaler('idee', idee.id)}>🚩</button>
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
					<WorkflowPastilles options={STATUTS_IDEE} valeur={idee.statut}
						on:choisir={(e) => onChangerStatut(idee.id, e.detail)} />
					{#if estAdmin}
						<button class="btn-icon-danger" title="Supprimer cette idée"
							on:click={() => onSupprimer(idee.id)}>🗑️</button>
					{/if}
				</div>
			{/if}
		</div>
	{/each}
</EtatListe>

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
	.idee-actions { display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; }
	.idee-card { display: flex; gap: 1rem; align-items: flex-start; padding: 1rem 1.25rem; margin-bottom: .5rem; }
	.vote-btn { display: flex; flex-direction: column; align-items: center; gap: .2rem; background: none; border: 1px solid var(--color-border); border-radius: var(--radius); padding: .5rem .6rem; cursor: pointer; transition: border-color .12s; min-width: 3.5rem; }
	.vote-btn:hover { border-color: var(--color-primary); }
	.vote-btn.voted { border-color: var(--color-primary); background: var(--color-primary-light); }
	.vote-icon { font-size: 1.1rem; }
	.vote-count { font-size: .85rem; font-weight: 700; color: var(--color-primary); }
	.idee-body { flex: 1; }
	.idee-neuf { margin-left: .5em; font-size: .82em; font-weight: 500; vertical-align: middle; }
	.idee-desc { font-size: .85rem; color: var(--color-text-muted); margin: .2rem 0 .3rem; }
	.signaler-inline:hover { opacity: 1; color: var(--color-danger); }
</style>
