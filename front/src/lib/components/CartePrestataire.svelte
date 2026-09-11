<!--
  La CARTE D'UN PRESTATAIRE — sa ligne de titre, ses actions, son détail déplié,
  et le formulaire qui prend sa place quand on le corrige.

  Extraite de `prestataires/+page.svelte` le 11/09/2026, pour la même raison que
  `CarteContrat` la veille et **sur exactement le même signalement** : *« le mode
  édition (crayon) ne respecte pas le standard UX déployé sur le reste du site,
  par exemple sur tickets »*. Le crayon était dans la carte, la boîte s'ouvrait en
  tête de liste — l'objet corrigé quittait sa place sous les yeux.

  🔴 **La correction s'ouvre DANS LA CARTE, à la place de son corps.** L'en-tête
  reste, avec son titre et ses actions ; le mode se lit sur le crayon
  (`aria-pressed`, `ux-patterns` §13 bis) ; aucune `cle` n'est nécessaire, rien
  n'a bougé donc il n'y a rien à ramener à l'écran.

  ⚠️ **Pourquoi un FICHIER et pas un bloc de plus dans la page** : le geste exige
  deux rendus de `FormulaireCreation` — la création en tête de page, la correction
  dans la carte —, et `lint:geste-edition` (règle B) refuse deux rendus éloignés
  dans un même fichier, à raison : c'est la signature du formulaire qui s'ouvre
  loin de son geste. Séparer la carte n'est donc pas un contournement du contrôle,
  c'est ce qui rend la règle vraie des deux côtés.
-->
<script lang="ts">
	import { fmtDateShort } from '$lib/date';
	import { equipLabel } from '$lib/prestataires';
	import { nomAffiche } from '$lib/noms';
	import BoutonLien from './BoutonLien.svelte';
	import NotationsPrestataire from './NotationsPrestataire.svelte';
	import FormulaireCreation from './FormulaireCreation.svelte';
	import ChampsPrestataire from './ChampsPrestataire.svelte';
	import PiedFormulaire from './PiedFormulaire.svelte';

	export let p: any;
	export let cs: any[] = [];
	export let nextVisit: string | null = null;
	export let notations: any[] = [];
	export let expanded = false;
	export let compactPrests = false;
	export let peutModifier = false;
	export let telephonesDe: (t: string) => string[] = () => [];
	/**  Le libellé d'un type — la table vit dans la page, qui l'administre. */
	export let typeLabel: (v: string) => string = (v) => v;

	/**  Le prestataire en cours de correction — la carte cède sa place au
	 *   formulaire quand c'est le sien. */
	export let editPrestId: number | null = null;
	export let prestForm: any = undefined;
	export let prestContacts: any[] = [];
	export let typesPrestataire: readonly { val: string; label: string; desc?: string }[] = [];
	export let equipements: readonly { val: string; label: string }[] = [];
	export let submitting = false;

	export let onBasculer: (id: number) => void = () => {};
	export let onModifier: (p: any) => void = () => {};
	export let onArchiver: (id: number) => void = () => {};
	export let onAnnuler: () => void = () => {};
	export let onEnregistrer: () => void = () => {};

	$: enEdition = editPrestId === p.id;
</script>

