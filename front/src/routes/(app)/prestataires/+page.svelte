<script lang="ts">
	import BarreFiltres from '$lib/components/BarreFiltres.svelte';
	import Modale from '$lib/components/Modale.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import EntetePage from '$lib/components/EntetePage.svelte';
	import BoutonNouveau from '$lib/components/BoutonNouveau.svelte';
	import FormulaireCreation from '$lib/components/FormulaireCreation.svelte';
	import FichiersUpload from '$lib/components/FichiersUpload.svelte';
	import AjoutDocumentContrat from '$lib/components/AjoutDocumentContrat.svelte';
	import { onMount } from 'svelte';
	import { prestataires as prestApi, documents as docsApi, ApiError } from '$lib/api';
	import { isCS } from '$lib/stores/auth';
	import RichEditor from '$lib/components/RichEditor.svelte';
	import { toast } from '$lib/components/Toast.svelte';
	import { getPageConfig, configStore, siteNomStore, defautsDePage } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';
	//  🔴 Le vocabulaire des prestataires vit dans `$lib/prestataires.ts`, pas
	//  ici. La table des équipements écrite dans cet écran recopiait
	//  `TypeEquipement` et en OUBLIAIT deux valeurs — `assurance` et `syndic`,
	//  précisément celles que la fiche de copropriété désigne (#553). Et les
	//  deux écrans de reporting, n'y ayant pas accès, affichaient la valeur
	//  brute : `chauffage_collectif`.
	import {
		EQUIPEMENTS as equipements,
		TYPES_PRESTATAIRE as typesPrestataire,
		equipLabel,
		frequenceLabel,
	} from '$lib/prestataires';
	import { fmtDateShort, fmtDayMonth } from '$lib/date';
	import { minuitDuJour, typeEquipementDuContrat } from '$lib/reporting';
	import { relire } from '$lib/utils';
	import { trackTabView } from '$lib/telemetry';
	import { cibleDuHash, ongletDeLUrl, revelerCible } from '$lib/deepLink';

	$: _pc = getPageConfig($configStore, 'prestataires', defautsDePage('prestataires'));
	$: _siteNom = $siteNomStore;

	let prestataires: any[] = [];
	let contrats: any[] = [];
	let notations: any[] = [];
	let loading = true;

	// ── Notation ──────────────────────────────────────────────────
	//  ⚠️ La notation SURVIT au retrait des prestations ponctuelles (#603) : elle
	//  se saisit depuis la fiche du prestataire, et son seul rattachement restant
	//  est le CONTRAT. Le rattachement à un devis part avec l'objet qui le portait.
	let showNotationForm: { prestataireId: number; contratId?: number } | null = null;
	let notationNote = 0;
	let notationCommentaire = '';
	let notationSaving = false;
	let notationHover = 0;

	function openNotationForm(prestataireId: number, contratId?: number) {
		showNotationForm = { prestataireId, contratId };
		notationNote = 0;
		notationCommentaire = '';
	}

	async function saveNotation() {
		if (!showNotationForm || notationNote < 1 || notationNote > 5) {
			toast('error', 'Sélectionnez une note entre 1 et 5');
			return;
		}
		notationSaving = true;
		try {
			const n = await prestApi.createNotation({
				prestataire_id: showNotationForm.prestataireId,
				note: notationNote,
				commentaire: notationCommentaire.trim() || undefined,
				contrat_id: showNotationForm.contratId,
			});
			notations = [n, ...notations];
			showNotationForm = null;
			toast('success', 'Notation enregistrée');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			notationSaving = false;
		}
	}

	function avgNote(prestataireId: number): number | null {
		const pn = notations.filter((n) => n.prestataire_id === prestataireId);
		if (pn.length === 0) return null;
		return Math.round((pn.reduce((s: number, n: any) => s + n.note, 0) / pn.length) * 10) / 10;
	}

	function starsDisplay(note: number): string {
		return '★'.repeat(Math.round(note)) + '☆'.repeat(5 - Math.round(note));
	}

	// ── Onglets (3) ────────────────────────────────────────────────
	// Liste explicite : elle sert aussi à valider le `?onglet=` d'un lien profond
	// (même convention que /calendrier et /sondages, cf. `$lib/deepLink.ts`).
	//
	// ⚠️ `'prestations'` et `'visites'` ont disparu (#603). Un lien profond qui les demande encore
	// — un favori, un vieux courriel — n'appartient plus à cette liste, donc
	// `ongletDeLUrl` rend `null` et la page s'ouvre sur son défaut. C'est
	// exactement le service que rend une liste explicite ; une validation par
	// `startsWith` ou par `in` aurait laissé passer un onglet qui n'existe plus.
	//  L'ordre EST celui de la barre ; le DÉFAUT reste « Contrats », 2ᵉ onglet.
	const ONGLETS = ['prestataires', 'contrats_tab', 'consommations'] as const;
	let onglet: (typeof ONGLETS)[number] = 'contrats_tab';
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
	let prestContacts: {
		telephone: string;
		prenom: string;
		nom: string;
		fonction: string;
		email: string;
	}[] = [{ telephone: '', prenom: '', nom: '', fonction: '', email: '' }];
	let submitting = false;

	// ── Contrat form ──────────────────────────────────────────────
	let contratFormPrestId: number | null = null;
	let editContratId: number | null = null;

	let contratForm = {
		copropriete_id: 1,
		batiment_id: '',
		prestataire_id: '',
		type_equipement: 'autre',
		libelle: '',
		numero_contrat: '',
		date_debut: new Date().toISOString().slice(0, 10),
		duree_initiale_valeur: '',
		duree_initiale_unite: 'mois',
		frequence_type: '',
		frequence_valeur: '',
		prochaine_visite: '',
		notes: '',
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

	$: filteredPrests = prestataires.filter(
		(p) =>
			(!filtreEquipement || p.specialite === filtreEquipement) &&
			(!filtreType || p.type_prestataire === filtreType),
	);
	$: compactPrests = filteredPrests.length > 7;

	// ── Échéances des contrats ────────────────────────────────────
	//  🔴 L'onglet « Visites » lisait ces mêmes contrats dans un écran à part
	//  (#603). Une visite n'est pas un objet : c'est la PROCHAINE ÉCHÉANCE d'un
	//  contrat, et elle avait deux définitions qui ne donnaient pas la même
	//  réponse — ici `prochaine_visite`, une date posée à la main ; dans le
	//  calendrier, `frequence_type` réparti sur les mois de l'exercice. Le
	//  décompte reste, l'écran séparé part.
	//
	//  ⚠️ Minuit, pas l'instant ; `contrats` cité pour relire (`utils.relire`).
	$: minuit = relire(contrats, minuitDuJour);
	$: contratEnRetard = (c: any) => !!c.prochaine_visite && new Date(c.prochaine_visite) < minuit;
	$: echeancesEnRetard = contrats.filter(contratEnRetard);
	$: echeancesAVenir = contrats.filter((c) => c.prochaine_visite && !contratEnRetard(c));
	$: contratsSansEcheance = contrats.filter((c) => !c.prochaine_visite);

	/**  Les contrats d'un groupe, la prochaine échéance d'abord.
	 *
	 *   ⚠️ Sans échéance = en FIN de liste, jamais en tête : `null` se compare mal
	 *   et un tri naïf les aurait remontés devant les retards. */
	function parEcheance(liste: any[]): any[] {
		return [...liste].sort((a, b) => {
			if (!a.prochaine_visite && !b.prochaine_visite) return 0;
			if (!a.prochaine_visite) return 1;
			if (!b.prochaine_visite) return -1;
			return a.prochaine_visite < b.prochaine_visite ? -1 : 1;
		});
	}

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

	$: currentCompteur = compteurConfigs.find((c) => c.type_compteur === typeCompteur) ?? null;

	$: relevesByYear = (() => {
		const map = new Map<number, any[]>();
		for (const r of releves) {
			const yr = new Date(r.date_releve).getFullYear();
			if (!map.has(yr)) map.set(yr, []);
			map.get(yr)!.push(r);
		}
		return [...map.entries()].sort((a, b) => b[0] - a[0]);
	})();

	//  🔴 CAS ZÉRO : sans compteur, `compteurConfigs.length === 0` restait vraie
	//  après l'appel et l'onglet rappelait l'API sans fin (#549). Le drapeau dit
	//  « DEMANDÉ », pas « reçu » : posé avant, jamais relevé.
	let compteursDemandes = false;

	async function loadCompteurConfigs() {
		compteursDemandes = true;
		try {
			compteurConfigs = await prestApi.compteurConfigs();
			if (compteurConfigs.length > 0 && !typeCompteur)
				typeCompteur = compteurConfigs[0].type_compteur;
		} catch {
			toast('error', 'Erreur chargement compteurs');
		}
	}

	async function loadReleves() {
		if (!typeCompteur) return;
		releveLoading = true;
		try {
			releves = await prestApi.releves(typeCompteur);
		} catch {
			toast('error', 'Erreur chargement relevés');
		} finally {
			releveLoading = false;
		}
	}

	$: if (onglet === 'consommations' && !compteursDemandes) loadCompteurConfigs();
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
				releves = releves.map((r) => (r.id === editReleveId ? saved : r));
			} else {
				saved = await prestApi.createReleve(payload);
				releves = [saved, ...releves];
			}
			if (relevePhotoFile) {
				try {
					const updated = await prestApi.uploadRelevePhoto(saved.id, relevePhotoFile);
					releves = releves.map((r) => (r.id === saved.id ? updated : r));
				} catch {
					toast('error', 'Photo non enregistrée');
				}
			}
			toast('success', editReleveId ? 'Relevé modifié' : 'Relevé ajouté');
			resetReleveForm();
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			releveSaving = false;
		}
	}

	async function deleteReleve(id: number) {
		if (!confirm('Supprimer ce relevé ?')) return;
		try {
			await prestApi.deleteReleve(id);
			releves = releves.filter((r) => r.id !== id);
			toast('success', 'Relevé supprimé');
		} catch {
			toast('error', 'Erreur');
		}
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
			compteurConfigs = compteurConfigs.map((c) => (c.id === cfg.id ? updated : c));
			editCompteurId = null;
			toast('success', 'Fournisseur mis à jour');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}

	async function addCompteurConfig() {
		if (!newCompteurLabel.trim()) return;
		addCompteurSaving = true;
		const slug = newCompteurLabel
			.trim()
			.toLowerCase()
			.normalize('NFD')
			.replace(/[\u0300-\u036f]/g, '')
			.replace(/[^a-z0-9]+/g, '_')
			.replace(/^_|_$/g, '');
		try {
			const created = await prestApi.createCompteurConfig({
				type_compteur: slug,
				label: newCompteurLabel.trim(),
				ordre: compteurConfigs.length,
			});
			compteurConfigs = [...compteurConfigs, created];
			newCompteurLabel = '';
			showAddCompteur = false;
			typeCompteur = created.type_compteur;
			toast('success', 'Catégorie ajoutée');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			addCompteurSaving = false;
		}
	}

	async function deleteCompteurConfig(cfg: any) {
		if (!confirm(`Supprimer la catégorie « ${cfg.label} » ?`)) return;
		try {
			await prestApi.deleteCompteurConfig(cfg.id);
			compteurConfigs = compteurConfigs.filter((c) => c.id !== cfg.id);
			if (typeCompteur === cfg.type_compteur)
				typeCompteur = compteurConfigs[0]?.type_compteur ?? '';
			toast('success', 'Catégorie supprimée');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}

	function fmtReleve(r: any) {
		return fmtDayMonth(r.date_releve);
	}

	function splitTels(tel: string): string[] {
		return tel.split(',').filter((t) => t.trim());
	}

	function contratsForPrest(prestId: number): any[] {
		return contrats.filter((c) => c.prestataire_id === prestId);
	}

	function typeLabel(v: string) {
		return typesPrestataire.find((t) => t.val === v)?.label ?? v;
	}

	// ── Toggle expand ──────────────────────────────────────────────
	function togglePrest(id: number) {
		if (expandedPrests.has(id)) expandedPrests.delete(id);
		else {
			expandedPrests.clear();
			expandedPrests.add(id);
			expandedContrats.clear();
			expandedNotes.clear();
			expandedContrats = expandedContrats;
			expandedNotes = expandedNotes;
		}
		expandedPrests = expandedPrests;
	}

	function toggleContrat(id: number) {
		if (expandedContrats.has(id)) expandedContrats.delete(id);
		else {
			expandedContrats.clear();
			expandedContrats.add(id);
			expandedNotes.clear();
			expandedNotes = expandedNotes;
		}
		expandedContrats = expandedContrats;
	}

	function nextVisitForPrest(prestId: number): string | null {
		const dates = contrats
			.filter((c) => c.prestataire_id === prestId && c.prochaine_visite)
			.map((c) => c.prochaine_visite as string)
			.sort();
		return dates[0] ?? null;
	}

	onMount(async () => {
		try {
			[prestataires, contrats, notations] = await Promise.all([
				prestApi.list(),
				prestApi.contrats(),
				prestApi.notations(),
			]);
		} catch {
			toast('error', 'Erreur de chargement');
		} finally {
			loading = false;
		}

		if (contrats.length > 0) {
			const results = await Promise.allSettled(
				contrats.map((c) =>
					docsApi.list(undefined, c.id).then((docs: any[]) => ({ id: c.id, docs })),
				),
			);
			const map: Record<number, any[]> = {};
			for (const r of results) {
				if (r.status === 'fulfilled') map[r.value.id] = r.value.docs;
			}
			contratDocsMap = map;
		}

		// Liens profonds : `?onglet=` pour la vue, `#presta-<id>` pour l'élément.
		// Cette page a QUATRE onglets et s'ouvre sur « Contrats » : une fiche
		// prestataire visée sans onglet restait invisible, l'ancre ne désignant aucun
		// élément rendu (`/prestataires#presta-23`, signalé le 28/07/2026).
		// L'ancre prime sur `?onglet=` : elle est plus précise que la vue demandée.
		//
		// ⚠️ L'ancre `#dv-<id>` d'une prestation ponctuelle est partie avec elle
		// (#603). Un lien qui la porte encore ne désigne plus rien : la page
		// s'ouvre sur son défaut, sans erreur — `cibleDuHash` n'est simplement
		// plus interrogé pour ce préfixe.
		const urlOnglet = ongletDeLUrl(ONGLETS);
		if (urlOnglet) onglet = urlOnglet;

		const idPresta = cibleDuHash('presta');
		if (idPresta !== null) {
			onglet = 'prestataires';
			expandedPrests = new Set([...expandedPrests, idPresta]);
			revelerCible(`presta-${idPresta}`);
		}
	});

	function resetPrestForm() {
		prestForm = { nom: '', specialite: '', type_prestataire: 'ponctuel', email: '' };
		prestContacts = [{ telephone: '', prenom: '', nom: '', fonction: '', email: '' }];
		editPrestId = null;
	}
	function startEditPrest(p: any) {
		prestForm = {
			nom: p.nom,
			specialite: p.specialite ?? '',
			type_prestataire: p.type_prestataire ?? 'ponctuel',
			email: p.email ?? '',
		};
		if (p.contacts && p.contacts.length > 0) {
			prestContacts = p.contacts.map((c: any) => ({
				telephone: c.telephone ?? '',
				prenom: c.prenom ?? '',
				nom: c.nom ?? '',
				fonction: c.fonction ?? '',
				email: c.email ?? '',
			}));
		} else {
			prestContacts = p.telephone
				? p.telephone
						.split(',')
						.filter((t: string) => t.trim())
						.map((t: string) => ({
							telephone: t.trim(),
							prenom: '',
							nom: '',
							fonction: '',
							email: '',
						}))
				: [{ telephone: '', prenom: '', nom: '', fonction: '', email: '' }];
		}
		if (prestContacts.length === 0)
			prestContacts = [{ telephone: '', prenom: '', nom: '', fonction: '', email: '' }];
		editPrestId = p.id;
		showPrestForm = true;
		window.scrollTo({ top: 0, behavior: 'smooth' });
	}

	async function savePrest() {
		if (!prestForm.nom || !prestForm.specialite) {
			toast('error', 'Nom et spécialité obligatoires');
			return;
		}
		const contacts = prestContacts.filter((c) => c.telephone.trim());
		const telephone = contacts.map((c) => c.telephone.trim()).join(',') || null;
		submitting = true;
		try {
			if (editPrestId) {
				await prestApi.update(editPrestId, { ...prestForm, telephone, contacts });
			} else {
				await prestApi.create({ ...prestForm, telephone, contacts });
			}
			prestataires = await prestApi.list();
			showPrestForm = false;
			resetPrestForm();
			toast('success', editPrestId ? 'Prestataire modifié' : 'Prestataire ajouté');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			submitting = false;
		}
	}

	async function deletePrest(id: number) {
		if (!confirm('Archiver ce prestataire ?')) return;
		try {
			await prestApi.delete(id);
			prestataires = prestataires.filter((p) => p.id !== id);
			toast('success', 'Archivé');
		} catch {
			toast('error', 'Erreur');
		}
	}

	function resetContratForm() {
		contratForm = {
			copropriete_id: 1,
			batiment_id: '',
			prestataire_id: '',
			type_equipement: 'autre',
			libelle: '',
			numero_contrat: '',
			date_debut: new Date().toISOString().slice(0, 10),
			duree_initiale_valeur: '',
			duree_initiale_unite: 'mois',
			frequence_type: '',
			frequence_valeur: '',
			prochaine_visite: '',
			notes: '',
		};
		editContratId = null;
	}

	function openAddContrat(prestId?: number) {
		resetContratForm();
		if (prestId) {
			contratForm.prestataire_id = String(prestId);
			const p = prestataires.find((pr) => pr.id === prestId);
			if (p?.specialite && p.specialite !== 'autre') contratForm.type_equipement = p.specialite;
		}
		contratFormPrestId = prestId ?? -1;
		editContratId = null;
	}

	function closeContratForm() {
		contratFormPrestId = null;
		resetContratForm();
	}

	function startEditContrat(c: any) {
		contratForm = {
			copropriete_id: c.copropriete_id,
			batiment_id: c.batiment_id ?? '',
			prestataire_id: String(c.prestataire_id ?? ''),
			type_equipement: typeEquipementDuContrat(c, prestataires),
			libelle: c.libelle,
			numero_contrat: c.numero_contrat ?? '',
			date_debut: c.date_debut,
			duree_initiale_valeur: c.duree_initiale_valeur ?? '',
			duree_initiale_unite: c.duree_initiale_unite ?? 'mois',
			frequence_type: c.frequence_type ?? '',
			frequence_valeur: c.frequence_valeur ?? '',
			prochaine_visite: c.prochaine_visite ?? '',
			notes: c.notes ?? '',
		};
		editContratId = c.id;
		contratFormPrestId = -1;
	}

	async function saveContrat() {
		if (!contratForm.libelle || !contratForm.prestataire_id) {
			toast('error', 'Libellé et prestataire obligatoires');
			return;
		}
		submitting = true;
		//  La règle vit dans `reporting.ts` — elle était écrite ici, dans le
		//  groupement des cartes et dans le chargement du formulaire, avec trois
		//  résultats différents sur le même contrat (29/08/2026).
		const resolvedType = typeEquipementDuContrat(
			{ ...contratForm, prestataire_id: Number(contratForm.prestataire_id) },
			prestataires,
		);
		const payload = {
			...contratForm,
			type_equipement: resolvedType,
			batiment_id: contratForm.batiment_id ? Number(contratForm.batiment_id) : null,
			prestataire_id: Number(contratForm.prestataire_id),
			duree_initiale_valeur: contratForm.duree_initiale_valeur
				? Number(contratForm.duree_initiale_valeur)
				: null,
			duree_initiale_unite: contratForm.duree_initiale_valeur
				? contratForm.duree_initiale_unite
				: null,
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
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			submitting = false;
		}
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
		} catch {
			toast('error', 'Erreur');
		}
	}

	async function deleteContrat(id: number) {
		if (!confirm('Archiver ce contrat ?')) return;
		try {
			await prestApi.deleteContrat(id);
			contrats = contrats.filter((c) => c.id !== id);
			toast('success', 'Archivé');
		} catch {
			toast('error', 'Erreur');
		}
	}
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<!--  Bascule « + … » ⇆ « ✕ Annuler » portée par `BoutonNouveau` (voir son
      en-tête) ; `alignerSaisie` cale le bouton sur la boîte de 720 px. -->
