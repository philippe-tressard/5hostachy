<script lang="ts">
	import { nomAffiche } from '$lib/noms';
	import { onMount } from 'svelte';
	import { get } from 'svelte/store';
	import OngletMaintenance from '$lib/components/OngletMaintenance.svelte';
	import { admin as adminApi, auth as authApi, config as configApi } from '$lib/api';
	import { badgeRole, badgeStatut, libelleRole, LIBELLES_STATUT_ABREGE } from '$lib/roles';
	import { aRole } from '$lib/stores/auth';
	import OngletUtilisateurs from '$lib/components/OngletUtilisateurs.svelte';
	import { essayer, messagePartiel } from '$lib/chargement';
	import ChargementPartiel from '$lib/components/ChargementPartiel.svelte';
	//  Les onglets qui ENREGISTRENT ce que `/config/admin` et `/config/legal` ont lu.
	//  Si la lecture a échoué, leur formulaire serait vide — et enregistré, il
	//  effacerait la configuration (#1459) : ils montrent l'échec à la place.
	const ONGLETS_DU_PARAMETRAGE = [
		'site',
		'pages',
		'legal',
		'whatsapp',
		'smtp',
		'ia',
		'copropriete',
	];
	import EtatListe from '$lib/components/EtatListe.svelte';
	import { toast } from '$lib/components/Toast.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import { defautsDePage } from '$lib/pages';
	import EntetePage from '$lib/components/EntetePage.svelte';
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
	import ValidationCompte from '$lib/components/ValidationCompte.svelte';
	import { validerCompte } from '$lib/comptes';
	import { messageErreur } from '$lib/erreurs';
	import OngletWhatsApp from '$lib/components/OngletWhatsApp.svelte';
	import OngletSmtp from '$lib/components/OngletSmtp.svelte';
	import OngletIA from '$lib/components/OngletIA.svelte';
	import OngletDescriptifPages from '$lib/components/OngletDescriptifPages.svelte';
	import OngletTelemetrie from '$lib/components/OngletTelemetrie.svelte';
	import OngletCsp from '$lib/components/OngletCsp.svelte';
	import OngletModelesEmail from '$lib/components/OngletModelesEmail.svelte';
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
	let erreurBatiments = '';
	async function loadBatiments() {
		[batimentsList, erreurBatiments] = await essayer(authApi.batiments(), []);
		batimentsMap = Object.fromEntries(batimentsList.map((b) => [b.id, `Bât. ${b.numero}`]));
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
			if (!(await accepterCommandeAcces(id))) return;
			toast('success', 'Commande acceptée.');
			commandes = commandes.filter((c) => c.id !== id);
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		}
	}

	async function refuserCommande(id: number, motif: string) {
		try {
			await refuserCommandeAcces(id, motif);
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

	//  🔴 Le compte rendu de la validation vit dans `$lib/comptes` depuis le
	//  12/09/2026 : l'espace CS en portait une version plus PAUVRE, qui taisait
	//  les lots résolus et l'avertissement sur un copropriétaire aidé introuvable.
	//  `standards/02` §4 bis — entre deux implémentations, la plus disante.
	async function confirmerCompteValidation() {
		if (!cvModal) return;
		const u = cvModal.user;
		cvSubmitting = true;
		try {
			const annonces = await validerCompte(u, {
				nouvelArrivant: cvNewArrivant,
				batiment: cvBatiment,
				ancienResident: cvAncienResident,
			});
			comptes = comptes.filter((c) => (c.user?.id ?? c.id) !== u.id);
			for (const a of annonces) toast(a.ton, a.texte);
			cvModal = null;
		} catch (e: any) {
			toast('error', messageErreur(e));
		} finally {
			cvSubmitting = false;
		}
	}

	//  🔴 L'échec se DIT (#1459) : ce chargement était un `try/finally` sans
	//  `catch` — un refus laissait la liste vide, sans un mot, et `lint:catch-vide`
	//  ne pouvait pas le voir faute de `catch`.
	let erreurUtilisateurs = '';
	//  🔴 Chargée dès que l'onglet actif en a besoin — et non au CLIC sur
	//  l'onglet, seul déclencheur jusqu'au 30/09/2026 : arrivé par un lien ou un
	//  rechargement sur `?onglet=utilisateurs`, l'écran restait sur « Chargement… »
	//  pour toujours, et l'onglet Site n'avait aucun gestionnaire à proposer.
	let listeDemandee = false;
	$: if ((onglet === 'utilisateurs' || onglet === 'site') && !listeDemandee) {
		listeDemandee = true;
		loadUtilisateurs();
	}
	async function loadUtilisateurs() {
		utilisateursLoading = true;
		[utilisateurs, erreurUtilisateurs] = await essayer(adminApi.utilisateurs(), []);
		utilisateursLoading = false;
	}

	//  🔴 La table des libellés vit dans `$lib/roles` depuis le 06/09/2026 (#801).
	//  Elle était écrite SIX fois — trois ici côté front, trois côté serveur — et
	//  les six avaient dérivé : « Copropriétaire Résident » dans deux écrans,
	//  « Copropriétaire résident » dans le troisième ; « Conseil syndical » ici,
	//  « Membre du Conseil Syndical » dans la notification que le serveur envoie.
	//  Chacune était cohérente avec elle-même : aucun contrôle ne pouvait le voir.

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
		// pour afficher cet écran. Les clés légales en sont exclues (perf) : route dédiée.
		//  🔴 Lu UNE fois (il l'était deux) et jamais en silence (#1459) : un échec
		//  laissait les textes légaux vides, et « Enregistrer » les effaçait.
		const [adminCfg, eAdmin] = await essayer(configApi.admin(), {} as Record<string, string>);
		const [legal, eLegal] = await essayer(configApi.legal(), {} as Record<string, string>);
		erreurParametrage = messagePartiel(eAdmin, eLegal);
		const cfg = { ...(get(configStore) as Record<string, string>), ...adminCfg };
		siteConfig = lireConfigSite(cfg, {
			mentions_legales: legal['mentions_legales'] ?? '',
			politique_confidentialite: legal['politique_confidentialite'] ?? '',
		});
		//  La configuration des pages est préparée par `OngletDescriptifPages`, qui
		//  la reçoit dans `valeurs` : la page n'a plus à connaître sa forme.
		// WhatsApp : la configuration part telle quelle vers l'onglet dédié.
		waCfgPublique = cfg;
		waApiKeySet = !!adminCfg['whatsapp_api_key'];
		smtpValeurs = adminCfg;
		loadBatiments();
		loadComptes();
		loadCommandes();
		loadDemandesProfil();
	});

	// ── Paramétrage site ──────────────────────────────────────────
	let siteConfig = { ...CONFIG_SITE_DEFAUT };
	let siteSaving = false;
	$: siteManagerUsers = utilisateurs.filter((u) => !!u.email && aRole(u, 'admin'));
	function openSiteTab() {
		onglet = 'site';
	}
	let erreurParametrage = '';
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
	import { accepterCommandeAcces, refuserCommandeAcces } from '$lib/commandes-acces';
	$: _pc = getPageConfig($configStore, 'admin', defautsDePage('admin'));
	$: _siteNom = $siteNomStore;
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<EntetePage
	titre={_pc.titre}
	descriptif={_pc.descriptif}
	icone={_pc.icone || 'sliders-horizontal'}
