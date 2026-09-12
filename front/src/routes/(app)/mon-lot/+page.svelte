<script lang="ts">
	import { nomAffiche } from '$lib/noms';
	import { etageLabel, lotTypeLabel } from '$lib/utils';
	import EntetePage from '$lib/components/EntetePage.svelte';
	import Modale from '$lib/components/Modale.svelte';
	import FormulaireCreation from '$lib/components/FormulaireCreation.svelte';
	import FormulaireBail from '$lib/components/FormulaireBail.svelte';
	import ModaleAccesBail from '$lib/components/ModaleAccesBail.svelte';
	import { onMount } from 'svelte';
	import { lots as lotsApi, bailleur as bailApi, ApiError, type ObjetRemis } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { currentUser, isAdmin, isCS } from '$lib/stores/auth';
	import { getPageConfig, configStore, siteNomStore, defautsDePage } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';
	import { fmtDateShort as fmt } from '$lib/date';
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import BarreOnglets from '$lib/components/BarreOnglets.svelte';
	import OngletAcces from '$lib/components/OngletAcces.svelte';
	import OngletGestionLocative from '$lib/components/OngletGestionLocative.svelte';
	import BoutonNouveau from '$lib/components/BoutonNouveau.svelte';
	import { messageErreur, tenter } from '$lib/erreurs';
	import { routeOnglet, routeSousOnglet } from '$lib/routes-onglets';

	$: _pc = getPageConfig($configStore, 'mon-lot', defautsDePage('mon-lot'));
	$: _siteNom = $siteNomStore;
	//  Deux lectures d'un même droit : le masquage dit ce qui s'AFFICHE, la
	//  redirection ce qui s'ATTEINT. Depuis que la gestion locative a une adresse,
	//  la seconde ne va plus de soi — un lien reçu par un locataire ouvrirait
	//  l'onglet que la barre lui cache.
	$: isBailleur = $currentUser?.statut === 'copropriétaire_bailleur';
	$: isResident = $currentUser?.statut === 'copropriétaire_résident';

	const ROUTE_BAUX_ACTIFS = routeSousOnglet('mon-lot', 'location', 'actif');

	// ── Onglet principal ───────────────────────────────────────────────────────
	//  L'onglet ET son sous-onglet viennent du CHEMIN — `/mon-lot/location/archives`
	//  est une adresse à part entière, qu'on peut envoyer. Le `load` les résout ;
	//  cet écran ne fait que les lire.
	export let data: { onglet: string; sous: string | null };
	$: mainTab = data.onglet;

	//  Les deux gestes d'accès (#928), refermés au changement d'onglet : un
	//  formulaire laissé derrière un onglet qu'on ne regarde plus est un
	//  formulaire qu'on croit avoir annulé.
	let accesDemande = false;
	let accesDeclare = false;
	$: if (mainTab) {
		accesDemande = false;
		accesDeclare = false;
	}
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

	//  🔴 `Objet` est devenu `ObjetRemis`, dans `$lib/api` (#806) : c'est une
	//  réponse d'API, pas une notion de cet écran, et il était déclaré à
	//  l'identique ici et dans le composant qui le rend.

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
		objets: ObjetRemis[];
	}

	// ── State (locataire bail) ────────────────────────────────────────────────
	let monBailData: any = null;
	$: isLocataire = $currentUser?.statut === 'locataire';

	// ── State (lots) ──────────────────────────────────────────────────────────
	let lots: LotDetail[] = [];
	let loading = true;
	/**  Non vide = on n'a PAS pu regarder. Distinct de « aucun lot associé ». */
	let erreurLots = '';
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

	//  🔴 L'état du retour d'objet vit dans `InventaireBail` (#806), avec les trois
	//  autres gestes d'inventaire. La page ne tient plus que les baux.

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

	// ── Derived ────────────────────────────────────────────────────────────────
	$: bauxActifs = baux.filter((b) => b.statut === 'actif' || b.statut === 'en_cours_sortie');
	$: bauxTermines = baux.filter((b) => b.statut === 'termine');

	// ── Init ───────────────────────────────────────────────────────────────────
	onMount(async () => {
		//  ⚠️ PAS `tenter` ici : ce `catch` fait plus que dire l'échec, il le
		//  MÉMORISE (`erreurLots`) pour que l'écran distingue « aucun lot » de
		//  « je n'ai pas pu regarder » (#816). `tenter` toaste et rend un booléen —
		//  il ne remplacerait pas cette nuance, il l'effacerait.
		try {
			lots = await lotsApi.mesList();
			if (lots.length > 0) selectedLotId = lots[0].id;
		} catch (e: any) {
			//  🔴 Sans cette variable, l'écran annonçait « Aucun lot associé » après
			//  un échec de chargement (#816) — et la page explique alors, en trois
			//  lignes, comment faire rattacher un lot qui EST peut-être déjà là.
			erreurLots = messageErreur(e, 'Impossible de charger vos lots');
			toast('error', erreurLots);
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
		const cible = bailATerminer;
		await tenter(async () => {
			const updated = await bailApi.terminerBail(cible.id, {
				date_sortie_reelle: dateSortie || null,
			});
			baux = baux.map((b) => (b.id === updated.id ? updated : b));
			bailATerminer = null;
		}, 'Bail terminé');
	}

	async function confirmerSupprimer() {
		if (!bailASupprimer) return;
		const cible = bailASupprimer;
		await tenter(async () => {
			await bailApi.supprimerBail(cible.id);
			baux = baux.filter((b) => b.id !== cible.id);
			bailASupprimer = null;
		}, 'Bail supprimé');
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
		const cible = bailEdite;
		await tenter(async () => {
			const updated = await bailApi.updateBail(cible.id, {
				...editLocataire,
				date_sortie_prevue: editLocataire.date_sortie_prevue || null,
				locataire_id: editLocataireId ?? null,
			});
			baux = baux.map((b) => (b.id === updated.id ? { ...updated, objets: b.objets } : b));
			bailEdite = null;
		}, 'Informations mises à jour');
	}

	//  `confirmerRetour` et `supprimerObjet` sont partis dans `InventaireBail`
	//  (#806) : quatre gestes sur une sous-entité entièrement contenue dans le
	//  bail. La page n'en apprend que le résultat, par `on:change`.
	/**  Recoud la liste d'objets d'un bail après un geste du composant. */
	function majObjets(bailId: number, objets: ObjetRemis[]) {
		baux = baux.map((b) => (b.id === bailId ? { ...b, objets } : b));
	}

	// ── Recherche locataire ────────────────────────────────────────────────────

	// ── Gestion accès ─────────────────────────────────────────────────────────

	//  🔴 L'ouverture ne fait plus QUE désigner le bail : le chargement des
	//  accès, la sélection et les deux gestes sont partis dans
	//  `ModaleAccesBail` (#779). La page n'en apprend rien — elle n'en avait
	//  besoin de rien.
	function ouvrirAccesBail(bail: Bail) {
		bailAcces = bail;
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

	// ── Helpers affichage ──────────────────────────────────────────────────────
	//  🔴 `typeLabel`, `statutObjetBadge` et `statutObjetLabel` sont partis AVEC le
	//  balisage qui les emploie (`InventaireBail`, #806). Les laisser ici aurait
	//  produit un tableau nu chez le voisin — le défaut de `standards/02` §4 ter,
	//  celui qui ne casse rien et qui se voit en production.

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
		//  ⚠️ SEPTIÈME écriture du libellé d'étage, et quatrième rendu (« Ét. 2 »).
		//  Trouvée par `lint:etage-libelle`, pas par ma relecture : elle est dans
		//  une fonction, pas dans le gabarit, et le relevé à la main l'avait sautée.
		const etiquette = etageLabel(lot.etage);
		const etage = etiquette ? ` · ${etiquette}` : '';
		const surface = lot.superficie ? ` · ${lot.superficie} m²` : '';
		return `${bat} — ${type}${sub} n°${lot.numero}${etage}${surface}`;
	}
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<EntetePage titre={_pc.titre} icone={_pc.icone || 'key-round'}>
	{#if mainTab === 'location'}
		<BoutonNouveau
			ouvert={showNewBail}
			libelle="Nouveau bail"
			on:basculer={() => (showNewBail = true)}
		/>
	{/if}
	<!--  🔴 DEUX gestes en tête (#928) : ils étaient deux sections tout en bas de
	      l'ancien écran. ⚠️ Ils disent deux choses — « Nouvel accès » demande au
	      syndic ce qu'on n'a pas, « Déclarer » signale ce qu'on détient déjà. -->
	{#if mainTab === 'badges' || mainTab === 'telecommandes'}
		<BoutonNouveau
			ouvert={accesDemande}
			libelle="Nouvel accès"
			on:basculer={() => {
				accesDemande = true;
				accesDeclare = false;
			}}
		/>
		<BoutonNouveau
			ouvert={accesDeclare}
			libelle="Déclarer un accès"
			on:basculer={() => {
				accesDeclare = true;
				accesDemande = false;
			}}
		/>
	{/if}
</EntetePage>
<div class="page-subtitle">{@html safeHtml(_pc.descriptif)}</div>

<!--  🔴 Barre TOUJOURS rendue (#928) : trois onglets pour tout le monde depuis
      que la page porte les accès. ⚠️ `masques` plutôt qu'une condition autour
      d'elle — le « si concerné » porte sur UN onglet, pas sur la rangée. -->
<BarreOnglets pageId="mon-lot" actif={mainTab} masques={peutGererLocation ? [] : ['location']} />

<!-- ── Onglets : Mes badges (Vigik) · Télécommandes de parking ───────── -->
<!--  🔴 Le contenu vit dans `OngletAcces` (#928) : `routeInterne` sert tous les
      onglets d'une page par UN écran, donc `/mon-lot/badges` arrive ici. Motif
      des dix-sept `Onglet*.svelte` de l'administration. -->
{#if mainTab === 'badges' || mainTab === 'telecommandes'}
	<OngletAcces section={mainTab} bind:showForm={accesDemande} bind:showDeclareForm={accesDeclare} />
{/if}

<!-- ── Onglet : Mes lots ────────────────────────────────────────────── -->
{#if mainTab === 'lots'}
	{#if loading}
		<p style="color:var(--color-text-muted)">Chargement…</p>
	{:else if erreurLots}
		<!--  L'échec AVANT le vide : « aucun lot » est une affirmation, et on ne
		      l'a pas constatée. -->
		<div class="empty-state">
			<h3>Impossible d’afficher vos lots</h3>
			<p>{erreurLots}</p>
		</div>
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
						<dd>{etageLabel(monBailData.lot_etage)}</dd>{/if}
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
							<dd>{etageLabel(lot.etage)}</dd>{/if}
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
								>{etageLabel(lot.etage, { suffixe: true })}</span
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
							class="btn-icon-edit"
							aria-label="Modifier le locataire"
							title="Modifier"
							on:click={() => ouvrirEditionLocataire(premierBail)}>&#x270F;&#xFE0F;</button
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
						<dd>{etageLabel(selectedLot.etage)}</dd>{/if}
					{#if selectedLot.superficie}<dt>Superficie</dt>
						<dd>{selectedLot.superficie} m²</dd>{/if}
				</dl>
			</div>
		{/if}
	{/if}
{/if}

<!-- ── Onglet : Gestion locative ────────────────────────────────────── -->
{#if mainTab === 'location'}
	<!--  Le contenu vit dans `OngletGestionLocative` (#928) : cette page a reçu les
	      deux sous-onglets d'accès, et le plafond de modularité a refusé — comme
	      l'audit de l'issue l'avait annoncé. La coupe suit la frontière que la
	      barre d'onglets dessine déjà. -->
	<OngletGestionLocative
		{baux}
		{bauxActifs}
		{bauxTermines}
		{bauxLoading}
		{lots}
		{bailTab}
		bind:showNewBail
		bind:newBail
		bind:newBailLotIds
		bind:newBailLocataireId
		{lotsACocher}
		{savingBail}
		{creerBail}
		{affecterAuto}
		{ouvrirEditionLocataire}
		{ouvrirAccesBail}
		{majObjets}
		{statutBailLabel}
		{nomLocataire}
		bind:bailATerminer
		bind:bailASupprimer
		bind:dateSortie
		{confirmerTerminer}
	/>
{/if}
<!-- ── Modal : terminer bail ────────────────────────────────────────── -->

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
<!--  Enveloppé pour sa `cle` : ce formulaire est rendu 240 lignes sous celui
      de création, donc en bas de page. Le motif est dans `FormulaireCreation`. -->
{#if bailEdite}
	<FormulaireCreation titre="Modifier les informations" cle={bailEdite.id}>
		<FormulaireBail
			edition
			intitule=""
			bind:bail={editLocataire}
			bind:locataireId={editLocataireId}
			on:annuler={() => (bailEdite = null)}
			on:enregistrer={sauvegarderLocataire}
		/>
	</FormulaireCreation>
{/if}

<!-- ── Modal : gestion des accès (Vigik / TC) ───────────────────────── -->
{#if bailAcces}
	<ModaleAccesBail
		bailId={bailAcces.id}
		titre={`Accès — ${nomLocataire(bailAcces)}`}
		typeLot={bailAccesLot?.type ?? null}
		on:fermer={() => (bailAcces = null)}
	/>
{/if}

<!-- ── Modal : retour objet ─────────────────────────────────────────── -->
<!--  🔴 La modale « Retour — … » A DÉMÉNAGÉ dans `InventaireBail` (#806) : elle
     porte sur un objet, pas sur un bail, et laisser son balisage ici pendant que
     le tableau qui l'ouvre est ailleurs aurait coupé un geste en deux fichiers. -->

<style>
	/*  ⚠️ Définie ICI **et** dans `OngletGestionLocative` : Svelte scope ses
	    styles au FICHIER, et la classe sert dans les deux. Ce n'est pas une
	    duplication à retirer — l'écran partirait nu. */
	.lbc-lot-badge {
		font-weight: 700;
		font-size: 0.92rem;
	}
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
	/*  🔴 DIX règles orphelines ont été retirées d'ici le 06/09/2026 (#806), et la
	    façon dont elles sont apparues vaut d'être écrite.

	    Elles étaient mortes DEPUIS LONGTEMPS — restes d'un balisage parti, dont
	    `.search-locataire-row`, recopiée ici alors que `RechercheLocataire.svelte`
	    la porte avec son propre balisage. `lint:css-orphelin` n'en signalait
	    aucune.

	    ⚠️ La raison : le tableau d'inventaire contenait une classe INTERPOLÉE
	    (`class="badge {statutObjetBadge[objet.statut] ?? …}"`). Devant une classe
	    qu'il ne peut pas résoudre, le compilateur Svelte devient conservateur et
	    cesse de déclarer des sélecteurs inutilisés — POUR TOUT LE FICHIER. Une
	    seule interpolation aveuglait donc le contrôle sur 1 600 lignes.

	    Le tableau parti dans `InventaireBail`, l'aveuglement est parti avec lui, et
	    les dix restes sont devenus visibles. Un contrôle vert peut ne rien mesurer
	    (`standards/04`) : ici il ne le disait pas — il annonçait « 0 orphelin »,
	    pas « je n'ai pas pu regarder ». */
	.lot-vacant {
		opacity: 0.8;
		border-style: dashed;
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
	/*  `.tabs` est partie avec les sous-onglets de la gestion locative
	    (12/09/2026, #928) : le style suit le balisage. */
	/* le reste vient de la charte (#607) */

	/* Bail sub-tabs */

	/* Lot multi-checklist */

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

	/*  🔴 `.chip-btn` retirée le 28/08/2026 (#491) : c'était la pastille de la
	    charte, sous un AUTRE NOM — donc invisible à toute recherche sur `pill`,
	    et libre de diverger sans que personne ne la rapproche de son modèle.
	    Elle avait déjà divergé : `.78rem`, `.2rem .55rem`, et un état actif en
	    teinte pâle là où la charte remplit la pastille. */
</style>
