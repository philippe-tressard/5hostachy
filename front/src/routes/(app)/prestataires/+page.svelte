<script lang="ts">
	import Modale from '$lib/components/Modale.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import EntetePage from '$lib/components/EntetePage.svelte';
	import BoutonNouveau from '$lib/components/BoutonNouveau.svelte';
	import FormulaireCreation from '$lib/components/FormulaireCreation.svelte';
	import FormulairePrestation from '$lib/components/FormulairePrestation.svelte';
	import FichiersUpload from '$lib/components/FichiersUpload.svelte';
	import ModaleOrdreService from '$lib/components/ModaleOrdreService.svelte';
	import AjoutDocumentContrat from '$lib/components/AjoutDocumentContrat.svelte';
	import PerimetrePicker from '$lib/components/PerimetrePicker.svelte';
	import { onMount } from 'svelte';
	import { prestataires as prestApi, documents as docsApi, ApiError } from '$lib/api';
	import { isCS } from '$lib/stores/auth';
	import RichEditor from '$lib/components/RichEditor.svelte';
	import SectionDiffusion from '$lib/components/SectionDiffusion.svelte';
	import { toast } from '$lib/components/Toast.svelte';
	import { getPageConfig, configStore, siteNomStore, defautsDePage } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';
	import OngletVisites from '$lib/components/OngletVisites.svelte';
	//  🔴 Le vocabulaire des prestataires vit dans `$lib/prestataires.ts`, pas
	//  ici. La table des équipements écrite dans cet écran recopiait
	//  `TypeEquipement` et en OUBLIAIT deux valeurs — `assurance` et `syndic`,
	//  précisément celles que la fiche de copropriété désigne (#553). Et les
	//  deux écrans de reporting, n'y ayant pas accès, affichaient la valeur
	//  brute : `chauffage_collectif`.
	import { EQUIPEMENTS as equipements, TYPES_PRESTATAIRE as typesPrestataire,
		equipLabel, frequenceLabel } from '$lib/prestataires';
	import { fmtDateShort, fmtDayMonth } from '$lib/date';
	import { trackTabView } from '$lib/telemetry';
	import { fmtMontant, perimetreLabel, perimetreDuBatiment, perimetreParDefaut, noeudPerimetre } from '$lib/utils';
	import { cibleDuHash, ongletDeLUrl, revelerCible } from '$lib/deepLink';

	$: _pc = getPageConfig($configStore, 'prestataires', defautsDePage('prestataires'));
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
	// Liste explicite : elle sert aussi à valider le `?onglet=` d'un lien profond
	// (même convention que /calendrier et /sondages, cf. `$lib/deepLink.ts`).
	const ONGLETS = ['prestations', 'visites', 'contrats_tab', 'prestataires', 'consommations'] as const;
	let onglet: (typeof ONGLETS)[number] = 'prestations';
	$: trackTabView(onglet);

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
		perimetre: perimetreParDefaut() ?? '',
		titre: '',
		date_prestation: '',
		montant_estime: '',
		statut: 'en_attente',
		notes: '',
		frequence_type: '',
		frequence_valeur: '',
		affichable: false,
		partager_whatsapp: false,
		envoyer_syndic: false,
		envoyer_cs: false,
	};
	//  Fichiers RETENUS jusqu'à l'enregistrement : ils sont stockés dans le
	//  répertoire privé et servis par une route authentifiée, ils ne peuvent donc
	//  pas partir par l'endpoint générique à la sélection. `FichiersUpload` en
	//  mode différé leur donne l'apparence qu'ils ont partout ailleurs — la
	//  `FileList` et la clé de remontage d'un `<input type="file">` nu, qui les
	//  faisaient ressembler à rien, ont disparu (signalé le 16/08/2026).
	let devisFichiers: File[] = [];

	// ── Devis colonnes kanban (reactive) ──────────────────────
	/*  Les quatre colonnes du kanban des prestations, DÉCRITES une fois (#453).
	    Elles étaient écrites quatre fois dans le balisage — 147 lignes qui ne
	    différaient que par la couleur, le libellé, la liste et les boutons — et
	    elles avaient divergé : l'ordre de service n'était ouvrable que dans deux
	    colonnes sur quatre, et la colonne « Prestataire » ANNONÇAIT un OS qu'elle
	    ne laissait pas ouvrir.

	    C'est le motif que le calendrier emploie déjà pour ses six colonnes
	    (`KANBAN_COLS` + un seul `{#each}`) : il était à un écran de distance. */
	const COLONNES_DEVIS = [
		{ statut: 'en_attente', libelle: '⏳ Syndic', couleur: '#f59e0b' },
		{ statut: 'accepte', libelle: '🔧 Prestataire', couleur: '#f97316' },
		{ statut: 'realise', libelle: '🏁 Réalisé', couleur: '#22c55e' },
		{ statut: 'refuse', libelle: '🚫 Refusé', couleur: '#9ca3af' },
	] as const;

	$: colonnesDevis = COLONNES_DEVIS.map((c) => ({
		...c,
		items: devis.filter((d: any) => d.actif !== false && d.statut === c.statut),
	}));

	// Séparation actifs / réalisés pour la vue liste
	$: devisActifs = devis.filter((d: any) => d.actif !== false && d.statut !== 'realise' && d.statut !== 'refuse');
	$: devisRealises = devis.filter((d: any) => d.actif !== false && d.statut === 'realise');

	// ── Devis OS upload ─────────────────────────────────────────
	let osUploadDevisId: number | null = null;
	let osUploading = false;
	//  Le bâtiment se LIT dans l'arbre (clé étrangère) : le déduire du code supposait
	//  la convention `bat:N` du seed, que l'administration peut ne pas suivre.
	const devisBatimentIdFromPerimetre = (p: string) => noeudPerimetre(p)?.batiment_id ?? null;
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
	//  ⚠️ `contratUploadFile`, `contratUploadTitre`, `uploadingDoc` et
	//  `uploadInputKey` ont disparu avec le bloc dupliqué (#370). Ils étaient
	//  UNIQUES pour toute la page alors que le bloc était affiché à deux endroits :
	//  choisir un fichier dans le formulaire d'édition le faisait apparaître dans
	//  la carte dépliée. Chaque `AjoutDocumentContrat` porte désormais le sien.

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

	// ── Visites : contrats actifs avec fréquence, exercice en cours ──
	$: visites = (() => {
		const year = new Date().getFullYear();
		return contrats.filter(c => c.actif && (c.frequence_type || c.prochaine_visite) && (
			!c.prochaine_visite || new Date(c.prochaine_visite).getFullYear() <= year
		));
	})();
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
	let relevePhotoFichiers: File[] = [];
	//  ⚠️ `relevePhotoKey` a disparu (#370) : la clé de remontage n'existait que
	//  pour vider un `<input type="file">` nu, qu'aucune affectation ne remet à
	//  zéro. `FichiersUpload` se vide en vidant sa liste.
	$: relevePhotoFile = relevePhotoFichiers[0] ?? null;
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
		relevePhotoFichiers = [];
		editReleveId = null;
		showReleveForm = false;
	}

	function startEditReleve(r: any) {
		releveForm = {
			date_releve: r.date_releve,
			index: r.index != null ? String(r.index) : '',
			note: r.note ?? '',
		};
		relevePhotoFichiers = [];
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
		return fmtDayMonth(r.date_releve);
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
			perimetre: perimetreParDefaut() ?? '',
			titre: '',
			date_prestation: '',
			montant_estime: '',
			statut: 'en_attente',
			notes: '',
			frequence_type: '',
			frequence_valeur: '',
			affichable: false,
			partager_whatsapp: false,
			envoyer_syndic: false,
			envoyer_cs: false,
		};
		devisFichiers = [];
		editDevisId = null;
	}


	function closeDevisForm() {
		devisFormPrestId = null;
		editDevisId = null;
		resetDevisForm();
	}

	//  ⚠️ `onOsFileChange` et `osFile` ont disparu avec l'`<input type="file">` nu
	//  (#370) : le fichier retenu appartient à `ModaleOrdreService`, qui le rend
	//  dans son événement `confirmer`. La page n'a plus d'état de saisie à tenir.


	function startEditDevis(d: any, openInModal = false) {
		       devisForm = {
			       copropriete_id: d.copropriete_id,
			       prestataire_id: String(d.prestataire_id),
			       perimetre: d.perimetre ?? perimetreDuBatiment(d.batiment_id),
			       titre: d.titre,
			       date_prestation: d.date_prestation ?? '',
			       montant_estime: d.montant_estime != null ? String(d.montant_estime) : '',
			       statut: d.statut,
			       notes: d.notes ?? '',
			       frequence_type: d.frequence_type ?? '',
			       frequence_valeur: d.frequence_valeur ? String(d.frequence_valeur) : '',
			       affichable: d.affichable ?? false,
			       partager_whatsapp: d.partager_whatsapp ?? false,
			       envoyer_syndic: d.envoyer_syndic ?? false,
			       envoyer_cs: d.envoyer_cs ?? false,
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
			const perimetre = devisForm.perimetre || (perimetreParDefaut() ?? '');
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
				       partager_whatsapp: devisForm.partager_whatsapp,
				       envoyer_syndic: devisForm.envoyer_syndic,
				       envoyer_cs: devisForm.envoyer_cs,
			       };
			let saved: any;
			if (editDevisId) {
				saved = await prestApi.updateDevis(editDevisId, payload);
				devis = devis.map(d => d.id === editDevisId ? saved : d);
			} else {
				saved = await prestApi.createDevis(payload);
				devis = [...devis, saved];
			}
			if (devisFichiers.length > 0) {
				let lastUpdated: any = saved;
				for (const file of devisFichiers) {
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

	async function acceptDevisWithOs(osFile: File | null) {
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
			osUploadDevisId = null; osUploading = false;
		}
	}

	$: orphanContrats = contrats.filter(c => !c.prestataire_id);




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

		// Liens profonds : `?onglet=` pour la vue, `#dv-<id>` / `#presta-<id>` pour l'élément.
		// Cette page a CINQ onglets et s'ouvre sur « Prestations ponctuelles » : une fiche
		// prestataire visée sans onglet restait invisible, l'ancre ne désignant aucun
		// élément rendu (`/prestataires#presta-23`, signalé le 28/07/2026).
		// L'ancre prime sur `?onglet=` : elle est plus précise que la vue demandée.
		const urlOnglet = ongletDeLUrl(ONGLETS);
		if (urlOnglet) onglet = urlOnglet;

		// La vue liste est la seule où chaque élément porte un id — le kanban
		// n'affiche qu'une colonne de statut à la fois.
		const idDevis = cibleDuHash('dv');
		if (idDevis !== null) {
			onglet = 'prestations';
			prestationsVue = 'liste';
			expandedDevis = new Set([...expandedDevis, idDevis]);
			revelerCible(`dv-${idDevis}`);
		}
		const idPresta = cibleDuHash('presta');
		if (idPresta !== null) {
			onglet = 'prestataires';
			expandedPrests = new Set([...expandedPrests, idPresta]);
			revelerCible(`presta-${idPresta}`);
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
		if (prestId) {
			contratForm.prestataire_id = String(prestId);
			const p = prestataires.find(pr => pr.id === prestId);
			if (p?.specialite && p.specialite !== 'autre') contratForm.type_equipement = p.specialite;
		}
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
		contratFormPrestId = -1;
	}

	async function saveContrat() {
		if (!contratForm.libelle || !contratForm.prestataire_id) { toast('error', 'Libellé et prestataire obligatoires'); return; }
		submitting = true;
		// Si l'équipement est "autre", prendre la spécialité du prestataire
		let resolvedType = contratForm.type_equipement;
		if (resolvedType === 'autre' && contratForm.prestataire_id) {
			const p = prestataires.find(pr => pr.id === Number(contratForm.prestataire_id));
			if (p?.specialite && p.specialite !== 'autre') resolvedType = p.specialite;
		}
		const payload = {
			...contratForm,
			type_equipement: resolvedType,
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

	//  L'ENVOI vit dans `AjoutDocumentContrat` ; il ne reste ici que le rechargement
	//  de la liste, qui appartient à la page puisque c'est elle qui l'affiche.
	async function rechargerDocs(contratId: number) {
		contratDocsMap = { ...contratDocsMap, [contratId]: await docsApi.list(undefined, contratId) };
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

<!--  Bascule « + … » ⇆ « ✕ Annuler » portée par `BoutonNouveau` (voir son
      en-tête) ; `alignerSaisie` cale le bouton sur la boîte de 720 px. -->
<EntetePage titre={_pc.titre} icone={_pc.icone || 'hard-hat'}
	alignerSaisie={showPrestForm || devisFormPrestId !== null || contratFormPrestId !== null || showReleveForm}>
	{#if $isCS}
		{#if onglet === 'prestataires'}
			<BoutonNouveau ouvert={showPrestForm} libelle="Nouveau prestataire"
				on:basculer={() => { showPrestForm = !showPrestForm; if (!showPrestForm) resetPrestForm(); }} />
		{:else if onglet === 'prestations'}
			<BoutonNouveau ouvert={devisFormPrestId !== null} libelle="Nouvelle prestation"
				on:basculer={() => { if (devisFormPrestId !== null) closeDevisForm(); else { resetDevisForm(); devisFormPrestId = -1; } }} />
		{:else if onglet === 'contrats_tab'}
			<BoutonNouveau ouvert={contratFormPrestId !== null} libelle="Nouveau contrat"
				on:basculer={() => { if (contratFormPrestId !== null) closeContratForm(); else openAddContrat(); }} />
		{:else if onglet === 'consommations'}
			<BoutonNouveau ouvert={showReleveForm}
				libelle={currentCompteur ? `Nouveau relevé — ${currentCompteur.label}` : 'Nouveau relevé'}
				on:basculer={() => { showReleveForm = !showReleveForm; if (!showReleveForm) resetReleveForm(); }} />
		{/if}
	{/if}
</EntetePage>
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

	<!--  Le formulaire s'affiche AU-DESSUS de la liste, comme sur toutes les autres
	      rubriques (#372). Il était rendu APRÈS elle : sur un onglet qui liste six
	      prestations, on ouvrait un formulaire qu'on ne voyait pas. -->
	{#if devisFormPrestId === -1}
		<FormulaireCreation titre={editDevisId ? 'Modifier la prestation' : 'Nouvelle prestation'}>
			<FormulairePrestation bind:devisForm {prestataires} {statutsDevis} {submitting}
				bind:devisFichiers onSave={saveDevis} />
		</FormulaireCreation>
	{/if}

	{#if prestationsVue === 'kanban'}
		<!-- ── Kanban ─────────────────────────────────── -->
		<div class="kanban devis-kanban">
			{#each colonnesDevis as col (col.statut)}
				<div class="kanban-col">
					<div class="kanban-col-header" style="border-top-color:{col.couleur}">
						<span>{col.libelle}</span>
						<span class="kanban-count">{col.items.length}</span>
					</div>
					{#if col.items.length === 0}
						<p class="kanban-empty">Aucune prestation</p>
					{:else}
						{#each col.items as d (d.id)}
							{@const prestNom = prestataires.find(p => p.id === d.prestataire_id)?.nom ?? '—'}
							<div class="kanban-card card">
								<div class="kanban-card-tags">
									{#if d.frequence_type}<span class="kb-tag" style="background:#6366f1">↺ récurrent</span>{/if}
								</div>
								<span class="kanban-card-prest">{prestNom}</span>
								<strong class="kanban-card-titre">{d.titre}</strong>
								<div class="kanban-card-footer">
									<div class="devis-card-meta">
										{#if d.date_prestation}<span class="devis-date">📅 {fmtDateShort(d.date_prestation)}</span>{/if}
										{#if d.montant_estime != null}<span class="devis-montant">💶 {fmtMontant(d.montant_estime)}</span>{/if}
										<!--  L'ordre de service se montre PARTOUT où il existe, et il s'ouvre.
										     Avant #453, les quatre copies l'affichaient chacune à sa façon : lien
										     dans « Syndic » et « Réalisé », simple tag « 📎 OS joint » — donc NON
										     ouvrable — dans « Prestataire », et rien du tout dans « Refusé ».
										     Le tag a disparu : le lien dit déjà qu'il y a un OS, et lui se clique. -->
										{#if d.os_fichier_url}<a href={d.os_fichier_url} target="_blank" rel="noopener" class="devis-os-link">📎 OS</a>{/if}
									</div>
									{#if $isCS}
										<div class="kanban-card-actions">
											{#if col.statut === 'en_attente'}
												<button class="devis-step-btn devis-step-btn--primary" title="Passer l'OS et transmettre au prestataire"
													on:click={() => { osUploadDevisId = d.id; }}>→ OS</button>
											{:else if col.statut === 'accepte'}
												<button class="devis-step-btn devis-step-btn--success" title="Marquer comme réalisé"
													on:click={() => moveDevisStatut(d.id, 'realise')}>✅</button>
												<button class="devis-step-btn" title="Retour Syndic"
													on:click={() => moveDevisStatut(d.id, 'en_attente')}>←</button>
											{:else if col.statut === 'realise'}
												<button class="devis-step-btn" title="Retour chez le prestataire"
													on:click={() => moveDevisStatut(d.id, 'accepte')}>←</button>
												<button class="devis-step-btn" title="Noter" style="color:#f59e0b"
													on:click={() => openNotationForm(d.prestataire_id, d.id)}>⭐</button>
											{:else}
												<button class="devis-step-btn" title="Remettre en attente syndic"
													on:click={() => moveDevisStatut(d.id, 'en_attente')}>↩</button>
											{/if}
											<button class="btn-icon-edit" title="Modifier" on:click={() => startEditDevis(d, true)}>✏️</button>
											{#if col.statut !== 'realise' && col.statut !== 'refuse'}
												<button class="btn-icon-danger" title="Refuser" on:click={() => moveDevisStatut(d.id, 'refuse')}>❌</button>
											{/if}
										</div>
									{/if}
								</div>
							</div>
						{/each}
					{/if}
				</div>
			{/each}
		</div>
	{:else}
		<!-- ── Vue liste ─────────────────────────────── -->
		{#if devisActifs.length === 0 && devisRealises.length === 0}
			<div class="empty-state card"><h3>Aucune prestation</h3><p>Ajoutez la première via le bouton ci-dessus.</p></div>
		{:else}
			{#each devisActifs as d (d.id)}
				{@const prestNom = prestataires.find(p => p.id === d.prestataire_id)?.nom ?? '—'}
				{@const devisExpanded = expandedDevis.has(d.id)}
				<div class="devis-expand" class:expanded={devisExpanded} id="dv-{d.id}">
					<div class="devis-row"
						role="button" tabindex="0"
						on:click|stopPropagation={() => toggleDevis(d.id)}
						on:keydown|stopPropagation={e => (e.key === 'Enter' || e.key === ' ') && toggleDevis(d.id)}>
						<div class="devis-body-inner">
							<span class="kanban-card-prest">{prestNom}</span>
							<strong class="devis-titre">{d.titre}</strong>
						</div>
						<div class="devis-infos">
							{#if d.date_prestation}
								<span style="font-size:.82rem;font-weight:600;color:var(--color-primary)">📅 {fmtDateShort(d.date_prestation)}</span>
							{/if}
						</div>
						<div class="devis-meta-right">
							<span class="badge" style="font-size:.78rem;color:{statutDevisColor(d.statut)}">{statutDevisLabel(d.statut)}</span>
							{#if d.montant_estime != null}
								<span class="badge badge-gray" style="font-size:.78rem">💶 {fmtMontant(d.montant_estime)}</span>
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
									<label class="field">Titre *<input bind:value={devisForm.titre} required /></label>
									<label class="field">Date de prestation<input type="date" bind:value={devisForm.date_prestation} /></label>
									<label class="field">Montant estimé (€)<input type="number" min="0" step="0.01" bind:value={devisForm.montant_estime} /></label>
									<!--  `titre=""` (§9 septies) et `champ-large` (§9 bis) — les deux manquaient. -->
									<div class="field champ-large" role="group" aria-labelledby="devis-perimetre-titre">
										<span class="libelle-groupe" id="devis-perimetre-titre">Périmètre *</span>
										<PerimetrePicker mode="single" titre=""
											value={devisForm.perimetre ? [devisForm.perimetre] : []}
											on:change={(e) => (devisForm.perimetre = e.detail[0] ?? '')} />
									</div>
									<label class="field">Suivi Kanban
										<select bind:value={devisForm.statut}>
											{#each statutsDevis as s}<option value={s.val}>{s.label}</option>{/each}
										</select>
									</label>
									<label class="field">Fréquence
										<select bind:value={devisForm.frequence_type}>
											<option value=''>— Ponctuelle —</option>
											<option value='fois_par_an'>× / an</option>
											<option value='mois'>Tous les N mois</option>
											<option value='semaines'>Toutes les N semaines</option>
											<option value='ans'>Tous les N ans</option>
										</select>
									</label>
									{#if devisForm.frequence_type}
										<label class="field">Valeur<input type="number" min="1" bind:value={devisForm.frequence_valeur} /></label>
									{/if}
								</div>
								<!--  Les canaux passent par l'OBJET Diffusion (#498) — cet écran était le
								      dernier à le contourner librement. « Afficher dans le tableau de bord »
								      va dans `options` : elle dit ce qui est PUBLIÉ, les canaux qui en est prévenu. -->
								<SectionDiffusion idPrefixe="devis" avecCanaux compact
									bind:whatsapp={devisForm.partager_whatsapp}
									bind:syndic={devisForm.envoyer_syndic} bind:cs={devisForm.envoyer_cs}>
									<svelte:fragment slot="options">
										<label class="case">
											<input type="checkbox" bind:checked={devisForm.affichable} />
											<span>Afficher dans le tableau de bord</span>
										</label>
									</svelte:fragment>
								</SectionDiffusion>
								<div style="margin-top:.5rem">
									<span class="libelle-groupe" id="devis-notes-titre" style="font-weight:600;margin-bottom:.3rem">Notes</span>
									<RichEditor bind:value={devisForm.notes} ariaLabelledby="devis-notes-titre" placeholder="Notes…" minHeight="60px" />
								</div>
								<div style="margin-top:.5rem" role="group" aria-labelledby="devis-fichiers-titre">
									<span class="libelle-groupe" id="devis-fichiers-titre" style="font-weight:600;margin-bottom:.3rem">Fichiers</span>
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
									<FichiersUpload id="devis-edit-fichiers" mode="documents" differe
										titre="" bind:fichiers={devisFichiers} />
								</div>
								<div style="display:flex;gap:.4rem;margin-top:.5rem;flex-wrap:wrap">
									<button class="btn btn-sm btn-outline" on:click|stopPropagation={closeDevisForm}>Annuler</button>
									<button class="btn btn-sm btn-primary" disabled={submitting} on:click|stopPropagation={saveDevis}>{submitting ? '…' : 'Enregistrer'}</button>
								</div>
							{:else}
								<div class="detail-grid">
									<div><span class="detail-label">Périmètre</span>{perimetreLabel(d.perimetre ?? perimetreDuBatiment(d.batiment_id))}</div>
									{#if d.date_prestation}<div><span class="detail-label">Date</span>📅 {fmtDateShort(d.date_prestation)}</div>{/if}
									{#if d.montant_estime != null}<div><span class="detail-label">Montant</span>💶 {fmtMontant(d.montant_estime)}</div>{/if}
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
											<button class="btn btn-sm btn-primary" on:click|stopPropagation={() => { osUploadDevisId = d.id; }}>→ Prestataire</button>
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
							<div class="devis-expand devis-expand--done" class:expanded={devisExpanded} id="dv-{d.id}">
								<div class="devis-row"
									role="button" tabindex="0"
									on:click|stopPropagation={() => toggleDevis(d.id)}
									on:keydown|stopPropagation={e => (e.key === 'Enter' || e.key === ' ') && toggleDevis(d.id)}>
									<div class="devis-body-inner">
										<span class="kanban-card-prest">{prestNom}</span>
										<strong class="devis-titre">{d.titre}</strong>
									</div>
									<div class="devis-infos">
										{#if d.date_prestation}
											<span style="font-size:.82rem;font-weight:600;color:var(--color-text-muted)">📅 {fmtDateShort(d.date_prestation)}</span>
										{/if}
									</div>
									<div class="devis-meta-right">
										<span class="badge" style="font-size:.78rem;color:#7c3aed">🏁 Réalisé</span>
										{#if d.montant_estime != null}
											<span class="badge badge-gray" style="font-size:.78rem">💶 {fmtMontant(d.montant_estime)}</span>
										{/if}
										<span class="toggle-arrow">{devisExpanded ? '▲' : '▼'}</span>
									</div>
								</div>
								{#if devisExpanded}
									<div class="devis-detail-body">
										<div class="detail-grid">
											<div><span class="detail-label">Périmètre</span>{perimetreLabel(d.perimetre ?? perimetreDuBatiment(d.batiment_id))}</div>
											{#if d.date_prestation}<div><span class="detail-label">Date</span>📅 {fmtDateShort(d.date_prestation)}</div>{/if}
											{#if d.montant_estime != null}<div><span class="detail-label">Montant</span>💶 {fmtMontant(d.montant_estime)}</div>{/if}
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

	<!--  🔴 La modale vit dans `ModaleOrdreService.svelte` (#370 et #453) : cette
	      page frôle les 2 000 lignes et le garde-fou de modularité refuse qu'elle
	      grossisse. On sort un OBJET complet plutôt que de comprimer des attributs
	      pour repasser sous le seuil — c'est le contournement que #453 nomme. -->
	<ModaleOrdreService
		devisId={osUploadDevisId}
		envoi={osUploading}
		on:fermer={() => (osUploadDevisId = null)}
		on:confirmer={(e) => acceptDevisWithOs(e.detail)}
	/>

<!-- ══════════════════════════════════════════════════════════════ -->
<!-- ONGLET 2 : VISITES                                           -->
<!-- ══════════════════════════════════════════════════════════════ -->
{:else if onglet === 'visites'}

	<!--  🔴 L'onglet vit dans `OngletVisites.svelte` (#453). Ses deux listes
	      étaient QUARANTE LIGNES RECOPIÉES à deux différences près : elles
	      passent maintenant par `CarteVisite`, écrite une fois.

	      ⚠️ Les données, l'état déplié et les gestes RESTENT ICI : quatre onglets
	      partagent `contrats`, `prestataires` et `expandedContrats`. Déplacer cet
	      état dans le composant en ferait une seconde source. On extrait un
	      RENDU, pas une moitié de logique. -->
	<OngletVisites
		{visites}
		{visitesEnRetard}
		{visitesAJour}
		{prestataires}
		{expandedContrats}
		on:basculer={(e) => toggleContrat(e.detail)}
		on:modifier={(e) => startEditContrat(e.detail)}
		on:noter={(e) => openNotationForm(e.detail.prestataire_id, undefined, e.detail.id)}
	/>
<!-- ══════════════════════════════════════════════════════════════ -->
<!-- ONGLET 3 : CONTRATS                                          -->
<!-- ══════════════════════════════════════════════════════════════ -->
{:else if onglet === 'contrats_tab'}
{#if contratFormPrestId === -1}
	<FormulaireCreation titre={editContratId ? 'Modifier le contrat' : 'Nouveau contrat'}>
			<div>
				<div class="form-grid">
					<label class="field champ-large">Libellé *<input bind:value={contratForm.libelle} required /></label>
					<label class="field">Prestataire *
						<select bind:value={contratForm.prestataire_id} required>
							<option value="">— Sélectionner —</option>
							{#each prestataires as pr}<option value={String(pr.id)}>{pr.nom}</option>{/each}
						</select>
					</label>
					<label class="field">Équipement
						<select bind:value={contratForm.type_equipement}>
							{#each equipements as e}<option value={e.val}>{e.label}</option>{/each}
						</select>
					</label>
					<label class="field">N° contrat<input bind:value={contratForm.numero_contrat} /></label>
					<label class="field">Début *<input type="date" bind:value={contratForm.date_debut} required /></label>
					<label class="field">Durée initiale
						<div style="display:flex;gap:.4rem">
							<input type="number" min="1" placeholder="Ex. 12" bind:value={contratForm.duree_initiale_valeur} style="flex:1" />
							<select bind:value={contratForm.duree_initiale_unite} style="width:auto">
								<option value="mois">mois</option>
								<option value="ans">ans</option>
							</select>
						</div>
					</label>
					<label class="field">Fréquence
						<select bind:value={contratForm.frequence_type}>
							<option value="">— Aucune —</option>
							<option value="semaines">Toutes les X semaines</option>
							<option value="mois">Mensuelle</option>
							<option value="fois_par_an">X fois par an</option>
							<option value="ans">Tous les X ans</option>
						</select>
					</label>
					{#if contratForm.frequence_type === 'semaines'}
						<label class="field">Toutes les … sem.<input type="number" min="1" bind:value={contratForm.frequence_valeur} /></label>
					{:else if contratForm.frequence_type === 'fois_par_an'}
						<label class="field">… fois/an<input type="number" min="1" bind:value={contratForm.frequence_valeur} /></label>
					{:else if contratForm.frequence_type === 'ans'}
						<label class="field">Tous les … ans<input type="number" min="1" bind:value={contratForm.frequence_valeur} /></label>
					{/if}
					<label class="field">Prochaine visite<input type="date" bind:value={contratForm.prochaine_visite} /></label>
				</div>
				<div style="margin-top:.6rem">
					<span class="libelle-groupe" id="contrat-notes-titre" style="font-weight:600;margin-bottom:.3rem">Notes</span>
					<RichEditor bind:value={contratForm.notes} ariaLabelledby="contrat-notes-titre" placeholder="Notes sur le contrat…" minHeight="60px" />
				</div>
				{#if editContratId}
					<div style="margin-top:.8rem">
						<div style="font-size:.85rem;font-weight:600;margin-bottom:.4rem">📄 Documents ({contratDocsMap[editContratId]?.length ?? 0})</div>
						{#if contratDocsMap[editContratId]?.length > 0}
							{#each contratDocsMap[editContratId] as doc}
								<div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.3rem;font-size:.85rem;flex-wrap:wrap">
									<a href={docsApi.downloadUrl(doc.id)} target="_blank">📎 {doc.titre || doc.fichier_nom}</a>
									<span style="font-size:.75rem;color:var(--color-text-muted)">{fmtDateShort(doc.publie_le)}</span>
									<button class="btn-icon-danger" title="Supprimer" style="margin-left:auto" on:click|stopPropagation={() => deleteDoc(editContratId ?? 0, doc.id)}>🗑️</button>
								</div>
							{/each}
						{:else}
							<p style="font-size:.82rem;color:var(--color-text-muted);margin:0">Aucun document.</p>
						{/if}
						<AjoutDocumentContrat
							id="contrat-edit-doc"
							contratId={editContratId ?? 0}
							on:ajoute={() => rechargerDocs(editContratId ?? 0)}
						/>
					</div>
				{/if}
			</div>
			<div class="form-actions">
				<button class="btn btn-primary" disabled={submitting} on:click={saveContrat}>{submitting ? '…' : 'Enregistrer'}</button>
			</div>
	</FormulaireCreation>
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
								<div style="font-size:.82rem;font-weight:600;color:var(--color-primary)">🗓 {fmtDateShort(c.prochaine_visite)}</div>
							{:else}
								<div>📅 {fmtDateShort(c.date_debut)}</div>
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
							{#if editContratId === c.id && contratFormPrestId !== -1}
								<div class="contrat-section">
									<div class="contrat-section-title">Infos contrat</div>
									<div class="form-grid">
										<label class="field">Libellé *<input bind:value={contratForm.libelle} required /></label>
										<label class="field">Prestataire *
											<select bind:value={contratForm.prestataire_id} required>
												<option value="">— Sélectionner —</option>
												{#each prestataires as pr}<option value={String(pr.id)}>{pr.nom}</option>{/each}
											</select>
										</label>
										<label class="field">N° contrat<input bind:value={contratForm.numero_contrat} /></label>
										<label class="field">Début *<input type="date" bind:value={contratForm.date_debut} required /></label>
										<label class="field">Durée initiale
											<div style="display:flex;gap:.4rem">
												<input type="number" min="1" placeholder="Ex. 12" bind:value={contratForm.duree_initiale_valeur} style="flex:1" />
												<select bind:value={contratForm.duree_initiale_unite} style="width:auto">
													<option value="mois">mois</option>
													<option value="ans">ans</option>
												</select>
											</div>
										</label>
										<label class="field">Fréquence
											<select bind:value={contratForm.frequence_type}>
												<option value="">— Aucune —</option>
												<option value="semaines">Toutes les X semaines</option>
												<option value="mois">Mensuelle</option>
												<option value="fois_par_an">X fois par an</option>
												<option value="ans">Tous les X ans</option>
											</select>
										</label>
										{#if contratForm.frequence_type === 'semaines'}
											<label class="field">Toutes les … sem.<input type="number" min="1" bind:value={contratForm.frequence_valeur} /></label>
										{:else if contratForm.frequence_type === 'fois_par_an'}
											<label class="field">… fois/an<input type="number" min="1" bind:value={contratForm.frequence_valeur} /></label>
										{:else if contratForm.frequence_type === 'ans'}
											<label class="field">Tous les … ans<input type="number" min="1" bind:value={contratForm.frequence_valeur} /></label>
										{/if}
										<label class="field">Prochaine visite<input type="date" bind:value={contratForm.prochaine_visite} /></label>
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
												<span style="font-size:.75rem;color:var(--color-text-muted)">{fmtDateShort(doc.publie_le)}</span>
												<button class="btn-icon-danger" title="Supprimer" style="margin-left:auto" on:click|stopPropagation={() => deleteDoc(c.id, doc.id)}>🗑️</button>
											</div>
										{/each}
									{:else}
										<p style="font-size:.82rem;color:var(--color-text-muted);margin:0">Aucun document.</p>
									{/if}
									<AjoutDocumentContrat
										id="contrat-{c.id}-doc"
										contratId={c.id}
										on:ajoute={() => rechargerDocs(c.id)}
									/>
								</div>
								<div style="display:flex;gap:.4rem;margin-top:.25rem;flex-wrap:wrap">
									<button class="btn btn-sm btn-outline" on:click|stopPropagation={() => { editContratId = null; resetContratForm(); }}>Annuler</button>
									<button class="btn btn-sm btn-primary" disabled={submitting} on:click|stopPropagation={saveContrat}>{submitting ? '…' : 'Enregistrer'}</button>
								</div>
							{:else}
								<div class="contrat-section">
									<div class="contrat-section-title">Infos contrat</div>
									<div class="detail-grid">
										<div><span class="detail-label">Date de début</span>📅 {fmtDateShort(c.date_debut)}</div>
										{#if c.duree_initiale_valeur}<div><span class="detail-label">Durée</span>{c.duree_initiale_valeur} {c.duree_initiale_unite}</div>{/if}
										{#if c.frequence_type}
											<div><span class="detail-label">Fréquence</span>{frequenceLabel(c)}</div>
										{/if}
										{#if c.prochaine_visite}<div><span class="detail-label">Prochaine visite</span><span style="color:var(--color-primary);font-weight:600">🗓 {fmtDateShort(c.prochaine_visite)}</span></div>{/if}
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
												<span style="font-size:.75rem;color:var(--color-text-muted)">{fmtDateShort(doc.publie_le)}</span>
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
								<div style="font-size:.82rem;font-weight:600;color:var(--color-primary)">🗓 {fmtDateShort(c.prochaine_visite)}</div>
							{:else}
								<div>📅 {fmtDateShort(c.date_debut)}</div>
							{/if}
						</div>
						<div class="contrat-meta-right">
							<span class="badge" style="font-size:.8rem">📄 {contratDocsMap[c.id]?.length ?? 0}</span>
							<span class="toggle-arrow">{contratExpanded ? '▲' : '▼'}</span>
						</div>
					</div>
					{#if contratExpanded}
						<div class="contrat-detail-body">
							{#if editContratId === c.id && contratFormPrestId !== -1}
								<div class="form-grid" style="margin-bottom:.6rem">
									<label class="field">Libellé *<input bind:value={contratForm.libelle} required /></label>
									<label class="field">Prestataire *
										<select bind:value={contratForm.prestataire_id} required>
											<option value="">— Sélectionner —</option>
											{#each prestataires as pr}<option value={String(pr.id)}>{pr.nom}</option>{/each}
										</select>
									</label>
									<label class="field">N° contrat<input bind:value={contratForm.numero_contrat} /></label>
									<label class="field">Début *<input type="date" bind:value={contratForm.date_debut} required /></label>
									<label class="field">Prochaine visite<input type="date" bind:value={contratForm.prochaine_visite} /></label>
								</div>
								<div style="display:flex;gap:.4rem;margin-top:.6rem;flex-wrap:wrap">
									<button class="btn btn-sm btn-outline" on:click={() => { editContratId = null; resetContratForm(); }}>Annuler</button>
									<button class="btn btn-sm btn-primary" disabled={submitting} on:click={saveContrat}>{submitting ? '…' : 'Enregistrer'}</button>
								</div>
							{:else}
								<div class="contrat-section">
									<div class="contrat-section-title">Infos contrat</div>
									<div class="detail-grid">
										<div><span class="detail-label">Date de début</span>📅 {fmtDateShort(c.date_debut)}</div>
										{#if c.prochaine_visite}<div><span class="detail-label">Prochaine visite</span><span style="color:var(--color-primary);font-weight:600">🗓 {fmtDateShort(c.prochaine_visite)}</span></div>{/if}
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
												<span style="font-size:.75rem;color:var(--color-text-muted)">{fmtDateShort(doc.publie_le)}</span>
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
	<div class="filters filters--defilante">
		<button class="btn btn-sm" class:btn-primary={filtreType === ''} on:click={() => filtreType = ''}>Tous</button>
		{#each typesPrestataire as t}
			<button class="btn btn-sm" class:btn-primary={filtreType === t.val} on:click={() => filtreType = t.val} title={t.desc}>{t.label}</button>
		{/each}
	</div>

	<!-- Filtres par équipement -->
	<div class="filters filters--defilante">
		<button class="btn btn-sm" class:btn-primary={filtreEquipement === ''} on:click={() => filtreEquipement = ''}>Tous équipements</button>
		{#each equipements as e}
			<button class="btn btn-sm" class:btn-primary={filtreEquipement === e.val} on:click={() => filtreEquipement = e.val}>{e.label}</button>
		{/each}
	</div>

	{#if $isCS && showPrestForm}
		<FormulaireCreation titre={editPrestId ? 'Modifier le prestataire' : 'Nouveau prestataire'}>
				<form on:submit|preventDefault={savePrest}>
					<div>
						<div class="form-grid">
							<label class="field">Nom *<input bind:value={prestForm.nom} required /></label>
							<label class="field">Type *
								<select bind:value={prestForm.type_prestataire} required>
									{#each typesPrestataire as t}<option value={t.val}>{t.label}</option>{/each}
								</select>
							</label>
							<label class="field">Spécialité *
								<select bind:value={prestForm.specialite} required>
									<option value="">— Sélectionner —</option>
									{#each equipements as e}<option value={e.val}>{e.label}</option>{/each}
								</select>
							</label>
							<label class="field">Email<input type="email" bind:value={prestForm.email} /></label>
						</div>
						<div style="margin-top:.75rem">
							<div style="font-size:.85rem;font-weight:600;margin-bottom:.35rem">Contact{prestContacts.length > 1 ? 's' : ''}</div>
							{#each prestContacts as contact, i}
								<div style="border:1px solid var(--color-border);border-radius:6px;padding:.6rem;margin-bottom:.5rem;background:var(--color-bg)">
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
					</div>
					<div class="form-actions">
						<button type="button" class="btn btn-outline" on:click={() => { showPrestForm = false; resetPrestForm(); }}>Annuler</button>
						<button class="btn btn-primary" disabled={submitting}>{submitting ? '…' : 'Enregistrer'}</button>
					</div>
				</form>
		</FormulaireCreation>
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
				<div class="prest-expand card" class:expanded id="presta-{p.id}">
					<div class="prest-header"
						role="button" tabindex="0"
						on:click={() => togglePrest(p.id)}
						on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && togglePrest(p.id)}>
						<div class="prest-main">
							<strong class="prest-nom">{p.nom}</strong>
							<span class="badge badge-type" style="margin-left:.5rem">{typeLabel(p.type_prestataire)}</span>
							<span class="badge badge-blue" style="margin-left:.25rem">{equipLabel(p.specialite)}</span>
							{#if avgNote(p.id) !== null}
								<span class="badge" style="margin-left:.25rem;color:#f59e0b;font-size:.82rem" title="{avgNote(p.id)}/5 ({notations.filter(n => n.prestataire_id === p.id).length} avis)">
									{starsDisplay(avgNote(p.id) ?? 0)} {avgNote(p.id)}
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
								{#if nextVisit}<span class="badge" style="font-size:.75rem;color:var(--color-primary)">🗓 {fmtDateShort(nextVisit)}</span>{/if}
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
								{#if nextVisit}<div><span class="detail-label">Prochaine visite</span><span style="color:var(--color-primary);font-weight:600">🗓 {fmtDateShort(nextVisit)}</span></div>{/if}
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

	<div style="margin-bottom:1.25rem">
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
		<FormulaireCreation titre={editReleveId ? 'Modifier le relevé' : currentCompteur ? `Nouveau relevé — ${currentCompteur.label}` : 'Nouveau relevé'}>
				<form on:submit|preventDefault={saveReleve}>
					<div>
						<div class="form-grid">
							<label class="field">Date du relevé *<input type="date" bind:value={releveForm.date_releve} required /></label>
							<label class="field">Index (m³)<input type="number" min="0" bind:value={releveForm.index} placeholder="Ex. 47047" /></label>
						</div>
						<div class="field" style="margin-top:.6rem">
							<label for="releve-note" style="font-size:.875rem;font-weight:500;display:block;margin-bottom:.25rem">Note (optionnel)</label>
							<input id="releve-note" type="text" bind:value={releveForm.note} placeholder="Ex. Changement compteur" style="width:100%" />
						</div>
						<div class="field" style="margin-top:.6rem">
							<span style="font-size:.875rem;font-weight:500;display:block;margin-bottom:.25rem">Photo du relevé (optionnel)</span>
							<!--  Différé : la photo part par `prestApi.uploadRelevePhoto`,
							      une fois le relevé créé. -->
							<FichiersUpload
								id="releve-photo"
								mode="photos"
								differe
								max={1}
								label="Choisir une photo"
								bind:fichiers={relevePhotoFichiers}
							/>
						</div>
					</div>
					<div class="form-actions">
						<button type="button" class="btn btn-outline" on:click={resetReleveForm}>Annuler</button>
						<button type="submit" class="btn btn-primary" disabled={releveSaving}>{releveSaving ? '…' : 'Enregistrer'}</button>
					</div>
				</form>
		</FormulaireCreation>
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

<!-- Modal contrat (global, hors onglets) -->

<!-- Modal notation prestataire (global, hors onglets) -->
{#if showNotationForm}
	<Modale titre="Noter le prestataire" styleBoite="max-width:420px"
		on:fermer={() => { showNotationForm = null; }}>
			<div class="modal-header">
				<h2>⭐ Noter le prestataire</h2>
				<button class="modal-close" on:click={() => { showNotationForm = null; }}>×</button>
			</div>
			<div class="modal-body">
				<div style="text-align:center;margin-bottom:1rem">
					<div style="display:inline-flex;gap:.25rem;font-size:2rem;cursor:pointer">
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
				<label class="field">
					Commentaire (optionnel)
					<textarea bind:value={notationCommentaire} rows="3" style="resize:vertical"></textarea>
				</label>
			</div>
			<div class="modal-footer">
				<button class="btn btn-outline" on:click={() => { showNotationForm = null; }}>Annuler</button>
				<button class="btn btn-primary" disabled={notationNote === 0 || notationSaving} on:click={saveNotation}>{notationSaving ? '…' : 'Enregistrer'}</button>
			</div>
	</Modale>
{/if}

<style>

	/* ── Onglets ── */
	.tabs { display: flex; gap: .25rem; border-bottom: 2px solid var(--color-border); padding-bottom: .1rem; margin-bottom: 1.5rem; overflow-x: auto; scrollbar-width: thin; }
	.tabs button { padding: .45rem .75rem; border: none; background: none; cursor: pointer; font-size: .85rem; color: var(--color-text-muted); border-bottom: 2px solid transparent; margin-bottom: -2px; border-radius: var(--radius) var(--radius) 0 0; white-space: nowrap; display: inline-flex; align-items: center; gap: .3rem; }
	.tabs button:hover { color: var(--color-text); background: var(--color-bg); }
	.tabs button.active { color: var(--color-primary); font-weight: 600; border-bottom-color: var(--color-primary); }

	/* ── Sous-vue toggle ── */
	.sous-vue-toggle { display: flex; gap: .4rem; align-items: center; margin-bottom: 1rem; flex-wrap: wrap; }

	/* ── Compteur config row ── */
	.compteur-config-row { display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; font-size: .82rem; }

	/*  Défilement horizontal : variante NOMMÉE `.filters--defilante` (app.css,
	    #446), lisible dans le balisage. Marge basse .75rem → 1.25rem, la norme. */

	/* Section type header */
	.type-section-header { display: flex; align-items: baseline; gap: .5rem; margin: 1.25rem 0 .5rem; padding-bottom: .3rem; border-bottom: 2px solid var(--color-border); }
	.type-section-header:first-child { margin-top: 0; }
	.type-section-label { font-size: 1rem; font-weight: 700; }
	.type-section-desc { font-size: .82rem; color: var(--color-text-muted); font-style: italic; }

	/* Carte prestataire expansible */
	/*  ⚠️ `overflow: hidden` retiré des trois cartes : il rognait l'infobulle des
	    boutons, posée sous eux donc hors de la carte (#598). */
	.prest-expand { margin-bottom: .5rem; border-left: 4px solid var(--color-border); transition: border-left-color .12s; padding: 0; background: var(--color-surface); box-shadow: 0 1px 2px rgba(30,58,95,.04); border-radius: var(--radius); }
	.prest-expand:hover, .prest-expand.expanded { border-left-color: var(--color-primary); }
	.prest-header { display: flex; align-items: center; gap: .75rem; padding: .85rem 1rem; cursor: pointer; flex-wrap: wrap; }
	.prest-main { display: flex; align-items: center; min-width: 160px; flex-wrap: wrap; gap: .25rem; }
	.prest-nom { font-size: .95rem; }
	.badge-type { background: var(--color-bg-secondary, #f0f0f0); color: var(--color-text); font-size: .75rem; }
	.prest-contacts { display: flex; flex-wrap: wrap; gap: .4rem .75rem; flex: 1; }
	.prest-contact { font-size: .82rem; color: var(--color-text-muted); }
	.prest-meta { display: flex; align-items: center; gap: .4rem; margin-left: auto; }
	.prest-body { padding: .25rem 1rem 1rem 1rem; border-top: 1px solid var(--color-border); }

	/* ── Visites ── */

	/* ── Contrats summary ── */
	.contrats-summary-count { font-size: .85rem; color: var(--color-text-muted); }

	/* Contrat expansible */
	.contrat-expand:hover, .contrat-expand.expanded { border-left-color: var(--color-primary); }

	/* Devis expansible */
	.contrat-expand, .devis-expand { margin-bottom: .5rem; border-left: 4px solid var(--color-border); border-radius: var(--radius); transition: border-left-color .12s; background: var(--color-surface); box-shadow: 0 1px 2px rgba(30,58,95,.04); }
	.devis-expand:hover, .devis-expand.expanded { border-left-color: #7c3aed; }
	.devis-row { display: flex; gap: .75rem; align-items: center; padding: .55rem .75rem; cursor: pointer; transition: background .12s; }
	.devis-row:hover { background: var(--color-bg-secondary, #f8f9fa); }
	.devis-infos { text-align: right; font-size: .82rem; min-width: 90px; flex-shrink: 0; }
	.devis-meta-right { display: flex; align-items: center; gap: .3rem; flex-shrink: 0; }
	.devis-detail-body { padding: .75rem 1rem 1rem; border-top: 1px solid var(--color-border); background: var(--color-bg-secondary, #f8f9fa); }
	.contrat-detail-body { padding: .75rem 1rem 1rem; border-top: 1px solid var(--color-border); background: var(--color-bg-secondary, #f8f9fa); }
	.contrats-summary, .contrat-section { margin-bottom: 1rem; }
	.contrat-section:last-child { margin-bottom: 0; }
	.contrat-section-title { font-size: .75rem; font-weight: 700; text-transform: uppercase; letter-spacing: .05em; color: var(--color-text-muted); margin-bottom: .4rem; padding-bottom: .25rem; border-bottom: 1px solid var(--color-border); }
	.contrat-section-title.clickable { cursor: pointer; user-select: none; }
	.contrat-section-title.clickable:hover { color: var(--color-primary); }

	.contrat-row { display: flex; gap: .75rem; align-items: flex-start; padding: .55rem .75rem; cursor: pointer; transition: background .12s; }
	.contrat-row:hover { background: var(--color-bg-secondary, #f8f9fa); }
	.devis-body-inner, .contrat-body-inner { flex: 1; min-width: 0; }
	.devis-titre, .contrat-titre { font-size: .9rem; }
	.contrat-meta { font-size: .78rem; color: var(--color-text-muted); margin-left: .5rem; }
	.contrat-infos { text-align: right; font-size: .82rem; min-width: 100px; flex-shrink: 0; }
	.contrat-meta-right { display: flex; align-items: flex-start; gap: .3rem; flex-shrink: 0; }


	.form-grid { grid-template-columns: repeat(auto-fit, minmax(min(180px, 100%), 1fr)); gap: .65rem; }
	.form-grid label { display: flex; flex-direction: column; gap: .25rem; font-size: .875rem; }
	.form-grid input, .form-grid select { padding: .4rem .55rem; border: 1px solid var(--color-border); border-radius: var(--radius); font-size: .875rem; background: var(--color-bg); width: 100%; }
	/*  `.devis-form-help` et `.devis-file-note` sont parties avec le formulaire,
	    dans `FormulairePrestation.svelte` — les laisser ici les rendait inertes. */
	.form-actions { display: flex; justify-content: flex-end; gap: .5rem; margin-top: .75rem; }


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
		.tabs button { padding: .4rem .55rem; font-size: .78rem; }
	}

	/* ── Devis kanban ───────────── */
	.devis-kanban { display: flex; gap: .6rem; align-items: flex-start; overflow-x: auto; padding-bottom: .5rem; margin-bottom: 1.5rem; }
	@media (max-width: 900px) { .devis-kanban { flex-direction: column; } .kanban-col { min-width: 100%; } }
	.devis-card-meta { display: flex; flex-direction: column; gap: .1rem; min-width: 0; }
	.devis-montant { font-size: .75rem; color: var(--color-primary); font-weight: 600; }
	.devis-date { font-size: .7rem; color: var(--color-text-muted); }
	.devis-os-link { font-size: .7rem; color: var(--color-primary); }
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
