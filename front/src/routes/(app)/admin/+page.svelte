<script lang="ts">
	import { nomAffiche } from '$lib/noms';
	import { onMount } from 'svelte';
	import { get } from 'svelte/store';
	import TachesPlanifiees from '$lib/components/TachesPlanifiees.svelte';
	import { api, config as configApi } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import { PAGES, ordonnerPages, type PageDef, defautsDePage, configDepuisPage } from '$lib/pages';
	import EntetePage from '$lib/components/EntetePage.svelte';
	import Modale from '$lib/components/Modale.svelte';
	import FormulaireUtilisateur from '$lib/components/FormulaireUtilisateur.svelte';
	import IntegriteReferentielle from '$lib/components/IntegriteReferentielle.svelte';
	import { CONFIG_SITE_DEFAUT, ecrireConfigSite, lireConfigSite } from '$lib/configSite';
	import LegalEditor from '$lib/components/LegalEditor.svelte';
	import RichEditor from '$lib/components/RichEditor.svelte';
	import OngletCopropriete from '$lib/components/OngletCopropriete.svelte';
	import OngletSite from '$lib/components/OngletSite.svelte';
	import OngletPerimetres from '$lib/components/OngletPerimetres.svelte';
	import OngletAuditLots from '$lib/components/OngletAuditLots.svelte';
	import OngletImportLots from '$lib/components/OngletImportLots.svelte';
	import OngletImportAcces from '$lib/components/OngletImportAcces.svelte';
	import { IMPORT_TELECOMMANDES, IMPORT_VIGIK } from '$lib/imports-acces';
	import Onglet from '$lib/components/Onglet.svelte';
	import OngletWhatsApp from '$lib/components/OngletWhatsApp.svelte';
	import OngletSmtp from '$lib/components/OngletSmtp.svelte';
	import OngletTelemetrie from '$lib/components/OngletTelemetrie.svelte';
	import OngletCsp from '$lib/components/OngletCsp.svelte';
	import OngletModelesEmail from '$lib/components/OngletModelesEmail.svelte';
	import { safeHtml } from '$lib/sanitize';
	import { fmtDatetimeShort as fmt } from '$lib/date';
	import { trackTabView } from '$lib/telemetry';

	//  Onglets
	// 'sauvegardes' retiré le 02/08/2026 : ce bloc n'était accessible par AUCUN
	// bouton et dupliquait, dans une version divergente (accents perdus), celui de
	// « Paramétrage site ». Les deux vivent désormais dans le sous-onglet Maintenance.
	//  🔴 La liste des onglets est écrite ICI et NULLE PART AILLEURS. Depuis le
	//  19/08/2026 elle couvre aussi les sept écrans qui vivaient sur leur propre
	//  route : on ne quitte plus Paramétrage, donc plus aucun « ← Retour ».
	//  `ONGLETS` sert au type ET à la lecture de `?onglet=` — deux listes
	//  divergeraient au premier onglet ajouté, et c’est l’adressage direct qui
	//  cesserait de fonctionner en silence.
	const ONGLETS = [
		'comptes',
		'acces',
		'emails',
		'utilisateurs',
		'demandes_profil',
		'site',
		'pages',
		'legal',
		'whatsapp',
		'smtp',
		'telemetry',
		'csp',
		'maintenance',
		'copropriete',
		'perimetres',
		'audit_lots',
		'import_lots',
		'import_tc',
		'import_vigik',
	] as const;
	type OngletAdmin = (typeof ONGLETS)[number];
	let onglet: OngletAdmin = 'comptes';
	$: trackTabView(onglet);

	//  Bâtiments (pour affichage)
	let batimentsMap: Record<number, string> = {};
	async function loadBatiments() {
		try {
			const list = await api.get<{ id: number; numero: string }[]>('/auth/batiments');
			batimentsMap = Object.fromEntries(
				list.map((b: { id: number; numero: string }) => [b.id, `Bât. ${b.numero}`]),
			);

			batimentsList = list;
		} catch {
			/* non bloquant */
		}
	}

	//  Comptes en attente
	let comptes: any[] = [];
	let comptesLoading = true;
	let refusMotif: Record<number, string> = {};
	let refusOpen: Record<number, boolean> = {};

	async function loadComptes() {
		comptesLoading = true;
		try {
			comptes = await api.get<any[]>('/admin/comptes-en-attente/enrichis');
		} finally {
			comptesLoading = false;
		}
	}

	async function refuserCompte(id: number) {
		try {
			await api.post(`/admin/comptes/${id}/traiter`, { action: 'refuser', motif: refusMotif[id] });
			toast('info', 'Compte refusé.');
			comptes = comptes.filter((c) => (c.user?.id ?? c.id) !== id);
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		}
	}

	async function relancerAutoMatch(userId: number, userNom: string) {
		try {
			const res = await api.post<any>(`/admin/utilisateurs/${userId}/auto-match`, {});
			const lots = res?.auto_match?.lots_resolus ?? 0;
			const lotsM = res?.auto_match?.lots ?? 0;
			if (lots > 0) toast('success', `${userNom} — ${lots} lot(s) résolu(s) automatiquement.`);
			else if (lotsM > 0)
				toast('success', `${userNom} — ${lotsM} lot(s) matché(s) (en attente de résolution).`);
			else toast('info', `${userNom} — Aucun import trouvé pour ce nom.`);
			await loadUtilisateurs();
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur auto-match');
		}
	}

	//  Commandes d'acces
	let commandes: any[] = [];
	let commandesLoading = true;
	let cmdMotif: Record<number, string> = {};
	let cmdRefusOpen: Record<number, boolean> = {};

	async function loadCommandes() {
		commandesLoading = true;
		try {
			commandes = await api.get<any[]>('/admin/commandes-acces');
		} finally {
			commandesLoading = false;
		}
	}

	async function accepterCommande(id: number) {
		try {
			await api.post(`/admin/commandes-acces/${id}/traiter`, { action: 'accepter' });
			toast('success', 'Commande acceptee.');
			commandes = commandes.filter((c) => c.id !== id);
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		}
	}

	async function refuserCommande(id: number) {
		try {
			await api.post(`/admin/commandes-acces/${id}/traiter`, {
				action: 'refuser',
				motif_refus: cmdMotif[id],
			});
			toast('info', 'Commande refusee.');
			commandes = commandes.filter((c) => c.id !== id);
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		}
	}

	//  Le sous-onglet Maintenance ne charge plus rien lui-même : `TachesPlanifiees`
	//  charge sa synthèse, déplie l'historique de la tâche qu'on ouvre et porte son
	//  bouton de lancement. Les deux cartes qui doublaient tout cela sont parties
	//  avec #299, et avec elles `historique`, `historiqueTelemetrie` et leurs
	//  déclencheurs — précharger ici des tableaux que plus personne n'affiche aurait
	//  laissé deux appels d'API sans lecteur.

	//  Utilisateurs & rôles
	let utilisateurs: any[] = [];
	let utilisateursLoading = true;
	let userSearch = '';
	let userStatutFilter = '';
	let userCompteFilter = '';
	let roleEnCours: { user: any; role: string; action: 'ajouter' | 'retirer' } | null = null;
	let editUser: any | null = null;
	let editForm = {
		nom: '',
		prenom: '',
		email: '',
		telephone: '',
		societe: '',
		statut: '',
		batiment_id: null as number | null,
		actif: true,
	};
	let deleteConfirm: any | null = null;
	let batimentsList: { id: number; numero: string }[] = [];

	// Validation modal (comptes en attente + Nouvel Arrivant)
	let cvModal: { user: any; lotsPrevus: number } | null = null;
	let cvNewArrivant = false;
	let cvBatiment = '';
	let cvAncienResident = '';
	let cvSubmitting = false;

	function openCompteValidation(item: any) {
		const u = item.user ?? item;
		cvModal = { user: u, lotsPrevus: item.lots_prevus ?? 0 };
		cvNewArrivant = false;
		cvBatiment = u.batiment_id ? (batimentsMap[u.batiment_id] ?? '') : '';
		cvAncienResident = '';
	}

	async function confirmerCompteValidation() {
		if (!cvModal) return;
		const u = cvModal.user;
		cvSubmitting = true;
		try {
			const res = await api.post<any>(`/admin/comptes/${u.id}/traiter`, { action: 'valider' });
			const lots = res?.auto_match?.lots_resolus ?? 0;
			const lotsMatches = res?.auto_match?.lots ?? 0;
			const aideMatch = res?.auto_match?.aide_match;
			if (aideMatch?.aide_trouve) {
				const parts = [`Compte activé — aidé(e) : ${aideMatch.aide_nom}`];
				if (aideMatch.lots > 0) parts.push(`${aideMatch.lots} lot(s)`);
				if (aideMatch.tc > 0) parts.push(`${aideMatch.tc} TC`);
				if (aideMatch.vigik > 0) parts.push(`${aideMatch.vigik} vigik`);
				if (aideMatch.delegation) parts.push('délégation créée');
				toast('success', parts.join(' — '));
			} else if (aideMatch && !aideMatch.aide_trouve) {
				toast(
					'warning',
					`Compte activé — ⚠️ Copropriétaire aidé(e) « ${nomAffiche(u.prenom_aide, u.nom_aide)} » non trouvé(e). Affectation manuelle requise.`,
				);
			} else if (lots > 0)
				toast('success', `Compte activé — ${lots} lot(s) résolu(s) automatiquement.`);
			else if (lotsMatches > 0)
				toast('success', `Compte activé — ${lotsMatches} lot(s) trouvé(s) dans l'import.`);
			else if (u.statut?.startsWith('copropriétaire'))
				toast('warning', "Compte activé — ⚠️ Aucun lot trouvé dans l'import.");
			else toast('success', 'Compte activé.');
			comptes = comptes.filter((c) => (c.user?.id ?? c.id) !== u.id);
			if (cvNewArrivant) {
				await api.post(`/admin/utilisateurs/${u.id}/accueil-arrivant`, {
					batiment: cvBatiment || null,
					ancien_resident: cvAncienResident || null,
				});
				toast('success', "Actions d'accueil envoyées (bienvenue, consignes, demandes syndic/CS).");
			}
			cvModal = null;
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		} finally {
			cvSubmitting = false;
		}
	}

	// Accueil arrivant (utilisateur existant)
	let accueilModal: { user: any } | null = null;
	let accueilBatiment = '';
	let accueilAncienResident = '';
	let accueilSubmitting = false;

	function openAccueilModal(u: any) {
		accueilModal = { user: u };
		accueilBatiment = u.batiment_id ? (batimentsMap[u.batiment_id] ?? '') : '';
		accueilAncienResident = '';
	}

	async function confirmerAccueil() {
		if (!accueilModal) return;
		const u = accueilModal.user;
		accueilSubmitting = true;
		try {
			await api.post(`/admin/utilisateurs/${u.id}/accueil-arrivant`, {
				batiment: accueilBatiment || null,
				ancien_resident: accueilAncienResident || null,
			});
			toast('success', `Actions d'accueil envoyées pour ${nomAffiche(u)}.`);
			accueilModal = null;
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		} finally {
			accueilSubmitting = false;
		}
	}

	async function loadUtilisateurs() {
		utilisateursLoading = true;
		try {
			utilisateurs = await api.get<any[]>('/admin/utilisateurs');
		} finally {
			utilisateursLoading = false;
		}
	}

	function demanderRole(u: any, role: string, action: 'ajouter' | 'retirer') {
		roleEnCours = { user: u, role, action };
	}

	async function confirmerRole() {
		if (!roleEnCours) return;
		const { user, role, action } = roleEnCours;
		try {
			const endpoint =
				action === 'ajouter'
					? `/admin/utilisateurs/${user.id}/ajouter-role`
					: `/admin/utilisateurs/${user.id}/retirer-role`;
			const updated = await api.post<any>(endpoint, { role });
			toast(
				'success',
				`Rôle ${roleLabels[role] ?? role} ${action === 'ajouter' ? 'ajouté à' : 'retiré de'} ${nomAffiche(user)}.`,
			);
			utilisateurs = utilisateurs.map((u) => (u.id === user.id ? { ...u, ...updated } : u));
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		} finally {
			roleEnCours = null;
		}
	}

	function openEdit(u: any) {
		editForm = {
			nom: u.nom,
			prenom: u.prenom,
			email: u.email,
			telephone: u.telephone ?? '',
			societe: u.societe ?? '',
			statut: u.statut,
			batiment_id: u.batiment_id ?? null,
			actif: u.actif,
		};
		editUser = u;
	}

	async function saveEdit() {
		if (!editUser) return;
		try {
			const updated = await api.patch<any>(`/admin/utilisateurs/${editUser.id}`, editForm);
			utilisateurs = utilisateurs.map((u) => (u.id === editUser!.id ? { ...u, ...updated } : u));
			toast('success', 'Utilisateur mis à jour.');
			editUser = null;
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		}
	}

	async function confirmerDelete() {
		if (!deleteConfirm) return;
		const target = deleteConfirm;
		deleteConfirm = null;
		try {
			await api.delete(`/admin/utilisateurs/${target.id}`);
			utilisateurs = utilisateurs.filter((u) => u.id !== target.id);
			toast('success', `${nomAffiche(target)} supprimé.`);
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		}
	}

	async function toggleBanCommunaute(u: any) {
		const isBanned =
			u.communaute_interdit ||
			(u.communaute_ban_jusqu_au && new Date(u.communaute_ban_jusqu_au) > new Date());
		const interdit = !isBanned;
		try {
			const updated = await api.patch<any>(`/admin/utilisateurs/${u.id}/ban-communaute`, {
				interdit,
			});
			utilisateurs = utilisateurs.map((x) => (x.id === u.id ? { ...x, ...updated } : x));
			if (interdit) {
				const msg = updated.communaute_interdit
					? `${nomAffiche(u)} banni définitivement de la communauté.`
					: `${nomAffiche(u)} banni de la communauté pour 1 mois (probatoire).`;
				toast('success', msg);
			} else {
				toast('success', `${nomAffiche(u)} réautorisé à la communauté.`);
			}
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		}
	}

	$: nbCS = utilisateurs.filter((u) => (u.roles ?? [u.role]).includes('conseil_syndical')).length;

	$: filteredUsers = utilisateurs
		.filter((u) => {
			if (userStatutFilter && u.statut !== userStatutFilter) return false;
			if (userCompteFilter === 'actif' && !u.actif) return false;
			if (userCompteFilter === 'inactif' && u.actif) return false;
			if (!userSearch.trim()) return true;
			const q = userSearch.toLowerCase();
			return (
				(u.prenom + ' ' + u.nom).toLowerCase().includes(q) || u.email.toLowerCase().includes(q)
			);
		})
		.sort((a, b) => {
			const nomCmp = (a.nom ?? '').localeCompare(b.nom ?? '', 'fr', { sensitivity: 'base' });
			if (nomCmp !== 0) return nomCmp;
			return (a.prenom ?? '').localeCompare(b.prenom ?? '', 'fr', { sensitivity: 'base' });
		});

	const roleLabels: Record<string, string> = {
		propriétaire: 'Propriétaire',
		résident: 'Résident',
		externe: 'Externe',
		conseil_syndical: 'Conseil syndical',
		admin: 'Admin',
		// legacy / compat
		locataire: 'Locataire',
		copropriétaire_résident: 'Copropriétaire Résident',
		copropriétaire_bailleur: 'Copropriétaire Bailleur',
		bailleur: 'Copropriétaire Bailleur',
		syndic: 'Syndic',
		mandataire: 'Mandataire',
	};

	const roleBadgeClass: Record<string, string> = {
		propriétaire: 'badge-teal',
		résident: 'badge-gray',
		externe: 'badge-yellow',
		conseil_syndical: 'badge-blue',
		admin: 'badge-orange',
		// legacy
		locataire: 'badge-gray',
		copropriétaire_résident: 'badge-teal',
		copropriétaire_bailleur: 'badge-purple',
		bailleur: 'badge-purple',
		syndic: 'badge-orange',
		mandataire: 'badge-yellow',
	};

	const statutLabels: Record<string, string> = {
		copropriétaire_résident: 'Copro. résident',
		copropriétaire_bailleur: 'Copro. bailleur',
		locataire: 'Locataire',
		syndic: 'Syndic',
		mandataire: 'Mandataire',
		aidant: 'Aidant (proche)',
		admin_technique: 'Admin technique',
	};

	const statutBadgeClass: Record<string, string> = {
		copropriétaire_résident: 'badge-green',
		copropriétaire_bailleur: 'badge-blue',
		locataire: 'badge-purple',
		syndic: 'badge-orange',
		mandataire: 'badge-gray',
		aidant: 'badge-yellow',
		admin_technique: 'badge-orange',
	};

	function userRoles(u: any): string[] {
		return u.roles?.length ? u.roles : [u.role];
	}

	// Rôles actifs : affiche les rôles réels (P·R·E·CS·A) depuis u.roles
	function displayRoles(u: any): { label: string; cls: string }[] {
		const roles: string[] = u.roles?.length ? u.roles : [u.role];
		return roles.map((r: string) => ({
			label: roleLabels[r] ?? r,
			cls: roleBadgeClass[r] ?? 'badge-gray',
		}));
	}

	function userBatimentLabel(u: any): string {
		if (u.batiment_id && batimentsMap[u.batiment_id]) return batimentsMap[u.batiment_id];
		if (u.batiment_nom) return u.batiment_nom;
		if (u.batiment_id) return `Bât. ${u.batiment_id}`;
		return '—';
	}

	//  Demandes de modification de profil
	let demandesProfil: any[] = [];
	let demandesProfilLoading = true;
	let refusDemande: Record<number, string> = {};
	let refusDemandeOpen: Record<number, boolean> = {};

	const statutLabelsAdmin: Record<string, string> = {
		copropriétaire_résident: 'Copro. résident',
		copropriétaire_bailleur: 'Copro. bailleur',
		locataire: 'Locataire',
		syndic: 'Syndic',
		mandataire: 'Mandataire',
		aidant: 'Aidant (proche)',
	};

	async function loadDemandesProfil() {
		demandesProfilLoading = true;
		try {
			demandesProfil = await api.get<any[]>('/admin/demandes-profil');
		} catch {
			/* ignore */
		} finally {
			demandesProfilLoading = false;
		}
	}

	async function approuverDemande(id: number) {
		try {
			await api.post(`/admin/demandes-profil/${id}/traiter`, { action: 'approuver' });
			toast('success', 'Demande approuvée.');
			demandesProfil = demandesProfil.filter((d) => d.id !== id);
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		}
	}

	async function rejeterDemande(id: number) {
		try {
			await api.post(`/admin/demandes-profil/${id}/traiter`, {
				action: 'rejeter',
				motif_refus: refusDemande[id] || null,
			});
			toast('info', 'Demande rejetée.');
			demandesProfil = demandesProfil.filter((d) => d.id !== id);
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		} finally {
			refusDemandeOpen[id] = false;
		}
	}

	//  Montage
	onMount(async () => {
		//  Adressage direct d’un onglet : `?onglet=perimetres`. Il remplace les sept
		//  routes `/admin/<ecran>` supprimées le 19/08/2026 — sans lui, un signet ou un
		//  lien vers un de ces écrans n’aurait plus AUCUN équivalent, et la conversion
		//  en onglets aurait retiré une capacité au lieu d’en uniformiser une.
		//  La validation se fait sur `ONGLETS`, la liste unique : une valeur inconnue
		//  est ignorée, jamais affichée.
		const demande = new URLSearchParams(window.location.search).get('onglet');
		if (demande && (ONGLETS as readonly string[]).includes(demande))
			onglet = demande as OngletAdmin;
		await loadSiteConfig();
		// Paramétrage site — lu depuis `/config/admin` (require_admin) et NON depuis le
		// store : depuis l'audit de sécurité du 26/07/2026, `/api/config` est filtré par
		// liste blanche et n'expose plus que les clés de la coquille d'interface. Les
		// champs édités ici (SMTP, WhatsApp, référence de copropriété, gestionnaire du
		// site…) ne sont accessibles qu'à l'admin, ce qui est précisément le rôle requis
		// pour afficher cet écran. Repli sur le store si l'appel échoue, pour ne pas
		// bloquer le reste de la page.
		let cfg = get(configStore) as Record<string, string>;
		try {
			cfg = { ...cfg, ...(await api.get<Record<string, string>>('/config/admin')) };
		} catch {
			toast('error', 'Impossible de charger le paramétrage complet (droits admin requis).');
		}
		// Les clés légales sont exclues de /api/config (perf) — fetch dédié
		let sMentions = '';
		let sPolitique = '';
		try {
			const r = await fetch('/api/config/legal');
			if (r.ok) {
				const legal = await r.json();
				sMentions = legal['mentions_legales'] ?? '';
				sPolitique = legal['politique_confidentialite'] ?? '';
			}
		} catch {
			/**/
		}
		siteConfig = lireConfigSite(cfg, {
			mentions_legales: sMentions,
			politique_confidentialite: sPolitique,
		});
		// Config des pages
		pagesConfig = pagesDefaults.map((pg) => {
			const s = cfg[`page_config_${pg.id}`];
			if (s) {
				try {
					const saved = normalizeSavedPageDef(JSON.parse(s), pg);
					const mergedOnglets = pg.onglets?.map((o) => {
						const so = saved.onglets?.[o.id];
						if (typeof so === 'string') return { ...o, label: so };
						return {
							id: o.id,
							label: so?.label ?? o.label,
							descriptif: so?.descriptif ?? o.descriptif,
						};
					});
					return { ...pg, ...saved, onglets: mergedOnglets ?? pg.onglets };
				} catch {
					/**/
				}
			}
			return { ...pg };
		});
		// Restaurer l'ordre personnalisé depuis le backend
		const savedOrder = cfg['pages_order'];
		//  `ordonnerPages` relègue les pages sans entrée de menu en fin : voir son en-tête.
		if (savedOrder) {
			try {
				pagesConfig = ordonnerPages(pagesConfig, JSON.parse(savedOrder));
			} catch {
				/**/
			}
		}
		// WhatsApp : la configuration part telle quelle vers l'onglet dédié.
		waCfgPublique = cfg;
		try {
			const adminCfg = await api.get<Record<string, string>>('/config/admin');
			waApiKeySet = !!adminCfg['whatsapp_api_key'];
			// SMTP config
			smtpValeurs = adminCfg;
		} catch {
			/**/
		}
		loadBatiments();
		loadComptes();
		loadCommandes();
		loadDemandesProfil();
	});

	// ── Paramétrage site ──────────────────────────────────────────
	let siteConfig = { ...CONFIG_SITE_DEFAUT };
	let siteSaving = false;
	$: siteManagerUsers = utilisateurs.filter((u) => !!u.email);
	function openSiteTab() {
		onglet = 'site';
		if (utilisateurs.length === 0) loadUtilisateurs();
	}
	async function saveSiteConfig() {
		siteSaving = true;
		try {
			//  🔴 Le MÊME payload part à l'API et rafraîchit le store. Les deux étaient
			//  écrits séparément, et le second oubliait quatre réglages : après
			//  sauvegarde, le store gardait leurs anciennes valeurs jusqu'au
			//  rechargement de la page (#515).
			const payload = ecrireConfigSite(siteConfig);
			await configApi.save(payload);
			configStore.update((c: Record<string, string>) => ({ ...c, ...payload }));
			toast('success', 'Paramètres sauvegardés.');
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur lors de la sauvegarde.');
		} finally {
			siteSaving = false;
		}
	}

	// ── WhatsApp ──────────────────────────────────
	//  L'onglet est un composant à part (`OngletWhatsApp.svelte`) : il porte son
	//  état, ses appels et son rendu. Ne restent ici que les deux valeurs que la
	//  page a déjà chargées et lui transmet.
	let waCfgPublique: Record<string, string> = {};
	let waApiKeySet = false;

	// ── SMTP ────────────────────────────────────────────────────
	// L'onglet vit dans `OngletSmtp.svelte` ; la page ne garde que les valeurs
	// brutes qu'elle a lues, et lui laisse leur interprétation.
	let smtpValeurs: Record<string, string> = {};

	// ── Descriptif des pages ──────────────────────────────────────
	// PageDef et la table des pages viennent de la source unique `$lib/pages.ts` (#401).
	function stripHtmlPreview(html: string) {
		return (html ?? '')
			.replace(/<[^>]+>/g, ' ')
			.replace(/\s+/g, ' ')
			.trim();
	}
	function normalizeSavedPageDef(saved: any, defaults: PageDef) {
		const normalized = { ...saved, onglets: saved?.onglets ? { ...saved.onglets } : undefined };
		if (normalized.onglets) {
			for (const [k, v] of Object.entries(normalized.onglets)) {
				if (typeof v === 'string') {
					(normalized.onglets as any)[k] = {
						label: v,
						descriptif: defaults.onglets?.find((o) => o.id === k)?.descriptif ?? '',
					};
				}
			}
		}
		if (defaults.id === 'prestataires') {
			if (normalized.onglets?.consommation && !normalized.onglets?.consommations) {
				normalized.onglets.consommations = normalized.onglets.consommation;
				delete normalized.onglets.consommation;
			}
		}
		if (defaults.id === 'espace-cs') {
			if (normalized.onglets?.validations?.label === '✅ Validations') {
				normalized.onglets.validations.label =
					defaults.onglets?.find((o) => o.id === 'validations')?.label ??
					normalized.onglets.validations.label;
			}
			if (
				normalized.onglets?.validations?.descriptif ===
				"Comptes en attente de validation et demandes d'accès à traiter."
			) {
				normalized.onglets.validations.descriptif =
					defaults.onglets?.find((o) => o.id === 'validations')?.descriptif ??
					normalized.onglets.validations.descriptif;
			}
		}
		return normalized;
	}
	const pagesDefaults: PageDef[] = PAGES;
	let pagesConfig: PageDef[] = pagesDefaults.map((pg) => ({ ...pg }));
	// Seules les pages du menu s'ordonnent : « Mon profil » et « Notifications » sont
	// atteignables sans entrée de navigation. Elles portaient pourtant des flèches, et
	// leur déplacement était enregistré puis écarté en silence par le menu (#401).
	$: indicesMenu = pagesConfig.map((p, i) => (p.href !== null ? i : -1)).filter((i) => i >= 0);
	let expandedPages = new Set<string>();
	function togglePage(id: string) {
		expandedPages = expandedPages.has(id) ? new Set() : new Set([id]);
	}
	async function savePageConfig(pg: PageDef) {
		// Conversion partagée avec `defautsDePage` (`$lib/pages.ts`, #420) ; `pg` et non son id : ce sont les valeurs ÉDITÉES qui partent.
		const val = JSON.stringify(configDepuisPage(pg));
		try {
			await configApi.save({ [`page_config_${pg.id}`]: val });
			configStore.update((c: Record<string, string>) => ({ ...c, [`page_config_${pg.id}`]: val }));
			toast('success', 'Configuration enregistrée.');
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur lors de la sauvegarde.');
		}
	}
	async function movePage(i: number, dir: number) {
		const arr = [...pagesConfig];
		// On échange avec la page de menu voisine, pas avec la ligne voisine : une page
		// sans entrée de navigation ne participe pas à l'ordre et ne doit pas s'intercaler.
		const rang = indicesMenu.indexOf(i);
		const j = indicesMenu[rang + dir];
		if (rang < 0 || j === undefined) return;
		[arr[i], arr[j]] = [arr[j], arr[i]];
		pagesConfig = arr;
		// `pages_order` ne porte que les pages du menu : y écrire des identifiants que le
		// menu ne connaît pas, c'était fabriquer l'incohérence que `Nav` signale désormais.
		const ordered = JSON.stringify(pagesConfig.filter((p) => p.href !== null).map((p) => p.id));
		configStore.update((c: Record<string, string>) => ({ ...c, pages_order: ordered }));
		try {
			await configApi.save({ pages_order: ordered });
			// Cet écran enregistre au fil de l'eau, sans bouton : jusqu'ici seul l'ÉCHEC
			// parlait, et l'absence de retour laissait croire que rien n'était enregistré.
			toast('success', 'Ordre enregistré.');
		} catch (e: any) {
			toast('error', e.message ?? "Erreur lors de la sauvegarde de l'ordre.");
		}
	}

	import { getPageConfig, configStore, siteNomStore, loadSiteConfig } from '$lib/stores/pageConfig';
	$: _pc = getPageConfig($configStore, 'admin', defautsDePage('admin'));
	$: _siteNom = $siteNomStore;
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<EntetePage titre={_pc.titre} icone={_pc.icone || 'sliders-horizontal'} />
<div class="page-subtitle">{@html safeHtml(_pc.descriptif)}</div>

