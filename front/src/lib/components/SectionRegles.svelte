<!--
  Les RÈGLES & RECOMMANDATIONS de la résidence — couleur des menuiseries, essence
  des haies, ce que la copropriété a décidé et qu'aucun règlement ne dit.

  Extraites de `residence/+page.svelte` le 10/09/2026, au fil de l'eau : cet écran
  était à 1 029 lignes et devait accueillir sa barre d'onglets pour le carnet
  d'entretien. Le plafond de modularité (rang 1) refuse qu'un fichier déjà
  au-dessus de 500 grossisse, et ce bloc est celui qui s'en détache le plus
  proprement — une notion autonome, son endpoint à elle, aucun état partagé avec
  les documents, les plans ou les diagnostics.

  ⚠️ Le balisage part AVEC ses règles CSS. C'est la régression de #356, notée dans
  `ux-patterns` : « le balisage est parti et ses règles sont restées derrière ».
  Svelte scope les styles au composant, donc les laisser dans la page les rendrait
  inertes ici et orphelines là-bas — et `svelte-check` est le seul à le dire.

  Il CHARGE ses propres règles plutôt que de les recevoir en propriété : elles ne
  servent qu'ici, et les faire transiter par l'écran aurait laissé dans celui-ci
  l'état, l'appel et la gestion d'erreur — c'est-à-dire la moitié de ce qu'on
  cherchait à en sortir.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { reglesResidence as reglesApi, ApiError } from '$lib/api';
	import { confirmer, SUPPRESSION } from '$lib/confirmation';
	import { toast } from '$lib/components/Toast.svelte';
	import { isCS } from '$lib/stores/auth';
	import EtatListe from './EtatListe.svelte';
	import FormulaireDocument from './FormulaireDocument.svelte';
	import { essayer } from '$lib/chargement';

	let regles: any[] = [];
	let eRegles = '';
	let chargement = true;

	let showRegleForm = false;
	let editingRegleId: number | null = null;
	let regleTitre = '';
	let regleContenu = '';
	let savingRegle = false;

	onMount(async () => {
		[regles, eRegles] = await essayer<any[]>(reglesApi.list(), []);
		chargement = false;
	});

	// ── Règles & Recommandations ───────────────────────────────────────────────
	function openRegleForm(regle?: any) {
		if (regle) {
			editingRegleId = regle.id;
			regleTitre = regle.titre;
			regleContenu = regle.contenu;
		} else {
			editingRegleId = null;
			regleTitre = '';
			regleContenu = '';
		}
		showRegleForm = true;
	}

	async function saveRegle() {
		if (!regleTitre.trim()) return;
		savingRegle = true;
		try {
			if (editingRegleId) {
				const updated = await reglesApi.update(editingRegleId, {
					titre: regleTitre.trim(),
					contenu: regleContenu.trim(),
				});
				regles = regles.map((r) => (r.id === editingRegleId ? { ...r, ...updated } : r));
				toast('success', 'Règle mise à jour');
			} else {
				const created = await reglesApi.create({
					titre: regleTitre.trim(),
					contenu: regleContenu.trim(),
				});
				regles = [...regles, created];
				toast('success', 'Règle ajoutée');
			}
			showRegleForm = false;
			regleTitre = '';
			regleContenu = '';
			editingRegleId = null;
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			savingRegle = false;
		}
	}

	async function deleteRegle(id: number) {
		if (!(await confirmer(SUPPRESSION('Cette règle')))) return;
		try {
			await reglesApi.remove(id);
			regles = regles.filter((r) => r.id !== id);
			toast('success', 'Règle supprimée');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}
</script>

<!-- ── Section : Règles & Recommandations ──────────────────────────── -->
<section style="margin-bottom:2.5rem">
	<div class="section-header">
		<h2 class="section-title">&#x1F4CB; Règles & Recommandations</h2>
		{#if $isCS}
			<button class="btn btn-sm" on:click={() => openRegleForm()}>+ Ajouter</button>
		{/if}
	</div>

	{#if showRegleForm}
		<FormulaireDocument
			edition={editingRegleId !== null}
			intitule={editingRegleId ? 'Modifier la règle' : 'Ajouter une règle'}
			bind:titre={regleTitre}
			placeholderTitre="Ex : RAL menuiseries façade bâtiment A"
			avecFichier={false}
			enregistrement={savingRegle}
			complet={!!regleTitre.trim()}
			on:annuler={() => (showRegleForm = false)}
			on:enregistrer={saveRegle}
		>
			<label class="field" for="regle-contenu" slot="description">
				Détail / valeur
				<textarea
					id="regle-contenu"
					bind:value={regleContenu}
					placeholder="Ex : Façade extérieure RAL 6021 vert clair"
					rows="3"></textarea>
			</label>
		</FormulaireDocument>
	{/if}

	<EtatListe
		{chargement}
		compact
		erreur={eRegles}
		vide={regles.length === 0}
		messageVide="Aucune règle ajoutée."
	>
		<div class="doc-list">
			{#each regles as regle (regle.id)}
				<div class="doc-row card">
					<div class="doc-info" style="flex-direction:column;align-items:flex-start;gap:.25rem">
						<span class="doc-titre">{regle.titre}</span>
						{#if regle.contenu}
							<span style="font-size:.85rem;color:var(--color-text-muted);white-space:pre-wrap"
								>{regle.contenu}</span
							>
						{/if}
					</div>
					{#if $isCS}
						<div class="doc-actions">
							<button
								class="btn-icon-edit"
								aria-label="Modifier"
								title="Modifier"
								on:click={() => openRegleForm(regle)}>✏️</button
							>
							<button
								class="btn-icon-danger"
								aria-label="Supprimer"
								title="Supprimer"
								on:click={() => deleteRegle(regle.id)}>&#x1F5D1;️</button
							>
						</div>
					{/if}
				</div>
			{/each}
		</div>
	</EtatListe>
</section>
