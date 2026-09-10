<script lang="ts">
	import { confirmer, SUPPRESSION } from '$lib/confirmation';
	import AideSource from '$lib/components/AideSource.svelte';
	import { perimetreLabel, estPerimetreParDefaut } from '$lib/perimetres';
	import Icon from '$lib/components/Icon.svelte';
	import FormulaireDocument from '$lib/components/FormulaireDocument.svelte';
	import SectionDiagnostics from '$lib/components/SectionDiagnostics.svelte';
	import FormulaireEditionDocument from '$lib/components/FormulaireEditionDocument.svelte';
	import EntetePage from '$lib/components/EntetePage.svelte';
	import { onMount } from 'svelte';
	import { isCS, currentUser } from '$lib/stores/auth';
	$: isLocataire = $currentUser?.statut === 'locataire';
	import {
		copropriete as coproprieteApi,
		uploads as uploadsApi,
		documents as documentsApi,
		diagnostics as diagnosticsApi,
		ApiError,
	} from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { cibleDuHash, revelerCible } from '$lib/deepLink';
	import { getPageConfig, configStore, siteNomStore, defautsDePage } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';
	import { fmtDateShort as fmt } from '$lib/date';
	import BarreOnglets from '$lib/components/BarreOnglets.svelte';
	import SectionRegles from '$lib/components/SectionRegles.svelte';
	import CarnetEntretien from '$lib/components/CarnetEntretien.svelte';
	import FicheResidence from '$lib/components/FicheResidence.svelte';
	import SectionDocuments from '$lib/components/SectionDocuments.svelte';
	import ChargementPartiel from '$lib/components/ChargementPartiel.svelte';
	import { essayer, messagePartiel } from '$lib/chargement';

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

	// Formulaires documents
	let showPlanForm = false;
	let newPlanTitre = '';
	let newPlanDescription = '';
	//  🔴 Le plan liait son sélecteur à `newCrAgPerimetre` — la variable du CR
	//  d'AG (copie du 27/08, #470). Choisir un périmètre sur un plan ne faisait
	//  donc rien pour le plan, et pré-remplissait en douce le formulaire d'AG.
	//  Il a désormais le sien, et les deux formulaires sont le même objet.
	let newPlanPerimetre: string[] = [];
	let newPlanFichiers: FileList | null = null;
	let savingPlan = false;

	let showReglementForm = false;
	let newReglementTitre = '';
	let newReglementDescription = '';
	let newReglementFichiers: FileList | null = null;
	let savingReglement = false;

	let showCrAgForm = false;
	let newCrAgTitre = '';
	let newCrAgDescription = '';
	let newCrAgAnnee: string | number = '';
	let newCrAgDateAg = '';
	//  🔴 Des CODES de périmètre, plus des identifiants de bâtiments (#470).
	//  L'écran parlait `number[]`, c'est-à-dire en clés primaires : il ne pouvait
	//  cibler ni le parking, ni les caves, ni l'AFUL, ni un espace de bâtiment —
	//  toute l'arborescence administrée lui était inaccessible.
	//
	//  ⚠️ Descriptif, jamais un droit : une AG est visible de TOUS les
	//  copropriétaires quel que soit le bâtiment dont elle parle (#617). C'est
	//  cet arbitrage qui a rendu la migration possible sans toucher aux accès.
	let newCrAgPerimetre: string[] = [];
	let newCrAgFichiers: FileList | null = null;
	let savingCrAg = false;

	// Édition document (plans, règlements, CR d'AG)
	let editingDocId: number | null = null;
	let editingDocMode: 'plan' | 'reglement' | 'ag' = 'plan';
	let editingDocTitre = '';
	let editingDocAnnee: string | number = '';
	let editingDocDate = '';
	//  🔴 Périmètre et description : deux des trois champs que l'édition
	//  n'exposait pas (#852). *« très peu de champs sont éditables »*.
	let editingDocPerimetre: string[] = [];
	let editingDocDescription = '';
	let savingDoc = false;

	// Diagnostics réglementaires
	let diagnosticTypes: any[] = [];
	//  ⚠️ L'état du dépôt et de la correction d'un rapport vit dans
	//  `SectionDiagnostics` : il n'a d'objet que là où il est employé.

	// Règles & Recommandations

	// ── Derived ────────────────────────────────────────────────────────────────
	// Composition depuis les champs stockés sur Batiment et Copropriete

	$: sortedPlans = [...plans].sort((a, b) => {
		if (!a.batiment_id && b.batiment_id) return -1;
		if (a.batiment_id && !b.batiment_id) return 1;
		const bA = batiments.find((x) => x.id === a.batiment_id);
		const bB = batiments.find((x) => x.id === b.batiment_id);
		return (bA?.numero ?? '').localeCompare(bB?.numero ?? '');
	});
	$: sortedCrAg = [...crAg].sort((a, b) => {
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
		} catch {
			toast('error', 'Erreur de chargement');
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
		try {
			copropriete = await coproprieteApi.update({
				nom: editNom || undefined,
				adresse: editAdresse || undefined,
				annee_construction: editAnnee ? Number(editAnnee) : undefined,
				nb_lots_total: editNbLots ? Number(editNbLots) : undefined,
				nb_lots_principaux: editNbLotsPrincipaux ? Number(editNbLotsPrincipaux) : undefined,
				numero_immatriculation: editImmatriculation || undefined,
			});
			editing = false;
			toast('success', 'Résidence mise à jour');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			saving = false;
		}
	}

	// ── Photo ──────────────────────────────────────────────────────────────────
	async function handlePhotoFile(e: Event) {
		const file = (e.target as HTMLInputElement).files?.[0];
		if (!file) return;
		uploadingPhoto = true;
		try {
			const { url } = await uploadsApi.residence(file);
			if (copropriete) copropriete = { ...copropriete, photo_url: url };
			toast('success', 'Photo mise à jour');
		} catch (err) {
			toast('error', err instanceof ApiError ? err.message : 'Erreur upload');
		} finally {
			uploadingPhoto = false;
			(e.target as HTMLInputElement).value = '';
		}
	}

	// ── Plans ──────────────────────────────────────────────────────────────────
	async function addPlan() {
		const fichier = newPlanFichiers?.[0];
		if (!catIdPlan || !newPlanTitre.trim() || !fichier) return;
		savingPlan = true;
		try {
			//  Le périmètre décrit DE QUOI parle le plan ; il ne restreint pas sa
			//  lecture — même règle que le CR d'AG ci-dessous, et même raison
			//  (migration 0159). Les droits restent à `résidence`.
			const doc = await documentsApi.upload({
				titre: newPlanTitre.trim(),
				categorieId: catIdPlan,
				file: fichier,
				description: newPlanDescription.trim(),
				perimetreCible: newPlanPerimetre,
			});
			plans = [doc, ...plans];
			showPlanForm = false;
			newPlanTitre = '';
			newPlanDescription = '';
			newPlanPerimetre = [];
			newPlanFichiers = null;
			toast('success', 'Plan ajouté');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			savingPlan = false;
		}
	}

	async function deletePlan(id: number) {
		if (!(await confirmer(SUPPRESSION('Ce plan')))) return;
		try {
			await documentsApi.delete(id);
			plans = plans.filter((d) => d.id !== id);
			toast('success', 'Plan supprimé');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}

	// ── Règlement ──────────────────────────────────────────────────────────────
	async function addReglement() {
		const fichier = newReglementFichiers?.[0];
		if (!catIdReglement || !newReglementTitre.trim() || !fichier) return;
		savingReglement = true;
		try {
			const doc = await documentsApi.upload({
				titre: newReglementTitre.trim(),
				categorieId: catIdReglement,
				file: fichier,
				description: newReglementDescription.trim(),
			});
			reglements = [doc, ...reglements];
			showReglementForm = false;
			newReglementTitre = '';
			newReglementDescription = '';
			newReglementFichiers = null;
			toast('success', 'Règlement ajouté');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			savingReglement = false;
		}
	}

	async function deleteReglement(id: number) {
		if (!(await confirmer(SUPPRESSION('Ce document')))) return;
		try {
			await documentsApi.delete(id);
			reglements = reglements.filter((d) => d.id !== id);
			toast('success', 'Supprimé');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}

	// ── CR d'AG ────────────────────────────────────────────────────────────────
	async function addCrAg() {
		const fichier = newCrAgFichiers?.[0];
		if (!catIdCrAg || !newCrAgTitre.trim() || !fichier) return;
		if (!newCrAgAnnee || !newCrAgDateAg) return;
		savingCrAg = true;
		try {
			//  🔴 UN PV D'AG N'EST JAMAIS RESTREINT PAR SON PÉRIMÈTRE : le ciblage
			//  dit de quoi il parle, pas qui peut le lire. Il part donc toujours en
			//  `résidence` côté DROITS, les périmètres dans `perimetre_cible`.
			//  Le pourquoi : migration 0159.
			const doc = await documentsApi.upload({
				titre: newCrAgTitre.trim(),
				categorieId: catIdCrAg,
				file: fichier,
				description: newCrAgDescription.trim(),
				annee: newCrAgAnnee ? Number(newCrAgAnnee) : undefined,
				dateAg: newCrAgDateAg || undefined,
				perimetreCible: newCrAgPerimetre,
			});
			crAg = [doc, ...crAg];
			showCrAgForm = false;
			newCrAgTitre = '';
			newCrAgDescription = '';
			newCrAgAnnee = '';
			newCrAgDateAg = '';
			newCrAgPerimetre = [];
			newCrAgFichiers = null;
			toast('success', "CR d'AG ajouté");
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			savingCrAg = false;
		}
	}

	async function deleteCrAg(id: number) {
		if (!(await confirmer(SUPPRESSION('Ce document')))) return;
		try {
			await documentsApi.delete(id);
			crAg = crAg.filter((d) => d.id !== id);
			toast('success', 'Supprimé');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		}
	}

	// ── Édition document ───────────────────────────────────────────────────────────────────
	function startEditDoc(doc: any, mode: 'plan' | 'reglement' | 'ag') {
		editingDocId = doc.id;
		editingDocMode = mode;
		editingDocTitre = doc.titre ?? '';
		editingDocAnnee = doc.annee ?? '';
		editingDocDate = doc.date_ag ? String(doc.date_ag).substring(0, 10) : '';
		editingDocDescription = doc.description ?? '';
		//  ⚠️ `perimetre_cible` sort du serveur en LISTE, jamais en JSON brut
		//  (`schemas.DocumentRead`). Le re-parser ici serait une seconde façon de
		//  lire la même chose, et elles divergeraient au premier format ajouté.
		editingDocPerimetre = Array.isArray(doc.perimetre_cible) ? [...doc.perimetre_cible] : [];
	}

	async function saveEditDoc() {
		if (!editingDocId) return;
		savingDoc = true;
		try {
			const updated = await documentsApi.update(editingDocId, {
				titre: editingDocTitre.trim() || undefined,
				//  🔴 Les deux champs que la correction n'envoyait pas (#852) —
				//  et que le serveur n'acceptait pas non plus. Les ouvrir d'un
				//  seul côté aurait donné des champs qui ne font rien.
				description: editingDocDescription,
				perimetre_cible: editingDocPerimetre,
				annee: editingDocAnnee ? Number(editingDocAnnee) : null,
				date_ag: editingDocDate || null,
			});
			if (editingDocMode === 'plan') {
				plans = plans.map((d) => (d.id === editingDocId ? updated : d));
			} else if (editingDocMode === 'reglement') {
				reglements = reglements.map((d) => (d.id === editingDocId ? updated : d));
			} else {
				crAg = crAg.map((d) => (d.id === editingDocId ? updated : d));
			}
			editingDocId = null;
			toast('success', 'Document mis à jour');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			savingDoc = false;
		}
	}
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<EntetePage titre={_pc.titre} icone={_pc.icone || 'building-2'} />

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
<div class="page-subtitle">{@html safeHtml(_pc.descriptif)}</div>

<!--  Le carnet est une VUE de la résidence, pas un écran à part : il partage
      l'en-tête, la barre d'onglets et l'adresse de cette page. -->
{#if onglet === 'carnet'}
	<CarnetEntretien />
{:else if onglet === 'fiche' && loading}
	<p style="color:var(--color-text-muted)">Chargement…</p>
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
			<h2 class="section-title">&#x1F3E2; Résidence : {copropriete.nom}</h2>
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
			<div class="card" style="padding:1.25rem">
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
					<div style="display:flex;gap:.5rem;justify-content:flex-end;margin-top:1rem">
						<button type="button" class="btn" on:click={() => (editing = false)}>Annuler</button>
						<button type="submit" class="btn btn-primary" disabled={saving}
							>{saving ? 'Enregistrement…' : 'Enregistrer'}</button
						>
					</div>
				</form>
			</div>
		{:else}
			<FicheResidence {copropriete} {batiments} />
		{/if}
	</section>

	<SectionRegles />

	<!-- ── Section : Plans ───────────────────────────────────────────────── -->
	<SectionDocuments
		titre="&#x1F5FA;️ Plans"
		documents={sortedPlans}
		erreur={ePlans}
		messageVide="Aucun plan ajouté."
		peutModifier={$isCS}
		urlTelechargement={(d) => documentsApi.downloadUrl(d.id)}
		dateDe={(d) => fmt(d.publie_le)}
		onAjouter={() => (showPlanForm = true)}
		onModifier={(d) => startEditDoc(d, 'plan')}
		onSupprimer={deletePlan}
	>
		<svelte:fragment slot="formulaire">
			{#if showPlanForm}
				<FormulaireDocument
					intitule="Ajouter un plan"
					bind:titre={newPlanTitre}
					placeholderTitre="ex : Plan de masse résidence"
					avecPerimetre
					bind:perimetre={newPlanPerimetre}
					bind:fichiers={newPlanFichiers}
					enregistrement={savingPlan}
					complet={!!newPlanTitre.trim() && !!newPlanFichiers?.length}
					on:annuler={() => (showPlanForm = false)}
					on:enregistrer={addPlan}
				>
					<label class="field" for="plan-description" slot="description">
						Description
						<textarea
							id="plan-description"
							bind:value={newPlanDescription}
							placeholder="Ce que ce plan montre, à quelle date il a été relevé…"
							rows="3"></textarea>
					</label>
				</FormulaireDocument>
			{/if}
			<!--  L'ÉDITION est un OBJET, monté par les trois sections sous condition
			      de leur mode. La recopier ici l'aurait fait diverger au premier
			      champ ajouté — trois en sont ajoutés dans ce même lot. -->
			{#if editingDocId !== null && editingDocMode === 'plan'}
				<FormulaireEditionDocument
					mode="plan"
					bind:titre={editingDocTitre}
					bind:annee={editingDocAnnee}
					bind:dateAg={editingDocDate}
					bind:perimetre={editingDocPerimetre}
					bind:description={editingDocDescription}
					enregistrement={savingDoc}
					on:annuler={() => (editingDocId = null)}
					on:enregistrer={saveEditDoc}
				/>
			{/if}
		</svelte:fragment>
		<svelte:fragment slot="badges" let:doc>
			<span class="badge badge-blue"
				>{doc.batiment_id ? batimentLabel(doc.batiment_id) : 'Copropriété'}</span
			>
		</svelte:fragment>
	</SectionDocuments>

	<!-- ── Section : Règlement de copropriété ────────────────────────────── -->
	<SectionDocuments
		titre="&#x1F4D6; Règlement de copropriété"
		documents={reglements}
		erreur={eReglements}
		messageVide="Aucun règlement ajouté."
		peutModifier={$isCS}
		urlTelechargement={(d) => documentsApi.downloadUrl(d.id)}
		dateDe={(d) => fmt(d.publie_le)}
		onAjouter={() => (showReglementForm = true)}
		onModifier={(d) => startEditDoc(d, 'reglement')}
		onSupprimer={deleteReglement}
	>
		<svelte:fragment slot="formulaire">
			{#if showReglementForm}
				<FormulaireDocument
					intitule="Ajouter un règlement"
					bind:titre={newReglementTitre}
					placeholderTitre="ex : Règlement de copropriété 2024"
					bind:fichiers={newReglementFichiers}
					enregistrement={savingReglement}
					complet={!!newReglementTitre.trim() && !!newReglementFichiers?.length}
					on:annuler={() => (showReglementForm = false)}
					on:enregistrer={addReglement}
				>
					<label class="field" for="reglement-description" slot="description">
						Description
						<textarea
							id="reglement-description"
							bind:value={newReglementDescription}
							placeholder="Ce qu'il remplace, ce qu'il ne couvre pas, où sont les annexes…"
							rows="3"></textarea>
					</label>
				</FormulaireDocument>
			{/if}
			<!--  L'ÉDITION est un OBJET, monté par les trois sections sous condition
			      de leur mode. La recopier ici l'aurait fait diverger au premier
			      champ ajouté — trois en sont ajoutés dans ce même lot. -->
			{#if editingDocId !== null && editingDocMode === 'reglement'}
				<FormulaireEditionDocument
					mode="reglement"
					bind:titre={editingDocTitre}
					bind:annee={editingDocAnnee}
					bind:dateAg={editingDocDate}
					bind:perimetre={editingDocPerimetre}
					bind:description={editingDocDescription}
					enregistrement={savingDoc}
					on:annuler={() => (editingDocId = null)}
					on:enregistrer={saveEditDoc}
				/>
			{/if}
		</svelte:fragment>
	</SectionDocuments>

	<!-- ── Section : Comptes-rendus d'AG ─────────────────────────────────── -->
	{#if !isLocataire}
		<SectionDocuments
			titre="&#x1F4CB; Comptes-rendus d'AG"
			documents={sortedCrAg}
			erreur={eCrAg}
			messageVide="Aucun compte-rendu ajouté."
			peutModifier={$isCS}
			urlTelechargement={(d) => documentsApi.downloadUrl(d.id)}
			onAjouter={() => (showCrAgForm = true)}
			onModifier={(d) => startEditDoc(d, 'ag')}
			onSupprimer={deleteCrAg}
		>
			<svelte:fragment slot="formulaire">
				{#if showCrAgForm}
					<FormulaireDocument
						intitule="Ajouter un CR d'AG"
						bind:titre={newCrAgTitre}
						placeholderTitre="ex : PV AG ordinaire 2025"
						avecPerimetre
						bind:perimetre={newCrAgPerimetre}
						bind:fichiers={newCrAgFichiers}
						enregistrement={savingCrAg}
						complet={!!newCrAgAnnee &&
							!!newCrAgDateAg &&
							!!newCrAgTitre.trim() &&
							!!newCrAgFichiers?.length}
						on:annuler={() => (showCrAgForm = false)}
						on:enregistrer={addCrAg}
					>
						<div class="paire" slot="specifiques">
							<label class="field" for="ag-annee">
								Année *
								<input
									id="ag-annee"
									type="number"
									bind:value={newCrAgAnnee}
									min="1900"
									max="2100"
									placeholder="2025"
								/>
							</label>
							<label class="field" for="ag-date">
								Date de l'AG *
								<input id="ag-date" type="date" bind:value={newCrAgDateAg} />
							</label>
						</div>
						<label class="field" for="ag-description" slot="description">
							Description
							<textarea
								id="ag-description"
								bind:value={newCrAgDescription}
								placeholder="Les points saillants, les résolutions votées, ce qui reste en suspens…"
								rows="3"></textarea>
						</label>
					</FormulaireDocument>
				{/if}
				<!--  L'ÉDITION est un OBJET, monté par les trois sections sous condition
				      de leur mode. La recopier ici l'aurait fait diverger au premier
				      champ ajouté — trois en sont ajoutés dans ce même lot. -->
				{#if editingDocId !== null && editingDocMode === 'ag'}
					<FormulaireEditionDocument
						mode="ag"
						bind:titre={editingDocTitre}
						bind:annee={editingDocAnnee}
						bind:dateAg={editingDocDate}
						bind:perimetre={editingDocPerimetre}
						bind:description={editingDocDescription}
						enregistrement={savingDoc}
						on:annuler={() => (editingDocId = null)}
						on:enregistrer={saveEditDoc}
					/>
				{/if}
			</svelte:fragment>
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
				{#if doc.perimetre_cible && !estPerimetreParDefaut(doc.perimetre_cible)}
					<span class="badge badge-purple">&#x1F539; {perimetreLabel(doc.perimetre_cible)}</span>
				{:else}
					<span class="badge badge-green">Copropriété</span>
				{/if}
			</svelte:fragment>
		</SectionDocuments>
	{/if}

	<!-- ── Section : Diagnostics et Contrôles Réglementaires ────────────── -->
	<!--  🔴 UN COMPOSANT depuis le 08/09/2026 (#852). C'était la dernière
	      section de cet écran à vivre à même la page — onze variables d'état,
	      six gestes, cent quatre-vingts lignes de balisage — alors que les
	      trois autres partagent `SectionDocuments` depuis #522. Le garde-fou
	      de modularité l'a refusée quand les formulaires y sont rentrés. -->
	{#if !isLocataire}
		<SectionDiagnostics bind:types={diagnosticTypes} erreur={eDiagnostics} peutModifier={$isCS} />
	{/if}
{:else}
	<div class="empty-state">
		<h3>Résidence non configurée</h3>
		<p>Les informations de la résidence ne sont pas encore disponibles.</p>
	</div>
{/if}

<style>
	/*  Deux champs courts qui vont ensemble — année et date d'AG. La règle
	    était écrite en `style=` sur la balise, dans les deux formulaires. */
	.paire {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.75rem;
	}
	/* ── Photo bannière ─────────────────────────────────────────── */
	.photo-figure {
		margin: 0 auto 2rem;
		max-width: 800px;
		text-align: center;
	}
	.photo-caption {
		font-size: 0.875rem;
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
		font-size: 0.9rem;
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
		font-size: 0.8rem;
		cursor: pointer;
		backdrop-filter: blur(4px);
		transition: background 0.15s;
	}
	.photo-change-btn:hover {
		background: rgba(0, 0, 0, 0.75);
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