<!--  Tous les onglets passent par `Onglet` — ceux qui basculent un panneau comme
      ceux qui mènent ailleurs. C'est ce qui garantit qu'ils se ressemblent :
      quinze onglets écrits à la main, et le seizième réintroduit l'écart. -->
<div class="tabs-group">
	<div class="tabs-group-label">&#x1F465; Gestion utilisateurs</div>
	<div class="tabs">
		<Onglet
			actif={onglet === 'comptes'}
			compte={comptes.length}
			on:click={() => (onglet = 'comptes')}
		>
			Comptes en attente
		</Onglet>
		<Onglet
			actif={onglet === 'acces'}
			compte={commandes.length}
			on:click={() => (onglet = 'acces')}
		>
			Commandes d'accès
		</Onglet>
		<Onglet
			actif={onglet === 'utilisateurs'}
			on:click={() => {
				onglet = 'utilisateurs';
				loadUtilisateurs();
			}}
		>
			Utilisateurs
		</Onglet>
		<Onglet
			actif={onglet === 'demandes_profil'}
			compte={demandesProfil.length}
			on:click={() => (onglet = 'demandes_profil')}
		>
			Demandes profil
		</Onglet>
		<Onglet actif={onglet === 'emails'} on:click={() => (onglet = 'emails')}>Modèles e-mail</Onglet>
		<Onglet actif={onglet === 'import_lots'} on:click={() => (onglet = 'import_lots')}
			>Import Lots</Onglet
		>
		<Onglet actif={onglet === 'import_tc'} on:click={() => (onglet = 'import_tc')}>Import TC</Onglet
		>
		<Onglet actif={onglet === 'import_vigik'} on:click={() => (onglet = 'import_vigik')}
			>Import Vigik</Onglet
		>
		<Onglet actif={onglet === 'audit_lots'} on:click={() => (onglet = 'audit_lots')}
			>Audit lots</Onglet
		>
	</div>
