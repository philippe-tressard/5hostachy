<script lang="ts">
	import { tenter, messageErreur } from '$lib/erreurs';
	import AideSource from '$lib/components/AideSource.svelte';
	import BadgePerimetre from '$lib/components/BadgePerimetre.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import SectionDiagnostics from '$lib/components/SectionDiagnostics.svelte';
	import EntetePage from '$lib/components/EntetePage.svelte';
	import FormulaireCreation from '$lib/components/FormulaireCreation.svelte';
	import PiedFormulaire from '$lib/components/PiedFormulaire.svelte';
	import { onMount } from 'svelte';
	import { isCS, isLocataire } from '$lib/stores/auth';
	import {
		copropriete as coproprieteApi,
		uploads as uploadsApi,
		documents as documentsApi,
		diagnostics as diagnosticsApi,
	} from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { cibleDuHash, revelerCible } from '$lib/deepLink';
	import { getPageConfig, configStore, siteNomStore, defautsDePage } from '$lib/stores/pageConfig';
	import { fmtDateShort as fmt } from '$lib/date';
	import BarreOnglets from '$lib/components/BarreOnglets.svelte';
	import SectionRegles from '$lib/components/SectionRegles.svelte';
	import CarnetEntretien from '$lib/components/CarnetEntretien.svelte';
	import FicheResidence from '$lib/components/FicheResidence.svelte';
	import RubriqueDocuments from '$lib/components/RubriqueDocuments.svelte';
	import ChargementPartiel from '$lib/components/ChargementPartiel.svelte';
	import { essayer, messagePartiel } from '$lib/chargement';
	import EtatListe from '$lib/components/EtatListe.svelte';

	/**  L'onglet vient du CHEMIN, résolu par `+page.ts` — jamais d'un `let`
	 *   qu'on affecte : une page qui écrit son propre onglet ne peut plus être
	 *   atteinte par son adresse (`ux-patterns` §4). */
	export let data: { onglet: string };
	$: onglet = data.onglet;

	$: _pc = getPageConfig($configStore, 'residence', defautsDePage('residence'));
	$: _siteNom = $siteNomStore;

	// ── State ──────────────────────────────────────────────────────────────────
	let copropriete: any = null;
	let batiments: any[] = [];
	let plans: any[] = [];
	let reglements: any[] = [];
	let crAg: any[] = [];
	let loading = true;
	//  🔴 Une erreur PAR liste, et non une pour la page (#522). Ces cinq
	//  rubriques se chargent indépendamment : dire « rien n'a marché » quand
	//  seuls les diagnostics ont échoué serait aussi faux que de ne rien dire.
	let ePlans = '',
		eReglements = '',
		eCrAg = '',
		eDiagnostics = '';
	//  Les bâtiments ne s'AFFICHENT pas : ils garnissent des menus déroulants et
	//  la correspondance « Bât. n ». Leur absence ne vide pas l'écran, elle le
	//  rend faux — d'où le bandeau plutôt qu'un état de liste.
	let eReference = '';

	let catIdPlan: number | null = null;
	let catIdReglement: number | null = null;
	let catIdCrAg: number | null = null;

	// Édition résidence
	let editing = false;
	let saving = false;
	let editNom = '';
	let editAdresse = '';
	let editAnnee: string | number = '';
	let editNbLots: string | number = '';
	let editNbLotsPrincipaux: string | number = '';
	let editImmatriculation = '';

	// Photo bannière
	let uploadingPhoto = false;

	//  Plans, règlement, CR d'AG : leur dépôt, leur correction et leur
	//  suppression vivent dans `RubriqueDocuments` (#779) — ils y étaient écrits
	//  trois fois, et la copie du plan liait son périmètre à celle de l'AG (#470).

	// Diagnostics réglementaires
	let diagnosticTypes: any[] = [];
	//  ⚠️ L'état du dépôt et de la correction d'un rapport vit dans
	//  `SectionDiagnostics` : il n'a d'objet que là où il est employé.

	// Règles & Recommandations

	// ── Derived ────────────────────────────────────────────────────────────────
	// Composition depuis les champs stockés sur Batiment et Copropriete

	//  Réactif : le tri des plans lit `batiments`, qui arrive après eux.
	$: trierPlans = (docs: any[]) =>
		[...docs].sort((a, b) => {
			if (!a.batiment_id && b.batiment_id) return -1;
			if (a.batiment_id && !b.batiment_id) return 1;
			const bA = batiments.find((x) => x.id === a.batiment_id);
			const bB = batiments.find((x) => x.id === b.batiment_id);
			return (bA?.numero ?? '').localeCompare(bB?.numero ?? '');
		});
	const trierCrAg = (docs: any[]) =>
		[...docs].sort((a, b) => {
			const anneeB = (b.annee as number) ?? 0;
			const anneeA = (a.annee as number) ?? 0;
			if (anneeB !== anneeA) return anneeB - anneeA;
			const dateB = (b.date_ag ?? b.publie_le ?? '') as string;
			const dateA = (a.date_ag ?? a.publie_le ?? '') as string;
			return dateB.localeCompare(dateA);
		});

	function batimentLabel(id: number | null | undefined): string {
		if (!id) return 'Résidence';
		const b = batiments.find((x) => x.id === id);
		return b ? `Bât. ${b.numero}` : 'Bât. ?';
	}

	// ── Init ───────────────────────────────────────────────────────────────────
	onMount(async () => {
		try {
			const [[copro, eCopro], [bats, eBats], [cats, eCats]] = await Promise.all([
				essayer<any>(coproprieteApi.get(), null),
				essayer<any[]>(coproprieteApi.batiments(), []),
				essayer<any[]>(documentsApi.listCategories(), []),
			]);
			copropriete = copro;
			batiments = bats;
			//  ⚠️ Les CATÉGORIES sont la donnée la plus traître des trois : sans
			//  elles, `catIdPlan` & consorts valent `null`, les trois appels
			//  suivants sont SAUTÉS, et les trois listes s'affichent vides sans
			//  qu'aucun appel n'ait échoué. Une absence parfaitement silencieuse,
			//  produite par une erreur survenue deux lignes plus haut.
			eReference = messagePartiel(eCopro, eBats, eCats);

			catIdPlan = (cats as any[]).find((c) => c.code === 'plan_residence')?.id ?? null;
			catIdReglement = (cats as any[]).find((c) => c.code === 'reglement_copropriete')?.id ?? null;
			catIdCrAg = (cats as any[]).find((c) => c.code === 'pv_ag')?.id ?? null;

			//  Une catégorie absente propage l'erreur des catégories : la liste
			//  n'est pas vide, elle est indéterminée.
			const [[p, ep], [r, er], [ag, eag], [diag, ediag]] = await Promise.all([
				catIdPlan
					? essayer<any[]>(documentsApi.list(catIdPlan), [])
					: Promise.resolve([[], eCats] as [any[], string]),
				catIdReglement
					? essayer<any[]>(documentsApi.list(catIdReglement), [])
					: Promise.resolve([[], eCats] as [any[], string]),
				catIdCrAg
					? essayer<any[]>(documentsApi.list(catIdCrAg), [])
					: Promise.resolve([[], eCats] as [any[], string]),
				essayer<any[]>(diagnosticsApi.listTypes(), []),
			]);
			plans = p;
			ePlans = ep;
			reglements = r;
			eReglements = er;
			crAg = ag;
			eCrAg = eag;
			diagnosticTypes = diag;
			eDiagnostics = ediag;

			// Lien profond depuis le fil d'activité ou une notification :
			// `#doc-<id>` (plan, règlement, PV d'AG) ou `#diag-<id>` (rapport de
			// diagnostic). La page est longue et découpée en sections — y arriver
			// sans viser l'élément revient à faire chercher l'utilisateur.
			const idDoc = cibleDuHash('doc');
			if (idDoc !== null) revelerCible(`doc-${idDoc}`);
			const idDiag = cibleDuHash('diag');
			if (idDiag !== null) revelerCible(`diag-${idDiag}`);
		} catch (e) {
			toast('error', messageErreur(e, 'Erreur de chargement'));
		} finally {
			loading = false;
		}
	});

	// ── Édition résidence ──────────────────────────────────────────────────────
	function startEdit() {
		if (!copropriete) return;
		editNom = copropriete.nom ?? '';
		editAdresse = copropriete.adresse ?? '';
		editAnnee = copropriete.annee_construction ?? '';
		editNbLots = copropriete.nb_lots_total ?? '';
		editNbLotsPrincipaux = copropriete.nb_lots_principaux ?? '';
		editImmatriculation = copropriete.numero_immatriculation ?? '';
		editing = true;
	}

	async function saveEdit() {
		saving = true;
		await tenter(async () => {
			copropriete = await coproprieteApi.update({
				nom: editNom || undefined,
				adresse: editAdresse || undefined,
				annee_construction: editAnnee ? Number(editAnnee) : undefined,
				nb_lots_total: editNbLots ? Number(editNbLots) : undefined,
				nb_lots_principaux: editNbLotsPrincipaux ? Number(editNbLotsPrincipaux) : undefined,
				numero_immatriculation: editImmatriculation || undefined,
			});
			editing = false;
		}, 'Résidence mise à jour');
		saving = false;
	}

	// ── Photo ──────────────────────────────────────────────────────────────────
	async function handlePhotoFile(e: Event) {
		const file = (e.target as HTMLInputElement).files?.[0];
		if (!file) return;
		uploadingPhoto = true;
		await tenter(
			async () => {
				const { url } = await uploadsApi.residence(file);
				if (copropriete) copropriete = { ...copropriete, photo_url: url };
			},
			'Photo mise à jour',
			'Erreur upload',
		);
		uploadingPhoto = false;
		(e.target as HTMLInputElement).value = '';
	}
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<EntetePage titre={_pc.titre} descriptif={_pc.descriptif} icone={_pc.icone || 'building-2'} />

