<script lang="ts">
	import { goto } from '$app/navigation';
	import { tickets as ticketsApi, ApiError } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import RichEditor from '$lib/components/RichEditor.svelte';
	import { siteNomStore } from '$lib/stores/pageConfig';

	$: _siteNom = $siteNomStore;

	let titre = '';
	let description = '';
	let categorie = 'panne';
	let perimetre: 'résidence' | 'specifique' = 'résidence';
	let lieux = new Set<string>();
	let error = '';
	let loading = false;

	const categories = [
		{ value: 'panne', label: '\u{1F6E0}️ Panne', description: 'Équipement défectueux, ascenseur, chauffage…' },
		{ value: 'nuisance', label: '\u{1F4E2} Nuisance', description: 'Bruit, odeur, parking…' },
		{ value: 'question', label: '❓ Question', description: 'Information, procédure…' },
		{ value: 'urgence', label: '\u{1F6A8} Urgence', description: 'Inondation, panne majeure, danger immédiat' },
		{ value: 'bug', label: '\u{1F41B} Bug', description: 'Problème technique sur le site ou l’application' },
	];

	function perimetreCibleValue(): string[] {
		if (perimetre === 'résidence') return ['résidence'];
		return Array.from(lieux);
	}

	const richEmpty = (html: string) => !html || html.replace(/<[^>]+>/g, '').trim() === '';

	async function submit() {
		if (!titre.trim() || richEmpty(description)) {
			error = 'Titre et description sont obligatoires.';
			return;
		}
		error = '';
		loading = true;
		try {
			const t = await ticketsApi.create({ titre, description, categorie, perimetre_cible: perimetreCibleValue() });
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
			<div class="perimetre-pills">
				<button type="button" class="pill" class:pill-active={perimetre === 'résidence'}
					on:click={() => { perimetre = 'résidence'; lieux = new Set(); }}>
					&#x1F3E7; Copropriété entière
				</button>
				{#each [['bat:1','Bât. 1'],['bat:2','Bât. 2'],['bat:3','Bât. 3'],['bat:4','Bât. 4'],['parking','Parking'],['cave','Cave'],['aful','AFUL']] as [val, lbl]}
					<button type="button" class="pill" class:pill-active={lieux.has(val)}
						on:click={() => { if (lieux.has(val)) { lieux.delete(val); } else { lieux.add(val); } lieux = lieux; perimetre = lieux.size > 0 ? 'specifique' : 'résidence'; }}>
						{lbl}
					</button>
				{/each}
			</div>
		</div>

		<div class="field">
			<label>Description *</label>
			<RichEditor bind:value={description} placeholder="Décrivez le problème avec le maximum de détails (localisation, depuis quand, fréquence…)" minHeight="120px" />
		</div>

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

	.perimetre-pills { display: flex; flex-wrap: wrap; gap: .4rem; margin-top: .4rem; }
	.pill { padding: .3rem .85rem; border-radius: 999px; border: 1.5px solid var(--color-border); background: var(--color-bg); font-size: .85rem; cursor: pointer; transition: background .15s, border-color .15s, color .15s; white-space: nowrap; line-height: 1.6; }
	.pill-active { background: var(--color-primary); border-color: var(--color-primary); color: #fff; }

	@media (max-width: 480px) { .cat-grid { grid-template-columns: 1fr; } }
</style>
