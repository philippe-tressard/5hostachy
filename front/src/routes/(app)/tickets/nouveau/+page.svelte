<script lang="ts">
	import { goto } from '$app/navigation';
	import { tickets as ticketsApi, admin as adminApi, ApiError } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import RichEditor from '$lib/components/RichEditor.svelte';
	import PerimetrePicker from '$lib/components/PerimetrePicker.svelte';
	import { siteNomStore } from '$lib/stores/pageConfig';
	import { isCS } from '$lib/stores/auth';
	import { onMount } from 'svelte';

	$: _siteNom = $siteNomStore;

	let titre = '';
	let description = '';
	let categorie = 'panne';
	let perimetreCible: string[] = ['résidence'];
	let destinataireSyndic = false;
	let destinataireCs = false;
	let photoFiles: File[] = [];
	let photoPreviews: string[] = [];
	let error = '';
	let loading = false;

	// Saisi pour (CS/Admin uniquement)
	type ModeSaisiPour = 'moi' | 'resident' | 'exterieur';
	let modeSaisiPour: ModeSaisiPour = 'moi';
	let saisiPourUserId: number | null = null;
	let saisiPourNom = '';
	let saisiPourEmail = '';
	let usersActifs: { id: number; prenom: string; nom: string; email: string }[] = [];

	onMount(async () => {
		if ($isCS) {
			try {
				const all = await adminApi.utilisateurs();
				usersActifs = all.filter((u: any) => u.actif).sort((a: any, b: any) =>
					`${a.prenom} ${a.nom}`.localeCompare(`${b.prenom} ${b.nom}`)
				);
			} catch { /* ignore */ }
		}
	});

	const categories = [
		{ value: 'panne', label: '\u{1F6E0}️ Panne', description: 'Équipement défectueux, ascenseur, chauffage…' },
		{ value: 'nuisance', label: '\u{1F4E2} Nuisance', description: 'Bruit, odeur, parking…' },
		{ value: 'question', label: '❓ Question', description: 'Information, procédure…' },
		{ value: 'urgence', label: '\u{1F6A8} Urgence', description: 'Inondation, panne majeure, danger immédiat' },
		{ value: 'bug', label: '\u{1F41B} Bug', description: 'Problème technique sur le site ou l\u2019application' },
	];

	const richEmpty = (html: string) => !html || html.replace(/<[^>]+>/g, '').trim() === '';

	function handlePhotoSelect(e: Event) {
		const input = e.target as HTMLInputElement;
		if (!input.files) return;
		const newFiles = Array.from(input.files).slice(0, 5 - photoFiles.length);
		photoFiles = [...photoFiles, ...newFiles];
		photoPreviews = [...photoPreviews, ...newFiles.map((f) => URL.createObjectURL(f))];
		input.value = '';
	}

	function removePhoto(index: number) {
		URL.revokeObjectURL(photoPreviews[index]);
		photoFiles = photoFiles.filter((_, i) => i !== index);
		photoPreviews = photoPreviews.filter((_, i) => i !== index);
	}

	async function submit() {
		if (!titre.trim() || richEmpty(description)) {
			error = 'Titre et description sont obligatoires.';
			return;
		}
		if ($isCS && modeSaisiPour === 'exterieur' && !saisiPourNom.trim()) {
			error = 'Veuillez saisir le nom de la personne.';
			return;
		}
		error = '';
		loading = true;
		try {
			const payload: any = {
				titre,
				description,
				categorie,
				perimetre_cible: perimetreCible,
				destinataire_syndic: destinataireSyndic,
				destinataire_cs: destinataireCs,
			};
			if ($isCS) {
				if (modeSaisiPour === 'resident' && saisiPourUserId) {
					payload.saisi_pour_user_id = saisiPourUserId;
				} else if (modeSaisiPour === 'exterieur') {
					if (saisiPourNom.trim()) payload.saisi_pour_nom = saisiPourNom.trim();
					if (saisiPourEmail.trim()) payload.saisi_pour_email = saisiPourEmail.trim();
				}
			}
			const t = await ticketsApi.create(payload);

			// Upload photos after ticket creation
			for (const file of photoFiles) {
				try {
					await ticketsApi.uploadPhoto(t.id, file);
				} catch {
					// Continue even if one photo fails
				}
			}

			toast('success', `Ticket ${t.numero} créé avec succès`);
			goto('/tickets');
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Erreur lors de la création';
		} finally {
			loading = false;
		}
	}
