<script lang="ts">
	import { perimetreDefautListe } from '$lib/perimetres';
	import { confirmer, SUPPRESSION } from '$lib/confirmation';
	import ChoixPastilles from '$lib/components/ChoixPastilles.svelte';
	import CarteContrat from '$lib/components/CarteContrat.svelte';
	import ChampsPrestataire from '$lib/components/ChampsPrestataire.svelte';
	import CartePrestataire from '$lib/components/CartePrestataire.svelte';
	import OngletConsommations from '$lib/components/OngletConsommations.svelte';
	import FormulaireContrat from '$lib/components/FormulaireContrat.svelte';
	import EntetePage from '$lib/components/EntetePage.svelte';
	import BoutonNouveau from '$lib/components/BoutonNouveau.svelte';
	import FormulaireCreation from '$lib/components/FormulaireCreation.svelte';
	import { onMount } from 'svelte';
	import { prestataires as prestApi, documents as docsApi, ApiError } from '$lib/api';
	import { isCS } from '$lib/stores/auth';
	import { toast } from '$lib/components/Toast.svelte';
	import { getPageConfig, configStore, siteNomStore, defautsDePage } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';
	//  🔴 Le vocabulaire des prestataires vit dans `$lib/prestataires.ts`, pas
	//  ici. La table des équipements écrite dans cet écran recopiait
	//  `TypeEquipement` et en OUBLIAIT deux valeurs — `assurance` et `syndic`,
	//  précisément celles que la fiche de copropriété désigne (#553). Et les
	//  deux écrans de reporting, n'y ayant pas accès, affichaient la valeur
	//  brute : `chauffage_collectif`.
	import {
		EQUIPEMENTS as equipements,
		TYPES_PRESTATAIRE as typesPrestataire,
	} from '$lib/prestataires';
	import { minuitDuJour, typeEquipementDuContrat } from '$lib/reporting';
	import { relire, telephonesDe } from '$lib/utils';
	import { trackTabView } from '$lib/telemetry';
	import { goto } from '$app/navigation';
	import { cibleDuHash, revelerCible } from '$lib/deepLink';
	import BarreOnglets from '$lib/components/BarreOnglets.svelte';
	import { routeOnglet } from '$lib/routes-onglets';
	import PiedFormulaire from '$lib/components/PiedFormulaire.svelte';

	$: _pc = getPageConfig($configStore, 'prestataires', defautsDePage('prestataires'));
	$: _siteNom = $siteNomStore;

	let prestataires: any[] = [];
	let contrats: any[] = [];
	let notations: any[] = [];
	let loading = true;

	// ── Notation ──────────────────────────────────────────────────
	//  ⚠️ La notation SURVIT au retrait des prestations ponctuelles (#603) : elle
	//  se saisit depuis la fiche du prestataire, et son seul rattachement restant
	//  est le CONTRAT. Le rattachement à un devis part avec l'objet qui le portait.
	let showNotationForm: { prestataireId: number; contratId?: number } | null = null;
	let notationNote: number | null = null;
	let notationCommentaire = '';
	let notationSaving = false;

	function openNotationForm(prestataireId: number, contratId?: number) {
		showNotationForm = { prestataireId, contratId };
		notationNote = null;
		notationCommentaire = '';
	}

	async function saveNotation() {
		if (!showNotationForm || !notationNote || notationNote < 1 || notationNote > 5) {
			toast('error', 'Sélectionnez une note entre 1 et 5');
			return;
		}
		notationSaving = true;
		try {
			const n = await prestApi.createNotation({
				prestataire_id: showNotationForm.prestataireId,
				note: notationNote,
				commentaire: notationCommentaire.trim() || undefined,
				contrat_id: showNotationForm.contratId,
			});
			notations = [n, ...notations];
			showNotationForm = null;
			toast('success', 'Notation enregistrée');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			notationSaving = false;
		}
	}

	//  🔴 `avgNote` et `starsDisplay` sont parties dans `$lib/notations` (#807) :
	//  la liste des avis en avait besoin AUSSI, et c'est le moment exact où une
	//  fonction se recopie. Le badge de moyenne est rendu par
	//  `NotationsPrestataire` en mode `resume` — la note et les avis qui la
	//  composent au même endroit.

	// ── Onglets (3) ────────────────────────────────────────────────
	//  La liste, l'ordre ET l'adresse de chaque onglet vivent dans la table
	//  (`$lib/pages.ts`). Elle était écrite ici, et la table n'en connaissait que
	//  DEUX sur trois : « Contrats » n'était donc ni renommable ni descriptible
	//  depuis l'administration, alors que les quatre autres pages du site le sont.
	//
	//  ⚠️ `'prestations'` et `'visites'` ont disparu (#603), comme `?onglet=` lui-même
	//  (05/09/2026). Une ancienne adresse qui les nomme encore est redirigée vers la
	//  page par `resoudreOnglet`, jamais vers un onglet inventé.
	export let data: { onglet: string };
	$: onglet = data.onglet;
	$: trackTabView(onglet);

	// Expand prestataire cards
	let expandedPrests = new Set<number>();
	// Expand contrat rows inline
	let expandedContrats = new Set<number>();
	// Expand notes dans un contrat

	// ── Prestataire form ──────────────────────────────────────────
	let showPrestForm = false;
	let editPrestId: number | null = null;
	let prestForm = { nom: '', specialite: '', type_prestataire: 'ponctuel', email: '' };
	let prestContacts: {
		telephone: string;
		prenom: string;
		nom: string;
		fonction: string;
		email: string;
	}[] = [{ telephone: '', prenom: '', nom: '', fonction: '', email: '' }];
	let submitting = false;

	// ── Contrat form ──────────────────────────────────────────────
	//  Deux états, deux variables qui disent ce qu'elles sont. L'ancien
	//  `contratFormPrestId: number | null` ne valait que `-1` ou `null` : un
	//  booléen déguisé en identifiant, et c'est ce déguisement qui a rendu
	//  invisible un `{#if}` toujours faux — voir `FormulaireContrat`.
	let contratFormOuvert = false;
	let editContratId: number | null = null;

	let contratForm = {
		copropriete_id: 1,
		//  Le PÉRIMÈTRE remplace `batiment_id`, qui n'était rempli par aucun
		//  champ (10/09/2026). Le serveur en dérive le bâtiment.
		perimetre_cible: perimetreDefautListe(),
		prestataire_id: '',
		type_equipement: 'autre',
		libelle: '',
		numero_contrat: '',
		date_debut: new Date().toISOString().slice(0, 10),
		duree_initiale_valeur: '',
		duree_initiale_unite: 'mois',
		frequence_type: '',
		frequence_valeur: '',
		prochaine_visite: '',
		notes: '',
	};

	// ── Documents ─────────────────────────────────────────────────
	let contratDocsMap: Record<number, any[]> = {};
	//  ⚠️ `contratUploadFile`, `contratUploadTitre`, `uploadingDoc` et
	//  `uploadInputKey` ont disparu avec le bloc dupliqué (#370). Ils étaient
	//  UNIQUES pour toute la page alors que le bloc était affiché à deux endroits :
	//  choisir un fichier dans le formulaire d'édition le faisait apparaître dans
	//  la carte dépliée. Chaque `AjoutDocumentContrat` porte désormais le sien.

	let filtreEquipement = '';
	let filtreType = '';

	$: filteredPrests = prestataires.filter(
		(p) =>
			(!filtreEquipement || p.specialite === filtreEquipement) &&
			(!filtreType || p.type_prestataire === filtreType),
	);
	$: compactPrests = filteredPrests.length > 7;

	// ── Échéances des contrats ────────────────────────────────────
	//  🔴 L'onglet « Visites » lisait ces mêmes contrats dans un écran à part
	//  (#603). Une visite n'est pas un objet : c'est la PROCHAINE ÉCHÉANCE d'un
	//  contrat, et elle avait deux définitions qui ne donnaient pas la même
	//  réponse — ici `prochaine_visite`, une date posée à la main ; dans le
	//  calendrier, `frequence_type` réparti sur les mois de l'exercice. Le
	//  décompte reste, l'écran séparé part.
	//
	//  ⚠️ Minuit, pas l'instant ; `contrats` cité pour relire (`utils.relire`).
	$: minuit = relire(contrats, minuitDuJour);
	$: contratEnRetard = (c: any) => !!c.prochaine_visite && new Date(c.prochaine_visite) < minuit;
	$: echeancesEnRetard = contrats.filter(contratEnRetard);
	$: echeancesAVenir = contrats.filter((c) => c.prochaine_visite && !contratEnRetard(c));
	$: contratsSansEcheance = contrats.filter((c) => !c.prochaine_visite);

	/**  Les contrats d'un groupe, la prochaine échéance d'abord.
	 *
	 *   ⚠️ Sans échéance = en FIN de liste, jamais en tête : `null` se compare mal
	 *   et un tri naïf les aurait remontés devant les retards. */
	function parEcheance(liste: any[]): any[] {
		return [...liste].sort((a, b) => {
			if (!a.prochaine_visite && !b.prochaine_visite) return 0;
			if (!a.prochaine_visite) return 1;
			if (!b.prochaine_visite) return -1;
			return a.prochaine_visite < b.prochaine_visite ? -1 : 1;
		});
	}

	//  ⚠️ Ces deux-là servent l'onglet PRESTATAIRES, pas les consommations : elles
	//  vivaient dans le bloc « Consommations » par accident de rangement, et
	//  l'extraction les a fait remonter. Une fonction se range avec ce qu'elle
	//  sert, pas avec ce qui l'entoure.
	function contratsForPrest(prestId: number): any[] {
		return contrats.filter((c) => c.prestataire_id === prestId);
	}

	function typeLabel(v: string) {
		return typesPrestataire.find((t) => t.val === v)?.label ?? v;
	}

	//  L'onglet Consommations possède son formulaire ; la page n'en garde que
	//  l'ouverture et le libellé, pour le bouton de l'en-tête (R1).
	let showReleveForm = false;
	let libelleReleve = 'Nouveau relevé';

	// ── Toggle expand ──────────────────────────────────────────────
	function togglePrest(id: number) {
		if (expandedPrests.has(id)) expandedPrests.delete(id);
		else {
			expandedPrests.clear();
			expandedPrests.add(id);
			expandedContrats.clear();
			expandedContrats = expandedContrats;
		}
		expandedPrests = expandedPrests;
	}

	function toggleContrat(id: number) {
		if (expandedContrats.has(id)) expandedContrats.delete(id);
		else {
			expandedContrats.clear();
			expandedContrats.add(id);
		}
		expandedContrats = expandedContrats;
	}

	function nextVisitForPrest(prestId: number): string | null {
		const dates = contrats
			.filter((c) => c.prestataire_id === prestId && c.prochaine_visite)
			.map((c) => c.prochaine_visite as string)
			.sort();
		return dates[0] ?? null;
	}

	onMount(async () => {
		try {
			[prestataires, contrats, notations] = await Promise.all([
				prestApi.list(),
				prestApi.contrats(),
				prestApi.notations(),
			]);
		} catch {
			toast('error', 'Erreur de chargement');
		} finally {
			loading = false;
		}

		if (contrats.length > 0) {
			const results = await Promise.allSettled(
				contrats.map((c) =>
					docsApi.list(undefined, c.id).then((docs: any[]) => ({ id: c.id, docs })),
				),
			);
			const map: Record<number, any[]> = {};
			for (const r of results) {
				if (r.status === 'fulfilled') map[r.value.id] = r.value.docs;
			}
			contratDocsMap = map;
		}

		// Liens profonds : `?onglet=` pour la vue, `#presta-<id>` pour l'élément.
		// Cette page a QUATRE onglets et s'ouvre sur « Contrats » : une fiche
		// prestataire visée sans onglet restait invisible, l'ancre ne désignant aucun
		// élément rendu (`/prestataires#presta-23`, signalé le 28/07/2026).
		// L'ancre décide de la ROUTE : elle est plus précise que la vue demandée.
		//
		// ⚠️ L'ancre `#dv-<id>` d'une prestation ponctuelle est partie avec elle
		// (#603). Un lien qui la porte encore ne désigne plus rien : la page
		// s'ouvre sur son défaut, sans erreur — `cibleDuHash` n'est simplement
		// plus interrogé pour ce préfixe.
		const idPresta = cibleDuHash('presta');
		if (idPresta !== null) {
			expandedPrests = new Set([...expandedPrests, idPresta]);
			if (onglet !== 'prestataires') {
				goto(`${routeOnglet('prestataires', 'prestataires')}#presta-${idPresta}`);
				return;
			}
			revelerCible(`presta-${idPresta}`);
		}
	});

	function resetPrestForm() {
		prestForm = { nom: '', specialite: '', type_prestataire: 'ponctuel', email: '' };
		prestContacts = [{ telephone: '', prenom: '', nom: '', fonction: '', email: '' }];
		editPrestId = null;
	}
	function startEditPrest(p: any) {
		prestForm = {
			nom: p.nom,
			specialite: p.specialite ?? '',
			type_prestataire: p.type_prestataire ?? 'ponctuel',
			email: p.email ?? '',
		};
		if (p.contacts && p.contacts.length > 0) {
			prestContacts = p.contacts.map((c: any) => ({
				telephone: c.telephone ?? '',
				prenom: c.prenom ?? '',
				nom: c.nom ?? '',
				fonction: c.fonction ?? '',
				email: c.email ?? '',
			}));
		} else {
			prestContacts = p.telephone
				? p.telephone
						.split(',')
						.filter((t: string) => t.trim())
						.map((t: string) => ({
							telephone: t.trim(),
							prenom: '',
							nom: '',
							fonction: '',
							email: '',
						}))
				: [{ telephone: '', prenom: '', nom: '', fonction: '', email: '' }];
		}
		if (prestContacts.length === 0)
			prestContacts = [{ telephone: '', prenom: '', nom: '', fonction: '', email: '' }];
		//  🔴 On n'ouvre PAS le formulaire de tête, et on ne fait PAS défiler : la
		//  correction s'ouvre dans la carte du prestataire, là où est le crayon
		//  (`CartePrestataire`). Ce `scrollTo` était la cause exacte du symptôme
		//  signalé le 11/09/2026 — la page remontait, et l'objet corrigé quittait
		//  sa place sous les yeux.
		editPrestId = p.id;
	}

	async function savePrest() {
		if (!prestForm.nom || !prestForm.specialite) {
			toast('error', 'Nom et spécialité obligatoires');
			return;
		}
		const contacts = prestContacts.filter((c) => c.telephone.trim());
		const telephone = contacts.map((c) => c.telephone.trim()).join(',') || null;
		submitting = true;
		try {
			if (editPrestId) {
				await prestApi.update(editPrestId, { ...prestForm, telephone, contacts });
			} else {
				await prestApi.create({ ...prestForm, telephone, contacts });
			}
			prestataires = await prestApi.list();
			showPrestForm = false;
			resetPrestForm();
			toast('success', editPrestId ? 'Prestataire modifié' : 'Prestataire ajouté');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			submitting = false;
		}
	}

	async function deletePrest(id: number) {
		if (!(await confirmer('Archiver ce prestataire ?'))) return;
		try {
			await prestApi.delete(id);
			prestataires = prestataires.filter((p) => p.id !== id);
			toast('success', 'Archivé');
		} catch {
			toast('error', 'Erreur');
		}
	}

	function resetContratForm() {
		contratForm = {
			copropriete_id: 1,
			perimetre_cible: perimetreDefautListe(),
			prestataire_id: '',
			type_equipement: 'autre',
			libelle: '',
			numero_contrat: '',
			date_debut: new Date().toISOString().slice(0, 10),
			duree_initiale_valeur: '',
			duree_initiale_unite: 'mois',
			frequence_type: '',
			frequence_valeur: '',
			prochaine_visite: '',
			notes: '',
		};
		editContratId = null;
	}

	function openAddContrat(prestId?: number) {
		resetContratForm();
		if (prestId) {
			contratForm.prestataire_id = String(prestId);
			const p = prestataires.find((pr) => pr.id === prestId);
			if (p?.specialite && p.specialite !== 'autre') contratForm.type_equipement = p.specialite;
		}
		contratFormOuvert = true;
		editContratId = null;
	}

	//  Ferme les deux enveloppes — une seule est ouverte à la fois.
	function closeContratForm() {
		contratFormOuvert = false;
		editContratId = null;
		resetContratForm();
	}

	/**  🔴 Le geste ✨ ouvre la CORRECTION, il n'en invente pas une seconde.
	 *
	 *   La proposition remplit le champ « Synthèse » du formulaire d'édition —
	 *   celui du crayon, le même composant, le même bouton Enregistrer. Écrire un
	 *   cadre à part aurait donné deux formulaires pour un seul objet, et deux
	 *   endroits où la règle d'enregistrement aurait divergé.
	 *
	 *   ⚠️ RIEN n'est enregistré : « Annuler » referme, et le contrat garde sa
	 *   synthèse d'origine. C'est la décision 03 du 11/09/2026 — le risque devient
	 *   nul, et améliorer une synthèse bâclée reste possible. */
	let syntheseEnCoursId: number | null = null;

	async function synthetiserContrat(c: any) {
		syntheseEnCoursId = c.id;
		try {
			const { synthese } = await prestApi.synthetiserContrat(c.id);
			startEditContrat({ ...c, notes: synthese });
			toast('info', 'Synthèse proposée — relisez-la avant d’enregistrer');
		} catch (e) {
			//  ⚠️ Le message vient du serveur : il dit POURQUOI (clé refusée, délai
			//  dépassé, quota). Un « Erreur » générique laisserait chercher.
			toast('error', e instanceof ApiError ? e.message : 'La rédaction n’a pas abouti');
		} finally {
			syntheseEnCoursId = null;
		}
	}

	function startEditContrat(c: any) {
		contratForm = {
			copropriete_id: c.copropriete_id,
			perimetre_cible: c.perimetre_cible?.length ? c.perimetre_cible : perimetreDefautListe(),
			prestataire_id: String(c.prestataire_id ?? ''),
			type_equipement: typeEquipementDuContrat(c, prestataires),
			libelle: c.libelle,
			numero_contrat: c.numero_contrat ?? '',
			date_debut: c.date_debut,
			duree_initiale_valeur: c.duree_initiale_valeur ?? '',
			duree_initiale_unite: c.duree_initiale_unite ?? 'mois',
			frequence_type: c.frequence_type ?? '',
			frequence_valeur: c.frequence_valeur ?? '',
			prochaine_visite: c.prochaine_visite ?? '',
			notes: c.notes ?? '',
		};
		editContratId = c.id;
		contratFormOuvert = false;
	}

	async function saveContrat() {
		if (!contratForm.libelle || !contratForm.prestataire_id) {
			toast('error', 'Libellé et prestataire obligatoires');
			return;
		}
		submitting = true;
		//  La règle vit dans `reporting.ts` — elle était écrite ici, dans le
		//  groupement des cartes et dans le chargement du formulaire, avec trois
		//  résultats différents sur le même contrat (29/08/2026).
		const resolvedType = typeEquipementDuContrat(
			{ ...contratForm, prestataire_id: Number(contratForm.prestataire_id) },
			prestataires,
		);
		const payload = {
			...contratForm,
			type_equipement: resolvedType,
			prestataire_id: Number(contratForm.prestataire_id),
			duree_initiale_valeur: contratForm.duree_initiale_valeur
				? Number(contratForm.duree_initiale_valeur)
				: null,
			duree_initiale_unite: contratForm.duree_initiale_valeur
				? contratForm.duree_initiale_unite
				: null,
			frequence_type: contratForm.frequence_type || null,
			frequence_valeur: contratForm.frequence_valeur ? Number(contratForm.frequence_valeur) : null,
			prochaine_visite: contratForm.prochaine_visite || null,
		};
		//  🔴 Lu AVANT la fermeture, qui remet `editContratId` à `null`. Le message
		//  le lisait après : une modification annonçait donc « Contrat créé ».
		const etaitUneModification = editContratId !== null;
		try {
			if (editContratId) {
				await prestApi.updateContrat(editContratId, payload);
			} else {
				await prestApi.createContrat(payload);
			}
			contrats = await prestApi.contrats();
			closeContratForm();
			toast('success', etaitUneModification ? 'Contrat modifié' : 'Contrat créé');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			submitting = false;
		}
	}

	//  L'ENVOI vit dans `AjoutDocumentContrat` ; il ne reste ici que le rechargement
	//  de la liste, qui appartient à la page puisque c'est elle qui l'affiche.
	async function rechargerDocs(contratId: number) {
		contratDocsMap = { ...contratDocsMap, [contratId]: await docsApi.list(undefined, contratId) };
	}

	async function deleteDoc(contratId: number, docId: number) {
		if (!(await confirmer(SUPPRESSION('Ce document')))) return;
		try {
			await docsApi.delete(docId);
			contratDocsMap = { ...contratDocsMap, [contratId]: await docsApi.list(undefined, contratId) };
			toast('success', 'Document supprimé');
		} catch {
			toast('error', 'Erreur');
		}
	}

	async function deleteContrat(id: number) {
		if (!(await confirmer('Archiver ce contrat ?'))) return;
		try {
			await prestApi.deleteContrat(id);
			contrats = contrats.filter((c) => c.id !== id);
			toast('success', 'Archivé');
		} catch {
			toast('error', 'Erreur');
		}
	}
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<!--  Bascule « + … » ⇆ « ✕ Annuler » portée par `BoutonNouveau` (voir son
      en-tête) ; `alignerSaisie` cale le bouton sur la boîte de 720 px. -->
