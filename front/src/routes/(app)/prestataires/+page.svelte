<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import { onMount } from 'svelte';
	import { prestataires as prestApi, documents as docsApi, ApiError } from '$lib/api';
	import { isCS } from '$lib/stores/auth';
	import RichEditor from '$lib/components/RichEditor.svelte';
	import { toast } from '$lib/components/Toast.svelte';
	import { getPageConfig, configStore, siteNomStore } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';

	$: _pc = getPageConfig($configStore, 'prestataires', { titre: 'Prestataires', navLabel: 'Prestataires', icone: 'hard-hat', descriptif: 'Intervenants de la résidence et leurs contrats de maintenance (avec synthèse IA du contrat) et documents contractuels.' });
	$: _siteNom = $siteNomStore;

	let prestataires: any[] = [];
	let contrats: any[] = [];
	let devis: any[] = [];
	let notations: any[] = [];
	let loading = true;

	// ── Notation ──────────────────────────────────────────────────
	let showNotationForm: { prestataireId: number; devisId?: number; contratId?: number } | null = null;
	let notationNote = 0;
	let notationCommentaire = '';
	let notationSaving = false;
	let notationHover = 0;

	function openNotationForm(prestataireId: number, devisId?: number, contratId?: number) {
		showNotationForm = { prestataireId, devisId, contratId };
		notationNote = 0;
		notationCommentaire = '';
	}

	async function saveNotation() {
		if (!showNotationForm || notationNote < 1 || notationNote > 5) { toast('error', 'Sélectionnez une note entre 1 et 5'); return; }
		notationSaving = true;
		try {
			const n = await prestApi.createNotation({
				prestataire_id: showNotationForm.prestataireId,
				note: notationNote,
				commentaire: notationCommentaire.trim() || undefined,
				devis_id: showNotationForm.devisId,
				contrat_id: showNotationForm.contratId,
			});
			notations = [n, ...notations];
			showNotationForm = null;
			toast('success', 'Notation enregistrée');
		} catch (e: any) { toast('error', e instanceof ApiError ? e.message : 'Erreur'); }
		finally { notationSaving = false; }
	}

	function avgNote(prestataireId: number): number | null {
		const pn = notations.filter(n => n.prestataire_id === prestataireId);
		if (pn.length === 0) return null;
		return Math.round(pn.reduce((s: number, n: any) => s + n.note, 0) / pn.length * 10) / 10;
	}

	function starsDisplay(note: number): string {
		return '★'.repeat(Math.round(note)) + '☆'.repeat(5 - Math.round(note));
	}

	// ── Onglets (5) ────────────────────────────────────────────────
	let onglet: 'prestations' | 'visites' | 'contrats_tab' | 'prestataires' | 'consommations' = 'prestations';

	// Expand prestataire cards
	let expandedPrests = new Set<number>();
	// Expand contrat rows inline
	let expandedContrats = new Set<number>();
	// Expand notes dans un contrat
	let expandedNotes = new Set<number>();

	// ── Prestataire form ──────────────────────────────────────────
	let showPrestForm = false;
	let editPrestId: number | null = null;
	let prestForm = { nom: '', specialite: '', type_prestataire: 'ponctuel', email: '' };
	let prestContacts: { telephone: string; prenom: string; nom: string; fonction: string; email: string }[] = [{ telephone: '', prenom: '', nom: '', fonction: '', email: '' }];
	let submitting = false;

	// ── Contrat form ──────────────────────────────────────────────
	let contratFormPrestId: number | null = null;
	let editContratId: number | null = null;

	// ── Devis form ────────────────────────────────────────────────
	let devisFormPrestId: number | null = null;
	let editDevisId: number | null = null;
	let expandedDevis = new Set<number>();
	let devisForm = {
		copropriete_id: 1,
		prestataire_id: '',
		perimetre: 'résidence',
		titre: '',
		date_prestation: '',
		montant_estime: '',
		statut: 'en_attente',
		notes: '',
		frequence_type: '',
		frequence_valeur: '',
		affichable: false,
	};
	let devisFichierFiles: FileList | null = null;
	let devisFichierKey = 0;

	// ── Devis colonnes kanban (reactive) ──────────────────────
	$: devisSyndic = devis.filter((d: any) => d.actif !== false && d.statut === 'en_attente');
	$: devisPrestataire = devis.filter((d: any) => d.actif !== false && d.statut === 'accepte');
	$: devisRealise = devis.filter((d: any) => d.actif !== false && d.statut === 'realise');
	$: devisRefuse = devis.filter((d: any) => d.actif !== false && d.statut === 'refuse');

	// Séparation actifs / réalisés pour la vue liste
	$: devisActifs = devis.filter((d: any) => d.actif !== false && d.statut !== 'realise' && d.statut !== 'refuse');
	$: devisRealises = devis.filter((d: any) => d.actif !== false && d.statut === 'realise');

	// ── Devis OS upload ─────────────────────────────────────────
	let osUploadDevisId: number | null = null;
	let osFile: File | null = null;
	let osUploading = false;
	const devisPerimetreOptions = [
		{ val: 'résidence', label: '🏘️ Copropriété entière' },
		{ val: 'bat:1', label: 'Bât. 1' },
		{ val: 'bat:2', label: 'Bât. 2' },
		{ val: 'bat:3', label: 'Bât. 3' },
		{ val: 'bat:4', label: 'Bât. 4' },
		{ val: 'parking', label: 'Parking' },
		{ val: 'cave', label: 'Cave' },
		{ val: 'aful', label: 'AFUL' },
	];

	function devisBatimentIdFromPerimetre(perimetre: string): number | null {
		if (!perimetre?.startsWith('bat:')) return null;
		const parsed = Number(perimetre.split(':')[1]);
		return Number.isFinite(parsed) ? parsed : null;
	}
	let contratForm = {
		copropriete_id: 1, batiment_id: '', prestataire_id: '',
		type_equipement: 'autre', libelle: '', numero_contrat: '',
		date_debut: new Date().toISOString().slice(0, 10),
		duree_initiale_valeur: '', duree_initiale_unite: 'mois',
		frequence_type: '', frequence_valeur: '',
		prochaine_visite: '', notes: '',
	};

	// ── Documents ─────────────────────────────────────────────────
	let contratDocsMap: Record<number, any[]> = {};
	let contratUploadFile: File | null = null;
	let contratUploadTitre = '';
	let uploadingDoc = false;
	let uploadInputKey = 0;

	let filtreEquipement = '';
	let filtreType = '';

	// ── Sous-vue dans onglet Prestations ──────────────────────────
	let prestationsVue: 'kanban' | 'liste' = 'liste';
	let showRealisees = false;

	$: filteredPrests = prestataires.filter(p =>
		(!filtreEquipement || p.specialite === filtreEquipement) &&
		(!filtreType || p.type_prestataire === filtreType)
	);
	$: compactPrests = filteredPrests.length > 7;

	// ── Visites : contrats avec fréquence ─────────────────────────
	$: visites = contrats.filter(c => c.frequence_type || c.prochaine_visite);
	$: visitesEnRetard = visites.filter(c => c.prochaine_visite && new Date(c.prochaine_visite) < new Date());
	$: visitesAJour = visites.filter(c => !c.prochaine_visite || new Date(c.prochaine_visite) >= new Date());

	// ── Consommations ─────────────────────────────────────────────
	let compteurConfigs: any[] = [];
	let typeCompteur = '';
	let releves: any[] = [];
	let releveLoading = false;
	let showReleveForm = false;
	let editReleveId: number | null = null;
	let releveForm = { date_releve: new Date().toISOString().slice(0, 10), index: '', note: '' };
	let relevePhotoFile: File | null = null;
	let relevePhotoKey = 0;
	let releveSaving = false;

	let editCompteurId: number | null = null;
	let editCompteurPrestId = '';
	let showAddCompteur = false;
	let newCompteurLabel = '';
	let addCompteurSaving = false;

	$: currentCompteur = compteurConfigs.find(c => c.type_compteur === typeCompteur) ?? null;

	$: relevesByYear = (() => {
		const map = new Map<number, any[]>();
		for (const r of releves) {
			const yr = new Date(r.date_releve).getFullYear();
			if (!map.has(yr)) map.set(yr, []);
			map.get(yr)!.push(r);
		}
		return [...map.entries()].sort((a, b) => b[0] - a[0]);
	})();

	async function loadCompteurConfigs() {
		try {
			compteurConfigs = await prestApi.compteurConfigs();
			if (compteurConfigs.length > 0 && !typeCompteur) typeCompteur = compteurConfigs[0].type_compteur;
		} catch { toast('error', 'Erreur chargement compteurs'); }
	}

	async function loadReleves() {
		if (!typeCompteur) return;
		releveLoading = true;
		try { releves = await prestApi.releves(typeCompteur); }
		catch { toast('error', 'Erreur chargement relevés'); }
		finally { releveLoading = false; }
	}

	$: if (onglet === 'consommations' && compteurConfigs.length === 0) loadCompteurConfigs();
	$: if (typeCompteur) loadReleves();

	function resetReleveForm() {
		releveForm = { date_releve: new Date().toISOString().slice(0, 10), index: '', note: '' };
		relevePhotoFile = null;
		relevePhotoKey++;
		editReleveId = null;
		showReleveForm = false;
	}

	function startEditReleve(r: any) {
		releveForm = {
			date_releve: r.date_releve,
			index: r.index != null ? String(r.index) : '',
			note: r.note ?? '',
		};
		relevePhotoFile = null;
		relevePhotoKey++;
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
				releves = releves.map(r => r.id === editReleveId ? saved : r);
			} else {
				saved = await prestApi.createReleve(payload);
				releves = [saved, ...releves];
			}
			if (relevePhotoFile) {
				try {
					const updated = await prestApi.uploadRelevePhoto(saved.id, relevePhotoFile);
					releves = releves.map(r => r.id === saved.id ? updated : r);
				} catch { toast('error', 'Photo non enregistrée'); }
			}
			toast('success', editReleveId ? 'Relevé modifié' : 'Relevé ajouté');
			resetReleveForm();
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally { releveSaving = false; }
	}

	async function deleteReleve(id: number) {
		if (!confirm('Supprimer ce relevé ?')) return;
		try {
			await prestApi.deleteReleve(id);
			releves = releves.filter(r => r.id !== id);
			toast('success', 'Relevé supprimé');
		} catch { toast('error', 'Erreur'); }
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
			compteurConfigs = compteurConfigs.map(c => c.id === cfg.id ? updated : c);
			editCompteurId = null;
			toast('success', 'Fournisseur mis à jour');
		} catch (e: any) { toast('error', e instanceof ApiError ? e.message : 'Erreur'); }
	}

	async function addCompteurConfig() {
		if (!newCompteurLabel.trim()) return;
		addCompteurSaving = true;
		const slug = newCompteurLabel.trim().toLowerCase()
			.normalize('NFD').replace(/[\u0300-\u036f]/g, '')
			.replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
		try {
			const created = await prestApi.createCompteurConfig({ type_compteur: slug, label: newCompteurLabel.trim(), ordre: compteurConfigs.length });
			compteurConfigs = [...compteurConfigs, created];
			newCompteurLabel = '';
			showAddCompteur = false;
			typeCompteur = created.type_compteur;
			toast('success', 'Catégorie ajoutée');
		} catch (e: any) { toast('error', e instanceof ApiError ? e.message : 'Erreur'); }
		finally { addCompteurSaving = false; }
	}

	async function deleteCompteurConfig(cfg: any) {
		if (!confirm(`Supprimer la catégorie « ${cfg.label} » ?`)) return;
		try {
			await prestApi.deleteCompteurConfig(cfg.id);
			compteurConfigs = compteurConfigs.filter(c => c.id !== cfg.id);
			if (typeCompteur === cfg.type_compteur) typeCompteur = compteurConfigs[0]?.type_compteur ?? '';
			toast('success', 'Catégorie supprimée');
		} catch (e: any) { toast('error', e instanceof ApiError ? e.message : 'Erreur'); }
	}

	function fmtReleve(r: any) {
		const d = new Date(r.date_releve);
		return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' });
	}

	function splitTels(tel: string): string[] {
		return tel.split(',').filter(t => t.trim());
	}

	function contratsForPrest(prestId: number): any[] {
		return contrats.filter(c => c.prestataire_id === prestId);
	}

	function devisForPrest(prestId: number): any[] {
		return devis.filter(d => d.prestataire_id === prestId);
	}

	function toggleDevis(id: number) {
		if (expandedDevis.has(id)) expandedDevis.delete(id);
		else { expandedDevis.clear(); expandedDevis.add(id); }
		expandedDevis = expandedDevis;
	}

	function resetDevisForm() {
		devisForm = {
			copropriete_id: 1,
			prestataire_id: '',
			perimetre: 'résidence',
			titre: '',
			date_prestation: '',
			montant_estime: '',
			statut: 'en_attente',
			notes: '',
			frequence_type: '',
			frequence_valeur: '',
			affichable: false,
		};
		devisFichierFiles = null;
		devisFichierKey++;
		editDevisId = null;
	}

	function openAddDevis(prestId: number) {
		resetDevisForm();
		devisForm.prestataire_id = String(prestId);
		devisFormPrestId = prestId;
		editDevisId = null;
	}

	function closeDevisForm() {
		devisFormPrestId = null;
		editDevisId = null;
		resetDevisForm();
	}

	function onDevisFilesChange(event: Event) {
		const input = event.currentTarget as HTMLInputElement | null;
		devisFichierFiles = input?.files ?? null;
	}

	function onOsFileChange(event: Event) {
		const input = event.currentTarget as HTMLInputElement | null;
		osFile = input?.files?.[0] ?? null;
	}

	function startEditDevis(d: any, openInModal = false) {
		devisForm = {
			copropriete_id: d.copropriete_id,
			prestataire_id: String(d.prestataire_id),
			perimetre: d.perimetre ?? (d.batiment_id ? `bat:${d.batiment_id}` : 'résidence'),
			titre: d.titre,
			date_prestation: d.date_prestation ?? '',
			montant_estime: d.montant_estime != null ? String(d.montant_estime) : '',
			statut: d.statut,
			notes: d.notes ?? '',
			frequence_type: d.frequence_type ?? '',
			frequence_valeur: d.frequence_valeur ? String(d.frequence_valeur) : '',
			affichable: d.affichable ?? false,
		};
		editDevisId = d.id;
		devisFormPrestId = openInModal ? -1 : d.prestataire_id;
		if (!expandedDevis.has(d.id)) { expandedDevis.clear(); expandedDevis.add(d.id); expandedDevis = expandedDevis; }
	}

	async function saveDevis() {
		if (!devisForm.titre.trim()) { toast('error', 'Titre obligatoire'); return; }
		if (!devisForm.prestataire_id) { toast('error', 'Prestataire obligatoire'); return; }
		submitting = true;
		try {
			const perimetre = devisForm.perimetre || 'résidence';
			const payload = {
				copropriete_id: devisForm.copropriete_id,
				prestataire_id: Number(devisForm.prestataire_id),
				perimetre,
				batiment_id: devisBatimentIdFromPerimetre(perimetre),
				titre: devisForm.titre.trim(),
				date_prestation: devisForm.date_prestation || null,
				montant_estime: devisForm.montant_estime !== '' ? Number(devisForm.montant_estime) : null,
				statut: devisForm.statut,
				notes: devisForm.notes.trim() || null,
				frequence_type: devisForm.frequence_type || null,
				frequence_valeur: devisForm.frequence_valeur ? Number(devisForm.frequence_valeur) : null,
				affichable: devisForm.affichable,
			};
			let saved: any;
			if (editDevisId) {
				saved = await prestApi.updateDevis(editDevisId, payload);
				devis = devis.map(d => d.id === editDevisId ? saved : d);
			} else {
				saved = await prestApi.createDevis(payload);
				devis = [...devis, saved];
			}
			if (devisFichierFiles && devisFichierFiles.length > 0) {
				let lastUpdated: any = saved;
				for (const file of Array.from(devisFichierFiles)) {
					try {
						lastUpdated = await prestApi.uploadDevisFichier(saved.id, file);
					} catch { toast('error', `Fichier « ${file.name} » non joint`); }
				}
				devis = devis.map(d => d.id === saved.id ? lastUpdated : d);
			}
			closeDevisForm();
			toast('success', editDevisId ? 'Prestation modifiée' : 'Prestation ajoutée');
		} catch (e: any) { toast('error', e instanceof ApiError ? e.message : 'Erreur'); } finally { submitting = false; }
	}

	async function deleteDevis(id: number) {
		if (!confirm('Supprimer cette prestation ?')) return;
		try { await prestApi.deleteDevis(id); devis = devis.filter(d => d.id !== id); toast('success', 'Prestation supprimée'); }
		catch { toast('error', 'Erreur'); }
	}

	async function deleteDevisFichier(devisId: number, url: string) {
		if (!confirm('Supprimer ce fichier ?')) return;
		try {
			const updated = await prestApi.deleteDevisFichier(devisId, url);
			devis = devis.map(d => d.id === devisId ? updated : d);
			toast('success', 'Fichier supprimé');
		} catch { toast('error', 'Erreur suppression fichier'); }
	}

	async function moveDevisStatut(id: number, newStatut: string) {
		try {
			const updated = await prestApi.updateDevis(id, { statut: newStatut });
			devis = devis.map(d => d.id === id ? updated : d);
			toast('success', 'Statut mis à jour');
		} catch { toast('error', 'Erreur mise à jour statut'); }
	}

	async function acceptDevisWithOs() {
		if (!osUploadDevisId) return;
		osUploading = true;
		try {
			let updated: any;
			if (osFile) {
				updated = await prestApi.uploadDevisOs(osUploadDevisId, osFile);
			} else {
				updated = await prestApi.updateDevis(osUploadDevisId, { statut: 'accepte' });
			}
			devis = devis.map(d => d.id === osUploadDevisId ? updated : d);
			toast('success', 'Devis accepté — passé chez le prestataire');
		} catch { toast('error', 'Erreur'); } finally {
			osUploadDevisId = null; osFile = null; osUploading = false;
		}
	}

	$: orphanContrats = contrats.filter(c => !c.prestataire_id);

	const equipements = [
		{ val: 'ascenseur', label: '\u{1F6D7} Ascenseur' },
		{ val: 'chauffage_collectif', label: '\u{1F525} Chauffage collectif' },
		{ val: 'eau', label: '\u{1F4A7} Eau' },
		{ val: 'electricite', label: '⚡ Électricité' },
		{ val: 'espaces_verts', label: '\u{1F33F} Espaces verts' },
		{ val: 'extincteurs', label: '\u{1F9EF} Extincteurs' },
		{ val: 'interphone_digicode', label: '\u{1F4DE} Interphone/Digicode' },
		{ val: 'nettoyage', label: '\u{1F9F9} Nettoyage' },
		{ val: 'plomberie', label: '\u{1F6BF} Plomberie' },
		{ val: 'pompe', label: '⚙️ Pompe' },
		{ val: 'porte_parking', label: '\u{1F697} Porte parking' },
		{ val: 'serrurerie', label: '\u{1F511} Serrurerie' },
		{ val: 'toiture', label: '\u{1F3E0} Toiture' },
		{ val: 'vmc', label: '\u{1F4A8} VMC' },
		{ val: 'autre', label: '\u{1F527} Autre' },
	];

	function equipLabel(v: string) {
		return equipements.find(e => e.val === v)?.label ?? v;
	}

	const typesPrestataire = [
		{ val: 'contrat_recurrent', label: '\u{1F504} Contrat récurrent', desc: 'Entretien, maintenance' },
		{ val: 'ponctuel', label: '\u{1F4CD} Dépannage', desc: 'Interventions ponctuelles' },
		{ val: 'travaux', label: '\u{1F3D7}️ Travaux', desc: 'Interventions importantes' },
		{ val: 'reglementaire', label: '\u{1F4CB} Réglementaire', desc: 'Contrôles obligatoires' },
		{ val: 'etudes_expertise', label: '\u{1F52C} Études / Expertise', desc: 'Analyses techniques' },
		{ val: 'gestion', label: '\u{1F5C2}️ Gestion', desc: 'Services administratifs (dont assurance)' },
	];

	function typeLabel(v: string) {
		return typesPrestataire.find(t => t.val === v)?.label ?? v;
	}

	const statutsDevis = [
		{ val: 'en_attente', label: '⏳ En attente', color: 'var(--color-text-muted)' },
		{ val: 'accepte', label: '✅ Accepté', color: '#16a34a' },
		{ val: 'refuse', label: '❌ Refusé', color: '#dc2626' },
		{ val: 'realise', label: '\u{1F3C1} Réalisé', color: '#7c3aed' },
	];
	function statutDevisLabel(v: string) { return statutsDevis.find(s => s.val === v)?.label ?? v; }
	function statutDevisColor(v: string) { return statutsDevis.find(s => s.val === v)?.color ?? 'var(--color-text-muted)'; }

	// ── Toggle expand ──────────────────────────────────────────────
	function togglePrest(id: number) {
		if (expandedPrests.has(id)) expandedPrests.delete(id);
		else { expandedPrests.clear(); expandedPrests.add(id); expandedContrats.clear(); expandedNotes.clear(); expandedContrats = expandedContrats; expandedNotes = expandedNotes; }
		expandedPrests = expandedPrests;
	}

	function toggleContrat(id: number) {
		if (expandedContrats.has(id)) expandedContrats.delete(id);
		else { expandedContrats.clear(); expandedContrats.add(id); expandedNotes.clear(); expandedNotes = expandedNotes; }
		expandedContrats = expandedContrats;
	}

	function nextVisitForPrest(prestId: number): string | null {
		const dates = contrats
			.filter(c => c.prestataire_id === prestId && c.prochaine_visite)
			.map(c => c.prochaine_visite as string)
			.sort();
		return dates[0] ?? null;
	}

	function frequenceLabel(c: any): string {
		if (c.frequence_type === 'semaines') return `↺ ${c.frequence_valeur} sem.`;
		if (c.frequence_type === 'mois') return '↺ Mensuel';
		if (c.frequence_type === 'fois_par_an') return `↺ ${c.frequence_valeur}×/an`;
		return '';
	}

	onMount(async () => {
		try {
			[prestataires, contrats, devis, notations] = await Promise.all([prestApi.list(), prestApi.contrats(), prestApi.devis(), prestApi.notations()]);
		} catch { toast('error', 'Erreur de chargement'); } finally { loading = false; }

		if (contrats.length > 0) {
			const results = await Promise.allSettled(
				contrats.map(c => docsApi.list(undefined, c.id).then((docs: any[]) => ({ id: c.id, docs })))
			);
			const map: Record<number, any[]> = {};
			for (const r of results) {
				if (r.status === 'fulfilled') map[r.value.id] = r.value.docs;
			}
			contratDocsMap = map;
		}
	});

	function resetPrestForm() { prestForm = { nom: '', specialite: '', type_prestataire: 'ponctuel', email: '' }; prestContacts = [{ telephone: '', prenom: '', nom: '', fonction: '', email: '' }]; editPrestId = null; }
	function startEditPrest(p: any) {
		prestForm = { nom: p.nom, specialite: p.specialite ?? '', type_prestataire: p.type_prestataire ?? 'ponctuel', email: p.email ?? '' };
		if (p.contacts && p.contacts.length > 0) {
			prestContacts = p.contacts.map((c: any) => ({
				telephone: c.telephone ?? '', prenom: c.prenom ?? '', nom: c.nom ?? '', fonction: c.fonction ?? '', email: c.email ?? '',
			}));
		} else {
			prestContacts = p.telephone ? p.telephone.split(',').filter((t: string) => t.trim()).map((t: string) => ({ telephone: t.trim(), prenom: '', nom: '', fonction: '', email: '' })) : [{ telephone: '', prenom: '', nom: '', fonction: '', email: '' }];
		}
		if (prestContacts.length === 0) prestContacts = [{ telephone: '', prenom: '', nom: '', fonction: '', email: '' }];
		editPrestId = p.id;
		showPrestForm = true;
		window.scrollTo({ top: 0, behavior: 'smooth' });
	}

	async function savePrest() {
		if (!prestForm.nom || !prestForm.specialite) { toast('error', 'Nom et spécialité obligatoires'); return; }
		const contacts = prestContacts.filter(c => c.telephone.trim());
		const telephone = contacts.map(c => c.telephone.trim()).join(',') || null;
		submitting = true;
		try {
			if (editPrestId) { await prestApi.update(editPrestId, { ...prestForm, telephone, contacts }); }
			else { await prestApi.create({ ...prestForm, telephone, contacts }); }
			prestataires = await prestApi.list();
			showPrestForm = false; resetPrestForm();
			toast('success', editPrestId ? 'Prestataire modifié' : 'Prestataire ajouté');
		} catch (e: any) { toast('error', e instanceof ApiError ? e.message : 'Erreur'); } finally { submitting = false; }
	}

	async function deletePrest(id: number) {
		if (!confirm('Archiver ce prestataire ?')) return;
		try { await prestApi.delete(id); prestataires = prestataires.filter(p => p.id !== id); toast('success', 'Archivé'); }
		catch { toast('error', 'Erreur'); }
	}

	function resetContratForm() {
		contratForm = { copropriete_id: 1, batiment_id: '', prestataire_id: '', type_equipement: 'autre', libelle: '', numero_contrat: '', date_debut: new Date().toISOString().slice(0, 10), duree_initiale_valeur: '', duree_initiale_unite: 'mois', frequence_type: '', frequence_valeur: '', prochaine_visite: '', notes: '' };
		editContratId = null;
	}

	function openAddContrat(prestId?: number) {
		resetContratForm();
		if (prestId) contratForm.prestataire_id = String(prestId);
		contratFormPrestId = prestId ?? -1;
		editContratId = null;
	}

	function closeContratForm() { contratFormPrestId = null; resetContratForm(); }

	function startEditContrat(c: any) {
		contratForm = {
			copropriete_id: c.copropriete_id, batiment_id: c.batiment_id ?? '', prestataire_id: String(c.prestataire_id ?? ''),
			type_equipement: c.type_equipement, libelle: c.libelle, numero_contrat: c.numero_contrat ?? '',
			date_debut: c.date_debut,
			duree_initiale_valeur: c.duree_initiale_valeur ?? '',
			duree_initiale_unite: c.duree_initiale_unite ?? 'mois',
			frequence_type: c.frequence_type ?? '',
			frequence_valeur: c.frequence_valeur ?? '',
			prochaine_visite: c.prochaine_visite ?? '', notes: c.notes ?? '',
		};
		editContratId = c.id;
		contratFormPrestId = null;
		expandedContrats.add(c.id);
		expandedContrats = expandedContrats;
	}

	async function saveContrat() {
		if (!contratForm.libelle || !contratForm.prestataire_id) { toast('error', 'Libellé et prestataire obligatoires'); return; }
		submitting = true;
		const payload = {
			...contratForm,
			batiment_id: contratForm.batiment_id ? Number(contratForm.batiment_id) : null,
			prestataire_id: Number(contratForm.prestataire_id),
			duree_initiale_valeur: contratForm.duree_initiale_valeur ? Number(contratForm.duree_initiale_valeur) : null,
			duree_initiale_unite: contratForm.duree_initiale_valeur ? contratForm.duree_initiale_unite : null,
			frequence_type: contratForm.frequence_type || null,
			frequence_valeur: contratForm.frequence_valeur ? Number(contratForm.frequence_valeur) : null,
			prochaine_visite: contratForm.prochaine_visite || null,
		};
		try {
			if (editContratId) {
				await prestApi.updateContrat(editContratId, payload);
			} else {
				await prestApi.createContrat(payload);
			}
			contrats = await prestApi.contrats();
			contratFormPrestId = null;
			resetContratForm();
			toast('success', editContratId ? 'Contrat modifié' : 'Contrat créé');
		} catch (e: any) { toast('error', e instanceof ApiError ? e.message : 'Erreur'); } finally { submitting = false; }
	}

	async function uploadDoc(contratId: number) {
		if (!contratUploadFile) return;
		const titre = contratUploadTitre.trim() || contratUploadFile.name;
		uploadingDoc = true;
		try {
			await docsApi.uploadForContrat(titre, contratId, contratUploadFile);
			contratDocsMap = { ...contratDocsMap, [contratId]: await docsApi.list(undefined, contratId) };
			contratUploadFile = null;
			contratUploadTitre = '';
			uploadInputKey++;
			toast('success', 'Document ajouté');
		} catch (e: any) { toast('error', e instanceof ApiError ? e.message : 'Erreur'); } finally { uploadingDoc = false; }
	}

	async function deleteDoc(contratId: number, docId: number) {
		if (!confirm('Supprimer ce document ?')) return;
		try {
			await docsApi.delete(docId);
			contratDocsMap = { ...contratDocsMap, [contratId]: await docsApi.list(undefined, contratId) };
			toast('success', 'Document supprimé');
		} catch { toast('error', 'Erreur'); }
	}

	async function deleteContrat(id: number) {
		if (!confirm('Archiver ce contrat ?')) return;
		try { await prestApi.deleteContrat(id); contrats = contrats.filter(c => c.id !== id); toast('success', 'Archivé'); }
		catch { toast('error', 'Erreur'); }
	}
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<div class="page-header" style="justify-content: space-between">
	<h1 style="display:flex;align-items:center;gap:.4rem;font-size:1.4rem;font-weight:700"><Icon name={_pc.icone || 'hard-hat'} size={20} />{_pc.titre}</h1>
	{#if $isCS}
		{#if onglet === 'prestataires'}
			<button class="btn btn-primary page-header-btn" on:click={() => { showPrestForm = !showPrestForm; if (!showPrestForm) resetPrestForm(); }}>
				{showPrestForm ? '✕ Annuler' : '+ Nouveau prestataire'}
			</button>
		{:else if onglet === 'prestations'}
			<button class="btn btn-primary page-header-btn" on:click={() => { resetDevisForm(); devisFormPrestId = -1; }}>+ Nouvelle prestation</button>
		{:else if onglet === 'contrats_tab'}
			<button class="btn btn-primary page-header-btn" on:click={() => openAddContrat()}>+ Nouveau contrat</button>
		{:else if onglet === 'consommations'}
			<button class="btn btn-primary page-header-btn" on:click={() => { showReleveForm = !showReleveForm; if (!showReleveForm) resetReleveForm(); }}>
				{showReleveForm ? '✕ Annuler' : currentCompteur ? `+ Nouveau relevé — ${currentCompteur.label}` : '+ Nouveau relevé'}
			</button>
		{/if}
	{/if}
</div>
<div class="page-subtitle">{@html safeHtml(_pc.descriptif)}</div>

<!-- ── Onglets ─────────────────────────────────────────────────── -->
<div class="tabs" role="tablist">
	<button role="tab" class:active={onglet === 'prestations'} on:click={() => onglet = 'prestations'}>
		<Icon name="clipboard-list" size={15} /> Prestations ponctuelles
	</button>
	<button role="tab" class:active={onglet === 'visites'} on:click={() => onglet = 'visites'}>
		<Icon name="calendar-days" size={15} /> Visites
	</button>
	<button role="tab" class:active={onglet === 'contrats_tab'} on:click={() => onglet = 'contrats_tab'}>
		<Icon name="file-text" size={15} /> Contrats
	</button>
	<button role="tab" class:active={onglet === 'prestataires'} on:click={() => onglet = 'prestataires'}>
		<Icon name="hard-hat" size={15} /> Prestataires
	</button>
	<button role="tab" class:active={onglet === 'consommations'} on:click={() => onglet = 'consommations'}>
		💧 Consommations
	</button>
</div>

{#if loading}
	<p style="color:var(--color-text-muted)">Chargement…</p>

<!-- ══════════════════════════════════════════════════════════════ -->
<!-- ONGLET 1 : PRESTATIONS (kanban + liste)                      -->
<!-- ══════════════════════════════════════════════════════════════ -->
{:else if onglet === 'prestations'}

	<!-- Toggle liste / kanban -->
	<div class="sous-vue-toggle">
		<button class="btn btn-sm" class:btn-primary={prestationsVue === 'liste'} on:click={() => prestationsVue = 'liste'}>Liste</button>
		{#if $isCS}<button class="btn btn-sm" class:btn-primary={prestationsVue === 'kanban'} on:click={() => prestationsVue = 'kanban'}>Kanban</button>{/if}
		<span class="kanban-count-total">{devis.filter(d => d.actif !== false).length} prestation{devis.filter(d => d.actif !== false).length > 1 ? 's' : ''}</span>
	</div>

	{#if prestationsVue === 'kanban'}
		<!-- ── Kanban ─────────────────────────────────── -->
		<div class="kanban devis-kanban">
			<!-- Colonne : Syndic -->
			<div class="kanban-col">
				<div class="kanban-col-header" style="border-top-color:#f59e0b">
					<span>⏳ Syndic</span>
					<span class="kanban-count">{devisSyndic.length}</span>
				</div>
				{#if devisSyndic.length === 0}
					<p class="kanban-empty">Aucune prestation</p>
				{:else}
					{#each devisSyndic as d (d.id)}
						{@const prestNom = prestataires.find(p => p.id === d.prestataire_id)?.nom ?? '—'}
						<div class="kanban-card card">
							<div class="kanban-card-tags">
								{#if d.frequence_type}<span class="kb-tag" style="background:#6366f1">↺ récurrent</span>{/if}
							</div>
							<span class="devis-card-prest">{prestNom}</span>
							<strong class="kanban-card-titre">{d.titre}</strong>
							<div class="kanban-card-footer">
								<div class="devis-card-meta">
									{#if d.date_prestation}<span class="devis-date">📅 {new Date(d.date_prestation).toLocaleDateString('fr-FR')}</span>{/if}
									{#if d.montant_estime != null}<span class="devis-montant">💶 {d.montant_estime.toLocaleString('fr-FR', {style:'currency',currency:'EUR'})}</span>{/if}
									{#if d.os_fichier_url}<a href={d.os_fichier_url} target="_blank" class="devis-os-link">📎 OS</a>{/if}
								</div>
								{#if $isCS}
									<div class="kanban-card-actions">
										<button class="devis-step-btn devis-step-btn--primary" title="Passer l'OS et transmettre au prestataire"
											on:click={() => { osUploadDevisId = d.id; osFile = null; }}>→ OS</button>
										<button class="btn-icon-edit" title="Modifier" on:click={() => startEditDevis(d, true)}>✏️</button>
										<button class="btn-icon-danger" title="Refuser" on:click={() => moveDevisStatut(d.id, 'refuse')}>❌</button>
									</div>
								{/if}
							</div>
						</div>
					{/each}
				{/if}
			</div>
			<!-- Colonne : Prestataire -->
			<div class="kanban-col">
				<div class="kanban-col-header" style="border-top-color:#f97316">
					<span>🔧 Prestataire</span>
					<span class="kanban-count">{devisPrestataire.length}</span>
				</div>
				{#if devisPrestataire.length === 0}
					<p class="kanban-empty">Aucune prestation</p>
				{:else}
					{#each devisPrestataire as d (d.id)}
						{@const prestNom = prestataires.find(p => p.id === d.prestataire_id)?.nom ?? '—'}
						<div class="kanban-card card">
							<div class="kanban-card-tags">
								{#if d.frequence_type}<span class="kb-tag" style="background:#6366f1">↺ récurrent</span>{/if}
								{#if d.os_fichier_url}<span class="kb-tag" style="background:#0ea5e9">📎 OS joint</span>{/if}
							</div>
							<span class="devis-card-prest">{prestNom}</span>
							<strong class="kanban-card-titre">{d.titre}</strong>
							<div class="kanban-card-footer">
								<div class="devis-card-meta">
									{#if d.date_prestation}<span class="devis-date">📅 {new Date(d.date_prestation).toLocaleDateString('fr-FR')}</span>{/if}
									{#if d.montant_estime != null}<span class="devis-montant">💶 {d.montant_estime.toLocaleString('fr-FR', {style:'currency',currency:'EUR'})}</span>{/if}
								</div>
								{#if $isCS}
									<div class="kanban-card-actions">
										<button class="devis-step-btn devis-step-btn--success" title="Marquer comme réalisé"
											on:click={() => moveDevisStatut(d.id, 'realise')}>✅</button>
										<button class="devis-step-btn" title="Retour Syndic"
											on:click={() => moveDevisStatut(d.id, 'en_attente')}>←</button>
										<button class="btn-icon-edit" title="Modifier" on:click={() => startEditDevis(d, true)}>✏️</button>
										<button class="btn-icon-danger" title="Refuser" on:click={() => moveDevisStatut(d.id, 'refuse')}>❌</button>
									</div>
								{/if}
							</div>
						</div>
					{/each}
				{/if}
			</div>
			<!-- Colonne : Réalisé -->
			<div class="kanban-col">
				<div class="kanban-col-header" style="border-top-color:#22c55e">
					<span>🏁 Réalisé</span>
					<span class="kanban-count">{devisRealise.length}</span>
				</div>
				{#if devisRealise.length === 0}
					<p class="kanban-empty">Aucune prestation</p>
				{:else}
					{#each devisRealise as d (d.id)}
						{@const prestNom = prestataires.find(p => p.id === d.prestataire_id)?.nom ?? '—'}
						<div class="kanban-card card">
							<div class="kanban-card-tags">
								{#if d.frequence_type}<span class="kb-tag" style="background:#6366f1">↺ récurrent</span>{/if}
							</div>
							<span class="devis-card-prest">{prestNom}</span>
							<strong class="kanban-card-titre">{d.titre}</strong>
							<div class="kanban-card-footer">
								<div class="devis-card-meta">
									{#if d.date_prestation}<span class="devis-date">📅 {new Date(d.date_prestation).toLocaleDateString('fr-FR')}</span>{/if}
									{#if d.montant_estime != null}<span class="devis-montant">💶 {d.montant_estime.toLocaleString('fr-FR', {style:'currency',currency:'EUR'})}</span>{/if}
									{#if d.os_fichier_url}<a href={d.os_fichier_url} target="_blank" class="devis-os-link">📎 OS</a>{/if}
								</div>
								{#if $isCS}
									<div class="kanban-card-actions">
										<button class="devis-step-btn" title="Retour chez le prestataire"
											on:click={() => moveDevisStatut(d.id, 'accepte')}>←</button>
										<button class="devis-step-btn" title="Noter" style="color:#f59e0b"
											on:click={() => openNotationForm(d.prestataire_id, d.id)}>⭐</button>
										<button class="btn-icon-edit" title="Modifier" on:click={() => startEditDevis(d, true)}>✏️</button>
									</div>
								{/if}
							</div>
						</div>
					{/each}
				{/if}
			</div>
			<!-- Colonne : Refusé -->
			<div class="kanban-col">
				<div class="kanban-col-header" style="border-top-color:#9ca3af">
					<span>🚫 Refusé</span>
					<span class="kanban-count">{devisRefuse.length}</span>
				</div>
				{#if devisRefuse.length === 0}
					<p class="kanban-empty">Aucune prestation</p>
				{:else}
					{#each devisRefuse as d (d.id)}
						{@const prestNom = prestataires.find(p => p.id === d.prestataire_id)?.nom ?? '—'}
						<div class="kanban-card card">
							<div class="kanban-card-tags">
								{#if d.frequence_type}<span class="kb-tag" style="background:#6366f1">↺ récurrent</span>{/if}
							</div>
							<span class="devis-card-prest">{prestNom}</span>
							<strong class="kanban-card-titre">{d.titre}</strong>
							<div class="kanban-card-footer">
								<div class="devis-card-meta">
									{#if d.date_prestation}<span class="devis-date">📅 {new Date(d.date_prestation).toLocaleDateString('fr-FR')}</span>{/if}
									{#if d.montant_estime != null}<span class="devis-montant">💶 {d.montant_estime.toLocaleString('fr-FR', {style:'currency',currency:'EUR'})}</span>{/if}
								</div>
								{#if $isCS}
									<div class="kanban-card-actions">
										<button class="devis-step-btn" title="Remettre en attente syndic"
											on:click={() => moveDevisStatut(d.id, 'en_attente')}>↩</button>
										<button class="btn-icon-edit" title="Modifier" on:click={() => startEditDevis(d, true)}>✏️</button>
									</div>
								{/if}
							</div>
						</div>
					{/each}
				{/if}
			</div>
		</div>
	{:else}
		<!-- ── Vue liste ─────────────────────────────── -->
		{#if devisActifs.length === 0 && devisRealises.length === 0}
			<div class="empty-state card"><h3>Aucune prestation</h3><p>Ajoutez la première via le bouton ci-dessus.</p></div>
		{:else}
			{#each devisActifs as d (d.id)}
				{@const prestNom = prestataires.find(p => p.id === d.prestataire_id)?.nom ?? '—'}
				{@const devisExpanded = expandedDevis.has(d.id)}
				<div class="devis-expand" class:expanded={devisExpanded}>
					<div class="devis-row"
						role="button" tabindex="0"
						on:click|stopPropagation={() => toggleDevis(d.id)}
						on:keydown|stopPropagation={e => (e.key === 'Enter' || e.key === ' ') && toggleDevis(d.id)}>
						<div class="devis-body-inner">
							<span class="devis-card-prest">{prestNom}</span>
							<strong class="devis-titre">{d.titre}</strong>
						</div>
						<div class="devis-infos">
							{#if d.date_prestation}
								<span style="font-size:.82rem;font-weight:600;color:var(--color-primary)">📅 {new Date(d.date_prestation).toLocaleDateString('fr-FR')}</span>
							{/if}
						</div>
						<div class="devis-meta-right">
							<span class="badge" style="font-size:.78rem;color:{statutDevisColor(d.statut)}">{statutDevisLabel(d.statut)}</span>
							{#if d.montant_estime != null}
								<span class="badge badge-gray" style="font-size:.78rem">💶 {d.montant_estime.toLocaleString('fr-FR')} €</span>
							{/if}
							{#if $isCS}
								<button class="btn-icon-danger" title="Supprimer" on:click|stopPropagation={() => deleteDevis(d.id)}>🗑️</button>
							{/if}
							<span class="toggle-arrow">{devisExpanded ? '▲' : '▼'}</span>
						</div>
					</div>
					{#if devisExpanded}
						<div class="devis-detail-body">
							{#if editDevisId === d.id}
								<div class="form-grid" style="margin-bottom:.6rem">
									<label>Titre *<input bind:value={devisForm.titre} required /></label>
									<label>Date de prestation<input type="date" bind:value={devisForm.date_prestation} /></label>
									<label>Montant estimé (€)<input type="number" min="0" step="0.01" bind:value={devisForm.montant_estime} /></label>
									<label>Périmètre *
										<select bind:value={devisForm.perimetre}>
											{#each devisPerimetreOptions as opt}<option value={opt.val}>{opt.label}</option>{/each}
										</select>
									</label>
									<label>Suivi Kanban
										<select bind:value={devisForm.statut}>
											{#each statutsDevis as s}<option value={s.val}>{s.label}</option>{/each}
										</select>
									</label>
									<label>Fréquence
										<select bind:value={devisForm.frequence_type}>
											<option value=''>— Ponctuelle —</option>
											<option value='fois_par_an'>× / an</option>
											<option value='mois'>Tous les N mois</option>
											<option value='semaines'>Toutes les N semaines</option>
										</select>
									</label>
									{#if devisForm.frequence_type}
										<label>Valeur<input type="number" min="1" bind:value={devisForm.frequence_valeur} /></label>
									{/if}
								</div>
								<div style="margin-top:.75rem">
									<label style="display:flex;align-items:center;gap:.5rem;cursor:pointer">
										<input type="checkbox" bind:checked={devisForm.affichable} style="width:auto;margin:0" />
										<span style="font-size:.875rem">Afficher dans le tableau de bord</span>
									</label>
								</div>
								<div style="margin-top:.5rem">
									<label style="font-size:.85rem;font-weight:600;display:block;margin-bottom:.3rem">Notes</label>
									<RichEditor bind:value={devisForm.notes} placeholder="Notes…" minHeight="60px" />
								</div>
								<div style="margin-top:.5rem">
									<label style="font-size:.85rem;font-weight:600;display:block;margin-bottom:.3rem">Fichiers</label>
									{#if d.fichiers_urls && d.fichiers_urls.length > 0}
										<div style="display:flex;flex-wrap:wrap;gap:.3rem;margin-bottom:.4rem">
											{#each d.fichiers_urls as url, i}
												<div style="display:flex;align-items:center;gap:.2rem">
													<a href={url} target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-outline" style="font-size:.8rem">📎 Fichier {i + 1}</a>
													<button type="button" class="btn btn-sm btn-outline" style="color:var(--color-danger);padding:.15rem .35rem" on:click|stopPropagation={() => deleteDevisFichier(d.id, url)}>✕</button>
												</div>
											{/each}
										</div>
									{/if}
									{#key devisFichierKey}
										<input type="file" multiple accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png" on:change={onDevisFilesChange} />
									{/key}
								</div>
								<div style="display:flex;gap:.4rem;margin-top:.5rem;flex-wrap:wrap">
									<button class="btn btn-sm btn-outline" on:click|stopPropagation={closeDevisForm}>Annuler</button>
									<button class="btn btn-sm btn-primary" disabled={submitting} on:click|stopPropagation={saveDevis}>{submitting ? '…' : 'Enregistrer'}</button>
								</div>
							{:else}
								<div class="detail-grid">
									<div><span class="detail-label">Périmètre</span>{(d.perimetre ?? (d.batiment_id ? `bat:${d.batiment_id}` : 'résidence'))}</div>
									{#if d.date_prestation}<div><span class="detail-label">Date</span>📅 {new Date(d.date_prestation).toLocaleDateString('fr-FR')}</div>{/if}
									{#if d.montant_estime != null}<div><span class="detail-label">Montant</span>💶 {d.montant_estime.toLocaleString('fr-FR')} €</div>{/if}
								</div>
								{#if d.notes}
									<div class="rich-content" style="font-size:.875rem;margin-top:.5rem">{@html safeHtml(d.notes)}</div>
								{/if}
								{#if d.fichiers_urls && d.fichiers_urls.length > 0}
									<div style="display:flex;flex-wrap:wrap;gap:.3rem;margin-top:.5rem">
										{#each d.fichiers_urls as url, i}
											<a href={url} target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-outline">📎 Fichier {i + 1}</a>
										{/each}
									</div>
								{/if}
								{#if $isCS}
									<div style="display:flex;gap:.4rem;margin-top:.5rem;flex-wrap:wrap;align-items:center">
										<button class="btn btn-sm btn-outline" on:click|stopPropagation={() => startEditDevis(d)}>✏️ Modifier</button>
										{#if d.statut === 'en_attente'}
											<button class="btn btn-sm btn-primary" on:click|stopPropagation={() => { osUploadDevisId = d.id; osFile = null; }}>→ Prestataire</button>
											<button class="btn btn-sm btn-outline" style="color:var(--color-danger)" on:click|stopPropagation={() => moveDevisStatut(d.id, 'refuse')}>❌ Refuser</button>
										{:else if d.statut === 'accepte'}
											<button class="btn btn-sm btn-primary" on:click|stopPropagation={() => moveDevisStatut(d.id, 'realise')}>✅ Réalisée</button>
											<button class="btn btn-sm btn-outline" on:click|stopPropagation={() => moveDevisStatut(d.id, 'en_attente')}>← Syndic</button>
											<button class="btn btn-sm btn-outline" style="color:var(--color-danger)" on:click|stopPropagation={() => moveDevisStatut(d.id, 'refuse')}>❌ Refuser</button>
										{:else if d.statut === 'realise'}
											<button class="btn btn-sm btn-outline" on:click|stopPropagation={() => moveDevisStatut(d.id, 'accepte')}>← Chez prestataire</button>
											<button class="btn btn-sm" style="color:#f59e0b" on:click|stopPropagation={() => openNotationForm(d.prestataire_id, d.id)}>⭐ Noter</button>
										{:else if d.statut === 'refuse'}
											<button class="btn btn-sm btn-outline" on:click|stopPropagation={() => moveDevisStatut(d.id, 'en_attente')}>← Remettre en attente</button>
										{/if}
									</div>
								{/if}
							{/if}
						</div>
					{/if}
				</div>
			{/each}

			<!-- Réalisées (accordion fermé) -->
			{#if devisRealises.length > 0}
				<div class="realisees-accordion" style="margin-top:1rem">
					<button class="realisees-toggle" on:click={() => showRealisees = !showRealisees}>
						<span>🏁 Prestations réalisées ({devisRealises.length})</span>
						<span class="toggle-arrow">{showRealisees ? '▲' : '▼'}</span>
					</button>
					{#if showRealisees}
						{#each devisRealises as d (d.id)}
							{@const prestNom = prestataires.find(p => p.id === d.prestataire_id)?.nom ?? '—'}
							{@const devisExpanded = expandedDevis.has(d.id)}
							<div class="devis-expand devis-expand--done" class:expanded={devisExpanded}>
								<div class="devis-row"
									role="button" tabindex="0"
									on:click|stopPropagation={() => toggleDevis(d.id)}
									on:keydown|stopPropagation={e => (e.key === 'Enter' || e.key === ' ') && toggleDevis(d.id)}>
									<div class="devis-body-inner">
										<span class="devis-card-prest">{prestNom}</span>
										<strong class="devis-titre">{d.titre}</strong>
									</div>
									<div class="devis-infos">
										{#if d.date_prestation}
											<span style="font-size:.82rem;font-weight:600;color:var(--color-text-muted)">📅 {new Date(d.date_prestation).toLocaleDateString('fr-FR')}</span>
										{/if}
									</div>
									<div class="devis-meta-right">
										<span class="badge" style="font-size:.78rem;color:#7c3aed">🏁 Réalisé</span>
										{#if d.montant_estime != null}
											<span class="badge badge-gray" style="font-size:.78rem">💶 {d.montant_estime.toLocaleString('fr-FR')} €</span>
										{/if}
										<span class="toggle-arrow">{devisExpanded ? '▲' : '▼'}</span>
									</div>
								</div>
								{#if devisExpanded}
									<div class="devis-detail-body">
										<div class="detail-grid">
											<div><span class="detail-label">Périmètre</span>{(d.perimetre ?? (d.batiment_id ? `bat:${d.batiment_id}` : 'résidence'))}</div>
											{#if d.date_prestation}<div><span class="detail-label">Date</span>📅 {new Date(d.date_prestation).toLocaleDateString('fr-FR')}</div>{/if}
											{#if d.montant_estime != null}<div><span class="detail-label">Montant</span>💶 {d.montant_estime.toLocaleString('fr-FR')} €</div>{/if}
										</div>
										{#if d.notes}
											<div class="rich-content" style="font-size:.875rem;margin-top:.5rem">{@html safeHtml(d.notes)}</div>
										{/if}
										{#if d.fichiers_urls && d.fichiers_urls.length > 0}
											<div style="display:flex;flex-wrap:wrap;gap:.3rem;margin-top:.5rem">
												{#each d.fichiers_urls as url, i}
													<a href={url} target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-outline">📎 Fichier {i + 1}</a>
												{/each}
											</div>
										{/if}
										{#if $isCS}
											<div style="display:flex;gap:.4rem;margin-top:.5rem;flex-wrap:wrap;align-items:center">
												<button class="btn btn-sm btn-outline" on:click|stopPropagation={() => moveDevisStatut(d.id, 'accepte')}>← Chez prestataire</button>
												<button class="btn btn-sm" style="color:#f59e0b" on:click|stopPropagation={() => openNotationForm(d.prestataire_id, d.id)}>⭐ Noter</button>
											</div>
										{/if}
									</div>
								{/if}
							</div>
						{/each}
					{/if}
				</div>
			{/if}
		{/if}
	{/if}

	<!-- Modal nouvelle prestation -->
	{#if devisFormPrestId === -1}
		<div class="modal-overlay" on:click={closeDevisForm}>
			<div class="modal" on:click|stopPropagation>
				<div class="modal-header">
					<h2>📋 {editDevisId ? 'Modifier la prestation' : 'Nouvelle prestation'}</h2>
					<button class="modal-close" on:click={closeDevisForm}>×</button>
				</div>
				<div class="modal-body">
					<p class="devis-form-help">Les prestations ponctuelles alimentent le Calendrier et le Kanban selon leur statut.</p>
					<div class="form-grid">
						<label>Prestataire *
							<select bind:value={devisForm.prestataire_id} required>
								<option value="">— Sélectionner —</option>
								{#each prestataires as p}<option value={String(p.id)}>{p.nom}</option>{/each}
							</select>
						</label>
						<label>Périmètre *
							<select bind:value={devisForm.perimetre}>
								{#each devisPerimetreOptions as opt}<option value={opt.val}>{opt.label}</option>{/each}
							</select>
						</label>
						<label>Titre *<input bind:value={devisForm.titre} required /></label>
						<label>Date de prestation<input type="date" bind:value={devisForm.date_prestation} /></label>
						<label>Montant estimé (€)<input type="number" min="0" step="0.01" bind:value={devisForm.montant_estime} placeholder="Ex. 1200" /></label>
						<label>Suivi Kanban
							<select bind:value={devisForm.statut}>
								{#each statutsDevis as s}<option value={s.val}>{s.label}</option>{/each}
							</select>
						</label>
						<label>Fréquence
							<select bind:value={devisForm.frequence_type}>
								<option value=''>— Ponctuelle —</option>
								<option value='fois_par_an'>× / an</option>
								<option value='mois'>Tous les N mois</option>
								<option value='semaines'>Toutes les N semaines</option>
							</select>
						</label>
						{#if devisForm.frequence_type}
							<label>Valeur<input type="number" min="1" bind:value={devisForm.frequence_valeur} /></label>
						{/if}
					</div>
					<div style="margin-top:.75rem">
						<label style="display:flex;align-items:center;gap:.5rem;cursor:pointer">
							<input type="checkbox" bind:checked={devisForm.affichable} style="width:auto;margin:0" />
							<span style="font-size:.875rem">Afficher dans le tableau de bord</span>
						</label>
					</div>
					<div style="margin-top:.6rem">
						<label style="font-size:.85rem;font-weight:600;display:block;margin-bottom:.3rem">Notes</label>
						<RichEditor bind:value={devisForm.notes} placeholder="Notes…" minHeight="60px" />
					</div>
					<div style="margin-top:.6rem">
						<label style="font-size:.85rem;font-weight:600;display:block;margin-bottom:.3rem">Fichiers</label>
						{#key devisFichierKey}
							<input type="file" multiple accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png" on:change={onDevisFilesChange} />
						{/key}
						{#if devisFichierFiles && devisFichierFiles.length > 0}<span class="devis-file-note">📎 {devisFichierFiles.length} fichier{devisFichierFiles.length > 1 ? 's' : ''}</span>{/if}
					</div>
				</div>
				<div class="modal-footer">
					<button class="btn btn-outline" on:click={closeDevisForm}>Annuler</button>
					<button class="btn btn-primary" disabled={submitting} on:click={saveDevis}>{submitting ? '…' : 'Enregistrer'}</button>
				</div>
			</div>
		</div>
	{/if}
	<!-- Modal OS upload -->
	{#if osUploadDevisId}
		<div class="modal-overlay" on:click={() => { osUploadDevisId = null; osFile = null; }}>
			<div class="modal modal-sm" on:click|stopPropagation>
				<div class="modal-header">
					<h2>Ordre de service</h2>
					<button class="modal-close" on:click={() => { osUploadDevisId = null; osFile = null; }}>×</button>
				</div>
				<div class="modal-body">
					<p style="font-size:.875rem;color:var(--color-text-muted)">Joindre l'OS signé (optionnel) — le statut passera en <strong>Accepté</strong>.</p>
					<input type="file" accept=".pdf,.jpg,.jpeg,.png" on:change={onOsFileChange} style="margin-top:.5rem" />
				</div>
				<div class="modal-footer">
					<button class="btn" on:click={() => { osUploadDevisId = null; osFile = null; }}>Annuler</button>
					<button class="btn btn-primary" disabled={osUploading} on:click={acceptDevisWithOs}>
						{osUploading ? 'Enregistrement...' : "Confirmer l'OS"}
					</button>
				</div>
			</div>
		</div>
	{/if}

<!-- ══════════════════════════════════════════════════════════════ -->
<!-- ONGLET 2 : VISITES                                           -->
<!-- ══════════════════════════════════════════════════════════════ -->
{:else if onglet === 'visites'}

	<div class="visites-summary">
		<div class="visites-kpi">
			<span class="visites-kpi-value">{visites.length}</span>
			<span class="visites-kpi-label">visites planifiées</span>
		</div>
		{#if visitesEnRetard.length > 0}
			<div class="visites-kpi visites-kpi--danger">
				<span class="visites-kpi-value">{visitesEnRetard.length}</span>
				<span class="visites-kpi-label">en retard</span>
			</div>
		{/if}
		<div class="visites-kpi visites-kpi--ok">
			<span class="visites-kpi-value">{visitesAJour.length}</span>
			<span class="visites-kpi-label">en cours</span>
		</div>
	</div>

	{#if visites.length === 0}
		<div class="empty-state card"><h3>Aucune visite planifiée</h3><p>Les visites récurrentes apparaîtront ici dès qu'un contrat avec fréquence sera créé.</p></div>
	{:else}
		<!-- En retard d'abord -->
		{#if visitesEnRetard.length > 0}
			<h2 class="section-title" style="color:var(--color-danger)">⚠️ Visites en retard</h2>
			{#each visitesEnRetard as c (c.id)}
				{@const prest = prestataires.find(p => p.id === c.prestataire_id)}
				{@const contratExpanded = expandedContrats.has(c.id)}
				<div class="visite-card card visite-card--retard" class:expanded={contratExpanded}>
					<div class="visite-row"
						role="button" tabindex="0"
						on:click={() => toggleContrat(c.id)}
						on:keydown={e => (e.key === 'Enter' || e.key === ' ') && toggleContrat(c.id)}>
						<div class="visite-main">
							<strong>{prest?.nom ?? '—'}</strong>
							<span class="badge badge-blue">{equipLabel(c.type_equipement)}</span>
						</div>
						<div class="visite-freq">
							{#if c.frequence_type}<span class="badge badge-blue" style="font-size:.75rem">{frequenceLabel(c)}</span>{/if}
						</div>
						<div class="visite-date visite-date--retard">
							🗓 {new Date(c.prochaine_visite).toLocaleDateString('fr-FR')}
						</div>
						<span class="toggle-arrow">{contratExpanded ? '▲' : '▼'}</span>
					</div>
					{#if contratExpanded}
						<div class="visite-detail">
							<div class="detail-grid">
								<div><span class="detail-label">Contrat</span>{c.libelle}</div>
								{#if c.numero_contrat}<div><span class="detail-label">N° contrat</span>{c.numero_contrat}</div>{/if}
								<div><span class="detail-label">Date début</span>📅 {new Date(c.date_debut).toLocaleDateString('fr-FR')}</div>
								{#if c.duree_initiale_valeur}<div><span class="detail-label">Durée</span>{c.duree_initiale_valeur} {c.duree_initiale_unite}</div>{/if}
							</div>
							{#if $isCS}
								<div style="display:flex;gap:.4rem;margin-top:.5rem;flex-wrap:wrap">
									<button class="btn btn-sm btn-outline" on:click|stopPropagation={() => startEditContrat(c)}>✏️ Modifier</button>
									<button class="btn btn-sm" style="color:#f59e0b" on:click|stopPropagation={() => openNotationForm(c.prestataire_id, undefined, c.id)}>⭐ Noter</button>
								</div>
							{/if}
						</div>
					{/if}
				</div>
			{/each}
		{/if}

		<!-- En cours -->
		{#if visitesAJour.length > 0}
			<h2 class="section-title" style="margin-top:1rem">✅ Visites en cours</h2>
			{#each visitesAJour as c (c.id)}
				{@const prest = prestataires.find(p => p.id === c.prestataire_id)}
				{@const contratExpanded = expandedContrats.has(c.id)}
				<div class="visite-card card" class:expanded={contratExpanded}>
					<div class="visite-row"
						role="button" tabindex="0"
						on:click={() => toggleContrat(c.id)}
						on:keydown={e => (e.key === 'Enter' || e.key === ' ') && toggleContrat(c.id)}>
						<div class="visite-main">
							<strong>{prest?.nom ?? '—'}</strong>
							<span class="badge badge-blue">{equipLabel(c.type_equipement)}</span>
						</div>
						<div class="visite-freq">
							{#if c.frequence_type}<span class="badge badge-blue" style="font-size:.75rem">{frequenceLabel(c)}</span>{/if}
						</div>
						<div class="visite-date">
							{#if c.prochaine_visite}🗓 {new Date(c.prochaine_visite).toLocaleDateString('fr-FR')}{:else}<span style="color:var(--color-text-muted)">Non planifiée</span>{/if}
						</div>
						<span class="toggle-arrow">{contratExpanded ? '▲' : '▼'}</span>
					</div>
					{#if contratExpanded}
						<div class="visite-detail">
							<div class="detail-grid">
								<div><span class="detail-label">Contrat</span>{c.libelle}</div>
								{#if c.numero_contrat}<div><span class="detail-label">N° contrat</span>{c.numero_contrat}</div>{/if}
								<div><span class="detail-label">Date début</span>📅 {new Date(c.date_debut).toLocaleDateString('fr-FR')}</div>
								{#if c.duree_initiale_valeur}<div><span class="detail-label">Durée</span>{c.duree_initiale_valeur} {c.duree_initiale_unite}</div>{/if}
							</div>
							{#if $isCS}
								<div style="display:flex;gap:.4rem;margin-top:.5rem;flex-wrap:wrap">
									<button class="btn btn-sm btn-outline" on:click|stopPropagation={() => startEditContrat(c)}>✏️ Modifier</button>
									<button class="btn btn-sm" style="color:#f59e0b" on:click|stopPropagation={() => openNotationForm(c.prestataire_id, undefined, c.id)}>⭐ Noter</button>
								</div>
							{/if}
						</div>
					{/if}
				</div>
			{/each}
		{/if}
	{/if}

	<!-- Modal notation prestataire -->
	{#if showNotationForm}
		<div class="modal-overlay" on:click={() => { showNotationForm = null; }}>
			<div class="modal" style="max-width:420px" on:click|stopPropagation>
				<div class="modal-header">
					<h2>⭐ Noter le prestataire</h2>
					<button class="modal-close" on:click={() => { showNotationForm = null; }}>×</button>
				</div>
				<div class="modal-body">
					<div style="text-align:center;margin-bottom:1rem">
						<div class="star-picker" style="display:inline-flex;gap:.25rem;font-size:2rem;cursor:pointer">
							{#each [1,2,3,4,5] as s}
								<button type="button" class="star-btn" class:active={notationNote >= s}
									style="background:none;border:none;cursor:pointer;font-size:2rem;color:{notationNote >= s ? '#f59e0b' : '#d1d5db'};transition:color .15s"
									on:click={() => notationNote = s}
									on:mouseenter={() => notationHover = s}
									on:mouseleave={() => notationHover = 0}>
									{(notationHover || notationNote) >= s ? '★' : '☆'}
								</button>
							{/each}
						</div>
						{#if notationNote > 0}<p style="margin:.25rem 0 0;font-size:.9rem;color:var(--color-text-muted)">{notationNote}/5</p>{/if}
					</div>
					<label style="display:block;margin-bottom:.75rem">
						Commentaire (optionnel)
						<textarea bind:value={notationCommentaire} rows="3" style="width:100%;margin-top:.25rem;resize:vertical"></textarea>
					</label>
				</div>
				<div class="modal-footer">
					<button class="btn btn-outline" on:click={() => { showNotationForm = null; }}>Annuler</button>
					<button class="btn btn-primary" disabled={notationNote === 0} on:click={saveNotation}>💾 Enregistrer</button>
				</div>
			</div>
		</div>
	{/if}

<!-- ══════════════════════════════════════════════════════════════ -->
<!-- ONGLET 3 : CONTRATS                                          -->
<!-- ══════════════════════════════════════════════════════════════ -->
{:else if onglet === 'contrats_tab'}

	<!-- Formulaire nouveau contrat (modal) -->
	{#if contratFormPrestId === -1}
		<div class="modal-overlay" on:click={closeContratForm}>
			<div class="modal" on:click|stopPropagation>
				<div class="modal-header">
					<h2>📄 {editContratId ? 'Modifier le contrat' : 'Nouveau contrat'}</h2>
					<button class="modal-close" on:click={closeContratForm}>×</button>
				</div>
				<div class="modal-body">
					<div class="form-grid">
						<label>Libellé *<input bind:value={contratForm.libelle} required /></label>
						<label>Prestataire *
							<select bind:value={contratForm.prestataire_id} required>
								<option value="">— Sélectionner —</option>
								{#each prestataires as pr}<option value={String(pr.id)}>{pr.nom}</option>{/each}
							</select>
						</label>
						<label>Équipement
							<select bind:value={contratForm.type_equipement}>
								{#each equipements as e}<option value={e.val}>{e.label}</option>{/each}
							</select>
						</label>
						<label>N° contrat<input bind:value={contratForm.numero_contrat} /></label>
						<label>Début *<input type="date" bind:value={contratForm.date_debut} required /></label>
						<label>Durée initiale
							<div style="display:flex;gap:.4rem">
								<input type="number" min="1" placeholder="Ex. 12" bind:value={contratForm.duree_initiale_valeur} style="flex:1" />
								<select bind:value={contratForm.duree_initiale_unite} style="width:auto">
									<option value="mois">mois</option>
									<option value="ans">ans</option>
								</select>
							</div>
						</label>
						<label>Fréquence
							<select bind:value={contratForm.frequence_type}>
								<option value="">— Aucune —</option>
								<option value="semaines">Toutes les X semaines</option>
								<option value="mois">Mensuelle</option>
								<option value="fois_par_an">X fois par an</option>
							</select>
						</label>
						{#if contratForm.frequence_type === 'semaines'}
							<label>Toutes les … sem.<input type="number" min="1" bind:value={contratForm.frequence_valeur} /></label>
						{:else if contratForm.frequence_type === 'fois_par_an'}
							<label>… fois/an<input type="number" min="1" bind:value={contratForm.frequence_valeur} /></label>
						{/if}
						<label>Prochaine visite<input type="date" bind:value={contratForm.prochaine_visite} /></label>
					</div>
					<div style="margin-top:.6rem">
						<label style="font-size:.85rem;font-weight:600;display:block;margin-bottom:.3rem">Notes</label>
						<RichEditor bind:value={contratForm.notes} placeholder="Notes sur le contrat…" minHeight="60px" />
					</div>
				</div>
				<div class="modal-footer">
					<button class="btn btn-outline" on:click={closeContratForm}>Annuler</button>
					<button class="btn btn-primary" disabled={submitting} on:click={saveContrat}>{submitting ? '…' : 'Enregistrer'}</button>
				</div>
			</div>
		</div>
	{/if}

	<!-- Synthèse -->
	<div class="contrats-summary">
		<span class="contrats-summary-count">{contrats.length} contrat{contrats.length !== 1 ? 's' : ''} actif{contrats.length !== 1 ? 's' : ''}</span>
	</div>

	<!-- Groupé par spécialité du prestataire -->
	{#if contrats.length === 0}
		<div class="empty-state card"><h3>Aucun contrat</h3><p>Ajoutez le premier contrat via le bouton ci-dessus.</p></div>
	{:else}
		{#each equipements.filter(e => contrats.some(c => { const p = prestataires.find(pr => pr.id === c.prestataire_id); return (p?.specialite ?? c.type_equipement) === e.val; })) as specGroup (specGroup.val)}
			<div class="type-section-header">
				<span class="type-section-label">{specGroup.label}</span>
			</div>
			{#each contrats.filter(c => { const p = prestataires.find(pr => pr.id === c.prestataire_id); return (p?.specialite ?? c.type_equipement) === specGroup.val; }) as c (c.id)}
				{@const prest = prestataires.find(p => p.id === c.prestataire_id)}
				{@const contratExpanded = expandedContrats.has(c.id)}
				<div class="contrat-expand" class:expanded={contratExpanded}>
					<div class="contrat-row"
						role="button" tabindex="0"
						on:click|stopPropagation={() => toggleContrat(c.id)}
						on:keydown|stopPropagation={e => e.key === 'Enter' && toggleContrat(c.id)}>
						<div class="contrat-body-inner">
							<strong class="contrat-titre">{c.libelle}</strong>
							{#if prest}<span class="contrat-meta">— {prest.nom}</span>{/if}
							{#if c.numero_contrat}<span class="contrat-meta">🔖 {c.numero_contrat}</span>{/if}
						</div>
						<div class="contrat-infos">
							{#if c.prochaine_visite}
								<div style="font-size:.82rem;font-weight:600;color:var(--color-primary)">🗓 {new Date(c.prochaine_visite).toLocaleDateString('fr-FR')}</div>
							{:else}
								<div>📅 {new Date(c.date_debut).toLocaleDateString('fr-FR')}</div>
							{/if}
							{#if c.frequence_type}
								<span class="badge badge-blue" style="font-size:.75rem">{frequenceLabel(c)}</span>
							{/if}
						</div>
						<div class="contrat-meta-right">
							<span class="badge" style="font-size:.8rem">📄 {contratDocsMap[c.id]?.length ?? 0}</span>
							{#if $isCS}
								<button class="btn-icon-danger" title="Archiver" on:click|stopPropagation={() => deleteContrat(c.id)}>🗑️</button>
							{/if}
							<span class="toggle-arrow">{contratExpanded ? '▲' : '▼'}</span>
						</div>
					</div>
					{#if contratExpanded}
						<div class="contrat-detail-body">
							{#if editContratId === c.id}
								<div class="contrat-section">
									<div class="contrat-section-title">Infos contrat</div>
									<div class="form-grid">
										<label>Libellé *<input bind:value={contratForm.libelle} required /></label>
										<label>Prestataire *
											<select bind:value={contratForm.prestataire_id} required>
												<option value="">— Sélectionner —</option>
												{#each prestataires as pr}<option value={String(pr.id)}>{pr.nom}</option>{/each}
											</select>
										</label>
										<label>N° contrat<input bind:value={contratForm.numero_contrat} /></label>
										<label>Début *<input type="date" bind:value={contratForm.date_debut} required /></label>
										<label>Durée initiale
											<div style="display:flex;gap:.4rem">
												<input type="number" min="1" placeholder="Ex. 12" bind:value={contratForm.duree_initiale_valeur} style="flex:1" />
												<select bind:value={contratForm.duree_initiale_unite} style="width:auto">
													<option value="mois">mois</option>
													<option value="ans">ans</option>
												</select>
											</div>
										</label>
										<label>Fréquence
											<select bind:value={contratForm.frequence_type}>
												<option value="">— Aucune —</option>
												<option value="semaines">Toutes les X semaines</option>
												<option value="mois">Mensuelle</option>
												<option value="fois_par_an">X fois par an</option>
											</select>
										</label>
										{#if contratForm.frequence_type === 'semaines'}
											<label>Toutes les … sem.<input type="number" min="1" bind:value={contratForm.frequence_valeur} /></label>
										{:else if contratForm.frequence_type === 'fois_par_an'}
											<label>… fois/an<input type="number" min="1" bind:value={contratForm.frequence_valeur} /></label>
										{/if}
										<label>Prochaine visite<input type="date" bind:value={contratForm.prochaine_visite} /></label>
									</div>
								</div>
								<div class="contrat-section">
									<div class="contrat-section-title">Notes</div>
									<RichEditor bind:value={contratForm.notes} placeholder="Notes…" minHeight="60px" />
								</div>
								<div class="contrat-section">
									<div class="contrat-section-title">📄 Documents ({contratDocsMap[c.id]?.length ?? 0})</div>
									{#if contratDocsMap[c.id]?.length > 0}
										{#each contratDocsMap[c.id] as doc}
											<div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.3rem;font-size:.85rem;flex-wrap:wrap">
												<a href={docsApi.downloadUrl(doc.id)} target="_blank">📎 {doc.titre || doc.fichier_nom}</a>
												<span style="font-size:.75rem;color:var(--color-text-muted)">{new Date(doc.publie_le).toLocaleDateString('fr-FR')}</span>
												<button class="btn-icon-danger" title="Supprimer" style="margin-left:auto" on:click|stopPropagation={() => deleteDoc(c.id, doc.id)}>🗑️</button>
											</div>
										{/each}
									{:else}
										<p style="font-size:.82rem;color:var(--color-text-muted);margin:0">Aucun document.</p>
									{/if}
									<div style="display:flex;gap:.4rem;flex-wrap:wrap;align-items:center;margin-top:.5rem">
										<input type="text" placeholder="Titre" bind:value={contratUploadTitre} style="font-size:.82rem;flex:1;min-width:110px" />
										{#key uploadInputKey}<input type="file" on:change={(e) => contratUploadFile = e.currentTarget.files?.[0] ?? null} style="font-size:.82rem" />{/key}
										<button class="btn btn-sm btn-primary" disabled={!contratUploadFile || uploadingDoc} on:click|stopPropagation={() => uploadDoc(c.id)}>{uploadingDoc ? '…' : '+ Document'}</button>
									</div>
								</div>
								<div style="display:flex;gap:.4rem;margin-top:.25rem;flex-wrap:wrap">
									<button class="btn btn-sm btn-outline" on:click|stopPropagation={() => { editContratId = null; resetContratForm(); }}>Annuler</button>
									<button class="btn btn-sm btn-primary" disabled={submitting} on:click|stopPropagation={saveContrat}>{submitting ? '…' : 'Enregistrer'}</button>
								</div>
							{:else}
								<div class="contrat-section">
									<div class="contrat-section-title">Infos contrat</div>
									<div class="detail-grid">
										<div><span class="detail-label">Date de début</span>📅 {new Date(c.date_debut).toLocaleDateString('fr-FR')}</div>
										{#if c.duree_initiale_valeur}<div><span class="detail-label">Durée</span>{c.duree_initiale_valeur} {c.duree_initiale_unite}</div>{/if}
										{#if c.frequence_type}
											<div><span class="detail-label">Fréquence</span>{frequenceLabel(c)}</div>
										{/if}
										{#if c.prochaine_visite}<div><span class="detail-label">Prochaine visite</span><span style="color:var(--color-primary);font-weight:600">🗓 {new Date(c.prochaine_visite).toLocaleDateString('fr-FR')}</span></div>{/if}
									</div>
								</div>
								{#if c.notes}
									<div class="contrat-section">
										<div class="contrat-section-title clickable" role="button" tabindex="0" on:click|stopPropagation={() => { expandedNotes.has(c.id) ? expandedNotes.delete(c.id) : expandedNotes.add(c.id); expandedNotes = expandedNotes; }} on:keydown|stopPropagation={(e) => (e.key === 'Enter' || e.key === ' ') && (expandedNotes.has(c.id) ? expandedNotes.delete(c.id) : expandedNotes.add(c.id), expandedNotes = expandedNotes)}>Synthèse du ou des contrats {expandedNotes.has(c.id) ? '▲' : '▼'}</div>
										{#if expandedNotes.has(c.id)}
											<div class="rich-content" style="font-size:.875rem">{@html safeHtml(c.notes)}</div>
										{/if}
									</div>
								{/if}
								<div class="contrat-section">
									<div class="contrat-section-title">📄 Documents ({contratDocsMap[c.id]?.length ?? 0})</div>
									{#if contratDocsMap[c.id]?.length > 0}
										{#each contratDocsMap[c.id] as doc}
											<div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.3rem;font-size:.85rem;flex-wrap:wrap">
												<a href={docsApi.downloadUrl(doc.id)} target="_blank">📎 {doc.titre || doc.fichier_nom}</a>
												<span style="font-size:.75rem;color:var(--color-text-muted)">{new Date(doc.publie_le).toLocaleDateString('fr-FR')}</span>
												{#if $isCS}
													<button class="btn-icon-danger" title="Supprimer" style="margin-left:auto" on:click|stopPropagation={() => deleteDoc(c.id, doc.id)}>🗑️</button>
												{/if}
											</div>
										{/each}
									{:else}
										<p style="font-size:.82rem;color:var(--color-text-muted);margin:0">Aucun document.</p>
									{/if}
								</div>
								{#if $isCS}
									<div style="display:flex;gap:.4rem;margin-top:.25rem;flex-wrap:wrap">
										<button class="btn btn-sm btn-outline" on:click|stopPropagation={() => startEditContrat(c)}>✏️ Modifier</button>
									</div>
								{/if}
							{/if}
						</div>
					{/if}
				</div>
			{/each}
		{/each}

		<!-- Contrats orphelins -->
		{#if orphanContrats.length > 0}
			<h2 style="font-size:1rem;font-weight:600;margin-top:1.5rem;margin-bottom:.75rem">Contrats sans intervenant</h2>
			{#each orphanContrats as c (c.id)}
				{@const contratExpanded = expandedContrats.has(c.id)}
				<div class="contrat-expand card" class:expanded={contratExpanded}>
					<div class="contrat-row"
						role="button" tabindex="0"
						on:click={() => toggleContrat(c.id)}
						on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && toggleContrat(c.id)}>
						<div class="contrat-body-inner">
							<strong class="contrat-titre">{c.libelle}</strong>
							{#if c.numero_contrat}<span class="contrat-meta">🔖 {c.numero_contrat}</span>{/if}
						</div>
						<div class="contrat-infos">
							{#if c.prochaine_visite}
								<div style="font-size:.82rem;font-weight:600;color:var(--color-primary)">🗓 {new Date(c.prochaine_visite).toLocaleDateString('fr-FR')}</div>
							{:else}
								<div>📅 {new Date(c.date_debut).toLocaleDateString('fr-FR')}</div>
							{/if}
						</div>
						<div class="contrat-meta-right">
							<span class="badge" style="font-size:.8rem">📄 {contratDocsMap[c.id]?.length ?? 0}</span>
							<span class="toggle-arrow">{contratExpanded ? '▲' : '▼'}</span>
						</div>
					</div>
					{#if contratExpanded}
						<div class="contrat-detail-body">
							{#if editContratId === c.id}
								<div class="form-grid" style="margin-bottom:.6rem">
									<label>Libellé *<input bind:value={contratForm.libelle} required /></label>
									<label>Prestataire *
										<select bind:value={contratForm.prestataire_id} required>
											<option value="">— Sélectionner —</option>
											{#each prestataires as pr}<option value={String(pr.id)}>{pr.nom}</option>{/each}
										</select>
									</label>
									<label>N° contrat<input bind:value={contratForm.numero_contrat} /></label>
									<label>Début *<input type="date" bind:value={contratForm.date_debut} required /></label>
									<label>Prochaine visite<input type="date" bind:value={contratForm.prochaine_visite} /></label>
								</div>
								<div style="display:flex;gap:.4rem;margin-top:.6rem;flex-wrap:wrap">
									<button class="btn btn-sm btn-outline" on:click={() => { editContratId = null; resetContratForm(); }}>Annuler</button>
									<button class="btn btn-sm btn-primary" disabled={submitting} on:click={saveContrat}>{submitting ? '…' : 'Enregistrer'}</button>
								</div>
							{:else}
								<div class="contrat-section">
									<div class="contrat-section-title">Infos contrat</div>
									<div class="detail-grid">
										<div><span class="detail-label">Date de début</span>📅 {new Date(c.date_debut).toLocaleDateString('fr-FR')}</div>
										{#if c.prochaine_visite}<div><span class="detail-label">Prochaine visite</span><span style="color:var(--color-primary);font-weight:600">🗓 {new Date(c.prochaine_visite).toLocaleDateString('fr-FR')}</span></div>{/if}
									</div>
								</div>
								{#if c.notes}
									<div class="contrat-section">
										<div class="contrat-section-title clickable" role="button" tabindex="0" on:click|stopPropagation={() => { expandedNotes.has(c.id) ? expandedNotes.delete(c.id) : expandedNotes.add(c.id); expandedNotes = expandedNotes; }} on:keydown|stopPropagation={(e) => (e.key === 'Enter' || e.key === ' ') && (expandedNotes.has(c.id) ? expandedNotes.delete(c.id) : expandedNotes.add(c.id), expandedNotes = expandedNotes)}>Synthèse {expandedNotes.has(c.id) ? '▲' : '▼'}</div>
										{#if expandedNotes.has(c.id)}
											<div class="rich-content" style="font-size:.875rem">{@html safeHtml(c.notes)}</div>
										{/if}
									</div>
								{/if}
								<div class="contrat-section">
									<div class="contrat-section-title">📄 Documents ({contratDocsMap[c.id]?.length ?? 0})</div>
									{#if contratDocsMap[c.id]?.length > 0}
										{#each contratDocsMap[c.id] as doc}
											<div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.3rem;font-size:.85rem;flex-wrap:wrap">
												<a href={docsApi.downloadUrl(doc.id)} target="_blank">📎 {doc.titre || doc.fichier_nom}</a>
												<span style="font-size:.75rem;color:var(--color-text-muted)">{new Date(doc.publie_le).toLocaleDateString('fr-FR')}</span>
												{#if $isCS}
													<button class="btn-icon-danger" title="Supprimer" style="margin-left:auto" on:click|stopPropagation={() => deleteDoc(c.id, doc.id)}>🗑️</button>
												{/if}
											</div>
										{/each}
									{:else}
										<p style="font-size:.82rem;color:var(--color-text-muted);margin:0">Aucun document.</p>
									{/if}
								</div>
								{#if $isCS}
									<div style="display:flex;gap:.4rem;margin-top:.25rem">
										<button class="btn btn-sm btn-outline" on:click={() => startEditContrat(c)}>✏️ Modifier</button>
										<button class="btn btn-sm btn-outline danger" on:click={() => deleteContrat(c.id)}>🗑️ Archiver</button>
									</div>
								{/if}
							{/if}
						</div>
					{/if}
				</div>
			{/each}
		{/if}
	{/if}

<!-- ══════════════════════════════════════════════════════════════ -->
<!-- ONGLET 4 : PRESTATAIRES (annuaire)                           -->
<!-- ══════════════════════════════════════════════════════════════ -->
{:else if onglet === 'prestataires'}

	<!-- Filtres par type -->
	<div class="filters">
		<button class="btn btn-sm" class:btn-primary={filtreType === ''} on:click={() => filtreType = ''}>Tous</button>
		{#each typesPrestataire as t}
			<button class="btn btn-sm" class:btn-primary={filtreType === t.val} on:click={() => filtreType = t.val} title={t.desc}>{t.label}</button>
		{/each}
	</div>

	<!-- Filtres par équipement -->
	<div class="filters">
		<button class="btn btn-sm" class:btn-primary={filtreEquipement === ''} on:click={() => filtreEquipement = ''}>Tous équipements</button>
		{#each equipements as e}
			<button class="btn btn-sm" class:btn-primary={filtreEquipement === e.val} on:click={() => filtreEquipement = e.val}>{e.label}</button>
		{/each}
	</div>

	{#if $isCS && showPrestForm}
		<div class="card" style="padding:1.25rem;margin-bottom:1.25rem">
			<h2 style="font-size:1rem;font-weight:600;margin-bottom:.75rem">{editPrestId ? 'Modifier le prestataire' : 'Nouveau prestataire'}</h2>
			<form on:submit|preventDefault={savePrest}>
				<div class="form-grid">
					<label>Nom *<input bind:value={prestForm.nom} required /></label>
					<label>Type *
						<select bind:value={prestForm.type_prestataire} required>
							{#each typesPrestataire as t}<option value={t.val}>{t.label}</option>{/each}
						</select>
					</label>
					<label>Spécialité *
						<select bind:value={prestForm.specialite} required>
							<option value="">— Sélectionner —</option>
							{#each equipements as e}<option value={e.val}>{e.label}</option>{/each}
						</select>
					</label>
					<label>Email<input type="email" bind:value={prestForm.email} /></label>
				</div>
				<div style="margin-top:.75rem">
					<div style="font-size:.85rem;font-weight:600;margin-bottom:.35rem">Contact{prestContacts.length > 1 ? 's' : ''}</div>
					{#each prestContacts as contact, i}
						<div class="contact-block" style="border:1px solid var(--color-border);border-radius:6px;padding:.6rem;margin-bottom:.5rem;background:var(--color-bg)">
							<div style="display:flex;gap:.4rem;flex-wrap:wrap;margin-bottom:.35rem">
								<input style="flex:2;min-width:140px" bind:value={prestContacts[i].telephone} placeholder="Téléphone *" />
								<input style="flex:1;min-width:100px" bind:value={prestContacts[i].prenom} placeholder="Prénom" />
								<input style="flex:1;min-width:100px" bind:value={prestContacts[i].nom} placeholder="Nom" />
							</div>
							<div style="display:flex;gap:.4rem;flex-wrap:wrap;align-items:center">
								<input style="flex:1;min-width:120px" bind:value={prestContacts[i].fonction} placeholder="Fonction" />
								<input style="flex:1;min-width:140px" type="email" bind:value={prestContacts[i].email} placeholder="Email" />
								{#if prestContacts.length > 1}
									<button type="button" class="btn btn-sm btn-outline" style="color:#dc2626;border-color:#dc2626;flex-shrink:0" on:click={() => prestContacts = prestContacts.filter((_, j) => j !== i)}>−</button>
								{/if}
							</div>
						</div>
					{/each}
					<button type="button" class="btn btn-sm btn-outline" on:click={() => prestContacts = [...prestContacts, { telephone: '', prenom: '', nom: '', fonction: '', email: '' }]}>+ Nouveau contact</button>
				</div>
				<div class="form-actions">
					<button type="button" class="btn btn-outline" on:click={() => { showPrestForm = false; resetPrestForm(); }}>Annuler</button>
					<button class="btn btn-primary" disabled={submitting}>{submitting ? '…' : 'Enregistrer'}</button>
				</div>
			</form>
		</div>
	{/if}

	{#if filteredPrests.length === 0}
		<div class="empty-state card"><h3>Aucun prestataire{filtreEquipement || filtreType ? ' pour ces critères' : ''}</h3></div>
	{:else}
		{#each typesPrestataire.filter(t => filteredPrests.some(p => p.type_prestataire === t.val)) as typeGroup (typeGroup.val)}
			{#if !filtreType}
				<div class="type-section-header">
					<span class="type-section-label">{typeGroup.label}</span>
					<span class="type-section-desc">{typeGroup.desc}</span>
				</div>
			{/if}
			{#each filteredPrests.filter(p => p.type_prestataire === typeGroup.val) as p (p.id)}
				{@const expanded = expandedPrests.has(p.id)}
				{@const cs = contratsForPrest(p.id)}
				{@const dv = devisForPrest(p.id)}
				{@const nextVisit = nextVisitForPrest(p.id)}
				<div class="prest-expand card" class:expanded>
					<div class="prest-header"
						role="button" tabindex="0"
						on:click={() => togglePrest(p.id)}
						on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && togglePrest(p.id)}>
						<div class="prest-main">
							<strong class="prest-nom">{p.nom}</strong>
							<span class="badge badge-type" style="margin-left:.5rem">{typeLabel(p.type_prestataire)}</span>
							<span class="badge badge-blue" style="margin-left:.25rem">{equipLabel(p.specialite)}</span>
							{@const avg = avgNote(p.id)}
							{#if avg !== null}
								<span class="badge" style="margin-left:.25rem;color:#f59e0b;font-size:.82rem" title="{avg}/5 ({notations.filter(n => n.prestataire_id === p.id).length} avis)">
									{starsDisplay(avg)} {avg}
								</span>
							{/if}
						</div>
						{#if !compactPrests || expanded}
							<div class="prest-contacts">
								{#if p.contacts && p.contacts.length > 0}
									{#each p.contacts as c}
										<span class="prest-contact">
											📞 {c.telephone}{#if c.prenom || c.nom}{' '}— {c.prenom ?? ''} {c.nom ?? ''}{/if}{#if c.fonction}{' '}({c.fonction}){/if}
										</span>
									{/each}
								{:else if p.telephone}
									{#each splitTels(p.telephone) as tel}
										<span class="prest-contact">📞 {tel.trim()}</span>
									{/each}
								{/if}
								{#if p.email}<span class="prest-contact">✉️ {p.email}</span>{/if}
							</div>
						{/if}
						<div class="prest-meta">
							{#if !compactPrests || expanded}
								<span class="badge badge-gray">{cs.length} contrat{cs.length !== 1 ? 's' : ''}</span>
								<span class="badge badge-gray">{dv.length} prestation{dv.length !== 1 ? 's' : ''}</span>
								{#if nextVisit}<span class="badge" style="font-size:.75rem;color:var(--color-primary)">🗓 {new Date(nextVisit).toLocaleDateString('fr-FR')}</span>{/if}
							{/if}
							{#if $isCS}
								<button class="btn-icon-edit" title="Modifier" on:click|stopPropagation={() => startEditPrest(p)}>✏️</button>
								<button class="btn-icon-danger" title="Archiver" on:click|stopPropagation={() => deletePrest(p.id)}>🗑️</button>
							{/if}
							<span class="toggle-arrow">{expanded ? '▲' : '▼'}</span>
						</div>
					</div>
					{#if expanded}
						<div class="prest-body">
							<div class="detail-grid">
								{#if p.telephone}
									<div><span class="detail-label">Téléphone</span>
										{#each splitTels(p.telephone) as tel}
											<span style="display:block">📞 {tel.trim()}</span>
										{/each}
									</div>
								{/if}
								{#if p.email}<div><span class="detail-label">Email</span>✉️ {p.email}</div>{/if}
								<div><span class="detail-label">Contrats</span>{cs.length}</div>
								<div><span class="detail-label">Prestations</span>{dv.length}</div>
								{#if nextVisit}<div><span class="detail-label">Prochaine visite</span><span style="color:var(--color-primary);font-weight:600">🗓 {new Date(nextVisit).toLocaleDateString('fr-FR')}</span></div>{/if}
							</div>
						</div>
					{/if}
				</div>
			{/each}
		{/each}
	{/if}

<!-- ══════════════════════════════════════════════════════════════ -->
<!-- ONGLET 5 : CONSOMMATIONS (inchangé)                          -->
<!-- ══════════════════════════════════════════════════════════════ -->
{:else if onglet === 'consommations'}

	<div class="compteur-selector" style="margin-bottom:1.25rem">
		<div style="display:flex;gap:.5rem;flex-wrap:wrap;align-items:center">
			{#each compteurConfigs as cfg}
				<button class="btn btn-sm" class:btn-primary={typeCompteur === cfg.type_compteur}
					on:click={() => { typeCompteur = cfg.type_compteur; }}>
					{cfg.label}
				</button>
			{/each}
			{#if $isCS}
				<button class="btn btn-sm btn-outline" on:click={() => { showAddCompteur = !showAddCompteur; newCompteurLabel = ''; }}
					title="Ajouter une catégorie">+ Catégorie</button>
			{/if}
		</div>

		{#if currentCompteur && $isCS}
			<div class="compteur-config-row" style="margin-top:.6rem">
				{#if editCompteurId === currentCompteur.id}
					<span style="font-size:.82rem;color:var(--color-text-muted)">Fournisseur :</span>
					<select bind:value={editCompteurPrestId} style="font-size:.82rem;padding:.2rem .4rem;border:1px solid var(--color-border);border-radius:var(--radius);background:var(--color-bg)">
						<option value="">— Aucun —</option>
						{#each prestataires as p}<option value={String(p.id)}>{p.nom}</option>{/each}
					</select>
					<button class="btn btn-sm btn-primary" on:click={() => saveCompteurPrestataire(currentCompteur)}>Enregistrer</button>
					<button class="btn btn-sm btn-outline" on:click={() => editCompteurId = null}>Annuler</button>
					{#if compteurConfigs.length > 1}
						<button class="btn btn-sm btn-outline" style="color:var(--color-danger);border-color:var(--color-danger);margin-left:auto"
							on:click={() => deleteCompteurConfig(currentCompteur)}>🗑️</button>
					{/if}
				{:else}
					{@const prest = currentCompteur.prestataire_id ? prestataires.find(p => p.id === currentCompteur.prestataire_id) : null}
					{#if prest}
						<span class="badge badge-blue" style="font-size:.78rem">🔧 {prest.nom}</span>
					{:else}
						<span style="font-size:.78rem;color:var(--color-text-muted)">Aucun fournisseur</span>
					{/if}
					<button class="btn-icon-edit" title="Modifier le fournisseur" on:click={() => startEditCompteur(currentCompteur)}>✏️</button>
				{/if}
			</div>
		{/if}

		{#if showAddCompteur && $isCS}
			<div style="display:flex;gap:.5rem;align-items:center;margin-top:.5rem;flex-wrap:wrap">
				<input type="text" bind:value={newCompteurLabel} placeholder="Ex. EDF Parking privé"
					style="flex:1;min-width:180px;font-size:.875rem;padding:.35rem .55rem;border:1px solid var(--color-border);border-radius:var(--radius);background:var(--color-bg)" />
				<button class="btn btn-sm btn-primary" disabled={addCompteurSaving || !newCompteurLabel.trim()}
					on:click={addCompteurConfig}>{addCompteurSaving ? '…' : 'Ajouter'}</button>
				<button class="btn btn-sm btn-outline" on:click={() => showAddCompteur = false}>Annuler</button>
			</div>
		{/if}
	</div>

	{#if showReleveForm && $isCS}
		<div class="card" style="padding:1.25rem;margin-bottom:1.25rem;max-width:520px">
			<h2 style="font-size:1rem;font-weight:600;margin-bottom:.75rem">{editReleveId ? 'Modifier le relevé' : currentCompteur ? `Nouveau relevé — ${currentCompteur.label}` : 'Nouveau relevé'}</h2>
			<form on:submit|preventDefault={saveReleve}>
				<div class="form-grid">
					<label>Date du relevé *<input type="date" bind:value={releveForm.date_releve} required /></label>
					<label>Index (m³)<input type="number" min="0" bind:value={releveForm.index} placeholder="Ex. 47047" /></label>
				</div>
				<div class="field" style="margin-top:.6rem">
					<label for="releve-note" style="font-size:.875rem;font-weight:500;display:block;margin-bottom:.25rem">Note (optionnel)</label>
					<input id="releve-note" type="text" bind:value={releveForm.note} placeholder="Ex. Changement compteur" style="width:100%" />
				</div>
				<div class="field" style="margin-top:.6rem">
					<span style="font-size:.875rem;font-weight:500;display:block;margin-bottom:.25rem">Photo du relevé (optionnel)</span>
					{#key relevePhotoKey}
						<input type="file" accept="image/*" on:change={(e) => relevePhotoFile = e.currentTarget.files?.[0] ?? null} style="font-size:.875rem" />
					{/key}
				</div>
				<div class="form-actions" style="margin-top:.75rem">
					<button type="button" class="btn btn-outline" on:click={resetReleveForm}>Annuler</button>
					<button type="submit" class="btn btn-primary" disabled={releveSaving}>{releveSaving ? '…' : 'Enregistrer'}</button>
				</div>
			</form>
		</div>
	{/if}

	{#if releveLoading}
		<p style="color:var(--color-text-muted)">Chargement…</p>
	{:else if releves.length === 0}
		<div class="empty-state card"><h3>Aucun relevé</h3><p>Ajoutez le premier relevé via le bouton ci-dessus.</p></div>
	{:else}
		{#each relevesByYear as [year, yearReleves] (year)}
			<h2 class="releve-year">{year}</h2>
			{#each yearReleves as r (r.id)}
				<div class="releve-row">
					<div class="releve-main">
						<span class="releve-date">Relevé {fmtReleve(r)}</span>
						{#if r.note}<span class="releve-note">{r.note}</span>{/if}
						{#if r.index != null}
							<span class="releve-index">Index : <strong>{r.index.toLocaleString('fr-FR')}</strong></span>
						{/if}
						{#if r.photo_url}
							<a href={r.photo_url} target="_blank" rel="noopener">
								<img src={r.photo_url} alt="Photo relevé" class="releve-photo-thumb" />
							</a>
						{/if}
					</div>
					{#if $isCS}
						<div class="releve-actions">
							<button class="btn-icon-edit" title="Modifier" on:click={() => startEditReleve(r)}>✏️</button>
							<button class="btn-icon-danger" title="Supprimer" on:click={() => deleteReleve(r.id)}>🗑️</button>
						</div>
					{/if}
				</div>
			{/each}
		{/each}
	{/if}
{/if}

<style>
	.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: .5rem; padding-left: 1.25rem; }

	/* ── Onglets ── */
	.tabs { display: flex; gap: .25rem; border-bottom: 2px solid var(--color-border); padding-bottom: .1rem; margin-bottom: 1.5rem; overflow-x: auto; scrollbar-width: thin; }
	.tabs button { padding: .45rem .75rem; border: none; background: none; cursor: pointer; font-size: .85rem; color: var(--color-text-muted); border-bottom: 2px solid transparent; margin-bottom: -2px; border-radius: var(--radius) var(--radius) 0 0; white-space: nowrap; display: inline-flex; align-items: center; gap: .3rem; }
	.tabs button:hover { color: var(--color-text); background: var(--color-bg); }
	.tabs button.active { color: var(--color-primary); font-weight: 600; border-bottom-color: var(--color-primary); }

	/* ── Sous-vue toggle ── */
	.sous-vue-toggle { display: flex; gap: .4rem; align-items: center; margin-bottom: 1rem; flex-wrap: wrap; }

	/* ── Compteur config row ── */
	.compteur-config-row { display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; font-size: .82rem; }

	.filters { display: flex; gap: .4rem; flex-wrap: nowrap; overflow-x: auto; padding-bottom: .25rem; margin-bottom: .75rem; scrollbar-width: thin; }
	.filters button { flex-shrink: 0; }

	/* Section type header */
	.type-section-header { display: flex; align-items: baseline; gap: .5rem; margin: 1.25rem 0 .5rem; padding-bottom: .3rem; border-bottom: 2px solid var(--color-border); }
	.type-section-header:first-child { margin-top: 0; }
	.type-section-label { font-size: 1rem; font-weight: 700; }
	.type-section-desc { font-size: .82rem; color: var(--color-text-muted); font-style: italic; }

	/* Carte prestataire expansible */
	.prest-expand { margin-bottom: .6rem; border-left: 3px solid var(--color-border); transition: border-color .12s; padding: 0; overflow: hidden; }
	.prest-expand:hover, .prest-expand.expanded { border-left-color: var(--color-primary); }
	.prest-header { display: flex; align-items: center; gap: .75rem; padding: .85rem 1rem; cursor: pointer; flex-wrap: wrap; }
	.prest-main { display: flex; align-items: center; min-width: 160px; flex-wrap: wrap; gap: .25rem; }
	.prest-nom { font-size: .95rem; }
	.badge-type { background: var(--color-bg-secondary, #f0f0f0); color: var(--color-text); font-size: .75rem; }
	.prest-contacts { display: flex; flex-wrap: wrap; gap: .4rem .75rem; flex: 1; }
	.prest-contact { font-size: .82rem; color: var(--color-text-muted); }
	.prest-meta { display: flex; align-items: center; gap: .4rem; margin-left: auto; }
	.toggle-arrow { font-size: .75rem; color: var(--color-primary); margin-left: .25rem; }
	.prest-body { padding: .25rem 1rem 1rem 1rem; border-top: 1px solid var(--color-border); }

	/* ── Visites ── */
	.visites-summary { display: flex; gap: .75rem; margin-bottom: 1.25rem; flex-wrap: wrap; }
	.visites-kpi { display: flex; flex-direction: column; align-items: center; padding: .6rem 1rem; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius); min-width: 90px; }
	.visites-kpi-value { font-size: 1.5rem; font-weight: 700; color: var(--color-primary); }
	.visites-kpi-label { font-size: .75rem; color: var(--color-text-muted); }
	.visites-kpi--danger .visites-kpi-value { color: var(--color-danger, #dc2626); }
	.visites-kpi--ok .visites-kpi-value { color: #16a34a; }
	.visite-card { margin-bottom: .5rem; border-left: 3px solid var(--color-border); overflow: hidden; transition: border-color .12s; }
	.visite-card:hover, .visite-card.expanded { border-left-color: var(--color-primary); }
	.visite-card--retard { border-left-color: var(--color-danger, #dc2626) !important; }
	.visite-row { display: flex; align-items: center; gap: .75rem; padding: .7rem 1rem; cursor: pointer; flex-wrap: wrap; }
	.visite-main { display: flex; align-items: center; gap: .5rem; flex: 1; min-width: 150px; flex-wrap: wrap; }
	.visite-freq { flex-shrink: 0; }
	.visite-date { font-size: .85rem; font-weight: 600; color: var(--color-primary); flex-shrink: 0; }
	.visite-date--retard { color: var(--color-danger, #dc2626) !important; }
	.visite-detail { padding: .75rem 1rem; border-top: 1px solid var(--color-border); background: var(--color-bg-secondary, #f8f9fa); }

	/* ── Contrats summary ── */
	.contrats-summary { margin-bottom: 1rem; }
	.contrats-summary-count { font-size: .85rem; color: var(--color-text-muted); }

	/* Contrat expansible */
	.contrat-expand { margin-bottom: .3rem; border-left: 2px solid var(--color-border); border-radius: var(--radius); overflow: hidden; transition: border-color .12s; }
	.contrat-expand:hover, .contrat-expand.expanded { border-left-color: var(--color-primary); }

	/* Devis expansible */
	.devis-expand { margin-bottom: .3rem; border-left: 2px solid var(--color-border); border-radius: var(--radius); overflow: hidden; transition: border-color .12s; }
	.devis-expand:hover, .devis-expand.expanded { border-left-color: #7c3aed; }
	.devis-row { display: flex; gap: .75rem; align-items: center; padding: .55rem .75rem; cursor: pointer; transition: background .12s; }
	.devis-row:hover { background: var(--color-bg-secondary, #f8f9fa); }
	.devis-body-inner { flex: 1; min-width: 0; }
	.devis-titre { font-size: .9rem; }
	.devis-infos { text-align: right; font-size: .82rem; min-width: 90px; flex-shrink: 0; }
	.devis-meta-right { display: flex; align-items: center; gap: .3rem; flex-shrink: 0; }
	.devis-detail-body { padding: .75rem 1rem 1rem; border-top: 1px solid var(--color-border); background: var(--color-bg-secondary, #f8f9fa); }
	.contrat-detail-body { padding: .75rem 1rem 1rem; border-top: 1px solid var(--color-border); background: var(--color-bg-secondary, #f8f9fa); }
	.contrat-section { margin-bottom: 1rem; }
	.contrat-section:last-child { margin-bottom: 0; }
	.contrat-section-title { font-size: .75rem; font-weight: 700; text-transform: uppercase; letter-spacing: .05em; color: var(--color-text-muted); margin-bottom: .4rem; padding-bottom: .25rem; border-bottom: 1px solid var(--color-border); }
	.contrat-section-title.clickable { cursor: pointer; user-select: none; }
	.contrat-section-title.clickable:hover { color: var(--color-primary); }

	.contrat-row { display: flex; gap: .75rem; align-items: flex-start; padding: .55rem .75rem; cursor: pointer; transition: background .12s; }
	.contrat-row:hover { background: var(--color-bg-secondary, #f8f9fa); }
	.contrat-body-inner { flex: 1; min-width: 0; }
	.contrat-titre { font-size: .9rem; }
	.contrat-meta { font-size: .78rem; color: var(--color-text-muted); margin-left: .5rem; }
	.contrat-infos { text-align: right; font-size: .82rem; min-width: 100px; flex-shrink: 0; }
	.contrat-meta-right { display: flex; align-items: flex-start; gap: .3rem; flex-shrink: 0; }

	.contrat-form-inline { margin-top: .75rem; padding: .85rem 1rem; background: var(--color-bg-secondary, #f8f9fa); border-radius: var(--radius); border: 1px solid var(--color-border); }
	.add-contrat-btn { margin-top: .6rem; }

	.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: .65rem; }
	.form-grid label { display: flex; flex-direction: column; gap: .25rem; font-size: .875rem; }
	.form-grid input, .form-grid select { padding: .4rem .55rem; border: 1px solid var(--color-border); border-radius: var(--radius); font-size: .875rem; background: var(--color-bg); width: 100%; }
	.devis-form-help { margin: 0 0 .75rem; font-size: .82rem; color: var(--color-text-muted); line-height: 1.45; }
	.devis-file-note { display: inline-block; margin-top: .35rem; font-size: .8rem; color: var(--color-text-muted); }
	.form-actions { display: flex; justify-content: flex-end; gap: .5rem; margin-top: .75rem; }

	.detail-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: .6rem; }
	.detail-label { display: block; font-size: .75rem; color: var(--color-text-muted); text-transform: uppercase; letter-spacing: .05em; margin-bottom: .1rem; }

	.muted-sm { font-size: .85rem; color: var(--color-text-muted); padding: .4rem 0; }
	.danger:hover { color: var(--color-danger); border-color: var(--color-danger); }
	.rich-content { font-size: .85rem; line-height: 1.6; color: var(--color-text); margin-bottom: .5rem; }
	.rich-content :global(p) { margin: 0 0 .5em; }
	.rich-content :global(ul), .rich-content :global(ol) { padding-left: 1.4em; margin: 0 0 .5em; }
	.rich-content :global(strong) { font-weight: 600; }
	.rich-content :global(em) { font-style: italic; }

	/* Relevés compteurs */
	.releve-year { font-size: 1.1rem; font-weight: 700; margin: 1.25rem 0 .6rem; padding-bottom: .3rem; border-bottom: 2px solid var(--color-border); }
	.releve-row { display: flex; align-items: flex-start; justify-content: space-between; gap: .75rem; padding: .6rem .9rem; border-left: 3px solid var(--color-border); border-radius: var(--radius); background: var(--color-surface); margin-bottom: .3rem; transition: border-color .12s; }
	.releve-row:hover { border-left-color: var(--color-primary); }
	.releve-main { display: flex; flex-direction: column; gap: .2rem; }
	.releve-date { font-size: .9rem; font-weight: 600; }
	.releve-note { font-size: .82rem; color: var(--color-text-muted); font-style: italic; }
	.releve-index { font-size: .875rem; }
	.releve-actions { display: flex; gap: .25rem; flex-shrink: 0; }
	.releve-photo-thumb { width: 56px; height: 56px; object-fit: cover; border-radius: var(--radius); border: 1px solid var(--color-border); margin-top: .2rem; display: block; }

	@media (max-width: 600px) {
		.prest-header { gap: .5rem; }
		.contrat-infos { min-width: 80px; }
		.visite-row { gap: .4rem; }
		.tabs button { padding: .4rem .55rem; font-size: .78rem; }
	}

	/* ── Devis kanban ───────────── */
	.devis-toolbar { display: flex; align-items: center; gap: 1rem; margin-bottom: .75rem; flex-wrap: wrap; }
	.kanban-count-total { font-size: .8rem; color: var(--color-text-muted); }
	.devis-kanban { display: flex; gap: .6rem; align-items: flex-start; overflow-x: auto; padding-bottom: .5rem; margin-bottom: 1.5rem; }
	.kanban-col { min-width: 230px; flex: 1; border-radius: var(--radius); background: var(--color-bg); border: 1px solid var(--color-border); overflow: hidden; }
	@media (max-width: 900px) { .devis-kanban { flex-direction: column; } .kanban-col { min-width: 100%; } }
	.kanban-col-header { display: flex; justify-content: space-between; align-items: center; padding: .6rem .9rem; border-top: 3px solid; font-weight: 600; font-size: .8rem; text-transform: uppercase; letter-spacing: .06em; }
	.kanban-count { background: var(--color-border); border-radius: 999px; padding: .1rem .45rem; font-size: .72rem; font-weight: 700; }
	.kanban-empty { padding: 1rem; font-size: .85rem; color: var(--color-text-muted); text-align: center; }
	.kanban-card { margin: .3rem; padding: .4rem .55rem; display: flex; flex-direction: column; gap: .15rem; cursor: pointer; transition: box-shadow .15s; }
	.kanban-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,.10); }
	.kanban-card-tags { display: flex; flex-wrap: wrap; gap: .25rem; margin-bottom: .1rem; min-height: .1rem; }
	.kb-tag { font-size: .65rem; font-weight: 600; padding: .1rem .4rem; border-radius: 3px; color: #fff; line-height: 1.4; }
	.devis-card-prest { font-size: .68rem; color: var(--color-text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
	.kanban-card-titre { font-size: .78rem; line-height: 1.3; }
	.kanban-card-footer { display: flex; justify-content: space-between; align-items: flex-end; margin-top: .25rem; gap: .3rem; }
	.devis-card-meta { display: flex; flex-direction: column; gap: .1rem; min-width: 0; }
	.devis-montant { font-size: .75rem; color: var(--color-primary); font-weight: 600; }
	.devis-date { font-size: .7rem; color: var(--color-text-muted); }
	.devis-os-link { font-size: .7rem; color: var(--color-primary); }
	.kanban-card-actions { display: flex; gap: .2rem; align-items: center; flex-shrink: 0; }
	.devis-step-btn { padding: .15rem .45rem; border: 1px solid var(--color-border); border-radius: var(--radius); background: var(--color-surface); font-size: .72rem; cursor: pointer; color: var(--color-text-muted); transition: background .12s, color .12s, border-color .12s; line-height: 1.4; white-space: nowrap; }
	.devis-step-btn:hover { background: var(--color-bg-hover, #f3f4f6); color: var(--color-text); border-color: var(--color-text-muted); }
	.devis-step-btn--primary { background: #fff7ed; border-color: #f97316; color: #c2410c; }
	.devis-step-btn--primary:hover { background: #f97316; color: #fff; border-color: #f97316; }
	.devis-step-btn--success { background: #f0fdf4; border-color: #22c55e; color: #16a34a; }
	.devis-step-btn--success:hover { background: #22c55e; color: #fff; border-color: #22c55e; }

	/* Réalisées accordion */
	.realisees-accordion { border: 1px solid var(--color-border); border-radius: var(--radius); overflow: hidden; }
	.realisees-toggle { display: flex; justify-content: space-between; align-items: center; width: 100%; padding: .65rem 1rem; border: none; background: var(--color-bg-secondary, #f8f9fa); cursor: pointer; font-size: .85rem; font-weight: 600; color: var(--color-text-muted); }
	.realisees-toggle:hover { background: var(--color-bg-hover, #f3f4f6); color: var(--color-text); }
	.devis-expand--done { opacity: .75; }
	.devis-expand--done:hover { opacity: 1; }
</style>
