<script lang="ts">
	import { onMount } from 'svelte';
	import { get } from 'svelte/store';
	import OngletMaintenance from '$lib/components/OngletMaintenance.svelte';
	import { admin as adminApi, auth as authApi, config as configApi } from '$lib/api';
	import { aRole } from '$lib/stores/auth';
	import OngletUtilisateurs from '$lib/components/OngletUtilisateurs.svelte';
	import { essayer, messagePartiel, TITRE_PARAMETRAGE_ILLISIBLE } from '$lib/chargement';
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
	import { defautsDePage, PAGES } from '$lib/pages';
	import { page } from '$app/stores';
	import BarreOnglets from '$lib/components/BarreOnglets.svelte';
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
	import OngletWhatsApp from '$lib/components/OngletWhatsApp.svelte';
	import OngletSmtp from '$lib/components/OngletSmtp.svelte';
	import OngletIA from '$lib/components/OngletIA.svelte';
	import OngletDescriptifPages from '$lib/components/OngletDescriptifPages.svelte';
	import OngletTelemetrie from '$lib/components/OngletTelemetrie.svelte';
	import OngletATraiter from '$lib/components/OngletATraiter.svelte';
	import OngletModelesEmail from '$lib/components/OngletModelesEmail.svelte';
	import { trackTabView } from '$lib/telemetry';

	//  Onglets
	// 'sauvegardes' retiré le 02/08/2026 : ce bloc n'était accessible par AUCUN
	// bouton et dupliquait, dans une version divergente (accents perdus), celui de
	// « Paramétrage site ». Les deux vivent désormais dans le sous-onglet Maintenance.
	//  🔴 La liste des onglets vit dans `$lib/pages-roles.ts` (page `admin`) et
	//  NULLE PART AILLEURS, depuis le 01/10/2026 : déclarés comme ceux des autres
	//  pages, ils se renomment et se décrivent dans « Descriptif pages », et
	//  `BarreOnglets` rend leurs deux rangées. Cette page en tenait sa propre liste,
	//  `const ONGLETS = [...] as const` — une seconde liste aurait divergé au
	//  premier onglet ajouté, et l'adressage direct aurait cessé de fonctionner en
	//  silence.
	//
	//  L'onglet actif SE LIT dans l'adresse (`?onglet=`, « sauf admin ») : chaque
	//  onglet est un lien, qui se copie et que le bouton Précédent rejoue. Une clé
	//  inconnue ouvre le premier onglet.
	const ONGLETS: string[] = (PAGES.find((p) => p.id === 'admin')?.onglets ?? []).map((o) => o.id);
	$: demande = $page.url.searchParams.get('onglet');
	$: onglet = demande && ONGLETS.includes(demande) ? demande : ONGLETS[0];
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

	//  Montage
	onMount(async () => {
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

<!--  Les deux rangées — « Gestion utilisateurs », « Configuration » — sont
      rendues par `BarreOnglets` depuis la table (`groupe`), avec le descriptif
      de l'onglet actif dessous, comme sur toutes les pages à onglets. -->
<BarreOnglets
	pageId="admin"
	actif={onglet}
	comptes={{ a_traiter: comptes.length + commandes.length + demandesProfil.length }}
/>

{#if onglet === 'a_traiter'}
	<OngletATraiter
		bind:comptes
		{comptesLoading}
		{erreurComptes}
		bind:commandes
		{commandesLoading}
		{erreurCommandes}
		bind:demandesProfil
		{demandesProfilLoading}
		{erreurDemandesProfil}
		{batimentsMap}
	/>
{:else if onglet === 'utilisateurs'}
	<OngletUtilisateurs
		bind:utilisateurs
		chargement={utilisateursLoading}
		erreur={erreurUtilisateurs}
		{batimentsList}
		{batimentsMap}
		recharger={loadUtilisateurs}
	/>
{:else if onglet === 'maintenance'}
	<OngletMaintenance />
{:else if onglet === 'emails'}
	<OngletModelesEmail />
{:else if erreurParametrage && ONGLETS_DU_PARAMETRAGE.includes(onglet)}
	<EtatListe erreur={erreurParametrage} titreErreur={TITRE_PARAMETRAGE_ILLISIBLE} />
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
	/* `.sticky-head`, `.config-section`, `.config-section-title` et `.muted` sont
   passées dans `app.css` le 11/08/2026 : scopées ici, elles ne suivaient pas les
   composants extraits de cette page. (`.backup-header` y était aussi, et en est
   repartie avec les deux cartes qui l'utilisaient — #299.) */
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
</style>
