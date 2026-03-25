<script lang="ts">
	import { onMount } from 'svelte';
	import { copropriete as coproprieteApi, ApiError } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { siteNomStore } from '$lib/stores/pageConfig';

	$: _siteNom = $siteNomStore;

	let form: any = {
		nom: '', adresse: '', code_postal: '', ville: '', nb_lots_total: '',
		annee_construction: '', numero_immatriculation: '',
		assurance_compagnie: '', assurance_numero: '', assurance_echeance: '',
		syndic_nom: '', syndic_contact: '', syndic_email: '', syndic_telephone: ''
	};
	let loading = true;
	let saving = false;

	onMount(async () => {
		try {
			const data = await coproprieteApi.get();
			if (data) {
				Object.keys(form).forEach(k => { if (data[k] !== undefined) form[k] = data[k] ?? ''; });
			}
		} catch { /* first time — empty form */ }
		finally { loading = false; }
	});

	async function save() {
		saving = true;
		try {
			const payload = { ...form };
			if (payload.nb_lots_total === '') payload.nb_lots_total = null;
			else payload.nb_lots_total = Number(payload.nb_lots_total);
			if (payload.annee_construction === '') payload.annee_construction = null;
			else payload.annee_construction = Number(payload.annee_construction);
			await coproprieteApi.update(payload);
			toast('success', 'Fiche enregistrée');
		} catch { toast('error', 'Erreur lors de la sauvegarde'); }
		finally { saving = false; }
	}
</script>

<svelte:head><title>Admin — Fiche copropriété — {_siteNom}</title></svelte:head>

<h1 style="font-size:1.3rem;font-weight:700;margin-bottom:1.5rem">⚙️ Fiche copropriété</h1>

{#if loading}
	<p style="color:var(--color-text-muted)">Chargement…</p>
{:else}
<form on:submit|preventDefault={save} style="max-width:640px;display:flex;flex-direction:column;gap:1.25rem">

	<section class="form-section">
		<h2 class="section-title">Identité</h2>
		<div class="form-grid">
			<label class="form-group">
				<span>Nom de la résidence *</span>
				<input class="input" bind:value={form.nom} required />
			</label>
			<label class="form-group">
				<span>Adresse</span>
				<input class="input" bind:value={form.adresse} />
			</label>
			<label class="form-group">
				<span>Code postal</span>
				<input class="input" bind:value={form.code_postal} maxlength="5" />
			</label>
			<label class="form-group">
				<span>Ville</span>
				<input class="input" bind:value={form.ville} />
			</label>
			<label class="form-group">
				<span>Nombre de lots total</span>
				<input class="input" type="number" min="1" bind:value={form.nb_lots_total} />
			</label>
			<label class="form-group">
				<span>Année de construction</span>
				<input class="input" type="number" min="1800" max="2100" bind:value={form.annee_construction} />
			</label>
			<label class="form-group" style="grid-column:1/-1">
				<span>N° immatriculation (ANAH)</span>
				<input class="input" bind:value={form.numero_immatriculation} placeholder="ex : D75010800001" />
			</label>
		</div>
	</section>

	<section class="form-section">
		<h2 class="section-title">Assurance</h2>
		<div class="form-grid">
			<label class="form-group">
				<span>Compagnie</span>
				<input class="input" bind:value={form.assurance_compagnie} />
			</label>
			<label class="form-group">
				<span>N° de contrat</span>
				<input class="input" bind:value={form.assurance_numero} />
			</label>
			<label class="form-group">
				<span>Échéance</span>
				<input class="input" type="date" bind:value={form.assurance_echeance} />
			</label>
		</div>
	</section>

	<section class="form-section">
		<h2 class="section-title">Syndic</h2>
		<div class="form-grid">
			<label class="form-group">
				<span>Nom du syndic</span>
				<input class="input" bind:value={form.syndic_nom} />
			</label>
			<label class="form-group">
				<span>Interlocuteur</span>
				<input class="input" bind:value={form.syndic_contact} />
			</label>
			<label class="form-group">
				<span>Email</span>
				<input class="input" type="email" bind:value={form.syndic_email} />
			</label>
			<label class="form-group">
				<span>Téléphone</span>
				<input class="input" type="tel" bind:value={form.syndic_telephone} />
			</label>
		</div>
	</section>

	<div>
		<button class="btn btn-primary" type="submit" disabled={saving}>
			{saving ? 'Enregistrement…' : 'Enregistrer'}
		</button>
	</div>
</form>
{/if}

<style>
	.section-title { font-size: .8rem; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; color: var(--color-text-muted); margin-bottom: .75rem; }
	.form-section { background: var(--color-card); border: 1px solid var(--color-border); border-radius: var(--radius); padding: 1.25rem; }
	.form-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: .75rem; }
	.form-group { display: flex; flex-direction: column; gap: .25rem; font-size: .875rem; }
	.form-group span { color: var(--color-text-muted); font-size: .8rem; }
</style>
