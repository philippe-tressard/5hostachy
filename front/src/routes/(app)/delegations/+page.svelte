<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import { onMount } from 'svelte';
	import { currentUser, isCS } from '$lib/stores/auth';
	import {
		delegations as delegationsApi,
		admin as adminApi,
		ApiError,
	} from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { getPageConfig, configStore, siteNomStore } from '$lib/stores/pageConfig';

	$: _siteNom = $siteNomStore;

	let delegations: any[] = [];
	let loading = true;
	let users: any[] = []; // pour le formulaire CS

	// Formulaire création
	let showForm = false;
	let formMandantId = 0;
	let formAidantId = 0;
	let formMotif = '';
	let formDateFin = '';
	let saving = false;

	onMount(async () => {
		try {
			delegations = await delegationsApi.list();
			if ($isCS) {
				users = await adminApi.utilisateurs().catch(() => []);
			}
		} catch {
			toast('error', 'Erreur de chargement');
		} finally {
			loading = false;
		}
	});

	function statutLabel(s: string): string {
		const map: Record<string, string> = {
			en_attente: 'En attente',
			active: 'Active',
			revoquee: 'Révoquée',
			expiree: 'Expirée',
		};
		return map[s] ?? s;
	}

	function statutBadge(s: string): string {
		const map: Record<string, string> = {
			en_attente: 'badge-orange',
			active: 'badge-green',
			revoquee: 'badge-red',
			expiree: 'badge-grey',
		};
		return map[s] ?? '';
	}

	function fmt(d: string | null | undefined): string {
		if (!d) return '\u2014';
		return new Date(d).toLocaleDateString('fr-FR');
	}

	async function creer() {
		if (!formMandantId || !formAidantId) return;
		saving = true;
		try {
			const created = await delegationsApi.create({
				mandant_id: formMandantId,
				aidant_id: formAidantId,
				motif: formMotif,
				date_fin: formDateFin || undefined,
			});
			delegations = [created, ...delegations];
			showForm = false;
			formMandantId = 0;
			formAidantId = 0;
			formMotif = '';
			formDateFin = '';
			toast('success', 'Délégation créée');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			saving = false;
		}
	}

	async function accepter(id: number) {
		try {
			const updated = await delegationsApi.accepter(id);
			delegations = delegations.map((d) => (d.id === id ? updated : d));
			toast('success', 'Délégation acceptée');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}

	async function revoquer(id: number) {
		if (!confirm('Révoquer cette délégation ?')) return;
		try {
			const updated = await delegationsApi.revoquer(id);
			delegations = delegations.map((d) => (d.id === id ? updated : d));
			toast('success', 'Délégation révoquée');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}
</script>

<svelte:head><title>Délégations aidant — {_siteNom}</title></svelte:head>

<div class="page-header" style="margin-bottom:.75rem">
	<h1 style="display:flex;align-items:center;gap:.4rem;font-size:1.4rem;font-weight:700">
		<Icon name="heart-handshake" size={20} />Délégations aidant
	</h1>
</div>
<p class="page-subtitle" style="margin-bottom:1.5rem;color:var(--color-text-muted);font-size:.9rem">
	Gestion des accès délégués pour les proches aidants.
	<br /><em style="font-size:.82rem">L'accès aidant ne constitue pas une procuration d'AG.</em>
</p>

{#if loading}
	<p style="color:var(--color-text-muted)">Chargement…</p>
{:else}

	{#if $isCS}
		<div style="margin-bottom:1.25rem">
			<button class="btn btn-primary" on:click={() => (showForm = true)}>+ Nouvelle délégation</button>
		</div>
	{/if}

	{#if delegations.length === 0}
		<div class="card" style="padding:2rem;text-align:center;color:var(--color-text-muted)">
			Aucune délégation.
		</div>
	{:else}
		<div class="deleg-list">
			{#each delegations as d (d.id)}
				<div class="card deleg-card">
					<div class="deleg-main">
						<div class="deleg-people">
							<div class="deleg-person">
								<span class="deleg-label">Personne aidée</span>
								<span class="deleg-name">{d.mandant_nom}</span>
							</div>
							<span class="deleg-arrow"><Icon name="arrow-right" size={16} /></span>
							<div class="deleg-person">
								<span class="deleg-label">Aidant</span>
								<span class="deleg-name">{d.aidant_nom}</span>
							</div>
						</div>
						<div class="deleg-meta">
							<span class="badge {statutBadge(d.statut)}">{statutLabel(d.statut)}</span>
							<span class="deleg-date">Du {fmt(d.date_debut)}{d.date_fin ? ` au ${fmt(d.date_fin)}` : ' — illimité'}</span>
						</div>
						{#if d.motif}
							<p class="deleg-motif">{d.motif}</p>
						{/if}
					</div>
					<div class="deleg-actions">
						{#if d.statut === 'en_attente' && d.aidant_id === $currentUser?.id}
							<button class="btn btn-sm btn-primary" on:click={() => accepter(d.id)}>Accepter</button>
						{/if}
						{#if d.statut === 'en_attente' || d.statut === 'active'}
							<button class="btn btn-sm btn-danger" on:click={() => revoquer(d.id)}>Révoquer</button>
						{/if}
					</div>
				</div>
			{/each}
		</div>
	{/if}
{/if}

<!-- ── Modal : créer une délégation ──────────────────────────────────── -->
{#if showForm}
	<div class="modal-overlay" on:click|self={() => (showForm = false)} role="dialog" aria-modal="true" aria-label="Nouvelle délégation" tabindex="-1">
		<div class="modal" style="width:min(500px,95vw)">
			<div class="modal-header">
				<h3>Nouvelle délégation aidant</h3>
				<button class="modal-close" on:click={() => (showForm = false)}>✕</button>
			</div>
			<div class="modal-body" style="display:flex;flex-direction:column;gap:.75rem">
				<div class="field">
					<label for="d-mandant">Personne aidée (mandant) *</label>
					<select id="d-mandant" bind:value={formMandantId}>
						<option value={0} disabled>Choisir…</option>
						{#each users.filter((u) => u.actif) as u}
							<option value={u.id}>{u.prenom} {u.nom} ({u.email})</option>
						{/each}
					</select>
				</div>
				<div class="field">
					<label for="d-aidant">Proche aidant *</label>
					<select id="d-aidant" bind:value={formAidantId}>
						<option value={0} disabled>Choisir…</option>
						{#each users.filter((u) => u.actif && u.id !== formMandantId) as u}
							<option value={u.id}>{u.prenom} {u.nom} ({u.email})</option>
						{/each}
					</select>
				</div>
				<div class="field">
					<label for="d-motif">Motif</label>
					<input id="d-motif" type="text" bind:value={formMotif} placeholder="Ex : Assistance personne âgée" />
				</div>
				<div class="field">
					<label for="d-fin">Date de fin <span style="color:var(--color-text-muted);font-size:.8rem">(optionnel — défaut : illimité)</span></label>
					<input id="d-fin" type="date" bind:value={formDateFin} />
				</div>
				<p style="font-size:.8rem;color:var(--color-text-muted);margin:0;padding:.25rem .5rem;background:var(--color-bg);border-radius:var(--radius)">
					&#x26A0;&#xFE0F; L'aidant devra accepter la délégation. L'accès aidant ne constitue pas une procuration d'AG.
				</p>
			</div>
			<div class="modal-footer">
				<button class="btn" on:click={() => (showForm = false)}>Annuler</button>
				<button class="btn btn-primary"
					disabled={saving || !formMandantId || !formAidantId || formMandantId === formAidantId}
					on:click={creer}>
					{saving ? 'Création…' : 'Créer'}
				</button>
			</div>
		</div>
	</div>
{/if}

<style>
	.deleg-list { display: flex; flex-direction: column; gap: .6rem; }
	.deleg-card { padding: 1rem 1.25rem; display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; flex-wrap: wrap; }
	.deleg-main { flex: 1; min-width: 0; }
	.deleg-people { display: flex; align-items: center; gap: .75rem; margin-bottom: .5rem; flex-wrap: wrap; }
	.deleg-person { display: flex; flex-direction: column; gap: .1rem; }
	.deleg-label { font-size: .7rem; text-transform: uppercase; letter-spacing: .04em; color: var(--color-text-muted); font-weight: 600; }
	.deleg-name { font-weight: 600; font-size: .95rem; }
	.deleg-arrow { color: var(--color-text-muted); }
	.deleg-meta { display: flex; align-items: center; gap: .6rem; flex-wrap: wrap; margin-bottom: .25rem; }
	.deleg-date { font-size: .82rem; color: var(--color-text-muted); }
	.deleg-motif { font-size: .85rem; color: var(--color-text-muted); margin: .25rem 0 0; font-style: italic; }
	.deleg-actions { display: flex; gap: .35rem; flex-shrink: 0; align-items: flex-start; padding-top: .25rem; }

	.badge-orange { background: #fef3c7; color: #92400e; }
	.badge-green { background: #dcfce7; color: #166534; }
	.badge-red { background: #fee2e2; color: #991b1b; }
	.badge-grey { background: #f3f4f6; color: #6b7280; }

	.btn-danger { background: #dc2626; color: #fff; border-color: #dc2626; }
	.btn-danger:hover { background: #b91c1c; }

	/* Modals & forms — réutilise les styles globaux */
	.modal-overlay { position: fixed; top: 0; right: 0; bottom: 0; left: 0; background: rgba(0,0,0,.45); display: flex; align-items: center; justify-content: center; z-index: 200; }
	.modal { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius); padding: 1.5rem; max-height: 90vh; overflow-y: auto; }
	.modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
	.modal-header h3 { font-size: 1.05rem; font-weight: 600; margin: 0; }
	.modal-close { background: none; border: none; font-size: 1.3rem; cursor: pointer; color: var(--color-text-muted); padding: 0; line-height: 1; }
	.modal-close:hover { color: var(--color-text); }
	.modal-body { margin-bottom: 1rem; }
	.modal-footer { display: flex; justify-content: flex-end; gap: .5rem; padding-top: .75rem; border-top: 1px solid var(--color-border); }
	.field { display: flex; flex-direction: column; gap: .25rem; }
	.field label { font-size: .8rem; font-weight: 500; color: var(--color-text-muted); }
	.field input, .field select, .field textarea { padding: .4rem .6rem; border: 1px solid var(--color-border); border-radius: 6px; font-size: .875rem; background: var(--color-surface); }
</style>
