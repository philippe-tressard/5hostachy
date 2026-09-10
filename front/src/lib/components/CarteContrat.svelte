<!--
  La CARTE D'UN CONTRAT d'entretien — sa ligne de titre, ses actions, son détail
  déplié, et le formulaire qui prend sa place quand on la corrige.

  Extraite de `prestataires/+page.svelte` le 10/09/2026, au fil de l'eau : cet
  écran était à 1 777 lignes et devait accueillir l'édition en place. Le plafond
  de modularité (rang 1) refuse qu'un fichier déjà au-dessus de 500 grossisse, et
  c'est cette carte qui s'en détache le plus proprement — un objet, ses gestes,
  aucun état partagé avec le reste de la page.

  🔴 **La correction s'ouvre À LA PLACE de la carte** (`ux-patterns` §14 ter).
  Arbitré à l'écran après deux essais manqués : la boîte s'ouvrait d'abord en bas
  de page, puis en haut. Les deux déplacent l'utilisateur loin de ce qu'il édite ;
  seule la position de l'objet ne le déplace pas du tout.

  ⚠️ §14 bis n'est pas remis en cause : c'est toujours LA MÊME BOÎTE — même
  composant, même format. Ce qui change est sa position.
-->
<script lang="ts">
	import { documents as documentsApi } from '$lib/api';
	import { frequenceLabel } from '$lib/prestataires';
	import { fmtDateShort } from '$lib/date';
	import { safeHtml } from '$lib/sanitize';
	import FormulaireCreation from './FormulaireCreation.svelte';
	import FormulaireContrat from './FormulaireContrat.svelte';

	export let contrat: any;
	export let prest: any = null;
	export let expanded = false;
	export let enRetard = false;
	export let documents: any[] = [];
	export let peutModifier = false;

	/**  Le contrat en cours de correction — `null` quand aucun ne l'est. La carte
	 *   cède sa place au formulaire quand c'est le sien. */
	export let editContratId: number | null = null;
	export let contratForm: any = undefined;
	export let prestataires: any[] = [];
	export let equipements: readonly { val: string; label: string }[] = [];
	export let submitting = false;

	export let onBasculer: (id: number) => void = () => {};
	export let onModifier: (c: any) => void = () => {};
	export let onArchiver: (id: number) => void = () => {};
	export let onSupprimerDoc: (contratId: number, docId: number) => void = () => {};
	export let onAjouteDoc: (contratId: number) => void = () => {};
	export let onAnnuler: () => void = () => {};
	export let onEnregistrer: () => void = () => {};
	/**  Noter le prestataire depuis la carte du contrat — le geste ne vivait
	 *   QUE dans l'onglet Visites retiré (#603), et un affichage sans son geste
	 *   de saisie ne se voit pas. */
	/**  Les notes dépliées — état LOCAL depuis l'extraction (10/09/2026) : il ne
	 *   concerne que cette carte, alors que le `Set` du parent retenait l'état de
	 *   toutes. Une carte qui sait se déplier n'a pas besoin qu'on le lui dise. */
	let notesOuvertes = false;

	export let onNoter: (prestataireId: number, contratId: number) => void = () => {};
</script>