<EntetePage
	titre={_pc.titre}
	icone={_pc.icone || 'hard-hat'}
	alignerSaisie={showPrestForm || contratFormOuvert || showReleveForm}
>
	{#if $isCS}
		{#if onglet === 'prestataires'}
			<BoutonNouveau
				ouvert={showPrestForm}
				libelle="Nouveau prestataire"
				on:basculer={() => {
					showPrestForm = !showPrestForm;
					//  Ouvrir la création referme une correction en cours : deux boîtes
					//  ouvertes en même temps, c'est le défaut des contrats du 10/09.
					if (showPrestForm) editPrestId = null;
					if (!showPrestForm) resetPrestForm();
				}}
			/>
		{:else if onglet === 'contrats'}
			<BoutonNouveau
				ouvert={contratFormOuvert}
				libelle="Nouveau contrat"
				on:basculer={() => {
					if (contratFormOuvert) closeContratForm();
					else openAddContrat();
				}}
			/>
		{:else if onglet === 'consommations'}
			<BoutonNouveau
				ouvert={showReleveForm}
				libelle={libelleReleve}
				on:basculer={() => (showReleveForm = !showReleveForm)}
			/>
		{/if}
	{/if}
</EntetePage>
<div class="page-subtitle">{@html safeHtml(_pc.descriptif)}</div>

<BarreOnglets pageId="prestataires" actif={onglet} />

{#if loading}
	<p style="color:var(--color-text-muted)">Chargement…</p>

	<!-- ══════════════════════════════════════════════════════════════ -->
	<!-- ONGLET 3 : CONTRATS                                          -->
	<!-- ══════════════════════════════════════════════════════════════ -->
{:else if onglet === 'contrats'}
	<!--  🔴 CE BLOC NE SERT QU'À LA CRÉATION (corrigé le 10/09/2026).

	      Il gouvernait les deux gestes (`contratFormOuvert || editContratId`) tant
	      que la correction se rendait ici. Elle a déménagé DANS la carte le matin
	      même — et ce bloc-ci est resté ouvert sur la même condition : deux boîtes
	      « Modifier le contrat » apparaissaient à l'écran en même temps, celle-ci
	      en tête de liste et celle de la carte plus bas, et sa `cle` ramenait la
	      page en haut.

	      ⚠️ C'est la régression de #356 dans sa forme la plus banale : on DÉPLACE
	      un rendu et on oublie de retirer l'ancien. `lint:geste-edition` ne
	      pouvait pas la voir — sa règle B compte les rendus d'un formulaire
	      FICHIER PAR FICHIER, et l'extraction venait justement d'en mettre un dans
	      un second fichier. Un contrôle dont la portée est le fichier devient
	      aveugle le jour où l'on découpe.

	      La création reste ici, en tête de liste : elle ne corrige aucun objet,
	      elle n'a donc pas de place à prendre — et pas de `cle` non plus, le geste
	      qui l'ouvre étant juste au-dessus. -->
	{#if contratFormOuvert}
		<FormulaireCreation titre="Nouveau contrat">
			<FormulaireContrat
				bind:contratForm
				{prestataires}
				{equipements}
				contratId={null}
				documents={[]}
				onSupprimer={deleteDoc}
				onAjoute={rechargerDocs}
				{submitting}
				onAnnuler={closeContratForm}
				onEnregistrer={saveContrat}
			/>
		</FormulaireCreation>
	{/if}

	<!--  Synthèse — les trois décomptes viennent de l'onglet « Visites » retiré
	      (#603). Ils portent sur les MÊMES contrats qu'il lisait ; ils sont
	      seulement rendus là où vivent les contrats. -->
	<div class="contrats-summary">
		<span class="contrats-summary-count"
			>{contrats.length} contrat{contrats.length !== 1 ? 's' : ''} actif{contrats.length !== 1
				? 's'
				: ''}</span
		>
		{#if echeancesEnRetard.length > 0}
			<span class="badge echeance-badge echeance-badge--retard"
				>⚠️ {echeancesEnRetard.length} visite{echeancesEnRetard.length > 1 ? 's' : ''} en retard</span
			>
		{/if}
		{#if echeancesAVenir.length > 0}
			<span class="badge echeance-badge echeance-badge--ok">🗓 {echeancesAVenir.length} à venir</span
			>
		{/if}
		{#if contratsSansEcheance.length > 0}
			<span class="badge echeance-badge">{contratsSansEcheance.length} sans échéance</span>
		{/if}
	</div>

	<!-- Groupé par spécialité du prestataire -->
	{#if contrats.length === 0}
		<div class="empty-state card">
			<h3>Aucun contrat</h3>
			<p>Ajoutez le premier contrat via le bouton ci-dessus.</p>
		</div>
	{:else}
		{#each equipements.filter( (e) => contrats.some((c) => typeEquipementDuContrat(c, prestataires) === e.val) ) as specGroup (specGroup.val)}
			<div class="type-section-header">
				<span class="type-section-label">{specGroup.label}</span>
			</div>
			{#each parEcheance(contrats.filter((c) => typeEquipementDuContrat(c, prestataires) === specGroup.val)) as c (c.id)}
				{@const contrat = c}
				{@const prest = prestataires.find((p) => p.id === c.prestataire_id)}
				{@const contratExpanded = expandedContrats.has(c.id)}
				{@const enRetard = contratEnRetard(c)}
				<CarteContrat
					{contrat}
					{prest}
					expanded={contratExpanded}
					{enRetard}
					documents={contratDocsMap[contrat.id] ?? []}
					peutModifier={$isCS}
					{editContratId}
					bind:contratForm
					{prestataires}
					{equipements}
					{submitting}
					onBasculer={toggleContrat}
					onModifier={startEditContrat}
					onSynthetiser={synthetiserContrat}
					{syntheseEnCoursId}
					onArchiver={deleteContrat}
					onSupprimerDoc={deleteDoc}
					onAjouteDoc={rechargerDocs}
					onAnnuler={closeContratForm}
					onEnregistrer={saveContrat}
					onNoter={openNotationForm}
					noteEnCours={showNotationForm?.contratId === c.id}
					bind:noteValeur={notationNote}
					bind:noteCommentaire={notationCommentaire}
					noteSaving={notationSaving}
					onAnnulerNote={() => (showNotationForm = null)}
					onEnregistrerNote={saveNotation}
				/>
			{/each}
		{/each}
	{/if}

	<!-- ══════════════════════════════════════════════════════════════ -->
	<!-- ONGLET 4 : PRESTATAIRES (annuaire)                           -->
	<!-- ══════════════════════════════════════════════════════════════ -->
{:else if onglet === 'prestataires'}
	<!--  Deux rangées et le champ « Type » du formulaire ci-dessous : UN motif,
	      porté par `ChoixPastilles` (#491). Il était écrit deux fois ici, à trois
	      mots près — la duplication la plus discrète, celle qu'aucun contrôle
	      inter-fichiers ne voit — et le composant qui l'a absorbée annonçait
	      lui-même qu'une troisième copie viendrait. Elle est venue le lendemain,
	      dans le formulaire : c'est ce qui a fait généraliser le composant.
	      `avecDetail` sur les types seuls : leur description vivait dans un `title`,
	      donc invisible au tactile. Les douze équipements n'en portent pas. -->
	<ChoixPastilles
		options={typesPrestataire}
		bind:valeur={filtreType}
		avecDetail
		libelle="Filtrer par type de prestataire"
	/>
	<ChoixPastilles
		options={equipements}
		bind:valeur={filtreEquipement}
		tous="Tous équipements"
		libelle="Filtrer par équipement"
	/>

	<!--  🔴 La CRÉATION seulement. Corriger un prestataire ouvre le formulaire DANS
	      sa carte, à la place de son corps — le motif des tickets, appliqué aux
	      contrats le 10/09/2026 et signalé ici le 11/09 : le crayon est dans la
	      carte, la boîte s'ouvrait en tête de liste.
	      Aucune `cle` : rien n'a bougé, il n'y a rien à ramener à l'écran. -->
	{#if $isCS && showPrestForm}
		<FormulaireCreation titre="Nouveau prestataire">
			<form on:submit|preventDefault={savePrest}>
				<ChampsPrestataire
					bind:prestForm
					bind:prestContacts
					{typesPrestataire}
					{equipements}
					etat="creation"
				/>
				<PiedFormulaire
					enCours={submitting}
					on:annule={() => {
						showPrestForm = false;
						resetPrestForm();
					}}
				/>
			</form>
		</FormulaireCreation>
	{/if}

	{#if filteredPrests.length === 0}
		<div class="empty-state card">
			<h3>Aucun prestataire{filtreEquipement || filtreType ? ' pour ces critères' : ''}</h3>
		</div>
	{:else}
		{#each typesPrestataire.filter( (t) => filteredPrests.some((p) => p.type_prestataire === t.val) ) as typeGroup (typeGroup.val)}
			{#if !filtreType}
				<div class="type-section-header">
					<span class="type-section-label">{typeGroup.label}</span>
					<span class="type-section-desc">{typeGroup.desc}</span>
				</div>
			{/if}
			{#each filteredPrests.filter((p) => p.type_prestataire === typeGroup.val) as p (p.id)}
				{@const expanded = expandedPrests.has(p.id)}
				{@const cs = contratsForPrest(p.id)}
				{@const nextVisit = nextVisitForPrest(p.id)}
				<CartePrestataire
					{p}
					{cs}
					{nextVisit}
					notations={notations.filter((n) => n.prestataire_id === p.id)}
					{expanded}
					{compactPrests}
					peutModifier={$isCS}
					{telephonesDe}
					{typeLabel}
					{editPrestId}
					bind:prestForm
					bind:prestContacts
					{typesPrestataire}
					{equipements}
					{submitting}
					onBasculer={togglePrest}
					onModifier={startEditPrest}
					onArchiver={deletePrest}
					onAnnuler={() => {
						showPrestForm = false;
						resetPrestForm();
					}}
					onEnregistrer={savePrest}
					on:supprimee={(e) => (notations = notations.filter((n) => n.id !== e.detail))}
				/>
			{/each}
		{/each}
	{/if}

	<!-- ══════════════════════════════════════════════════════════════ -->
	<!-- ONGLET 5 : CONSOMMATIONS (inchangé)                          -->
	<!-- ══════════════════════════════════════════════════════════════ -->
{:else if onglet === 'consommations'}
	<OngletConsommations bind:showReleveForm bind:libelleBouton={libelleReleve} {prestataires} />
{/if}

<style>
	/* ── Sous-vue toggle ── */

	/*  Défilement horizontal : variante NOMMÉE `.filters--defilante` (app.css,
	    #446), lisible dans le balisage. Marge basse .75rem → 1.25rem, la norme. */

	/* Section type header */
	.type-section-header {
		display: flex;
		align-items: baseline;
		gap: 0.5rem;
		margin: 1.25rem 0 0.5rem;
		padding-bottom: 0.3rem;
		border-bottom: 2px solid var(--color-border);
	}
	.type-section-header:first-child {
		margin-top: 0;
	}
	.type-section-label {
		font-size: 1rem;
		font-weight: 700;
	}
	.type-section-desc {
		font-size: 0.82rem;
		color: var(--color-text-muted);
		font-style: italic;
	}

	/* Carte prestataire expansible */
	/*  ⚠️ `overflow: hidden` retiré des trois cartes : il rognait l'infobulle des
	    boutons, posée sous eux donc hors de la carte (#598). */
	/*  `.carte-liste` depuis le 28/08/2026 (#598) : la carte combinait `.card`
	    et en ANNULAIT le remplissage — ce que la norme donne sans annuler. */

	/* ── Visites ── */

	/* ── Contrats summary ── */
	.contrats-summary {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.contrats-summary-count {
		font-size: 0.85rem;
		color: var(--color-text-muted);
	}

	/*  Les trois décomptes d'échéance, repris de l'onglet « Visites » retiré. */
	.echeance-badge {
		font-size: 0.78rem;
	}
	.echeance-badge--retard {
		color: var(--color-danger);
		border-color: var(--color-danger);
	}
	.echeance-badge--ok {
		color: var(--color-primary);
		border-color: var(--color-primary);
	}

	/*  🔴 Ce commentaire n'était PAS FERMÉ, et il ne l'était déjà pas dans `main`
	    (trouvé le 11/09/2026 en extrayant la carte). Il commençait à « Contrat
	    expansible », s'interrompait en milieu de phrase, et c'est la marque de
	    fermeture du commentaire SUIVANT — celui de `.form-grid`, sept lignes plus
	    bas — qui le refermait. Tout ce qui était entre les deux était donc du CSS
	    mangé par un commentaire : un sélecteur `.contrats-summary,` en attente d'un
	    second nom qui n'est jamais venu.

	    Retirer `.form-grid` (parti avec son balisage) a rendu le défaut visible en
	    cassant la compilation. Aucun contrôle ne l'avait vu : `lint:css-orphelin`
	    lit les sélecteurs QUI COMPILENT, et celui-ci n'en était pas un — il était
	    du texte. Les débris sont supprimés ici ; `.contrats-summary` garde sa
	    définition complète plus haut. */
</style>
