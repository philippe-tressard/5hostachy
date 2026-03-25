<script lang="ts">
	import { onMount } from 'svelte';
	import { acces as accesApi, api } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { siteNomStore } from '$lib/stores/pageConfig';

	$: _siteNom = $siteNomStore;
	// ── Données ────────────────────────────────────────────────────────────────
	let imports: any[] = [];
	let stats: any = null;
	let utilisateurs: any[] = [];
	let lots: any[] = [];
	let loading = true;
	let filtre = '';

	// ── Upload ─────────────────────────────────────────────────────────────────
	let uploadFile: FileList | null = null;
	let remplacer = false;
	let uploading = false;

	async function uploadExcel() {
		if (!uploadFile?.length) { toast('error', 'Choisissez un fichier .xlsx'); return; }
		uploading = true;
		try {
			const result = await accesApi.uploadImportVigik(uploadFile[0], remplacer);
			toast('success', `Import : ${result.importes} ajoutés, ${result.doublons} doublons, ${result.ignores} ignorés`);
			await reload();
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur import');
		} finally {
			uploading = false;
			uploadFile = null;
		}
	}

	// ── Auto-match ─────────────────────────────────────────────────────────────
	let autoMatching = false;

	async function autoMatch() {
		autoMatching = true;
		try {
			const r = await accesApi.autoMatchImportsVigik();
			toast('success', `${r.matches} liaison(s) automatique(s) trouvée(s)`);
			await reload();
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		} finally {
			autoMatching = false;
		}
	}

	// ── Edition inline ─────────────────────────────────────────────────────────
	let editId: number | null = null;
	let editProprio = '';
	let editLoc = '';
	let editLot = '';
	let editChezLoc = false;
	let editNotes = '';
	let saving = false;

	function openEdit(imp: any) {
		editId = imp.id;
		editProprio = String(imp.user_proprietaire_id ?? '');
		editLoc = String(imp.user_locataire_id ?? '');
		editLot = String(imp.lot_id ?? '');
		editChezLoc = imp.chez_locataire;
		editNotes = imp.notes_admin ?? '';
	}

	function cancelEdit() { editId = null; }

	async function saveEdit() {
		if (editId === null) return;
		saving = true;
		try {
			await accesApi.patchImportVigik(editId, {
				user_proprietaire_id: editProprio ? Number(editProprio) : null,
				user_locataire_id: editLoc ? Number(editLoc) : null,
				lot_id: editLot ? Number(editLot) : null,
				chez_locataire: editChezLoc,
				notes_admin: editNotes || null,
			});
			toast('success', 'Liaisons mises à jour');
			editId = null;
			await reload();
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		} finally {
			saving = false;
		}
	}

	// ── Résolution / Ignorer ───────────────────────────────────────────────────
	async function resoudre(id: number) {
		if (!confirm('Créer le badge Vigik et marquer cet import comme résolu ?')) return;
		try {
			await accesApi.resoudreImportVigik(id);
			toast('success', 'Badge Vigik créé et lié');
			await reload();
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur résolution');
		}
	}

	async function ignorer(id: number) {
		if (!confirm('Ignorer cet import ?')) return;
		try {
			await accesApi.ignorerImportVigik(id);
			toast('info', 'Import ignoré');
			await reload();
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		}
	}

	// ── Chargement ─────────────────────────────────────────────────────────────
	async function reload() {
		[imports, stats] = await Promise.all([
			accesApi.listImportsVigik(filtre || undefined),
			accesApi.statsImportsVigik(),
		]);
	}

	onMount(async () => {
		loading = true;
		try {
			[utilisateurs, lots] = await Promise.all([
				api.get<any[]>('/admin/utilisateurs'),
				api.get<any[]>('/copropriete/lots'),
			]);
			await reload();
		} catch (e) {
			toast('error', 'Erreur de chargement');
		} finally {
			loading = false;
		}
	});

	// ── Helpers ────────────────────────────────────────────────────────────────
	const statutBadge: Record<string, string> = {
		en_attente: 'badge-orange',
		proprietaire_lie: 'badge-blue',
		resolu: 'badge-green',
		ignore: 'badge-gray',
	};
	const statutLabel: Record<string, string> = {
		en_attente: 'En attente',
		proprietaire_lie: 'Proprio lié',
		resolu: 'Résolu',
		ignore: 'Ignoré',
	};

	function userName(id: number | null) {
		if (!id) return '—';
		const u = utilisateurs.find(x => x.id === id);
		return u ? `${u.prenom} ${u.nom}` : `#${id}`;
	}
</script>

<svelte:head><title>Import Vigik — {_siteNom}</title></svelte:head>

<div class="page-header">
	<a href="/admin" class="btn btn-outline btn-sm" style="margin-right:.75rem">← Paramétrage</a>
	<h1>&#x1F3F7; Import Vigik</h1>
</div>

