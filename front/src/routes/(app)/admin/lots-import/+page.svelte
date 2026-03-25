<script lang="ts">
	import { onMount } from 'svelte';
	import { lots as lotsApi, api } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { siteNomStore } from '$lib/stores/pageConfig';

	$: _siteNom = $siteNomStore;
	// ── Données ─────────────────────────────────────────────────────────────
	let imports: any[] = [];
	let stats: any = null;
	let utilisateurs: any[] = [];
	let lots: any[] = [];
	let batiments: any[] = [];
	let loading = true;
	let filtre = '';
	let tri = 'copro'; // copro | batiment | numero

	// ── Upload ───────────────────────────────────────────────────────────────
	let uploadFile: FileList | null = null;
	let remplacer = false;
	let uploading = false;

	async function uploadExcel() {
		if (!uploadFile?.length) { toast('error', 'Choisissez un fichier .xlsx'); return; }
		uploading = true;
		try {
			const result = await lotsApi.uploadImport(uploadFile[0], remplacer);
			toast('success', `Import : ${result.importes} ajoutés, ${result.doublons} doublons, ${result.ignores} ignorés${result.auto_resolus ? ` — ${result.auto_resolus} copropriétaire(s) résolu(s) automatiquement` : ''}`);
			if (result.erreurs?.length) toast('error', result.erreurs.slice(0, 3).join('\n'));
			if (result.auto_skipped_locataire) toast('info', `${result.auto_skipped_locataire} import(s) avec locataire à traiter manuellement`);
			if (result.auto_skipped_no_lot) toast('info', `${result.auto_skipped_no_lot} parking(s) sans lot — à associer via ✏️`);
			await reload();
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur import');
		} finally {
			uploading = false;
			uploadFile = null;
		}
	}

	// ── Auto-match ───────────────────────────────────────────────────────────
	let autoMatching = false;

	async function autoMatch() {
		autoMatching = true;
		try {
			const r = await lotsApi.autoMatchImports();
			toast('success', `${r.matches} liaison(s) automatique(s) trouvée(s)`);
			await reload();
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		} finally {
			autoMatching = false;
		}
	}

	// ── Auto-résoudre copropriétaires ────────────────────────────────────────
	let autoResolving = false;

	async function autoResoudre() {
		autoResolving = true;
		try {
			const r = await lotsApi.autoResoudreImports();
			toast('success', `${r.resolus} copropriétaire(s) résolu(s) automatiquement`);
			if (r.skipped_locataire) toast('info', `${r.skipped_locataire} import(s) avec locataire laissé(s) en staging`);
			if (r.skipped_no_lot) toast('info', `${r.skipped_no_lot} parking(s) sans lot lié — à traiter manuellement`);
			await reload();
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		} finally {
			autoResolving = false;
		}
	}

	// ── Édition inline ───────────────────────────────────────────────────────
	let editId: number | null = null;
	let editLot = '';
	let editOccupants: { user_id: string; type_lien: string }[] = [];
	let editNotes = '';
	let saving = false;

	const TYPES_LIEN = [
		{ value: 'propriétaire', label: 'Copropriétaire résident' },
		{ value: 'bailleur',     label: 'Copropriétaire bailleur' },
		{ value: 'locataire',   label: 'Locataire' },
		{ value: 'mandataire',  label: 'Mandataire (gestion)' },
	];
	const TYPE_LIEN_BADGE: Record<string, string> = {
		'propriétaire': '#16a34a',
		'bailleur':     '#2563eb',
		'locataire':    '#d97706',
		'mandataire':   '#7c3aed',
	};
	const TYPE_LIEN_LABEL: Record<string, string> = {
		'propriétaire': 'Propriétaire',
		'bailleur':     'Bailleur',
		'locataire':    'Locataire',
		'mandataire':   'Mandataire',
	};

	function openEdit(imp: any) {
		editId = imp.id;
		editLot = String(imp.lot_id ?? '');
		editNotes = imp.notes_admin ?? '';
		if (imp.utilisateurs?.length) {
			editOccupants = imp.utilisateurs.map((u: any) => ({
				user_id: String(u.user_id ?? ''),
				type_lien: u.type_lien ?? 'propriétaire',
			}));
		} else {
			editOccupants = [{ user_id: '', type_lien: 'propriétaire' }];
		}
	}

	function ajouterOccupant() {
		editOccupants = [...editOccupants, { user_id: '', type_lien: 'locataire' }];
	}

	function supprimerOccupant(i: number) {
		editOccupants = editOccupants.filter((_, idx) => idx !== i);
	}

	function cancelEdit() { editId = null; }

	async function saveEdit() {
		if (editId === null) return;
		saving = true;
		try {
			const utilisateurs = editOccupants
				.filter(o => o.user_id)
				.map(o => ({ user_id: Number(o.user_id), type_lien: o.type_lien }));
			await lotsApi.patchImport(editId, {
				lot_id:      editLot ? Number(editLot) : null,
				utilisateurs,
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

	// ── Résolution / Ignorer ─────────────────────────────────────────────────
	async function resoudre(id: number) {
		if (!confirm('Créer/confirmer le lot et créer le lien copropriétaire ?')) return;
		try {
			await lotsApi.resoudreImport(id);
			toast('success', 'Lot confirmé et lien copropriétaire créé');
			await reload();
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur résolution');
		}
	}

	async function ignorer(id: number) {
		if (!confirm('Ignorer cet import ?')) return;
		try {
			await lotsApi.ignorerimport(id);
			toast('info', 'Import ignoré');
			await reload();
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		}
	}

	// ── Chargement ───────────────────────────────────────────────────────────
	async function reload() {
		[imports, stats] = await Promise.all([
			lotsApi.listImports(filtre || undefined, tri),
			lotsApi.statsImports(),
		]);
	}

	onMount(async () => {
		loading = true;
		try {
			[utilisateurs, lots, batiments] = await Promise.all([
				api.get<any[]>('/admin/utilisateurs'),
				lotsApi.tous(),
				api.get<any[]>('/copropriete/batiments'),
			]);
			await reload();
		} catch (e) {
			toast('error', 'Erreur de chargement');
		} finally {
			loading = false;
		}
	});

	// ── Helpers ──────────────────────────────────────────────────────────────
	const statutBadge: Record<string, string> = {
		en_attente:      'badge-orange',
		utilisateur_lie: 'badge-purple',
		lot_lie:         'badge-blue',
		resolu:          'badge-green',
		ignore:          'badge-gray',
	};
	const statutLabel: Record<string, string> = {
		en_attente:      'En attente',
		utilisateur_lie: 'Occupant lié',
		lot_lie:         'Lot lié',
		resolu:          'Résolu',
		ignore:          'Ignoré',
	};
</script>

<svelte:head><title>Import Lots — {_siteNom}</title></svelte:head>

<div class="page-header">
	<a href="/admin" class="btn btn-outline btn-sm" style="margin-right:.75rem">← Paramétrage</a>
	<h1>&#x1F3E0; Import Lots</h1>
</div>

<!-- ── Stats ─────────────────────────────────────────────────────────────── -->
{#if stats}
<div class="stats-bar card">
	<div class="stat"><span class="stat-val">{stats.total}</span><span class="stat-lbl">Total</span></div>
	<div class="stat"><span class="stat-val" style="color:#d97706">{stats.en_attente}</span><span class="stat-lbl">En attente</span></div>
	<div class="stat"><span class="stat-val" style="color:#7c3aed">{stats.utilisateur_lie ?? 0}</span><span class="stat-lbl">Occupant lié</span></div>
	<div class="stat"><span class="stat-val" style="color:#2563eb">{stats.lot_lie}</span><span class="stat-lbl">Lot lié</span></div>
	<div class="stat"><span class="stat-val" style="color:#16a34a">{stats.resolu}</span><span class="stat-lbl">Résolus</span></div>
	<div class="stat"><span class="stat-val" style="color:#6b7280">{stats.ignore}</span><span class="stat-lbl">Ignorés</span></div>
	<div class="stat"><span class="stat-val">{stats.avec_user}</span><span class="stat-lbl">Copro lié</span></div>
</div>
{/if}

<!-- ── Upload ────────────────────────────────────────────────────────────── -->
<div class="card upload-section">
	<h2 class="section-title">Importer un fichier Excel</h2>
	<p class="muted" style="font-size:.85rem;margin-bottom:.75rem">
		Colonnes attendues : <code>ID_BATIMENT | N° LOT | TYPE | ÉTAGE | N° PORTE | N° COPROPRIÉTAIRE | NOM COPROPRIÉTAIRE</code>
	</p>
	<div class="upload-row">
		<input type="file" accept=".xlsx,.xls" bind:files={uploadFile} class="file-input" />
		<label class="checkbox-label">
			<input type="checkbox" bind:checked={remplacer} />
			Remplacer les imports non résolus
		</label>
		<button class="btn btn-primary" on:click={uploadExcel} disabled={uploading || !uploadFile?.length}>
			{uploading ? 'Import…' : 'Importer'}
		</button>
	</div>
</div>

<!-- ── Filtres + actions ─────────────────────────────────────────────────── -->
<div class="toolbar">
	<div style="display:flex;gap:.5rem;align-items:center">
		<span class="muted" style="font-size:.85rem">Filtrer :</span>
		{#each ['', 'en_attente', 'utilisateur_lie', 'lot_lie', 'resolu', 'ignore'] as s}
			<button
				class="btn btn-sm {filtre === s ? 'btn-primary' : 'btn-outline'}"
				on:click={async () => { filtre = s; await reload(); }}>
				{s === '' ? 'Tous' : statutLabel[s]}
			</button>
		{/each}
	</div>
	<div style="display:flex;gap:.35rem;align-items:center">
		<button class="btn btn-outline btn-sm" on:click={autoMatch} disabled={autoMatching}>
			{autoMatching ? 'Recherche…' : '\u{1F517} Auto-match'}
		</button>
		<button class="btn btn-outline btn-sm" on:click={autoResoudre} disabled={autoResolving}>
			{autoResolving ? 'Résolution…' : '✅ Auto-résoudre copropriétaires'}
		</button>
	</div>
</div>

<!-- ── Table ─────────────────────────────────────────────────────────────── -->
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
				<th>Nom copropriétaire</th><th>N° Copro</th>
				<th>Bât.</th><th>N° Lot</th><th>Type</th><th>Étage</th>
				<th>Lot lié</th><th>Occupants liés</th>
				<th>Statut</th><th>Actions</th>
			</tr>
		</thead>
		<tbody>
			{#each imports as imp (imp.id)}
				<tr class:row-resolu={imp.statut === 'resolu'} class:row-ignore={imp.statut === 'ignore'}>
					<td style="font-weight:600">{imp.nom_coproprietaire ?? '—'}</td>
					<td style="font-size:.8rem;color:var(--color-text-muted)">{imp.no_coproprietaire ?? '—'}</td>
					<td style="font-size:.8rem;font-weight:600">{imp.batiment_nom ?? imp.batiment_id}</td>
					<td style="font-weight:500">{imp.numero}</td>
					<td><span class="badge badge-type">{imp.type_raw}</span></td>
					<td style="font-size:.8rem;color:var(--color-text-muted)">{imp.etage_raw ?? '—'}</td>
					<td style="font-size:.8rem;color:var(--color-text-muted)">{imp.lot_label ?? '—'}</td>
					<td style="font-size:.8rem">
						{#if imp.utilisateurs?.length}
							<div class="occupants-list">
								{#each imp.utilisateurs as occ}
									<div class="occupant-tag">
										<span class="occ-role" style="color:{TYPE_LIEN_BADGE[occ.type_lien] ?? '#6b7280'}">{TYPE_LIEN_LABEL[occ.type_lien] ?? occ.type_lien}</span>
										{#if occ.utilisateur}
											<span style="color:#16a34a">{occ.utilisateur.prenom} {occ.utilisateur.nom}</span>
										{:else}
											<span style="color:#d97706">Non lié</span>
										{/if}
									</div>
								{/each}
							</div>
						{:else if imp.nom_coproprietaire}
							<span style="color:#d97706">Non lié</span>
						{:else}—{/if}
					</td>
					<td><span class="badge {statutBadge[imp.statut] ?? 'badge-gray'}">{statutLabel[imp.statut] ?? imp.statut}</span></td>
					<td>
							{#if imp.statut !== 'resolu' && imp.statut !== 'ignore'}
							<div class="action-row">
								<button class="btn-icon-edit" aria-label="Modifier" title="Modifier" on:click={() => openEdit(imp)}>✏️</button>
							{#if imp.utilisateurs?.length > 0}
								<button class="btn btn-sm btn-primary" on:click={() => resoudre(imp.id)}>✓ Valider</button>
								{/if}
								<button class="btn-icon-warn" aria-label="Ignorer cet import" title="Ignorer" on:click={() => ignorer(imp.id)}>⊘</button>
							</div>
						{:else if imp.statut === 'resolu'}
								<div class="action-row">
									<span class="badge badge-green" style="font-size:.75rem">✓ Lot #{imp.lot_id}</span>
									<button class="btn-icon-edit" aria-label="Lier un occupant" title="Lier un occupant" on:click={() => openEdit(imp)}>✏️</button>
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
							Lier : <em>{imp.nom_coproprietaire ?? '—'} — Bât. {imp.batiment_nom ?? imp.batiment_id} n°{imp.numero} ({imp.type_raw})</em>
							</h3>
							<!-- Lot en base -->
							<div class="field" style="margin-bottom:.75rem">
								<label>Lot en base</label>
								<select bind:value={editLot}>
									<option value="">— Non lié —</option>
									{#each lots as l}
										<option value={String(l.id)}>{l.batiment_nom ?? `Bât.${l.batiment_id}`} — {l.numero} ({l.type})</option>
									{/each}
								</select>
							</div>
							<!-- Occupants -->
							<div class="occupants-editor">
								<div class="occupants-header">
									<span style="font-size:.85rem;font-weight:600">Occupants du lot</span>
									<button type="button" class="btn btn-sm btn-outline" on:click={ajouterOccupant}>+ Ajouter</button>
								</div>
								{#each editOccupants as occ, i}
								<div class="occupant-row">
									<select bind:value={occ.type_lien} class="select-role">
										{#each TYPES_LIEN as tl}
											<option value={tl.value}>{tl.label}</option>
										{/each}
									</select>
									<select bind:value={occ.user_id} class="select-user">
										<option value="">— Non lié —</option>
										{#each utilisateurs as u}
											<option value={String(u.id)}>{u.prenom} {u.nom} ({u.email})</option>
										{/each}
									</select>
									<button type="button" class="btn-icon-danger" aria-label="Retirer cet occupant" title="Retirer" on:click={() => supprimerOccupant(i)}>&#x1F5D1;️</button>
								</div>
								{/each}
							</div>
							<!-- Notes -->
							<div class="field" style="margin-top:.75rem">
								<label>Notes admin</label>
								<input type="text" bind:value={editNotes} placeholder="Note interne…" />
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

	.badge-type {
		background: #f0f4ff;
		color: #1e40af;
		font-size: .75rem;
		padding: .1rem .4rem;
		border-radius: 4px;
		font-weight: 600;
	}

	.table-dense td, .table-dense th { padding: .35rem .55rem; }
	.row-resolu td { opacity: .55; }
	.row-ignore td { opacity: .4; }

	.edit-row td { background: var(--color-bg-secondary, #f8f9fa); padding: 0; }
	.edit-form { padding: .75rem 1rem; border-left: 3px solid var(--color-primary, #1a56db); }
	.occupants-editor {
		border: 1px solid var(--color-border, #e5e7eb);
		border-radius: 6px;
		padding: .5rem .75rem;
		margin-bottom: .25rem;
	}
	.occupants-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: .5rem;
	}
	.occupant-row {
		display: flex;
		gap: .5rem;
		align-items: center;
		margin-bottom: .4rem;
	}
	.select-role { min-width: 180px; flex-shrink: 0; }
	.select-user { flex: 1; min-width: 0; }

	.occupants-list { display: flex; flex-direction: column; gap: .2rem; }
	.occupant-tag { display: flex; gap: .35rem; align-items: baseline; font-size: .8rem; }
	.occ-role { font-weight: 600; font-size: .72rem; }

	@media (max-width: 600px) {
		.occupant-row { flex-wrap: wrap; }
		.select-role { min-width: 140px; }
	}
	@media (max-width: 600px) {
		.stats-bar { gap: 1rem; }
	}
</style>
