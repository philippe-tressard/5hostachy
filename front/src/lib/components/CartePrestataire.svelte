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
	import EnteteCarte from './EnteteCarte.svelte';
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

<!--  🔴 L'en-tête passe par `EnteteCarte` (12/09/2026) — comme les ONZE autres
      cartes du site. Il était écrit à la main ici, et il en portait les deux
      défauts que ce composant existe pour supprimer :

        • le NOM partageait sa ligne avec les badges de type, de spécialité et la
          note. Sur un téléphone, les badges ayant une largeur fixe et la ligne
          étant en `flex`, c'est le nom qui se réduisait à trois points — on
          lisait une liste de prestataires sans savoir lesquels.
        • le geste était SYMÉTRIQUE : le conteneur portait `role="button"`, donc
          la carte dépliée se refermait au moindre clic dans son corps, et la
          sélection de texte était interceptée. La norme du 18/08 est
          asymétrique — repliée, toute la carte ouvre ; dépliée, seul le titre
          referme.

      Le chevron suit : `›` qui pivote, comme partout, et non `▲/▼` — deux formes
      pour un même signal, c'est ce que `ux-patterns` §0 appelle une décision
      qu'on reprend à chaque écran. -->
<div
	class="carte-liste"
	class:expanded={expanded || enEdition}
	id="presta-{p.id}"
	role="presentation"
	on:click={() => {
		if (!expanded && !enEdition) onBasculer(p.id);
	}}
>
	<EnteteCarte
		titre={p.nom}
		date={nextVisit && (!compactPrests || expanded) ? fmtDateShort(nextVisit) : ''}
		basculable
		on:toggle={() => onBasculer(p.id)}
	>
		<svelte:fragment slot="tags">
			<span class="badge badge-type">{typeLabel(p.type_prestataire)}</span>
			<span class="badge badge-blue">{equipLabel(p.specialite)}</span>
			<NotationsPrestataire resume {notations} />
			{#if !compactPrests || expanded}
				<span class="badge badge-gray">{cs.length} contrat{cs.length !== 1 ? 's' : ''}</span>
			{/if}
		</svelte:fragment>

		<svelte:fragment slot="actions">
			<BoutonLien ancre="presta-{p.id}" quoi="la fiche prestataire" />
			{#if peutModifier}
				<!--  `aria-pressed` : le mode se lit sur l'icône qui l'a ouvert
				      (`ux-patterns` §13 bis), jamais sur un titre au-dessus. -->
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
		</svelte:fragment>

		<svelte:fragment slot="chevron"
			><span class="chevron" class:open={expanded || enEdition}>›</span></svelte:fragment
		>
	</EnteteCarte>

	<!--  Les contacts sont l'APERÇU de la carte : ils viennent sous l'en-tête, à
	      la place que le modèle leur donne, et non serrés dans sa ligne de titre. -->
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
					<ChampsPrestataire
						bind:prestForm
						bind:prestContacts
						{typesPrestataire}
						{equipements}
						etat="edition"
					/>
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
	/*  🔴 Cinq règles ont disparu avec l'en-tête écrit à la main (12/09/2026) :
	    `.prest-header`, `.prest-main`, `.prest-nom`, `.prest-meta` et leur point
	    de rupture à 600 px. Elles décrivaient une disposition que `EnteteCarte`
	    porte désormais — et le point de rupture avec, ce qui est précisément R1 :
	    la responsivité appartient au squelette, pas à chaque carte.

	    ⚠️ Le style part AVEC le balisage. Laissé derrière, il ne lève rien à
	    l'exécution : `lint:css-orphelin` et `svelte-check` sont les seuls à le
	    voir, et c'est le défaut qui a été repris quatre fois cette semaine. */
	.badge-type {
		background: var(--color-bg-secondary, #f0f0f0);
		color: var(--color-text);
		font-size: 0.75rem;
	}
	/*  L'aperçu de la carte : les contacts, sous l'en-tête. */
	.prest-contacts {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem 0.75rem;
		padding: 0 0.9rem 0.6rem;
	}
	.prest-contact {
		font-size: 0.82rem;
		color: var(--color-text-muted);
	}
	.prest-body {
		padding: 0.25rem 1rem 1rem 1rem;
		border-top: 1px solid var(--color-border);
	}
</style>