<EntetePage
	titre={_pc.titre}
	icone={_pc.icone || 'hard-hat'}
	alignerSaisie={showPrestForm || contratFormPrestId !== null || showReleveForm}
>
	{#if $isCS}
		{#if onglet === 'prestataires'}
			<BoutonNouveau
				ouvert={showPrestForm}
				libelle="Nouveau prestataire"
				on:basculer={() => {
					showPrestForm = !showPrestForm;
					if (!showPrestForm) resetPrestForm();
				}}
			/>
		{:else if onglet === 'contrats_tab'}
			<BoutonNouveau
				ouvert={contratFormPrestId !== null}
				libelle="Nouveau contrat"
				on:basculer={() => {
					if (contratFormPrestId !== null) closeContratForm();
					else openAddContrat();
				}}
			/>
		{:else if onglet === 'consommations'}
			<BoutonNouveau
				ouvert={showReleveForm}
				libelle={currentCompteur ? `Nouveau relevé — ${currentCompteur.label}` : 'Nouveau relevé'}
				on:basculer={() => {
					showReleveForm = !showReleveForm;
					if (!showReleveForm) resetReleveForm();
				}}
			/>
		{/if}
	{/if}
</EntetePage>
<div class="page-subtitle">{@html safeHtml(_pc.descriptif)}</div>

<!-- ── Onglets ─────────────────────────────────────────────────── -->
<div class="tabs" role="tablist">
	<button
		role="tab"
		class:active={onglet === 'prestataires'}
		on:click={() => (onglet = 'prestataires')}
	>
		<Icon name="hard-hat" size={15} /> Prestataires
	</button>
	<button
		role="tab"
		class:active={onglet === 'contrats_tab'}
		on:click={() => (onglet = 'contrats_tab')}
	>
		<Icon name="file-text" size={15} /> Contrats
	</button>
	<button
		role="tab"
		class:active={onglet === 'consommations'}
		on:click={() => (onglet = 'consommations')}
	>
		💧 Consommations
	</button>
</div>

{#if loading}
	<p style="color:var(--color-text-muted)">Chargement…</p>

	<!-- ══════════════════════════════════════════════════════════════ -->
	<!-- ONGLET 3 : CONTRATS                                          -->
	<!-- ══════════════════════════════════════════════════════════════ -->
{:else if onglet === 'contrats_tab'}
	{#if contratFormPrestId === -1}
		<FormulaireCreation
			cle={editContratId}
			titre={editContratId ? 'Modifier le contrat' : 'Nouveau contrat'}
		>
			<div>
				<div class="form-grid">
					<label class="field champ-large"
						>Libellé *<input bind:value={contratForm.libelle} required /></label
					>
					<label class="field"
						>Prestataire *
						<select bind:value={contratForm.prestataire_id} required>
							<option value="">— Sélectionner —</option>
							{#each prestataires as pr}<option value={String(pr.id)}>{pr.nom}</option>{/each}
						</select>
					</label>
					<label class="field"
						>Équipement
						<select bind:value={contratForm.type_equipement}>
							{#each equipements as e}<option value={e.val}>{e.label}</option>{/each}
						</select>
					</label>
					<label class="field">N° contrat<input bind:value={contratForm.numero_contrat} /></label>
					<label class="field"
						>Début *<input type="date" bind:value={contratForm.date_debut} required /></label
					>
					<label class="field"
						>Durée initiale
						<div style="display:flex;gap:.4rem">
							<input
								type="number"
								min="1"
								placeholder="Ex. 12"
								bind:value={contratForm.duree_initiale_valeur}
								style="flex:1"
							/>
							<select bind:value={contratForm.duree_initiale_unite} style="width:auto">
								<option value="mois">mois</option>
								<option value="ans">ans</option>
							</select>
						</div>
					</label>
					<label class="field"
						>Fréquence
						<select bind:value={contratForm.frequence_type}>
							<option value="">— Aucune —</option>
							<option value="semaines">Toutes les X semaines</option>
							<option value="mois">Mensuelle</option>
							<option value="fois_par_an">X fois par an</option>
							<option value="ans">Tous les X ans</option>
						</select>
					</label>
					{#if contratForm.frequence_type === 'semaines'}
						<label class="field"
							>Toutes les … sem.<input
								type="number"
								min="1"
								bind:value={contratForm.frequence_valeur}
							/></label
						>
					{:else if contratForm.frequence_type === 'fois_par_an'}
						<label class="field"
							>… fois/an<input
								type="number"
								min="1"
								bind:value={contratForm.frequence_valeur}
							/></label
						>
					{:else if contratForm.frequence_type === 'ans'}
						<label class="field"
							>Tous les … ans<input
								type="number"
								min="1"
								bind:value={contratForm.frequence_valeur}
							/></label
						>
					{/if}
					<label class="field"
						>Prochaine visite<input type="date" bind:value={contratForm.prochaine_visite} /></label
					>
				</div>
				<div style="margin-top:.6rem">
					<span
						class="libelle-groupe"
						id="contrat-notes-titre"
						style="font-weight:600;margin-bottom:.3rem">Notes</span
					>
					<RichEditor
						bind:value={contratForm.notes}
						ariaLabelledby="contrat-notes-titre"
						placeholder="Notes sur le contrat…"
						minHeight="60px"
					/>
				</div>
				{#if editContratId}
					<div style="margin-top:.8rem">
						<div style="font-size:.85rem;font-weight:600;margin-bottom:.4rem">
							📄 Documents ({contratDocsMap[editContratId]?.length ?? 0})
						</div>
						{#if contratDocsMap[editContratId]?.length > 0}
							{#each contratDocsMap[editContratId] as doc}
								<div
									style="display:flex;align-items:center;gap:.5rem;margin-bottom:.3rem;font-size:.85rem;flex-wrap:wrap"
								>
									<a href={docsApi.downloadUrl(doc.id)} target="_blank"
										>📎 {doc.titre || doc.fichier_nom}</a
									>
									<span style="font-size:.75rem;color:var(--color-text-muted)"
										>{fmtDateShort(doc.publie_le)}</span
									>
									<button
										class="btn-icon-danger"
										title="Supprimer"
										style="margin-left:auto"
										on:click|stopPropagation={() => deleteDoc(editContratId ?? 0, doc.id)}
										>🗑️</button
									>
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
				<button type="button" class="btn btn-outline" on:click={closeContratForm}>Annuler</button>
				<button class="btn btn-primary" disabled={submitting} on:click={saveContrat}
					>{submitting ? 'Enregistrement…' : 'Enregistrer'}</button
				>
			</div>
		</FormulaireCreation>
	{/if}

	<!--  Synthèse — les trois décomptes viennent de l'onglet « Visites » retiré
	      (#603). Ils portent sur les MÊMES contrats qu'il lisait ; ils sont
	      seulement rendus là où vivent les contrats. -->
	<div class="contrats-summary">
		<span class="contrats-summary-count"
			>{contrats.length} contrat{contrats.length !== 1 ? 's' : ''} actif{contrats.length !== 1
				? 's'
				: ''}</span
		>
		{#if echeancesEnRetard.length > 0}
			<span class="badge echeance-badge echeance-badge--retard"
				>⚠️ {echeancesEnRetard.length} visite{echeancesEnRetard.length > 1 ? 's' : ''} en retard</span
			>
		{/if}
		{#if echeancesAVenir.length > 0}
			<span class="badge echeance-badge echeance-badge--ok">🗓 {echeancesAVenir.length} à venir</span
			>
		{/if}
		{#if contratsSansEcheance.length > 0}
			<span class="badge echeance-badge">{contratsSansEcheance.length} sans échéance</span>
		{/if}
	</div>

	<!-- Groupé par spécialité du prestataire -->
	{#if contrats.length === 0}
		<div class="empty-state card">
			<h3>Aucun contrat</h3>
			<p>Ajoutez le premier contrat via le bouton ci-dessus.</p>
		</div>
	{:else}
		{#each equipements.filter( (e) => contrats.some((c) => typeEquipementDuContrat(c, prestataires) === e.val) ) as specGroup (specGroup.val)}
			<div class="type-section-header">
				<span class="type-section-label">{specGroup.label}</span>
			</div>
			{#each parEcheance(contrats.filter((c) => typeEquipementDuContrat(c, prestataires) === specGroup.val)) as c (c.id)}
				{@const prest = prestataires.find((p) => p.id === c.prestataire_id)}
				{@const contratExpanded = expandedContrats.has(c.id)}
				{@const enRetard = contratEnRetard(c)}
				<div class="carte-liste" class:expanded={contratExpanded} class:urgent={enRetard}>
					<div
						class="contrat-row"
						role="button"
						tabindex="0"
						on:click|stopPropagation={() => toggleContrat(c.id)}
						on:keydown|stopPropagation={(e) => e.key === 'Enter' && toggleContrat(c.id)}
					>
						<div class="contrat-body-inner">
							<strong class="contrat-titre">{c.libelle}</strong>
							{#if prest}
								<span class="contrat-meta">— {prest.nom}</span>
							{:else}
								<!--  Un contrat sans intervenant avait sa propre section, qui le
								      rendait une SECONDE fois : le groupement par équipement
								      retombe déjà sur `type_equipement` quand le prestataire
								      manque. Le fait se dit ici, sur la ligne (#603). -->
								<span class="badge badge-gray" style="font-size:.72rem">sans intervenant</span>
							{/if}
							{#if c.numero_contrat}<span class="contrat-meta">🔖 {c.numero_contrat}</span>{/if}
						</div>
						<div class="contrat-infos">
							{#if c.prochaine_visite}
								<div class="contrat-echeance" class:contrat-echeance--retard={enRetard}>
									{enRetard ? '⚠️' : '🗓'}
									{fmtDateShort(c.prochaine_visite)}
								</div>
							{:else}
								<div>📅 {fmtDateShort(c.date_debut)}</div>
							{/if}
							{#if c.frequence_type}
								<span class="badge badge-blue" style="font-size:.75rem">{frequenceLabel(c)}</span>
							{/if}
						</div>
						<div class="contrat-meta-right">
							<span class="badge" style="font-size:.8rem"
								>📄 {contratDocsMap[c.id]?.length ?? 0}</span
							>
							{#if $isCS}
								<button
									class="btn-icon-danger"
									title="Archiver"
									on:click|stopPropagation={() => deleteContrat(c.id)}>🗑️</button
								>
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
										<label class="field"
											>Libellé *<input bind:value={contratForm.libelle} required /></label
										>
										<label class="field"
											>Prestataire *
											<select bind:value={contratForm.prestataire_id} required>
												<option value="">— Sélectionner —</option>
												{#each prestataires as pr}<option value={String(pr.id)}>{pr.nom}</option
													>{/each}
											</select>
										</label>
										<label class="field"
											>N° contrat<input bind:value={contratForm.numero_contrat} /></label
										>
										<label class="field"
											>Début *<input
												type="date"
												bind:value={contratForm.date_debut}
												required
											/></label
										>
										<label class="field"
											>Durée initiale
											<div style="display:flex;gap:.4rem">
												<input
													type="number"
													min="1"
													placeholder="Ex. 12"
													bind:value={contratForm.duree_initiale_valeur}
													style="flex:1"
												/>
												<select bind:value={contratForm.duree_initiale_unite} style="width:auto">
													<option value="mois">mois</option>
													<option value="ans">ans</option>
												</select>
											</div>
										</label>
										<label class="field"
											>Fréquence
											<select bind:value={contratForm.frequence_type}>
												<option value="">— Aucune —</option>
												<option value="semaines">Toutes les X semaines</option>
												<option value="mois">Mensuelle</option>
												<option value="fois_par_an">X fois par an</option>
												<option value="ans">Tous les X ans</option>
											</select>
										</label>
										{#if contratForm.frequence_type === 'semaines'}
											<label class="field"
												>Toutes les … sem.<input
													type="number"
													min="1"
													bind:value={contratForm.frequence_valeur}
												/></label
											>
										{:else if contratForm.frequence_type === 'fois_par_an'}
											<label class="field"
												>… fois/an<input
													type="number"
													min="1"
													bind:value={contratForm.frequence_valeur}
												/></label
											>
										{:else if contratForm.frequence_type === 'ans'}
											<label class="field"
												>Tous les … ans<input
													type="number"
													min="1"
													bind:value={contratForm.frequence_valeur}
												/></label
											>
										{/if}
										<label class="field"
											>Prochaine visite<input
												type="date"
												bind:value={contratForm.prochaine_visite}
											/></label
										>
									</div>
								</div>
								<div class="contrat-section">
									<div class="contrat-section-title">Notes</div>
									<RichEditor
										bind:value={contratForm.notes}
										placeholder="Notes…"
										minHeight="60px"
									/>
								</div>
								<div class="contrat-section">
									<div class="contrat-section-title">
										📄 Documents ({contratDocsMap[c.id]?.length ?? 0})
									</div>
									{#if contratDocsMap[c.id]?.length > 0}
										{#each contratDocsMap[c.id] as doc}
											<div
												style="display:flex;align-items:center;gap:.5rem;margin-bottom:.3rem;font-size:.85rem;flex-wrap:wrap"
											>
												<a href={docsApi.downloadUrl(doc.id)} target="_blank"
													>📎 {doc.titre || doc.fichier_nom}</a
												>
												<span style="font-size:.75rem;color:var(--color-text-muted)"
													>{fmtDateShort(doc.publie_le)}</span
												>
												<button
													class="btn-icon-danger"
													title="Supprimer"
													style="margin-left:auto"
													on:click|stopPropagation={() => deleteDoc(c.id, doc.id)}>🗑️</button
												>
											</div>
										{/each}
									{:else}
										<p style="font-size:.82rem;color:var(--color-text-muted);margin:0">
											Aucun document.
										</p>
									{/if}
									<AjoutDocumentContrat
										id="contrat-{c.id}-doc"
										contratId={c.id}
										on:ajoute={() => rechargerDocs(c.id)}
									/>
								</div>
								<div style="display:flex;gap:.4rem;margin-top:.25rem;flex-wrap:wrap">
									<button
										class="btn btn-sm btn-outline"
										on:click|stopPropagation={() => {
											editContratId = null;
											resetContratForm();
										}}>Annuler</button
									>
									<button
										class="btn btn-sm btn-primary"
										disabled={submitting}
										on:click|stopPropagation={saveContrat}
										>{submitting ? 'Enregistrement…' : 'Enregistrer'}</button
									>
								</div>
							{:else}
								<div class="contrat-section">
									<div class="contrat-section-title">Infos contrat</div>
									<div class="detail-grid">
										<div>
											<span class="detail-label">Date de début</span>📅 {fmtDateShort(c.date_debut)}
										</div>
										{#if c.duree_initiale_valeur}<div>
												<span class="detail-label">Durée</span>{c.duree_initiale_valeur}
												{c.duree_initiale_unite}
											</div>{/if}
										{#if c.frequence_type}
											<div><span class="detail-label">Fréquence</span>{frequenceLabel(c)}</div>
										{/if}
										{#if c.prochaine_visite}<div>
												<span class="detail-label">Prochaine visite</span><span
													style="color:var(--color-primary);font-weight:600"
													>🗓 {fmtDateShort(c.prochaine_visite)}</span
												>
											</div>{/if}
									</div>
								</div>
								{#if c.notes}
									<div class="contrat-section">
										<div
											class="contrat-section-title clickable"
											role="button"
											tabindex="0"
											on:click|stopPropagation={() => {
												expandedNotes.has(c.id)
													? expandedNotes.delete(c.id)
													: expandedNotes.add(c.id);
												expandedNotes = expandedNotes;
											}}
											on:keydown|stopPropagation={(e) =>
												(e.key === 'Enter' || e.key === ' ') &&
												(expandedNotes.has(c.id)
													? expandedNotes.delete(c.id)
													: expandedNotes.add(c.id),
												(expandedNotes = expandedNotes))}
										>
											Synthèse du ou des contrats {expandedNotes.has(c.id) ? '▲' : '▼'}
										</div>
										{#if expandedNotes.has(c.id)}
											<div class="rich-content" style="font-size:.875rem">
												{@html safeHtml(c.notes)}
											</div>
										{/if}
									</div>
								{/if}
								<div class="contrat-section">
									<div class="contrat-section-title">
										📄 Documents ({contratDocsMap[c.id]?.length ?? 0})
									</div>
									{#if contratDocsMap[c.id]?.length > 0}
										{#each contratDocsMap[c.id] as doc}
											<div
												style="display:flex;align-items:center;gap:.5rem;margin-bottom:.3rem;font-size:.85rem;flex-wrap:wrap"
											>
												<a href={docsApi.downloadUrl(doc.id)} target="_blank"
													>📎 {doc.titre || doc.fichier_nom}</a
												>
												<span style="font-size:.75rem;color:var(--color-text-muted)"
													>{fmtDateShort(doc.publie_le)}</span
												>
												{#if $isCS}
													<button
														class="btn-icon-danger"
														title="Supprimer"
														style="margin-left:auto"
														on:click|stopPropagation={() => deleteDoc(c.id, doc.id)}>🗑️</button
													>
												{/if}
											</div>
										{/each}
									{:else}
										<p style="font-size:.82rem;color:var(--color-text-muted);margin:0">
											Aucun document.
										</p>
									{/if}
								</div>
								{#if $isCS}
									<div style="display:flex;gap:.4rem;margin-top:.25rem;flex-wrap:wrap">
										<button
											class="btn btn-sm btn-outline"
											on:click|stopPropagation={() => startEditContrat(c)}>✏️ Modifier</button
										>
										<!--  🔴 « Noter » ne vivait QUE dans `CarteVisite`, donc dans le
										      seul onglet Visites : retirer cet onglet sans porter le geste
										      ici aurait rendu la notation d'un prestataire IMPOSSIBLE à
										      saisir, alors que la fiche et le reporting continuaient d'en
										      afficher la moyenne. Un affichage sans son geste de saisie ne
										      se voit pas — rien ne lève, la note reste simplement à jamais
										      celle d'hier (#603).
										      Sans intervenant, il n'y a personne à noter : le bouton
										      n'apparaît pas plutôt que d'ouvrir une modale sans cible. -->
										{#if c.prestataire_id}
											<button
												class="btn btn-sm btn-outline contrat-noter"
												on:click|stopPropagation={() => openNotationForm(c.prestataire_id, c.id)}
												>⭐ Noter</button
											>
										{/if}
									</div>
								{/if}
							{/if}
						</div>
					{/if}
				</div>
			{/each}
		{/each}
	{/if}

	<!-- ══════════════════════════════════════════════════════════════ -->
	<!-- ONGLET 4 : PRESTATAIRES (annuaire)                           -->
	<!-- ══════════════════════════════════════════════════════════════ -->
{:else if onglet === 'prestataires'}
	<!--  Deux rangées, UN motif : `BarreFiltres` le porte (#491). Il était écrit
	      deux fois ici, à trois mots près — la duplication la plus discrète, celle
	      qu'aucun contrôle inter-fichiers ne voit.
	      `avecDetail` sur les types seuls : leur description vivait dans un `title`,
	      donc invisible au tactile. Les douze équipements n'en portent pas. -->
	<BarreFiltres
		options={typesPrestataire}
		bind:valeur={filtreType}
		avecDetail
		libelle="Filtrer par type de prestataire"
	/>
	<BarreFiltres
		options={equipements}
		bind:valeur={filtreEquipement}
		tous="Tous équipements"
		libelle="Filtrer par équipement"
	/>

	{#if $isCS && showPrestForm}
		<FormulaireCreation
			cle={editPrestId}
			titre={editPrestId ? 'Modifier le prestataire' : 'Nouveau prestataire'}
		>
			<form on:submit|preventDefault={savePrest}>
				<div>
					<div class="form-grid">
						<label class="field">Nom *<input bind:value={prestForm.nom} required /></label>
						<label class="field"
							>Type *
							<select bind:value={prestForm.type_prestataire} required>
								{#each typesPrestataire as t}<option value={t.val}>{t.label}</option>{/each}
							</select>
						</label>
						<label class="field"
							>Spécialité *
							<select bind:value={prestForm.specialite} required>
								<option value="">— Sélectionner —</option>
								{#each equipements as e}<option value={e.val}>{e.label}</option>{/each}
							</select>
						</label>
						<label class="field">Email<input type="email" bind:value={prestForm.email} /></label>
					</div>
					<div style="margin-top:.75rem">
						<div style="font-size:.85rem;font-weight:600;margin-bottom:.35rem">
							Contact{prestContacts.length > 1 ? 's' : ''}
						</div>
						{#each prestContacts as _contact, i}
							<div
								style="border:1px solid var(--color-border);border-radius:6px;padding:.6rem;margin-bottom:.5rem;background:var(--color-bg)"
							>
								<div style="display:flex;gap:.4rem;flex-wrap:wrap;margin-bottom:.35rem">
									<input
										style="flex:2;min-width:140px"
										bind:value={prestContacts[i].telephone}
										placeholder="Téléphone *"
									/>
									<input
										style="flex:1;min-width:100px"
										bind:value={prestContacts[i].prenom}
										placeholder="Prénom"
									/>
									<input
										style="flex:1;min-width:100px"
										bind:value={prestContacts[i].nom}
										placeholder="Nom"
									/>
								</div>
								<div style="display:flex;gap:.4rem;flex-wrap:wrap;align-items:center">
									<input
										style="flex:1;min-width:120px"
										bind:value={prestContacts[i].fonction}
										placeholder="Fonction"
									/>
									<input
										style="flex:1;min-width:140px"
										type="email"
										bind:value={prestContacts[i].email}
										placeholder="Email"
									/>
									{#if prestContacts.length > 1}
										<button
											type="button"
											class="btn btn-sm btn-outline"
											style="color:#dc2626;border-color:#dc2626;flex-shrink:0"
											on:click={() => (prestContacts = prestContacts.filter((_, j) => j !== i))}
											>−</button
										>
									{/if}
								</div>
							</div>
						{/each}
						<button
							type="button"
							class="btn btn-sm btn-outline"
							on:click={() =>
								(prestContacts = [
									...prestContacts,
									{ telephone: '', prenom: '', nom: '', fonction: '', email: '' },
								])}>+ Nouveau contact</button
						>
					</div>
				</div>
				<div class="form-actions">
					<button
						type="button"
						class="btn btn-outline"
						on:click={() => {
							showPrestForm = false;
							resetPrestForm();
						}}>Annuler</button
					>
					<button class="btn btn-primary" disabled={submitting}
						>{submitting ? 'Enregistrement…' : 'Enregistrer'}</button
					>
				</div>
			</form>
		</FormulaireCreation>
	{/if}

	{#if filteredPrests.length === 0}
		<div class="empty-state card">
			<h3>Aucun prestataire{filtreEquipement || filtreType ? ' pour ces critères' : ''}</h3>
		</div>
	{:else}
		{#each typesPrestataire.filter( (t) => filteredPrests.some((p) => p.type_prestataire === t.val) ) as typeGroup (typeGroup.val)}
			{#if !filtreType}
				<div class="type-section-header">
					<span class="type-section-label">{typeGroup.label}</span>
					<span class="type-section-desc">{typeGroup.desc}</span>
				</div>
			{/if}
			{#each filteredPrests.filter((p) => p.type_prestataire === typeGroup.val) as p (p.id)}
				{@const expanded = expandedPrests.has(p.id)}
				{@const cs = contratsForPrest(p.id)}
				{@const nextVisit = nextVisitForPrest(p.id)}
				<div class="carte-liste" class:expanded id="presta-{p.id}">
					<div
						class="prest-header"
						role="button"
						tabindex="0"
						on:click={() => togglePrest(p.id)}
						on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && togglePrest(p.id)}
					>
						<div class="prest-main">
							<strong class="prest-nom">{p.nom}</strong>
							<span class="badge badge-type" style="margin-left:.5rem"
								>{typeLabel(p.type_prestataire)}</span
							>
							<span class="badge badge-blue" style="margin-left:.25rem"
								>{equipLabel(p.specialite)}</span
							>
							{#if avgNote(p.id) !== null}
								<span
									class="badge"
									style="margin-left:.25rem;color:#f59e0b;font-size:.82rem"
									title="{avgNote(p.id)}/5 ({notations.filter((n) => n.prestataire_id === p.id)
										.length} avis)"
								>
									{starsDisplay(avgNote(p.id) ?? 0)}
									{avgNote(p.id)}
								</span>
							{/if}
						</div>
						{#if !compactPrests || expanded}
							<div class="prest-contacts">
								{#if p.contacts && p.contacts.length > 0}
									{#each p.contacts as c}
										<span class="prest-contact">
											📞 {c.telephone}{#if c.prenom || c.nom}&nbsp;— {c.prenom ?? ''}
												{c.nom ?? ''}{/if}{#if c.fonction}&nbsp;({c.fonction}){/if}
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
								<span class="badge badge-gray">{cs.length} contrat{cs.length !== 1 ? 's' : ''}</span
								>
								{#if nextVisit}<span
										class="badge"
										style="font-size:.75rem;color:var(--color-primary)"
										>🗓 {fmtDateShort(nextVisit)}</span
									>{/if}
							{/if}
							{#if $isCS}
								<button
									class="btn-icon-edit"
									title="Modifier"
									on:click|stopPropagation={() => startEditPrest(p)}>✏️</button
								>
								<button
									class="btn-icon-danger"
									title="Archiver"
									on:click|stopPropagation={() => deletePrest(p.id)}>🗑️</button
								>
							{/if}
							<span class="toggle-arrow">{expanded ? '▲' : '▼'}</span>
						</div>
					</div>
					{#if expanded}
						<div class="prest-body">
							<div class="detail-grid">
								{#if p.telephone}
									<div>
										<span class="detail-label">Téléphone</span>
										{#each splitTels(p.telephone) as tel}
											<span style="display:block">📞 {tel.trim()}</span>
										{/each}
									</div>
								{/if}
								{#if p.email}<div><span class="detail-label">Email</span>✉️ {p.email}</div>{/if}
								<div><span class="detail-label">Contrats</span>{cs.length}</div>
								{#if nextVisit}<div>
										<span class="detail-label">Prochaine visite</span><span
											style="color:var(--color-primary);font-weight:600"
											>🗓 {fmtDateShort(nextVisit)}</span
										>
									</div>{/if}
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
				<button
					class="btn btn-sm"
					class:btn-primary={typeCompteur === cfg.type_compteur}
					on:click={() => {
						typeCompteur = cfg.type_compteur;
					}}
				>
					{cfg.label}
				</button>
			{/each}
			{#if $isCS}
				<button
					class="btn btn-sm btn-outline"
					on:click={() => {
						showAddCompteur = !showAddCompteur;
						newCompteurLabel = '';
					}}
					title="Ajouter une catégorie">+ Catégorie</button
				>
			{/if}
		</div>

		{#if currentCompteur && $isCS}
			<div class="compteur-config-row" style="margin-top:.6rem">
				{#if editCompteurId === currentCompteur.id}
					<span style="font-size:.82rem;color:var(--color-text-muted)">Fournisseur :</span>
					<select
						bind:value={editCompteurPrestId}
						style="font-size:.82rem;padding:.2rem .4rem;border:1px solid var(--color-border);border-radius:var(--radius);background:var(--color-bg)"
					>
						<option value="">— Aucun —</option>
						{#each prestataires as p}<option value={String(p.id)}>{p.nom}</option>{/each}
					</select>
					<button class="btn btn-sm btn-outline" on:click={() => (editCompteurId = null)}
						>Annuler</button
					>
					<button
						class="btn btn-sm btn-primary"
						on:click={() => saveCompteurPrestataire(currentCompteur)}>Enregistrer</button
					>
					{#if compteurConfigs.length > 1}
						<button
							class="btn btn-sm btn-outline"
							style="color:var(--color-danger);border-color:var(--color-danger);margin-left:auto"
							on:click={() => deleteCompteurConfig(currentCompteur)}>🗑️</button
						>
					{/if}
				{:else}
					{@const prest = currentCompteur.prestataire_id
						? prestataires.find((p) => p.id === currentCompteur.prestataire_id)
						: null}
					{#if prest}
						<span class="badge badge-blue" style="font-size:.78rem">🔧 {prest.nom}</span>
					{:else}
						<span style="font-size:.78rem;color:var(--color-text-muted)">Aucun fournisseur</span>
					{/if}
					<button
						class="btn-icon-edit"
						title="Modifier le fournisseur"
						on:click={() => startEditCompteur(currentCompteur)}>✏️</button
					>
				{/if}
			</div>
		{/if}

		{#if showAddCompteur && $isCS}
			<div style="display:flex;gap:.5rem;align-items:center;margin-top:.5rem;flex-wrap:wrap">
				<input
					type="text"
					bind:value={newCompteurLabel}
					placeholder="Ex. EDF Parking privé"
					style="flex:1;min-width:180px;font-size:.875rem;padding:.35rem .55rem;border:1px solid var(--color-border);border-radius:var(--radius);background:var(--color-bg)"
				/>
				<button
					class="btn btn-sm btn-primary"
					disabled={addCompteurSaving || !newCompteurLabel.trim()}
					on:click={addCompteurConfig}>{addCompteurSaving ? '…' : 'Ajouter'}</button
				>
				<button class="btn btn-sm btn-outline" on:click={() => (showAddCompteur = false)}
					>Annuler</button
				>
			</div>
		{/if}
	</div>

	{#if showReleveForm && $isCS}
		<FormulaireCreation
			cle={editReleveId}
			titre={editReleveId
				? 'Modifier le relevé'
				: currentCompteur
					? `Nouveau relevé — ${currentCompteur.label}`
					: 'Nouveau relevé'}
		>
			<form on:submit|preventDefault={saveReleve}>
				<div>
					<div class="form-grid">
						<label class="field"
							>Date du relevé *<input
								type="date"
								bind:value={releveForm.date_releve}
								required
							/></label
						>
						<label class="field"
							>Index (m³)<input
								type="number"
								min="0"
								bind:value={releveForm.index}
								placeholder="Ex. 47047"
							/></label
						>
					</div>
					<div class="field" style="margin-top:.6rem">
						<label
							for="releve-note"
							style="font-size:.875rem;font-weight:500;display:block;margin-bottom:.25rem"
							>Note (optionnel)</label
						>
						<input
							id="releve-note"
							type="text"
							bind:value={releveForm.note}
							placeholder="Ex. Changement compteur"
							style="width:100%"
						/>
					</div>
					<div class="field" style="margin-top:.6rem">
						<span style="font-size:.875rem;font-weight:500;display:block;margin-bottom:.25rem"
							>Photo du relevé (optionnel)</span
						>
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
					<button type="submit" class="btn btn-primary" disabled={releveSaving}
						>{releveSaving ? 'Enregistrement…' : 'Enregistrer'}</button
					>
				</div>
			</form>
		</FormulaireCreation>
	{/if}

	{#if releveLoading}
		<p style="color:var(--color-text-muted)">Chargement…</p>
	{:else if releves.length === 0}
		<div class="empty-state card">
			<h3>Aucun relevé</h3>
			<p>Ajoutez le premier relevé via le bouton ci-dessus.</p>
		</div>
	{:else}
		{#each relevesByYear as [year, yearReleves] (year)}
			<h2 class="releve-year">{year}</h2>
			{#each yearReleves as r (r.id)}
				<div class="releve-row">
					<div class="releve-main">
						<span class="releve-date">Relevé {fmtReleve(r)}</span>
						{#if r.note}<span class="releve-note">{r.note}</span>{/if}
						{#if r.index != null}
							<span class="releve-index"
								>Index : <strong>{r.index.toLocaleString('fr-FR')}</strong></span
							>
						{/if}
						{#if r.photo_url}
							<a href={r.photo_url} target="_blank" rel="noopener">
								<img src={r.photo_url} alt="Relevé de compteur" class="releve-photo-thumb" />
							</a>
						{/if}
					</div>
					{#if $isCS}
						<div class="releve-actions">
							<button class="btn-icon-edit" title="Modifier" on:click={() => startEditReleve(r)}
								>✏️</button
							>
							<button class="btn-icon-danger" title="Supprimer" on:click={() => deleteReleve(r.id)}
								>🗑️</button
							>
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
	<Modale
		titre="⭐ Noter le prestataire"
		styleBoite="max-width:420px"
		on:fermer={() => {
			showNotationForm = null;
		}}
	>
		<div class="modal-body">
			<div style="text-align:center;margin-bottom:1rem">
				<div style="display:inline-flex;gap:.25rem;font-size:2rem;cursor:pointer">
					{#each [1, 2, 3, 4, 5] as s}
						<button
							type="button"
							class="star-btn"
							class:active={notationNote >= s}
							style="background:none;border:none;cursor:pointer;font-size:2rem;color:{notationNote >=
							s
								? '#f59e0b'
								: '#d1d5db'};transition:color .15s"
							on:click={() => (notationNote = s)}
							on:mouseenter={() => (notationHover = s)}
							on:mouseleave={() => (notationHover = 0)}
						>
							{(notationHover || notationNote) >= s ? '★' : '☆'}
						</button>
					{/each}
				</div>
				{#if notationNote > 0}<p
						style="margin:.25rem 0 0;font-size:.9rem;color:var(--color-text-muted)"
					>
						{notationNote}/5
					</p>{/if}
			</div>
			<label class="field">
				Commentaire (optionnel)
				<textarea bind:value={notationCommentaire} rows="3" style="resize:vertical"></textarea>
			</label>
		</div>
		<div class="modal-footer">
			<button
				class="btn btn-outline"
				on:click={() => {
					showNotationForm = null;
				}}>Annuler</button
			>
			<button
				class="btn btn-primary"
				disabled={notationNote === 0 || notationSaving}
				on:click={saveNotation}>{notationSaving ? '…' : 'Enregistrer'}</button
			>
		</div>
	</Modale>
{/if}

<style>
	/* ── Onglets ── */
	.tabs {
		padding-bottom: 0.1rem;
		overflow-x: auto;
		scrollbar-width: thin;
	} /* le reste : charte (#607) */
	.tabs button {
		padding: 0.45rem 0.75rem;
		border: none;
		background: none;
		cursor: pointer;
		font-size: 0.85rem;
		color: var(--color-text-muted);
		border-bottom: 2px solid transparent;
		margin-bottom: -2px;
		border-radius: var(--radius) var(--radius) 0 0;
		white-space: nowrap;
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
	}
	/*  `:hover` et `.active` viennent de la charte (#491) : cet écran ne garde
	    que son ÉCART — des onglets à icône, plus compacts, qui tiennent sur
	    une ligne. Les redéfinir à l'identique ne servait à rien. */

	/* ── Sous-vue toggle ── */

	/* ── Compteur config row ── */
	.compteur-config-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
		font-size: 0.82rem;
	}

	/*  Défilement horizontal : variante NOMMÉE `.filters--defilante` (app.css,
	    #446), lisible dans le balisage. Marge basse .75rem → 1.25rem, la norme. */

	/* Section type header */
	.type-section-header {
		display: flex;
		align-items: baseline;
		gap: 0.5rem;
		margin: 1.25rem 0 0.5rem;
		padding-bottom: 0.3rem;
		border-bottom: 2px solid var(--color-border);
	}
	.type-section-header:first-child {
		margin-top: 0;
	}
	.type-section-label {
		font-size: 1rem;
		font-weight: 700;
	}
	.type-section-desc {
		font-size: 0.82rem;
		color: var(--color-text-muted);
		font-style: italic;
	}

	/* Carte prestataire expansible */
	/*  ⚠️ `overflow: hidden` retiré des trois cartes : il rognait l'infobulle des
	    boutons, posée sous eux donc hors de la carte (#598). */
	/*  `.carte-liste` depuis le 28/08/2026 (#598) : la carte combinait `.card`
	    et en ANNULAIT le remplissage — ce que la norme donne sans annuler. */
	.prest-header {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.85rem 1rem;
		cursor: pointer;
		flex-wrap: wrap;
	}
	.prest-main {
		display: flex;
		align-items: center;
		min-width: 160px;
		flex-wrap: wrap;
		gap: 0.25rem;
	}
	.prest-nom {
		font-size: 0.95rem;
	}
	.badge-type {
		background: var(--color-bg-secondary, #f0f0f0);
		color: var(--color-text);
		font-size: 0.75rem;
	}
	.prest-contacts {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem 0.75rem;
		flex: 1;
	}
	.prest-contact {
		font-size: 0.82rem;
		color: var(--color-text-muted);
	}
	.prest-meta {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		margin-left: auto;
	}
	.prest-body {
		padding: 0.25rem 1rem 1rem 1rem;
		border-top: 1px solid var(--color-border);
	}

	/* ── Visites ── */

	/* ── Contrats summary ── */
	.contrats-summary {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.contrats-summary-count {
		font-size: 0.85rem;
		color: var(--color-text-muted);
	}

	/*  Les trois décomptes d'échéance, repris de l'onglet « Visites » retiré. */
	.echeance-badge {
		font-size: 0.78rem;
	}
	.echeance-badge--retard {
		color: var(--color-danger);
		border-color: var(--color-danger);
	}
	.echeance-badge--ok {
		color: var(--color-primary);
		border-color: var(--color-primary);
	}

	/*  Contrat expansible — `.carte-liste` depuis le 28/08/2026 (#598). Il en
	    recomposait la définition avec un espacement, une ombre et un `position`
	    différents, et l'accent de retard redisait `.carte-liste.urgent`, à un
	    `!important` près que l'ordre de la charte rend inutile. */
	.contrat-echeance {
		font-size: 0.82rem;
		font-weight: 600;
		color: var(--color-primary);
	}
	.contrat-echeance--retard {
		color: var(--color-danger);
	}
	.contrat-noter {
		color: #f59e0b;
	}

	.contrat-detail-body {
		padding: 0.75rem 1rem 1rem;
		border-top: 1px solid var(--color-border);
		background: var(--color-bg-secondary, #f8f9fa);
	}
	.contrats-summary,
	.contrat-section {
		margin-bottom: 1rem;
	}
	.contrat-section:last-child {
		margin-bottom: 0;
	}
	.contrat-section-title {
		font-size: 0.75rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-text-muted);
		margin-bottom: 0.4rem;
		padding-bottom: 0.25rem;
		border-bottom: 1px solid var(--color-border);
	}
	.contrat-section-title.clickable {
		cursor: pointer;
		user-select: none;
	}
	.contrat-section-title.clickable:hover {
		color: var(--color-primary);
	}

	.contrat-row {
		display: flex;
		gap: 0.75rem;
		align-items: flex-start;
		padding: 0.55rem 0.75rem;
		cursor: pointer;
		transition: background 0.12s;
	}
	.contrat-row:hover {
		background: var(--color-bg-secondary, #f8f9fa);
	}
	.contrat-body-inner {
		flex: 1;
		min-width: 0;
	}
	.contrat-titre {
		font-size: 0.9rem;
	}
	.contrat-meta {
		font-size: 0.78rem;
		color: var(--color-text-muted);
		margin-left: 0.5rem;
	}
	.contrat-infos {
		text-align: right;
		font-size: 0.82rem;
		min-width: 100px;
		flex-shrink: 0;
	}
	.contrat-meta-right {
		display: flex;
		align-items: flex-start;
		gap: 0.3rem;
		flex-shrink: 0;
	}

	/*  Seuls la répartition et l'espacement : la peau des contrôles est partie
	    le 28/08/2026 — le pourquoi vit dans `check-styles-nus.mjs`, volet C. */
	.form-grid {
		grid-template-columns: repeat(auto-fit, minmax(min(180px, 100%), 1fr));
		gap: 0.65rem;
	}

	.rich-content {
		font-size: 0.85rem;
		line-height: 1.6;
		color: var(--color-text);
		margin-bottom: 0.5rem;
	}
	.rich-content :global(p) {
		margin: 0 0 0.5em;
	}
	.rich-content :global(ul),
	.rich-content :global(ol) {
		padding-left: 1.4em;
		margin: 0 0 0.5em;
	}
	.rich-content :global(strong) {
		font-weight: 600;
	}
	.rich-content :global(em) {
		font-style: italic;
	}

	/* Relevés compteurs */
	.releve-year {
		font-size: 1.1rem;
		font-weight: 700;
		margin: 1.25rem 0 0.6rem;
		padding-bottom: 0.3rem;
		border-bottom: 2px solid var(--color-border);
	}
	.releve-row {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 0.75rem;
		padding: 0.6rem 0.9rem;
		border-left: 3px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
		margin-bottom: 0.3rem;
		transition: border-color 0.12s;
	}
	.releve-row:hover {
		border-left-color: var(--color-primary);
	}
	.releve-main {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
	}
	.releve-date {
		font-size: 0.9rem;
		font-weight: 600;
	}
	.releve-note {
		font-size: 0.82rem;
		color: var(--color-text-muted);
		font-style: italic;
	}
	.releve-index {
		font-size: 0.875rem;
	}
	.releve-actions {
		display: flex;
		gap: 0.25rem;
		flex-shrink: 0;
	}
	.releve-photo-thumb {
		width: 56px;
		height: 56px;
		object-fit: cover;
		border-radius: var(--radius);
		border: 1px solid var(--color-border);
		margin-top: 0.2rem;
		display: block;
	}

	@media (max-width: 600px) {
		.prest-header {
			gap: 0.5rem;
		}
		.contrat-infos {
			min-width: 80px;
		}
		.tabs button {
			padding: 0.4rem 0.55rem;
			font-size: 0.78rem;
		}
	}
</style>
