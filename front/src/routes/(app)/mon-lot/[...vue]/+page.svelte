<script lang="ts">
	import { nomAffiche } from '$lib/noms';
	import Pastille from '$lib/components/Pastille.svelte';
	import EntetePage from '$lib/components/EntetePage.svelte';
	import Modale from '$lib/components/Modale.svelte';
	import FormulaireBail from '$lib/components/FormulaireBail.svelte';
	import { onMount } from 'svelte';
	import { lots as lotsApi, bailleur as bailApi, ApiError } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { currentUser, isAdmin, isCS } from '$lib/stores/auth';
	import { getPageConfig, configStore, siteNomStore, defautsDePage } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';
	import { fmtDateShort as fmt } from '$lib/date';
	import Onglet from '$lib/components/Onglet.svelte';
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import BarreOnglets from '$lib/components/BarreOnglets.svelte';
	import { routeOnglet, routeSousOnglet } from '$lib/routes-onglets';
	import { TITRE_ARCHIVES } from '$lib/archives';

	$: _pc = getPageConfig($configStore, 'mon-lot', defautsDePage('mon-lot'));
	$: _siteNom = $siteNomStore;
	//  Deux lectures d'un même droit : le masquage dit ce qui s'AFFICHE, la
	//  redirection ce qui s'ATTEINT. Depuis que la gestion locative a une adresse,
	//  la seconde ne va plus de soi — un lien reçu par un locataire ouvrirait
	//  l'onglet que la barre lui cache.
	$: isBailleur = $currentUser?.statut === 'copropriétaire_bailleur';
	$: isResident = $currentUser?.statut === 'copropriétaire_résident';

	const ROUTE_BAUX_ACTIFS = routeSousOnglet('mon-lot', 'location', 'actif');
	const ROUTE_BAUX_ARCHIVES = routeSousOnglet('mon-lot', 'location', 'archives');

	// ── Onglet principal ───────────────────────────────────────────────────────
	//  L'onglet ET son sous-onglet viennent du CHEMIN — `/mon-lot/location/archives`
	//  est une adresse à part entière, qu'on peut envoyer. Le `load` les résout ;
	//  cet écran ne fait que les lire.
	export let data: { onglet: string; sous: string | null };
	$: mainTab = data.onglet;
	$: bailTab = data.sous ?? 'actif';
	$: peutGererLocation = isBailleur || $isAdmin || $isCS || (isResident && bauxTermines.length > 0);
	$: if (browser && !bauxLoading && mainTab === 'location' && !peutGererLocation) {
		goto(routeOnglet('mon-lot', 'lots'), { replaceState: true });
	}

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
		? (lots.find((l) => l.id === (bailAcces?.lot_id ?? -1)) ?? null)
		: null;

	// ── State (gestion locative) ──────────────────────────────────────────────
	let baux: Bail[] = [];
	let bauxLoading = true;

	// Nouveau bail
	let showNewBail = false;
	let newBailLotIds = new Set<number>();
	let newBail = {
		locataire_nom: '',
		locataire_prenom: '',
		locataire_email: '',
		locataire_telephone: '',
		date_entree: '',
		date_sortie_prevue: '',
		notes: '',
	};
	let savingBail = false;
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
	let editLocataire = {
		locataire_nom: '',
		locataire_prenom: '',
		locataire_email: '',
		locataire_telephone: '',
		date_sortie_prevue: '',
		notes: '',
	};
	let editLocataireId: number | null = null;

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
			} catch {
				/* pas de bail */
			}
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
			toast('error', "Sélectionnez au moins un lot et renseignez la date d'entrée");
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
			newBail = {
				locataire_nom: '',
				locataire_prenom: '',
				locataire_email: '',
				locataire_telephone: '',
				date_entree: '',
				date_sortie_prevue: '',
				notes: '',
			};
			//  L'état de la RECHERCHE de locataire vit dans `FormulaireBail` : il
			//  n'a d'existence que pendant la saisie. Le formulaire est démonté par
			//  `showNewBail = false`, donc il repart vierge — rien à réinitialiser
			//  ici, et surtout rien à réinitialiser DEUX fois.
			newBailLocataireId = null;
			toast(
				'success',
				nouvellesBaux.length > 1 ? `${nouvellesBaux.length} baux créés` : 'Bail créé',
			);
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			savingBail = false;
		}
	}

	async function confirmerTerminer() {
		if (!bailATerminer) return;
		try {
			const updated = await bailApi.terminerBail(bailATerminer.id, {
				date_sortie_reelle: dateSortie || null,
			});
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
		//  L'état de la recherche — compte associé, résultats, suggestions — vit
		//  dans `FormulaireBail` : il n'existe que pendant la saisie, et le
		//  formulaire est monté à l'ouverture, démonté à la fermeture.
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
		} catch {
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
			toast(
				'error',
				e instanceof ApiError ? e.message : "Erreur lors de l'affectation automatique",
			);
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

	function toggleFiltreLot(lotId: number) {
		if (filtreLotsAcces.has(lotId)) filtreLotsAcces.delete(lotId);
		else filtreLotsAcces.add(lotId);
		filtreLotsAcces = new Set(filtreLotsAcces);
	}

	async function transfererAcces() {
		if (!bailAcces) return;
		const tVigik = [...selectionVigik].filter((id) => {
			const a = accesListe.find((x) => x.type === 'vigik' && x.id === id);
			return a && !a.chez_locataire;
		});
		const tTc = [...selectionTc].filter((id) => {
			const a = accesListe.find((x) => x.type === 'telecommande' && x.id === id);
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
		const rVigik = [...selectionVigik].filter((id) => {
			const a = accesListe.find((x) => x.type === 'vigik' && x.id === id);
			return a?.chez_locataire;
		});
		const rTc = [...selectionTc].filter((id) => {
			const a = accesListe.find((x) => x.type === 'telecommande' && x.id === id);
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
	$: accesFiltres = accesListe.filter(
		(a) => filtreLotsAcces.size === 0 || (a.lot_id != null && filtreLotsAcces.has(a.lot_id)),
	);

	$: nTransfert =
		[...selectionVigik].filter((id) => {
			const a = accesListe.find((x) => x.type === 'vigik' && x.id === id);
			return a && !a.chez_locataire;
		}).length +
		[...selectionTc].filter((id) => {
			const a = accesListe.find((x) => x.type === 'telecommande' && x.id === id);
			return a && !a.chez_locataire;
		}).length;
	$: nRecuperation =
		[...selectionVigik].filter(
			(id) => accesListe.find((x) => x.type === 'vigik' && x.id === id)?.chez_locataire,
		).length +
		[...selectionTc].filter(
			(id) => accesListe.find((x) => x.type === 'telecommande' && x.id === id)?.chez_locataire,
		).length;

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
			return nomAffiche(bail.locataire_prenom, bail.locataire_nom);
		}
		return 'Locataire non renseigné';
	}

	function lotTypeLabel(t: string | null | undefined): string {
		if (!t) return '—';
		if (t === 'appartement') return 'Appartement';
		if (t === 'parking') return 'Parking';
		if (t === 'cave') return 'Cave';
		return t;
	}

	//  Les lots tels que `FormulaireBail` les attend : un libellé et un état.
	//  🔴 La préparation vit ICI, pas dans le composant : `lotLabel` s'appuie sur
	//  `lotTypeLabel`, qui sert encore à l'affichage des accès plus bas. L'emporter
	//  dans le composant en aurait fait une deuxième écriture.
	$: lotsACocher = lots.map((l) => ({
		id: l.id,
		libelle: lotLabel(l),
		occupe: !!bauxActifs.find((b) => b.lot_id === l.id),
	}));

	function lotLabel(lot: LotDetail): string {
		const bat = lot.batiment_nom ?? '—';
		const type = lotTypeLabel(lot.type);
		const sub = lot.type_appartement ? ` ${lot.type_appartement}` : '';
		const etage = lot.etage !== null ? (lot.etage === 0 ? ' · RDC' : ` · Ét. ${lot.etage}`) : '';
		const surface = lot.superficie ? ` · ${lot.superficie} m²` : '';
		return `${bat} — ${type}${sub} n°${lot.numero}${etage}${surface}`;
	}
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<EntetePage titre={_pc.titre} icone={_pc.icone || 'door-closed'}>
	{#if mainTab === 'location'}
		<button class="btn btn-primary page-header-btn" on:click={() => (showNewBail = true)}
			>+ Nouveau bail</button
		>
	{/if}
</EntetePage>
<div class="page-subtitle">{@html safeHtml(_pc.descriptif)}</div>

{#if peutGererLocation}
	<BarreOnglets pageId="mon-lot" actif={mainTab} />
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
					Votre propriétaire doit vous rattacher depuis la section <strong>Gestion locative</strong> de
					son espace.
				</p>
			{:else}
				<p style="font-size:.85rem;color:var(--color-text-muted);margin-top:.5rem">
					Si votre compte vient d'être validé, la liaison se fait automatiquement.<br />
					Si aucun lot n'apparaît, contactez le gestionnaire du site ou
					<a href="/tickets?nouveau=1" style="color:var(--color-primary)"
						>faites une nouvelle demande</a
					>.
				</p>
			{/if}
		</div>
	{:else if isLocataire}
		<!-- ── Vue locataire : lot loué via bail ── -->
		{#if monBailData}
			<div class="lots-section-label">🏠 Lot loué</div>
			<div class="card largeur-saisie" style="margin-bottom:1.5rem">
				<div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.75rem">
					<span class="lbc-lot-badge"
						>{monBailData.lot_batiment_nom ?? '—'} / {monBailData.lot_numero ?? '—'}</span
					>
					<span class="badge badge-green" style="font-size:.72rem"
						>{monBailData.statut === 'actif'
							? 'Bail actif'
							: monBailData.statut.replace('_', ' ')}</span
					>
				</div>
				<dl class="details-grid">
					<dt>Bâtiment</dt>
					<dd>{monBailData.lot_batiment_nom ?? '—'}</dd>
					{#if monBailData.lot_type}<dt>Type</dt>
						<dd style="text-transform:capitalize">
							{monBailData.lot_type.replace('_', ' ')}{monBailData.lot_type_appartement
								? ` – ${monBailData.lot_type_appartement}`
								: ''}
						</dd>{/if}
					{#if monBailData.lot_etage !== null && monBailData.lot_etage !== undefined}<dt>Étage</dt>
						<dd>{monBailData.lot_etage === 0 ? 'RDC' : monBailData.lot_etage}</dd>{/if}
					{#if monBailData.lot_superficie}<dt>Superficie</dt>
						<dd>{monBailData.lot_superficie} m²</dd>{/if}
					<dt>Entrée</dt>
					<dd>{fmt(monBailData.date_entree)}</dd>
					{#if monBailData.date_sortie_prevue}<dt>Sortie prévue</dt>
						<dd>{fmt(monBailData.date_sortie_prevue)}</dd>{/if}
				</dl>
				{#if monBailData.bailleur_nom || monBailData.bailleur_prenom}
					<div style="margin-top:.75rem;font-size:.85rem;color:var(--color-text-muted)">
						🏢 Propriétaire : <strong
							>{nomAffiche(monBailData.bailleur_prenom, monBailData.bailleur_nom)}</strong
						>
						{#if monBailData.bailleur_email}<br />📬
							<a href="mailto:{monBailData.bailleur_email}" style="color:var(--color-primary)"
								>{monBailData.bailleur_email}</a
							>{/if}
						{#if monBailData.bailleur_telephone}<br />📞 {monBailData.bailleur_telephone}{/if}
					</div>
				{/if}
			</div>
		{:else}
			<div class="empty-state">
				<h3>Aucun bail actif</h3>
				<p>
					Votre propriétaire doit vous rattacher depuis la section <strong>Gestion locative</strong> de
					son espace.
				</p>
			</div>
		{/if}

		<!-- Lots en propre du locataire (s'il en possède aussi) -->
		{#if lots.length > 0}
			<div class="lots-section-label" style="margin-top:1.5rem">
				🏢 Lots en propriété ({lots.length})
			</div>
			{#each lots as lot (lot.id)}
				<div class="card largeur-saisie" style="margin-bottom:1rem">
					<h2 style="font-size:1rem;font-weight:600;margin-bottom:.75rem">
						{lot.batiment_nom ?? '—'} / {lot.numero}
					</h2>
					<dl class="details-grid">
						<dt>Type</dt>
						<dd style="text-transform:capitalize">
							{lot.type.replace('_', ' ')}{lot.type_appartement ? ` – ${lot.type_appartement}` : ''}
						</dd>
						{#if lot.etage !== null}<dt>Étage</dt>
							<dd>{lot.etage === 0 ? 'RDC' : lot.etage}</dd>{/if}
						{#if lot.superficie}<dt>Superficie</dt>
							<dd>{lot.superficie} m²</dd>{/if}
					</dl>
				</div>
			{/each}
		{/if}
	{:else if isBailleur}
		<!-- ── Vue bailleur : lots possédés + locataires ── -->
		{@const lotsAvecBail = lots.map((l) => ({
			...l,
			bail: bauxActifs.find((b) => b.lot_id === l.id) ?? null,
		}))}
		{@const locatairesMap = (() => {
			const map = new Map();
			for (const b of bauxActifs) {
				const key = b.locataire_id ?? `ext_${b.id}`;
				if (!map.has(key)) map.set(key, { bail: b, baux: [] });
				map.get(key).baux.push(b);
			}
			return [...map.values()];
		})()}
		{@const lotsVacants = lots.filter((l) => !bauxActifs.find((b) => b.lot_id === l.id))}

		<!-- Section 1 : Tous les lots possédés -->
		<div class="lots-section-label">🏢 Lots possédés ({lots.length})</div>
		<div class="lots-possedes-grid">
			{#each lotsAvecBail as lot (lot.id)}
				<div
					class="lot-possede-card card"
					class:lot-occupe={!!lot.bail}
					class:lot-vacant={!lot.bail}
				>
					<div class="lpc-header">
						<span class="lbc-lot-badge">{lot.batiment_nom ?? '—'} / {lot.numero}</span>
						{#if lot.bail}
							<span class="badge badge-green" style="font-size:.7rem">Occupé</span>
						{:else}
							<span class="badge badge-gray" style="font-size:.7rem">Vacant</span>
						{/if}
					</div>
					<div class="lpc-details">
						<span class="badge badge-gray" style="font-size:.72rem;text-transform:capitalize"
							>{lot.type.replace('_', ' ')}{lot.type_appartement
								? ` – ${lot.type_appartement}`
								: ''}</span
						>
						{#if lot.etage !== null}<span style="font-size:.78rem;color:var(--color-text-muted)"
								>Étage {lot.etage === 0 ? 'RDC' : lot.etage}</span
							>{/if}
						{#if lot.superficie}<span style="font-size:.78rem;color:var(--color-text-muted)"
								>{lot.superficie} m²</span
							>{/if}
					</div>
					{#if lot.bail}
						<div class="lpc-occupant">👤 {nomLocataire(lot.bail)}</div>
					{:else}
						<button
							class="btn btn-sm btn-primary"
							style="margin-top:.4rem"
							on:click={() => {
								newBailLotIds = new Set([lot.id]);
								showNewBail = true;
								goto(ROUTE_BAUX_ACTIFS);
							}}
						>
							+ Créer un bail
						</button>
					{/if}
				</div>
			{/each}
		</div>

		<!-- Section 2 : Locataires (lots regroupés par locataire) -->
		{#if locatairesMap.length > 0}
			<div class="lots-section-label" style="margin-top:1.8rem">
				👥 Locataires ({locatairesMap.length})
			</div>
			{#each locatairesMap as loc (loc.bail.locataire_id ?? `ext_${loc.bail.id}`)}
				{@const premierBail = loc.bail}
				<div class="locataire-card card">
					<div class="loc-header">
						<div class="loc-name">
							👤 <strong>{nomLocataire(premierBail)}</strong>
							<span
								class="badge {premierBail.statut === 'actif' ? 'badge-green' : 'badge-yellow'}"
								style="font-size:.7rem"
								>{statutBailLabel[premierBail.statut] ?? premierBail.statut}</span
							>
						</div>
						<div class="loc-contact">
							{#if premierBail.locataire_email}<a
									href="mailto:{premierBail.locataire_email}"
									style="color:var(--color-primary);font-size:.82rem"
									>📬 {premierBail.locataire_email}</a
								>{/if}
							{#if premierBail.locataire_telephone}<span
									style="font-size:.82rem;color:var(--color-text-muted)"
									>📞 {premierBail.locataire_telephone}</span
								>{/if}
						</div>
					</div>
					<div class="loc-lots">
						{#each loc.baux as bail (bail.id)}
							{@const lot = lots.find((l) => l.id === bail.lot_id)}
							{#if lot}
								<div class="loc-lot-row">
									<span class="lbc-lot-badge">{lot.batiment_nom ?? '—'} / {lot.numero}</span>
									<span class="badge badge-gray" style="font-size:.7rem;text-transform:capitalize"
										>{lot.type.replace('_', ' ')}{lot.type_appartement
											? ` – ${lot.type_appartement}`
											: ''}</span
									>
									<span style="font-size:.78rem;color:var(--color-text-muted)"
										>Depuis le {fmt(bail.date_entree)}{bail.date_sortie_prevue
											? ` · Sortie prévue ${fmt(bail.date_sortie_prevue)}`
											: ''}</span
									>
								</div>
							{/if}
						{/each}
					</div>
					<div class="lbc-actions">
						<button class="btn btn-sm btn-outline" on:click={() => goto(ROUTE_BAUX_ACTIFS)}
							>📋 Gestion locative</button
						>
						<button class="btn btn-sm btn-outline" on:click={() => ouvrirAccesBail(premierBail)}
							>🔑 Accès</button
						>
						<button
							class="btn btn-sm btn-outline"
							on:click={() => ouvrirEditionLocataire(premierBail)}>✏️ Modifier</button
						>
					</div>
				</div>
			{/each}
		{/if}

		<!-- Lots vacants (rappel rapide) -->
		{#if lotsVacants.length > 0}
			<div class="lots-section-label" style="margin-top:1.8rem">
				🔓 Lots vacants ({lotsVacants.length})
			</div>
			<p style="font-size:.85rem;color:var(--color-text-muted);margin:0 0 .6rem">
				Ces lots n'ont pas de bail actif. Créez un bail depuis la fiche du lot ci-dessus ou l'onglet <strong
					>Gestion locative</strong
				>.
			</p>
		{/if}
	{:else}
		<!-- ── Vue standard (non bailleur) : sélecteur lot + carte ── -->
		{#if lots.length > 1}
			<div class="lot-tabs" role="tablist">
				{#each lots as lot (lot.id)}
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
			<div class="card largeur-saisie" style="margin-bottom:1.5rem">
				<h2 style="font-size:1rem;font-weight:600;margin-bottom:1rem">Caractéristiques</h2>
				<dl class="details-grid">
					<dt>Lot</dt>
					<dd>{selectedLot.numero}</dd>
					<dt>Bâtiment</dt>
					<dd>{selectedLot.batiment_nom ?? '—'}</dd>
					<dt>Type</dt>
					<dd style="text-transform:capitalize">
						{selectedLot.type.replace('_', ' ')}{selectedLot.type_appartement
							? ` – ${selectedLot.type_appartement}`
							: ''}
					</dd>
					{#if selectedLot.etage !== null}<dt>Étage</dt>
						<dd>{selectedLot.etage === 0 ? 'RDC' : selectedLot.etage}</dd>{/if}
					{#if selectedLot.superficie}<dt>Superficie</dt>
						<dd>{selectedLot.superficie} m²</dd>{/if}
				</dl>
			</div>
		{/if}
	{/if}
{/if}

<!-- ── Onglet : Gestion locative ────────────────────────────────────── -->
{#if mainTab === 'location'}
	<div style="max-width:900px">
		<!--  🔴 LA BOÎTE DANS LA PAGE, et non une modale (#367 / #672).

		      « Nouveau bail » était la dernière modale de création du site. Elle y
		      avait échappé parce que `lint:formulaires` ne cherchait qu'un `<form>`,
		      et ce formulaire n'en porte aucun — seulement des `.field`.

		      ⚠️ Le corps vit dans `FormulaireBail.svelte` : cette page pesait 2 229
		      lignes, et le contrôle de modularité refusait d'y ajouter la moindre
		      ligne. Comme les huit refus précédents, il désignait un PLACEMENT — la
		      saisie d'un bail n'a rien à faire dans l'écran qui liste les lots, les
		      baux, les accès et les diagnostics. -->
		{#if showNewBail}
			<FormulaireBail
				lots={lotsACocher}
				bind:lotIds={newBailLotIds}
				bind:bail={newBail}
				bind:locataireId={newBailLocataireId}
				enregistrement={savingBail}
				on:annuler={() => (showNewBail = false)}
				on:enregistrer={creerBail}
			/>
		{/if}

		<!--  Deux LIENS, pas deux boutons : le sous-onglet a une adresse, donc il
		      s'envoie, le bouton Précédent le retrouve et le clic milieu l'ouvre à
		      côté. Et c'est `Onglet` qui les rend : `.bail-tabs` était une rangée
		      d'onglets de plus, avec ses 25 lignes de style et sans les trois marques
		      de l'onglet actif (`ux-patterns` §4 bis). -->
		<div class="tabs sous-onglets">
			<Onglet href={ROUTE_BAUX_ACTIFS} actif={bailTab === 'actif'}>
				Baux actifs ({bauxActifs.length})
			</Onglet>
			<Onglet href={ROUTE_BAUX_ARCHIVES} actif={bailTab === 'archives'}>
				{TITRE_ARCHIVES} ({bauxTermines.length})
			</Onglet>
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
				{#each grouped as group (group)}
					{@const premierBail = group.bail}
					<div class="card" style="margin-bottom:1.5rem;padding:1.25rem">
						<!-- En-tête locataire -->
						<div
							style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:1rem"
						>
							<div>
								<div style="font-weight:700;font-size:1rem">{nomLocataire(premierBail)}</div>
								{#if premierBail.locataire_email}
									<div style="font-size:0.82rem;color:var(--color-text-muted)">
										{premierBail.locataire_email}
									</div>
								{/if}
								{#if premierBail.locataire_telephone}
									<div style="font-size:0.82rem;color:var(--color-text-muted)">
										{premierBail.locataire_telephone}
									</div>
								{/if}
							</div>
							<div style="display:flex;gap:0.5rem;flex-wrap:wrap;justify-content:flex-end">
								<span
									class="badge {premierBail.statut === 'actif'
										? 'badge-green'
										: premierBail.statut === 'en_cours_sortie'
											? 'badge-yellow'
											: 'badge-gray'}"
								>
									{statutBailLabel[premierBail.statut] ?? premierBail.statut}
								</span>
							</div>
						</div>

						<!-- Actions globales locataire -->
						{#if premierBail.statut !== 'termine'}
							<div style="display:flex;gap:0.5rem;margin-bottom:1.25rem;flex-wrap:wrap">
								<button class="btn btn-sm" on:click={() => ouvrirEditionLocataire(premierBail)}
									>✏️ Modifier</button
								>
								<button class="btn btn-sm" on:click={() => ouvrirAccesBail(premierBail)}
									>&#x1F511; Accès</button
								>
							</div>
						{/if}

						<!-- Détails par bail (lot) -->
						{#each group.baux as bail (bail.id)}
							{@const lot = lots.find((l) => l.id === bail.lot_id)}
							<div
								style="border-top:1px solid var(--color-border);padding-top:1rem;margin-top:1rem"
							>
								<div
									style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.6rem;flex-wrap:wrap;gap:.5rem"
								>
									<div style="display:flex;align-items:center;gap:.5rem;flex-wrap:wrap">
										{#if lot}
											<span class="lbc-lot-badge">{lot.batiment_nom ?? '—'} / {lot.numero}</span>
											<span
												class="badge badge-gray"
												style="font-size:.72rem;text-transform:capitalize"
												>{lot.type.replace('_', ' ')}{lot.type_appartement
													? ` – ${lot.type_appartement}`
													: ''}</span
											>
										{/if}
										{#if group.baux.length > 1}
											<span
												class="badge {bail.statut === 'actif'
													? 'badge-green'
													: bail.statut === 'en_cours_sortie'
														? 'badge-yellow'
														: 'badge-gray'}"
												style="font-size:.7rem"
											>
												{statutBailLabel[bail.statut] ?? bail.statut}
											</span>
										{/if}
									</div>
									{#if bail.statut !== 'termine'}
										<button
											class="btn btn-xs btn-outline"
											on:click={() => affecterAuto(bail)}
											title="Affecter automatiquement les accès recommandés"
										>
											⚡ Auto
										</button>
										<button
											class="btn btn-xs btn-danger"
											on:click={() => {
												bailATerminer = bail;
												dateSortie = '';
											}}
										>
											Terminer
										</button>
									{/if}
									{#if $isAdmin || $isCS}
										<button
											class="btn btn-xs btn-danger"
											on:click={() => {
												bailASupprimer = bail;
											}}
										>
											🗑️ Supprimer
										</button>
									{/if}
								</div>

								<div
									style="display:flex;gap:2rem;font-size:0.85rem;margin-bottom:.75rem;flex-wrap:wrap"
								>
									<span><strong>Entrée :</strong> {fmt(bail.date_entree)}</span>
									<span><strong>Sortie prévue :</strong> {fmt(bail.date_sortie_prevue)}</span>
									{#if bail.date_sortie_reelle}
										<span><strong>Sortie réelle :</strong> {fmt(bail.date_sortie_reelle)}</span>
									{/if}
								</div>

								{#if bail.notes}
									<div
										class="rich-content"
										style="font-size:0.85rem;color:var(--color-text-muted);margin-bottom:.75rem;font-style:italic"
									>
										{@html safeHtml(bail.notes)}
									</div>
								{/if}

								<div>
									<div style="font-weight:600;font-size:0.9rem;margin-bottom:0.5rem">
										Inventaire ({bail.objets.length} objet{bail.objets.length !== 1 ? 's' : ''})
									</div>
									{#if bail.objets.length === 0}
										<p style="font-size:0.83rem;color:var(--color-text-muted)">
											Aucun objet enregistré.
										</p>
									{:else}
										<div class="table-wrap">
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
																<span
																	class="badge {statutObjetBadge[objet.statut] ?? 'badge-gray'}"
																>
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
																				on:click={() => {
																					objetRetour = objet;
																					retourDate = '';
																					retourPerdu = false;
																				}}>↩</button
																			>
																		{/if}
																		<button
																			class="btn btn-xs btn-danger"
																			title="Supprimer"
																			on:click={() => supprimerObjet(bail, objet)}>✕</button
																		>
																	</div>
																</td>
															{/if}
														</tr>
													{/each}
												</tbody>
											</table>
										</div>
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

<!-- ── Modal : terminer bail ────────────────────────────────────────── -->
{#if bailATerminer}
	<Modale
		edition
		titre="Terminer le bail"
		styleBoite="width:min(400px,95vw)"
		on:fermer={() => (bailATerminer = null)}
	>
		<div class="modal-body">
			<p style="margin-bottom:0.75rem">
				Confirmer la fin du bail de <strong>{nomLocataire(bailATerminer)}</strong> ?
			</p>
			<div class="field">
				<label for="tb-sortie">Date de sortie réelle</label>
				<input id="tb-sortie" type="date" bind:value={dateSortie} />
			</div>
		</div>
		<div class="modal-footer">
			<button class="btn" on:click={() => (bailATerminer = null)}>Annuler</button>
			<button class="btn btn-danger" on:click={confirmerTerminer}>Terminer</button>
		</div>
	</Modale>
{/if}

<!-- ── Modal : supprimer bail (admin) ──────────────────────────────── -->
{#if bailASupprimer}
	<Modale
		titre="Supprimer le bail"
		styleBoite="width:min(400px,95vw)"
		on:fermer={() => (bailASupprimer = null)}
	>
		<div class="modal-body">
			<p>
				Supprimer définitivement le bail de <strong>{nomLocataire(bailASupprimer)}</strong> et tous ses
				objets associés ?
			</p>
			<p style="color:var(--color-danger);font-size:0.85rem;margin-top:0.5rem">
				Cette action est irréversible.
			</p>
		</div>
		<div class="modal-footer">
			<button class="btn" on:click={() => (bailASupprimer = null)}>Annuler</button>
			<button class="btn btn-danger" on:click={confirmerSupprimer}>Supprimer</button>
		</div>
	</Modale>
{/if}

<!-- ── Correction d'un bail : LE MÊME formulaire, en modale ─────────── -->
<!--  🔴 Il était écrit une SECONDE fois ici (01/09/2026, #672) : mêmes champs,
      même recherche de locataire, six variables d'état en double et trois
      fonctions recopiées. Deux écritures du même formulaire, et rien pour dire
      qu'elles avaient divergé — c'est le défaut qui a fait qu'un sélecteur de
      périmètre de plan écrivait dans la variable du CR d'AG (#453).

      `avecLots` et `avecDateEntree` portent les DEUX seules différences : un
      bail existant ne change ni de lot ni de date d'entrée. -->
{#if bailEdite}
	<FormulaireBail
		edition
		intitule="Modifier les informations"
		bind:bail={editLocataire}
		bind:locataireId={editLocataireId}
		on:annuler={() => (bailEdite = null)}
		on:enregistrer={sauvegarderLocataire}
	/>
{/if}

<!-- ── Modal : retour objet ─────────────────────────────────────────── -->
{#if objetRetour}
	<Modale
		edition
		titre={`Retour — ${objetRetour.libelle}`}
		styleBoite="width:min(380px,95vw)"
		on:fermer={() => (objetRetour = null)}
	>
		<div class="modal-body">
			<div class="field">
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
			<button class="btn {retourPerdu ? 'btn-danger' : 'btn-primary'}" on:click={confirmerRetour}>
				{retourPerdu ? 'Perdu' : 'Retour confirmé'}
			</button>
		</div>
	</Modale>
{/if}

<!-- ── Modal : gestion des accès (Vigik / TC) ───────────────────────── -->
{#if bailAcces}
	<Modale
		edition
		titre={`Accès — ${nomLocataire(bailAcces)}`}
		styleBoite="width:min(620px,95vw)"
		on:fermer={() => (bailAcces = null)}
	>
		<div class="modal-body">
			{#if loadingAcces}
				<p style="color:var(--color-text-muted)">Chargement…</p>
			{:else if bailAccesLot && (bailAccesLot.type === 'parking' || bailAccesLot.type === 'cave')}
				<p
					style="font-size:0.85rem;color:#92400e;background:#fef3c7;border:1px solid #fde68a;border-radius:8px;padding:.5rem .65rem;margin-bottom:.7rem"
				>
					Ce bail concerne un {bailAccesLot.type}. <strong>TC uniquement</strong> : les Vigik ne sont
					pas autorisés.
				</p>
			{:else if accesListe.length === 0}
				<p style="color:var(--color-text-muted);font-size:0.9rem">
					Aucun Vigik ni télécommande rattaché à ce lot.
				</p>
			{:else}
				<p style="font-size:0.85rem;color:var(--color-text-muted);margin-bottom:0.6rem">
					Sélection intelligente : utilisez un préréglage puis ajustez manuellement. Les règles de
					cohérence sont appliquées automatiquement (ex. pas de Vigik pour un bail parking seul).
				</p>
				<div class="acces-presets">
					<button class="btn btn-sm" on:click={preselectionRecommandee}
						>✨ Préselection recommandée</button
					>
					<button class="btn btn-sm btn-outline" on:click={clearSelection}>Effacer</button>
				</div>
				{#if lotsSourcesAcces.length > 1}
					<div class="acces-filters">
						<span style="font-size:.78rem;color:var(--color-text-muted)">Filtrer lots source :</span
						>
						{#each lotsSourcesAcces as ls (ls.id)}
							<Pastille active={filtreLotsAcces.has(ls.id)} on:click={() => toggleFiltreLot(ls.id)}
								>{ls.label}</Pastille
							>
						{/each}
					</div>
				{/if}
				<div class="table-wrap">
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
												checked={acces.type === 'vigik'
													? selectionVigik.has(acces.id)
													: selectionTc.has(acces.id)}
												on:change={() => toggleAcces(acces.type, acces.id)}
											/>
										{/if}
									</td>
									<td
										>{acces.lot_label ?? '—'}
										<span class="badge badge-gray" style="margin-left:.25rem"
											>{lotTypeLabel(acces.lot_type)}</span
										></td
									>
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
											<span class="badge badge-gray" title={acces.motif_non_eligible}
												>{acces.motif_non_eligible}</span
											>
										{/if}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
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
				<button class="btn btn-primary" on:click={recupererSelection}>
					↩ Récupérer ({nRecuperation})
				</button>
			{/if}
			{#if nTransfert > 0}
				<button class="btn btn-primary" on:click={transfererAcces}>
					Transférer ({nTransfert})
				</button>
			{/if}
		</div>
	</Modale>
{/if}

<style>
	/* Lot tabs (multi-lot selector) */
	.lot-tabs {
		display: flex;
		gap: 0.5rem;
		margin-bottom: 1rem;
		flex-wrap: wrap;
	}
	.lot-tabs button {
		padding: 0.4rem 0.9rem;
		border: 1px solid var(--color-border);
		background: var(--color-bg);
		border-radius: var(--radius);
		cursor: pointer;
		font-size: 0.875rem;
		color: var(--color-text);
	}
	.lot-tabs button.active {
		background: var(--color-primary);
		color: #fff;
		border-color: var(--color-primary);
	}

	/* Lot characteristics */
	.details-grid {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.4rem 0.8rem;
		font-size: 0.875rem;
	}
	.details-grid dt {
		font-weight: 500;
		color: var(--color-text-muted);
	}
	.details-grid dd {
		margin: 0;
	}
	/* Bailleur lot cards */
	.lots-section-label {
		font-size: 0.78rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--color-text-muted);
		margin-bottom: 0.6rem;
	}
	.lot-bailleur-card {
		padding: 1rem 1.2rem;
		margin-bottom: 0.6rem;
	}
	.lot-vacant {
		opacity: 0.8;
		border-style: dashed;
	}
	.lbc-top {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
		margin-bottom: 0.5rem;
	}
	.lbc-lot-id {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.lbc-lot-badge {
		font-weight: 700;
		font-size: 0.92rem;
	}
	.lbc-tenant {
		border-top: 1px solid var(--color-border);
		padding-top: 0.6rem;
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
	}
	.lbc-tenant-name {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
		font-size: 0.92rem;
	}
	.lbc-tenant-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem;
		align-items: center;
	}
	.lbc-actions {
		display: flex;
		gap: 0.4rem;
		flex-wrap: wrap;
		margin-top: 0.3rem;
	}

	/* Lots possédés grid */
	.lots-possedes-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(220px, 100%), 1fr));
		gap: 0.6rem;
		margin-bottom: 0.6rem;
	}
	.lot-possede-card {
		padding: 0.85rem 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}
	.lot-possede-card.lot-occupe {
		border-left: 3px solid var(--color-success, #22c55e);
	}
	.lot-possede-card.lot-vacant {
		border-left: 3px dashed var(--color-border);
		opacity: 0.8;
	}
	.lpc-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.4rem;
	}
	.lpc-details {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		align-items: center;
	}
	.lpc-occupant {
		font-size: 0.82rem;
		color: var(--color-text-muted);
	}

	/* Locataire cards */
	.locataire-card {
		padding: 1rem 1.2rem;
		margin-bottom: 0.6rem;
	}
	.loc-header {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
		margin-bottom: 0.6rem;
	}
	.loc-name {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
		font-size: 0.95rem;
	}
	.loc-contact {
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem;
		align-items: center;
	}
	.loc-lots {
		border-top: 1px solid var(--color-border);
		padding-top: 0.5rem;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		margin-bottom: 0.5rem;
	}
	.loc-lot-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
		padding: 0.3rem 0.5rem;
		background: var(--color-bg-alt, #f8fafc);
		border-radius: var(--radius);
	}

	/* Main tabs (like communauté) */
	.tabs {
		padding-bottom: 0.1rem;
	} /* le reste vient de la charte (#607) */

	/* Bail sub-tabs */
	.sous-onglets {
		margin-bottom: 1.5rem;
	}

	/* Lot multi-checklist */
	.mode-personnel-note {
		margin: 0.6rem 0 0.9rem;
		padding: 0.55rem 0.75rem;
		font-size: 0.84rem;
		color: var(--color-text-muted);
		background: var(--color-bg-alt, #f8fafc);
		border: 1px solid var(--color-border);
		border-left: 3px solid var(--color-primary);
		border-radius: var(--radius);
	}

	/*  🔴 L'EN-TÊTE d'une modale ne s'écrit plus ici : `Modale.svelte` le rend, et
	    `styles/composants.css` le style (`.modal-titre`). #607 avait retiré
	    `.modal-header`, `.modal-close` et `.modal-footer` de ces trois écrans en
	    laissant `.modal-header h3` — la seule des quatre qui n'existait PAS en
	    global, donc la seule que le retrait ne pouvait pas solder. Elle a survécu
	    à l'identique dans les trois, et divergeait du `h2` de la charte. */

	/* Bloc recherche locataire */
	/*  Le champ vit dans un `.field champ-en-ligne` depuis le 28/08/2026 : il
	    repeignait `.field input` et perdait le focus de la charte (#593, volet
	    C). Ne reste ici que la répartition, propre à cette rangée. */

	.locataire-edit-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.8rem;
	}
	.acces-presets {
		display: flex;
		flex-wrap: wrap;
		gap: 0.45rem;
		margin-bottom: 0.7rem;
	}
	.acces-filters {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.35rem;
		margin-bottom: 0.7rem;
	}
	/*  🔴 `.chip-btn` retirée le 28/08/2026 (#491) : c'était la pastille de la
	    charte, sous un AUTRE NOM — donc invisible à toute recherche sur `pill`,
	    et libre de diverger sans que personne ne la rapproche de son modèle.
	    Elle avait déjà divergé : `.78rem`, `.2rem .55rem`, et un état actif en
	    teinte pâle là où la charte remplit la pastille. */

	@media (max-width: 680px) {
		.locataire-edit-grid {
			grid-template-columns: 1fr;
		}
		.search-locataire-row {
			flex-direction: column;
		}
	}
</style>
