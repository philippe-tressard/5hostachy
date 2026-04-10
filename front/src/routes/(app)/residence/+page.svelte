<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import { onMount } from 'svelte';
	import { isCS, currentUser } from '$lib/stores/auth';
	$: isLocataire = $currentUser?.statut === 'locataire';
	import {
		copropriete as coproprieteApi,
		uploads as uploadsApi,
		documents as documentsApi,
		diagnostics as diagnosticsApi,
		reglesResidence as reglesApi,
		ApiError,
	} from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { getPageConfig, configStore, siteNomStore } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';
	import { fmtDateShort as fmt } from '$lib/date';

	$: _pc = getPageConfig($configStore, 'residence', {
		titre: 'Ma résidence',
		navLabel: 'Résidence',
		icone: 'building-2',
		descriptif: 'Informations, plans et documents de la copropriété.',
	});
	$: _siteNom = $siteNomStore;

	// ── State ──────────────────────────────────────────────────────────────────
	let copropriete: any = null;
	let batiments: any[] = [];
	let plans: any[] = [];
	let reglements: any[] = [];
	let crAg: any[] = [];
	let regles: any[] = [];
	let loading = true;

	let catIdPlan: number | null = null;
	let catIdReglement: number | null = null;
	let catIdCrAg: number | null = null;

	// Édition résidence
	let editing = false;
	let saving = false;
	let editNom = '';
	let editAdresse = '';
	let editAnnee: string | number = '';
	let editNbLots: string | number = '';
	let editImmatriculation = '';
	let editAssuranceCompagnie = '';
	let editAssuranceNumero = '';
	let editAssuranceEcheance = '';

	// Photo bannière
	let uploadingPhoto = false;

	// Formulaires documents
	let showPlanForm = false;
	let newPlanTitre = '';
	let newPlanPerimetre: 'résidence' | 'bâtiment' = 'résidence';
	let newPlanBatimentId = 0;
	let newPlanFile: File | null = null;
	let savingPlan = false;

	let showReglementForm = false;
	let newReglementTitre = '';
	let newReglementFile: File | null = null;
	let savingReglement = false;

	let showCrAgForm = false;
	let newCrAgTitre = '';
	let newCrAgAnnee: string | number = '';
	let newCrAgDateAg = '';
	let newCrAgScope: 'copropriété' | 'bâtiment' = 'copropriété';
	let newCrAgBatimentIds: number[] = [];
	let newCrAgFile: File | null = null;
	let savingCrAg = false;

	// Édition document (plans, règlements, CR d'AG)
	let editingDocId: number | null = null;
	let editingDocMode: 'plan' | 'reglement' | 'ag' = 'plan';
	let editingDocTitre = '';
	let editingDocAnnee: string | number = '';
	let editingDocDate = '';
	let savingDoc = false;

	// Diagnostics réglementaires
	let diagnosticTypes: any[] = [];
	let showDiagForm: number | null = null;  // id du type en cours d'ajout
	let newDiagTitre = '';
	let newDiagDate = '';
	let newDiagFiles: FileList | null = null;
	let savingDiag = false;
	let editingRapportId: number | null = null;
	let editingRapportTitre = '';
	let editingRapportDate = '';
	let editingRapportSynthese = '';
	let savingRapport = false;
	let togglingNonApplicableId: number | null = null;
	let expandedSynths = new Set<number>();

	// Règles & Recommandations
	let showRegleForm = false;
	let editingRegleId: number | null = null;
	let regleTitre = '';
	let regleContenu = '';
	let savingRegle = false;

	// ── Derived ────────────────────────────────────────────────────────────────
	// Composition depuis les champs stockés sur Batiment et Copropriete
	$: hasOrphanLots = (copropriete?.nb_parkings_communs ?? 0) > 0;
	$: totalAppart  = batiments.reduce((s, b) => s + (b.nb_appartements ?? 0), 0);
	$: totalCave    = batiments.reduce((s, b) => s + (b.nb_caves ?? 0), 0);
	$: totalParking = batiments.reduce((s, b) => s + (b.nb_parkings ?? 0), 0) + (copropriete?.nb_parkings_communs ?? 0);
	$: totalLocaux  = batiments.reduce((s, b) => s + (b.nb_locaux_commerciaux ?? 0), 0);

	$: activeDiagTypes       = diagnosticTypes.filter((t) => !t.non_applicable);
	$: nonApplicableDiagTypes = diagnosticTypes.filter((t) => t.non_applicable);

	$: sortedPlans = [...plans].sort((a, b) => {
		if (!a.batiment_id && b.batiment_id) return -1;
		if (a.batiment_id && !b.batiment_id) return 1;
		const bA = batiments.find((x) => x.id === a.batiment_id);
		const bB = batiments.find((x) => x.id === b.batiment_id);
		return (bA?.numero ?? '').localeCompare(bB?.numero ?? '');
	});
	$: sortedCrAg = [...crAg].sort((a, b) => {
		const anneeB = (b.annee as number) ?? 0;
		const anneeA = (a.annee as number) ?? 0;
		if (anneeB !== anneeA) return anneeB - anneeA;
		const dateB = (b.date_ag ?? b.publie_le ?? '') as string;
		const dateA = (a.date_ag ?? a.publie_le ?? '') as string;
		return dateB.localeCompare(dateA);
	});

	function batimentLabel(id: number | null | undefined): string {
		if (!id) return 'Résidence';
		const b = batiments.find((x) => x.id === id);
		return b ? `Bât. ${b.numero}` : 'Bât. ?';
	}

	// ── Init ───────────────────────────────────────────────────────────────────
	onMount(async () => {
		try {
			const [copro, bats, cats] = await Promise.all([
				coproprieteApi.get().catch(() => null),
				coproprieteApi.batiments().catch(() => []),
				documentsApi.listCategories().catch(() => []),
			]);
			copropriete = copro;
			batiments   = bats;

			catIdPlan      = (cats as any[]).find((c) => c.code === 'plan_residence')?.id ?? null;
			catIdReglement = (cats as any[]).find((c) => c.code === 'reglement_copropriete')?.id ?? null;
			catIdCrAg      = (cats as any[]).find((c) => c.code === 'pv_ag')?.id ?? null;

			const [p, r, ag, diag] = await Promise.all([
				catIdPlan      ? documentsApi.list(catIdPlan).catch(() => [])      : Promise.resolve([]),
				catIdReglement ? documentsApi.list(catIdReglement).catch(() => []) : Promise.resolve([]),
				catIdCrAg      ? documentsApi.list(catIdCrAg).catch(() => [])      : Promise.resolve([]),
				diagnosticsApi.listTypes().catch(() => []),
			]);
			plans          = p as any[];
			reglements     = r as any[];
			crAg           = ag as any[];
			diagnosticTypes = diag as any[];

			regles = await reglesApi.list().catch(() => []);
		} catch {
			toast('error', 'Erreur de chargement');
		} finally {
			loading = false;
		}
	});

	// ── Édition résidence ──────────────────────────────────────────────────────
	function startEdit() {
		if (!copropriete) return;
		editNom               = copropriete.nom ?? '';
		editAdresse           = copropriete.adresse ?? '';
		editAnnee             = copropriete.annee_construction ?? '';
		editNbLots            = copropriete.nb_lots_total ?? '';
		editImmatriculation   = copropriete.numero_immatriculation ?? '';
		editAssuranceCompagnie = copropriete.assurance_compagnie ?? '';
		editAssuranceNumero   = copropriete.assurance_numero_police ?? '';
		editAssuranceEcheance = copropriete.assurance_echeance
			? String(copropriete.assurance_echeance).substring(0, 10)
			: '';
		editing = true;
	}

	async function saveEdit() {
		saving = true;
		try {
			copropriete = await coproprieteApi.update({
				nom:                     editNom || undefined,
				adresse:                 editAdresse || undefined,
				annee_construction:      editAnnee ? Number(editAnnee) : undefined,
				nb_lots_total:           editNbLots ? Number(editNbLots) : undefined,
				numero_immatriculation:  editImmatriculation || undefined,
				assurance_compagnie:     editAssuranceCompagnie || undefined,
				assurance_numero_police: editAssuranceNumero || undefined,
				assurance_echeance:      editAssuranceEcheance || undefined,
			});
			editing = false;
			toast('success', 'Résidence mise à jour');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			saving = false;
		}
	}

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
		if (!confirm('Supprimer cette règle ?')) return;
		try {
			await reglesApi.remove(id);
			regles = regles.filter((r) => r.id !== id);
			toast('success', 'Règle supprimée');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}

	// ── Photo ──────────────────────────────────────────────────────────────────
	async function handlePhotoFile(e: Event) {
		const file = (e.target as HTMLInputElement).files?.[0];
		if (!file) return;
		uploadingPhoto = true;
		try {
			const { url } = await uploadsApi.residence(file);
			if (copropriete) copropriete = { ...copropriete, photo_url: url };
			toast('success', 'Photo mise à jour');
		} catch (err) {
			toast('error', err instanceof ApiError ? err.message : 'Erreur upload');
		} finally {
			uploadingPhoto = false;
			(e.target as HTMLInputElement).value = '';
		}
	}

	// ── Plans ──────────────────────────────────────────────────────────────────
	async function addPlan() {
		if (!catIdPlan || !newPlanTitre.trim() || !newPlanFile) return;
		savingPlan = true;
		try {
			const doc = await documentsApi.upload(
				newPlanTitre.trim(),
				catIdPlan,
				newPlanFile,
				newPlanPerimetre,
				newPlanPerimetre === 'bâtiment' && newPlanBatimentId ? newPlanBatimentId : undefined,
			);
			plans = [doc, ...plans];
			showPlanForm = false;
			newPlanTitre = ''; newPlanPerimetre = 'résidence'; newPlanBatimentId = 0; newPlanFile = null;
			toast('success', 'Plan ajouté');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			savingPlan = false;
		}
	}

	async function deletePlan(id: number) {
		if (!confirm('Supprimer ce plan ?')) return;
		try {
			await documentsApi.delete(id);
			plans = plans.filter((d) => d.id !== id);
			toast('success', 'Plan supprimé');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}

	// ── Règlement ──────────────────────────────────────────────────────────────
	async function addReglement() {
		if (!catIdReglement || !newReglementTitre.trim() || !newReglementFile) return;
		savingReglement = true;
		try {
			const doc = await documentsApi.upload(newReglementTitre.trim(), catIdReglement, newReglementFile, 'résidence');
			reglements = [doc, ...reglements];
			showReglementForm = false;
			newReglementTitre = ''; newReglementFile = null;
			toast('success', 'Règlement ajouté');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			savingReglement = false;
		}
	}

	async function deleteReglement(id: number) {
		if (!confirm('Supprimer ce document ?')) return;
		try {
			await documentsApi.delete(id);
			reglements = reglements.filter((d) => d.id !== id);
			toast('success', 'Supprimé');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}

	// ── CR d'AG ────────────────────────────────────────────────────────────────
	async function addCrAg() {
		if (!catIdCrAg || !newCrAgTitre.trim() || !newCrAgFile) return;
		if (!newCrAgAnnee || !newCrAgDateAg) return;
		if (newCrAgScope === 'bâtiment' && newCrAgBatimentIds.length === 0) return;
		savingCrAg = true;
		try {
			let perimetre: string;
			let batimentId: number | undefined;
			let batimentsJson: string | undefined;
			if (newCrAgScope === 'copropriété') {
				perimetre = 'résidence';
			} else if (newCrAgBatimentIds.length === 1) {
				perimetre = 'bâtiment';
				batimentId = newCrAgBatimentIds[0];
			} else {
				perimetre = 'résidence';
				batimentsJson = JSON.stringify(newCrAgBatimentIds);
			}
			const doc = await documentsApi.upload(
				newCrAgTitre.trim(), catIdCrAg, newCrAgFile, perimetre, batimentId,
				newCrAgAnnee ? Number(newCrAgAnnee) : undefined,
				newCrAgDateAg || undefined,
				batimentsJson,
			);
			crAg = [doc, ...crAg];
			showCrAgForm = false;
			newCrAgTitre = ''; newCrAgAnnee = ''; newCrAgDateAg = '';
			newCrAgScope = 'copropriété'; newCrAgBatimentIds = []; newCrAgFile = null;
			toast('success', 'CR d\'AG ajouté');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			savingCrAg = false;
		}
	}

	async function deleteCrAg(id: number) {
		if (!confirm('Supprimer ce document ?')) return;
		try {
			await documentsApi.delete(id);
			crAg = crAg.filter((d) => d.id !== id);
			toast('success', 'Supprimé');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}

	// ── Édition document ───────────────────────────────────────────────────────────────────
	function startEditDoc(doc: any, mode: 'plan' | 'reglement' | 'ag') {
		editingDocId = doc.id;
		editingDocMode = mode;
		editingDocTitre = doc.titre ?? '';
		editingDocAnnee = doc.annee ?? '';
		editingDocDate = doc.date_ag ? String(doc.date_ag).substring(0, 10) : '';
	}

	async function saveEditDoc() {
		if (!editingDocId) return;
		savingDoc = true;
		try {
			const updated = await documentsApi.update(editingDocId, {
				titre: editingDocTitre.trim() || undefined,
				annee: editingDocAnnee ? Number(editingDocAnnee) : null,
				date_ag: editingDocDate || null,
			});
			if (editingDocMode === 'plan') {
				plans = plans.map((d) => (d.id === editingDocId ? updated : d));
			} else if (editingDocMode === 'reglement') {
				reglements = reglements.map((d) => (d.id === editingDocId ? updated : d));
			} else {
				crAg = crAg.map((d) => (d.id === editingDocId ? updated : d));
			}
			editingDocId = null;
			toast('success', 'Document mis à jour');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			savingDoc = false;
		}
	}

	// ── Diagnostics réglementaires ───────────────────────────────────────────────────────
	function startAddRapport(typeId: number) {
		showDiagForm = typeId;
		newDiagTitre = '';
		newDiagDate = '';
		newDiagFiles = null;
	}

	async function addRapport() {
		if (!showDiagForm || !newDiagFiles?.length) return;
		savingDiag = true;
		const files = Array.from(newDiagFiles);
		const newRapports: any[] = [];
		try {
			for (const file of files) {
				const titre = newDiagTitre.trim() || file.name.replace(/\.[^.]+$/, '');
				const rapport = await diagnosticsApi.uploadRapport(
					showDiagForm,
					titre,
					newDiagDate || undefined,
					file,
				);
				newRapports.push(rapport);
			}
			diagnosticTypes = diagnosticTypes.map((t) =>
				t.id === showDiagForm
					? { ...t, rapports: [...newRapports, ...t.rapports] }
					: t
			);
			showDiagForm = null;
			toast('success', files.length > 1 ? `${files.length} rapports ajoutés` : 'Rapport ajouté');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			savingDiag = false;
		}
	}

	function startEditRapport(r: any) {
		editingRapportId = r.id;
		editingRapportTitre = r.titre;
		editingRapportDate = r.date_rapport ? String(r.date_rapport).substring(0, 10) : '';
		editingRapportSynthese = r.synthese ?? '';
	}

	async function saveRapport() {
		if (!editingRapportId) return;
		savingRapport = true;
		try {
			const updated = await diagnosticsApi.updateRapport(editingRapportId, {
				titre: editingRapportTitre.trim() || undefined,
				date_rapport: editingRapportDate || null,
				synthese: editingRapportSynthese.trim() || null,
			});
			diagnosticTypes = diagnosticTypes.map((t) => ({
				...t,
				rapports: t.rapports.map((r: any) => (r.id === editingRapportId ? updated : r)),
			}));
			editingRapportId = null;
			toast('success', 'Rapport mis à jour');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			savingRapport = false;
		}
	}

	async function deleteRapport(typeId: number, rapportId: number) {
		if (!confirm('Supprimer ce rapport ?')) return;
		try {
			await diagnosticsApi.deleteRapport(rapportId);
			diagnosticTypes = diagnosticTypes.map((t) =>
				t.id === typeId
					? { ...t, rapports: t.rapports.filter((r: any) => r.id !== rapportId) }
					: t
			);
			toast('success', 'Rapport supprimé');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}

	async function toggleNonApplicable(typeId: number, value: boolean) {
		togglingNonApplicableId = typeId;
		try {
			const updated = await diagnosticsApi.toggleNonApplicable(typeId, value);
			diagnosticTypes = diagnosticTypes.map((t) =>
				t.id === typeId ? { ...t, non_applicable: updated.non_applicable } : t
			);
			toast('success', value ? 'Diagnostic masqué (non applicable)' : 'Diagnostic réactivé');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			togglingNonApplicableId = null;
		}
	}
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<div class="page-header" style="margin-bottom:.75rem">
	<h1 style="display:flex;align-items:center;gap:.4rem;font-size:1.4rem;font-weight:700">
		<Icon name={_pc.icone || 'building-2'} size={20} />{_pc.titre}
	</h1>
</div>
<div class="page-subtitle">{@html safeHtml(_pc.descriptif)}</div>

{#if loading}
	<p style="color:var(--color-text-muted)">Chargement…</p>
{:else if copropriete}

	<!-- ── Photo Bannière ─────────────────────────────────────────────────── -->
	<figure class="photo-figure">
		<div class="photo-banner">
			{#if copropriete.photo_url}
				<img src={copropriete.photo_url} alt="La résidence" />
			{:else}
				<div class="photo-placeholder">
					<Icon name="building-2" size={48} />
					<span>Aucune photo</span>
				</div>
			{/if}
			{#if $isCS}
				<label class="photo-change-btn" class:uploading={uploadingPhoto}>
					{uploadingPhoto ? '…' : '\u{1F4F8} Changer la photo'}
					<input type="file" accept="image/*" on:change={handlePhotoFile} style="display:none" />
				</label>
			{/if}
		</div>
		<figcaption class="photo-caption">{copropriete.nom}</figcaption>
	</figure>

	<!-- ── Section : Résidence ───────────────────────────────────────────── -->
	<section style="margin-bottom:2.5rem">
		<div class="section-header">
			<h2 class="section-title">&#x1F3E2; Résidence : {copropriete.nom}</h2>
			{#if $isCS && !editing}
				<button class="btn btn-sm" on:click={startEdit}>✏️ Modifier</button>
			{/if}
		</div>

		{#if editing}
			<div class="card" style="padding:1.25rem;max-width:700px">
				<form on:submit|preventDefault={saveEdit}>
					<div class="edit-grid">
						<div class="field"><label for="e-nom">Nom</label><input id="e-nom" type="text" bind:value={editNom} /></div>
						<div class="field"><label for="e-adr">Adresse</label><input id="e-adr" type="text" bind:value={editAdresse} /></div>
						<div class="field"><label for="e-ann">Année de construction</label><input id="e-ann" type="number" bind:value={editAnnee} min="1800" max="2100" /></div>
						<div class="field"><label for="e-lots">Nb lots (manuel)</label><input id="e-lots" type="number" bind:value={editNbLots} min="1" /></div>
						<div class="field"><label for="e-imm">N° immatriculation (ANAH)</label><input id="e-imm" type="text" bind:value={editImmatriculation} /></div>
						<div class="field"><label for="e-ass">Assurance – compagnie</label><input id="e-ass" type="text" bind:value={editAssuranceCompagnie} /></div>
						<div class="field"><label for="e-pol">Assurance – n° police</label><input id="e-pol" type="text" bind:value={editAssuranceNumero} /></div>
						<div class="field"><label for="e-ech">Assurance – échéance</label><input id="e-ech" type="date" bind:value={editAssuranceEcheance} /></div>
					</div>
					<div style="display:flex;gap:.5rem;justify-content:flex-end;margin-top:1rem">
						<button type="button" class="btn" on:click={() => (editing = false)}>Annuler</button>
						<button type="submit" class="btn btn-primary" disabled={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</button>
					</div>
				</form>
			</div>
		{:else}
			<div class="card" style="padding:1.25rem">
				{#if copropriete.adresse}
					<div style="margin-bottom:1rem">
						<span class="info-label">Adresse</span>
						<div class="info-value" style="margin-top:.25rem">{copropriete.adresse}</div>
					</div>
				{/if}

				{#if copropriete.numero_immatriculation || copropriete.assurance_compagnie}
					<div class="info-grid" style="margin-bottom:1.25rem">
						{#if copropriete.numero_immatriculation}
							<div class="info-item">
								<span class="info-label">N° immatriculation</span>
								<span class="info-value info-highlight">{copropriete.numero_immatriculation}</span>
							</div>
						{/if}
						{#if copropriete.assurance_compagnie}
							<div class="info-item">
								<span class="info-label">Assurance</span>
								<span class="info-value">{copropriete.assurance_compagnie}{#if copropriete.assurance_echeance} — échéance {fmt(copropriete.assurance_echeance)}{/if}</span>
							</div>
						{/if}
					</div>
				{/if}

				{#if batiments.length > 0}
					<div style="border-top:1px solid var(--color-border);padding-top:1rem">
						<p class="info-label" style="margin-bottom:.6rem">Composition</p>
						<table class="batiment-table">
							<thead>
								<tr>
									<th>Bâtiment</th>
									<th>Parkings</th>
									<th>Caves</th>
									<th>Appartements</th>
									<th>Loc. commerciaux</th>
								</tr>
							</thead>
							<tbody>
								{#each batiments as b}
									<tr>
										<td style="font-weight:600">Bât. {b.numero}</td>
										<td>{(b.nb_parkings ?? 0) > 0 ? b.nb_parkings : '—'}</td>
										<td>{(b.nb_caves ?? 0) > 0 ? b.nb_caves : '—'}</td>
										<td>{(b.nb_appartements ?? 0) > 0 ? b.nb_appartements : '—'}</td>
										<td>{(b.nb_locaux_commerciaux ?? 0) > 0 ? b.nb_locaux_commerciaux : '—'}</td>
									</tr>
								{/each}
								{#if hasOrphanLots}
									<tr>
										<td style="color:var(--color-text-muted);font-style:italic">Communs</td>
										<td>{copropriete.nb_parkings_communs}</td>
										<td>—</td>
										<td>—</td>
										<td>—</td>
									</tr>
								{/if}
							</tbody>
							<tfoot>
								<tr>
									<td>Total</td>
									<td>{totalParking > 0 ? totalParking : '—'}</td>
									<td>{totalCave > 0 ? totalCave : '—'}</td>
									<td>{totalAppart > 0 ? totalAppart : '—'}</td>
									<td>{totalLocaux > 0 ? totalLocaux : '—'}</td>
								</tr>
							</tfoot>
						</table>
					</div>
				{/if}
			</div>
		{/if}
	</section>

	<!-- ── Section : Règles & Recommandations ──────────────────────────── -->
	<section style="margin-bottom:2.5rem">
		<div class="section-header">
			<h2 class="section-title">&#x1F4CB; Règles & Recommandations</h2>
			{#if $isCS}
				<button class="btn btn-sm" on:click={() => openRegleForm()}>+ Ajouter</button>
			{/if}
		</div>

		{#if regles.length === 0}
			<p class="empty-msg">Aucune règle ajoutée.</p>
		{:else}
			<div class="doc-list">
				{#each regles as regle (regle.id)}
					<div class="doc-row card">
						<div class="doc-info" style="flex-direction:column;align-items:flex-start;gap:.25rem">
							<span class="doc-titre">{regle.titre}</span>
							{#if regle.contenu}
								<span style="font-size:.85rem;color:var(--color-text-muted);white-space:pre-wrap">{regle.contenu}</span>
							{/if}
						</div>
						{#if $isCS}
							<div class="doc-actions">
								<button class="btn-icon-edit" aria-label="Modifier" title="Modifier" on:click={() => openRegleForm(regle)}>✏️</button>
								<button class="btn-icon-danger" aria-label="Supprimer" title="Supprimer" on:click={() => deleteRegle(regle.id)}>&#x1F5D1;️</button>
							</div>
						{/if}
					</div>
				{/each}
			</div>
		{/if}
	</section>

	<!-- ── Section : Plans ───────────────────────────────────────────────── -->
	<section style="margin-bottom:2.5rem">
		<div class="section-header">
			<h2 class="section-title">&#x1F5FA;️ Plans</h2>
			{#if $isCS}
				<button class="btn btn-sm" on:click={() => (showPlanForm = true)}>+ Ajouter</button>
			{/if}
		</div>

		{#if sortedPlans.length === 0}
			<p class="empty-msg">Aucun plan ajouté.</p>
		{:else}
			<div class="doc-list">
				{#each sortedPlans as doc (doc.id)}
					<div class="doc-row card">
						<div class="doc-info">
							<Icon name="file-text" size={16} />
							<span class="doc-titre">{doc.titre}</span>
							<span class="badge badge-blue">{doc.batiment_id ? batimentLabel(doc.batiment_id) : 'Copropriété'}</span>
							<span class="doc-date">{fmt(doc.publie_le)}</span>
						</div>
						<div class="doc-actions">
							<a href={documentsApi.downloadUrl(doc.id)} target="_blank" class="btn btn-sm" download>
								⬇ Télécharger
							</a>
							{#if $isCS}
								<button class="btn-icon-edit" aria-label="Modifier" title="Modifier" on:click={() => startEditDoc(doc, 'plan')}>✏️</button>
								<button class="btn-icon-danger" aria-label="Supprimer" title="Supprimer" on:click={() => deletePlan(doc.id)}>&#x1F5D1;️</button>
							{/if}
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</section>

	<!-- ── Section : Règlement de copropriété ────────────────────────────── -->
	<section style="margin-bottom:2.5rem">
		<div class="section-header">
			<h2 class="section-title">&#x1F4D6; Règlement de copropriété</h2>
			{#if $isCS}
				<button class="btn btn-sm" on:click={() => (showReglementForm = true)}>+ Ajouter</button>
			{/if}
		</div>

		{#if reglements.length === 0}
			<p class="empty-msg">Aucun règlement ajouté.</p>
		{:else}
			<div class="doc-list">
				{#each reglements as doc (doc.id)}
					<div class="doc-row card">
						<div class="doc-info">
							<Icon name="file-text" size={16} />
							<span class="doc-titre">{doc.titre}</span>
							<span class="doc-date">{fmt(doc.publie_le)}</span>
						</div>
						<div class="doc-actions">
							<a href={documentsApi.downloadUrl(doc.id)} target="_blank" class="btn btn-sm" download>
								⬇ Télécharger
							</a>
							{#if $isCS}
							<button class="btn-icon-edit" aria-label="Modifier" title="Modifier" on:click={() => startEditDoc(doc, 'reglement')}>✏️</button>
							<button class="btn-icon-danger" aria-label="Supprimer" title="Supprimer" on:click={() => deleteReglement(doc.id)}>&#x1F5D1;️</button>
							{/if}
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</section>

	<!-- ── Section : Comptes-rendus d'AG ─────────────────────────────────── -->
	{#if !isLocataire}
	<section style="margin-bottom:2.5rem">
		<div class="section-header">
			<h2 class="section-title">&#x1F4CB; Comptes-rendus d'AG</h2>
			{#if $isCS}
				<button class="btn btn-sm" on:click={() => (showCrAgForm = true)}>+ Ajouter</button>
			{/if}
		</div>

		{#if sortedCrAg.length === 0}
			<p class="empty-msg">Aucun compte-rendu ajouté.</p>
		{:else}
			<div class="doc-list">
				{#each sortedCrAg as doc (doc.id)}
					<div class="doc-row card">
						<div class="doc-info">
							<Icon name="file-text" size={16} />
							{#if doc.annee}<span class="badge badge-gray" style="font-variant-numeric:tabular-nums">{doc.annee}</span>{/if}
							<span class="doc-titre">{doc.titre}</span>
							{#if doc.date_ag}<span class="doc-date">AG du {fmt(doc.date_ag)}</span>{/if}
							{#if doc.batiments_ids_json}
								{#each JSON.parse(doc.batiments_ids_json) as bid (bid)}
									<span class="badge badge-purple">{batimentLabel(bid)}</span>
								{/each}
							{:else if doc.batiment_id}
								<span class="badge badge-purple">{batimentLabel(doc.batiment_id)}</span>
							{:else}
								<span class="badge badge-green">Copropriété</span>
							{/if}
						</div>
						<div class="doc-actions">
							<a href={documentsApi.downloadUrl(doc.id)} target="_blank" class="btn btn-sm" download>
								⬇ Télécharger
							</a>
							{#if $isCS}
								<button class="btn-icon-edit" aria-label="Modifier" title="Modifier" on:click={() => startEditDoc(doc, 'ag')}>✏️</button>
								<button class="btn-icon-danger" aria-label="Supprimer" title="Supprimer" on:click={() => deleteCrAg(doc.id)}>&#x1F5D1;️</button>
							{/if}
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</section>
	{/if}

	<!-- ── Section : Diagnostics et Contrôles Réglementaires ────────────── -->
	{#if !isLocataire}
	<section style="margin-bottom:2.5rem">
		<div class="section-header">
			<h2 class="section-title">&#x1F50D; Diagnostics et Contrôles Réglementaires</h2>
		</div>

		{#if diagnosticTypes.length === 0}
			<p class="empty-msg">Aucun diagnostic réglementaire disponible.</p>
		{:else}
			<div class="diag-list">
				{#each activeDiagTypes as dtype (dtype.id)}
					<div class="diag-card card">
						<div class="diag-header">
							<div class="diag-title-row">
								<span class="diag-nom">{dtype.nom}</span>
								{#if dtype.frequence}
									<span class="badge badge-blue">{dtype.frequence}</span>
								{/if}
								{#if $isCS && dtype.rapports.length === 0}
									<button
										class="btn-icon"
										style="margin-left:auto"
										aria-label="Non applicable à cette copropriété"
										title="Non applicable à cette copropriété"
										disabled={togglingNonApplicableId === dtype.id}
										on:click={() => toggleNonApplicable(dtype.id, true)}
									><Icon name="eye-off" size={14} /></button>
								{/if}
							</div>
							<p class="diag-texte">{dtype.texte_legislatif}</p>
						</div>

						{#if dtype.rapports.length > 0}
							<div class="diag-rapports">
								{#each dtype.rapports as rapport (rapport.id)}
									<div class="diag-rapport-block">
										<div class="doc-row">
											<div class="doc-info">
												<Icon name="file-text" size={16} />
												<span class="doc-titre">{rapport.titre}</span>
												{#if rapport.date_rapport}
													<span class="doc-date">{fmt(rapport.date_rapport)}</span>
												{/if}
												{#if rapport.synthese}
													<button class="synthese-toggle" aria-label="Afficher la synthèse"
														on:click={() => { if (expandedSynths.has(rapport.id)) expandedSynths.delete(rapport.id); else expandedSynths.add(rapport.id); expandedSynths = expandedSynths; }}
													>&#x1F4A1; Synthèse {expandedSynths.has(rapport.id) ? '▲' : '▼'}</button>
												{/if}
											</div>
											<div class="doc-actions">
												<a href={diagnosticsApi.downloadUrl(rapport.id)} target="_blank" class="btn btn-sm" download>
													⬇ Télécharger
												</a>
												{#if $isCS}
													<button class="btn-icon-edit" aria-label="Modifier" title="Modifier" on:click={() => startEditRapport(rapport)}>✏️</button>
													<button class="btn-icon-danger" aria-label="Supprimer" title="Supprimer" on:click={() => deleteRapport(dtype.id, rapport.id)}>&#x1F5D1;️</button>
												{/if}
											</div>
										</div>
										{#if rapport.synthese && expandedSynths.has(rapport.id)}
											<div class="synthese-body rich-content">{@html safeHtml(rapport.synthese)}</div>
										{/if}
									</div>
								{/each}
							</div>
						{/if}

						{#if $isCS}
							<div class="diag-add">
								<button class="btn btn-sm" on:click={() => startAddRapport(dtype.id)}>+ Ajouter un rapport</button>
							</div>
						{/if}
					</div>
				{/each}
			</div>

			{#if $isCS && nonApplicableDiagTypes.length > 0}
				<details class="diag-non-applicable-section">
					<summary>Diagnostics non applicables ({nonApplicableDiagTypes.length})</summary>
					<div class="diag-list" style="margin-top:.75rem">
						{#each nonApplicableDiagTypes as dtype (dtype.id)}
							<div class="diag-card card diag-card-disabled">
								<div class="diag-header">
									<div class="diag-title-row">
										<span class="diag-nom">{dtype.nom}</span>
										{#if dtype.frequence}
											<span class="badge badge-blue">{dtype.frequence}</span>
										{/if}
										<button
											class="btn btn-sm"
											disabled={togglingNonApplicableId === dtype.id}
											on:click={() => toggleNonApplicable(dtype.id, false)}
										>↩ Réactiver</button>
									</div>
									<p class="diag-texte">{dtype.texte_legislatif}</p>
								</div>
							</div>
						{/each}
					</div>
				</details>
			{/if}
		{/if}
	</section>
	{/if}

{:else}
	<div class="empty-state">
		<h3>Résidence non configurée</h3>
		<p>Les informations de la résidence ne sont pas encore disponibles.</p>
	</div>
{/if}

<!-- ── Modal : ajouter un plan ────────────────────────────────────────── -->
{#if showPlanForm}
	<div class="modal-overlay" on:click|self={() => (showPlanForm = false)} role="dialog" aria-modal="true" aria-label="Ajouter un plan" tabindex="-1">
		<div class="modal" style="width:min(480px,95vw)">
			<div class="modal-header">
				<h3>Ajouter un plan</h3>
				<button class="modal-close" on:click={() => (showPlanForm = false)}>✕</button>
			</div>
			<div class="modal-body" style="display:flex;flex-direction:column;gap:.75rem">
				<div class="field">
					<label for="plan-titre">Titre *</label>
					<input id="plan-titre" type="text" bind:value={newPlanTitre} placeholder="ex : Plan de masse résidence" />
				</div>
				<div class="field">
					<label>Périmètre *</label>
					<div style="display:flex;gap:1rem;margin-top:.25rem">
						<label style="display:flex;align-items:center;gap:.4rem;cursor:pointer">
							<input type="radio" bind:group={newPlanPerimetre} value="résidence" /> Résidence entière
						</label>
						<label style="display:flex;align-items:center;gap:.4rem;cursor:pointer">
							<input type="radio" bind:group={newPlanPerimetre} value="bâtiment" /> Bâtiment spécifique
						</label>
					</div>
				</div>
				{#if newPlanPerimetre === 'bâtiment'}
					<div class="field">
						<label for="plan-bat">Bâtiment *</label>
						<select id="plan-bat" bind:value={newPlanBatimentId}>
							<option value={0}>— Sélectionner —</option>
							{#each batiments as b}
								<option value={b.id}>Bâtiment {b.numero}</option>
							{/each}
						</select>
					</div>
				{/if}
				<div class="field">
					<label for="plan-file">Fichier *</label>
					<input id="plan-file" type="file" accept=".pdf,.jpg,.jpeg,.png,.webp"
						on:change={(e) => { newPlanFile = (e.target as HTMLInputElement).files?.[0] ?? null; }} />
					{#if newPlanFile}<p style="font-size:.8rem;color:var(--color-text-muted);margin-top:.25rem">{newPlanFile.name}</p>{/if}
				</div>
			</div>
			<div class="modal-footer">
				<button class="btn" on:click={() => (showPlanForm = false)}>Annuler</button>
				<button class="btn btn-primary"
					disabled={savingPlan || !newPlanTitre.trim() || !newPlanFile || (newPlanPerimetre === 'bâtiment' && !newPlanBatimentId)}
					on:click={addPlan}>
					{savingPlan ? 'Ajout…' : 'Ajouter'}
				</button>
			</div>
		</div>
	</div>
{/if}

<!-- ── Modal : ajouter un règlement ───────────────────────────────────── -->
{#if showReglementForm}
	<div class="modal-overlay" on:click|self={() => (showReglementForm = false)} role="dialog" aria-modal="true" aria-label="Ajouter un règlement" tabindex="-1">
		<div class="modal" style="width:min(440px,95vw)">
			<div class="modal-header">
				<h3>Ajouter un règlement</h3>
				<button class="modal-close" on:click={() => (showReglementForm = false)}>✕</button>
			</div>
			<div class="modal-body" style="display:flex;flex-direction:column;gap:.75rem">
				<div class="field">
					<label for="regl-titre">Titre *</label>
					<input id="regl-titre" type="text" bind:value={newReglementTitre} placeholder="ex : Règlement de copropriété 2024" />
				</div>
				<div class="field">
					<label for="regl-file">Fichier *</label>
					<input id="regl-file" type="file" accept=".pdf,.jpg,.jpeg,.png,.webp"
						on:change={(e) => { newReglementFile = (e.target as HTMLInputElement).files?.[0] ?? null; }} />
					{#if newReglementFile}<p style="font-size:.8rem;color:var(--color-text-muted);margin-top:.25rem">{newReglementFile.name}</p>{/if}
				</div>
			</div>
			<div class="modal-footer">
				<button class="btn" on:click={() => (showReglementForm = false)}>Annuler</button>
				<button class="btn btn-primary"
					disabled={savingReglement || !newReglementTitre.trim() || !newReglementFile}
					on:click={addReglement}>
					{savingReglement ? 'Ajout…' : 'Ajouter'}
				</button>
			</div>
		</div>
	</div>
{/if}

<!-- ── Modal : ajouter un CR d'AG ─────────────────────────────────────── -->
{#if showCrAgForm}
	<div class="modal-overlay" on:click|self={() => (showCrAgForm = false)} role="dialog" aria-modal="true" aria-label="Ajouter un CR d'AG" tabindex="-1">
		<div class="modal" style="width:min(520px,95vw)">
			<div class="modal-header">
				<h3>Ajouter un CR d'AG</h3>
				<button class="modal-close" on:click={() => (showCrAgForm = false)}>✕</button>
			</div>
			<div class="modal-body" style="display:flex;flex-direction:column;gap:.75rem">
				<div style="display:grid;grid-template-columns:1fr 1fr;gap:.75rem">
					<div class="field">
						<label for="ag-annee">Année *</label>
						<input id="ag-annee" type="number" bind:value={newCrAgAnnee} min="1900" max="2100" placeholder="2025" />
					</div>
					<div class="field">
						<label for="ag-date">Date de l'AG *</label>
						<input id="ag-date" type="date" bind:value={newCrAgDateAg} />
					</div>
				</div>
				<div class="field">
					<label for="ag-titre">Titre *</label>
					<input id="ag-titre" type="text" bind:value={newCrAgTitre} placeholder="ex : PV AG ordinaire 2025" />
				</div>
				<div class="field">
					<label>Périmètre *</label>
					<div class="perimetre-pills" style="margin-top:.25rem">
						<button type="button" class="pill" class:pill-active={newCrAgScope === 'copropriété'}
							on:click={() => { newCrAgScope = 'copropriété'; newCrAgBatimentIds = []; }}>
							Copropriété entière
						</button>
						<button type="button" class="pill" class:pill-active={newCrAgScope === 'bâtiment'}
							on:click={() => (newCrAgScope = 'bâtiment')}>
							Bâtiment(s) spécifique(s)
						</button>
					</div>
				</div>
				{#if newCrAgScope === 'bâtiment'}
					<div class="field">
						<label>Bâtiment(s) *</label>
						<div style="display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.25rem">
							{#each batiments as b}
								<label style="display:flex;align-items:center;gap:.35rem;cursor:pointer;font-size:.875rem">
									<input type="checkbox" bind:group={newCrAgBatimentIds} value={b.id} />
									Bâtiment {b.numero}
								</label>
							{/each}
						</div>
					</div>
				{/if}
				<div class="field">
					<label for="ag-file">Fichier *</label>
					<input id="ag-file" type="file" accept=".pdf,.jpg,.jpeg,.png,.webp"
						on:change={(e) => { newCrAgFile = (e.target as HTMLInputElement).files?.[0] ?? null; }} />
					{#if newCrAgFile}<p style="font-size:.8rem;color:var(--color-text-muted);margin-top:.25rem">{newCrAgFile.name}</p>{/if}
				</div>
			</div>
			<div class="modal-footer">
				<button class="btn" on:click={() => (showCrAgForm = false)}>Annuler</button>
				<button class="btn btn-primary"
					disabled={savingCrAg || !newCrAgAnnee || !newCrAgDateAg || !newCrAgTitre.trim() || !newCrAgFile || (newCrAgScope === 'bâtiment' && newCrAgBatimentIds.length === 0)}
					on:click={addCrAg}>
					{savingCrAg ? 'Ajout…' : 'Ajouter'}
				</button>
			</div>
		</div>
	</div>
{/if}

<!-- ── Modal : modifier un document ────────────────────────────────────────────────── -->
{#if editingDocId !== null}
	<div class="modal-overlay" on:click|self={() => (editingDocId = null)} role="dialog" aria-modal="true" aria-label="Modifier le document" tabindex="-1">
		<div class="modal" style="width:min(440px,95vw)">
			<div class="modal-header">
				<h3>Modifier le document</h3>
				<button class="modal-close" on:click={() => (editingDocId = null)}>✕</button>
			</div>
			<div class="modal-body" style="display:flex;flex-direction:column;gap:.75rem">
				<div class="field">
					<label for="edit-doc-titre">Titre *</label>
					<input id="edit-doc-titre" type="text" bind:value={editingDocTitre} />
				</div>
				{#if editingDocMode === 'ag'}
					<div style="display:grid;grid-template-columns:1fr 1fr;gap:.75rem">
						<div class="field">
							<label for="edit-doc-annee">Année</label>
							<input id="edit-doc-annee" type="number" bind:value={editingDocAnnee} min="1900" max="2100" />
						</div>
						<div class="field">
							<label for="edit-doc-date">Date de l'AG</label>
							<input id="edit-doc-date" type="date" bind:value={editingDocDate} />
						</div>
					</div>
				{/if}
			</div>
			<div class="modal-footer">
				<button class="btn" on:click={() => (editingDocId = null)}>Annuler</button>
				<button class="btn btn-primary"
					disabled={savingDoc || !editingDocTitre.trim()}
					on:click={saveEditDoc}>
					{savingDoc ? 'Enregistrement…' : 'Enregistrer'}
				</button>
			</div>
		</div>
	</div>
{/if}

<!-- ── Modal : ajouter un rapport diagnostique ───────────────────────────────── -->
{#if showDiagForm !== null}
	<div class="modal-overlay" on:click|self={() => (showDiagForm = null)} role="dialog" aria-modal="true" aria-label="Ajouter un rapport" tabindex="-1">
		<div class="modal" style="width:min(460px,95vw)">
			<div class="modal-header">
				<h3>Ajouter un rapport</h3>
				<button class="modal-close" on:click={() => (showDiagForm = null)}>✕</button>
			</div>
			<div class="modal-body" style="display:flex;flex-direction:column;gap:.75rem">
				<div class="field">
					<label for="diag-titre">Titre <span style="color:var(--color-text-muted);font-size:.8rem">(optionnel si multi-fichiers)</span></label>
					<input id="diag-titre" type="text" bind:value={newDiagTitre} placeholder="Rapport DPE 2024… (auto si vide)" />
				</div>
				<div class="field">
					<label for="diag-date">Date du diagnostic</label>
					<input id="diag-date" type="date" bind:value={newDiagDate} />
				</div>
				<div class="field">
					<label for="diag-file">Fichier(s) *</label>
					<input id="diag-file" type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.webp"
						on:change={(e) => { newDiagFiles = (e.target as HTMLInputElement).files; }} />
					{#if newDiagFiles?.length}
						<p style="font-size:.8rem;color:var(--color-text-muted);margin-top:.25rem">
							{#if newDiagFiles.length === 1}{newDiagFiles[0].name}{:else}{newDiagFiles.length} fichiers sélectionnés{/if}
						</p>
					{/if}
				</div>
			</div>
			<div class="modal-footer">
				<button class="btn" on:click={() => (showDiagForm = null)}>Annuler</button>
				<button class="btn btn-primary"
					disabled={savingDiag || !newDiagFiles?.length}
					on:click={addRapport}>
					{savingDiag ? 'Ajout…' : 'Ajouter'}
				</button>
			</div>
		</div>
	</div>
{/if}

<!-- ── Modal : modifier un rapport diagnostique ──────────────────────────────── -->
{#if editingRapportId !== null}
	<div class="modal-overlay" on:click|self={() => (editingRapportId = null)} role="dialog" aria-modal="true" aria-label="Modifier le rapport" tabindex="-1">
		<div class="modal" style="width:min(440px,95vw)">
			<div class="modal-header">
				<h3>Modifier le rapport</h3>
				<button class="modal-close" on:click={() => (editingRapportId = null)}>✕</button>
			</div>
			<div class="modal-body" style="display:flex;flex-direction:column;gap:.75rem">
				<div class="field">
					<label for="edit-r-titre">Titre *</label>
					<input id="edit-r-titre" type="text" bind:value={editingRapportTitre} />
				</div>
				<div class="field">
					<label for="edit-r-date">Date du diagnostic</label>
					<input id="edit-r-date" type="date" bind:value={editingRapportDate} />
				</div>
				<div class="field">
					<label for="edit-r-synthese">Synthèse <span style="color:var(--color-text-muted);font-size:.8rem">(optionnel)</span></label>
					<textarea id="edit-r-synthese" bind:value={editingRapportSynthese}
						placeholder="Conclusions clés, points d'attention, recommandations…"
						rows="4" style="width:100%;resize:vertical"></textarea>
				</div>
			</div>
			<div class="modal-footer">
				<button class="btn" on:click={() => (editingRapportId = null)}>Annuler</button>
				<button class="btn btn-primary"
					disabled={savingRapport || !editingRapportTitre.trim()}
					on:click={saveRapport}>
					{savingRapport ? 'Enregistrement…' : 'Enregistrer'}
				</button>
			</div>
		</div>
	</div>
{/if}

<!-- ── Modal : ajouter / modifier une règle ──────────────────────────────────── -->
{#if showRegleForm}
	<div class="modal-overlay" on:click|self={() => (showRegleForm = false)} role="dialog" aria-modal="true" aria-label="Règle" tabindex="-1">
		<div class="modal" style="width:min(480px,95vw)">
			<div class="modal-header">
				<h3>{editingRegleId ? 'Modifier la règle' : 'Ajouter une règle'}</h3>
				<button class="modal-close" on:click={() => (showRegleForm = false)}>✕</button>
			</div>
			<div class="modal-body" style="display:flex;flex-direction:column;gap:.75rem">
				<div class="field">
					<label for="regle-titre">Titre *</label>
					<input id="regle-titre" type="text" bind:value={regleTitre} placeholder="Ex : RAL menuiseries façade bâtiment A" />
				</div>
				<div class="field">
					<label for="regle-contenu">Détail / valeur</label>
					<textarea id="regle-contenu" bind:value={regleContenu}
						placeholder="Ex : Façade extérieure RAL 6021 vert clair"
						rows="3" style="width:100%;resize:vertical"></textarea>
				</div>
			</div>
			<div class="modal-footer">
				<button class="btn" on:click={() => (showRegleForm = false)}>Annuler</button>
				<button class="btn btn-primary"
					disabled={savingRegle || !regleTitre.trim()}
					on:click={saveRegle}>
					{savingRegle ? 'Enregistrement…' : 'Enregistrer'}
				</button>
			</div>
		</div>
	</div>
{/if}

<style>
	/* ── Photo bannière ─────────────────────────────────────────── */
	.photo-figure {
		margin: 0 auto 2rem;
		max-width: 800px;
		text-align: center;
	}
	.photo-caption {
		font-size: .875rem;
		color: var(--color-text-muted);
		padding: .35rem 0;
		font-style: italic;
	}
	.photo-banner {
		position: relative;
		width: 100%;
		border-radius: var(--radius);
		overflow: hidden;
		background: var(--color-bg);
		border: 1px solid var(--color-border);
	}
	.photo-banner img {
		width: 100%;
		aspect-ratio: 16 / 5;
		object-fit: cover;
		display: block;
	}
	.photo-placeholder {
		width: 100%;
		aspect-ratio: 16 / 5;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: .5rem;
		color: var(--color-text-muted);
		background: var(--color-bg);
		font-size: .9rem;
	}
	.photo-change-btn {
		position: absolute;
		bottom: .75rem;
		right: .75rem;
		background: rgba(0,0,0,.55);
		color: #fff;
		border: none;
		border-radius: var(--radius);
		padding: .35rem .75rem;
		font-size: .8rem;
		cursor: pointer;
		backdrop-filter: blur(4px);
		transition: background .15s;
	}
	.photo-change-btn:hover { background: rgba(0,0,0,.75); }
	.photo-change-btn.uploading { opacity: .6; pointer-events: none; }

	/* ── Sections ───────────────────────────────────────────────── */
	.section-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: .75rem;
	}
	.section-title {
		font-size: .85rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: .05em;
		color: var(--color-text-muted);
		margin: 0;
	}

	/* ── Infos résidence ────────────────────────────────────────── */
	.info-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
		gap: .6rem;
	}
	.info-item { display: flex; flex-direction: column; gap: .1rem; }
	.info-label {
		font-size: .72rem;
		color: var(--color-text-muted);
		text-transform: uppercase;
		letter-spacing: .04em;
		font-weight: 600;
	}
	.info-value { font-size: .9rem; font-weight: 500; }
	.info-highlight { color: var(--color-primary); font-weight: 700; }

	/* ── Bâtiments / lot counts ─────────────────────────────────── */
	.batiment-row {
		display: flex;
		align-items: center;
		gap: 1rem;
		padding: .35rem 0;
		border-bottom: 1px solid var(--color-border);
		font-size: .875rem;
	}
	.batiment-row:last-child { border-bottom: none; }
	.total-row { padding-top: .6rem; }
	.lot-counts { display: flex; gap: .5rem; flex-wrap: wrap; align-items: center; }
	.lot-counts span { color: var(--color-text-muted); font-size: .85rem; }

	/* ── Documents ──────────────────────────────────────────────── */
	.doc-list { display: flex; flex-direction: column; gap: .4rem; }
	.doc-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: .7rem 1rem;
		gap: .75rem;
	}
	.doc-info {
		display: flex;
		align-items: center;
		gap: .5rem;
		flex: 1;
		min-width: 0;
		flex-wrap: wrap;
	}
	.doc-titre {
		font-weight: 500;
		font-size: .9rem;
	}
	.doc-date { font-size: .78rem; color: var(--color-text-muted); margin-left: auto; white-space: nowrap; }
	.doc-actions { display: flex; gap: .35rem; flex-shrink: 0; }
	.empty-msg { font-size: .875rem; color: var(--color-text-muted); padding: .5rem 0; }

	/* ── Tableau bâtiments ────────────────────────────────────────────── */
	.batiment-table { width: 100%; border-collapse: collapse; font-size: .875rem; margin-top: .25rem; }
	.batiment-table th {
		text-align: left;
		padding: .4rem .75rem;
		font-size: .72rem;
		text-transform: uppercase;
		letter-spacing: .04em;
		color: var(--color-text-muted);
		border-bottom: 2px solid var(--color-border);
		font-weight: 600;
	}
	.batiment-table td { padding: .4rem .75rem; border-bottom: 1px solid var(--color-border); }
	.batiment-table tfoot td { font-weight: 700; border-top: 2px solid var(--color-border); border-bottom: none; }

	/* ── Edit form ──────────────────────────────────────────────── */
	.edit-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: .75rem; }
	.field { display: flex; flex-direction: column; gap: .25rem; }
	.field label { font-size: .8rem; font-weight: 500; color: var(--color-text-muted); }
	.field input, .field select { padding: .4rem .6rem; border: 1px solid var(--color-border); border-radius: 6px; font-size: .875rem; background: var(--color-surface); }

	/* ── badge-purple ───────────────────────────────────────────── */
	:global(.badge-purple) { background: #ede9fe; color: #6d28d9; }
	:global(.badge-green) { background: #dcfce7; color: #166534; }
	:global(.badge-blue) { background: #dbeafe; color: #1d4ed8; }

	/* ── Pills périmètre ────────────────────────────────────────── */
	.perimetre-pills { display: flex; flex-wrap: wrap; gap: .4rem; }
	.pill {
		padding: .3rem .85rem;
		border-radius: 999px;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		font-size: .8rem;
		cursor: pointer;
		transition: background .12s, color .12s, border-color .12s;
	}
	.pill:hover { border-color: var(--color-primary); color: var(--color-primary); }
	.pill-active { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }

	/* ── Modals ─────────────────────────────────────────────────── */
	.modal-overlay { position: fixed; top: 0; right: 0; bottom: 0; left: 0; background: rgba(0,0,0,.45); display: flex; align-items: center; justify-content: center; z-index: 200; }
	.modal { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius); padding: 1.5rem; max-height: 90vh; overflow-y: auto; }
	.modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
	.modal-header h3 { font-size: 1.05rem; font-weight: 600; margin: 0; }
	.modal-close { background: none; border: none; font-size: 1.3rem; cursor: pointer; color: var(--color-text-muted); padding: 0; line-height: 1; }
	.modal-close:hover { color: var(--color-text); }
	.modal-body { margin-bottom: 1rem; }
	.modal-footer { display: flex; justify-content: flex-end; gap: .5rem; padding-top: .75rem; border-top: 1px solid var(--color-border); }

	/* ── Diagnostics ─────────────────────────────────────────────── */
	.diag-list { display: flex; flex-direction: column; gap: 1rem; }
	.diag-card { padding: 1rem 1.25rem; }
	.diag-header { margin-bottom: .75rem; }
	.diag-title-row { display: flex; align-items: center; gap: .6rem; flex-wrap: wrap; margin-bottom: .4rem; }
	.diag-nom { font-weight: 600; font-size: .975rem; }
	.diag-texte { font-size: .82rem; color: var(--color-text-muted); line-height: 1.5; margin: 0; }
	.diag-rapports { border-top: 1px solid var(--color-border); padding-top: .6rem; margin-bottom: .6rem; display: flex; flex-direction: column; gap: .35rem; }
	.diag-add { padding-top: .4rem; }
	.diag-card-disabled { opacity: .65; }
	.diag-non-applicable-section {
		margin-top: 1rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: .6rem 1rem;
		background: var(--color-surface);
	}
	.diag-non-applicable-section > summary {
		cursor: pointer;
		font-size: .85rem;
		color: var(--color-text-muted);
		font-weight: 500;
		user-select: none;
	}
	.diag-non-applicable-section > summary:hover { color: var(--color-text); }

	/* ── Synthèse rapport diagnostique ────────────────────── */
	.diag-rapport-block { border-bottom: 1px solid var(--color-border); }
	.diag-rapport-block:last-child { border-bottom: none; }
	.synthese-toggle {
		background: none; border: none; cursor: pointer;
		font-size: .78rem; color: var(--color-primary);
		padding: .1rem .3rem; border-radius: var(--radius);
		white-space: nowrap; flex-shrink: 0;
	}
	.synthese-toggle:hover { background: var(--color-bg); }
	.synthese-body {
		padding: .5rem 1rem .75rem;
		font-size: .875rem;
		background: var(--color-bg);
		border-left: 3px solid var(--color-primary);
		margin: 0 .5rem .35rem;
		border-radius: 0 var(--radius) var(--radius) 0;
	}
</style>