<!--  Cette page n'avait pas d'onglets avant le carnet d'entretien (10/09/2026).
      La rangée passe par `BarreOnglets`, qui lit la liste, l'ordre, les libellés
      et les routes dans `$lib/pages` — un `<div class="tabs">` local rouvrirait
      les cinq divergences que ce composant a fermées. -->
<BarreOnglets pageId="residence" actif={onglet} />

<!--  ⚠️ En HAUT, avant tout le reste : les bâtiments et les catégories de
      document garnissent les menus déroulants et la correspondance « Bât. n ».
      Leur absence ne vide pas l'écran, elle le rend faux — et un avertissement
      posé plus bas serait lu après ce qu'il devait qualifier (#522). -->
<ChargementPartiel
	erreur={eReference}
	consequence="Les numéros de bâtiment et les listes de documents peuvent être incomplets ou absents."
/>

<!--  Le carnet est une VUE de la résidence, pas un écran à part : il partage
      l'en-tête, la barre d'onglets et l'adresse de cette page. -->
{#if onglet === 'carnet'}
	<CarnetEntretien />
{:else if onglet === 'fiche' && loading}
	<EtatListe chargement />
{:else if onglet === 'fiche' && copropriete}
	<!-- ── Photo Bannière ─────────────────────────────────────────────────── -->
	<figure class="photo-figure">
		<div class="photo-banner">
			{#if copropriete.photo_url}
				<img src={copropriete.photo_url} alt="La résidence" />
			{:else}
				<div class="photo-placeholder">
					<Icon name="building-2" size={48} />
					<span>Aucune photo</span>
				</div>
			{/if}
			{#if $isCS}
				<label class="photo-change-btn" class:uploading={uploadingPhoto}>
					{uploadingPhoto ? '…' : '\u{1F4F8} Changer la photo'}
					<input type="file" accept="image/*" on:change={handlePhotoFile} style="display:none" />
				</label>
			{/if}
		</div>
		<figcaption class="photo-caption">{copropriete.nom}</figcaption>
	</figure>

	<!-- ── Section : Résidence ───────────────────────────────────────────── -->
	<section style="margin-bottom:2.5rem">
		<div class="section-header">
			<h2 class="section-title">Résidence : {copropriete.nom}</h2>
			{#if $isCS && !editing}
				<button
					class="btn-icon-edit"
					aria-label="Modifier la fiche de la résidence"
					title="Modifier"
					on:click={startEdit}>&#x270F;&#xFE0F;</button
				>
			{/if}
		</div>

		{#if editing}
			<!--  Le cadre et le pied STANDARD (#1329) : une carte et une rangée de
			      boutons écrites à la main, « Annuler » en bouton plein. -->
			<FormulaireCreation titre="Modifier la fiche de la résidence" cle="fiche">
				<form on:submit|preventDefault={saveEdit}>
					<div class="edit-grid">
						<div class="field">
							<label for="e-nom">Nom</label><input id="e-nom" type="text" bind:value={editNom} />
						</div>
						<div class="field">
							<label for="e-adr">Adresse</label><input
								id="e-adr"
								type="text"
								bind:value={editAdresse}
							/>
						</div>
						<div class="field">
							<label for="e-ann">Année de construction</label><input
								id="e-ann"
								type="number"
								bind:value={editAnnee}
								min="1800"
								max="2100"
							/>
						</div>
						<div class="field">
							<label for="e-lots">Lots — total, caves et parkings compris</label><input
								id="e-lots"
								type="number"
								bind:value={editNbLots}
								min="1"
							/>
						</div>
						<div class="field">
							<label for="e-lots-p">Dont habitation, commerces et bureaux</label><input
								id="e-lots-p"
								type="number"
								bind:value={editNbLotsPrincipaux}
								min="1"
							/>
						</div>
						<div class="field">
							<label for="e-imm">N° immatriculation (ANAH)</label><input
								id="e-imm"
								type="text"
								bind:value={editImmatriculation}
							/>
						</div>
						<!--  🔴 Compagnie, n° de police et échéance ONT ÉTÉ RETIRÉS d'ici.
						      Depuis #490 la fiche les lit sur le CONTRAT d'assurance, et
						      `copropriete_lue` efface ces colonnes : les saisir ici
						      corrigeait donc une valeur que plus aucun écran n'affiche.
						      Trouvé le 29/08/2026 en instruisant la remarque sur la
						      reconduction tacite. C'est le défaut que `source_du_nom` a
						      fermé pour le nom du syndic (#535), sur trois champs cette
						      fois — un formulaire qui survit à sa source se lit comme une
						      commande, pas comme un vestige. -->
						<div class="field" style="grid-column:1/-1">
							<AideSource
								active
								origine="contrat d'assurance"
								ou="Prestataires → Contrats"
								repli=""
							/>
						</div>
					</div>
					<PiedFormulaire enCours={saving} on:annule={() => (editing = false)} />
				</form>
			</FormulaireCreation>
		{:else}
			<FicheResidence {copropriete} {batiments} />
		{/if}
	</section>

	<SectionRegles />

	<!-- ── Plans · Règlement · Comptes-rendus d'AG : une rubrique, trois usages ── -->
	<RubriqueDocuments
		mode="plan"
		titre="&#x1F5FA;️ Plans"
		categorieId={catIdPlan}
		bind:documents={plans}
		erreur={ePlans}
		trier={trierPlans}
		messageVide="Aucun plan ajouté."
		peutModifier={$isCS}
		dateDe={(d) => fmt(d.publie_le)}
		intitule="Ajouter un plan"
		placeholderTitre="ex : Plan de masse résidence"
		placeholderDescription="Ce que ce plan montre, à quelle date il a été relevé…"
		avecPerimetre
		quoi="Ce plan"
		messageAjout="Plan ajouté"
	>
		<svelte:fragment slot="badges" let:doc>
			<span class="badge badge-blue"
				>{doc.batiment_id ? batimentLabel(doc.batiment_id) : 'Copropriété'}</span
			>
		</svelte:fragment>
	</RubriqueDocuments>

	<RubriqueDocuments
		mode="reglement"
		titre="&#x1F4D6; Règlement de copropriété"
		categorieId={catIdReglement}
		bind:documents={reglements}
		erreur={eReglements}
		messageVide="Aucun règlement ajouté."
		peutModifier={$isCS}
		dateDe={(d) => fmt(d.publie_le)}
		intitule="Ajouter un règlement"
		placeholderTitre="ex : Règlement de copropriété 2024"
		placeholderDescription="Ce qu'il remplace, ce qu'il ne couvre pas, où sont les annexes…"
		quoi="Ce règlement"
		messageAjout="Règlement ajouté"
	/>

	{#if !$isLocataire}
		<RubriqueDocuments
			mode="ag"
			titre="&#x1F4CB; Comptes-rendus d'AG"
			categorieId={catIdCrAg}
			bind:documents={crAg}
			erreur={eCrAg}
			trier={trierCrAg}
			messageVide="Aucun compte-rendu ajouté."
			peutModifier={$isCS}
			intitule="Ajouter un CR d'AG"
			placeholderTitre="ex : PV AG ordinaire 2025"
			placeholderDescription="Les points saillants, les résolutions votées, ce qui reste en suspens…"
			avecPerimetre
			quoi="Ce compte-rendu d'AG"
			messageAjout="CR d'AG ajouté"
		>
			<svelte:fragment slot="badges" let:doc>
				{#if doc.annee}<span class="badge badge-gray" style="font-variant-numeric:tabular-nums"
						>{doc.annee}</span
					>{/if}
				{#if doc.date_ag}<span class="doc-date">AG du {fmt(doc.date_ag)}</span>{/if}
				<!--  🔴 `perimetreLabel` sur des CODES, plus `batimentLabel` sur des
			      identifiants (#470). Trois branches se sont réduites à une : le
			      libellé d'un périmètre se calcule, il ne se décide pas ici.
			      L'ancien rendu ne savait dire que « Bât. N » ou « Copropriété » ;
			      celui-ci nomme le parking, les caves, l'AFUL et les espaces —
			      et suit l'arbre quand un nœud est renommé. -->
				<BadgePerimetre perimetre={doc.perimetre_cible} ton="purple">
					<span class="badge badge-green">Copropriété</span>
				</BadgePerimetre>
			</svelte:fragment>
		</RubriqueDocuments>
	{/if}

	<!-- ── Section : Diagnostics et Contrôles Réglementaires ────────────── -->
	<!--  🔴 UN COMPOSANT depuis le 08/09/2026 (#852). C'était la dernière
	      section de cet écran à vivre à même la page — onze variables d'état,
	      six gestes, cent quatre-vingts lignes de balisage — alors que les
	      trois autres partagent `SectionDocuments` depuis #522. Le garde-fou
	      de modularité l'a refusée quand les formulaires y sont rentrés. -->
	{#if !$isLocataire}
		<SectionDiagnostics bind:types={diagnosticTypes} erreur={eDiagnostics} peutModifier={$isCS} />
	{/if}
{:else}
	<div class="empty-state">
		<h3>Résidence non configurée</h3>
		<p>Les informations de la résidence ne sont pas encore disponibles.</p>
	</div>
{/if}

<style>
	/* ── Photo bannière ─────────────────────────────────────────── */
	.photo-figure {
		margin: 0 auto 2rem;
		max-width: 800px;
		text-align: center;
	}
	.photo-caption {
		font-size: var(--fs-base);
		color: var(--color-text-muted);
		padding: 0.35rem 0;
		font-style: italic;
	}
	.photo-banner {
		position: relative;
		width: 100%;
		border-radius: var(--radius);
		overflow: hidden;
		background: var(--color-bg);
		border: 1px solid var(--color-border);
	}
	.photo-banner img {
		width: 100%;
		aspect-ratio: 16 / 5;
		object-fit: cover;
		display: block;
	}
	.photo-placeholder {
		width: 100%;
		aspect-ratio: 16 / 5;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		color: var(--color-text-muted);
		background: var(--color-bg);
		font-size: var(--fs-base);
	}
	.photo-change-btn {
		position: absolute;
		bottom: 0.75rem;
		right: 0.75rem;
		background: rgba(0, 0, 0, 0.55);
		color: #fff;
		border: none;
		border-radius: var(--radius);
		padding: 0.35rem 0.75rem;
		font-size: var(--fs-sm);
		cursor: pointer;
		backdrop-filter: blur(4px);
		transition: background var(--duree-geste);
	}
	@media (hover: hover) and (pointer: fine) {
		.photo-change-btn:hover {
			background: rgba(0, 0, 0, 0.75);
		}
	}
	.photo-change-btn.uploading {
		opacity: 0.6;
		pointer-events: none;
	}

	/* ── Sections ───────────────────────────────────────────────── */
	/*  🔴 `.section-header` est remontée dans `styles/composants.css` le
	    06/09/2026 (#805) : elle était écrite trois fois à l'identique — ici, dans
	    `SectionDocuments` et dans `acces-securite` — et un quatrième écran qui
	    l'employait l'aurait rendue NUE. C'est `lint:classes-nues` qui l'a dit, et
	    c'est le moment où une copie devient une règle. */
	/*  Seul `margin: 0` differe : la charte pose `margin-bottom` (#607, 28/08/2026). */
	.section-title {
		margin: 0;
	}

	/* ── Bâtiments / lot counts ─────────────────────────────────── */

	/* ── Documents ──────────────────────────────────────────────── */
	/*  🔴 TOUTE la « ligne de document » vit dans `styles/composants.css` (#491) :
	    cette page l'emploie dans SON balisage, et trois blocs en sortaient NUS.
	    Le récit — et pourquoi `lint:classes-nues` ne le voyait pas — est là-bas. */

	/* ── Edit form ──────────────────────────────────────────────── */
	.edit-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(260px, 100%), 1fr));
		gap: 0.75rem;
	}

	/*  Trois couleurs de badge réécrites ici en `:global(…)`, donc pour tout le
	    site une fois cette feuille chargée — et `.badge-purple` y prenait encore
	    une quatrième valeur, différente de celle d'`espace-cs`. Retirées (#562) :
	    la charte de `styles/composants.css` les porte déjà. */

	/* ── Pills périmètre ────────────────────────────────────────── */
	/*  `.perimetre-pills` retirée (#561) : copie identique au caractère près de
	    celle de `styles/composants.css`, donc inerte — révélée en passant la
	    classe en PROP. Un composant partagé montre ce qu'une page gardait. */
	/*  🔴 `.pill`, `.pill:hover` et `.pill-active` retirées le 28/08/2026 (#491).
	    Cet écran portait SA variante — bordure 1px au lieu de 1.5px, fond
	    `surface` au lieu de `bg`, taille .8rem au lieu de .85rem — et elle
	    GAGNAIT, par la classe de portée que Svelte ajoute au sélecteur. Deux
	    styles de pastille coexistaient donc sciemment. `ecrans.css` portait
	    l'avertissement en toutes lettres : un commentaire n'est pas un
	    garde-fou. */

	/*  🔴 L'EN-TÊTE d'une modale ne s'écrit plus ici : `Modale.svelte` le rend, et
	    `styles/composants.css` le style (`.modal-titre`). #607 avait retiré
	    `.modal-header`, `.modal-close` et `.modal-footer` de ces trois écrans en
	    laissant `.modal-header h3` — la seule des quatre qui n'existait PAS en
	    global, donc la seule que le retrait ne pouvait pas solder. Elle a survécu
	    à l'identique dans les trois, et divergeait du `h2` de la charte. */

	/* ── Diagnostics ─────────────────────────────────────────────── */
</style>
