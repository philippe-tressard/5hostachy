<!--
  L'onglet **Consommations** de l'écran Prestataires : les compteurs de la
  résidence, leurs relevés, et la saisie d'un nouveau relevé.

  ## Pourquoi ce composant (11/09/2026)

  `prestataires/+page.svelte` était à 1 528 lignes, et le garde-fou de modularité
  (rang 1) a refusé les lignes qu'ajoutait le geste ✨ de synthèse d'un contrat.
  Trois réponses possibles : découper, remonter la règle d'un cran, **jamais
  raboter**. Celle-ci est un découpage franc — un onglet entier, son état et ses
  appels réseau, rien de partagé avec les contrats ni l'annuaire.

  C'est la dette n° 2 de l'issue #779, après l'administration.

  Même forme que les onglets d'administration : l'état vit ici, la page ne garde
  que le choix de l'onglet.
-->
<script lang="ts">
	import { prestataires as prestApi, ApiError } from '$lib/api';
	import { isCS } from '$lib/stores/auth';
	import { toast } from '$lib/components/Toast.svelte';
	import { SUPPRESSION, confirmerPuis } from '$lib/confirmation';
	import { fmtDayMonth } from '$lib/date';
	import FichiersUpload from '$lib/components/FichiersUpload.svelte';
	import FormulaireCreation from '$lib/components/FormulaireCreation.svelte';
	import PiedFormulaire from '$lib/components/PiedFormulaire.svelte';

	/** L'annuaire des prestataires — la page le charge déjà, on ne le recharge pas. */
	export let prestataires: any[] = [];

	// ── Consommations ─────────────────────────────────────────────
	let compteurConfigs: any[] = [];
	let typeCompteur = '';
	let releves: any[] = [];
	let releveLoading = false;
	/**  🔴 L'action primaire d'un onglet est rendue par l'EN-TÊTE DE PAGE, pas par
	 *   l'onglet (`ux-patterns` R1 : le squelette porte titre et action primaire).
	 *   L'onglet, lui, possède l'ÉTAT du formulaire — c'est lui qui sait ce qu'on
	 *   saisit. Les deux se rejoignent par un `bind:`, comme `OngletSmtp` remonte
	 *   la signature des e-mails à sa page.
	 *
	 *   ⚠️ Ne pas déplacer le bouton ici : il serait alors au-dessus du contenu et
	 *   plus dans la barre, et les six autres écrans qui suivent R1 deviendraient
	 *   la minorité. */
	export let showReleveForm = false;
	/** Le libellé que le bouton de page affiche — il nomme le compteur choisi. */
	export let libelleBouton = 'Nouveau relevé';
	let editReleveId: number | null = null;
	let releveForm = { date_releve: new Date().toISOString().slice(0, 10), index: '', note: '' };
	let relevePhotoFichiers: File[] = [];
	//  ⚠️ `relevePhotoKey` a disparu (#370) : la clé de remontage n'existait que
	//  pour vider un `<input type="file">` nu, qu'aucune affectation ne remet à
	//  zéro. `FichiersUpload` se vide en vidant sa liste.
	$: relevePhotoFile = relevePhotoFichiers[0] ?? null;
	let releveSaving = false;

	let editCompteurId: number | null = null;
	let editCompteurPrestId = '';
	let showAddCompteur = false;
	let newCompteurLabel = '';
	let addCompteurSaving = false;

	$: currentCompteur = compteurConfigs.find((c) => c.type_compteur === typeCompteur) ?? null;
	$: libelleBouton = currentCompteur
		? `Nouveau relevé — ${currentCompteur.label}`
		: 'Nouveau relevé';

	$: relevesByYear = (() => {
		const map = new Map<number, any[]>();
		for (const r of releves) {
			const yr = new Date(r.date_releve).getFullYear();
			if (!map.has(yr)) map.set(yr, []);
			map.get(yr)!.push(r);
		}
		return [...map.entries()].sort((a, b) => b[0] - a[0]);
	})();

	//  🔴 CAS ZÉRO : sans compteur, `compteurConfigs.length === 0` restait vraie
	//  après l'appel et l'onglet rappelait l'API sans fin (#549). Le drapeau dit
	//  « DEMANDÉ », pas « reçu » : posé avant, jamais relevé.
	let compteursDemandes = false;

	async function loadCompteurConfigs() {
		compteursDemandes = true;
		try {
			compteurConfigs = await prestApi.compteurConfigs();
			if (compteurConfigs.length > 0 && !typeCompteur)
				typeCompteur = compteurConfigs[0].type_compteur;
		} catch {
			toast('error', 'Erreur chargement compteurs');
		}
	}

	async function loadReleves() {
		if (!typeCompteur) return;
		releveLoading = true;
		try {
			releves = await prestApi.releves(typeCompteur);
		} catch {
			toast('error', 'Erreur chargement relevés');
		} finally {
			releveLoading = false;
		}
	}

	//  L'onglet s'amorce SEUL : il n'est monté que lorsqu'on l'ouvre, la
	//  condition sur le nom de l'onglet n'a donc plus lieu d'être. C'est un des
	//  gains de l'extraction — la page n'a plus à dire à l'onglet qu'il est
	//  visible.
	import { onMount } from 'svelte';
	onMount(() => {
		if (!compteursDemandes) loadCompteurConfigs();
	});
	$: if (typeCompteur) loadReleves();

	function resetReleveForm() {
		releveForm = { date_releve: new Date().toISOString().slice(0, 10), index: '', note: '' };
		relevePhotoFichiers = [];
		editReleveId = null;
		showReleveForm = false;
	}

	function startEditReleve(r: any) {
		releveForm = {
			date_releve: r.date_releve,
			index: r.index != null ? String(r.index) : '',
			note: r.note ?? '',
		};
		relevePhotoFichiers = [];
		editReleveId = r.id;
		showReleveForm = true;
	}

	async function saveReleve() {
		if (!releveForm.date_releve) return;
		releveSaving = true;
		try {
			const payload = {
				type_compteur: typeCompteur,
				date_releve: releveForm.date_releve,
				index: releveForm.index !== '' ? Number(releveForm.index) : null,
				note: releveForm.note.trim() || null,
				prestataire_id: currentCompteur?.prestataire_id ?? null,
			};
			let saved: any;
			if (editReleveId) {
				saved = await prestApi.updateReleve(editReleveId, payload);
				releves = releves.map((r) => (r.id === editReleveId ? saved : r));
			} else {
				saved = await prestApi.createReleve(payload);
				releves = [saved, ...releves];
			}
			if (relevePhotoFile) {
				try {
					const updated = await prestApi.uploadRelevePhoto(saved.id, relevePhotoFile);
					releves = releves.map((r) => (r.id === saved.id ? updated : r));
				} catch {
					toast('error', 'Photo non enregistrée');
				}
			}
			toast('success', editReleveId ? 'Relevé modifié' : 'Relevé ajouté');
			resetReleveForm();
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			releveSaving = false;
		}
	}

	async function deleteReleve(id: number) {
		await confirmerPuis(SUPPRESSION('Ce relevé'), 'Relevé supprimé', async () => {
			await prestApi.deleteReleve(id);
			releves = releves.filter((r) => r.id !== id);
		});
	}

	function startEditCompteur(cfg: any) {
		editCompteurId = cfg.id;
		editCompteurPrestId = cfg.prestataire_id ? String(cfg.prestataire_id) : '';
	}

	async function saveCompteurPrestataire(cfg: any) {
		try {
			const updated = await prestApi.updateCompteurConfig(cfg.id, {
				prestataire_id: editCompteurPrestId ? Number(editCompteurPrestId) : null,
			});
			compteurConfigs = compteurConfigs.map((c) => (c.id === cfg.id ? updated : c));
			editCompteurId = null;
			toast('success', 'Fournisseur mis à jour');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}

	async function addCompteurConfig() {
		if (!newCompteurLabel.trim()) return;
		addCompteurSaving = true;
		const slug = newCompteurLabel
			.trim()
			.toLowerCase()
			.normalize('NFD')
			.replace(/[\u0300-\u036f]/g, '')
			.replace(/[^a-z0-9]+/g, '_')
			.replace(/^_|_$/g, '');
		try {
			const created = await prestApi.createCompteurConfig({
				type_compteur: slug,
				label: newCompteurLabel.trim(),
				ordre: compteurConfigs.length,
			});
			compteurConfigs = [...compteurConfigs, created];
			newCompteurLabel = '';
			showAddCompteur = false;
			typeCompteur = created.type_compteur;
			toast('success', 'Catégorie ajoutée');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			addCompteurSaving = false;
		}
	}

	async function deleteCompteurConfig(cfg: any) {
		await confirmerPuis(
			SUPPRESSION(`La catégorie « ${cfg.label} »`),
			'Catégorie supprimée',
			async () => {
				await prestApi.deleteCompteurConfig(cfg.id);
				compteurConfigs = compteurConfigs.filter((c) => c.id !== cfg.id);
				if (typeCompteur === cfg.type_compteur)
					typeCompteur = compteurConfigs[0]?.type_compteur ?? '';
			},
		);
	}

	function fmtReleve(r: any) {
		return fmtDayMonth(r.date_releve);
	}
</script>

<div style="margin-bottom:1.25rem">
	<div style="display:flex;gap:.5rem;flex-wrap:wrap;align-items:center">
		{#each compteurConfigs as cfg (cfg.type_compteur)}
			<button
				class="btn btn-sm"
				class:btn-primary={typeCompteur === cfg.type_compteur}
				on:click={() => {
					typeCompteur = cfg.type_compteur;
				}}
			>
				{cfg.label}
			</button>
		{/each}
		{#if $isCS}
			<button
				class="btn btn-sm btn-outline"
				on:click={() => {
					showAddCompteur = !showAddCompteur;
					newCompteurLabel = '';
				}}
				title="Ajouter une catégorie">+ Catégorie</button
			>
		{/if}
	</div>

	{#if currentCompteur && $isCS}
		<div class="compteur-config-row" style="margin-top:.6rem">
			{#if editCompteurId === currentCompteur.id}
				<span style="font-size:.82rem;color:var(--color-text-muted)">Fournisseur :</span>
				<select bind:value={editCompteurPrestId} class="input-sm">
					<option value="">— Aucun —</option>
					{#each prestataires as p (p.id)}<option value={String(p.id)}>{p.nom}</option>{/each}
				</select>
				<button class="btn btn-sm btn-outline" on:click={() => (editCompteurId = null)}
					>Annuler</button
				>
				<button
					class="btn btn-sm btn-primary"
					on:click={() => saveCompteurPrestataire(currentCompteur)}>Enregistrer</button
				>
				{#if compteurConfigs.length > 1}
					<button
						class="btn btn-sm btn-outline"
						style="color:var(--color-danger);border-color:var(--color-danger);margin-left:auto"
						on:click={() => deleteCompteurConfig(currentCompteur)}>🗑️</button
					>
				{/if}
			{:else}
				{@const prest = currentCompteur.prestataire_id
					? prestataires.find((p) => p.id === currentCompteur.prestataire_id)
					: null}
				{#if prest}
					<span class="badge badge-blue" style="font-size:.78rem">🔧 {prest.nom}</span>
				{:else}
					<span style="font-size:.78rem;color:var(--color-text-muted)">Aucun fournisseur</span>
				{/if}
				<button
					class="btn-icon-edit"
					aria-label="Modifier le fournisseur"
					title="Modifier le fournisseur"
					on:click={() => startEditCompteur(currentCompteur)}>✏️</button
				>
			{/if}
		</div>
	{/if}

	{#if showAddCompteur && $isCS}
		<div style="display:flex;gap:.5rem;align-items:center;margin-top:.5rem;flex-wrap:wrap">
			<input
				type="text"
				bind:value={newCompteurLabel}
				placeholder="Ex. EDF Parking privé"
				class="input-sm"
				style="flex:1"
			/>
			<button
				class="btn btn-sm btn-primary"
				disabled={addCompteurSaving || !newCompteurLabel.trim()}
				on:click={addCompteurConfig}>{addCompteurSaving ? '…' : 'Ajouter'}</button
			>
			<button class="btn btn-sm btn-outline" on:click={() => (showAddCompteur = false)}
				>Annuler</button
			>
		</div>
	{/if}
</div>

{#if showReleveForm && $isCS}
	<FormulaireCreation
		cle={editReleveId}
		titre={editReleveId
			? 'Modifier le relevé'
			: currentCompteur
				? `Nouveau relevé — ${currentCompteur.label}`
				: 'Nouveau relevé'}
	>
		<form on:submit|preventDefault={saveReleve}>
			<div>
				<div class="form-grid">
					<label class="field"
						>Date du relevé *<input
							type="date"
							bind:value={releveForm.date_releve}
							required
						/></label
					>
					<label class="field"
						>Index (m³)<input
							type="number"
							min="0"
							bind:value={releveForm.index}
							placeholder="Ex. 47047"
						/></label
					>
				</div>
				<div class="field" style="margin-top:.6rem">
					<label for="releve-note">Note</label>
					<input
						id="releve-note"
						type="text"
						bind:value={releveForm.note}
						placeholder="Ex. Changement compteur"
						style="width:100%"
					/>
				</div>
				<div class="field" style="margin-top:.6rem">
					<span class="libelle-groupe">Photo du relevé</span>
					<!--  Différé : la photo part par `prestApi.uploadRelevePhoto`,
						      une fois le relevé créé. -->
					<FichiersUpload
						id="releve-photo"
						mode="photos"
						differe
						max={1}
						label="Choisir une photo"
						bind:fichiers={relevePhotoFichiers}
					/>
				</div>
			</div>
			<PiedFormulaire enCours={releveSaving} on:annule={resetReleveForm} />
		</form>
	</FormulaireCreation>
{/if}

{#if releveLoading}
	<p style="color:var(--color-text-muted)">Chargement…</p>
{:else if releves.length === 0}
	<div class="empty-state card">
		<h3>Aucun relevé</h3>
		<p>Ajoutez le premier relevé via le bouton ci-dessus.</p>
	</div>
{:else}
	{#each relevesByYear as [year, yearReleves] (year)}
		<h2 class="releve-year">{year}</h2>
		{#each yearReleves as r (r.id)}
			<div class="releve-row">
				<div class="releve-main">
					<span class="releve-date">Relevé {fmtReleve(r)}</span>
					{#if r.note}<span class="releve-note">{r.note}</span>{/if}
					{#if r.index != null}
						<span class="releve-index"
							>Index : <strong>{r.index.toLocaleString('fr-FR')}</strong></span
						>
					{/if}
					{#if r.photo_url}
						<a href={r.photo_url} target="_blank" rel="noopener">
							<img src={r.photo_url} alt="Relevé de compteur" class="releve-photo-thumb" />
						</a>
					{/if}
				</div>
				{#if $isCS}
					<div class="releve-actions">
						<button
							class="btn-icon-edit"
							aria-label="Modifier"
							title="Modifier"
							on:click={() => startEditReleve(r)}>✏️</button
						>
						<button
							class="btn-icon-danger"
							aria-label="Supprimer"
							title="Supprimer"
							on:click={() => deleteReleve(r.id)}>🗑️</button
						>
					</div>
				{/if}
			</div>
		{/each}
	{/each}
{/if}

<style>
	/* ── Configuration des compteurs ── */
	.compteur-config-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
		font-size: 0.82rem;
	}

	/* Relevés compteurs */
	.releve-year {
		font-size: 1.1rem;
		font-weight: 700;
		margin: 1.25rem 0 0.6rem;
		padding-bottom: 0.3rem;
		border-bottom: 2px solid var(--color-border);
	}
	.releve-row {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 0.75rem;
		padding: 0.6rem 0.9rem;
		border-left: 3px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
		margin-bottom: 0.3rem;
		transition: border-color 0.12s;
	}
	.releve-row:hover {
		border-left-color: var(--color-primary);
	}
	.releve-main {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
	}
	.releve-date {
		font-size: 0.9rem;
		font-weight: 600;
	}
	.releve-note {
		font-size: 0.82rem;
		color: var(--color-text-muted);
		font-style: italic;
	}
	.releve-index {
		font-size: 0.875rem;
	}
	.releve-actions {
		display: flex;
		gap: 0.25rem;
		flex-shrink: 0;
	}
	.releve-photo-thumb {
		width: 56px;
		height: 56px;
		object-fit: cover;
		border-radius: var(--radius);
		border: 1px solid var(--color-border);
		margin-top: 0.2rem;
		display: block;
	}
</style>