{#if editContratId === contrat.id}
	<FormulaireCreation titre="Modifier le contrat" cle={editContratId}>
		<FormulaireContrat
			bind:contratForm
			{prestataires}
			{equipements}
			contratId={contrat.id}
			{documents}
			onSupprimer={onSupprimerDoc}
			onAjoute={onAjouteDoc}
			{submitting}
			{onAnnuler}
			{onEnregistrer}
		/>
	</FormulaireCreation>
{:else}
	<!--  L'ancre `contrat-{id}` : le carnet d'entretien y renvoie (#870 → carnet,
     10/09/2026), et `test_liens_front` refuse un lien vers une ancre qu'aucun
     onglet ne rend — il a attrapé celui-ci avant la production. -->
	<div class="carte-liste" class:expanded class:urgent={enRetard} id="contrat-{contrat.id}">
		<div
			class="contrat-row"
			role="button"
			tabindex="0"
			on:click|stopPropagation={() => onBasculer(contrat.id)}
			on:keydown|stopPropagation={(e) => e.key === 'Enter' && onBasculer(contrat.id)}
		>
			<div class="contrat-body-inner">
				<strong class="contrat-titre">{contrat.libelle}</strong>
				{#if prest}
					<span class="contrat-meta">— {prest.nom}</span>
				{:else}
					<!--  Un contrat sans intervenant avait sa propre section, qui le
				      rendait une SECONDE fois : le groupement par équipement
				      retombe déjà sur `type_equipement` quand le prestataire
				      manque. Le fait se dit ici, sur la ligne (#603). -->
					<span class="badge badge-gray" style="font-size:.72rem">sans intervenant</span>
				{/if}
				{#if contrat.numero_contrat}<span class="contrat-meta">🔖 {contrat.numero_contrat}</span
					>{/if}
			</div>
			<div class="contrat-infos">
				{#if contrat.prochaine_visite}
					<div class="contrat-echeance" class:contrat-echeance--retard={enRetard}>
						{enRetard ? '⚠️' : '🗓'}
						{fmtDateShort(contrat.prochaine_visite)}
					</div>
				{:else}
					<div>📅 {fmtDateShort(contrat.date_debut)}</div>
				{/if}
				{#if contrat.frequence_type}
					<span class="badge badge-blue" style="font-size:.75rem">{frequenceLabel(contrat)}</span>
				{/if}
			</div>
			<div class="contrat-meta-right">
				<span class="badge" style="font-size:.8rem">📄 {documents?.length ?? 0}</span>
				<!--  ✏️ puis 🗑️, sur la ligne du titre (`ux-patterns` §3). -->
				{#if peutModifier}
					<button
						class="btn-icon-edit"
						aria-label="Modifier ce contrat"
						title="Modifier"
						on:click|stopPropagation={() => onModifier(contrat)}>&#x270F;&#xFE0F;</button
					>
					<button
						class="btn-icon-danger"
						aria-label="Archiver"
						title="Archiver"
						on:click|stopPropagation={() => onArchiver(contrat.id)}>🗑️</button
					>
				{/if}
				<span class="toggle-arrow">{expanded ? '▲' : '▼'}</span>
			</div>
		</div>
		{#if expanded}
			<div class="contrat-detail-body">
				<div class="contrat-section">
					<div class="contrat-section-title">Infos contrat</div>
					<div class="detail-grid">
						<div>
							<span class="detail-label">Date de début</span>📅 {fmtDateShort(contrat.date_debut)}
						</div>
						{#if contrat.duree_initiale_valeur}<div>
								<span class="detail-label">Durée</span>{contrat.duree_initiale_valeur}
								{contrat.duree_initiale_unite}
							</div>{/if}
						{#if contrat.frequence_type}
							<div><span class="detail-label">Fréquence</span>{frequenceLabel(contrat)}</div>
						{/if}
						{#if contrat.prochaine_visite}<div>
								<span class="detail-label">Prochaine visite</span><span
									style="color:var(--color-primary);font-weight:600"
									>🗓 {fmtDateShort(contrat.prochaine_visite)}</span
								>
							</div>{/if}
					</div>
				</div>
				{#if contrat.notes}
					<div class="contrat-section">
						<div
							class="contrat-section-title clickable"
							role="button"
							tabindex="0"
							on:click|stopPropagation={() => (notesOuvertes = !notesOuvertes)}
							on:keydown|stopPropagation={(e) =>
								(e.key === 'Enter' || e.key === ' ') && (notesOuvertes = !notesOuvertes)}
						>
							Synthèse du ou des contrats {notesOuvertes ? '▲' : '▼'}
						</div>
						{#if notesOuvertes}
							<div class="rich-content" style="font-size:.875rem">
								{@html safeHtml(contrat.notes)}
							</div>
						{/if}
					</div>
				{/if}
				<div class="contrat-section">
					<div class="contrat-section-title">
						📄 Documents ({documents?.length ?? 0})
					</div>
					{#if documents?.length > 0}
						{#each documents as doc (doc.id)}
							<div
								style="display:flex;align-items:center;gap:.5rem;margin-bottom:.3rem;font-size:.85rem;flex-wrap:wrap"
							>
								<a href={documentsApi.downloadUrl(doc.id)} target="_blank"
									>📎 {doc.titre || doc.fichier_nom}</a
								>
								<span style="font-size:.75rem;color:var(--color-text-muted)"
									>{fmtDateShort(doc.publie_le)}</span
								>
								{#if peutModifier}
									<button
										class="btn-icon-danger"
										aria-label="Supprimer"
										title="Supprimer"
										style="margin-left:auto"
										on:click|stopPropagation={() => onSupprimerDoc(contrat.id, doc.id)}>🗑️</button
									>
								{/if}
							</div>
						{/each}
					{:else}
						<p style="font-size:.82rem;color:var(--color-text-muted);margin:0">Aucun document.</p>
					{/if}
				</div>
				{#if peutModifier}
					<div style="display:flex;gap:.4rem;margin-top:.25rem;flex-wrap:wrap">
						<!--  🔴 « Noter » ne vivait QUE dans `CarteVisite`, donc dans le
						      seul onglet Visites : retirer cet onglet sans porter le geste
						      ici aurait rendu la notation d'un prestataire IMPOSSIBLE à
						      saisir, alors que la fiche et le reporting continuaient d'en
						      afficher la moyenne. Un affichage sans son geste de saisie ne
						      se voit pas — rien ne lève, la note reste simplement à jamais
						      celle d'hier (#603).
						      Sans intervenant, il n'y a personne à noter : le bouton
						      n'apparaît pas plutôt que d'ouvrir une modale sans cible. -->
						{#if contrat.prestataire_id}
							<button
								class="btn btn-sm btn-outline contrat-noter"
								on:click|stopPropagation={() => onNoter(contrat.prestataire_id, contrat.id)}
								>⭐ Noter</button
							>
						{/if}
					</div>
				{/if}
			</div>
		{/if}
	</div>
{/if}

<style>
	/*  Ces règles ont SUIVI le balisage (10/09/2026). Svelte scope les styles au
	    composant : les laisser dans la page les rendait inertes ici et orphelines
	    là-bas. C'est la régression de #356, et ce sont `lint:css-orphelin` et
	    `lint:classes-nues` qui l'ont refusée — la relecture, elle, ne l'avait pas
	    vue. */
	.contrat-echeance {
		font-size: 0.82rem;
		font-weight: 600;
		color: var(--color-primary);
	}
	.contrat-echeance--retard {
		color: var(--color-danger);
	}
	.contrat-noter {
		color: #f59e0b;
	}
	.contrat-detail-body {
		padding: 0.75rem 1rem 1rem;
		border-top: 1px solid var(--color-border);
		background: var(--color-bg-secondary, #f8f9fa);
	}
	.contrat-section {
		margin-bottom: 1rem;
	}
	.contrat-section:last-child {
		margin-bottom: 0;
	}
	.contrat-section-title {
		font-size: 0.75rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-text-muted);
		margin-bottom: 0.4rem;
		padding-bottom: 0.25rem;
		border-bottom: 1px solid var(--color-border);
	}
	.contrat-section-title.clickable {
		cursor: pointer;
		user-select: none;
	}
	.contrat-section-title.clickable:hover {
		color: var(--color-primary);
	}
	.contrat-row {
		display: flex;
		gap: 0.75rem;
		align-items: flex-start;
		padding: 0.55rem 0.75rem;
		cursor: pointer;
		transition: background 0.12s;
	}
	.contrat-row:hover {
		background: var(--color-bg-secondary, #f8f9fa);
	}
	.contrat-body-inner {
		flex: 1;
		min-width: 0;
	}
	.contrat-titre {
		font-size: 0.9rem;
	}
	.contrat-meta {
		font-size: 0.78rem;
		color: var(--color-text-muted);
		margin-left: 0.5rem;
	}
	.contrat-infos {
		text-align: right;
		font-size: 0.82rem;
		min-width: 100px;
		flex-shrink: 0;
	}
	.contrat-meta-right {
		display: flex;
		align-items: flex-start;
		gap: 0.3rem;
		flex-shrink: 0;
	}
	.rich-content {
		font-size: 0.85rem;
		line-height: 1.6;
		color: var(--color-text);
		margin-bottom: 0.5rem;
	}
	.rich-content :global(p) {
		margin: 0 0 0.5em;
	}
	.rich-content :global(ul),
	.rich-content :global(ol) {
		padding-left: 1.4em;
		margin: 0 0 0.5em;
	}
	.rich-content :global(strong) {
		font-weight: 600;
	}
	.rich-content :global(em) {
		font-style: italic;
	}
	.contrat-infos {
		min-width: 80px;
	}
</style>