</script>

<svelte:head><title>Nouveau ticket — {_siteNom}</title></svelte:head>

<div class="page-header">
	<a href="/tickets" class="btn btn-outline">← Retour</a>
	<h1>Nouveau ticket</h1>
</div>

{#if categorie === 'urgence'}
	<div class="alert alert-error" style="margin-bottom:1rem">
		&#x1F6A8; <strong>Urgence</strong> — Le conseil syndical et le syndic seront notifiés immédiatement.
		En cas de danger immédiat, composez le <strong>15 (SAMU), 17 (Police) ou 18 (Pompiers)</strong>.
	</div>
{/if}

{#if error}
	<div class="alert alert-error">{error}</div>
{/if}

<div class="card" style="max-width:640px">
	<form on:submit|preventDefault={submit}>
		<fieldset class="field" style="border:none;padding:0;margin:0">
			<legend style="font-size:.875rem;font-weight:500;margin-bottom:.5rem;color:var(--color-text)">Catégorie *</legend>
			<div class="cat-grid">
				{#each categories as cat}
					<label class="cat-option" class:selected={categorie === cat.value}>
						<input type="radio" bind:group={categorie} value={cat.value} />
						<span class="cat-label">{cat.label}</span>
						<span class="cat-desc">{cat.description}</span>
					</label>
				{/each}
			</div>
		</fieldset>

		<div class="field">
			<label for="titre">Titre *</label>
			<input
				id="titre"
				type="text"
				bind:value={titre}
				required
				placeholder="Ex : Ascenseur bâtiment A en panne"
				maxlength="200"
			/>
		</div>

		<div class="field">
			<label>Périmètre</label>
			<PerimetrePicker bind:value={perimetreCible} />
		</div>

		<div class="field">
			<label>Description *</label>
			<RichEditor bind:value={description} placeholder="Décrivez le problème avec le maximum de détails (localisation, depuis quand, fréquence…)" minHeight="120px" />
		</div>

		<div class="field">
			<label>Photos <span style="color:var(--color-text-muted);font-weight:normal">(max 5)</span></label>
			{#if photoPreviews.length > 0}
				<div class="photo-previews">
					{#each photoPreviews as src, i}
						<div class="photo-thumb">
							<img src={src} alt="Photo {i + 1}" />
							<button type="button" class="photo-remove" on:click={() => removePhoto(i)} title="Retirer">✕</button>
						</div>
					{/each}
				</div>
			{/if}
			{#if photoFiles.length < 5}
				<input type="file" accept="image/*" multiple on:change={handlePhotoSelect} />
			{/if}
		</div>

		{#if $isCS}
			<div class="field saisi-pour-section">
				<label style="font-weight:500">Saisi pour</label>
				<div class="saisi-pour-tabs">
					<button type="button" class="tab-btn" class:active={modeSaisiPour === 'moi'} on:click={() => modeSaisiPour = 'moi'}>
						En mon nom
					</button>
					<button type="button" class="tab-btn" class:active={modeSaisiPour === 'resident'} on:click={() => modeSaisiPour = 'resident'}>
						Résident inscrit
					</button>
					<button type="button" class="tab-btn" class:active={modeSaisiPour === 'exterieur'} on:click={() => modeSaisiPour = 'exterieur'}>
						Personne extérieure
					</button>
				</div>
				{#if modeSaisiPour === 'resident'}
					<select bind:value={saisiPourUserId} style="margin-top:.5rem">
						<option value={null}>— Sélectionner un résident —</option>
						{#each usersActifs as u}
							<option value={u.id}>{u.prenom} {u.nom}{u.email ? ` (${u.email})` : ''}</option>
						{/each}
					</select>
				{:else if modeSaisiPour === 'exterieur'}
					<div style="margin-top:.5rem;display:flex;flex-direction:column;gap:.5rem">
						<input type="text" bind:value={saisiPourNom} placeholder="Nom complet *" required />
						<input type="email" bind:value={saisiPourEmail} placeholder="Email (optionnel)" />
					</div>
				{/if}
			</div>
			<label class="checkbox-field">
				<input type="checkbox" bind:checked={destinataireSyndic} />
				<span>📧 Envoyer au syndic</span>
				<small style="display:block; color:var(--color-text-muted); margin-top:.25rem">
					Le syndic principal recevra un email.
				</small>
			</label>
			<label class="checkbox-field">
				<input type="checkbox" bind:checked={destinataireCs} />
				<span>📧 Envoyer au Conseil Syndical</span>
				<small style="display:block; color:var(--color-text-muted); margin-top:.25rem">
					Les membres du CS recevront un email.
				</small>
			</label>
		{/if}

		<div class="form-actions">
			<a href="/tickets" class="btn btn-outline">Annuler</a>
			<button type="submit" class="btn btn-primary" disabled={loading}>
				{loading ? 'Envoi…' : 'Envoyer la demande'}
			</button>
		</div>
	</form>
</div>

<style>
	.page-header {
		display: flex;
		align-items: center;
		gap: 1rem;
		margin-bottom: 1.5rem;
	}
	.page-header h1 { font-size: 1.4rem; font-weight: 700; }

	.cat-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: .5rem;
	}

	.cat-option {
		display: flex;
		flex-direction: column;
		gap: .15rem;
		padding: .75rem;
		border: 2px solid var(--color-border);
		border-radius: var(--radius);
		cursor: pointer;
		transition: border-color .15s, background .15s;
	}

	.cat-option input[type="radio"] { display: none; }
	.cat-option.selected { border-color: var(--color-primary); background: var(--color-primary-light); }

	.cat-label { font-weight: 600; font-size: .9rem; }
	.cat-desc  { font-size: .78rem; color: var(--color-text-muted); }

	.form-actions { display: flex; justify-content: flex-end; gap: .5rem; margin-top: 1rem; }

	.photo-previews {
		display: flex;
		gap: .5rem;
		flex-wrap: wrap;
		margin-bottom: .5rem;
	}
	.photo-thumb {
		position: relative;
		width: 80px;
		height: 80px;
		border-radius: var(--radius);
		overflow: hidden;
		border: 1px solid var(--color-border);
	}
	.photo-thumb img {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}
	.photo-remove {
		position: absolute;
		top: 2px;
		right: 2px;
		background: rgba(0,0,0,.6);
		color: #fff;
		border: none;
		border-radius: 50%;
		width: 20px;
		height: 20px;
		font-size: .7rem;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		line-height: 1;
	}

	.checkbox-field {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-start;
		gap: .5rem;
		padding: .75rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		cursor: pointer;
		margin-bottom: .5rem;
	}
	.checkbox-field input[type="checkbox"] { margin-top: .2rem; }

	.saisi-pour-section {
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: .75rem;
		margin-bottom: .5rem;
	}

	.saisi-pour-tabs {
		display: flex;
		gap: .25rem;
		margin-top: .5rem;
		flex-wrap: wrap;
	}

	.tab-btn {
		padding: .375rem .75rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: transparent;
		cursor: pointer;
		font-size: .85rem;
		color: var(--color-text-muted);
		transition: background .15s, color .15s, border-color .15s;
	}
	.tab-btn.active {
		background: var(--color-primary);
		color: #fff;
		border-color: var(--color-primary);
	}

	@media (max-width: 480px) { .cat-grid { grid-template-columns: 1fr; } }
</style>
