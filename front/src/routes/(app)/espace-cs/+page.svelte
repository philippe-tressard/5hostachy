<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import EntetePage from '$lib/components/EntetePage.svelte';
	import Modale from '$lib/components/Modale.svelte';
	import ChargementPartiel from '$lib/components/ChargementPartiel.svelte';
	import ArchivesParAnnee from '$lib/components/ArchivesParAnnee.svelte';
	import OngletAnnoncesHall from '$lib/components/OngletAnnoncesHall.svelte';
	import { essayer, messagePartiel } from '$lib/chargement';
	import { onMount } from 'svelte';
	import { currentUser, isCS, isAdmin } from '$lib/stores/auth';
	import { goto } from '$app/navigation';
	import { admin as adminApi, annuaireAdmin, lots as lotsApi, api, tickets as ticketsApi, ApiError, type Ticket, type TicketEvolution } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { getPageConfig, configStore, siteNomStore, defautsDePage } from '$lib/stores/pageConfig';
	import { safeHtml, safeDescription } from '$lib/sanitize';
	import EvolForm from '$lib/components/EvolForm.svelte';
	import RubriqueHistorique from '$lib/components/RubriqueHistorique.svelte';
	import { fmtDate, fmtDateShort } from '$lib/date';
	import OngletReporting from '$lib/components/reporting/OngletReporting.svelte';
	import { trackTabView } from '$lib/telemetry';
	import ApercuTicket from '$lib/components/ApercuTicket.svelte';
	import { fichiersDepuisUrls, MAX_FICHIERS } from '$lib/fichiers';
	import { STATUT_TICKET_BADGE as TK_STATUT_BADGE, STATUT_TICKET_LABELS as TK_STATUT_LABELS, STATUT_TICKET_OPTIONS as TK_STATUT_OPTIONS, STATUTS_TICKET_FILTRE, estTicketClos } from '$lib/tickets';

	$: _pc = getPageConfig($configStore, 'espace-cs', defautsDePage('espace-cs'));
	$: _siteNom = $siteNomStore;

	interface PendingUser {
		id: number; prenom: string; nom: string;
		statut: string; batiment_id: number | null; cree_le: string;
		nom_aide?: string | null; prenom_aide?: string | null;
	}
	interface PendingAcces {
		id: number;
		lot: { reference: string; batiment: { nom: string } };
		proprietaire: { prenom: string; nom: string };
		type_acces: string; quantite: number; cree_le: string;
	}
	interface MembreCSForm {
		genre: string; prenom: string; nom: string;
		batiment_id: number | null; batiment_nom: string | null;
		etage: number | null; user_id: number | null;
		est_gestionnaire_site: boolean;
		est_president: boolean;
	}
	interface MembreSyndicForm {
		genre: string; prenom: string; nom: string;
		fonction: string; email: string; telephones: string[];
		est_principal: boolean; user_id: number | null;
	}
	interface SimpleUser {
		id: number; prenom: string; nom: string;
		email: string; telephone: string | null; batiment_id: number | null;
	}
	interface LotRow {
		id: number; numero: string; type: string;
		etage: number | null; batiment_id: number | null; batiment_nom: string | null;
	}

	// -- Onglet -------------------------------------------------------------
	let onglet: 'validations' | 'tickets' | 'reporting' | 'annonces-hall' | 'annuaire' = 'validations';
	/** Vue de reporting demandée par l'URL — c'est `OngletReporting` qui la valide. */
	let vueReporting: string | null = null;
	$: trackTabView(onglet);

	// -- Tickets ------------------------------------------------------------
	//  Renommée en extrayant le reporting (#453) : c'est la MÊME liste que lit
	//  `OngletReporting`, passée en prop plutôt que rechargée de son côté.
	let tickets: Ticket[] = [];
	let tkLoading = false;
	let tkLoaded = false;
	//  Type élargi : il énumérait les deux états filtrables, une écriture de plus
	//  de la même liste. Options : `STATUTS_TICKET_FILTRE` ; `''` vaut « Tous ».
	let tkFilter = '';
	let tkExpandedId: number | null = null;
	let tkEvolsMap: Record<number, TicketEvolution[]> = {};
	let tkEvolsLoaded = new Set<number>();
	let tkShowForm: number | null = null;
	let tkEvolSaving = false;
	let tkEditingEvolId: number | null = null;
	let tkEditEvolSaving = false;



	//  Badges, libellés et options du workflow : `$lib/tickets` (#415).
	const TK_CAT_ICON: Record<string, string> = { panne: '\u{1F6E0}️', nuisance: '\u{1F4E2}', question: '❓', urgence: '\u{1F6A8}', bug: '\u{1F41B}' };

	$: tkActive = tickets.filter(t => !estTicketClos(t.statut));
	$: tkFiltered = tkActive.filter(t => !tkFilter || t.statut === tkFilter);
	$: tkPendingCount = tickets.filter(t => t.statut === 'ouvert').length;

	const TK_THREE_YEARS_AGO = new Date();
	TK_THREE_YEARS_AGO.setFullYear(TK_THREE_YEARS_AGO.getFullYear() - 3);
	$: tkHistory = tickets
		.filter(t => estTicketClos(t.statut) && new Date(t.mis_a_jour_le ?? t.cree_le) >= TK_THREE_YEARS_AGO)
		.sort((a, b) => new Date(b.mis_a_jour_le ?? b.cree_le).getTime() - new Date(a.mis_a_jour_le ?? a.cree_le).getTime());
	//  ⚠️ Le groupement par année et l'état des années ouvertes sont partis dans
	//  `ArchivesParAnnee` : ce bloc en était la TROISIÈME copie, avec l'écran
	//  Tickets et le composant lui-même. Ce qui reste ici est le FILTRE — quels
	//  tickets sont archivés —, qui est propre à cet onglet.
	let tkHistoryExpanded = false;














	async function loadTickets() {
		if (tkLoaded) return;
		tkLoading = true;
		try {
			tickets = await ticketsApi.list();
			tkLoaded = true;
		} catch { toast('error', 'Erreur chargement tickets'); }
		finally { tkLoading = false; }
	}





	async function tkToggle(id: number) {
		if (tkExpandedId === id) { tkExpandedId = null; return; }
		tkExpandedId = id;
		tkShowForm = null;
		if (!tkEvolsLoaded.has(id)) await tkLoadEvols(id);
	}

	async function tkLoadEvols(id: number) {
		try {
			tkEvolsMap[id] = await ticketsApi.evolutions(id);
			tkEvolsLoaded = new Set([...tkEvolsLoaded, id]);
			tkEvolsMap = { ...tkEvolsMap };
		} catch { /* silencieux */ }
	}

	//  UN point d'entrée (#426) : le formulaire porte les deux gestes, et lequel a
	//  été fait se lit dans les pastilles de la section Workflow.
	function tkOpenForm(id: number) {
		tkShowForm = id;
		tkExpandedId = id;
	}

	async function tkSubmitEvol(t: Ticket, e: CustomEvent) {
		const data = e.detail;
		tkEvolSaving = true;
		try {
			await ticketsApi.addEvolution(t.id, {
				type: data.type,
				contenu: data.contenu || undefined,
				nouveau_statut: data.type === 'etat' ? data.nouveau_statut : undefined,
				fichiers_urls: data.fichiers_urls,
			});
			if (data.type === 'etat') {
				tickets = tickets.map(x => x.id === t.id ? { ...x, statut: data.nouveau_statut } : x);
			}
			await tkLoadEvols(t.id);
			tkShowForm = null;
			toast('success', data.type === 'etat' ? 'Statut mis à jour' : 'Commentaire ajouté');
		} catch (err: any) {
			toast('error', err instanceof ApiError ? err.message : 'Erreur');
		} finally { tkEvolSaving = false; }
	}

	async function tkSaveEvolEdit(ticketId: number, e: CustomEvent) {
		if (tkEditingEvolId === null) return;
		tkEditEvolSaving = true;
		try {
			await ticketsApi.updateEvolution(ticketId, tkEditingEvolId, {
				contenu: e.detail.contenu || undefined,
				fichiers_urls: e.detail.fichiers_urls,
			});
			await tkLoadEvols(ticketId);
			tkEditingEvolId = null;
			toast('success', 'Commentaire mis à jour');
		} catch { toast('error', 'Erreur de mise à jour'); }
		finally { tkEditEvolSaving = false; }
	}

	// -- Validations --------------------------------------------------------
	let batimentsMap: Record<number, string> = {};
	let comptesEnAttente: PendingUser[] = [];
	let commandesEnAttente: PendingAcces[] = [];
	let loading = true;
	$: nbComptes = comptesEnAttente.length;
	$: nbCommandes = commandesEnAttente.length;

	//  ⚠️ Les 31 symboles `ah*` vivent dans `OngletAnnoncesHall.svelte` depuis le
	//  20/08/2026 : ils ne servaient qu'à cet onglet, et l'onglet s'amorce seul.

	// -- Annuaire -----------------------------------------------------------
	/** Non vide = une donnée de référence manque : l'écran est faux, pas vide. */
	let erreurReference = '';
	let allUsers: SimpleUser[] = [];
	let allLots: LotRow[] = [];
	let annuaireLoading = false;

	// CS
	let agAnnee: number | null = null;
	let agDate = '';
	let membresCS: MembreCSForm[] = [];
	let savingCS = false;
	let savingCSIdx: number | null = null;
	let csOpenIdx: number | null = null;
	let csEditIdx: number | null = null;

	// Syndic
	let nomSyndic = '';
	let adresseSyndic = '';
	let siteWebSyndic = '';
	let membresSyndic: MembreSyndicForm[] = [];
	let savingSyndic = false;
	let savingSyndicIdx: number | null = null;
	let syndicOpenIdx: number | null = null;
	let syndicEditIdx: number | null = null;

	// WhatsApp
	let whatsappUrl = '';

	// -- Header inline-edit flags -----------------------------------------
	let csHeaderEditing = false;
	let syndicHeaderEditing = false;

	// -- Normalisation : minuscules sans accents (NFD) -----------------------
	function normalizeStr(s: string): string {
		return s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
	}

	// -- Liaison inscrit via NOM ------------------------------------------
	function findUserByNom(nom: string): SimpleUser | null {
		if (!nom || nom.length < 2) return null;
		const q = normalizeStr(nom);
		return allUsers.find(u => normalizeStr(u.nom) === q) ?? null;
	}

	// Cherche dans les LotImport (via lots.listImports) pour trouver bâtiment/étage
	let lotImports: any[] = [];
	// Conversion etage_raw brut → entier (même logique que le backend)
	function etageFromRaw(raw: string | null | undefined): number | null {
		if (raw == null) return null;
		const s = raw.trim().toUpperCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\s+/g, ' ');
		const map: Record<string, number> = {
			'RDC': 0, '0': 0,
			'1ER': 1, '1': 1,
			'2EME': 2, '2': 2,
			'3EME': 3, '3': 3,
			'4EME': 4, '4': 4,
			'5EME': 5, '5': 5,
			'6EME': 6, '6': 6,
			'7EME': 7, '7': 7,
			'1SS': -1, '-1': -1,
			'2SS': -2, '-2': -2,
		};
		return map[s] ?? null;
	}

	function findImportForNom(nom: string): { batiment_id: number | null; batiment_nom: string | null; etage: number | null } | null {
		if (!nom || nom.length < 2) return null;
		const q = normalizeStr(nom);
		// Préférer le lot de type appartement pour la localisation (pas le parking ni la cave)
		const hits = lotImports.filter(imp =>
			imp.nom_coproprietaire && normalizeStr(imp.nom_coproprietaire).includes(q)
		);
		if (!hits.length) return null;
		// Exclure CA (cave) et PS (parking) via type_raw — fiable même si lot_id non résolu
		const hitsAppt = hits.filter(imp => {
			const raw = (imp.type_raw ?? '').toUpperCase().trim();
			if (raw.startsWith('CA') || raw.startsWith('PS')) return false;
			if (imp.lot_id) {
				const lot = allLots.find(l => l.id === imp.lot_id);
				if (lot && lot.type !== 'appartement') return false;
			}
			return true;
		});
		// Priorité : appartement résolu > non résolu > rien (parking/cave écarté)
		const hit = hitsAppt.find(imp => imp.lot_id && allLots.find(l => l.id === imp.lot_id)?.type === 'appartement')
			?? hitsAppt.find(imp => imp.lot_id)
			?? hitsAppt[0]
			?? null;
		if (!hit) return null;
		// Étage : source primaire = etage_raw de la ligne import (colonne Etage)
		const etage: number | null = etageFromRaw(hit.etage_raw);
		// Bâtiment : allLots (si lot résolu) puis batimentsMap, sinon batiment_id de la ligne import
		let batiment_id: number | null = null;
		let batiment_nom: string | null = null;
		if (hit.lot_id) {
			const lot = allLots.find(l => l.id === hit.lot_id);
			if (lot) {
				batiment_id = lot.batiment_id;
				const mapName = lot.batiment_id ? (batimentsMap[lot.batiment_id] ?? null) : null;
				batiment_nom = mapName
					? mapName.replace(/^Bât\. /i, '')
					: (lot.batiment_nom ? lot.batiment_nom.replace(/^Bât\. /i, '') : null);
			}
		}
		if (!batiment_id) batiment_id = hit.batiment_id ?? null;
		if (!batiment_nom && hit.batiment_nom)
			batiment_nom = hit.batiment_nom.replace(/^Bât\. /i, '');
		return { batiment_id, batiment_nom, etage };
	}

	onMount(async () => {
		if (!$isCS) { goto('/tableau-de-bord'); return; }

		// Navigation depuis le dashboard via ?onglet=...&vue=...
		const params = new URLSearchParams(window.location.search);
		const pOnglet = params.get('onglet') as typeof onglet | null;
		const pVue = params.get('vue');
		if (pOnglet && ['validations', 'tickets', 'reporting', 'annonces-hall', 'annuaire'].includes(pOnglet)) {
			onglet = pOnglet;
		}
		if (pVue && onglet === 'reporting') vueReporting = pVue;

		try {
			//  🔴 Quatre données de RÉFÉRENCE (#522) : elles ne s'affichent nulle
			//  part, elles garnissent `batimentsMap` et les rapprochements de lots.
			//  Un échec ne vidait aucune liste — il faisait afficher « Bât. ? »
			//  partout et rendait le rapprochement automatique muet, sans que rien
			//  ne distingue « aucune correspondance » de « je n'ai pas cherché ».
			const [comptes, commandes, [batList, eBat], [users, eUsers], [lotsData, eLots], [importsData, eImports]] = await Promise.all([
				adminApi.comptesEnAttente(),
				adminApi.commandesAccesEnAttente(),
				essayer<{ id: number; numero: string }[]>(api.get('/auth/batiments'), []),
				essayer<any[]>(adminApi.utilisateurs(), []),
				essayer<any[]>(lotsApi.tous(), []),
				essayer<any[]>(lotsApi.listImports(), []),
			]);
			erreurReference = messagePartiel(eBat, eUsers, eLots, eImports);
			comptesEnAttente = comptes;
			commandesEnAttente = commandes;
			batimentsMap = Object.fromEntries((batList as any[]).map((b) => [b.id, `Bât. ${b.numero}`]));
			allUsers = (users as any[]).map((u) => ({
				id: u.id, prenom: u.prenom, nom: u.nom,
				email: u.email, telephone: u.telephone, batiment_id: u.batiment_id,
			}));
			allLots = lotsData as LotRow[];
			lotImports = importsData as any[];
		} catch {
			toast('error', 'Erreur de chargement');
		} finally {
			loading = false;
		}
		loadAnnuaire();
	});

	async function loadAnnuaire() {
		annuaireLoading = true;
		try {
			const [csData, syndicData] = await Promise.all([
				annuaireAdmin.getCS(),
				annuaireAdmin.getSyndic(),
			]);
			agAnnee = csData.ag_annee ?? null;
			agDate = csData.ag_date ?? '';
			whatsappUrl = csData.whatsapp_url ?? '';
			membresCS = (csData.membres ?? []).map((m: any): MembreCSForm => ({
				genre: m.genre ?? 'Mme',
				prenom: m.prenom ?? '', nom: m.nom ?? '',
				batiment_id: m.batiment_id ?? null,
				batiment_nom: m.batiment_nom ?? null,
				etage: m.etage ?? null,
				user_id: m.user_id ?? null,
				est_gestionnaire_site: m.est_gestionnaire_site ?? false,
				est_president: m.est_president ?? false,
			}));
			membresCS.sort((a, b) => {
				const bat = (a.batiment_nom ?? 'zzz').localeCompare(b.batiment_nom ?? 'zzz', 'fr');
				if (bat !== 0) return bat;
				return (a.nom ?? '').localeCompare(b.nom ?? '', 'fr');
			});
			membresCS = [...membresCS];
			csOpenIdx = null; csEditIdx = null;
			csHeaderEditing = false;
			nomSyndic = syndicData.nom_syndic ?? '';
			adresseSyndic = syndicData.adresse ?? '';
			siteWebSyndic = syndicData.site_web ?? '';
			membresSyndic = (syndicData.membres ?? []).map((m: any): MembreSyndicForm => ({
				genre: m.genre ?? 'Mme',
				prenom: m.prenom ?? '', nom: m.nom ?? '',
				fonction: m.fonction ?? '', email: m.email ?? '',
				telephones: m.telephone
					? m.telephone.split(',').map((t: string) => t.trim()).filter(Boolean)
					: [''],
				est_principal: m.est_principal ?? false,
				user_id: m.user_id ?? null,
			}));
			syndicOpenIdx = null; syndicEditIdx = null;
			syndicHeaderEditing = false;
		} catch {
			toast('error', 'Erreur chargement annuaire');
		} finally {
			annuaireLoading = false;
		}
	}

	// -- CS handlers --------------------------------------------------------
	function addMembreCS() {
		membresCS = [...membresCS, { genre: 'Mme', prenom: '', nom: '', batiment_id: null, batiment_nom: null, etage: null, user_id: null, est_gestionnaire_site: false, est_president: false }];
		csOpenIdx = membresCS.length - 1;
		csEditIdx = membresCS.length - 1;
	}
	function removeMembreCS(i: number) {
		membresCS = membresCS.filter((_, j) => j !== i);
		if (csOpenIdx === i) { csOpenIdx = null; csEditIdx = null; }
		else if (csOpenIdx !== null && csOpenIdx > i) csOpenIdx--;
		if (csEditIdx !== null && csEditIdx !== i && csEditIdx > i) csEditIdx--;
	}

	function onCSNomInput(i: number) {
		const nom = membresCS[i].nom;
		const imp = findImportForNom(nom);
		if (imp) {
			membresCS[i] = { ...membresCS[i], batiment_id: imp.batiment_id, batiment_nom: imp.batiment_nom, etage: imp.etage };
		}
		if (!membresCS[i].user_id) {
			const matchedUser = findUserByNom(nom);
			if (matchedUser) membresCS[i] = { ...membresCS[i], user_id: matchedUser.id };
		}
		membresCS = [...membresCS];
	}

	function clearUserCS(i: number) {
		membresCS[i] = { ...membresCS[i], user_id: null };
		membresCS = [...membresCS];
	}

	async function onPresidentChange(i: number) {
		// Si on décoche, c'est OK
		if (!membresCS[i].est_president) {
			membresCS[i] = { ...membresCS[i], est_president: false };
			membresCS = [...membresCS];
			return;
		}

		// Si on coche, vérifier s'il y a déjà un président
		const currentPresident = membresCS.findIndex(m => m.est_president && membresCS.indexOf(m) !== i);
		if (currentPresident !== -1) {
			// Demander confirmation
			const oldName = `${membresCS[currentPresident].prenom} ${membresCS[currentPresident].nom}`;
			const newName = `${membresCS[i].prenom} ${membresCS[i].nom}`;
			const confirmed = confirm(`Un président existe déjà (${oldName}).\n\nVoulez-vous remplacer par ${newName} ?`);
			
			if (confirmed) {
				// Désélectionner l'ancien
				membresCS[currentPresident] = { ...membresCS[currentPresident], est_president: false };
				// Sélectionner le nouveau
				membresCS[i] = { ...membresCS[i], est_president: true };
				membresCS = [...membresCS];
				toast('info', `${newName} est maintenant président du CS`);
			} else {
				// Annuler la sélection
				membresCS[i] = { ...membresCS[i], est_president: false };
				membresCS = [...membresCS];
			}
		} else {
			// Aucun président existant, on peut le cocher
			membresCS[i] = { ...membresCS[i], est_president: true };
			membresCS = [...membresCS];
			toast('info', `${membresCS[i].prenom} ${membresCS[i].nom} est maintenant président du CS`);
		}
	}

	async function saveCS() {
		savingCS = true;
		try {
			await annuaireAdmin.putCS({ ag_annee: agAnnee, ag_date: agDate || null, whatsapp_url: whatsappUrl || null, membres: membresCS });
			toast('success', 'Conseil Syndical enregistré');
			csHeaderEditing = false;
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally { savingCS = false; }
	}

	async function saveMembreCS(i: number) {
		savingCSIdx = i;
		try {
			await annuaireAdmin.putCS({ ag_annee: agAnnee, ag_date: agDate || null, whatsapp_url: whatsappUrl || null, membres: membresCS });
			csOpenIdx = null; csEditIdx = null;
			toast('success', `${membresCS[i].prenom} ${membresCS[i].nom} enregistré`);
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally { savingCSIdx = null; }
	}

	// -- Syndic handlers ----------------------------------------------------
	function addMembreSyndic() {
		membresSyndic = [...membresSyndic, { genre: 'Mme', prenom: '', nom: '', fonction: '', email: '', telephones: [''], est_principal: false, user_id: null }];
		syndicOpenIdx = membresSyndic.length - 1;
		syndicEditIdx = membresSyndic.length - 1;
	}
	function removeMembreSyndic(i: number) {
		membresSyndic = membresSyndic.filter((_, j) => j !== i);
		if (syndicOpenIdx === i) { syndicOpenIdx = null; syndicEditIdx = null; }
		else if (syndicOpenIdx !== null && syndicOpenIdx > i) syndicOpenIdx--;
		if (syndicEditIdx !== null && syndicEditIdx !== i && syndicEditIdx > i) syndicEditIdx--;
	}

	function clearUserSyndic(i: number) {
		membresSyndic[i] = { ...membresSyndic[i], user_id: null };
		membresSyndic = [...membresSyndic];
	}

	function onSyndicNomInput(i: number) {
		if (!membresSyndic[i].user_id) {
			const matchedUser = findUserByNom(membresSyndic[i].nom);
			if (matchedUser) {
				membresSyndic[i] = { ...membresSyndic[i], user_id: matchedUser.id };
				membresSyndic = [...membresSyndic];
			}
		}
	}

	function setPrincipal(i: number) {
		membresSyndic = membresSyndic.map((m, j) => ({ ...m, est_principal: j === i }));
	}

	/**
	 * La charge utile de `putSyndic`, écrite UNE fois.
	 *
	 * Elle l'était **trois** — réordonnancement d'un membre, enregistrement de
	 * l'en-tête, enregistrement d'un membre — à l'identique au caractère près.
	 * Trois copies d'une charge utile, c'est trois endroits où un champ ajouté au
	 * modèle peut manquer : `check-charge-utile` existe précisément pour ce défaut,
	 * et il ne voit pas une recopie interne à un fichier.
	 */
	function chargeUtileSyndic() {
		return {
			nom_syndic: nomSyndic,
			adresse: adresseSyndic,
			site_web: siteWebSyndic || null,
			membres: membresSyndic.map((m) => ({
				genre: m.genre, prenom: m.prenom, nom: m.nom,
				fonction: m.fonction || null, email: m.email || null,
				telephone: m.telephones.map((t) => t.trim()).filter(Boolean).join(',') || null,
				est_principal: m.est_principal, user_id: m.user_id,
			})),
		};
	}

	async function moveMembreSyndic(i: number, dir: -1 | 1) {
		const j = i + dir;
		if (j < 0 || j >= membresSyndic.length) return;
		const arr = [...membresSyndic];
		[arr[i], arr[j]] = [arr[j], arr[i]];
		membresSyndic = arr;
		syndicOpenIdx = null; syndicEditIdx = null;
		// Sauvegarde silencieuse de l'ordre
		try {
			await annuaireAdmin.putSyndic(chargeUtileSyndic());
		} catch { /* silencieux */ }
	}

	async function saveSyndic() {
		for (const m of membresSyndic) {
			if (!m.telephones.some((t) => t.trim())) {
				toast('error', `Au moins un téléphone requis pour ${m.prenom || '…'} ${m.nom || ''}`);
				return;
			}
		}
		savingSyndic = true;
		try {
			await annuaireAdmin.putSyndic(chargeUtileSyndic());
			toast('success', 'Syndic enregistré');
			syndicHeaderEditing = false;
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally { savingSyndic = false; }
	}

	async function saveMembreSyndic(i: number) {
		if (!membresSyndic[i].telephones.some((t) => t.trim())) {
			toast('error', 'Au moins un téléphone requis');
			return;
		}
		savingSyndicIdx = i;
		try {
			await annuaireAdmin.putSyndic(chargeUtileSyndic());
			syndicOpenIdx = null; syndicEditIdx = null;
			toast('success', `${membresSyndic[i].prenom} ${membresSyndic[i].nom} enregistré`);
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally { savingSyndicIdx = null; }
	}

	// -- Validations handlers -----------------------------------------------
	// Validation + Nouvel Arrivant
	let cvModal: PendingUser | null = null;
	let cvNewArrivant = false;
	let cvBatiment = '';
	let cvAncienResident = '';
	let cvSubmitting = false;

	function openCSValidation(user: PendingUser) {
		cvModal = user;
		cvNewArrivant = false;
		cvBatiment = user.batiment_id ? (batimentsMap[user.batiment_id] ?? '') : '';
		cvAncienResident = '';
	}

	async function confirmerCSValidation() {
		if (!cvModal) return;
		const u = cvModal;
		cvSubmitting = true;
		try {
			await adminApi.traiterCompte(u.id, { action: 'valider' });
			comptesEnAttente = comptesEnAttente.filter((x) => x.id !== u.id);
			toast('success', 'Compte approuvé.');
			if (cvNewArrivant) {
				await api.post(`/admin/utilisateurs/${u.id}/accueil-arrivant`, {
					batiment: cvBatiment || null,
					ancien_resident: cvAncienResident || null,
				});
				toast('success', 'Actions d\'accueil envoyées.');
			}
			cvModal = null;
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			cvSubmitting = false;
		}
	}

	async function traiterCompte(id: number, decision: 'approuver' | 'rejeter') {
		try {
			await adminApi.traiterCompte(id, { action: decision === 'approuver' ? 'valider' : 'refuser' });
			comptesEnAttente = comptesEnAttente.filter((u) => u.id !== id);
			toast('success', decision === 'approuver' ? 'Compte approuvé' : 'Compte rejeté');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}
	async function traiterCommande(id: number, decision: 'approuver' | 'rejeter') {
		try {
			await adminApi.traiterCommandeAcces(id, { action: decision === 'approuver' ? 'accepter' : 'refuser' });
			commandesEnAttente = commandesEnAttente.filter((c) => c.id !== id);
			toast('success', decision === 'approuver' ? 'Commande approuvée' : 'Commande rejetée');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}
</script>

{#if cvModal}
<Modale titre="Valider le compte" classeBoite="modal-box card" styleBoite="max-width:460px"
	on:fermer={() => (cvModal = null)}>
    <h2 style="font-size:1rem;font-weight:700;margin-bottom:.75rem">Valider le compte de {cvModal.prenom} {cvModal.nom}</h2>
    <label style="display:flex;align-items:flex-start;gap:.6rem;cursor:pointer;border:1.5px solid var(--color-border);border-radius:var(--radius);padding:.75rem;margin-bottom:.75rem">
      <input type="checkbox" bind:checked={cvNewArrivant} style="margin-top:.2rem;flex-shrink:0" />
      <div>
        <strong style="font-size:.9rem">&#x1F3E0; Nouvel Arrivant</strong>
        <p style="font-size:.78rem;color:var(--color-text-muted);margin:.25rem 0 0">
          À cocher uniquement pour un <strong>nouveau résident</strong> qui emménage dans la copropriété.
          Déclenche automatiquement : message de bienvenue, consignes de copropriété,
          demande d'étiquette boîte aux lettres auprès du syndic, et demande d'ajout sur l'interphone.
          <em>Ne pas cocher pour un résident existant qui crée simplement son compte.</em>
        </p>
      </div>
    </label>
    {#if cvNewArrivant}
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:.6rem;margin-bottom:.75rem">
      <label class="field">Bâtiment / logement<input bind:value={cvBatiment} placeholder="Ex: Bât. A, Apt. 12…" /></label>
      <label class="field">Ancien résident (optionnel)<input bind:value={cvAncienResident} placeholder="Nom de l'ancien occupant…" /></label>
    </div>
    {/if}
    <div class="modal-actions">
      <button class="btn btn-outline" on:click={() => (cvModal = null)}>Annuler</button>
      <button class="btn btn-success" disabled={cvSubmitting} on:click={confirmerCSValidation}>
        {cvSubmitting ? 'En cours…' : '✓ Valider le compte'}
      </button>
    </div>
</Modale>
{/if}

<svelte:head><title>{_pc.titre} · {_siteNom}</title></svelte:head>

<EntetePage titre={_pc.titre} icone={_pc.icone || 'shield-half'} />

<ChargementPartiel erreur={erreurReference}
	consequence="Les numéros de bâtiment peuvent s'afficher « Bât. ? », et le rapprochement automatique des lots ne trouvera rien — faute d'avoir pu chercher." />
<div class="page-subtitle">{@html safeHtml(_pc.descriptif)}</div>

<!-- Onglets -->
<div class="tabs" style="margin-bottom:1.5rem">
	<button class="tab-btn" class:active={onglet === 'validations'} on:click={() => (onglet = 'validations')}>
		{_pc.onglets?.validations?.label ?? '✅ Comptes & accès'}
		{#if nbComptes + nbCommandes > 0}<span class="badge-count">{nbComptes + nbCommandes}</span>{/if}
	</button>
	<button class="tab-btn" class:active={onglet === 'tickets'} on:click={() => { onglet = 'tickets'; loadTickets(); }}>
		{_pc.onglets?.tickets?.label ?? '\u{1F3AB} Tickets résidence'}
		{#if tkPendingCount > 0}<span class="badge-count">{tkPendingCount}</span>{/if}
	</button>
	<button class="tab-btn" class:active={onglet === 'reporting'} on:click={() => (onglet = 'reporting')}>
		{_pc.onglets?.reporting?.label ?? '\u{1F4CA} Reporting'}
	</button>
	<button class="tab-btn" class:active={onglet === 'annonces-hall'} on:click={() => (onglet = 'annonces-hall')}>
		{_pc.onglets?.['annonces-hall']?.label ?? '\u{1F4C4} Annonces Hall'}
	</button>
	<button class="tab-btn" class:active={onglet === 'annuaire'} on:click={() => (onglet = 'annuaire')}>
		{_pc.onglets?.annuaire?.label ?? '\u{1F4D2} Annuaire CS & Syndic'}
	</button>
</div>
{#if _pc.onglets?.[onglet]?.descriptif}
<p class="tab-descriptif">{@html safeHtml(_pc.onglets[onglet].descriptif)}</p>
{/if}

{#if onglet === 'validations'}
	{#if loading}
		<p style="color:var(--color-text-muted)">Chargement…</p>
	{:else}
		<!-- KPI Cards -->
		<div class="kpi-row" style="margin-bottom:1.5rem">
			<div class="kpi-card" class:kpi-alert={nbComptes > 0}>
				<div class="kpi-value">{nbComptes}</div>
				<div class="kpi-label">Compte(s) à valider</div>
			</div>
			<div class="kpi-card" class:kpi-alert={nbCommandes > 0}>
				<div class="kpi-value">{nbCommandes}</div>
				<div class="kpi-label">Demande(s) d'accès</div>
			</div>
		</div>

		<!-- Comptes en attente -->
		<section class="largeur-saisie" style="margin-bottom:2rem">
			<h2 style="font-size:1rem;font-weight:600;margin-bottom:.75rem">
				Comptes en attente de validation
			</h2>
			{#if comptesEnAttente.length === 0}
				<p class="text-muted-sm">Aucun compte en attente.</p>
			{:else}
				{#each comptesEnAttente as user}
					<div class="pending-row card">
						<div class="pending-info">
							<strong>{user.prenom} {user.nom}</strong>
							<span class="text-muted-sm">
								{user.statut?.replace(/_/g, ' ') ?? '…'}{user.batiment_id ? ` — ${batimentsMap[user.batiment_id] ?? `Bât. #${user.batiment_id}`}` : ''}
							</span>
							{#if (user.statut === 'aidant' || user.statut === 'mandataire') && user.nom_aide}
								<span class="text-muted-sm">👤 Aidé : {user.prenom_aide} {user.nom_aide}</span>
							{/if}
							<span class="text-muted-sm">{fmtDateShort(user.cree_le)}</span>
						</div>
						<div class="pending-actions">
							<button class="btn btn-sm btn-success" on:click={() => openCSValidation(user)}>✓ Approuver</button>
							<button class="btn btn-sm btn-danger"  on:click={() => traiterCompte(user.id, 'rejeter')}>✗ Rejeter</button>
						</div>
					</div>
				{/each}
			{/if}
		</section>

		<!-- Commandes d'accès -->
		<section class="largeur-saisie">
			<h2 style="font-size:1rem;font-weight:600;margin-bottom:.75rem">
				Demandes d'accès (badges / télécommandes)
			</h2>
			{#if commandesEnAttente.length === 0}
				<p class="text-muted-sm">Aucune demande en attente.</p>
			{:else}
				{#each commandesEnAttente as cmd}
					<div class="pending-row card">
						<div class="pending-info">
							<strong>{cmd.proprietaire.prenom} {cmd.proprietaire.nom}</strong>
							<span class="text-muted-sm">
								{cmd.lot.batiment.nom} · {cmd.lot.reference} ·
								{cmd.type_acces.replace('_', ' ')} · {cmd.quantite}
							</span>
							<span class="text-muted-sm">{fmtDateShort(cmd.cree_le)}</span>
						</div>
						<div class="pending-actions">
							<button class="btn btn-sm btn-success" on:click={() => traiterCommande(cmd.id, 'approuver')}>✓ Approuver</button>
							<button class="btn btn-sm btn-danger"  on:click={() => traiterCommande(cmd.id, 'rejeter')}>✗ Rejeter</button>
						</div>
					</div>
				{/each}
			{/if}
		</section>
	{/if}

{:else if onglet === 'tickets'}
	<div style="margin-bottom:1.25rem;display:flex;gap:.4rem;flex-wrap:wrap;align-items:center">
		<button class="btn btn-sm" class:btn-primary={tkFilter === ''} on:click={() => tkFilter = ''}>Tous</button>
		{#each STATUTS_TICKET_FILTRE as s}
			<button class="btn btn-sm" class:btn-primary={tkFilter === s.value}
				on:click={() => tkFilter = s.value}>{s.label}</button>
		{/each}

	</div>

	{#if tkLoading}
		<p style="color:var(--color-text-muted)">Chargement…</p>
	{:else if tkFiltered.length === 0}
		<div class="empty-state">
			<h3>Aucun ticket{tkFilter ? ' dans ce statut' : ''}</h3>
		</div>
	{:else}
		{#each tkFiltered as t (t.id)}
			{@const expanded = tkExpandedId === t.id}
			{@const evols = tkEvolsMap[t.id] ?? []}
			<div class="carte-liste tk-expand" class:expanded class:urgent={t.categorie === 'urgence'}
				role="button" tabindex="0"
				on:click={() => tkToggle(t.id)}
				on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && tkToggle(t.id)}>
				<div class="tk-row">
					<div class="tk-main">
						<div class="tk-row-inner">
							<span class="tk-cat">{TK_CAT_ICON[t.categorie] ?? '\u{1F4CB}'}</span>
							<span class="tk-row-titre">{t.titre}</span>
							<span class="badge {TK_STATUT_BADGE[t.statut] ?? 'badge-gray'}" style="flex-shrink:0">{TK_STATUT_LABELS[t.statut] ?? t.statut}</span>
							{#if t.priorite === 'haute'}<span class="badge badge-orange" style="flex-shrink:0">⚡ Urgente</span>{/if}
						</div>
						{#if t.auteur_nom || t.auteur_batiment_nom}
							<div class="tk-ticket-meta">
								{#if t.auteur_nom}<span>&#x1F464; {t.auteur_nom}</span>{/if}
								{#if t.auteur_batiment_nom}<span>&#x1F4CD; {t.auteur_batiment_nom}</span>{/if}
							</div>
						{/if}
					</div>
					<div class="tk-row-right">
						<span class="tk-row-date">{fmtDate(t.mis_a_jour_le ?? t.cree_le)}</span>
						<button class="btn-icon" aria-label="Commenter ou changer l’état" title="Commenter ou changer l’état" on:click|stopPropagation={() => tkOpenForm(t.id)}>&#x1F504;</button>
						<span class="chevron" class:open={expanded}>›</span>
					</div>
				</div>

				{#if !expanded}
					<ApercuTicket ticket={t} />
				{/if}

				{#if expanded}
					<div class="tk-body" on:click|stopPropagation on:keydown|stopPropagation>
						{#if tkShowForm === t.id}
						<div class="evol-form">
							{#key tkShowForm}
							<EvolForm idPrefixe="cs-tk-evol-{t.id}" titre="Commenter ou changer l’état"
								statutOptions={TK_STATUT_OPTIONS}
								statutLabels={TK_STATUT_LABELS}
								currentStatut={t.statut ?? ''}
								showNotifs={false}
								showEmail={false}
								showPhotos={true}
								showDocuments={true}
								saving={tkEvolSaving}
								on:submit={(e) => tkSubmitEvol(t, e)}
								on:cancel={() => (tkShowForm = null)}
							/>
							{/key}
						</div>

					{:else}
							{#if t.auteur_nom || t.auteur_batiment_nom}
								<div class="tk-context-meta">
									{#if t.auteur_nom}<span class="context-chip">Demandeur : {t.auteur_nom}</span>{/if}
									{#if t.auteur_batiment_nom}<span class="context-chip">Bâtiment : {t.auteur_batiment_nom}</span>{/if}
								</div>
							{/if}
							<div class="rich-content" style="font-size:.875rem;line-height:1.6;margin-bottom:.5rem">{@html safeDescription(t.description)}</div>
							<small style="color:var(--color-text-muted);font-size:.78rem">
								Créé le {fmtDate(t.cree_le)} · <span style="font-family:monospace">#{t.numero}</span>
							</small>
							<!--  L'HISTORIQUE — cinquième des six recopies du fil relevées par
							      #431, remplacée ici (#433). Celle-ci n'avait PAS la
							      pagination des autres : un ticket à trente entrées les
							      déroulait toutes. Elle habillait aussi son bouton
							      « Modifier » par six déclarations en ligne. Tout cela vit
							      une fois, dans la rubrique, avec ses styles — Svelte les
							      scope au composant qui rend le balisage. -->
							{#if evols.length > 0}
								<div>
									<RubriqueHistorique
										evolutions={evols}
										statutLabels={TK_STATUT_LABELS}
										peutModifier={true} currentUserId={$currentUser?.id} estAdmin={$isAdmin}
										enEdition={tkEditingEvolId}
										on:modifier={(e) => (tkEditingEvolId = e.detail)}
									>
										<svelte:fragment slot="edition" let:evol>
											{#key tkEditingEvolId}
												<EvolForm idPrefixe="cs-tk-evol-edit-{evol.id}" titre="Modifier le commentaire"
													editMode={true}
													initialContenu={evol.contenu || ''}
													initialFichiers={fichiersDepuisUrls(evol.fichiers_urls)}
													showPhotos={true}
													showDocuments={true}
													saving={tkEditEvolSaving}
													on:submit={(e) => tkSaveEvolEdit(t.id, e)}
													on:cancel={() => tkEditingEvolId = null}
												/>
											{/key}
										</svelte:fragment>
									</RubriqueHistorique>
								</div>
							{/if}
							<!--  ⚠️ Cette commande double celle de l'en-tête de la carte —
							      c'était déjà le cas avant #426 ; à arbitrer sur cet écran. -->
							<div style="margin-top:.75rem">
								<button class="btn btn-sm btn-outline" on:click|stopPropagation={() => tkOpenForm(t.id)}>&#x1F504; Commenter ou changer l’état</button>
							</div>
						{/if}
					</div>
				{/if}
			</div>
		{/each}
	{/if}

	<!--  ARCHIVES des tickets clos — bandeau, groupement par année et titre
	      viennent tous d'`ArchivesParAnnee` (#516). Le bandeau était réécrit ici
	      une 4e fois (chevron figé à « ▼ »), et le groupement une 3e. -->
	{#if tkHistory.length > 0}
	<div>
		<ArchivesParAnnee items={tkHistory} dateDe={(t) => t.mis_a_jour_le ?? t.cree_le}
			compte={tkHistory.length} charge bind:ouvert={tkHistoryExpanded}
			let:objet={t}>
					{@const hExpanded = tkExpandedId === t.id}
					{@const evols = tkEvolsMap[t.id] ?? []}
					<div class="tk-expand history-item" class:expanded={hExpanded} class:urgent={t.categorie === 'urgence'}
						role="button" tabindex="0"
						on:click={() => tkToggle(t.id)}
						on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && tkToggle(t.id)}>
						<div class="tk-row">
							<div class="tk-main">
								<div class="tk-row-inner">
									<span class="tk-cat">{TK_CAT_ICON[t.categorie] ?? '📋'}</span>
									<span class="tk-row-titre">{t.titre}</span>
									<span class="badge {TK_STATUT_BADGE[t.statut] ?? 'badge-gray'}" style="flex-shrink:0">{TK_STATUT_LABELS[t.statut] ?? t.statut}</span>
								</div>
								{#if t.auteur_nom || t.auteur_batiment_nom}
									<div class="tk-ticket-meta">
										{#if t.auteur_nom}<span>👤 {t.auteur_nom}</span>{/if}
										{#if t.auteur_batiment_nom}<span>📍 {t.auteur_batiment_nom}</span>{/if}
									</div>
								{/if}
							</div>
							<div class="tk-row-right">
								<span class="tk-row-date">{fmtDate(t.mis_a_jour_le ?? t.cree_le)}</span>
								<span class="chevron" class:open={hExpanded}>›</span>
							</div>
						</div>
						{#if !hExpanded}
							<ApercuTicket ticket={t} />
						{/if}
						{#if hExpanded}
							<div class="tk-body" on:click|stopPropagation on:keydown|stopPropagation>
								{#if t.auteur_nom || t.auteur_batiment_nom}
									<div class="tk-context-meta">
										{#if t.auteur_nom}<span class="context-chip">Demandeur : {t.auteur_nom}</span>{/if}
										{#if t.auteur_batiment_nom}<span class="context-chip">Bâtiment : {t.auteur_batiment_nom}</span>{/if}
									</div>
								{/if}
								<div class="rich-content" style="font-size:.875rem;line-height:1.6;margin-bottom:.5rem">{@html safeDescription(t.description)}</div>
								<small style="color:var(--color-text-muted);font-size:.78rem">Créé le {fmtDate(t.cree_le)} · <span style="font-family:monospace">#{t.numero}</span></small>
								<!--  🔴 Le fil passe par `RubriqueHistorique`, le composant qui le rend
								      déjà pour la fiche et la carte d'un ticket. Il était RECOMPOSÉ ici
								      à la main — même balisage, mêmes classes, et une icône qui avait
								      divergé : 📝 pour un commentaire, là où le bouton dit « 💬 Commenter »
								      (signalé à l'écran le 19/08/2026).
								      Les gestes de correction ne sont PAS proposés ici : cet onglet est une
								      vue de suivi, la correction se fait depuis la fiche du ticket. -->
								<RubriqueHistorique
									evolutions={[...evols].sort((x, y) => new Date(y.cree_le).getTime() - new Date(x.cree_le).getTime())}
									statutLabels={TK_STATUT_LABELS}
								/>
							</div>
						{/if}
					</div>
		</ArchivesParAnnee>
	</div>
	{/if}

{:else if onglet === 'reporting'}
	<OngletReporting
		{tickets}
		chargerTickets={loadTickets}
		titreOnglet={_pc.onglets?.reporting?.label ?? 'Reporting'}
		vueInitiale={vueReporting}
	/>

{:else if onglet === 'annonces-hall'}
	<OngletAnnoncesHall {MAX_FICHIERS} />

{:else if onglet === 'annuaire'}
	{#if annuaireLoading}
		<p style="color:var(--color-text-muted)">Chargement…</p>
	{:else}

		<!-- ── Lien consignes de copropriété ─────────────────────────────────── -->
		<div style="display:flex;justify-content:flex-end;margin-bottom:0.75rem">
			<a href="/api/admin/fiche-arrivant" target="_blank" class="btn btn-outline" style="display:inline-flex;align-items:center;gap:0.4rem;font-size:0.85rem">
				📄 Consignes de copropriété
			</a>
		</div>

		<!-- ── Section Conseil Syndical ──────────────────────────────────────── -->
		<section class="annuaire-section">
			<div class="annuaire-section-header">
				<h2 class="section-title">Conseil Syndical</h2>
			</div>

			{#if csHeaderEditing}
				<div class="form-grid" style="max-width:460px;margin-bottom:1rem">
					<label class="field">
						Voté en AG
						<input type="number" min="2000" max="2099" placeholder="ex. 2024" bind:value={agAnnee} />
					</label>
					<label class="field">
						Date de l'AG
						<input type="date" bind:value={agDate} />
					</label>
					<label class="field">
						URL communauté WhatsApp
						<input type="url" placeholder="https://chat.whatsapp.com/..." bind:value={whatsappUrl} />
					</label>
					<div class="header-edit-actions">
						<button class="btn btn-primary btn-sm" on:click={saveCS} disabled={savingCS}>{savingCS ? '…' : '\u{1F4BE} Enregistrer'}</button>
						<button class="btn btn-sm btn-outline" on:click={() => csHeaderEditing = false}>Annuler</button>
					</div>
				</div>
			{:else}
				<div class="header-summary">
					<span>{agAnnee ? `AG ${agAnnee}` : 'Année AG non renseignée'}{agDate ? ` · ${fmtDateShort(agDate)}` : ''}</span>
					{#if whatsappUrl}<span style="margin-left:.5rem">· <a href={whatsappUrl} target="_blank" rel="noopener">WhatsApp</a></span>{/if}
					<button type="button" class="btn-icon btn-icon-edit" title="Modifier" on:click={() => csHeaderEditing = true}><Icon name="pencil" size={13} /></button>
				</div>
			{/if}

			{#each membresCS as m, i}
				<div class="membre-card" class:membre-president={m.est_president} style="cursor:pointer"
					on:click={() => { if (csEditIdx !== i) csOpenIdx = csOpenIdx === i ? null : i; }}>
					<!-- Header fiche -->
					<div class="membre-card-header">
						<div style="display:flex;align-items:center;gap:.5rem;flex-wrap:wrap">
							{#if m.est_president}<span class="badge-president">👑 Président</span>{/if}
							<span class="membre-card-title">{m.genre} {m.prenom || '…'} <span class="nom-upper">{m.nom || ''}</span></span>
						</div>
						<div class="membre-card-actions" on:click|stopPropagation>
							{#if csEditIdx === i}
								<button type="button" class="btn-icon btn-icon-save" title="Enregistrer ce membre"
									disabled={savingCSIdx === i}
									on:click={() => saveMembreCS(i)}>
									{#if savingCSIdx === i}…{:else}&#x1F4BE;{/if}
								</button>
							{:else}
								<button type="button" class="btn-icon btn-icon-edit" title="Modifier" on:click={() => { csOpenIdx = i; csEditIdx = i; }}><Icon name="pencil" size={13} /></button>
							{/if}
							<button type="button" class="btn-icon btn-icon-remove" title="Supprimer" on:click={() => removeMembreCS(i)}><Icon name="trash-2" size={14} /></button>
						</div>
					</div>

					{#if csOpenIdx === i}
						{#if csEditIdx === i}
							<div class="form-grid">
								<label class="field">
									Civilité
									<select bind:value={membresCS[i].genre} on:change={() => membresCS = [...membresCS]}>
										<option value="Mme">Mme</option>
										<option value="Mlle">Mlle</option>
										<option value="Mr">Mr</option>
									</select>
								</label>
								<label class="field">
									Prénom
									<input type="text" bind:value={membresCS[i].prenom} placeholder="Prénom" />
								</label>
								<label class="field">
									NOM
									<input type="text" bind:value={membresCS[i].nom} placeholder="NOM" class="input-nom"
										on:input={() => onCSNomInput(i)} />
								</label>
							</div>
							{#if m.batiment_nom || m.etage != null}
								<div class="localisation-info">
									&#x1F4CD; {m.batiment_nom ? `Bât. ${m.batiment_nom}` : ''}{m.batiment_nom && m.etage != null ? ' — ' : ''}{m.etage != null ? `Étage ${m.etage}` : ''}
								</div>
							{/if}
							<div class="user-link-indicator">
								{#if m.user_id}
									<span class="user-linked"><span>&#x1F517; Inscrit lié</span><button type="button" class="btn-unlink" on:click={() => clearUserCS(i)}>Délier</button></span>
								{:else if membresCS[i].nom.length >= 2}
									<span class="user-no-match">Aucun inscrit avec ce NOM</span>
								{/if}
							</div>
							<div class="cs-role-flags">
								<label class="cs-role-flag">
									<input type="checkbox" checked={membresCS[i].est_president} on:change={() => onPresidentChange(i)} />
									<span>Président du Conseil Syndical (optionnel)</span>
								</label>
							</div>
							<div class="header-edit-actions" style="margin-top:.75rem">
								<button class="btn btn-primary btn-sm" on:click={() => saveMembreCS(i)} disabled={savingCSIdx === i}>
									{savingCSIdx === i ? '…' : '💾 Enregistrer'}
								</button>
								<button class="btn btn-sm btn-outline" on:click={() => { csEditIdx = null; csOpenIdx = null; }}>Annuler</button>
							</div>
						{:else}
							<!-- Vue lecture seule (déplié, non édité) -->
							{#if m.batiment_nom || m.etage != null}
								<div class="localisation-info">
									&#x1F4CD; {m.batiment_nom ? `Bât. ${m.batiment_nom}` : ''}{m.batiment_nom && m.etage != null ? ' — ' : ''}{m.etage != null ? `Étage ${m.etage}` : ''}
								</div>
							{/if}
							<div class="user-link-indicator">
								{#if m.user_id}
									<span class="user-linked">&#x1F517; Inscrit lié</span>
								{/if}
							</div>
						{/if}
					{:else}
						<!-- Vue résumé (replié) -->
						<div class="membre-summary">
							{#if m.batiment_nom || m.etage != null}
								<span class="summary-loc">&#x1F4CD; {m.batiment_nom ? `Bât. ${m.batiment_nom}` : ''}{m.batiment_nom && m.etage != null ? ' – ' : ''}{m.etage != null ? `Étage ${m.etage}` : ''}</span>
							{/if}
							{#if m.est_gestionnaire_site}
								<span class="summary-role-badge" title="Gestionnaire du Site">🏢 Gestionnaire du Site</span>
							{/if}
							{#if m.est_president}
								<span class="summary-role-badge summary-role-badge-president" title="Président du Conseil Syndical">👑 Président</span>
							{/if}
							{#if m.user_id}
								<span class="user-linked" style="font-size:.75rem;padding:.15rem .45rem">&#x1F517; Inscrit lié</span>
							{/if}
						</div>
					{/if}
				</div>
			{/each}

			<button type="button" class="btn btn-sm btn-outline" style="margin-top:.5rem" on:click={addMembreCS}>
				+ Nouveau membre CS
			</button>
		</section>

		<!-- ── Section Syndic ────────────────────────────────────────────────── -->
		<section class="annuaire-section">
			<div class="annuaire-section-header">
				<h2 class="section-title">Syndic</h2>
			</div>

			{#if syndicHeaderEditing}
				<div class="form-grid" style="max-width:580px;margin-bottom:1rem">
					<label class="field champ-large">
						Nom du syndic
						<input type="text" bind:value={nomSyndic} placeholder="ex. Cabinet Bertrand" />
					</label>
					<label class="field champ-large">
						Adresse
						<textarea rows="2" bind:value={adresseSyndic} placeholder="ex. 12 rue des Lilas, 75015 Paris"></textarea>
					</label>
					<label class="field champ-large">
						Espace client (site web)
						<input type="url" bind:value={siteWebSyndic} placeholder="https://..." />
					</label>
					<div class="header-edit-actions" style="grid-column:1/-1">
						<button class="btn btn-primary btn-sm" on:click={saveSyndic} disabled={savingSyndic}>{savingSyndic ? '…' : '\u{1F4BE} Enregistrer'}</button>
						<button class="btn btn-sm btn-outline" on:click={() => syndicHeaderEditing = false}>Annuler</button>
					</div>
				</div>
			{:else}
				<div class="header-summary">
					<span>{nomSyndic || 'Nom du syndic non renseigné'}{adresseSyndic ? ` · ${adresseSyndic}` : ''}</span>
					{#if siteWebSyndic}<span style="margin-left:.5rem">· <a href={siteWebSyndic} target="_blank" rel="noopener">Espace client</a></span>{/if}
					<button type="button" class="btn-icon btn-icon-edit" title="Modifier" on:click={() => syndicHeaderEditing = true}><Icon name="pencil" size={13} /></button>
				</div>
			{/if}

			{#each membresSyndic as m, i}
				<div class="membre-card" class:membre-principal={m.est_principal} style="cursor:pointer"
					on:click={() => { if (syndicEditIdx !== i) syndicOpenIdx = syndicOpenIdx === i ? null : i; }}>
					<!-- Header avec badge principal + actions -->
					<div class="membre-card-header">
						<div style="display:flex;align-items:center;gap:.5rem;flex-wrap:wrap">
							{#if m.est_principal}<span class="badge-principal">Interlocuteur principal</span>{/if}
							<span class="membre-card-title">{m.genre} {m.prenom || '…'} <span class="nom-upper">{m.nom || ''}</span></span>
						</div>
						<div class="membre-card-actions" on:click|stopPropagation>
							{#if i > 0}
								<button type="button" class="btn-icon btn-icon-move" title="Monter" on:click={() => moveMembreSyndic(i, -1)}>↑</button>
							{/if}
							<button type="button" class="btn-icon btn-icon-move" title="Descendre" disabled={i === membresSyndic.length - 1} on:click={() => moveMembreSyndic(i, 1)}>↓</button>
							{#if !m.est_principal}
								<button type="button" class="btn-icon btn-icon-star" title="Définir interlocuteur principal" on:click={() => setPrincipal(i)}>★</button>
							{/if}
							{#if syndicEditIdx === i}
								<button type="button" class="btn-icon btn-icon-save" title="Enregistrer ce membre"
									disabled={savingSyndicIdx === i}
									on:click={() => saveMembreSyndic(i)}>
									{#if savingSyndicIdx === i}…{:else}&#x1F4BE;{/if}
								</button>
							{:else}
								<button type="button" class="btn-icon btn-icon-edit" title="Modifier" on:click={() => { syndicOpenIdx = i; syndicEditIdx = i; }}><Icon name="pencil" size={13} /></button>
							{/if}
							<button type="button" class="btn-icon btn-icon-remove" title="Supprimer" on:click={() => removeMembreSyndic(i)}><Icon name="trash-2" size={14} /></button>
						</div>
					</div>

					{#if syndicOpenIdx === i}
						{#if syndicEditIdx === i}
							<div class="form-grid">
								<label class="field">
									Civilité
									<select bind:value={membresSyndic[i].genre} on:change={() => membresSyndic = [...membresSyndic]}>
										<option value="Mme">Mme</option>
										<option value="Mlle">Mlle</option>
										<option value="Mr">Mr</option>
									</select>
								</label>
								<label class="field">
									Prénom
									<input type="text" bind:value={membresSyndic[i].prenom} placeholder="Prénom" />
								</label>
								<label class="field">
									NOM
									<input type="text" bind:value={membresSyndic[i].nom} placeholder="NOM" class="input-nom" on:input={() => onSyndicNomInput(i)} />
								</label>
								<label class="field">
									Fonction
									<input type="text" bind:value={membresSyndic[i].fonction} placeholder="ex. Directeur de gérance" />
								</label>
								<label class="field">
									Email
									<input type="email" bind:value={membresSyndic[i].email} placeholder="Email" />
								</label>
							</div>
							<!-- Téléphones -->
							<div style="margin-top:.65rem">
								<div style="font-size:.85rem;font-weight:600;margin-bottom:.35rem">
									Téléphone{m.telephones.length > 1 ? 's' : ''}
								</div>
								{#each m.telephones as _tel, ti}
									<div style="display:flex;gap:.4rem;margin-bottom:.35rem">
										<input style="flex:1" bind:value={membresSyndic[i].telephones[ti]} placeholder="ex. 01 23 45 67 89" />
										{#if m.telephones.length > 1}
											<button type="button" class="btn btn-sm btn-outline"
												style="color:#dc2626;border-color:#dc2626"
												on:click={() => { membresSyndic[i].telephones = membresSyndic[i].telephones.filter((_, j) => j !== ti); membresSyndic = [...membresSyndic]; }}>
												-
											</button>
										{/if}
									</div>
								{/each}
								<button type="button" class="btn btn-sm btn-outline"
									on:click={() => { membresSyndic[i].telephones = [...membresSyndic[i].telephones, '']; membresSyndic = [...membresSyndic]; }}>
									+ N° de téléphone
								</button>
							</div>
							<!-- Liaison inscrit automatique via NOM -->
							<div class="user-link-indicator" style="margin-top:.65rem">
								{#if m.user_id}
									<span class="user-linked"><span>&#x1F517; Inscrit lié</span><button type="button" class="btn-unlink" on:click={() => clearUserSyndic(i)}>Délier</button></span>
								{:else if membresSyndic[i].nom.length >= 2}
									<span class="user-no-match">Aucun inscrit avec ce NOM</span>
								{/if}
							</div>
						{:else}
							<!-- Vue détail lecture seule (déplié, non édité) -->
							<div class="membre-summary" style="margin-top:.5rem">
								{#if m.fonction}<span class="summary-fonction">{m.fonction}</span>{/if}
								{#if m.email}<span class="summary-loc">{m.email}</span>{/if}
								{#if m.telephones[0]}<span class="summary-loc">{m.telephones.filter(t => t.trim()).join(' · ')}</span>{/if}
								{#if m.user_id}<span class="user-linked" style="font-size:.75rem;padding:.15rem .45rem">&#x1F517; Inscrit lié</span>{/if}
							</div>
						{/if}
					{:else}
						<!-- Vue résumé (replié) -->
						<div class="membre-summary">
							{#if m.fonction}
								<span class="summary-fonction">{m.fonction}</span>
							{/if}
							{#if m.email}
								<span class="summary-loc">{m.email}</span>
							{/if}
							{#if m.telephones[0]}
								<span class="summary-loc">{m.telephones.filter(t => t.trim()).join(' · ')}</span>
							{/if}
							{#if m.user_id}
								<span class="user-linked" style="font-size:.75rem;padding:.15rem .45rem">&#x1F517; Inscrit lié</span>
							{/if}
						</div>
					{/if}
				</div>
			{/each}

			<button type="button" class="btn btn-sm btn-outline" style="margin-top:.5rem" on:click={addMembreSyndic}>
				+ Nouveau membre Syndic
			</button>
		</section>
	{/if}
{/if}

<style>
	/* Tabs */
	.tabs { display: flex; flex-wrap: wrap; gap: .25rem; border-bottom: 2px solid var(--color-border); }
	.tab-btn {
		padding: .45rem .9rem; border: none; background: none; cursor: pointer;
		font-size: .875rem; color: var(--color-text-muted);
		border-bottom: 2px solid transparent; margin-bottom: -2px;
		font-weight: 500; display: flex; align-items: center; gap: .4rem;
		transition: color .15s, border-color .15s; white-space: nowrap;
	}
	.tab-btn:hover { color: var(--color-text); }
	.tab-btn.active { color: var(--color-primary); border-bottom-color: var(--color-primary); }
	.badge-count {
		background: var(--color-danger); color: #fff; border-radius: 999px;
		font-size: .7rem; padding: .1rem .45rem; font-weight: 700;
	}

	/* KPI */

	/* Validations */
	.pending-row {
		display: flex; justify-content: space-between; align-items: center;
		gap: 1rem; margin-bottom: .5rem; flex-wrap: wrap;
	}
	.pending-info { display: flex; flex-direction: column; gap: .15rem; }
	.pending-actions { display: flex; gap: .5rem; flex-shrink: 0; }
	.btn-success { background: #22c55e; color: #fff; border: none; }
	.btn-success:hover:not(:disabled) { background: #16a34a; }
	.btn-danger { background: var(--color-danger); color: #fff; border: none; }
	.btn-danger:hover:not(:disabled) { background: #b91c1c; }

	/* Annuaire sections */
	.annuaire-section { margin-bottom: 2.5rem; max-width: 780px; }
	.annuaire-section-header {
		display: flex; align-items: center; justify-content: space-between;
		margin-bottom: .75rem;
	}
	.section-title {
		font-size: .85rem; font-weight: 700; text-transform: uppercase;
		letter-spacing: .06em; color: var(--color-text-muted); margin: 0;
	}

	/* Form grid */
	.form-grid { grid-template-columns: repeat(auto-fit, minmax(min(150px, 100%), 1fr)); gap: .65rem; }
	.form-grid label { display: flex; flex-direction: column; gap: .25rem; font-size: .875rem; }
	.form-grid input, .form-grid select, .form-grid textarea {
		padding: .4rem .55rem; border: 1px solid var(--color-border);
		border-radius: var(--radius); font-size: .875rem;
		background: var(--color-bg); width: 100%; box-sizing: border-box;
	}
	.form-grid textarea { resize: vertical; }
	.input-nom { text-transform: uppercase; }

	/* Membre card */
	.membre-card {
		background: var(--color-bg-secondary, #f8f9fa);
		border: 1px solid var(--color-border);
		border-left: 3px solid var(--color-border);
		border-radius: var(--radius);
		padding: .85rem 1rem;
		margin-bottom: .6rem;
	}
	.membre-card.membre-principal { border-left-color: var(--color-accent, #C9983A); }
	.membre-card.membre-president { border-left-color: #fbbf24; }

	/* Membre card header */
	.membre-card-header {
		display: flex; justify-content: space-between; align-items: center;
		flex-wrap: wrap; gap: .4rem; margin-bottom: .55rem;
	}
	.membre-card-title { font-size: .875rem; font-weight: 600; }
	.nom-upper { text-transform: uppercase; }
	.membre-card-actions { display: flex; gap: .3rem; align-items: center; }

	/* Boutons icône */
	.btn-icon {
		width: 2rem; height: 2rem; border-radius: var(--radius);
		border: 1px solid var(--color-border); background: var(--color-bg);
		cursor: pointer; font-size: 1rem; display: flex; align-items: center;
		justify-content: center; transition: background .15s, border-color .15s;
		padding: 0;
	}
	.btn-icon:disabled { opacity: .5; cursor: not-allowed; }
	.btn-icon-save:hover:not(:disabled) { background: #dbeafe; border-color: #3b82f6; }
	.btn-icon-remove { border-color: var(--color-danger); color: var(--color-danger); }
	.btn-icon-remove:hover { background: var(--color-danger); color: #fff; }
	.btn-icon-star { border-color: var(--color-accent, #C9983A); color: var(--color-accent, #C9983A); font-size: .875rem; }
	.btn-icon-star:hover { background: var(--color-accent, #C9983A); color: #fff; }

	/* Badge principal */
	.badge-principal {
		display: inline-block; font-size: .72rem; font-weight: 700;
		background: var(--color-accent, #C9983A); color: #fff;
		border-radius: 999px; padding: .1rem .55rem;
		text-transform: uppercase; letter-spacing: .04em;
	}
	.badge-president {
		display: inline-block; font-size: .72rem; font-weight: 700;
		background: #fbbf24; color: #7c2d12;
		border-radius: 999px; padding: .1rem .55rem;
		text-transform: uppercase; letter-spacing: .04em;
	}

	/* Localisation auto */
	.localisation-info {
		font-size: .8rem; color: var(--color-primary); margin: .35rem 0 .5rem;
		padding: .25rem .5rem; background: #eff6ff;
		border-radius: var(--radius); display: inline-block;
	}

	/* Recherche inscrit */
	.user-search-wrap { margin-top: .65rem; position: relative; }
	.user-search-label { font-size: .8rem; color: var(--color-text-muted); display: flex; align-items: center; gap: .4rem; flex-wrap: wrap; }
	.user-search-input { font-size: .8rem; padding: .25rem .4rem; border: 1px solid var(--color-border); border-radius: var(--radius); background: var(--color-bg); min-width: 180px; }
	.user-suggestions {
		list-style: none; margin: .25rem 0 0; padding: 0;
		border: 1px solid var(--color-border); border-radius: var(--radius);
		background: var(--color-bg); box-shadow: 0 4px 12px rgba(0,0,0,.08);
		max-height: 220px; overflow-y: auto; z-index: 10; position: relative;
	}
	.sugg-bat { font-size: .75rem; color: var(--color-text-muted); }
	.user-no-result { font-size: .78rem; color: var(--color-text-muted); margin: .25rem 0 0; padding: .35rem .5rem; }
	.user-link-indicator { margin-top: .5rem; }
	.user-no-match { font-size: .78rem; color: var(--color-text-muted); font-style: italic; }
	.cs-role-flags {
		display: flex;
		flex-direction: column;
		gap: .35rem;
		margin-top: .65rem;
	}
	.cs-role-flag {
		display: inline-flex;
		align-items: center;
		gap: .45rem;
		font-size: .8rem;
		color: var(--color-text);
	}
	.cs-role-flag input { accent-color: var(--color-primary); }
	.user-linked {
		display: inline-flex; align-items: center; gap: .6rem; font-size: .8rem;
		color: #16a34a; background: #f0fdf4; border-radius: var(--radius);
		padding: .3rem .6rem; border: 1px solid #bbf7d0;
	}
	.btn-unlink {
		font-size: .75rem; background: none; border: none; cursor: pointer;
		color: var(--color-text-muted); text-decoration: underline; padding: 0;
	}
	.btn-unlink:hover { color: var(--color-danger); }

	/* Header inline-edit */
	.header-summary {
		display: flex; align-items: center; gap: .5rem; flex-wrap: wrap;
		font-size: .875rem; color: var(--color-text-muted);
		margin-bottom: 1rem; padding: .4rem 0;
	}
	.header-edit-actions { display: flex; gap: .5rem; align-items: center; padding-top: .25rem; }

	/* Mode replié */
	.membre-summary { display: flex; flex-wrap: wrap; align-items: center; gap: .4rem; margin-top: .25rem; }
	.summary-loc { font-size: .8rem; color: var(--color-text-muted); }
	.summary-fonction { font-size: .8rem; font-weight: 600; color: var(--color-text); }
	.summary-role-badge {
		font-size: .74rem;
		font-weight: 600;
		color: #0f766e;
		background: #ecfeff;
		border: 1px solid #99f6e4;
		border-radius: 999px;
		padding: .12rem .48rem;
	}
	.summary-role-badge-president {
		color: #7c2d12;
		background: #fffbeb;
		border-color: #fcd34d;
	}
	.btn-icon-edit { border-color: var(--color-primary); color: var(--color-primary); }
	.btn-icon-edit:hover { background: var(--color-primary); color: #fff; }
	.btn-icon-move { border-color: var(--color-border); color: var(--color-text-muted); font-size: .85rem; }
	.btn-icon-move:hover:not(:disabled) { background: var(--color-bg-secondary, #f8f9fa); color: var(--color-text); }
	.btn-icon-move:disabled { opacity: .25; cursor: not-allowed; }

	/* Tickets CS */
	.tk-expand { margin-bottom: .3rem; border-left: 4px solid var(--color-border); border-radius: var(--radius); overflow: visible; position: relative; background: var(--color-surface); transition: border-left-color .12s; }
	.tk-expand:hover, .tk-expand.expanded { border-left-color: var(--color-primary); }
	.tk-expand.urgent { border-left-color: var(--color-danger); }
	.tk-row { display: flex; align-items: center; gap: .6rem; padding: .6rem .9rem; cursor: pointer; user-select: none; transition: background .12s; }
	.tk-main { display: flex; flex-direction: column; gap: .25rem; flex: 1; min-width: 0; overflow: hidden; }
	.tk-row-inner { display: flex; align-items: center; gap: .4rem; flex: 1; min-width: 0; overflow: hidden; }
	.tk-cat { flex-shrink: 0; font-size: .95rem; }
	.tk-row-titre { font-size: .9rem; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.tk-row-right { display: flex; align-items: center; gap: .3rem; flex-shrink: 0; }
	.tk-row-date { font-size: .78rem; color: var(--color-text-muted); margin-right: .3rem; white-space: nowrap; }
	.tk-ticket-meta { display: flex; gap: .6rem; flex-wrap: wrap; font-size: .78rem; color: var(--color-text-muted); }
	.tk-preview { padding: .4rem 1rem .6rem; font-size: .875rem; line-height: 1.6; color: var(--color-text-muted); }
	.tk-preview :global(p) { margin: 0 0 .4em; }
	.tk-body { padding: .75rem 1rem 1rem; border-top: 1px solid var(--color-border); }
	.tk-context-meta { display: flex; gap: .5rem; flex-wrap: wrap; margin-bottom: .65rem; }
	.context-chip {
		display: inline-flex; align-items: center; gap: .25rem;
		padding: .2rem .55rem; border-radius: 999px;
		background: var(--color-bg); border: 1px solid var(--color-border);
		font-size: .78rem; color: var(--color-text-muted);
	}
	.rich-content { font-size: .85rem; line-height: 1.6; color: var(--color-text); }
	.rich-content :global(p) { margin: 0 0 .5em; }
	/*  Les onze règles du FIL sont parties avec lui dans `RubriqueHistorique`
	    (19/08/2026) : la page le recomposait à la main, jusqu'à l'icône. Les
	    garder ici en ferait des règles orphelines — la moitié du défaut que
	    `lint:classes-nues` surveille par l'autre bout. `.evol-form` reste : il
	    habille le formulaire d'évolution, que cette page ouvre encore. */
	.evol-form { padding: .25rem 0; }
	/*  `.field label` et `.field textarea` : morts, retirés le 18/08/2026. */
	.field select { padding: .4rem .55rem; border: 1px solid var(--color-border); border-radius: var(--radius); font-size: .875rem; background: var(--color-bg); }
	/*  Trois couleurs de badge réécrites ici en `:global(…)`, donc pour tout le
	    site une fois cette feuille chargée. Retirées (#562) : la charte de
	    `styles/composants.css` les porte déjà. */

	/* Reporting */
	/*  Les trente-six règles `.ah-*` sont parties avec `OngletAnnoncesHall` :
	    Svelte scope les styles au composant qui rend le balisage, et les laisser
	    ici aurait livré l'onglet entièrement NU (v2.67.11). */







  /* Archives des tickets clos */
  /*  🔴 Onze règles sont parties avec `ArchivesParAnnee` et `SectionRepliee` :
      le bandeau, son compteur, son chevron, et tout le groupement par année.
      Svelte scope les styles au composant qui rend le balisage — les laisser
      ici les aurait rendues inertes, pas dangereuses, mais elles auraient
      continué d'être lues comme la référence du rendu (#516).

      Ne restent que les deux qui habillent ce que CETTE page rend encore :
      l'encadré de la section, et la ligne d'un ticket archivé (contenu du
      `slot`, donc dans la portée de la page). */
  /*  Séparateur : celui de `SectionRepliee`, dessiné ici AUSSI jusqu'au 20/08 (#536). */
  .history-item { border-left: 4px solid var(--color-border); border-radius: var(--radius); background: var(--color-surface); opacity: .8; transition: opacity .15s, border-left-color .15s; }
  .history-item:hover { opacity: 1; }
  .history-item.expanded { opacity: 1; }

</style>