</div>

<div class="tabs-group" style="margin-top:.5rem;margin-bottom:1.5rem">
	<div class="tabs-group-label">⚙️ Configuration</div>
	<div class="tabs" style="margin-bottom:0">
		<Onglet actif={onglet === 'site'} on:click={openSiteTab}>Paramétrage site</Onglet>
		<Onglet actif={onglet === 'copropriete'} on:click={() => (onglet = 'copropriete')}
			>Fiche copropriété</Onglet
		>
		<Onglet actif={onglet === 'perimetres'} on:click={() => (onglet = 'perimetres')}
			>Périmètres</Onglet
		>
		<Onglet actif={onglet === 'pages'} on:click={() => (onglet = 'pages')}>Descriptif pages</Onglet>
		<Onglet actif={onglet === 'legal'} on:click={() => (onglet = 'legal')}>Pages légales</Onglet>
		<!--  Pas d'icône sur un onglet : 4 sur 15 en portaient une — une par le
          composant `Icon`, trois en emoji — et les onze autres non. On uniformise
          sur la forme la plus répandue (`standards/11` §1 bis), qui est aussi
          celle du pattern d'onglets (`ux-patterns` §4). Signalé à l'écran le
          16/08/2026, capture à l'appui. -->
		<Onglet actif={onglet === 'whatsapp'} on:click={() => (onglet = 'whatsapp')}>WhatsApp</Onglet>
		<Onglet actif={onglet === 'smtp'} on:click={() => (onglet = 'smtp')}>SMTP</Onglet>
		<Onglet actif={onglet === 'telemetry'} on:click={() => (onglet = 'telemetry')}
			>Télémétrie</Onglet
		>
		<Onglet actif={onglet === 'csp'} on:click={() => (onglet = 'csp')}>Sécurité (CSP)</Onglet>
		<Onglet actif={onglet === 'maintenance'} on:click={() => (onglet = 'maintenance')}
			>Maintenance</Onglet
		>
	</div>
