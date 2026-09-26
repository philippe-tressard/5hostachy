<!--
  Les CATÉGORIES de compteur (onglet Consommations) : la rangée qui choisit la
  catégorie affichée, son fournisseur, l'ajout et la suppression d'une catégorie.

  Sorti d'`OngletConsommations` le 26/09/2026 (#1329) : ses deux petits
  formulaires — fournisseur, nouvelle catégorie — avaient leurs boutons écrits à
  la main, « Ajouter » avant « Annuler » et « … » pendant l'enregistrement. Ils
  passent par `PiedFormulaire`, et le fichier hôte dépassait alors 500 lignes.
  Le composant porte son état et ses gestes ; la page ne lui confie que la liste
  et la catégorie choisie, liées.
-->
<script lang="ts">
	import { prestataires as prestApi } from '$lib/api';
	import { messageErreur } from '$lib/erreurs';
	import { slug } from '$lib/texte';
	import { isCS } from '$lib/stores/auth';
	import { toast } from '$lib/components/Toast.svelte';
	import { SUPPRESSION, confirmerPuis } from '$lib/confirmation';
	import EtoileRequis from '$lib/components/EtoileRequis.svelte';
	import PiedFormulaire from '$lib/components/PiedFormulaire.svelte';

	/** Les catégories de compteur, liées : la page les charge et les lit. */
	export let compteurConfigs: any[] = [];
	/** La catégorie affichée, liée. */
	export let typeCompteur = '';
	/** L'annuaire des prestataires, déjà chargé par la page. */
	export let prestataires: any[] = [];

	let editCompteurId: number | null = null;
	let editCompteurPrestId = '';
	let showAddCompteur = false;
	let newCompteurLabel = '';
	let addCompteurSaving = false;

	$: currentCompteur = compteurConfigs.find((c) => c.type_compteur === typeCompteur) ?? null;

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
			toast('error', messageErreur(e));
		}
	}

	async function addCompteurConfig() {
		if (!newCompteurLabel.trim()) return;
		addCompteurSaving = true;
		const code = slug(newCompteurLabel, '_');
		try {
			const created = await prestApi.createCompteurConfig({
				type_compteur: code,
				label: newCompteurLabel.trim(),
				ordre: compteurConfigs.length,
			});
			compteurConfigs = [...compteurConfigs, created];
			newCompteurLabel = '';
			showAddCompteur = false;
			typeCompteur = created.type_compteur;
			toast('success', 'Catégorie ajoutée');
		} catch (e: any) {
			toast('error', messageErreur(e));
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
				<!--  Un petit formulaire STANDARD (#1329) : champ libellé, pied commun.
				      Les boutons étaient écrits à la main, sur la même ligne. -->
				<form
					class="compteur-edition"
					on:submit|preventDefault={() => saveCompteurPrestataire(currentCompteur)}
				>
					<div class="compteur-config-row">
						<label class="field compteur-champ"
							>Fournisseur<select bind:value={editCompteurPrestId}>
								<option value="">— Aucun —</option>
								{#each prestataires as p (p.id)}<option value={String(p.id)}>{p.nom}</option>{/each}
							</select></label
						>
						{#if compteurConfigs.length > 1}
							<button
								type="button"
								class="btn-icon-danger"
								aria-label="Supprimer la catégorie"
								title="Supprimer la catégorie"
								on:click={() => deleteCompteurConfig(currentCompteur)}>🗑️</button
							>
						{/if}
					</div>
					<PiedFormulaire petit on:annule={() => (editCompteurId = null)} />
				</form>
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
		<!--  Même forme : « Ajouter » AVANT « Annuler » et « … » en cours, c'était
		      l'inverse de tous les formulaires du site (#1329). -->
		<form class="compteur-edition" on:submit|preventDefault={addCompteurConfig}>
			<label class="field"
				><span>Nouvelle catégorie<EtoileRequis vide={!newCompteurLabel.trim()} /></span><input
					type="text"
					bind:value={newCompteurLabel}
					placeholder="Ex. EDF Parking privé"
				/></label
			>
			<PiedFormulaire
				petit
				enCours={addCompteurSaving}
				desactive={!newCompteurLabel.trim()}
				on:annule={() => (showAddCompteur = false)}
			/>
		</form>
	{/if}
</div>

<style>
	.compteur-config-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
		font-size: 0.82rem;
	}
	.compteur-edition {
		flex: 1 1 100%;
		margin-top: 0.5rem;
	}
	.compteur-champ {
		flex: 1;
		margin: 0;
	}
</style>
