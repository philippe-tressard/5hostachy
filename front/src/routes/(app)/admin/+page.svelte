<script lang="ts">
	import { nomAffiche } from '$lib/noms';
	import { onMount } from 'svelte';
	import { get } from 'svelte/store';
	import OngletMaintenance from '$lib/components/OngletMaintenance.svelte';
	import { api, admin as adminApi, auth as authApi, config as configApi } from '$lib/api';
	import { libelleRole, badgeRole, badgeStatut, LIBELLES_STATUT_ABREGE } from '$lib/roles';
	import { essayer } from '$lib/chargement';
	import EtatListe from '$lib/components/EtatListe.svelte';
	import { toast } from '$lib/components/Toast.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import { defautsDePage } from '$lib/pages';
	import EntetePage from '$lib/components/EntetePage.svelte';
	import Modale from '$lib/components/Modale.svelte';
	import FormulaireCreation from '$lib/components/FormulaireCreation.svelte';
	import FormulaireUtilisateur from '$lib/components/FormulaireUtilisateur.svelte';
	import { CONFIG_SITE_DEFAUT, ecrireConfigSite, lireConfigSite } from '$lib/configSite';
	import LegalEditor from '$lib/components/LegalEditor.svelte';
	import OngletCopropriete from '$lib/components/OngletCopropriete.svelte';
	import OngletSite from '$lib/components/OngletSite.svelte';
	import OngletPerimetres from '$lib/components/OngletPerimetres.svelte';
	import OngletAuditLots from '$lib/components/OngletAuditLots.svelte';
	import OngletImportLots from '$lib/components/OngletImportLots.svelte';
	import OngletImportAcces from '$lib/components/OngletImportAcces.svelte';
	import { IMPORT_TELECOMMANDES, IMPORT_VIGIK } from '$lib/imports-acces';
	import Onglet from '$lib/components/Onglet.svelte';
	import AccepterRefuser from '$lib/components/AccepterRefuser.svelte';
	import OngletWhatsApp from '$lib/components/OngletWhatsApp.svelte';
	import OngletSmtp from '$lib/components/OngletSmtp.svelte';
	import OngletIA from '$lib/components/OngletIA.svelte';
	import OngletDescriptifPages from '$lib/components/OngletDescriptifPages.svelte';
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
		'ia',
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
			const list = await authApi.batiments();
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
	/** Non vide = on n'a PAS pu regarder. Distinct de « la liste est vide ». */
	let erreurComptes = '';

	async function loadComptes() {
		comptesLoading = true;
		//  🔴 `essayer` rend `[valeur, erreur]` — jamais l'un sans l'autre (#816).
		//  Ce `try/finally` n'avait AUCUN `catch` : une session expirée ou un 500
		//  rejetait la promesse dans le vide, `comptes` restait à `[]`, et l'écran
		//  annonçait « Aucun compte en attente ». Pas même un toast.
		[comptes, erreurComptes] = await essayer(adminApi.comptesEnAttenteEnrichis(), []);
		comptesLoading = false;
	}

	async function refuserCompte(id: number, motif: string) {
		try {
			await adminApi.traiterCompte(id, { action: 'refuser', motif });
			toast('info', 'Compte refusé.');
			comptes = comptes.filter((c) => (c.user?.id ?? c.id) !== id);
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		}
	}

	async function relancerAutoMatch(userId: number, userNom: string) {
		try {
			const res = await adminApi.autoMatchUtilisateur(userId);
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
	/** Non vide = on n'a PAS pu regarder. Distinct de « la liste est vide ». */
	let erreurCommandes = '';

	async function loadCommandes() {
		commandesLoading = true;
		[commandes, erreurCommandes] = await essayer(adminApi.commandesAccesEnAttente(), []);
		commandesLoading = false;
	}

	async function accepterCommande(id: number) {
		try {
			await adminApi.traiterCommandeAcces(id, { action: 'accepter' });
			toast('success', 'Commande acceptee.');
			commandes = commandes.filter((c) => c.id !== id);
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		}
	}

	async function refuserCommande(id: number, motif: string) {
		try {
			await adminApi.traiterCommandeAcces(id, {
				action: 'refuser',
				motif_refus: motif,
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
			const res = await adminApi.traiterCompte(u.id, { action: 'valider' });
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
				await adminApi.accueilArrivant(u.id, {
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
			await adminApi.accueilArrivant(u.id, {
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
			utilisateurs = await adminApi.utilisateurs();
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
			//  🔴 Les deux méthodes EXISTAIENT dans le client et n'étaient appelées
			//  nulle part (#801) : l'écran construisait l'URL dans un ternaire, ce
			//  qui la rendait invisible à toute recherche par route. C'est la forme
			//  la plus tenace du contournement — la chaîne recopiée ne ressemble
			//  même plus à une route.
			const updated = await (action === 'ajouter'
				? adminApi.ajouterRole(user.id, role)
				: adminApi.retirerRole(user.id, role));
			toast(
				'success',
				`Rôle ${libelleRole(role)} ${action === 'ajouter' ? 'ajouté à' : 'retiré de'} ${nomAffiche(user)}.`,
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
			const updated = await adminApi.modifierUtilisateur(editUser.id, editForm);
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
			await adminApi.supprimerUtilisateur(target.id);
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
			const updated = await adminApi.banCommunaute(u.id, { interdit });
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

	//  🔴 La table des libellés vit dans `$lib/roles` depuis le 06/09/2026 (#801).
	//  Elle était écrite SIX fois — trois ici côté front, trois côté serveur — et
	//  les six avaient dérivé : « Copropriétaire Résident » dans deux écrans,
	//  « Copropriétaire résident » dans le troisième ; « Conseil syndical » ici,
	//  « Membre du Conseil Syndical » dans la notification que le serveur envoie.
	//  Chacune était cohérente avec elle-même : aucun contrôle ne pouvait le voir.

	function userRoles(u: any): string[] {
		return u.roles?.length ? u.roles : [u.role];
	}

	// Rôles actifs : affiche les rôles réels (P·R·E·CS·A) depuis u.roles
	function displayRoles(u: any): { label: string; cls: string }[] {
		const roles: string[] = u.roles?.length ? u.roles : [u.role];
		return roles.map((r: string) => ({
			label: libelleRole(r),
			cls: badgeRole(r),
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
	/** Non vide = on n'a PAS pu regarder. Distinct de « la liste est vide ». */
	let erreurDemandesProfil = '';

	async function loadDemandesProfil() {
		demandesProfilLoading = true;
		//  ⚠️ Le `catch { /* ignore */ }` d'origine est la forme la plus explicite
		//  du défaut : l'échec était écrit, lu, et jeté.
		[demandesProfil, erreurDemandesProfil] = await essayer(adminApi.demandesProfil(), []);
		demandesProfilLoading = false;
	}

	async function approuverDemande(id: number) {
		try {
			await adminApi.traiterDemandeProfil(id, { action: 'approuver' });
			toast('success', 'Demande approuvée.');
			demandesProfil = demandesProfil.filter((d) => d.id !== id);
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		}
	}

	async function rejeterDemande(id: number, motif: string) {
		try {
			await adminApi.traiterDemandeProfil(id, {
				action: 'rejeter',
				motif_refus: motif || null,
			});
			toast('info', 'Demande rejetée.');
			demandesProfil = demandesProfil.filter((d) => d.id !== id);
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
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
		//  La configuration des pages est préparée par `OngletDescriptifPages`, qui
		//  la reçoit dans `valeurs` : la page n'a plus à connaître sa forme.
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
		<Onglet actif={onglet === 'ia'} on:click={() => (onglet = 'ia')}>Assistant IA</Onglet>
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
	{#if comptesLoading || erreurComptes || comptes.length === 0}
		<EtatListe
			chargement={comptesLoading}
			erreur={erreurComptes}
			vide={comptes.length === 0}
			titreErreur="Impossible d’afficher les comptes en attente"
			titreVide="Aucun compte en attente"
			messageVide="Tous les comptes ont été traités."
		/>
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
								><span class="badge {badgeStatut(u.statut)}" style="font-size:.75rem"
									>{LIBELLES_STATUT_ABREGE[u.statut] ?? u.statut}</span
								></td
							>
							<td>
								<div style="display:flex;gap:.25rem;flex-wrap:wrap">
									{#each u.roles?.length ? u.roles : [u.role] as r (r)}
										<span class="badge {badgeRole(r)}" style="font-size:.75rem"
											>{libelleRole(r)}</span
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
									<AccepterRefuser
										libelleAccepter="Valider →"
										onAccepter={() => openCompteValidation(item)}
										onRefuser={(motif) => refuserCompte(u.id, motif)}
									/>
								</div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
{:else if onglet === 'acces'}
	{#if commandesLoading || erreurCommandes || commandes.length === 0}
		<EtatListe
			chargement={commandesLoading}
			erreur={erreurCommandes}
			vide={commandes.length === 0}
			titreErreur="Impossible d’afficher les commandes d’accès"
			titreVide="Aucune commande en attente"
			messageVide="Toutes les demandes d’accès ont été traitées."
		/>
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
									<AccepterRefuser
										onAccepter={() => accepterCommande(cmd.id)}
										onRefuser={(motif) => refuserCommande(cmd.id, motif)}
									/>
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
				{#each Object.entries(LIBELLES_STATUT_ABREGE) as [val, label] (val)}
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
									<span class="badge {badgeStatut(u.statut)}" style="font-size:.75rem">
										{LIBELLES_STATUT_ABREGE[u.statut] ?? u.statut ?? '—'}
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
				<strong>{libelleRole(roleEnCours.role)}</strong>
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
		<!--  La CORRECTION d'un utilisateur — la même boîte que partout depuis le
		      06/09/2026 (`ux-patterns` §14 bis). `cle` fait remonter le formulaire
		      quand on passe d'un utilisateur à un autre : la liste est longue, et
		      sans elle le second clic serait muet. -->
		<FormulaireCreation titre="Modifier l'utilisateur" cle={editUser}>
			<FormulaireUtilisateur
				bind:editForm
				statutLabels={LIBELLES_STATUT_ABREGE}
				{batimentsList}
				onAnnuler={() => (editUser = null)}
				onEnregistrer={saveEdit}
			/>
		</FormulaireCreation>
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
	{#if demandesProfilLoading || erreurDemandesProfil || demandesProfil.length === 0}
		<EtatListe
			chargement={demandesProfilLoading}
			erreur={erreurDemandesProfil}
			vide={demandesProfil.length === 0}
			titreErreur="Impossible d’afficher les demandes de profil"
			titreVide="Aucune demande en attente"
			messageVide="Toutes les demandes de modification de profil ont été traitées."
		/>
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
									>{LIBELLES_STATUT_ABREGE[d.statut_actuel] ?? d.statut_actuel ?? '—'}</span
								></td
							>
							<td><span style="font-size:.82rem">{d.batiment_actuel ?? '—'}</span></td>
							<td>
								{#if d.statut_souhaite}
									<div style="font-size:.82rem">
										Type : <strong
											>{LIBELLES_STATUT_ABREGE[d.statut_souhaite] ?? d.statut_souhaite}</strong
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
									<AccepterRefuser
										libelleAccepter="✓ Approuver"
										libelleRefuser="✗ Rejeter"
										onAccepter={() => approuverDemande(d.id)}
										onRefuser={(motif) => rejeterDemande(d.id, motif)}
									/>
								</div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
{:else if onglet === 'maintenance'}
	<OngletMaintenance />
{:else if onglet === 'emails'}
	<OngletModelesEmail />
{:else if onglet === 'site'}
	<OngletSite bind:siteConfig {siteSaving} {siteManagerUsers} {saveSiteConfig} />
{:else if onglet === 'pages'}
	<OngletDescriptifPages valeurs={smtpValeurs} />
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
	<OngletSmtp bind:emailFooter={siteConfig.email_footer} valeurs={smtpValeurs} />
{:else if onglet === 'ia'}
	<!--  Les mêmes valeurs que le SMTP : c'est `adminCfg`, la configuration
	      complète lue une fois au chargement. Un second appel pour les mêmes
	      clés donnerait deux vérités à quelques millisecondes d'écart. -->
	<OngletIA valeurs={smtpValeurs} />
{:else if onglet === 'telemetry'}
	<OngletTelemetrie />
{:else if onglet === 'csp'}
	<OngletCsp />
{:else if onglet === 'copropriete'}
	<OngletCopropriete bind:referenceCopro={siteConfig.reference_copro} />
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
			{cvModal.user.statut
				? (LIBELLES_STATUT_ABREGE[cvModal.user.statut] ?? cvModal.user.statut)
				: ''}
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
	/*  🔴 `.refus-inline` est partie le 07/09/2026 avec le balisage qu'elle
	    habillait : `AccepterRefuser.svelte` porte le geste « accepter · refuser
	    avec motif », qui était écrit TROIS fois ici. `.input-sm` est montée dans
	    la charte — la page l'emploie encore trois fois, le composant une, et
	    deux écritures d'une même règle divergent au premier ajustement. */
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
	.ref-meta {
		font-size: 0.8rem;
		white-space: nowrap;
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
</style>
