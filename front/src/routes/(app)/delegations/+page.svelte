<script lang="ts">
	import Modale from '$lib/components/Modale.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import EntetePage from '$lib/components/EntetePage.svelte';
	import { onMount } from 'svelte';
	import { currentUser, isCS } from '$lib/stores/auth';
	import { delegations as delegationsApi, admin as adminApi, ApiError } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { getPageConfig, configStore, siteNomStore, defautsDePage } from '$lib/stores/pageConfig';
	import { fmtDateShort as fmt } from '$lib/date';
	import ChargementPartiel from '$lib/components/ChargementPartiel.svelte';
	import { essayer } from '$lib/chargement';

	// Cette page importait déjà getPageConfig sans s'en servir : son titre était en
	// dur, elle était donc la seule entrée du menu qu'on ne pouvait ni renommer ni
	// positionner (#401).
	$: _pc = getPageConfig($configStore, 'delegations', defautsDePage('delegations'));
	$: _siteNom = $siteNomStore;

	let delegations: any[] = [];
	let loading = true;
	let users: any[] = []; // pour le formulaire CS
	/** Non vide = la liste des résidents n'a pas pu être chargée (#522). */
	let erreurUtilisateurs = '';

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
				//  Donnée de RÉFÉRENCE : elle garnit deux menus déroulants. Un
				//  échec les laissait vides, et l'écran donnait à croire qu'aucun
				//  résident n'était délégable (#522).
				[users, erreurUtilisateurs] = await essayer<any[]>(adminApi.utilisateurs(), []);
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

<EntetePage titre={_pc.titre} icone={_pc.icone || 'heart-handshake'} />

<ChargementPartiel
	erreur={erreurUtilisateurs}
	consequence="Les menus « mandant » et « aidant » du formulaire de délégation sont vides : ce n'est pas qu'aucun résident n'est éligible."
/>
<p class="page-subtitle" style="margin-bottom:1.5rem;color:var(--color-text-muted);font-size:.9rem">
	Gestion des accès délégués pour les proches aidants.
	<br /><em style="font-size:.82rem">L'accès aidant ne constitue pas une procuration d'AG.</em>
</p>

{#if loading}
	<p style="color:var(--color-text-muted)">Chargement…</p>
{:else}
	{#if $isCS}
		<div style="margin-bottom:1.25rem">
			<button class="btn btn-primary" on:click={() => (showForm = true)}
				>+ Nouvelle délégation</button
			>
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
							<span class="deleg-date"
								>Du {fmt(d.date_debut)}{d.date_fin ? ` au ${fmt(d.date_fin)}` : ' — illimité'}</span
							>
						</div>
						{#if d.motif}
							<p class="deleg-motif">{d.motif}</p>
						{/if}
					</div>
					<div class="deleg-actions">
						{#if d.statut === 'en_attente' && d.aidant_id === $currentUser?.id}
							<button class="btn btn-sm btn-primary" on:click={() => accepter(d.id)}
								>Accepter</button
							>
						{/if}
						{#if d.statut === 'en_attente' || d.statut === 'active'}
							<button class="btn btn-sm btn-danger" on:click={() => revoquer(d.id)}>Révoquer</button
							>
						{/if}
					</div>
				</div>
			{/each}
		</div>
	{/if}
{/if}

<!-- ── Modal : créer une délégation ──────────────────────────────────── -->
{#if showForm}
	<Modale
		titre="Nouvelle délégation aidant"
		styleBoite="width:min(500px,95vw)"
		on:fermer={() => (showForm = false)}
	>
		<div class="modal-body">
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
				<input
					id="d-motif"
					type="text"
					bind:value={formMotif}
					placeholder="Ex : Assistance personne âgée"
				/>
			</div>
			<div class="field">
				<label for="d-fin"
					>Date de fin <span style="color:var(--color-text-muted);font-size:.8rem"
						>(optionnel — défaut : illimité)</span
					></label
				>
				<input id="d-fin" type="date" bind:value={formDateFin} />
			</div>
			<p
				style="font-size:.8rem;color:var(--color-text-muted);margin:0;padding:.25rem .5rem;background:var(--color-bg);border-radius:var(--radius)"
			>
				&#x26A0;&#xFE0F; L'aidant devra accepter la délégation. L'accès aidant ne constitue pas une
				procuration d'AG.
			</p>
		</div>
		<div class="modal-footer">
			<button class="btn" on:click={() => (showForm = false)}>Annuler</button>
			<button
				class="btn btn-primary"
				disabled={saving || !formMandantId || !formAidantId || formMandantId === formAidantId}
				on:click={creer}
			>
				{saving ? 'Création…' : 'Créer'}
			</button>
		</div>
	</Modale>
{/if}

<style>
	.deleg-list {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}
	.deleg-card {
		padding: 1rem 1.25rem;
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 1rem;
		flex-wrap: wrap;
	}
	.deleg-main {
		flex: 1;
		min-width: 0;
	}
	.deleg-people {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-bottom: 0.5rem;
		flex-wrap: wrap;
	}
	.deleg-person {
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
	}
	.deleg-label {
		font-size: 0.7rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--color-text-muted);
		font-weight: 600;
	}
	.deleg-name {
		font-weight: 600;
		font-size: 0.95rem;
	}
	.deleg-arrow {
		color: var(--color-text-muted);
	}
	.deleg-meta {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		flex-wrap: wrap;
		margin-bottom: 0.25rem;
	}
	.deleg-date {
		font-size: 0.82rem;
		color: var(--color-text-muted);
	}
	.deleg-motif {
		font-size: 0.85rem;
		color: var(--color-text-muted);
		margin: 0.25rem 0 0;
		font-style: italic;
	}
	.deleg-actions {
		display: flex;
		gap: 0.35rem;
		flex-shrink: 0;
		align-items: flex-start;
		padding-top: 0.25rem;
	}

	/*  🔴 `.badge-orange`, `.badge-green` et `.badge-red` retirees le 28/08/2026
	    (#607) : la charte les porte. `.badge-grey` reste — elle n'y est pas. */
	.badge-grey {
		background: #f3f4f6;
		color: #6b7280;
	}

	/*  La charte porte `.btn-danger` ; cet ecran ecrivait `#dc2626`
    EN DUR au lieu du jeton, donc hors du theme (#607, 28/08/2026). */
	.btn-danger {
		border-color: var(--color-danger);
	}
	.btn-danger:hover {
		background: #b91c1c;
	}

	/*  🔴 L'EN-TÊTE d'une modale ne s'écrit plus ici : `Modale.svelte` le rend, et
	    `styles/composants.css` le style (`.modal-titre`). #607 avait retiré
	    `.modal-header`, `.modal-close` et `.modal-footer` de ces trois écrans en
	    laissant `.modal-header h3` — la seule des quatre qui n'existait PAS en
	    global, donc la seule que le retrait ne pouvait pas solder. Elle a survécu
	    à l'identique dans les trois, et divergeait du `h2` de la charte. */
</style>
