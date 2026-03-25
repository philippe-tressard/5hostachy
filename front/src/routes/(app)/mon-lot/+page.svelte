<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import { onMount } from 'svelte';
	import { lots as lotsApi, bailleur as bailApi, ApiError } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { currentUser, isAdmin, isCS } from '$lib/stores/auth';
	import { getPageConfig, configStore, siteNomStore } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';
	import RichEditor from '$lib/components/RichEditor.svelte';

	$: _pc = getPageConfig($configStore, 'mon-lot', { titre: 'Mes lots', navLabel: 'Mes lots', icone: 'door-closed', descriptif: "Informations sur votre bien : situation de vos lots (appartement, cave & parkings) dans la résidence.", onglets: { lots: { label: '\u{1F3E0} Mes lots', descriptif: 'Situation de vos lots dans la résidence : appartements, caves et parkings.' }, location: { label: '\u{1F4CB} Gestion locative', descriptif: 'Suivi de vos baux, locataires et documents de gestion locative.' } } });
	$: _siteNom = $siteNomStore;
	$: isBailleur = $currentUser?.statut === 'copropriétaire_bailleur';
	$: isResident = $currentUser?.statut === 'copropriétaire_résident';

	// ── Onglet principal ───────────────────────────────────────────────────────
	type MainTab = 'lots' | 'location';
	let mainTab: MainTab = 'lots';

	// ── Types ──────────────────────────────────────────────────────────────────
	interface LotDetail {
		id: number;
		numero: string;
		type: string;
		type_appartement: string | null;
		superficie: number | null;
		etage: number | null;
		batiment_id: number;
		batiment_nom: string | null;
	}

	interface Objet {
		id: number;
		bail_id: number;
		type: string;
		libelle: string;
		quantite: number;
		reference: string | null;
		statut: string;
		remis_le: string | null;
		rendu_le: string | null;
		notes: string | null;
		cree_le: string;
	}

	interface Bail {
		id: number;
		lot_id: number;
		locataire_id: number | null;
		locataire_nom: string | null;
		locataire_prenom: string | null;
		locataire_email: string | null;
		locataire_telephone: string | null;
		date_entree: string;
		date_sortie_prevue: string | null;
		date_sortie_reelle: string | null;
		statut: string;
		notes: string | null;
		objets: Objet[];
	}

	interface Acces {
		id: number;
		code: string;
		type: 'vigik' | 'telecommande';
		lot_id: number | null;
		lot_type: 'appartement' | 'parking' | 'cave' | string | null;
		lot_label: string | null;
		statut: string;
		chez_locataire: boolean;
		bail_id: number | null;
		eligible_transfert: boolean;
		recommande: boolean;
		motif_non_eligible: string | null;
		cree_le: string;
	}

	// ── State (locataire bail) ────────────────────────────────────────────────
	let monBailData: any = null;
	$: isLocataire = $currentUser?.statut === 'locataire';

	// ── State (lots) ──────────────────────────────────────────────────────────
	let lots: LotDetail[] = [];
	let loading = true;
	let selectedLotId: number | null = null;

	$: selectedLot = lots.find((l) => l.id === selectedLotId) ?? null;
	$: bailAccesLot = bailAcces
		? lots.find((l) => l.id === (bailAcces?.lot_id ?? -1)) ?? null
		: null;

	// ── State (gestion locative) ──────────────────────────────────────────────
	let baux: Bail[] = [];
	let bauxLoading = true;
	let bailTab: 'actif' | 'historique' = 'actif';

	// Nouveau bail
	let showNewBail = false;
	let newBailLotIds = new Set<number>();
	let newBail = { locataire_nom: '', locataire_prenom: '', locataire_email: '', locataire_telephone: '', date_entree: '', date_sortie_prevue: '', notes: '' };
	let savingBail = false;
	let rechercheLocataire = '';
	let locataireTrouve: { id: number; nom: string; prenom: string; email: string; actif: boolean } | null = null;
	let locataireResultats: { id: number; nom: string; prenom: string; email: string; actif: boolean }[] = [];
	let locataireRechercheFaite = false;
	let cherchantLocataire = false;
	let newBailLocataireId: number | null = null;

	// Terminer bail
	let bailATerminer: Bail | null = null;
	let dateSortie = '';

	// Supprimer bail (admin)
	let bailASupprimer: Bail | null = null;

	// Retour objet
	let objetRetour: Objet | null = null;
	let retourDate = '';
	let retourPerdu = false;

	// Edition locataire
	let bailEdite: Bail | null = null;
	let editLocataire = { locataire_nom: '', locataire_prenom: '', locataire_email: '', locataire_telephone: '', date_sortie_prevue: '', notes: '' };
	let editLocataireId: number | null = null;
	// Recherche / suggestions dans le modal d'édition
	let editRechercheLocataire = '';
	let editCherchant = false;
	let editLocataireResultats: { id: number; nom: string; prenom: string; email: string; actif: boolean }[] = [];
	let editLocataireRechercheFaite = false;
	let editLocataireTrouve: { id: number; nom: string; prenom: string; email: string; actif: boolean } | null = null;
	let editSuggestions: { id: number; nom: string; prenom: string; email: string; actif: boolean }[] = [];
	let editSuggestionsLoaded = false;

	// Gestion des accès (Vigik / TC) par bail
	let bailAcces: Bail | null = null;
	let accesListe: Acces[] = [];
	let loadingAcces = false;
	let selectionVigik = new Set<number>();
	let selectionTc = new Set<number>();
	let filtreLotsAcces = new Set<number>();

	// ── Derived ────────────────────────────────────────────────────────────────
	$: bauxActifs = baux.filter((b) => b.statut === 'actif' || b.statut === 'en_cours_sortie');
	$: bauxTermines = baux.filter((b) => b.statut === 'termine');

	// ── Init ───────────────────────────────────────────────────────────────────
	onMount(async () => {
		try {
			lots = await lotsApi.mesList();
			if (lots.length > 0) selectedLotId = lots[0].id;
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Impossible de charger vos lots');
		} finally {
			loading = false;
		}
		if ($currentUser?.statut === 'locataire') {
			try {
				monBailData = await bailApi.monBail();
			} catch { /* pas de bail */ }
		}
		if ($currentUser?.statut === 'copropriétaire_bailleur' || isResident) {
			try {
				baux = await bailApi.mesBaux();
			} catch (e: any) {
				toast('error', e instanceof ApiError ? e.message : 'Erreur de chargement des baux');
			} finally {
				bauxLoading = false;
			}
		} else if ($isAdmin || $isCS) {
			try {
				baux = await bailApi.tousBaux();
			} catch (e: any) {
				toast('error', e instanceof ApiError ? e.message : 'Erreur de chargement des baux');
			} finally {
				bauxLoading = false;
			}
		} else {
			bauxLoading = false;
		}
	});

	// ── Actions bail ───────────────────────────────────────────────────────────
	async function creerBail() {
		if (newBailLotIds.size === 0 || !newBail.date_entree) {
			toast('error', 'Sélectionnez au moins un lot et renseignez la date d\'entrée');
			return;
		}
		savingBail = true;
		try {
			const nouvellesBaux = await bailApi.creerBailMulti({
				lot_ids: [...newBailLotIds],
				...newBail,
				locataire_id: newBailLocataireId ?? null,
				date_sortie_prevue: newBail.date_sortie_prevue || null,
			});
			baux = [...nouvellesBaux, ...baux];
			showNewBail = false;
			newBailLotIds = new Set();
			newBail = { locataire_nom: '', locataire_prenom: '', locataire_email: '', locataire_telephone: '', date_entree: '', date_sortie_prevue: '', notes: '' };
			rechercheLocataire = '';
			locataireTrouve = null;
			locataireResultats = [];
			locataireRechercheFaite = false;
			newBailLocataireId = null;
			toast('success', nouvellesBaux.length > 1 ? `${nouvellesBaux.length} baux créés` : 'Bail créé');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			savingBail = false;
		}
	}

	async function confirmerTerminer() {
		if (!bailATerminer) return;
		try {
			const updated = await bailApi.terminerBail(bailATerminer.id, { date_sortie_reelle: dateSortie || null });
			baux = baux.map((b) => (b.id === updated.id ? updated : b));
			bailATerminer = null;
			toast('success', 'Bail terminé');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}

	async function confirmerSupprimer() {
		if (!bailASupprimer) return;
		try {
			await bailApi.supprimerBail(bailASupprimer.id);
			baux = baux.filter((b) => b.id !== bailASupprimer!.id);
			bailASupprimer = null;
			toast('success', 'Bail supprimé');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}

	function ouvrirEditionLocataire(bail: Bail) {
		bailEdite = bail;
		editLocataireId = bail.locataire_id ?? null;
		editLocataire = {
			locataire_nom: bail.locataire_nom ?? '',
			locataire_prenom: bail.locataire_prenom ?? '',
			locataire_email: bail.locataire_email ?? '',
			locataire_telephone: bail.locataire_telephone ?? '',
			date_sortie_prevue: bail.date_sortie_prevue ?? '',
			notes: bail.notes ?? '',
		};
		editLocataireTrouve = bail.locataire_id ? { id: bail.locataire_id, nom: bail.locataire_nom ?? '', prenom: bail.locataire_prenom ?? '', email: bail.locataire_email ?? '', actif: true } : null;
		editRechercheLocataire = '';
		editLocataireResultats = [];
		editLocataireRechercheFaite = false;
		if (!editSuggestionsLoaded) {
			bailApi.locatairesSuggeres().then(r => { editSuggestions = r; editSuggestionsLoaded = true; }).catch(() => {});
		}
	}

	function editSelectionnerLocataire(l: { id: number; nom: string; prenom: string; email: string; actif: boolean }) {
		editLocataireTrouve = l;
		editLocataireId = l.id;
		editLocataire.locataire_nom = l.nom;
		editLocataire.locataire_prenom = l.prenom;
		editLocataire.locataire_email = l.email;
		editLocataireResultats = [];
		editRechercheLocataire = '';
	}

	function editDissocierLocataire() {
		editLocataireTrouve = null;
		editLocataireId = null;
	}

	async function editChercherLocataire() {
		if (!editRechercheLocataire.trim()) return;
		editCherchant = true;
		editLocataireTrouve = null;
		editLocataireId = null;
		editLocataireResultats = [];
		try {
			const results = await bailApi.searchLocataire(editRechercheLocataire.trim());
			editLocataireRechercheFaite = true;
			if (results.length === 1) {
				editSelectionnerLocataire(results[0]);
			} else {
				editLocataireResultats = results;
			}
		} catch {
			editLocataireRechercheFaite = true;
		} finally {
			editCherchant = false;
		}
	}

	async function sauvegarderLocataire() {
		if (!bailEdite) return;
		try {
			const updated = await bailApi.updateBail(bailEdite.id, {
				...editLocataire,
				date_sortie_prevue: editLocataire.date_sortie_prevue || null,
				locataire_id: editLocataireId ?? null,
			});
			baux = baux.map((b) => (b.id === updated.id ? { ...updated, objets: b.objets } : b));
			bailEdite = null;
			toast('success', 'Informations mises à jour');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}

	async function confirmerRetour() {
		if (!objetRetour) return;
		try {
			const updated = await bailApi.retourObjet(objetRetour.bail_id, objetRetour.id, {
				rendu_le: retourDate || null,
				perdu: retourPerdu,
			});
			baux = baux.map((b) =>
				b.id === updated.bail_id
					? { ...b, objets: b.objets.map((o) => (o.id === updated.id ? updated : o)) }
					: b,
			);
			objetRetour = null;
			toast('success', retourPerdu ? 'Objet marqué perdu' : 'Retour enregistré');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}

	async function supprimerObjet(bail: Bail, objet: Objet) {
		if (!confirm(`Supprimer "${objet.libelle}" ?`)) return;
		try {
			await bailApi.supprimerObjet(bail.id, objet.id);
			baux = baux.map((b) =>
				b.id === bail.id ? { ...b, objets: b.objets.filter((o) => o.id !== objet.id) } : b,
			);
			toast('success', 'Objet supprimé');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}

	// ── Recherche locataire ────────────────────────────────────────────────────
	function selectionnerLocataire(l: { id: number; nom: string; prenom: string; email: string; actif: boolean }) {
		locataireTrouve = l;
		newBailLocataireId = l.id;
		newBail.locataire_email = l.email;
		newBail.locataire_nom = l.nom;
		newBail.locataire_prenom = l.prenom;
		locataireResultats = [];
	}

	function reinitialiserLocataire() {
		locataireTrouve = null;
		newBailLocataireId = null;
		locataireResultats = [];
		locataireRechercheFaite = false;
		rechercheLocataire = '';
		newBail.locataire_email = '';
		newBail.locataire_nom = '';
		newBail.locataire_prenom = '';
	}

	async function chercherLocataire() {
		if (!rechercheLocataire.trim()) return;
		cherchantLocataire = true;
		locataireTrouve = null;
		locataireResultats = [];
		try {
			const results = await bailApi.searchLocataire(rechercheLocataire.trim());
			locataireRechercheFaite = true;
			if (results.length === 1) {
				// Sélection automatique si un seul résultat
				selectionnerLocataire(results[0]);
			} else {
				locataireResultats = results;
				newBailLocataireId = null;
			}
		} catch {
			locataireRechercheFaite = true;
			newBailLocataireId = null;
		} finally {
			cherchantLocataire = false;
		}
	}

	// ── Gestion accès ─────────────────────────────────────────────────────────
	async function ouvrirAccesBail(bail: Bail) {
		bailAcces = bail;
		accesListe = [];
		selectionVigik = new Set();
		selectionTc = new Set();
		filtreLotsAcces = new Set();
		loadingAcces = true;
		try {
			accesListe = await bailApi.accesBail(bail.id);
			preselectionRecommandee();
		} catch (e: any) {
			toast('error', 'Impossible de charger les accès');
		} finally {
			loadingAcces = false;
		}
	}

	async function affecterAuto(bail: Bail) {
		try {
			const accesAll = await bailApi.accesBail(bail.id);
			const vigikIds: number[] = [];
			const tcIds: number[] = [];
			for (const a of accesAll) {
				if (!a.eligible_transfert || a.chez_locataire || !a.recommande) continue;
				if (a.type === 'vigik') vigikIds.push(a.id);
				else tcIds.push(a.id);
			}
			if (vigikIds.length === 0 && tcIds.length === 0) {
				toast('info', 'Aucun accès à affecter automatiquement');
				return;
			}
			await bailApi.transfererAcces(bail.id, { vigik_ids: vigikIds, tc_ids: tcIds });
			const n = vigikIds.length + tcIds.length;
			toast('success', `${n} accès affecté${n > 1 ? 's' : ''} automatiquement`);
			if ($currentUser?.statut === 'copropriétaire_bailleur' || isResident) {
				baux = await bailApi.mesBaux();
			} else if ($isAdmin || $isCS) {
				baux = await bailApi.tousBaux();
			}
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur lors de l\'affectation automatique');
		}
	}

	function isSelectable(acces: Acces): boolean {
		if (!bailAcces) return false;
		if (!acces.eligible_transfert) return false;
		if (acces.chez_locataire && acces.bail_id !== bailAcces.id) return false;
		return true;
	}

	function clearSelection() {
		selectionVigik = new Set();
		selectionTc = new Set();
	}

	function preselectionRecommandee() {
		clearSelection();
		for (const a of accesListe) {
			if (!isSelectable(a) || !a.recommande) continue;
			if (a.type === 'vigik') selectionVigik.add(a.id);
			else selectionTc.add(a.id);
		}
		selectionVigik = new Set(selectionVigik);
		selectionTc = new Set(selectionTc);
	}

	function preselectionParTypeLot(typeLot: 'appartement' | 'parking') {
		clearSelection();
		for (const a of accesListe) {
			if (!isSelectable(a) || a.chez_locataire) continue;
			if (a.lot_type !== typeLot) continue;
			if (a.type === 'vigik') selectionVigik.add(a.id);
			else selectionTc.add(a.id);
		}
		selectionVigik = new Set(selectionVigik);
		selectionTc = new Set(selectionTc);
	}

	function toggleFiltreLot(lotId: number) {
		if (filtreLotsAcces.has(lotId)) filtreLotsAcces.delete(lotId);
		else filtreLotsAcces.add(lotId);
		filtreLotsAcces = new Set(filtreLotsAcces);
	}

	async function transfererAcces() {
		if (!bailAcces) return;
		const tVigik = [...selectionVigik].filter(id => {
			const a = accesListe.find(x => x.type === 'vigik' && x.id === id);
			return a && !a.chez_locataire;
		});
		const tTc = [...selectionTc].filter(id => {
			const a = accesListe.find(x => x.type === 'telecommande' && x.id === id);
			return a && !a.chez_locataire;
		});
		if (tVigik.length === 0 && tTc.length === 0) {
			toast('error', 'Sélectionnez au moins un accès à transférer');
			return;
		}
		try {
			const updated = await bailApi.transfererAcces(bailAcces.id, {
				vigik_ids: tVigik,
				tc_ids: tTc,
			});
			accesListe = accesListe.map((a) => {
				const u = updated.find((x: Acces) => x.id === a.id && x.type === a.type);
				return u ?? a;
			});
			selectionVigik = new Set();
			selectionTc = new Set();
			toast('success', 'Accès transférés au locataire');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur lors du transfert');
		}
	}

	async function recupererSelection() {
		if (!bailAcces) return;
		const rVigik = [...selectionVigik].filter(id => {
			const a = accesListe.find(x => x.type === 'vigik' && x.id === id);
			return a?.chez_locataire;
		});
		const rTc = [...selectionTc].filter(id => {
			const a = accesListe.find(x => x.type === 'telecommande' && x.id === id);
			return a?.chez_locataire;
		});
		if (rVigik.length === 0 && rTc.length === 0) {
			toast('error', 'Sélectionnez au moins un accès à récupérer');
			return;
		}
		try {
			const updated = await bailApi.recupererAcces(bailAcces.id, {
				vigik_ids: rVigik,
				tc_ids: rTc,
			});
			accesListe = accesListe.map((a) => {
				const u = updated.find((x: Acces) => x.id === a.id && x.type === a.type);
				return u ?? a;
			});
			for (const id of rVigik) selectionVigik.delete(id);
			for (const id of rTc) selectionTc.delete(id);
			selectionVigik = new Set(selectionVigik);
			selectionTc = new Set(selectionTc);
			toast('success', 'Accès récupérés');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}

	async function recupererAcces() {
		if (!bailAcces) return;
		if (!confirm('Récupérer tous les accès confiés au locataire pour ce bail ?')) return;
		try {
			const updated = await bailApi.recupererAcces(bailAcces.id);
			accesListe = accesListe.map((a) => {
				const u = updated.find((x: Acces) => x.id === a.id && x.type === a.type);
				return u ?? a;
			});
			selectionVigik = new Set();
			selectionTc = new Set();
			toast('success', 'Accès récupérés');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}

	function toggleAcces(type: 'vigik' | 'telecommande', id: number) {
		if (type === 'vigik') {
			if (selectionVigik.has(id)) selectionVigik.delete(id);
			else selectionVigik.add(id);
			selectionVigik = new Set(selectionVigik);
		} else {
			if (selectionTc.has(id)) selectionTc.delete(id);
			else selectionTc.add(id);
			selectionTc = new Set(selectionTc);
		}
	}

	$: lotsSourcesAcces = (() => {
		const map = new Map<number, string>();
		for (const a of accesListe) {
			if (a.lot_id == null) continue;
			if (!map.has(a.lot_id)) map.set(a.lot_id, a.lot_label ?? `Lot #${a.lot_id}`);
		}
		return [...map.entries()].map(([id, label]) => ({ id, label }));
	})();
	$: accesFiltres = accesListe.filter((a) => filtreLotsAcces.size === 0 || (a.lot_id != null && filtreLotsAcces.has(a.lot_id)));

	$: nTransfert = [...selectionVigik].filter(id => { const a = accesListe.find(x => x.type === 'vigik' && x.id === id); return a && !a.chez_locataire; }).length
		+ [...selectionTc].filter(id => { const a = accesListe.find(x => x.type === 'telecommande' && x.id === id); return a && !a.chez_locataire; }).length;
	$: nRecuperation = [...selectionVigik].filter(id => accesListe.find(x => x.type === 'vigik' && x.id === id)?.chez_locataire).length
		+ [...selectionTc].filter(id => accesListe.find(x => x.type === 'telecommande' && x.id === id)?.chez_locataire).length;

	// ── Helpers affichage ──────────────────────────────────────────────────────
	const typeLabel: Record<string, string> = {
		cle: '\u{1F511} Clé',
		telecommande: '\u{1F4E1} Télécommande',
		vigik: '\u{1F3F7}️ Vigik',
		autre: '\u{1F4E6} Autre',
	};

	const statutObjetBadge: Record<string, string> = {
		en_possession: 'badge-green',
		rendu: 'badge-blue',
		perdu: 'badge-red',
		non_remis: 'badge-gray',
	};

	const statutObjetLabel: Record<string, string> = {
		en_possession: 'En possession',
		rendu: 'Rendu',
		perdu: 'Perdu',
		non_remis: 'Non remis',
	};

	const statutBailLabel: Record<string, string> = {
		actif: 'Actif',
		en_cours_sortie: 'En cours de sortie',
		termine: 'Terminé',
	};

	function nomLocataire(bail: Bail): string {
		if (bail.locataire_prenom || bail.locataire_nom) {
			return [bail.locataire_prenom, bail.locataire_nom].filter(Boolean).join(' ');
		}
		return 'Locataire non renseigné';
	}

	function fmt(d: string | null): string {
		if (!d) return '—';
		return new Date(d).toLocaleDateString('fr-FR');
	}

	function lotTypeLabel(t: string | null | undefined): string {
		if (!t) return '—';
		if (t === 'appartement') return 'Appartement';
		if (t === 'parking') return 'Parking';
		if (t === 'cave') return 'Cave';
		return t;
	}

	function lotLabel(lot: LotDetail): string {
		const bat = lot.batiment_nom ?? '—';
		const type = lotTypeLabel(lot.type);
		const sub = lot.type_appartement ? ` ${lot.type_appartement}` : '';
		const etage = lot.etage !== null ? (lot.etage === 0 ? ' · RDC' : ` · Ét. ${lot.etage}`) : '';
		const surface = lot.superficie ? ` · ${lot.superficie} m²` : '';
		return `${bat} — ${type}${sub} n°${lot.numero}${etage}${surface}`;
	}

	function toggleNewBailLot(id: number) {
		if (newBailLotIds.has(id)) newBailLotIds.delete(id);
		else newBailLotIds.add(id);
		newBailLotIds = new Set(newBailLotIds);
	}
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<div class="page-header" style="justify-content:space-between;flex-wrap:wrap">
	<h1 style="display:flex;align-items:center;gap:.4rem;font-size:1.4rem;font-weight:700"><Icon name={_pc.icone || 'door-closed'} size={20} />{_pc.titre}</h1>
	{#if mainTab === 'location'}
		<button class="btn btn-primary page-header-btn" on:click={() => (showNewBail = true)}>+ Nouveau bail</button>
	{/if}
</div>
<div class="page-subtitle">{@html safeHtml(_pc.descriptif)}</div>

{#if isBailleur || $isAdmin || $isCS || (isResident && bauxTermines.length > 0)}
	<div class="tabs" role="tablist" style="margin-bottom:1.5rem">
		<button role="tab" class:active={mainTab === 'lots'} on:click={() => mainTab = 'lots'}>
			{_pc.onglets?.lots?.label ?? '\u{1F3E0} Mes lots'}
		</button>
		<button role="tab" class:active={mainTab === 'location'} on:click={() => mainTab = 'location'}>
			{_pc.onglets?.location?.label ?? '\u{1F4CB} Gestion locative'}
		</button>
	</div>
	{#if _pc.onglets?.[mainTab]?.descriptif}
	<p class="tab-descriptif">{@html safeHtml(_pc.onglets[mainTab].descriptif)}</p>
	{/if}
{/if}

<!-- ── Onglet : Mes lots ────────────────────────────────────────────── -->
{#if mainTab === 'lots'}
	{#if loading}
		<p style="color:var(--color-text-muted)">Chargement…</p>
	{:else if lots.length === 0 && !isLocataire}
		<div class="empty-state">
			<h3>Aucun lot associé</h3>
			<p>Votre compte n'est pas encore lié à un lot.</p>
			{#if $currentUser?.statut === 'locataire'}
				<p style="font-size:.85rem;color:var(--color-text-muted);margin-top:.5rem">
					Votre propriétaire doit vous rattacher depuis la section <strong>Gestion locative</strong> de son espace.
				</p>
			{:else}
				<p style="font-size:.85rem;color:var(--color-text-muted);margin-top:.5rem">
					Si votre compte vient d'être validé, la liaison se fait automatiquement.<br>
					Si aucun lot n'apparaît, contactez le gestionnaire du site ou <a href="/tickets/nouveau" style="color:var(--color-primary)">faites une nouvelle demande</a>.
				</p>
			{/if}
		</div>
	{:else if isLocataire}
		<!-- ── Vue locataire : lot loué via bail ── -->
		{#if monBailData}
			<div class="lots-section-label">🏠 Lot loué</div>
			<div class="card" style="max-width:640px;margin-bottom:1.5rem">
				<div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.75rem">
					<span class="lbc-lot-badge">{monBailData.lot_batiment_nom ?? '—'} / {monBailData.lot_numero ?? '—'}</span>
					<span class="badge badge-green" style="font-size:.72rem">{monBailData.statut === 'actif' ? 'Bail actif' : monBailData.statut.replace('_', ' ')}</span>
				</div>
				<dl class="details-grid">
					<dt>Bâtiment</dt><dd>{monBailData.lot_batiment_nom ?? '—'}</dd>
					{#if monBailData.lot_type}<dt>Type</dt><dd style="text-transform:capitalize">{monBailData.lot_type.replace('_', ' ')}{monBailData.lot_type_appartement ? ` – ${monBailData.lot_type_appartement}` : ''}</dd>{/if}
					{#if monBailData.lot_etage !== null && monBailData.lot_etage !== undefined}<dt>Étage</dt><dd>{monBailData.lot_etage === 0 ? 'RDC' : monBailData.lot_etage}</dd>{/if}
					{#if monBailData.lot_superficie}<dt>Superficie</dt><dd>{monBailData.lot_superficie} m²</dd>{/if}
					<dt>Entrée</dt><dd>{fmt(monBailData.date_entree)}</dd>
					{#if monBailData.date_sortie_prevue}<dt>Sortie prévue</dt><dd>{fmt(monBailData.date_sortie_prevue)}</dd>{/if}
				</dl>
				{#if monBailData.bailleur_nom || monBailData.bailleur_prenom}
					<div style="margin-top:.75rem;font-size:.85rem;color:var(--color-text-muted)">
						🏢 Propriétaire : <strong>{[monBailData.bailleur_prenom, monBailData.bailleur_nom].filter(Boolean).join(' ')}</strong>
						{#if monBailData.bailleur_email}<br>📬 <a href="mailto:{monBailData.bailleur_email}" style="color:var(--color-primary)">{monBailData.bailleur_email}</a>{/if}
						{#if monBailData.bailleur_telephone}<br>📞 {monBailData.bailleur_telephone}{/if}
					</div>
				{/if}
			</div>
		{:else}
			<div class="empty-state">
				<h3>Aucun bail actif</h3>
				<p>Votre propriétaire doit vous rattacher depuis la section <strong>Gestion locative</strong> de son espace.</p>
			</div>
		{/if}

		<!-- Lots en propre du locataire (s'il en possède aussi) -->
		{#if lots.length > 0}
			<div class="lots-section-label" style="margin-top:1.5rem">🏢 Lots en propriété ({lots.length})</div>
			{#each lots as lot (lot.id)}
				<div class="card" style="max-width:640px;margin-bottom:1rem">
					<h2 style="font-size:1rem;font-weight:600;margin-bottom:.75rem">{lot.batiment_nom ?? '—'} / {lot.numero}</h2>
					<dl class="details-grid">
						<dt>Type</dt><dd style="text-transform:capitalize">{lot.type.replace('_', ' ')}{lot.type_appartement ? ` – ${lot.type_appartement}` : ''}</dd>
						{#if lot.etage !== null}<dt>Étage</dt><dd>{lot.etage === 0 ? 'RDC' : lot.etage}</dd>{/if}
						{#if lot.superficie}<dt>Superficie</dt><dd>{lot.superficie} m²</dd>{/if}
					</dl>
				</div>
			{/each}
		{/if}
	{:else if isBailleur}
		<!-- ── Vue bailleur : lots possédés + locataires ── -->
		{@const lotsAvecBail = lots.map(l => ({ ...l, bail: bauxActifs.find(b => b.lot_id === l.id) ?? null }))}
		{@const locatairesMap = (() => {
			const map = new Map();
			for (const b of bauxActifs) {
				const key = b.locataire_id ?? `ext_${b.id}`;
				if (!map.has(key)) map.set(key, { bail: b, baux: [] });
				map.get(key).baux.push(b);
			}
			return [...map.values()];
		})()}
		{@const lotsVacants = lots.filter(l => !bauxActifs.find(b => b.lot_id === l.id))}

		<!-- Section 1 : Tous les lots possédés -->
		<div class="lots-section-label">🏢 Lots possédés ({lots.length})</div>
		<div class="lots-possedes-grid">
		{#each lotsAvecBail as lot}
			<div class="lot-possede-card card" class:lot-occupe={!!lot.bail} class:lot-vacant={!lot.bail}>
				<div class="lpc-header">
					<span class="lbc-lot-badge">{lot.batiment_nom ?? '—'} / {lot.numero}</span>
					{#if lot.bail}
						<span class="badge badge-green" style="font-size:.7rem">Occupé</span>
					{:else}
						<span class="badge badge-gray" style="font-size:.7rem">Vacant</span>
					{/if}
				</div>
				<div class="lpc-details">
					<span class="badge badge-gray" style="font-size:.72rem;text-transform:capitalize">{lot.type.replace('_', ' ')}{lot.type_appartement ? ` – ${lot.type_appartement}` : ''}</span>
					{#if lot.etage !== null}<span style="font-size:.78rem;color:var(--color-text-muted)">Étage {lot.etage === 0 ? 'RDC' : lot.etage}</span>{/if}
					{#if lot.superficie}<span style="font-size:.78rem;color:var(--color-text-muted)">{lot.superficie} m²</span>{/if}
				</div>
				{#if lot.bail}
					<div class="lpc-occupant">👤 {nomLocataire(lot.bail)}</div>
				{:else}
					<button class="btn btn-sm btn-primary" style="margin-top:.4rem" on:click={() => { mainTab = 'location'; newBailLotIds = new Set([lot.id]); showNewBail = true; }}>
						+ Créer un bail
					</button>
				{/if}
			</div>
		{/each}
		</div>

		<!-- Section 2 : Locataires (lots regroupés par locataire) -->
		{#if locatairesMap.length > 0}
		<div class="lots-section-label" style="margin-top:1.8rem">👥 Locataires ({locatairesMap.length})</div>
		{#each locatairesMap as loc}
			{@const premierBail = loc.bail}
			<div class="locataire-card card">
				<div class="loc-header">
					<div class="loc-name">
						👤 <strong>{nomLocataire(premierBail)}</strong>
						<span class="badge {premierBail.statut === 'actif' ? 'badge-green' : 'badge-yellow'}" style="font-size:.7rem">{statutBailLabel[premierBail.statut] ?? premierBail.statut}</span>
					</div>
					<div class="loc-contact">
						{#if premierBail.locataire_email}<a href="mailto:{premierBail.locataire_email}" style="color:var(--color-primary);font-size:.82rem">📬 {premierBail.locataire_email}</a>{/if}
						{#if premierBail.locataire_telephone}<span style="font-size:.82rem;color:var(--color-text-muted)">📞 {premierBail.locataire_telephone}</span>{/if}
					</div>
				</div>
				<div class="loc-lots">
					{#each loc.baux as bail}
						{@const lot = lots.find(l => l.id === bail.lot_id)}
						{#if lot}
						<div class="loc-lot-row">
							<span class="lbc-lot-badge">{lot.batiment_nom ?? '—'} / {lot.numero}</span>
							<span class="badge badge-gray" style="font-size:.7rem;text-transform:capitalize">{lot.type.replace('_', ' ')}{lot.type_appartement ? ` – ${lot.type_appartement}` : ''}</span>
							<span style="font-size:.78rem;color:var(--color-text-muted)">Depuis le {fmt(bail.date_entree)}{bail.date_sortie_prevue ? ` · Sortie prévue ${fmt(bail.date_sortie_prevue)}` : ''}</span>
						</div>
						{/if}
					{/each}
				</div>
				<div class="lbc-actions">
					<button class="btn btn-sm btn-outline" on:click={() => { mainTab = 'location'; bailTab = 'actif'; }}>📋 Gestion locative</button>
					<button class="btn btn-sm btn-outline" on:click={() => ouvrirAccesBail(premierBail)}>🔑 Accès</button>
					<button class="btn btn-sm btn-outline" on:click={() => ouvrirEditionLocataire(premierBail)}>✏️ Modifier</button>
				</div>
			</div>
		{/each}
		{/if}

		<!-- Lots vacants (rappel rapide) -->
		{#if lotsVacants.length > 0}
		<div class="lots-section-label" style="margin-top:1.8rem">🔓 Lots vacants ({lotsVacants.length})</div>
		<p style="font-size:.85rem;color:var(--color-text-muted);margin:0 0 .6rem">Ces lots n'ont pas de bail actif. Créez un bail depuis la fiche du lot ci-dessus ou l'onglet <strong>Gestion locative</strong>.</p>
		{/if}

	{:else}
		<!-- ── Vue standard (non bailleur) : sélecteur lot + carte ── -->
		{#if lots.length > 1}
			<div class="lot-tabs" role="tablist">
				{#each lots as lot}
					<button
						role="tab"
						class:active={selectedLotId === lot.id}
						on:click={() => (selectedLotId = lot.id)}
					>
						{lot.batiment_nom ?? '—'} / {lot.type.charAt(0).toUpperCase() + lot.type.slice(1)} - {lot.numero}
					</button>
				{/each}
			</div>
		{/if}

		{#if selectedLot}
			<div class="card" style="max-width:640px;margin-bottom:1.5rem">
				<h2 style="font-size:1rem;font-weight:600;margin-bottom:1rem">Caractéristiques</h2>
				<dl class="details-grid">
					<dt>Lot</dt><dd>{selectedLot.numero}</dd>
					<dt>Bâtiment</dt><dd>{selectedLot.batiment_nom ?? '—'}</dd>
					<dt>Type</dt><dd style="text-transform:capitalize">{selectedLot.type.replace('_', ' ')}{selectedLot.type_appartement ? ` – ${selectedLot.type_appartement}` : ''}</dd>
					{#if selectedLot.etage !== null}<dt>Étage</dt><dd>{selectedLot.etage === 0 ? 'RDC' : selectedLot.etage}</dd>{/if}
					{#if selectedLot.superficie}<dt>Superficie</dt><dd>{selectedLot.superficie} m²</dd>{/if}
				</dl>
			</div>
		{/if}
	{/if}
{/if}

<!-- ── Onglet : Gestion locative ────────────────────────────────────── -->
{#if mainTab === 'location'}
	<div style="max-width:900px">
		<div class="bail-tabs" style="margin-bottom:1.5rem">
			<button class:active={bailTab === 'actif'} on:click={() => (bailTab = 'actif')}>
				Baux actifs ({bauxActifs.length})
			</button>
			<button class:active={bailTab === 'historique'} on:click={() => (bailTab = 'historique')}>
				Historique ({bauxTermines.length})
			</button>
		</div>

		{#if bauxLoading}
			<p style="color:var(--color-text-muted)">Chargement…</p>
		{:else}
			{@const displayed = bailTab === 'actif' ? bauxActifs : bauxTermines}
			{@const grouped = (() => {
				const map = new Map();
				for (const b of displayed) {
					const key = b.locataire_id ?? `ext_${b.id}`;
					if (!map.has(key)) map.set(key, { bail: b, baux: [] });
					map.get(key).baux.push(b);
				}
				return [...map.values()];
			})()}

			{#if grouped.length === 0}
				<div class="empty-state">
					<p>{bailTab === 'actif' ? 'Aucun bail actif.' : 'Aucun bail terminé.'}</p>
				</div>
			{:else}
				{#each grouped as group}
					{@const premierBail = group.bail}
					<div class="card" style="margin-bottom:1.5rem;padding:1.25rem">
						<!-- En-tête locataire -->
						<div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:1rem">
							<div>
								<div style="font-weight:700;font-size:1rem">{nomLocataire(premierBail)}</div>
								{#if premierBail.locataire_email}
									<div style="font-size:0.82rem;color:var(--color-text-muted)">{premierBail.locataire_email}</div>
								{/if}
								{#if premierBail.locataire_telephone}
									<div style="font-size:0.82rem;color:var(--color-text-muted)">{premierBail.locataire_telephone}</div>
								{/if}
							</div>
							<div style="display:flex;gap:0.5rem;flex-wrap:wrap;justify-content:flex-end">
								<span class="badge {premierBail.statut === 'actif' ? 'badge-green' : premierBail.statut === 'en_cours_sortie' ? 'badge-yellow' : 'badge-gray'}">
									{statutBailLabel[premierBail.statut] ?? premierBail.statut}
								</span>
							</div>
						</div>

						<!-- Actions globales locataire -->
						{#if premierBail.statut !== 'termine'}
							<div style="display:flex;gap:0.5rem;margin-bottom:1.25rem;flex-wrap:wrap">
								<button class="btn btn-sm" on:click={() => ouvrirEditionLocataire(premierBail)}>✏️ Modifier</button>
								<button class="btn btn-sm" on:click={() => ouvrirAccesBail(premierBail)}>&#x1F511; Accès</button>
							</div>
						{/if}

						<!-- Détails par bail (lot) -->
						{#each group.baux as bail (bail.id)}
							{@const lot = lots.find(l => l.id === bail.lot_id)}
							<div class="gl-bail-section" style="border-top:1px solid var(--color-border);padding-top:1rem;margin-top:1rem">
								<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.6rem;flex-wrap:wrap;gap:.5rem">
									<div style="display:flex;align-items:center;gap:.5rem;flex-wrap:wrap">
										{#if lot}
											<span class="lbc-lot-badge">{lot.batiment_nom ?? '—'} / {lot.numero}</span>
											<span class="badge badge-gray" style="font-size:.72rem;text-transform:capitalize">{lot.type.replace('_', ' ')}{lot.type_appartement ? ` – ${lot.type_appartement}` : ''}</span>
										{/if}
										{#if group.baux.length > 1}
											<span class="badge {bail.statut === 'actif' ? 'badge-green' : bail.statut === 'en_cours_sortie' ? 'badge-yellow' : 'badge-gray'}" style="font-size:.7rem">
												{statutBailLabel[bail.statut] ?? bail.statut}
											</span>
										{/if}
									</div>
									{#if bail.statut !== 'termine'}
										<button class="btn btn-xs btn-outline" on:click={() => affecterAuto(bail)} title="Affecter automatiquement les accès recommandés">
											⚡ Auto
										</button>
										<button class="btn btn-xs btn-danger" on:click={() => { bailATerminer = bail; dateSortie = ''; }}>
											Terminer
										</button>
									{/if}
									{#if $isAdmin || $isCS}
										<button class="btn btn-xs btn-danger" on:click={() => { bailASupprimer = bail; }}>
											🗑️ Supprimer
										</button>
									{/if}
								</div>

								<div style="display:flex;gap:2rem;font-size:0.85rem;margin-bottom:.75rem;flex-wrap:wrap">
									<span><strong>Entrée :</strong> {fmt(bail.date_entree)}</span>
									<span><strong>Sortie prévue :</strong> {fmt(bail.date_sortie_prevue)}</span>
									{#if bail.date_sortie_reelle}
										<span><strong>Sortie réelle :</strong> {fmt(bail.date_sortie_reelle)}</span>
									{/if}
								</div>

								{#if bail.notes}
									<div class="rich-content" style="font-size:0.85rem;color:var(--color-text-muted);margin-bottom:.75rem;font-style:italic">{@html safeHtml(bail.notes)}</div>
								{/if}

								<div>
									<div style="font-weight:600;font-size:0.9rem;margin-bottom:0.5rem">
										Inventaire ({bail.objets.length} objet{bail.objets.length !== 1 ? 's' : ''})
									</div>
									{#if bail.objets.length === 0}
										<p style="font-size:0.83rem;color:var(--color-text-muted)">Aucun objet enregistré.</p>
									{:else}
										<table class="table" style="font-size:0.85rem">
											<thead>
												<tr>
													<th>Type</th>
													<th>Libellé</th>
													<th>Qté</th>
													<th>Référence</th>
													<th>Statut</th>
													<th>Remis le</th>
													<th>Rendu le</th>
													{#if bail.statut !== 'termine'}
														<th></th>
													{/if}
												</tr>
											</thead>
											<tbody>
												{#each bail.objets as objet (objet.id)}
													<tr>
														<td>{typeLabel[objet.type] ?? objet.type}</td>
														<td>{objet.libelle}</td>
														<td style="text-align:center">{objet.quantite}</td>
														<td>{objet.reference ?? '—'}</td>
														<td>
															<span class="badge {statutObjetBadge[objet.statut] ?? 'badge-gray'}">
																{statutObjetLabel[objet.statut] ?? objet.statut}
															</span>
														</td>
														<td>{fmt(objet.remis_le)}</td>
														<td>{fmt(objet.rendu_le)}</td>
														{#if bail.statut !== 'termine'}
															<td>
																<div style="display:flex;gap:0.35rem">
																	{#if objet.statut === 'en_possession'}
																		<button
																			class="btn btn-xs"
																			title="Enregistrer retour / perte"
																			on:click={() => { objetRetour = objet; retourDate = ''; retourPerdu = false; }}
																		>↩</button>
																	{/if}
																	<button
																		class="btn btn-xs btn-danger"
																		title="Supprimer"
																		on:click={() => supprimerObjet(bail, objet)}
																	>✕</button>
																</div>
															</td>
														{/if}
													</tr>
												{/each}
											</tbody>
										</table>
									{/if}
								</div>
							</div>
						{/each}
					</div>
				{/each}
			{/if}
		{/if}
	</div>
{/if}

<!-- ── Modal : nouveau bail ─────────────────────────────────────────── -->
{#if showNewBail}
	<div class="modal-overlay" on:click|self={() => (showNewBail = false)} role="dialog" aria-modal="true" aria-label="Nouveau bail" tabindex="-1">
		<div class="modal" style="width:min(560px,95vw)">
			<div class="modal-header">
				<h3>Nouveau bail</h3>
				<button class="modal-close" on:click={() => (showNewBail = false)}>✕</button>
			</div>
			<div class="modal-body">
				<!-- Sélection des lots -->
				<div class="form-group">
					<label>Lot(s) concerné(s) *</label>
					<div class="lot-checklist">
						{#each lots as lot (lot.id)}
							{@const occupied = !!bauxActifs.find(b => b.lot_id === lot.id)}
							<label class="lot-check-item" class:disabled={occupied} title={occupied ? 'Ce lot a déjà un bail actif' : undefined}>
								<input
									type="checkbox"
									checked={newBailLotIds.has(lot.id)}
									disabled={occupied}
									on:change={() => toggleNewBailLot(lot.id)}
								/>
								<span class="lot-check-label">
									<span class="lot-check-name">{lotLabel(lot)}</span>
									{#if occupied}<span class="badge badge-yellow" style="font-size:.68rem">Bail actif</span>{/if}
								</span>
							</label>
						{/each}
					</div>
					{#if newBailLotIds.size > 0}
						<p class="lot-selection-hint">{newBailLotIds.size} lot{newBailLotIds.size > 1 ? 's' : ''} sélectionné{newBailLotIds.size > 1 ? 's' : ''} — un bail sera créé pour chacun</p>
					{/if}
				</div>

				<!-- Recherche locataire inscrit -->
				<fieldset class="search-locataire-box">
					<legend>Associer un compte existant <span class="optional-hint">(optionnel)</span></legend>
					{#if locataireTrouve}
						<!-- Locataire sélectionné -->
						<div class="locataire-selected">
							<div class="locataire-selected-info">
								<span class="locataire-selected-name">✓ {locataireTrouve.prenom} {locataireTrouve.nom}</span>
								<span class="locataire-selected-email">{locataireTrouve.email}</span>
								{#if !locataireTrouve.actif}
									<span class="badge badge-yellow" style="font-size:.72rem">En attente d'activation</span>
								{/if}
							</div>
							<button class="btn btn-xs btn-outline" on:click={reinitialiserLocataire} title="Changer de locataire">✕ Changer</button>
						</div>
					{:else}
						<div class="search-locataire-row">
							<input
								type="search"
								id="nb-recherche"
								placeholder="Nom, prénom ou email…"
								bind:value={rechercheLocataire}
								on:keydown={(e) => e.key === 'Enter' && chercherLocataire()}
								autocomplete="off"
							/>
							<button class="btn btn-sm" disabled={cherchantLocataire || !rechercheLocataire.trim()} on:click={chercherLocataire}>
								{cherchantLocataire ? '…' : '🔍 Chercher'}
							</button>
						</div>
						{#if locataireRechercheFaite && locataireResultats.length === 0 && !cherchantLocataire}
							<p class="search-no-result">Aucun compte trouvé — renseignez manuellement ci-dessous.</p>
						{:else if locataireResultats.length > 1}
							<ul class="locataire-resultats">
								{#each locataireResultats as r (r.id)}
									<li>
										<button class="locataire-resultat-btn" on:click={() => selectionnerLocataire(r)}>
											<span class="lr-name">{r.prenom} {r.nom}</span>
											<span class="lr-email">{r.email}</span>
											{#if !r.actif}<span class="badge badge-yellow" style="font-size:.68rem">En attente</span>{/if}
										</button>
									</li>
								{/each}
							</ul>
						{/if}
					{/if}
				</fieldset>

				<!-- Informations locataire (pré-remplies si compte sélectionné) -->
				<div class="form-grid-2">
					<div class="form-group">
						<label for="nb-prenom">Prénom</label>
						<input id="nb-prenom" type="text" bind:value={newBail.locataire_prenom} placeholder="Prénom" readonly={!!locataireTrouve} />
					</div>
					<div class="form-group">
						<label for="nb-nom">Nom</label>
						<input id="nb-nom" type="text" bind:value={newBail.locataire_nom} placeholder="Nom" readonly={!!locataireTrouve} />
					</div>
					<div class="form-group">
						<label for="nb-email">E-mail</label>
						<input id="nb-email" type="email" bind:value={newBail.locataire_email} placeholder="email@exemple.fr" readonly={!!locataireTrouve} />
					</div>
					<div class="form-group">
						<label for="nb-tel">Téléphone</label>
						<input id="nb-tel" type="text" bind:value={newBail.locataire_telephone} placeholder="06 …" />
					</div>
					<div class="form-group">
						<label for="nb-entree">Date d'entrée *</label>
						<input id="nb-entree" type="date" bind:value={newBail.date_entree} />
					</div>
					<div class="form-group">
						<label for="nb-sortie">Sortie prévue</label>
						<input id="nb-sortie" type="date" bind:value={newBail.date_sortie_prevue} />
					</div>
				</div>
				<div class="form-group">
					<label>Notes</label>
					<RichEditor bind:value={newBail.notes} placeholder="Notes sur le bail…" minHeight="80px" />
				</div>
			</div>
			<div class="modal-footer">
				<button class="btn" on:click={() => (showNewBail = false)}>Annuler</button>
				<button class="btn btn-primary" disabled={savingBail} on:click={creerBail}>
					{savingBail ? 'Création…' : 'Créer le bail'}
				</button>
			</div>
		</div>
	</div>
{/if}

<!-- ── Modal : terminer bail ────────────────────────────────────────── -->
{#if bailATerminer}
	<div class="modal-overlay" on:click|self={() => (bailATerminer = null)} role="dialog" aria-modal="true" aria-label="Terminer le bail" tabindex="-1">
		<div class="modal" style="width:min(400px,95vw)">
			<div class="modal-header">
				<h3>Terminer le bail</h3>
				<button class="modal-close" on:click={() => (bailATerminer = null)}>✕</button>
			</div>
			<div class="modal-body">
				<p style="margin-bottom:0.75rem">Confirmer la fin du bail de <strong>{nomLocataire(bailATerminer)}</strong> ?</p>
				<div class="form-group">
					<label for="tb-sortie">Date de sortie réelle</label>
					<input id="tb-sortie" type="date" bind:value={dateSortie} />
				</div>
			</div>
			<div class="modal-footer">
				<button class="btn" on:click={() => (bailATerminer = null)}>Annuler</button>
				<button class="btn btn-danger" on:click={confirmerTerminer}>Terminer</button>
			</div>
		</div>
	</div>
{/if}

<!-- ── Modal : supprimer bail (admin) ──────────────────────────────── -->
{#if bailASupprimer}
	<div class="modal-overlay" on:click|self={() => (bailASupprimer = null)} role="dialog" aria-modal="true" aria-label="Supprimer le bail" tabindex="-1">
		<div class="modal" style="width:min(400px,95vw)">
			<div class="modal-header">
				<h3>Supprimer le bail</h3>
				<button class="modal-close" on:click={() => (bailASupprimer = null)}>✕</button>
			</div>
			<div class="modal-body">
				<p>Supprimer définitivement le bail de <strong>{nomLocataire(bailASupprimer)}</strong> et tous ses objets associés ?</p>
				<p style="color:var(--color-danger);font-size:0.85rem;margin-top:0.5rem">Cette action est irréversible.</p>
			</div>
			<div class="modal-footer">
				<button class="btn" on:click={() => (bailASupprimer = null)}>Annuler</button>
				<button class="btn btn-danger" on:click={confirmerSupprimer}>Supprimer</button>
			</div>
		</div>
	</div>
{/if}

<!-- ── Modal : modifier locataire ───────────────────────────────────── -->
{#if bailEdite}
	<div class="modal-overlay" on:click|self={() => (bailEdite = null)} role="dialog" aria-modal="true" aria-label="Modifier locataire" tabindex="-1">
		<div class="modal" style="width:min(560px,95vw)">
			<div class="modal-header">
				<h3>Modifier les informations</h3>
				<button class="modal-close" on:click={() => (bailEdite = null)}>✕</button>
			</div>
			<div class="modal-body">
				<!-- Associer un compte locataire -->
				<fieldset class="search-locataire-box" style="margin-bottom:1rem">
					<legend>Compte locataire associé <span class="optional-hint">(optionnel)</span></legend>
					{#if editLocataireTrouve}
						<div class="locataire-selected">
							<div class="locataire-selected-info">
								<span class="locataire-selected-name">✓ {editLocataireTrouve.prenom} {editLocataireTrouve.nom}</span>
								<span class="locataire-selected-email">{editLocataireTrouve.email}</span>
								{#if !editLocataireTrouve.actif}
									<span class="badge badge-yellow" style="font-size:.72rem">En attente d'activation</span>
								{/if}
							</div>
							<button class="btn btn-xs btn-outline" on:click={editDissocierLocataire} title="Dissocier ce compte">✕ Dissocier</button>
						</div>
					{:else}
						<!-- Suggestions : locataires ayant déclaré ce bailleur -->
						{#if editSuggestions.length > 0}
							<p style="font-size:.78rem;color:var(--color-text-muted);margin-bottom:.4rem">Locataires ayant déclaré votre nom :</p>
							<ul class="locataire-resultats" style="margin-bottom:.65rem">
								{#each editSuggestions as s (s.id)}
									<li>
										<button class="locataire-resultat-btn" on:click={() => editSelectionnerLocataire(s)}>
											<span class="lr-name">{s.prenom} {s.nom}</span>
											<span class="lr-email">{s.email}</span>
											{#if !s.actif}<span class="badge badge-yellow" style="font-size:.68rem">En attente</span>{/if}
										</button>
									</li>
								{/each}
							</ul>
							<p style="font-size:.75rem;color:var(--color-text-muted);margin-bottom:.35rem">Ou recherchez un autre compte :</p>
						{/if}
						<div class="search-locataire-row">
							<input
								type="search"
								placeholder="Nom, prénom ou email…"
								bind:value={editRechercheLocataire}
								on:keydown={(e) => e.key === 'Enter' && editChercherLocataire()}
								autocomplete="off"
							/>
							<button class="btn btn-sm" disabled={editCherchant || !editRechercheLocataire.trim()} on:click={editChercherLocataire}>
								{editCherchant ? '…' : '🔍 Chercher'}
							</button>
						</div>
						{#if editLocataireRechercheFaite && editLocataireResultats.length === 0 && !editCherchant}
							<p class="search-no-result">Aucun compte trouvé.</p>
						{:else if editLocataireResultats.length > 0}
							<ul class="locataire-resultats">
								{#each editLocataireResultats as r (r.id)}
									<li>
										<button class="locataire-resultat-btn" on:click={() => editSelectionnerLocataire(r)}>
											<span class="lr-name">{r.prenom} {r.nom}</span>
											<span class="lr-email">{r.email}</span>
											{#if !r.actif}<span class="badge badge-yellow" style="font-size:.68rem">En attente</span>{/if}
										</button>
									</li>
								{/each}
							</ul>
						{/if}
					{/if}
				</fieldset>

				<div class="locataire-edit-grid">
					<div class="form-group">
						<label for="el-prenom">Prénom</label>
						<input id="el-prenom" type="text" bind:value={editLocataire.locataire_prenom} placeholder="Prénom" />
					</div>
					<div class="form-group">
						<label for="el-nom">Nom</label>
						<input id="el-nom" type="text" bind:value={editLocataire.locataire_nom} placeholder="Nom" />
					</div>
					<div class="form-group">
						<label for="el-email">E-mail</label>
						<input id="el-email" type="email" bind:value={editLocataire.locataire_email} placeholder="email@exemple.fr" />
					</div>
					<div class="form-group">
						<label for="el-tel">Téléphone</label>
						<input id="el-tel" type="text" bind:value={editLocataire.locataire_telephone} placeholder="06 …" />
					</div>
					<div class="form-group locataire-edit-full">
						<label for="el-sortie">Sortie prévue</label>
						<input id="el-sortie" type="date" bind:value={editLocataire.date_sortie_prevue} />
					</div>
					<div class="form-group locataire-edit-full">
						<label>Notes</label>
						<RichEditor bind:value={editLocataire.notes} placeholder="Notes sur le bail…" minHeight="120px" />
					</div>
				</div>
			</div>
			<div class="modal-footer">
				<button class="btn" on:click={() => (bailEdite = null)}>Annuler</button>
				<button class="btn btn-primary" on:click={sauvegarderLocataire}>Enregistrer</button>
			</div>
		</div>
	</div>
{/if}

<!-- ── Modal : retour objet ─────────────────────────────────────────── -->
{#if objetRetour}
	<div class="modal-overlay" on:click|self={() => (objetRetour = null)} role="dialog" aria-modal="true" aria-label="Retour objet" tabindex="-1">
		<div class="modal" style="width:min(380px,95vw)">
			<div class="modal-header">
				<h3>Retour — {objetRetour.libelle}</h3>
				<button class="modal-close" on:click={() => (objetRetour = null)}>✕</button>
			</div>
			<div class="modal-body" style="display:flex;flex-direction:column;gap:0.75rem">
				<div class="form-group">
					<label for="ro-date">Date de retour</label>
					<input id="ro-date" type="date" bind:value={retourDate} />
				</div>
				<label style="display:flex;align-items:center;gap:0.5rem;font-size:0.9rem">
					<input type="checkbox" bind:checked={retourPerdu} />
					Marquer comme perdu
				</label>
			</div>
			<div class="modal-footer">
				<button class="btn" on:click={() => (objetRetour = null)}>Annuler</button>
				<button
					class="btn {retourPerdu ? 'btn-danger' : 'btn-primary'}"
					on:click={confirmerRetour}
				>
					{retourPerdu ? 'Perdu' : 'Retour confirmé'}
				</button>
			</div>
		</div>
	</div>
{/if}

<!-- ── Modal : gestion des accès (Vigik / TC) ───────────────────────── -->
{#if bailAcces}
	<div class="modal-overlay" on:click|self={() => (bailAcces = null)} role="dialog" aria-modal="true" aria-label="Accès du bail" tabindex="-1">
		<div class="modal" style="width:min(620px,95vw)">
			<div class="modal-header">
				<h3>Accès — {nomLocataire(bailAcces)}</h3>
				<button class="modal-close" on:click={() => (bailAcces = null)}>✕</button>
			</div>
			<div class="modal-body">
				{#if loadingAcces}
					<p style="color:var(--color-text-muted)">Chargement…</p>
				{:else if bailAccesLot && (bailAccesLot.type === 'parking' || bailAccesLot.type === 'cave')}
					<p style="font-size:0.85rem;color:#92400e;background:#fef3c7;border:1px solid #fde68a;border-radius:8px;padding:.5rem .65rem;margin-bottom:.7rem">
						Ce bail concerne un {bailAccesLot.type}. <strong>TC uniquement</strong> : les Vigik ne sont pas autorisés.
					</p>
				{:else if accesListe.length === 0}
					<p style="color:var(--color-text-muted);font-size:0.9rem">
						Aucun Vigik ni télécommande rattaché à ce lot.
					</p>
				{:else}
					<p style="font-size:0.85rem;color:var(--color-text-muted);margin-bottom:0.6rem">
						Sélection intelligente : utilisez un préréglage puis ajustez manuellement. Les règles de cohérence sont appliquées automatiquement (ex. pas de Vigik pour un bail parking seul).
					</p>
					<div class="acces-presets">
						<button class="btn btn-sm" on:click={preselectionRecommandee}>✨ Préselection recommandée</button>
						<button class="btn btn-sm btn-outline" on:click={clearSelection}>Effacer</button>
					</div>
					{#if lotsSourcesAcces.length > 1}
						<div class="acces-filters">
							<span style="font-size:.78rem;color:var(--color-text-muted)">Filtrer lots source :</span>
							{#each lotsSourcesAcces as ls}
								<button class="chip-btn" class:active={filtreLotsAcces.has(ls.id)} on:click={() => toggleFiltreLot(ls.id)}>{ls.label}</button>
							{/each}
						</div>
					{/if}
					<table class="table" style="font-size:0.85rem">
						<thead>
							<tr>
								<th style="width:2rem"></th>
								<th>Lot source</th>
								<th>Type</th>
								<th>Code</th>
								<th>Statut</th>
								<th>Localisation</th>
								<th>Info</th>
							</tr>
						</thead>
						<tbody>
							{#each accesFiltres as acces (acces.type + acces.id)}
								<tr>
									<td>
										{#if isSelectable(acces)}
											<input
												type="checkbox"
												checked={acces.type === 'vigik' ? selectionVigik.has(acces.id) : selectionTc.has(acces.id)}
												on:change={() => toggleAcces(acces.type, acces.id)}
											/>
										{/if}
									</td>
									<td>{acces.lot_label ?? '—'} <span class="badge badge-gray" style="margin-left:.25rem">{lotTypeLabel(acces.lot_type)}</span></td>
									<td>{acces.type === 'vigik' ? '\u{1F3F7}️ Vigik' : '\u{1F4E1} Télécommande'}</td>
									<td style="font-family:monospace">{acces.code}</td>
									<td>
										<span class="badge {acces.statut === 'actif' ? 'badge-green' : 'badge-gray'}">
											{acces.statut}
										</span>
									</td>
									<td>
										{#if acces.chez_locataire}
											<span class="badge badge-yellow">Chez locataire</span>
										{:else}
											<span class="badge badge-blue">Chez bailleur</span>
										{/if}
									</td>
									<td>
										{#if acces.recommande}
											<span class="badge badge-green">Recommandé</span>
										{:else if acces.motif_non_eligible}
											<span class="badge badge-gray" title={acces.motif_non_eligible}>{acces.motif_non_eligible}</span>
										{/if}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
					{#if accesListe.some((a) => a.chez_locataire)}
						<button class="btn btn-sm" style="margin-top:0.75rem" on:click={recupererAcces}>
							↩ Tout récupérer
						</button>
					{/if}
				{/if}
			</div>
			<div class="modal-footer">
				<button class="btn" on:click={() => (bailAcces = null)}>Fermer</button>
				{#if nRecuperation > 0}
					<button class="btn btn-warning" on:click={recupererSelection}>
						↩ Récupérer ({nRecuperation})
					</button>
				{/if}
				{#if nTransfert > 0}
					<button class="btn btn-primary" on:click={transfererAcces}>
						Transférer ({nTransfert})
					</button>
				{/if}
			</div>
		</div>
	</div>
{/if}

<style>
	/* Lot tabs (multi-lot selector) */
	.lot-tabs { display: flex; gap: .5rem; margin-bottom: 1rem; flex-wrap: wrap; }
	.lot-tabs button { padding: .4rem .9rem; border: 1px solid var(--color-border); background: var(--color-bg); border-radius: var(--radius); cursor: pointer; font-size: .875rem; color: var(--color-text); }
	.lot-tabs button.active { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }

	/* Lot characteristics */
	.details-grid { display: grid; grid-template-columns: auto 1fr; gap: .4rem .8rem; font-size: .875rem; }
	.details-grid dt { font-weight: 500; color: var(--color-text-muted); }
	.details-grid dd { margin: 0; }
	/* Bailleur lot cards */
	.lots-section-label { font-size: .78rem; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; color: var(--color-text-muted); margin-bottom: .6rem; }
	.lot-bailleur-card { padding: 1rem 1.2rem; margin-bottom: .6rem; }
	.lot-vacant { opacity: .8; border-style: dashed; }
	.lbc-top { display: flex; justify-content: space-between; align-items: center; gap: .5rem; flex-wrap: wrap; margin-bottom: .5rem; }
	.lbc-lot-id { display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; }
	.lbc-lot-badge { font-weight: 700; font-size: .92rem; }
	.lbc-tenant { border-top: 1px solid var(--color-border); padding-top: .6rem; display: flex; flex-direction: column; gap: .3rem; }
	.lbc-tenant-name { display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; font-size: .92rem; }
	.lbc-tenant-meta { display: flex; flex-wrap: wrap; gap: .6rem; align-items: center; }
	.lbc-actions { display: flex; gap: .4rem; flex-wrap: wrap; margin-top: .3rem; }

	/* Lots possédés grid */
	.lots-possedes-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: .6rem; margin-bottom: .6rem; }
	.lot-possede-card { padding: .85rem 1rem; display: flex; flex-direction: column; gap: .35rem; }
	.lot-possede-card.lot-occupe { border-left: 3px solid var(--color-success, #22c55e); }
	.lot-possede-card.lot-vacant { border-left: 3px dashed var(--color-border); opacity: .8; }
	.lpc-header { display: flex; justify-content: space-between; align-items: center; gap: .4rem; }
	.lpc-details { display: flex; flex-wrap: wrap; gap: .4rem; align-items: center; }
	.lpc-occupant { font-size: .82rem; color: var(--color-text-muted); }

	/* Locataire cards */
	.locataire-card { padding: 1rem 1.2rem; margin-bottom: .6rem; }
	.loc-header { display: flex; flex-direction: column; gap: .3rem; margin-bottom: .6rem; }
	.loc-name { display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; font-size: .95rem; }
	.loc-contact { display: flex; flex-wrap: wrap; gap: .6rem; align-items: center; }
	.loc-lots { border-top: 1px solid var(--color-border); padding-top: .5rem; display: flex; flex-direction: column; gap: .35rem; margin-bottom: .5rem; }
	.loc-lot-row { display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; padding: .3rem .5rem; background: var(--color-bg-alt, #f8fafc); border-radius: var(--radius); }

	/* Main tabs (like communauté) */
	.tabs { display: flex; gap: .4rem; border-bottom: 2px solid var(--color-border); padding-bottom: .1rem; }
	.tabs button { padding: .45rem 1rem; border: none; background: none; cursor: pointer; font-size: .9rem; color: var(--color-text-muted); border-bottom: 2px solid transparent; margin-bottom: -2px; border-radius: var(--radius) var(--radius) 0 0; }
	.tabs button:hover { color: var(--color-text); background: var(--color-bg); }
	.tabs button.active { color: var(--color-primary); font-weight: 600; border-bottom-color: var(--color-primary); }

	/* Bail sub-tabs */
	.bail-tabs { display: flex; gap: 0.25rem; border-bottom: 2px solid var(--color-border); }
	.bail-tabs button { background: none; border: none; padding: 0.5rem 1rem; cursor: pointer; font-size: 0.9rem; color: var(--color-text-muted); border-bottom: 2px solid transparent; margin-bottom: -2px; transition: color 0.15s; }
	.bail-tabs button:hover { color: var(--color-text); background: var(--color-bg); }
	.bail-tabs button.active { color: var(--color-primary); border-bottom-color: var(--color-primary); font-weight: 600; }

	/* Lot multi-checklist */
	.lot-checklist {
		display: flex;
		flex-direction: column;
		gap: .25rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		overflow: hidden;
	}
	.lot-check-item {
		display: flex;
		align-items: center;
		gap: .65rem;
		padding: .5rem .75rem;
		cursor: pointer;
		background: var(--color-bg);
		border-bottom: 1px solid var(--color-border);
		transition: background .1s;
	}
	.lot-check-item:last-child { border-bottom: none; }
	.lot-check-item:hover:not(.disabled) { background: color-mix(in srgb, var(--color-primary) 5%, var(--color-bg)); }
	.lot-check-item.disabled { opacity: .55; cursor: default; }
	.lot-check-label { display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; font-size: .9rem; line-height: 1.3; }
	.lot-check-name { flex: 1; }
	.lot-selection-hint { font-size: .8rem; color: var(--color-primary); margin-top: .35rem; }
	.mode-personnel-note {
		margin: .6rem 0 .9rem;
		padding: .55rem .75rem;
		font-size: .84rem;
		color: var(--color-text-muted);
		background: var(--color-bg-alt, #f8fafc);
		border: 1px solid var(--color-border);
		border-left: 3px solid var(--color-primary);
		border-radius: var(--radius);
	}

	/* Modal overlay + structure */
	.modal-overlay { position: fixed; top: 0; right: 0; bottom: 0; left: 0; background: rgba(0,0,0,.45); display: flex; align-items: center; justify-content: center; z-index: 200; }
	.modal { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius); padding: 1.5rem; max-height: 90vh; overflow-y: auto; }
	.modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
	.modal-header h3 { font-size: 1.05rem; font-weight: 600; margin: 0; }
	.modal-close { background: none; border: none; font-size: 1.3rem; cursor: pointer; color: var(--color-text-muted); padding: 0; line-height: 1; }
	.modal-close:hover { color: var(--color-text); }
	.modal-body { margin-bottom: 1rem; display: flex; flex-direction: column; gap: .85rem; }
	.modal-footer { display: flex; justify-content: flex-end; gap: 0.5rem; padding-top: 0.75rem; border-top: 1px solid var(--color-border); }

	/* Grille 2 colonnes pour les champs de formulaire */
	.form-grid-2 {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: .75rem;
	}
	.form-group { display: flex; flex-direction: column; gap: .3rem; }
	.form-group label { font-size: .85rem; font-weight: 500; color: var(--color-text-muted); }
	.form-group input,
	.form-group select,
	.form-group textarea {
		padding: .42rem .6rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		font-size: .9rem;
		background: var(--color-bg);
		width: 100%;
		box-sizing: border-box;
	}
	.form-group input[readonly] { background: var(--color-surface-alt, #f8f9fa); color: var(--color-text-muted); cursor: default; }

	/* Bloc recherche locataire */
	.search-locataire-box {
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: .75rem .85rem;
		background: var(--color-surface-alt, #f8f9fa);
		margin: 0;
	}
	.search-locataire-box legend {
		font-size: .82rem;
		font-weight: 600;
		padding: 0 .3rem;
		color: var(--color-text);
	}
	.optional-hint { font-weight: 400; color: var(--color-text-muted); }
	.search-locataire-row { display: flex; gap: .5rem; margin-top: .4rem; }
	.search-locataire-row input {
		flex: 1;
		padding: .42rem .6rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		font-size: .9rem;
		background: var(--color-bg);
	}
	.search-no-result { font-size: .82rem; color: var(--color-danger, #dc2626); margin-top: .45rem; }
	.locataire-resultats {
		list-style: none;
		margin: .5rem 0 0;
		padding: 0;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		overflow: hidden;
	}
	.locataire-resultats li + li { border-top: 1px solid var(--color-border); }
	.locataire-resultat-btn {
		width: 100%;
		text-align: left;
		background: var(--color-bg);
		border: none;
		padding: .5rem .75rem;
		cursor: pointer;
		display: flex;
		align-items: center;
		gap: .75rem;
		flex-wrap: wrap;
		transition: background .1s;
	}
	.locataire-resultat-btn:hover { background: color-mix(in srgb, var(--color-primary) 6%, var(--color-bg)); }
	.lr-name { font-weight: 600; font-size: .88rem; }
	.lr-email { font-size: .8rem; color: var(--color-text-muted); }
	.locataire-selected {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: .5rem;
		flex-wrap: wrap;
		margin-top: .4rem;
		padding: .45rem .6rem;
		background: color-mix(in srgb, var(--color-success, #16a34a) 8%, var(--color-bg));
		border: 1px solid color-mix(in srgb, var(--color-success, #16a34a) 35%, transparent);
		border-radius: var(--radius);
	}
	.locataire-selected-info { display: flex; flex-direction: column; gap: .1rem; }
	.locataire-selected-name { font-weight: 600; font-size: .88rem; }
	.locataire-selected-email { font-size: .78rem; color: var(--color-text-muted); }

	.locataire-edit-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: .8rem;
	}
	.locataire-edit-full {
		grid-column: 1 / -1;
	}
	.acces-presets {
		display: flex;
		flex-wrap: wrap;
		gap: .45rem;
		margin-bottom: .7rem;
	}
	.acces-filters {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: .35rem;
		margin-bottom: .7rem;
	}
	.chip-btn {
		border: 1px solid var(--color-border);
		background: var(--color-bg);
		padding: .2rem .55rem;
		border-radius: 999px;
		font-size: .78rem;
		cursor: pointer;
	}
	.chip-btn.active {
		border-color: var(--color-primary);
		color: var(--color-primary);
		background: color-mix(in srgb, var(--color-primary) 8%, var(--color-bg));
	}

	@media (max-width: 680px) {
		.locataire-edit-grid { grid-template-columns: 1fr; }
		.form-grid-2 { grid-template-columns: 1fr; }
		.search-locataire-row { flex-direction: column; }
	}

	.btn-xs { padding: 0.15rem 0.4rem; font-size: 0.75rem; }
</style>