<div class="carte-liste" class:expanded={expanded || enEdition} id="presta-{p.id}">
	<div
		class="prest-header"
		role="button"
		tabindex="0"
		on:click={() => onBasculer(p.id)}
		on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && onBasculer(p.id)}
	>
		<div class="prest-main">
			<strong class="prest-nom">{p.nom}</strong>
			<span class="badge badge-type" style="margin-left:.5rem">{typeLabel(p.type_prestataire)}</span
			>
			<span class="badge badge-blue" style="margin-left:.25rem">{equipLabel(p.specialite)}</span>
			<NotationsPrestataire resume {notations} />
		</div>
		{#if !compactPrests || expanded}
			<div class="prest-contacts">
				{#if p.contacts && p.contacts.length > 0}
					{#each p.contacts as c (c.id ?? c)}
						<span class="prest-contact">
							📞 {c.telephone}{#if c.prenom || c.nom}&nbsp;— {nomAffiche(
									c,
								)}{/if}{#if c.fonction}&nbsp;({c.fonction}){/if}
						</span>
					{/each}
				{:else if p.telephone}
					{#each telephonesDe(p.telephone) as tel (tel)}
						<span class="prest-contact">📞 {tel.trim()}</span>
					{/each}
				{/if}
				{#if p.email}<span class="prest-contact">✉️ {p.email}</span>{/if}
			</div>
		{/if}
		<div class="prest-meta">
			{#if !compactPrests || expanded}
				<span class="badge badge-gray">{cs.length} contrat{cs.length !== 1 ? 's' : ''}</span>
				{#if nextVisit}<span class="badge" style="font-size:.75rem;color:var(--color-primary)"
						>🗓 {fmtDateShort(nextVisit)}</span
					>{/if}
			{/if}
			<BoutonLien ancre="presta-{p.id}" quoi="la fiche prestataire" />
			{#if peutModifier}
				<button
					class="btn-icon-edit"
					aria-label={enEdition ? 'Annuler la correction' : 'Modifier'}
					title={enEdition ? 'Annuler la correction' : 'Modifier'}
					aria-pressed={enEdition}
					on:click|stopPropagation={() => (enEdition ? onAnnuler() : onModifier(p))}>✏️</button
				>
				<button
					class="btn-icon-danger"
					aria-label="Archiver"
					title="Archiver"
					on:click|stopPropagation={() => onArchiver(p.id)}>🗑️</button
				>
			{/if}
			<span class="toggle-arrow">{expanded || enEdition ? '▲' : '▼'}</span>
		</div>
	</div>
	{#if enEdition}
		<!--  Le corps ne referme pas la carte : sans `stopPropagation`, un clic
		      dans le formulaire remonterait à la ligne de titre et replierait ce
		      qu'on est en train de corriger (`ux-patterns` §3). -->
		<div class="prest-body" role="presentation" on:click|stopPropagation on:keydown|stopPropagation>
			<!--  `encadre={false}` : la carte EST le cadre, et sa ligne de titre en
			      est l'en-tête — une carte dans une carte, c'est deux bordures pour
			      un seul objet (#425). -->
			<FormulaireCreation titre="Modifier le prestataire" encadre={false}>
				<form on:submit|preventDefault={onEnregistrer}>
					<ChampsPrestataire bind:prestForm bind:prestContacts {typesPrestataire} {equipements} />
					<PiedFormulaire enCours={submitting} on:annule={onAnnuler} />
				</form>
			</FormulaireCreation>
		</div>
	{:else if expanded}
		<div class="prest-body">
			<div class="detail-grid">
				{#if p.telephone}
					<div>
						<span class="detail-label">Téléphone</span>
						{#each telephonesDe(p.telephone) as tel (tel)}
							<span style="display:block">📞 {tel.trim()}</span>
						{/each}
					</div>
				{/if}
				{#if p.email}<div><span class="detail-label">Email</span>✉️ {p.email}</div>{/if}
				<div><span class="detail-label">Contrats</span>{cs.length}</div>
				{#if nextVisit}<div>
						<span class="detail-label">Prochaine visite</span><span
							style="color:var(--color-primary);font-weight:600">🗓 {fmtDateShort(nextVisit)}</span
						>
					</div>{/if}
			</div>
			<!--  Les avis, enfin visibles un par un (#807). L'écran n'en montrait
			      que la MOYENNE, dans un badge : impossible de savoir qui avait
			      noté quoi, et donc impossible de retirer une note posée par
			      erreur — alors que l'endpoint de suppression existait. -->
			<NotationsPrestataire {notations} peutSupprimer={peutModifier} on:supprimee />
		</div>
	{/if}
</div>

<style>
	.prest-header {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.85rem 1rem;
		cursor: pointer;
		flex-wrap: wrap;
	}
	.prest-main {
		display: flex;
		align-items: center;
		min-width: 160px;
		flex-wrap: wrap;
		gap: 0.25rem;
	}
	.prest-nom {
		font-size: 0.95rem;
	}
	.badge-type {
		background: var(--color-bg-secondary, #f0f0f0);
		color: var(--color-text);
		font-size: 0.75rem;
	}
	.prest-contacts {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem 0.75rem;
		flex: 1;
	}
	.prest-contact {
		font-size: 0.82rem;
		color: var(--color-text-muted);
	}
	.prest-meta {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		margin-left: auto;
	}
	.prest-body {
		padding: 0.25rem 1rem 1rem 1rem;
		border-top: 1px solid var(--color-border);
	}

	@media (max-width: 600px) {
		.prest-header {
			gap: 0.5rem;
		}
	}
</style>