<!-- ── Stats ──────────────────────────────────────────────────────────────── -->
{#if stats}
<div class="stats-bar card">
	<div class="stat"><span class="stat-val">{stats.total}</span><span class="stat-lbl">Total</span></div>
	<div class="stat"><span class="stat-val" style="color:#d97706">{stats.en_attente}</span><span class="stat-lbl">En attente</span></div>
	<div class="stat"><span class="stat-val" style="color:#2563eb">{stats.proprietaire_lie}</span><span class="stat-lbl">Proprio lié</span></div>
	<div class="stat"><span class="stat-val" style="color:#16a34a">{stats.resolu}</span><span class="stat-lbl">Résolus</span></div>
	<div class="stat"><span class="stat-val" style="color:#6b7280">{stats.ignore}</span><span class="stat-lbl">Ignorés</span></div>
	<div class="stat"><span class="stat-val">{stats.avec_lot}</span><span class="stat-lbl">Lot auto-lié</span></div>
</div>
{/if}

<!-- ── Upload ─────────────────────────────────────────────────────────────── -->
<div class="card upload-section">
	<h2 class="section-title">Importer un fichier Excel</h2>
	<p class="muted" style="font-size:.85rem;margin-bottom:.75rem">
		Colonnes attendues : <code>BATIMENT | APPARTEMENT | NOM DU COPROPRIÉTAIRE | NOM LOCATAIRE | N° CLÉS</code>
	</p>
	<div class="upload-row">
		<input type="file" accept=".xlsx,.xls" bind:files={uploadFile} class="file-input" />
		<label class="checkbox-label">
			<input type="checkbox" bind:checked={remplacer} />
			Remplacer les imports en attente existants
		</label>
		<button class="btn btn-primary" on:click={uploadExcel} disabled={uploading || !uploadFile?.length}>
			{uploading ? 'Import…' : 'Importer'}
		</button>
	</div>
</div>

<!-- ── Filtres + actions ──────────────────────────────────────────────────── -->
<div class="toolbar">
	<div style="display:flex;gap:.5rem;align-items:center">
		<span class="muted" style="font-size:.85rem">Filtrer :</span>
		{#each ['', 'en_attente', 'proprietaire_lie', 'resolu', 'ignore'] as s}
			<button
				class="btn btn-sm {filtre === s ? 'btn-primary' : 'btn-outline'}"
				on:click={async () => { filtre = s; await reload(); }}>
				{s === '' ? 'Tous' : statutLabel[s]}
			</button>
		{/each}
	</div>
	<button class="btn btn-outline btn-sm" on:click={autoMatch} disabled={autoMatching}>
		{autoMatching ? 'Recherche…' : '\u{1F517} Auto-match'}
	</button>
</div>

<!-- ── Table ──────────────────────────────────────────────────────────────── -->
{#if loading}
	<p class="muted">Chargement…</p>
{:else if imports.length === 0}
	<div class="empty-state card">
		<h3>Aucun import</h3>
		<p>Importez un fichier .xlsx pour démarrer.</p>
	</div>
{:else}
<div class="card" style="overflow:auto">
	<table class="table table-dense">
		<thead>
			<tr>
				<th>Bât.</th><th>Appt.</th>
				<th>Propriétaire (Excel)</th><th>Locataire (Excel)</th>
				<th>Code</th><th>Lot lié</th>
				<th>Proprio lié</th><th>Locataire lié</th>
				<th>Statut</th><th>Actions</th>
			</tr>
		</thead>
		<tbody>
			{#each imports as imp (imp.id)}
				<tr class:row-resolu={imp.statut === 'resolu'} class:row-ignore={imp.statut === 'ignore'}>
					<td style="font-size:.8rem">{imp.batiment_raw ?? '—'}</td>
					<td style="font-size:.8rem">{imp.appartement_raw ?? '—'}</td>
					<td style="font-weight:500">{imp.nom_proprietaire}</td>
					<td style="color:var(--color-text-muted)">{imp.nom_locataire ?? '—'}</td>
					<td><code style="font-size:.8rem">{imp.code ?? '—'}</code></td>
					<td style="font-size:.8rem;color:var(--color-text-muted)">{imp.lot_label ?? '—'}</td>
					<td style="font-size:.8rem">
						{#if imp.proprietaire}
							<span style="color:#16a34a">{imp.proprietaire.prenom} {imp.proprietaire.nom}</span>
						{:else}
							<span style="color:#d97706">Non lié</span>
						{/if}
					</td>
					<td style="font-size:.8rem;color:var(--color-text-muted)">
						{#if imp.locataire}
							{imp.locataire.prenom} {imp.locataire.nom}
						{:else if imp.nom_locataire}
							<span style="color:#d97706">Non lié</span>
						{:else}—{/if}
					</td>
					<td><span class="badge {statutBadge[imp.statut] ?? 'badge-gray'}">{statutLabel[imp.statut] ?? imp.statut}</span></td>
					<td>
						{#if imp.statut !== 'resolu' && imp.statut !== 'ignore'}
							<div class="action-row">
									<button class="btn-icon-edit" aria-label="Modifier" title="Modifier" on:click={() => openEdit(imp)}>✏️</button>
									{#if imp.user_proprietaire_id && imp.code}
										<button class="btn btn-sm btn-primary" on:click={() => resoudre(imp.id)}>✓ Créer</button>
									{/if}
									<button class="btn-icon-warn" aria-label="Ignorer cet import" title="Ignorer" on:click={() => ignorer(imp.id)}>⊘</button>
							</div>
						{:else if imp.statut === 'resolu'}
							<div class="action-row">
								<span class="badge badge-green" style="font-size:.75rem">✓ Badge #{imp.vigik_id}</span>
								<button class="btn-icon-edit" aria-label="Corriger les liens" title="Corriger les liens" on:click={() => openEdit(imp)}>✏️</button>
							</div>
						{/if}
					</td>
				</tr>

				<!-- Formulaire d'édition inline -->
				{#if editId === imp.id}
				<tr class="edit-row">
					<td colspan="10">
						<div class="edit-form card" style="margin:.5rem 0">
							<h3 style="font-size:.9rem;font-weight:700;margin-bottom:.75rem">
								Lier : <em>{imp.nom_proprietaire}</em>
							</h3>
							<div class="edit-grid">
								<div class="field">
									<label for="vigik-proprio">Propriétaire *</label>
									<select id="vigik-proprio" bind:value={editProprio}>
										<option value="">— Non lié —</option>
										{#each utilisateurs as u}
											<option value={String(u.id)}>{u.prenom} {u.nom} ({u.email})</option>
										{/each}
									</select>
								</div>
								<div class="field">
									<label for="vigik-loc">Locataire</label>
									<select id="vigik-loc" bind:value={editLoc}>
										<option value="">— Aucun —</option>
										{#each utilisateurs as u}
											<option value={String(u.id)}>{u.prenom} {u.nom} ({u.email})</option>
										{/each}
									</select>
								</div>
								<div class="field">
									<label for="vigik-lot">Lot</label>
									<select id="vigik-lot" bind:value={editLot}>
										<option value="">— Auto / Inconnu —</option>
										{#each lots as l}
											<option value={String(l.id)}>Bât.{l.batiment_nom ?? l.batiment_id} — {l.numero} ({l.type})</option>
										{/each}
									</select>
								</div>
								<div class="field field-checkbox">
									<label>
										<input type="checkbox" bind:checked={editChezLoc} />
										Vigik chez le locataire
									</label>
								</div>
								<div class="field" style="grid-column:span 2">
									<label for="vigik-notes">Notes admin</label>
									<input id="vigik-notes" type="text" bind:value={editNotes} placeholder="Note interne…" />
								</div>
							</div>
							<div class="form-actions">
								<button class="btn btn-outline" on:click={cancelEdit} disabled={saving}>Annuler</button>
								<button class="btn btn-primary" on:click={saveEdit} disabled={saving}>
									{saving ? 'Enregistrement…' : 'Enregistrer'}
								</button>
							</div>
						</div>
					</td>
				</tr>
				{/if}
			{/each}
		</tbody>
	</table>
</div>
{/if}

<style>
	.page-header {
		display: flex;
		align-items: center;
		gap: .5rem;
		margin-bottom: 1.5rem;
	}
	h1 { font-size: 1.4rem; font-weight: 700; }

	.stats-bar {
		display: flex;
		gap: 1.5rem;
		padding: .75rem 1.25rem;
		margin-bottom: 1.25rem;
		flex-wrap: wrap;
	}
	.stat { display: flex; flex-direction: column; align-items: center; gap: .1rem; }
	.stat-val { font-size: 1.4rem; font-weight: 700; line-height: 1.2; }
	.stat-lbl { font-size: .75rem; color: var(--color-text-muted); }

	.upload-section { padding: 1rem 1.25rem; margin-bottom: 1rem; }
	.upload-row {
		display: flex;
		gap: .75rem;
		align-items: center;
		flex-wrap: wrap;
	}
	.file-input { flex: 1; min-width: 200px; }
	.checkbox-label { display: flex; align-items: center; gap: .4rem; font-size: .875rem; }

	.toolbar {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: .75rem;
		margin-bottom: .75rem;
		flex-wrap: wrap;
	}

	.table-dense td, .table-dense th { padding: .35rem .55rem; }
	.row-resolu td { opacity: .55; }
	.row-ignore td { opacity: .4; }

	.edit-row td { background: var(--color-bg-secondary, #f8f9fa); padding: 0; }
	.edit-form { padding: .75rem 1rem; border-left: 3px solid var(--color-primary, #1a56db); }
	.edit-grid {
		display: grid;
		grid-template-columns: 1fr 1fr 1fr 1fr;
		gap: .5rem .75rem;
		margin-bottom: .75rem;
	}
	.field-checkbox { display: flex; align-items: flex-end; }
	.field-checkbox label { display: flex; align-items: center; gap: .4rem; font-size: .875rem; }

	@media (max-width: 900px) {
		.edit-grid { grid-template-columns: 1fr 1fr; }
	}
	@media (max-width: 600px) {
		.edit-grid { grid-template-columns: 1fr; }
		.stats-bar { gap: 1rem; }
	}
</style>