/>
<ChargementPartiel
	erreur={messagePartiel(erreurParametrage, erreurBatiments)}
	consequence={erreurParametrage
		? 'Les onglets de paramétrage restent fermés : enregistrés vides, ils effaceraient la configuration.'
		: 'Les numéros de bâtiment peuvent manquer dans les listes.'}
/>

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
		<Onglet actif={onglet === 'utilisateurs'} on:click={() => (onglet = 'utilisateurs')}>
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
									<div
										style="font-size:var(--fs-xs);color:var(--color-text-muted);margin-top:.15rem"
									>
										&#x1F464; Prop. : {u.nom_proprietaire}
									</div>
								{/if}
								{#if (u.statut === 'aidant' || u.statut === 'mandataire') && u.nom_aide}
									<div
										style="font-size:var(--fs-xs);color:var(--color-text-muted);margin-top:.15rem"
									>
										&#x1F464; Aidé : {u.prenom_aide}
										{u.nom_aide}
									</div>
								{/if}
							</td>
							<td
								><span class="badge {badgeStatut(u.statut)}" style="font-size:var(--fs-xs)"
									>{LIBELLES_STATUT_ABREGE[u.statut] ?? u.statut}</span
								></td
							>
							<td>
								<div style="display:flex;gap:.25rem;flex-wrap:wrap">
									{#each u.roles?.length ? u.roles : [u.role] as r (r)}
										<span class="badge {badgeRole(r)}" style="font-size:var(--fs-xs)"
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
							<td style="color:var(--color-text-muted);font-size:var(--fs-sm)">{fmt(u.cree_le)}</td>
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
						<!--  🔴 Le formulaire s'ouvre SOUS la ligne du compte, pas dans une
						      fenêtre (#889, arbitrage du 11/09/2026). Dans un tableau, « à la
						      place du corps de la carte » se dit en une ligne de plus qui
						      s'étend sur toutes les colonnes : l'objet ne bouge pas, et le
						      formulaire reste attaché à lui.

						      C'est le MÊME composant que l'espace CS — les deux écrans en
						      portaient chacun une copie, qui avait déjà dérivé. -->
						{#if cvModal?.user?.id === u.id}
							<tr class="ligne-formulaire">
								<td colspan="7">
									<ValidationCompte
										utilisateur={u}
										precision={(cvModal?.lotsPrevus ?? 0) > 0
											? `${cvModal?.lotsPrevus} lot(s) détecté(s) dans l'import`
											: ''}
										enCours={cvSubmitting}
										bind:nouvelArrivant={cvNewArrivant}
										bind:batiment={cvBatiment}
										bind:ancienResident={cvAncienResident}
										onAnnuler={() => (cvModal = null)}
										onValider={confirmerCompteValidation}
									/>
								</td>
							</tr>
						{/if}
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
							<td style="color:var(--color-text-muted);font-size:var(--fs-sm)"
								>{fmt(cmd.cree_le)}</td
							>
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
	<OngletUtilisateurs
		bind:utilisateurs
		chargement={utilisateursLoading}
		erreur={erreurUtilisateurs}
		{batimentsList}
		{batimentsMap}
		recharger={loadUtilisateurs}
	/>
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
								<div style="font-size:var(--fs-sm);color:var(--color-text-muted)">
									{d.utilisateur_email}
								</div>
							</td>
							<td
								><span style="font-size:var(--fs-md)"
									>{LIBELLES_STATUT_ABREGE[d.statut_actuel] ?? d.statut_actuel ?? '—'}</span
								></td
							>
							<td><span style="font-size:var(--fs-md)">{d.batiment_actuel ?? '—'}</span></td>
							<td>
								{#if d.statut_souhaite}
									<div style="font-size:var(--fs-md)">
										Type : <strong
											>{LIBELLES_STATUT_ABREGE[d.statut_souhaite] ?? d.statut_souhaite}</strong
										>
									</div>
								{/if}
								{#if d.batiment_nom_souhaite}
									<div style="font-size:var(--fs-md)">
										Bât. : <strong>{d.batiment_nom_souhaite}</strong>
									</div>
								{/if}
							</td>
							<td
								style="font-size:var(--fs-md);color:var(--color-text-muted);max-width:140px;white-space:pre-wrap"
								>{d.motif ?? '—'}</td
							>
							<td style="font-size:var(--fs-md);color:var(--color-text-muted)">{fmt(d.cree_le)}</td>
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
{:else if erreurParametrage && ONGLETS_DU_PARAMETRAGE.includes(onglet)}
	<EtatListe
		erreur={erreurParametrage}
		titreErreur="Paramétrage illisible — rien n’a été modifié"
	/>
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

<style>
	/*  La ligne qui accueille le formulaire de validation, sous celle du compte.
	    Elle n'a ni bordure haute ni fond propre : les deux lignes doivent se lire
	    comme un seul objet, sinon le formulaire semble concerner le compte
	    suivant. */
	.ligne-formulaire > td {
		border-top: none;
		background: var(--color-bg-alt, #fafafa);
		padding: 1rem;
	}

	/* `.sticky-head`, `.config-section`, `.config-section-title` et `.muted` sont
   passées dans `app.css` le 11/08/2026 : scopées ici, elles ne suivaient pas les
   composants extraits de cette page. (`.backup-header` y était aussi, et en est
   repartie avec les deux cartes qui l'utilisaient — #299.) */
	.tabs-group {
		margin-bottom: 0;
	}
	.tabs-group-label {
		font-size: var(--fs-2xs);
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
	/*  🔴 `.badge-orange` et `.badge-purple` retirees le 28/08/2026 (#607) :
    la charte les porte, et cet ecran en donnait une TROISIEME teinte —
    `delegations` en avait une deuxieme. Meme notion, trois couleurs. */
	.ref-meta {
		font-size: var(--fs-sm);
		white-space: nowrap;
	}
</style>
