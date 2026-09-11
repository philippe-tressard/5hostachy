<script lang="ts">
	import { nomAffiche } from '$lib/noms';
	import { perimetreDefautListe } from '$lib/perimetres';
	import { confirmer, SUPPRESSION } from '$lib/confirmation';
	import ChoixPastilles from '$lib/components/ChoixPastilles.svelte';
	import CarteContrat from '$lib/components/CarteContrat.svelte';
	import OngletConsommations from '$lib/components/OngletConsommations.svelte';
	import FormulaireContrat from '$lib/components/FormulaireContrat.svelte';
	import Modale from '$lib/components/Modale.svelte';
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
		equipLabel,
	} from '$lib/prestataires';
	import { fmtDateShort } from '$lib/date';
	import { minuitDuJour, typeEquipementDuContrat } from '$lib/reporting';
	import { relire, telephonesDe } from '$lib/utils';
	import { trackTabView } from '$lib/telemetry';
	import { goto } from '$app/navigation';
	import { cibleDuHash, revelerCible } from '$lib/deepLink';
	import BarreOnglets from '$lib/components/BarreOnglets.svelte';
	import BoutonLien from '$lib/components/BoutonLien.svelte';
	import NotationsPrestataire from '$lib/components/NotationsPrestataire.svelte';
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
	let notationNote = 0;
	let notationCommentaire = '';
	let notationSaving = false;
	let notationHover = 0;

	function openNotationForm(prestataireId: number, contratId?: number) {
		showNotationForm = { prestataireId, contratId };
		notationNote = 0;
		notationCommentaire = '';
	}

	async function saveNotation() {
		if (!showNotationForm || notationNote < 1 || notationNote > 5) {
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
		editPrestId = p.id;
		showPrestForm = true;
		window.scrollTo({ top: 0, behavior: 'smooth' });
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

	{#if $isCS && showPrestForm}
		<FormulaireCreation
			cle={editPrestId}
			titre={editPrestId ? 'Modifier le prestataire' : 'Nouveau prestataire'}
		>
			<form on:submit|preventDefault={savePrest}>
				<div>
					<div class="form-grid">
						<label class="field">Nom *<input bind:value={prestForm.nom} required /></label>
						<!--  🔴 Six entrées portant chacune une description : c'est le cas
						      qui a fait donner un sous-texte à `Pastille` (#491, seuil arbitré
						      à 6). Le FILTRE de cette même liste la montre depuis le 29/08 —
						      le formulaire, lui, gardait un `<select>` où la description ne
						      s'affichait nulle part. Deux rendus du même objet, et c'est
						      celui qui sert à CHOISIR qui perdait ce qui aide à choisir.
						      `champ-large` : dix pastilles à sous-texte dans une colonne de
						      grille s'empileraient une par ligne (`ux-patterns` §9 bis). -->
						<ChoixPastilles
							options={typesPrestataire}
							bind:valeur={prestForm.type_prestataire}
							tous={false}
							libelle="Type"
							libelleVisible
							requis
							avecDetail
						/>
						<label class="field"
							>Spécialité *
							<select bind:value={prestForm.specialite} required>
								<option value="">— Sélectionner —</option>
								{#each equipements as e (e.val)}<option value={e.val}>{e.label}</option>{/each}
							</select>
						</label>
						<label class="field">Email<input type="email" bind:value={prestForm.email} /></label>
					</div>
					<div style="margin-top:.75rem">
						<div style="font-size:.85rem;font-weight:600;margin-bottom:.35rem">
							Contact{prestContacts.length > 1 ? 's' : ''}
						</div>
						{#each prestContacts as _contact, i (_contact)}
							<div
								style="border:1px solid var(--color-border);border-radius:6px;padding:.6rem;margin-bottom:.5rem;background:var(--color-bg)"
							>
								<div style="display:flex;gap:.4rem;flex-wrap:wrap;margin-bottom:.35rem">
									<input
										style="flex:2;min-width:140px"
										bind:value={prestContacts[i].telephone}
										placeholder="Téléphone *"
									/>
									<input
										style="flex:1;min-width:100px"
										bind:value={prestContacts[i].prenom}
										placeholder="Prénom"
									/>
									<input
										style="flex:1;min-width:100px"
										bind:value={prestContacts[i].nom}
										placeholder="Nom"
									/>
								</div>
								<div style="display:flex;gap:.4rem;flex-wrap:wrap;align-items:center">
									<input
										style="flex:1;min-width:120px"
										bind:value={prestContacts[i].fonction}
										placeholder="Fonction"
									/>
									<input
										style="flex:1;min-width:140px"
										type="email"
										bind:value={prestContacts[i].email}
										placeholder="Email"
									/>
									{#if prestContacts.length > 1}
										<button
											type="button"
											class="btn btn-sm btn-outline"
											style="color:#dc2626;border-color:#dc2626;flex-shrink:0"
											on:click={() => (prestContacts = prestContacts.filter((_, j) => j !== i))}
											>−</button
										>
									{/if}
								</div>
							</div>
						{/each}
						<button
							type="button"
							class="btn btn-sm btn-outline"
							on:click={() =>
								(prestContacts = [
									...prestContacts,
									{ telephone: '', prenom: '', nom: '', fonction: '', email: '' },
								])}>+ Nouveau contact</button
						>
					</div>
				</div>
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
				<div class="carte-liste" class:expanded id="presta-{p.id}">
					<div
						class="prest-header"
						role="button"
						tabindex="0"
						on:click={() => togglePrest(p.id)}
						on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && togglePrest(p.id)}
					>
						<div class="prest-main">
							<strong class="prest-nom">{p.nom}</strong>
							<span class="badge badge-type" style="margin-left:.5rem"
								>{typeLabel(p.type_prestataire)}</span
							>
							<span class="badge badge-blue" style="margin-left:.25rem"
								>{equipLabel(p.specialite)}</span
							>
							<NotationsPrestataire
								resume
								notations={notations.filter((n) => n.prestataire_id === p.id)}
							/>
						</div>
						{#if !compactPrests || expanded}
							<div class="prest-contacts">
								{#if p.contacts && p.contacts.length > 0}
									{#each p.contacts as c (c.id ?? c)}
										<span class="prest-contact">
											📞 {c.telephone}{#if c.prenom || c.nom}&nbsp;— {nomAffiche(
													c,
												)}{/if}{#if c.fonction}&nbsp;({c.fonction}){/if}
										</span>
									{/each}
								{:else if p.telephone}
									{#each telephonesDe(p.telephone) as tel (tel)}
										<span class="prest-contact">📞 {tel.trim()}</span>
									{/each}
								{/if}
								{#if p.email}<span class="prest-contact">✉️ {p.email}</span>{/if}
							</div>
						{/if}
						<div class="prest-meta">
							{#if !compactPrests || expanded}
								<span class="badge badge-gray">{cs.length} contrat{cs.length !== 1 ? 's' : ''}</span
								>
								{#if nextVisit}<span
										class="badge"
										style="font-size:.75rem;color:var(--color-primary)"
										>🗓 {fmtDateShort(nextVisit)}</span
									>{/if}
							{/if}
							<BoutonLien ancre="presta-{p.id}" quoi="la fiche prestataire" />
							{#if $isCS}
								<button
									class="btn-icon-edit"
									aria-label="Modifier"
									title="Modifier"
									on:click|stopPropagation={() => startEditPrest(p)}>✏️</button
								>
								<button
									class="btn-icon-danger"
									aria-label="Archiver"
									title="Archiver"
									on:click|stopPropagation={() => deletePrest(p.id)}>🗑️</button
								>
							{/if}
							<span class="toggle-arrow">{expanded ? '▲' : '▼'}</span>
						</div>
					</div>
					{#if expanded}
						<div class="prest-body">
							<div class="detail-grid">
								{#if p.telephone}
									<div>
										<span class="detail-label">Téléphone</span>
										{#each telephonesDe(p.telephone) as tel (tel)}
											<span style="display:block">📞 {tel.trim()}</span>
										{/each}
									</div>
								{/if}
								{#if p.email}<div><span class="detail-label">Email</span>✉️ {p.email}</div>{/if}
								<div><span class="detail-label">Contrats</span>{cs.length}</div>
								{#if nextVisit}<div>
										<span class="detail-label">Prochaine visite</span><span
											style="color:var(--color-primary);font-weight:600"
											>🗓 {fmtDateShort(nextVisit)}</span
										>
									</div>{/if}
							</div>
							<!--  Les avis, enfin visibles un par un (#807). L'écran n'en montrait
							      que la MOYENNE, dans un badge : impossible de savoir qui avait
							      noté quoi, et donc impossible de retirer une note posée par
							      erreur — alors que l'endpoint de suppression existait. -->
							<NotationsPrestataire
								notations={notations.filter((n) => n.prestataire_id === p.id)}
								peutSupprimer={$isCS}
								on:supprimee={(e) => (notations = notations.filter((n) => n.id !== e.detail))}
							/>
						</div>
					{/if}
				</div>
			{/each}
		{/each}
	{/if}

	<!-- ══════════════════════════════════════════════════════════════ -->
	<!-- ONGLET 5 : CONSOMMATIONS (inchangé)                          -->
	<!-- ══════════════════════════════════════════════════════════════ -->
{:else if onglet === 'consommations'}
	<OngletConsommations bind:showReleveForm bind:libelleBouton={libelleReleve} {prestataires} />
{/if}

<!-- Modal notation prestataire (global, hors onglets) -->
{#if showNotationForm}
	<Modale
		edition
		titre="⭐ Noter le prestataire"
		styleBoite="max-width:420px"
		on:fermer={() => {
			showNotationForm = null;
		}}
	>
		<div class="modal-body">
			<div style="text-align:center;margin-bottom:1rem">
				<div style="display:inline-flex;gap:.25rem;font-size:2rem;cursor:pointer">
					<!--  Les cinq étoiles : littérales et distinctes, chacune sa propre clé. -->
					{#each [1, 2, 3, 4, 5] as s (s)}
						<button
							type="button"
							class="star-btn"
							class:active={notationNote >= s}
							style="background:none;border:none;cursor:pointer;font-size:2rem;color:{notationNote >=
							s
								? '#f59e0b'
								: '#d1d5db'};transition:color .15s"
							on:click={() => (notationNote = s)}
							on:mouseenter={() => (notationHover = s)}
							on:mouseleave={() => (notationHover = 0)}
						>
							{(notationHover || notationNote) >= s ? '★' : '☆'}
						</button>
					{/each}
				</div>
				{#if notationNote > 0}<p
						style="margin:.25rem 0 0;font-size:.9rem;color:var(--color-text-muted)"
					>
						{notationNote}/5
					</p>{/if}
			</div>
			<label class="field">
				Commentaire
				<textarea bind:value={notationCommentaire} rows="3" style="resize:vertical"></textarea>
			</label>
		</div>
		<div class="modal-footer">
			<button
				class="btn btn-outline"
				on:click={() => {
					showNotationForm = null;
				}}>Annuler</button
			>
			<button
				class="btn btn-primary"
				disabled={notationNote === 0 || notationSaving}
				on:click={saveNotation}>{notationSaving ? '…' : 'Enregistrer'}</button
			>
		</div>
	</Modale>
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
	.prest-header {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.85rem 1rem;
		cursor: pointer;
		flex-wrap: wrap;
	}
	.prest-main {
		display: flex;
		align-items: center;
		min-width: 160px;
		flex-wrap: wrap;
		gap: 0.25rem;
	}
	.prest-nom {
		font-size: 0.95rem;
	}
	.badge-type {
		background: var(--color-bg-secondary, #f0f0f0);
		color: var(--color-text);
		font-size: 0.75rem;
	}
	.prest-contacts {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem 0.75rem;
		flex: 1;
	}
	.prest-contact {
		font-size: 0.82rem;
		color: var(--color-text-muted);
	}
	.prest-meta {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		margin-left: auto;
	}
	.prest-body {
		padding: 0.25rem 1rem 1rem 1rem;
		border-top: 1px solid var(--color-border);
	}

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

	/*  Contrat expansible — `.carte-liste` depuis le 28/08/2026 (#598). Il en
	    recomposait la définition avec un espacement, une ombre et un `position`
	    différents, et l'accent de retard redisait `.carte-liste.urgent`, à un

	.contrats-summary,


	/*  Seuls la répartition et l'espacement : la peau des contrôles est partie
	    le 28/08/2026 — le pourquoi vit dans `check-styles-nus.mjs`, volet C. */
	.form-grid {
		grid-template-columns: repeat(auto-fit, minmax(min(180px, 100%), 1fr));
		gap: 0.65rem;
	}

	@media (max-width: 600px) {
		.prest-header {
			gap: 0.5rem;
		}
	}
</style>