</div>

{#if onglet === 'comptes'}
	{#if comptesLoading}
		<p class="muted">Chargement...</p>
	{:else if comptes.length === 0}
		<div class="empty-state">
			<h3>Aucun compte en attente</h3>
			<p>Tous les comptes ont ete traites.</p>
		</div>
	{:else}
		<div class="card" style="overflow:hidden">
			<table class="table">
				<thead>
					<tr>
						<th>Nom</th><th>Statut</th><th>Rôle(s)</th><th>Bât.</th><th>Lots import</th><th
							>Inscription</th
						><th>Actions</th>
					</tr>
				</thead>
				<tbody>
					{#each comptes as item ((item.user ?? item).id)}
						{@const u = item.user ?? item}
						<tr>
							<td style="font-weight:500"
								>{nomAffiche(u)}
								{#if u.statut === 'locataire' && u.nom_proprietaire}
									<div style="font-size:.75rem;color:var(--color-text-muted);margin-top:.15rem">
										&#x1F464; Prop. : {u.nom_proprietaire}
									</div>
								{/if}
								{#if (u.statut === 'aidant' || u.statut === 'mandataire') && u.nom_aide}
									<div style="font-size:.75rem;color:var(--color-text-muted);margin-top:.15rem">
										&#x1F464; Aidé : {u.prenom_aide}
										{u.nom_aide}
									</div>
								{/if}
							</td>
							<td
								><span
									class="badge {statutBadgeClass[u.statut] ?? 'badge-gray'}"
									style="font-size:.75rem">{statutLabels[u.statut] ?? u.statut}</span
								></td
							>
							<td>
								<div style="display:flex;gap:.25rem;flex-wrap:wrap">
									{#each u.roles?.length ? u.roles : [u.role] as r}
										<span class="badge {roleBadgeClass[r] ?? 'badge-gray'}" style="font-size:.75rem"
											>{roleLabels[r] ?? r}</span
										>
									{/each}
								</div>
							</td>
							<td style="color:var(--color-text-muted)"
								>{u.batiment_id ? (batimentsMap[u.batiment_id] ?? `#${u.batiment_id}`) : '—'}</td
							>
							<td>
								{#if item.lots_prevus > 0}
									<span
										class="badge badge-green"
										title="{item.lots_prevus} lot(s) trouvé(s) dans l'import"
										>✓ {item.lots_prevus}</span
									>
								{:else if u.statut?.startsWith('copropriétaire')}
									<span class="badge badge-orange" title="Pas trouvé dans l'import Lots">⚠ 0</span>
								{:else}
									<span style="color:var(--color-text-muted)">—</span>
								{/if}
							</td>
							<td style="color:var(--color-text-muted);font-size:.8rem">{fmt(u.cree_le)}</td>
							<td>
								<div class="action-row">
									<button class="btn btn-primary btn-sm" on:click={() => openCompteValidation(item)}
										>Valider →</button
									>
									{#if !refusOpen[u.id]}
										<button class="btn btn-danger btn-sm" on:click={() => (refusOpen[u.id] = true)}
											>Refuser</button
										>
									{:else}
										<div class="refus-inline">
											<input
												type="text"
												placeholder="Motif (optionnel)"
												bind:value={refusMotif[u.id]}
												class="input-sm"
											/>
											<button
												class="btn btn-outline btn-sm"
												on:click={() => (refusOpen[u.id] = false)}>Annuler</button
											>
											<button class="btn btn-danger btn-sm" on:click={() => refuserCompte(u.id)}
												>Confirmer</button
											>
										</div>
									{/if}
								</div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
{:else if onglet === 'acces'}
	{#if commandesLoading}
		<p class="muted">Chargement...</p>
	{:else if commandes.length === 0}
		<div class="empty-state">
			<h3>Aucune commande en attente</h3>
			<p>Toutes les demandes d'acces ont ete traitees.</p>
		</div>
	{:else}
		<div class="card" style="overflow:hidden">
			<table class="table">
				<thead>
					<tr><th>Utilisateur</th><th>Type</th><th>Lot</th><th>Date</th><th>Actions</th></tr>
				</thead>
				<tbody>
					{#each commandes as cmd (cmd.id)}
						<tr>
							<td style="font-weight:500">#{cmd.user_id}</td>
							<td><span class="badge badge-blue">{cmd.type}</span></td>
							<td style="color:var(--color-text-muted)">{cmd.lot_id ?? ''}</td>
							<td style="color:var(--color-text-muted);font-size:.8rem">{fmt(cmd.cree_le)}</td>
							<td>
								<div class="action-row">
									<button class="btn btn-primary btn-sm" on:click={() => accepterCommande(cmd.id)}
										>Accepter</button
									>
									{#if !cmdRefusOpen[cmd.id]}
										<button
											class="btn btn-danger btn-sm"
											on:click={() => (cmdRefusOpen[cmd.id] = true)}>Refuser</button
										>
									{:else}
										<div class="refus-inline">
											<input
												type="text"
												placeholder="Motif du refus"
												bind:value={cmdMotif[cmd.id]}
												class="input-sm"
											/>
											<button
												class="btn btn-outline btn-sm"
												on:click={() => (cmdRefusOpen[cmd.id] = false)}>Annuler</button
											>
											<button class="btn btn-danger btn-sm" on:click={() => refuserCommande(cmd.id)}
												>Confirmer</button
											>
										</div>
									{/if}
								</div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
{:else if onglet === 'utilisateurs'}
	{#if utilisateursLoading}
		<p class="muted">Chargement...</p>
	{:else}
		<!-- Barre de recherche + filtres + compteurs -->
		<div class="users-toolbar">
			<input
				type="search"
				class="input-sm user-search"
				placeholder="Rechercher par nom ou e-mail…"
				bind:value={userSearch}
			/>
			<select class="input-sm role-select" bind:value={userStatutFilter} style="min-width:160px">
				<option value="">— Tous les types —</option>
				{#each Object.entries(statutLabels) as [val, label] (val)}
					<option value={val}>{label}</option>
				{/each}
			</select>
			<select class="input-sm role-select" bind:value={userCompteFilter} style="min-width:130px">
				<option value="">— Tous comptes —</option>
				<option value="actif">Actifs</option>
				<option value="inactif">En attente</option>
			</select>
			<span class="muted" style="font-size:.8rem">
				{filteredUsers.length} / {utilisateurs.length} utilisateur{utilisateurs.length > 1
					? 's'
					: ''}
				&nbsp;·&nbsp;
				{nbCS} membre{nbCS > 1 ? 's' : ''} CS
			</span>
		</div>

		{#if filteredUsers.length === 0}
			<div class="empty-state"><h3>Aucun résultat</h3></div>
		{:else}
			<div class="card" style="overflow:hidden">
				<table class="table">
					<thead>
						<tr
							><th>Nom</th><th>E-mail</th><th>Type</th><th>Bâtiment</th><th>Compte</th><th
								>Rôles actifs</th
							><th>Ajouter / Retirer un rôle</th><th>Actions</th></tr
						>
					</thead>
					<tbody>
						{#each filteredUsers as u (u.id)}
							<tr
								class:row-cs={userRoles(u).includes('conseil_syndical')}
								class:row-inactive={!u.actif}
							>
								<td style="font-weight:500">
									{nomAffiche(u)}
									{#if u.statut === 'locataire' && u.nom_proprietaire}
										<div style="font-size:.75rem;color:var(--color-text-muted);margin-top:.15rem">
											🏠 Bailleur : {u.nom_proprietaire}
										</div>
									{/if}
									<div class="user-tags">
										{#if u.has_lots}<span class="utag utag-ok">Loti</span>{:else}<span
												class="utag utag-ko">Loti</span
											>{/if}
										{#if u.has_tc}<span class="utag utag-ok">TC</span>{:else}<span
												class="utag utag-ko">TC</span
											>{/if}
										{#if u.has_vigik}<span class="utag utag-ok">Vigik</span>{:else}<span
												class="utag utag-ko">Vigik</span
											>{/if}
										{#if u.has_bail}<span class="utag utag-ok">Lié</span>{:else}<span
												class="utag utag-ko">Lié</span
											>{/if}
									</div>
								</td>
								<td style="color:var(--color-text-muted);font-size:.85rem">{u.email}</td>
								<td>
									<span
										class="badge {statutBadgeClass[u.statut] ?? 'badge-gray'}"
										style="font-size:.75rem"
									>
										{statutLabels[u.statut] ?? u.statut ?? '—'}
									</span>
								</td>
								<td>
									<span class="badge badge-gray">{userBatimentLabel(u)}</span>
								</td>
								<td>
									{#if u.actif}
										<span class="badge badge-green">Actif</span>
									{:else if u.email_verifie === false}
										<span class="badge badge-orange" title="Email non vérifié"
											>Email non vérifié</span
										>
									{:else}
										<span class="badge badge-gray">En attente</span>
									{/if}
								</td>
								<td>
									<div style="display:flex;gap:.3rem;flex-wrap:wrap">
										{#each displayRoles(u) as d (d.label)}
											<span class="badge {d.cls}">{d.label}</span>
										{/each}
									</div>
								</td>
								<td>
									{#if !u.actif}
										<span class="muted" style="font-size:.8rem">Compte inactif</span>
									{:else}
										<div class="action-row">
											<!-- Ajouter CS si pas déjà — réservé aux propriétaires -->
											{#if !userRoles(u).includes('conseil_syndical')}
												{#if u.statut?.startsWith('copropriétaire')}
													<button
														class="btn btn-outline btn-sm"
														style="color:#1d4ed8;border-color:#1d4ed8"
														on:click={() => demanderRole(u, 'conseil_syndical', 'ajouter')}
													>
														+ CS
													</button>
												{/if}
											{:else}
												<button
													class="btn btn-outline btn-sm"
													style="color:#dc2626;border-color:#dc2626"
													on:click={() => demanderRole(u, 'conseil_syndical', 'retirer')}
												>
													– CS
												</button>
											{/if}
											<!-- Ajouter Admin si pas déjà — réservé aux propriétaires -->
											{#if !userRoles(u).includes('admin')}
												{#if u.statut?.startsWith('copropriétaire')}
													<button
														class="btn btn-outline btn-sm"
														style="color:#c2410c;border-color:#c2410c"
														on:click={() => demanderRole(u, 'admin', 'ajouter')}
													>
														+ Admin
													</button>
												{/if}
											{:else}
												<button
													class="btn btn-outline btn-sm"
													style="color:#dc2626;border-color:#dc2626"
													on:click={() => demanderRole(u, 'admin', 'retirer')}
												>
													– Admin
												</button>
											{/if}
										</div>
									{/if}
								</td>
								<td>
									<div class="action-row">
										<button
											class="btn-icon-edit"
											aria-label="Modifier"
											title="Modifier"
											on:click={() => openEdit(u)}>✏️</button
										>
										<button
											class="btn-icon"
											aria-label="Accueil nouvel arrivant"
											title="Accueil nouvel arrivant"
											on:click={() => openAccueilModal(u)}>&#x1F3E0;</button
										>
										{#if u.actif && !u.has_lots}
											<button
												class="btn-icon"
												aria-label="Rejouer auto-match lots"
												title="Rejouer auto-match lots"
												on:click={() => relancerAutoMatch(u.id, nomAffiche(u))}>🔄</button
											>
										{/if}
										<button
											class={u.communaute_interdit ||
											(u.communaute_ban_jusqu_au &&
												new Date(u.communaute_ban_jusqu_au) > new Date())
												? 'btn-icon-success'
												: 'btn-icon-warn'}
											aria-label={u.communaute_interdit ||
											(u.communaute_ban_jusqu_au &&
												new Date(u.communaute_ban_jusqu_au) > new Date())
												? 'Autoriser la communauté'
												: 'Interdire la communauté'}
											title={u.communaute_interdit
												? 'Banni définitivement — cliquer pour débannir'
												: u.communaute_ban_jusqu_au &&
													  new Date(u.communaute_ban_jusqu_au) > new Date()
													? 'Banni 1 mois (probatoire) — cliquer pour débannir'
													: 'Interdire la communauté'}
											on:click={() => toggleBanCommunaute(u)}
										>
											{u.communaute_interdit
												? '⛔'
												: u.communaute_ban_jusqu_au &&
													  new Date(u.communaute_ban_jusqu_au) > new Date()
													? '🔓'
													: '🔒'}
										</button>
										<button
											class="btn-icon-danger"
											aria-label="Supprimer"
											title="Supprimer"
											on:click={() => (deleteConfirm = u)}>&#x1F5D1;️</button
										>
									</div>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{/if}

	<!-- Modal de confirmation rôle -->
	{#if roleEnCours}
		<Modale
			titre="Confirmer"
			classeBoite="modal-box card modal-sm"
			on:fermer={() => (roleEnCours = null)}
		>
			<p style="font-size:.875rem;margin-bottom:1rem">
				{roleEnCours.action === 'ajouter' ? 'Ajouter' : 'Retirer'} le rôle
				<strong>{roleLabels[roleEnCours.role] ?? roleEnCours.role}</strong>
				{roleEnCours.action === 'ajouter' ? 'à' : 'de'}
				<strong>{nomAffiche(roleEnCours.user)}</strong> ?
				<br />
				<span style="font-size:.8rem;color:var(--color-text-muted)">
					Cette personne recevra une notification.
				</span>
			</p>
			<div class="modal-footer">
				<button class="btn btn-outline" on:click={() => (roleEnCours = null)}>Annuler</button>
				<button class="btn btn-primary" on:click={confirmerRole}>Confirmer</button>
			</div>
		</Modale>
	{/if}

	<!-- Modal édition utilisateur -->
	<!-- Éditer un objet existant → la modale, qui déclare son geste (§14 bis, #640). -->
	{#if editUser}
		<Modale
			edition
			titre="Modifier l'utilisateur"
			classeBoite="modal-box card"
			styleBoite="max-width:520px"
			on:fermer={() => (editUser = null)}
		>
			<FormulaireUtilisateur
				bind:editForm
				{statutLabels}
				{batimentsList}
				onAnnuler={() => (editUser = null)}
				onEnregistrer={saveEdit}
			/>
		</Modale>
	{/if}

	{#if accueilModal}
		<Modale
			edition
			titre="🏠 Accueil nouvel arrivant"
			classeBoite="modal-box card"
			styleBoite="max-width:480px"
			on:fermer={() => (accueilModal = null)}
		>
			<p style="font-size:.85rem;margin-bottom:.1rem">
				<strong>{nomAffiche(accueilModal.user)}</strong>
			</p>
			<p style="font-size:.78rem;color:var(--color-text-muted);margin-bottom:.75rem">
				Déclenche : bienvenue, consignes de copropriété, demande d'étiquette BAL (syndic), demande
				d'interphone (CS), avec copie des démarches au résident.
			</p>
			<div class="form-grid" style="margin-bottom:.75rem">
				<label class="field"
					>Bâtiment / logement
					<input bind:value={accueilBatiment} placeholder="Ex: Bât. A, Apt. 12…" />
				</label>
				<label class="field"
					>Ancien résident
					<input bind:value={accueilAncienResident} placeholder="Nom de l'ancien occupant…" />
				</label>
			</div>
			<div class="modal-footer">
				<button class="btn btn-outline" on:click={() => (accueilModal = null)}>Annuler</button>
				<button class="btn btn-primary" disabled={accueilSubmitting} on:click={confirmerAccueil}>
					{accueilSubmitting ? 'En cours…' : "Lancer les actions d'accueil"}
				</button>
			</div>
		</Modale>
	{/if}

	{#if deleteConfirm}
		<Modale
			titre="Supprimer l'utilisateur ?"
			classeBoite="modal-box card modal-sm"
			on:fermer={() => (deleteConfirm = null)}
		>
			<p style="font-size:.875rem;margin-bottom:1rem">
				Vous êtes sur le point de supprimer définitivement le compte de
				<strong>{nomAffiche(deleteConfirm)}</strong> ({deleteConfirm.email}).
				<br /><span style="color:var(--color-danger);font-size:.8rem"
					>Cette action est irréversible.</span
				>
			</p>
			<div class="modal-footer">
				<button class="btn btn-outline" on:click={() => (deleteConfirm = null)}>Annuler</button>
				<button class="btn btn-danger" on:click={confirmerDelete}>Supprimer définitivement</button>
			</div>
		</Modale>
	{/if}
{:else if onglet === 'demandes_profil'}
	{#if demandesProfilLoading}
		<p class="muted">Chargement...</p>
	{:else if demandesProfil.length === 0}
		<div class="empty-state">
			<h3>Aucune demande en attente</h3>
			<p>Toutes les demandes de modification de profil ont été traitées.</p>
		</div>
	{:else}
		<div class="card" style="overflow:hidden">
			<table class="table">
				<thead>
					<tr
						><th>Résident</th><th>Statut actuel</th><th>Bâtiment actuel</th><th
							>Changement souhaité</th
						><th>Motif</th><th>Date</th><th>Actions</th></tr
					>
				</thead>
				<tbody>
					{#each demandesProfil as d (d.id)}
						<tr>
							<td>
								<div style="font-weight:600">{d.utilisateur_nom}</div>
								<div style="font-size:.8rem;color:var(--color-text-muted)">
									{d.utilisateur_email}
								</div>
							</td>
							<td
								><span style="font-size:.82rem"
									>{statutLabelsAdmin[d.statut_actuel] ?? d.statut_actuel ?? '—'}</span
								></td
							>
							<td><span style="font-size:.82rem">{d.batiment_actuel ?? '—'}</span></td>
							<td>
								{#if d.statut_souhaite}
									<div style="font-size:.82rem">
										Type : <strong
											>{statutLabelsAdmin[d.statut_souhaite] ?? d.statut_souhaite}</strong
										>
									</div>
								{/if}
								{#if d.batiment_nom_souhaite}
									<div style="font-size:.82rem">
										Bât. : <strong>{d.batiment_nom_souhaite}</strong>
									</div>
								{/if}
							</td>
							<td
								style="font-size:.82rem;color:var(--color-text-muted);max-width:140px;white-space:pre-wrap"
								>{d.motif ?? '—'}</td
							>
							<td style="font-size:.82rem;color:var(--color-text-muted)">{fmt(d.cree_le)}</td>
							<td>
								<div class="action-row">
									<button
										class="btn btn-sm"
										style="background:#16a34a;color:#fff;border-color:#16a34a"
										on:click={() => approuverDemande(d.id)}>✓ Approuver</button
									>
									{#if refusDemandeOpen[d.id]}
										<div style="display:flex;gap:.35rem;align-items:center">
											<input
												type="text"
												bind:value={refusDemande[d.id]}
												placeholder="Motif refus"
												style="font-size:.78rem;padding:.25rem .5rem;width:120px;border:1px solid var(--color-border);border-radius:4px"
											/>
											<button class="btn btn-sm btn-danger" on:click={() => rejeterDemande(d.id)}
												>Confirmer</button
											>
											<button class="btn btn-sm" on:click={() => (refusDemandeOpen[d.id] = false)}
												>✕</button
											>
										</div>
									{:else}
										<button
											class="btn btn-sm btn-danger btn-outline"
											on:click={() => (refusDemandeOpen[d.id] = true)}>✗ Rejeter</button
										>
									{/if}
								</div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
{:else if onglet === 'maintenance'}
	<p class="muted" style="margin-bottom:1.25rem">
		Exécution des tâches planifiées sur les <strong>deux</strong> Raspberry&nbsp;Pi. Le nœud actif assure
		la maintenance applicative (purges, VACUUM) ; le nœud en veille fait son hygiène locale (cache de
		build, rotation des logs) et transmet son rapport au nœud actif.
	</p>

	<!--  Les deux cartes « Sauvegarde quotidienne — historique » et « Agrégation
      télémétrie — historique » vivaient ici. Supprimées avec #299 : depuis que la
      synthèse déplie l'historique de chaque tâche et porte son bouton de
      lancement, elles montraient les MÊMES lignes, tirées des MÊMES endpoints,
      sous un titre construit exprès pour ressembler à celui de la synthèse.
      Ce qu'elles portaient d'unique — le lieu de stockage des archives et le rôle
      de l'agrégation — est déplacé dans `TachesPlanifiees` (AIDE_TACHE), et la
      profondeur d'historique y passe de 4 à 10 : retirer les cartes sans
      compenser aurait réduit en silence ce qu'un administrateur peut voir. -->
	<TachesPlanifiees />
	<IntegriteReferentielle />
{:else if onglet === 'emails'}
	<OngletModelesEmail />
{:else if onglet === 'site'}
	<OngletSite bind:siteConfig {siteSaving} {siteManagerUsers} {saveSiteConfig} />
{:else if onglet === 'pages'}
	<p class="muted" style="margin-bottom:1.25rem">
		Personnalisez l'icône, le label de navigation, le titre et la description de chaque page.
		Cliquer sur une entrée pour la modifier ; les autres se referment automatiquement.
	</p>
	<div class="ref-list">
		{#each pagesConfig as pg, i (pg.id)}
			<div class="ref-item" class:expanded={expandedPages.has(pg.id)}>
				<div class="page-row">
					<div class="order-btns">
						{#if pg.href !== null}
							<button
								type="button"
								class="btn-order"
								disabled={indicesMenu[0] === i}
								on:click={() => movePage(i, -1)}
								aria-label="Monter {pg.nom} dans le menu">▲</button
							>
							<button
								type="button"
								class="btn-order"
								disabled={indicesMenu[indicesMenu.length - 1] === i}
								on:click={() => movePage(i, 1)}
								aria-label="Descendre {pg.nom} dans le menu">▼</button
							>
						{:else}
							<span
								class="hors-menu"
								title="Cette page n'a pas d'entrée de menu : son ordre n'a pas de sens.">—</span
							>
						{/if}
					</div>
					<button class="page-row-btn" on:click={() => togglePage(pg.id)} type="button">
						<span class="page-row-icon"><Icon name={pg.icone || 'help-circle'} size={16} /></span>
						<span class="page-nom">{pg.nom}</span>
						<span class="ref-desc muted">{stripHtmlPreview(pg.descriptif)}</span>
						<span class="chevron" class:open={expandedPages.has(pg.id)}>›</span>
					</button>
				</div>
				{#if expandedPages.has(pg.id)}
					<div class="ref-body">
						<div class="pages-form-grid">
							<div class="pages-form-section">
								<div class="pages-form-section-title">Navigation (barre de menu)</div>
								<label class="field">
									Icône Lucide
									<div style="display:flex;align-items:center;gap:.5rem">
										<input
											style="flex:1"
											type="text"
											bind:value={pg.icone}
											placeholder="ex. : layout-dashboard"
										/>
										<span
											style="color:var(--color-text-muted);flex-shrink:0;display:flex;align-items:center"
											><Icon name={pg.icone || 'help-circle'} size={20} /></span
										>
									</div>
									<span class="field-hint"
										>Cette icône s'affiche dans le menu <strong>et</strong> aussi avant le titre H1
										en haut de la page (c'est la même icône, modifiable ici).
										<a href="https://lucide.dev/icons/" target="_blank" rel="noopener noreferrer"
											>Parcourir lucide.dev →</a
										></span
									>
								</label>
								<label class="field">
									Label menu
									<input type="text" bind:value={pg.navLabel} />
									<span class="field-hint">Texte affiché dans la barre de navigation.</span>
								</label>
							</div>
							<div class="pages-form-section">
								<div class="pages-form-section-title">Page</div>
								<label class="field">
									Titre de la page
									<input type="text" bind:value={pg.titre} />
									<span class="field-hint"
										>Titre de Page avec reprise de l'icône (de navigation du menu associé).</span
									>
								</label>
								<label class="field">
									Description
									<RichEditor bind:value={pg.descriptif} minHeight="80px" />
									<span class="field-hint"
										>Sous-titre affiché sous le titre de page. Mise en forme riche supportée (gras,
										italique, listes, liens).</span
									>
								</label>
							</div>
							{#if pg.onglets && pg.onglets.length > 0}
								<div class="pages-form-section" style="grid-column:1/-1">
									<div class="pages-form-section-title">Onglets</div>
									<div class="onglets-cards">
										{#each pg.onglets as o (o.id)}
											<div class="onglet-card">
												<label class="field">
													Label « {o.id} »
													<input type="text" bind:value={o.label} />
												</label>
												<label class="field">
													Descriptif
													<RichEditor bind:value={o.descriptif} minHeight="56px" />
												</label>
											</div>
										{/each}
									</div>
									<span class="field-hint"
										>Labels et descriptifs de chaque onglet. Le descriptif apparaît sous les onglets
										quand l'onglet est actif.</span
									>
								</div>
							{/if}
						</div>
						<div class="form-actions">
							<button class="btn btn-primary btn-sm" on:click={() => savePageConfig(pg)}
								>Enregistrer</button
							>
						</div>
					</div>
				{/if}
			</div>
		{/each}
	</div>
{:else if onglet === 'legal'}
	<section class="card config-section">
		<h2 class="config-section-title"><Icon name="file-text" size={17} />Mentions légales</h2>
		<p class="muted" style="margin-bottom:1rem">
			Contenu affiché sur <code>/mentions-legales</code>.
		</p>
		<LegalEditor bind:value={siteConfig.mentions_legales} minHeight="380px" />
	</section>
	<hr style="border:none;border-top:1px solid var(--color-border);margin:1.5rem 0" />
	<section class="card config-section">
		<h2 class="config-section-title">
			<Icon name="shield" size={17} />Politique de confidentialité
		</h2>
		<p class="muted" style="margin-bottom:1rem">
			Contenu affiché sur <code>/politique-de-confidentialite</code>.
		</p>
		<LegalEditor bind:value={siteConfig.politique_confidentialite} minHeight="380px" />
	</section>
	<div class="form-actions">
		<button class="btn btn-primary" on:click={saveSiteConfig} disabled={siteSaving}>
			{siteSaving ? 'Enregistrement…' : 'Enregistrer'}
		</button>
	</div>
{:else if onglet === 'whatsapp'}
	<OngletWhatsApp
		cfgPublique={waCfgPublique}
		apiKeySet={waApiKeySet}
		bind:footer={siteConfig.whatsapp_footer}
		footerSaving={siteSaving}
		onSaveFooter={saveSiteConfig}
	/>
{:else if onglet === 'smtp'}
	<OngletSmtp
		bind:emailFooter={siteConfig.email_footer}
		bind:referenceCopro={siteConfig.reference_copro}
		valeurs={smtpValeurs}
	/>
{:else if onglet === 'telemetry'}
	<OngletTelemetrie />
{:else if onglet === 'csp'}
	<OngletCsp />
{:else if onglet === 'copropriete'}
	<OngletCopropriete />
{:else if onglet === 'perimetres'}
	<OngletPerimetres />
{:else if onglet === 'audit_lots'}
	<OngletAuditLots />
{:else if onglet === 'import_lots'}
	<OngletImportLots />
{:else if onglet === 'import_tc'}
	<OngletImportAcces modele={IMPORT_TELECOMMANDES} />
{:else if onglet === 'import_vigik'}
	<OngletImportAcces modele={IMPORT_VIGIK} />
{/if}
{#if cvModal}
	<Modale
		edition
		titre={`Valider le compte de ${nomAffiche(cvModal.user)}`}
		classeBoite="modal-box card"
		styleBoite="max-width:480px"
		on:fermer={() => (cvModal = null)}
	>
		<p style="font-size:.85rem;color:var(--color-text-muted);margin-bottom:1rem">
			{cvModal.user.statut ? (statutLabels[cvModal.user.statut] ?? cvModal.user.statut) : ''}
			{cvModal.lotsPrevus > 0 ? ` — ${cvModal.lotsPrevus} lot(s) détecté(s) dans l'import` : ''}
		</p>
		<label
			style="display:flex;align-items:flex-start;gap:.6rem;cursor:pointer;border:1.5px solid var(--color-border);border-radius:var(--radius);padding:.75rem;margin-bottom:.75rem"
			class:nouvel-arrivant-checked={cvNewArrivant}
		>
			<input type="checkbox" bind:checked={cvNewArrivant} style="margin-top:.2rem;flex-shrink:0" />
			<div>
				<strong style="font-size:.9rem">&#x1F3E0; Nouvel Arrivant</strong>
				<p style="font-size:.78rem;color:var(--color-text-muted);margin:.25rem 0 0">
					À cocher uniquement pour un <strong>nouveau résident</strong> qui emménage dans la
					copropriété. Déclenche automatiquement : message de bienvenue, envoi des consignes de
					copropriété, demande d'étiquette de boîte aux lettres auprès du syndic, et demande d'ajout
					sur l'interphone auprès du Conseil Syndical.
					<em>Ne pas cocher pour un résident existant qui crée simplement son compte.</em>
				</p>
			</div>
		</label>
		{#if cvNewArrivant}
			<div class="form-grid" style="margin-bottom:.75rem">
				<label class="field"
					>Bâtiment / logement
					<input bind:value={cvBatiment} placeholder="Ex: Bât. A, Apt. 12…" />
				</label>
				<label class="field"
					>Ancien résident
					<input bind:value={cvAncienResident} placeholder="Nom de l'ancien occupant…" />
				</label>
			</div>
		{/if}
		<div class="modal-footer">
			<button class="btn btn-outline" on:click={() => (cvModal = null)}>Annuler</button>
			<button class="btn btn-primary" disabled={cvSubmitting} on:click={confirmerCompteValidation}>
				{cvSubmitting ? 'En cours…' : 'Valider le compte'}
			</button>
		</div>
	</Modale>
{/if}

<style>
	/* `.sticky-head`, `.config-section`, `.config-section-title` et `.muted` sont
   passées dans `app.css` le 11/08/2026 : scopées ici, elles ne suivaient pas les
   composants extraits de cette page. (`.backup-header` y était aussi, et en est
   repartie avec les deux cartes qui l'utilisaient — #299.) */
	.tabs-group {
		margin-bottom: 0;
	}
	.tabs-group-label {
		font-size: 0.72rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--color-text-muted);
		padding: 0 0.25rem 0.3rem;
	}
	/*  `.tabs` et `.tab-btn` sont dans `app.css` : partagées avec
    `LiensEcransAdmin.svelte`, elles ne peuvent pas vivre dans un style scopé. */
	/*  `.badge-count` est parti avec le balisage, dans `Onglet.svelte` : une règle
    laissée ici ne s'appliquerait plus (Svelte scope au fichier) et tromperait le
    prochain lecteur — c'est la régression du 14/08, deux fois répétée. */
	.action-row {
		display: flex;
		gap: 0.4rem;
		flex-wrap: wrap;
		align-items: center;
	}
	.btn-sm {
		padding: 0.3rem 0.7rem;
		font-size: 0.8rem;
	}
	.refus-inline {
		display: flex;
		gap: 0.4rem;
		align-items: center;
		flex-wrap: wrap;
	}
	.input-sm {
		padding: 0.3rem 0.5rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		font-size: 0.85rem;
		min-width: 160px;
	}
	code {
		background: var(--color-bg);
		padding: 0.1rem 0.35rem;
		border-radius: 0.25rem;
		font-size: 0.85em;
	}
	.role-select {
		padding: 0.25rem 0.4rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		font-size: 0.82rem;
		background: var(--color-surface);
		color: var(--color-text);
		cursor: pointer;
	}
	.users-toolbar {
		display: flex;
		align-items: center;
		gap: 1rem;
		margin-bottom: 1rem;
		flex-wrap: wrap;
	}
	.user-search {
		flex: 1;
		min-width: 200px;
		max-width: 340px;
		padding: 0.4rem 0.7rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		font-size: 0.875rem;
	}
	.row-cs td {
		background: #eff6ff;
	}
	.row-inactive td {
		opacity: 0.6;
	}
	/*  La charte porte fond, bordure, rayon, curseur et couleur ;
    seuls la taille et le remplissage sont propres a cet ecran (#607, 28/08/2026). */
	.btn-outline {
		font-size: 0.8rem;
		padding: 0.3rem 0.7rem;
	}
	.btn-outline:hover {
		border-color: var(--color-primary);
		color: var(--color-primary);
	}
	/*  🔴 `.badge-orange` et `.badge-purple` retirees le 28/08/2026 (#607) :
    la charte les porte, et cet ecran en donnait une TROISIEME teinte —
    `delegations` en avait une deuxieme. Meme notion, trois couleurs. */
	.form-grid {
		grid-template-columns: 1fr 1fr;
	}
	.ref-list {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}
	.page-row {
		width: 100%;
		display: flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.4rem 0.5rem 0.4rem 0.75rem;
	}
	.page-row:hover {
		background: var(--color-bg);
	}
	.page-row-btn {
		flex: 1;
		display: flex;
		align-items: center;
		gap: 0.5rem;
		background: none;
		border: none;
		cursor: pointer;
		text-align: left;
		font-size: 0.875rem;
		padding: 0.25rem 0.25rem;
		min-width: 0;
	}
	.page-row-icon {
		flex: 0 0 18px;
		display: flex;
		align-items: center;
		color: var(--color-text-muted);
	}
	.page-nom {
		flex: 0 0 20%;
		min-width: 80px;
		max-width: 180px;
		font-weight: 600;
		font-size: 0.875rem;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.pages-form-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1.25rem;
	}
	.pages-form-section {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.pages-form-section-title {
		font-size: 0.7rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.07em;
		color: var(--color-text-muted);
		padding-bottom: 0.3rem;
		border-bottom: 1px solid var(--color-border);
		margin-bottom: 0.1rem;
	}
	.ref-desc {
		font-size: 0.78rem;
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		min-width: 0;
	}
	.order-btns {
		display: flex;
		flex-direction: column;
		gap: 1px;
		flex-shrink: 0;
	}
	.btn-order {
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 3px;
		cursor: pointer;
		font-size: 0.6rem;
		padding: 1px 4px;
		line-height: 1.5;
		color: var(--color-text-muted);
	}
	.btn-order:hover:not(:disabled) {
		border-color: var(--color-primary);
		color: var(--color-primary);
		background: var(--color-bg);
	}
	.btn-order:disabled {
		opacity: 0.3;
		cursor: default;
	}
	.hors-menu {
		color: var(--color-text-muted);
		opacity: 0.4;
		font-size: 0.7rem;
		line-height: 1.5;
		cursor: help;
	}
	.ref-item {
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		overflow: hidden;
		background: var(--color-surface);
	}
	.ref-item.expanded {
		border-color: var(--color-primary);
	}
	.ref-row {
		width: 100%;
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.65rem 1rem;
		background: none;
		border: none;
		cursor: pointer;
		text-align: left;
		font-size: 0.875rem;
	}
	.ref-row:hover {
		background: var(--color-bg);
	}
	.ref-name {
		font-weight: 600;
		flex: 1;
	}
	.ref-meta {
		font-size: 0.8rem;
		white-space: nowrap;
	}
	.ref-body {
		padding: 0.75rem 1rem;
		border-top: 1px solid var(--color-border);
		background: var(--color-bg);
	}
	.ref-chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		margin-bottom: 0.75rem;
	}
	.ref-chip {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 999px;
		padding: 0.2rem 0.65rem;
		font-size: 0.8rem;
	}
	.chip-del {
		background: none;
		border: none;
		cursor: pointer;
		color: var(--color-text-muted);
		padding: 0 0.1rem;
		font-size: 1rem;
		line-height: 1;
		margin-left: 0.1rem;
	}
	.chip-del:hover {
		color: var(--color-danger);
	}
	.ref-add-row {
		display: flex;
		gap: 0.5rem;
		align-items: center;
	}
	.user-tags {
		display: flex;
		flex-wrap: wrap;
		gap: 0.2rem;
		margin-top: 0.15rem;
	}
	.utag {
		font-size: 0.6rem;
		font-weight: 600;
		padding: 0.05rem 0.35rem;
		border-radius: 4px;
		line-height: 1.3;
	}
	.utag-ok {
		background: #d4edda;
		color: #155724;
	}
	.utag-ko {
		background: #f8d7da;
		color: #721c24;
	}
	.onglets-cards {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(240px, 100%), 1fr));
		gap: 0.75rem;
	}
	.onglet-card {
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: 8px;
		padding: 0.75rem;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
</style>
