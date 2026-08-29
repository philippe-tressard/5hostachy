<script lang="ts">
	import EntetePage from '$lib/components/EntetePage.svelte';
	import { delaiArchivageMs, evenementArchive } from '$lib/archivage';
	import { TITRE_ARCHIVES } from '$lib/archives';
	import OngletArchivesCalendrier from '$lib/components/OngletArchivesCalendrier.svelte';
	import FormulaireCreation from '$lib/components/FormulaireCreation.svelte';
	import FormulaireEvenement from '$lib/components/FormulaireEvenement.svelte';
import { onMount } from 'svelte';
import { cibleDuHash, ongletDeLUrl, revelerCible } from '$lib/deepLink';
	import { calendrier as calApi, publications as pubsApi, prestataires as prestApi, ApiError, type Publication } from '$lib/api';
	import { isCS, isAdmin, currentUser } from '$lib/stores/auth';
	import CarteEvenement from '$lib/components/CarteEvenement.svelte';
	import RangeeCalendrier from '$lib/components/RangeeCalendrier.svelte';
	import { toast } from '$lib/components/Toast.svelte';
	import { getPageConfig, configStore, siteNomStore, defautsDePage } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';
	import { fmtDatetimeShort, fmtMonthYear } from '$lib/date';
	import { trackTabView } from '$lib/telemetry';
	import { KANBAN_COLS, kanbanEvVisible, kanbanColVisible, kanbanEvMatchesYear } from '$lib/kanban';
	import { clePlanifiee, planifier, resumePlan, type SourceRecurrente } from '$lib/init-prestataires';
	import { perimetreLabel, estPerimetreParDefaut, perimetreDefautListe, perimetreDuBatiment, perimetreLabelUn, noeudPerimetre } from '$lib/utils';
	import { perimetresStore } from '$lib/stores/perimetres';

	$: _pc = getPageConfig($configStore, 'calendrier', defautsDePage('calendrier'));
	$: _siteNom = $siteNomStore;

	let evenements: any[] = [];
	let prestataires: any[] = [];
	let loading = true;
	// Liste explicite : sert aussi à valider le `?onglet=` d'un lien profond.
	const ONGLETS = ['liste', 'kanban', 'archives'] as const;
	let onglet: (typeof ONGLETS)[number] = 'liste';
	$: isLocataire = $currentUser?.statut === 'locataire';
	$: if (isLocataire && (onglet === 'kanban' || onglet === 'archives')) onglet = 'liste';
	$: trackTabView(onglet);
	let filtreType = '';

	let archivedPubs: Publication[] = [];
	let archivedPubsLoaded = false;

	const _now = new Date();
	let expandedArchiveYears = new Set<number>();

	//  Le délai d'archivage du site — voir `$lib/archivage` (#515).
	$: archivageDelaiMs = delaiArchivageMs($configStore);

	let showForm = false;
	let editId: number | null = null;
	// État de l'épinglage à l'ouverture du formulaire : sert à ne pas compter
	// deux fois un événement déjà épinglé dans l'avertissement de plafond.
	let epingleInitial = false;
	let expandedEvId: number | null = null;
	let expandedKanbanId: number | null = null;

	let form = {
		titre: '',
		description: '',
		type: 'autre',
		lieu: '',
		debut: '',
		debut_heure: '',
		fin: '',
		statut_kanban: '',
		prestataire_id: '',
		frequence_type: '',
		frequence_valeur: '',
		affichable: true,
		// Absent de cette déclaration, `epingle` n'existait pas dans le type
		// inféré de `form` : les sept endroits qui l'utilisent étaient en erreur
		// TypeScript depuis l'ajout de l'épinglage des événements.
		epingle: false,
		partager_whatsapp: false,
		envoyer_syndic: false,
		envoyer_cs: false,
	};
	let formPerimetreCible: string[] = perimetreDefautListe();
	let submitting = false;

	// `affichable` avait TROIS valeurs par défaut différentes pour un même champ :
	// `false` à la création ici, `?? true` à l'édition (`startEdit`), et `True` dans
	// le schéma d'API (`EvenementCreate`). Résultat : un événement créé depuis le
	// calendrier n'apparaissait jamais dans le fil d'activité, alors que le même
	// événement rouvert puis réenregistré s'y affichait. Une seule valeur désormais :
	// visible par défaut, comme l'API l'annonce.
	//
	// Seule exception, et c'est une règle métier ferme : les maintenances récurrentes
	// ne vont jamais au fil (elles sont aussi exclues de la vue Liste et générées à
	// `affichable: false` par le Kanban) — sinon une seule campagne annuelle inonde
	// le tableau de bord.
	$: if (form.type === 'maintenance_recurrente') form.affichable = false;
	// Épingler suppose d'être dans le fil : les deux ne peuvent pas diverger.
	$: if (!form.affichable) form.epingle = false;

	const types = [
		{ val: 'travaux', label: '\u{1F528} Travaux' },
		{ val: 'coupure', label: '⚡ Coupure' },
		{ val: 'ag', label: '\u{1F3DB}️ AG' },
		{ val: 'maintenance', label: '\u{1F527} Maintenance' },
		{ val: 'maintenance_recurrente', label: '\u{1F504} Maintenance récurrente' },
		{ val: 'autre', label: '\u{1F4CC} Autre' },
	];

	function typeLabel(t: string) {
		return types.find(x => x.val === t)?.label ?? t;
	}


	onMount(async () => {
		try {
			evenements = await calApi.list();
			const expiredYears = [...new Set(evenements.filter(e => evenementArchive(e, archivageDelaiMs)).map(e => new Date(e.fin ?? e.debut).getFullYear()))].sort((a, b) => b - a);
			if (expiredYears.length > 0) expandedArchiveYears = new Set([expiredYears[0]]);
			// Liens profonds : `?onglet=` pour la vue, `#ev-<id>` pour l'événement.
			// L'ancre impose la vue liste — c'est la seule où un événement porte un id.
			const urlOnglet = ongletDeLUrl(ONGLETS);
			if (urlOnglet) onglet = urlOnglet;
			const idEv = cibleDuHash('ev');
			if (idEv !== null) {
				onglet = 'liste';
				expandedEvId = idEv;
				revelerCible(`ev-${idEv}`);
			}
		} catch {
			toast('error', 'Erreur de chargement');
		} finally {
			loading = false;
		}
	});

	// Chargement des données prestataires après que le store utilisateur soit disponible
	// (évite les appels 403 pour les non-CS/admin, et corrige la course entre onMount et le chargement du store)
	let _prestLoaded = false;
	$: if ($currentUser && !_prestLoaded) {
		_prestLoaded = true;
		//  `prestApi.list()` est restreint au CS et aux admins : un résident qui
		//  reçoit `[]` voit les cartes sans le nom du prestataire, et non une erreur.
		//  ⚠️ Faux positif déclaré : `_prestLoaded` ferme le bloc (#549).
		// eslint-disable-next-line svelte/infinite-reactive-loop
		if ($isCS || $isAdmin) prestApi.list().then((p) => { prestataires = p; }).catch(() => {});
	}

	// AG visibles uniquement par propriétaires, CS et admin
	$: canSeeAG = ($currentUser?.roles ?? []).some((r: string) => ['propriétaire', 'conseil_syndical', 'admin'].includes(r));
	$: visibleTypes = (canSeeAG ? types : types.filter(t => t.val !== 'ag')).filter(t => t.val !== 'maintenance_recurrente');
	$: filtered = (() => {
		let evs = canSeeAG ? evenements : evenements.filter(e => e.type !== 'ag');
		// Un événement avec suivi kanban actif (non terminé / non annulé) reste visible en Liste
		// même si sa date de début est passée — il disparaîtra seulement à la clôture du kanban.
		evs = evs.filter(e => {
			if (e.archivee) return false;
			const kanbanActif = e.statut_kanban && !['termine', 'annule'].includes(e.statut_kanban);
			return !evenementArchive(e, archivageDelaiMs) || kanbanActif;
		});
		// Les maintenances récurrentes restent hors vue Liste.
		// Exception métier: les prestations ponctuelles (non récurrentes) avec workflow restent visibles en Liste ET Kanban.
		evs = evs.filter(e => {
			if (e.type === 'maintenance_recurrente') return false;
			if (!e.statut_kanban) return true;
			// Tout événement marqué affichable est visible en liste (cohérence avec "Événements récents" du tableau de bord)
			if (e.affichable === true) return true;
			// CS/admin : les événements kanban avec prestataire (workflow non-public) restent visibles en liste
			if ($isCS || $isAdmin) return !!e.prestataire_id;
			return false;
		});
		return filtreType ? evs.filter(e => e.type === filtreType) : evs;
	})();
	$: allArchiveEvs = (() => {
		let evs = canSeeAG ? evenements : evenements.filter(e => e.type !== 'ag');
		evs = evs.filter(e => evenementArchive(e, archivageDelaiMs) || e.archivee);
		// Règle métier : un événement avec suivi kanban ne peut figurer en archives
		// que s'il est Terminé ou Annulé. Les statuts actifs (ag, cs, syndic, fournisseur)
		// restent dans la vue Kanban jusqu'à leur clôture.
		evs = evs.filter(e => !e.statut_kanban || ['termine', 'annule'].includes(e.statut_kanban));
		// Maintenances récurrentes : uniquement les terminées (pas les annulées)
		evs = evs.filter(e => e.type !== 'maintenance_recurrente' || e.statut_kanban === 'termine');
		return filtreType ? evs.filter(e => e.type === filtreType) : evs;
	})();

	// Fusion événements + publications + prestations archivés en une seule liste
	$: allArchiveItems = (() => {
		const items: any[] = [
			...allArchiveEvs.map(ev => ({ ...ev, _kind: 'ev', _date: ev.fin ?? ev.debut })),
			...archivedPubs.map(pub => ({ ...pub, _kind: 'pub', _date: pub.mis_a_jour_le ?? pub.cree_le })),
		];
		items.sort((a, b) => new Date(b._date).getTime() - new Date(a._date).getTime());
		return items;
	})();

	$: archiveByYear = (() => {
		const map = new Map<number, any[]>();
		for (const item of allArchiveItems) {
			const y = new Date(item._date).getFullYear();
			if (!map.has(y)) map.set(y, []);
			map.get(y)!.push(item);
		}
		return [...map.entries()].sort((a, b) => b[0] - a[0]).map(([year, items]) => {
			const monthMap = new Map<string, any[]>();
			for (const item of items) {
				const key = fmtMonthYear(item._date);
				if (!monthMap.has(key)) monthMap.set(key, []);
				monthMap.get(key)!.push(item);
			}
			return [year, [...monthMap.entries()]] as [number, [string, any[]][]];
		});
	})();

	// ── Pièces jointes ─────────────────────────────────────────────────────
	// Photos et documents passent par `POST /uploads/fichier`, qui n'a pas besoin
	// que l'affaire existe : l'URL est connue tout de suite et part dans la
	// création. La file d'attente précédente (téléverser APRÈS, avec un aperçu
	// blob:) avait un défaut invisible — l'e-mail au syndic était construit avant
	// les photos, et partait sans elles.
	let photosUrls: string[] = [];
	let fichiersUrls: string[] = [];

	function resetForm() {
		form = { titre: '', description: '', type: 'autre', lieu: '', debut: _now.toISOString().slice(0, 10), debut_heure: '', fin: '', statut_kanban: '', prestataire_id: '', frequence_type: '', frequence_valeur: '', affichable: true, epingle: false, partager_whatsapp: false, envoyer_syndic: false, envoyer_cs: false };
		formPerimetreCible = perimetreDefautListe();
		epingleInitial = false;
		editId = null;
		photosUrls = [];
		fichiersUrls = [];
	}

	function startEdit(ev: any) {
		form = {
			titre: ev.titre, description: ev.description ?? '', type: ev.type,
			lieu: ev.lieu ?? '', debut: ev.debut?.slice(0, 10) ?? '',
			debut_heure: ev.debut?.slice(11, 16) ?? '',
			fin: ev.fin?.slice(0, 16) ?? '',
			statut_kanban: ev.statut_kanban ?? '',
			prestataire_id: ev.prestataire_id ? String(ev.prestataire_id) : '',
			frequence_type: ev.frequence_type ?? '',
			frequence_valeur: ev.frequence_valeur ? String(ev.frequence_valeur) : '',
			affichable: ev.affichable ?? true,
			epingle: ev.epingle ?? false,
			partager_whatsapp: ev.partager_whatsapp ?? false,
			envoyer_syndic: ev.envoyer_syndic ?? false,
			envoyer_cs: ev.envoyer_cs ?? false,
		};
		// Mémorisé pour que l'avertissement de plafond ne recompte pas l'événement
		// en cours d'édition comme un épinglage supplémentaire.
		epingleInitial = form.epingle;
		const p = ev.perimetre ?? '';
		formPerimetreCible = estPerimetreParDefaut(p) ? perimetreDefautListe() : p.split(',').filter(Boolean);
		editId = ev.id;
		photosUrls = ev.photos_urls ?? [];
		fichiersUrls = ev.fichiers_urls ?? [];
		showForm = true;
	}

	async function save() {
		if (!form.titre || !form.debut) { toast('error', 'Titre et date de début obligatoires'); return; }
		submitting = true;
		const perimetre = formPerimetreCible.join(',');
		//  `debut_heure` est écarté DÉLIBÉRÉMENT de `formData` : il est recomposé
		//  dans `debut` ci-dessous. Le préfixe `_` dit que l'inemploi est voulu.
		const { debut_heure: _debut_heure, frequence_type: ft, frequence_valeur: fv, ...formData } = form;
		const payload = {
			...formData,
			perimetre,
			batiment_id: null,
			debut: form.debut + (form.debut_heure ? 'T' + form.debut_heure : 'T00:00'),
			fin: form.fin || null,
			lieu: form.lieu.trim() || null,
			description: form.description || null,
			statut_kanban: form.statut_kanban || null,
			prestataire_id: form.prestataire_id ? Number(form.prestataire_id) : null,
			frequence_type: ft || null,
			frequence_valeur: fv ? Number(fv) : null,
			affichable: form.affichable,
			epingle: form.affichable && form.epingle,
			partager_whatsapp: form.partager_whatsapp,
			envoyer_syndic: form.envoyer_syndic,
			envoyer_cs: form.envoyer_cs,
			photos_urls: photosUrls,
			fichiers_urls: fichiersUrls,
		};
		try {
			if (editId) {
				await calApi.update(editId, payload);
			} else {
				await calApi.create(payload);
			}
			evenements = await calApi.list();
			showForm = false;
			resetForm();
			toast('success', editId ? 'Événement modifié' : 'Événement créé');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally {
			submitting = false;
		}
	}

	async function archiveEv(id: number) {
		if (!confirm('Archiver cet événement ?')) return;
		try {
			await calApi.archive(id);
			evenements = evenements.map(e => e.id === id ? { ...e, archivee: true } : e);
			toast('success', 'Événement archivé');
		} catch { toast('error', 'Erreur'); }
	}

	async function deleteEv(id: number) {
		if (!confirm('Supprimer définitivement cet événement ? Cette action est irréversible.')) return;
		try {
			await calApi.delete(id);
			evenements = evenements.filter(e => e.id !== id);
			toast('success', 'Événement supprimé définitivement');
		} catch { toast('error', 'Erreur'); }
	}

	async function loadArchivedPubs() {
		if (archivedPubsLoaded) return;
		try {
			archivedPubs = await pubsApi.list(true);
		} catch { /* silencieux */ }
		archivedPubsLoaded = true;
	}

	async function deleteArchivedPub(pub: Publication) {
		if (!confirm(`Supprimer définitivement « ${pub.titre} » ? Cette action est irréversible.`)) return;
		try {
			await pubsApi.delete(pub.id);
			archivedPubs = archivedPubs.filter(p => p.id !== pub.id);
			toast('success', 'Publication supprimée définitivement');
		} catch { toast('error', 'Erreur'); }
	}

	$: if (onglet === 'archives') loadArchivedPubs();

	function formatDate(d: string) {
		return fmtDatetimeShort(d);
	}

	/*  Vue liste : années passées → « 2025 », année courante → « mars 2026 ».
	    ⚠️ L'ORDRE vit ici, une seule fois : il était écrit DEUX fois (28/08/2026). */
	const duPlusRecent = (a: any, b: any) => new Date(b.debut).getTime() - new Date(a.debut).getTime();

	function groupByYear(evs: any[]) {
		const currentYear = new Date().getFullYear();
		const result: [string, any[]][] = [];
		const indexMap = new Map<string, number>();
		for (const ev of [...evs].sort(duPlusRecent)) {
			const d = new Date(ev.debut);
			const year = d.getFullYear();
			const key = year < currentYear
				? String(year)
				: fmtMonthYear(ev.debut);
			if (!indexMap.has(key)) { indexMap.set(key, result.length); result.push([key, []]); }
			result[indexMap.get(key)!][1].push(ev);
		}
		return result;
	}

	$: listItems = [...filtered].sort(duPlusRecent);
	$: groups = groupByYear(listItems);
	// Maintenances récurrentes trackées dans le workflow Kanban (statut_kanban actif, non archivées, non périmées)
	$: recurringMaintenances = (() => {
		if (filtreType && filtreType !== 'maintenance_recurrente') return [];
		return evenements.filter((e: any) =>
			e.type === 'maintenance_recurrente'
			&& e.statut_kanban && e.statut_kanban !== 'annule'
			&& !e.archivee && !evenementArchive(e, archivageDelaiMs));
	})();
	let showPeriodicSection = false;

	// ── Kanban ────────────────────────────────────────────────
	//  Le fil vit dans `HistoriqueEvenement` ; la page garde le geste et le rechargement.
	let evolOuverte: number | null = null;

	function ouvrirSuivi(ev: any) {
		expandedEvId = ev.id;
		evolOuverte = ev.id;
	}

	async function recharger() {
		evenements = await calApi.list();
	}

	//  Couleur DÉRIVÉE du code : la table de sept clés en dur laissait en gris tout
	//  périmètre créé depuis l'administration, et tout bâtiment au-delà du quatrième.
	const PALETTE_PERIMETRE = ['#ef4444', '#3b82f6', '#22c55e', '#f59e0b', '#f97316', '#8b5cf6', '#ec4899', '#0ea5e9', '#14b8a6'];
	function couleurPerimetre(code: string): string {
		let s = 0;
		for (let i = 0; i < code.length; i++) s = (s * 31 + code.charCodeAt(i)) >>> 0;
		return PALETTE_PERIMETRE[s % PALETTE_PERIMETRE.length];
	}
	// Exercice = année. Par défaut : année courante, sauf si < février → N-1
	const defaultExercice = _now.getMonth() < 1 ? _now.getFullYear() - 1 : _now.getFullYear();
	let kanbanExercice = defaultExercice;
	let kanbanBatiment = '';

	//  Les bâtiments viennent de l'arborescence en base : ce sont les nœuds qui
	//  portent un `batiment_id`. Ils étaient dérivés d'une table de sept clés
	//  écrite en dur, arrêtée à `bat:4` — un cinquième bâtiment n'apparaissait pas
	//  du tout dans ce filtre. Réactif : la liste se remplit dès que le store est
	//  chargé, sans que cette page attende quoi que ce soit.
	$: BATIMENT_OPTIONS = [
		{ val: '', label: 'Tous les bâtiments' },
		...$perimetresStore
			.filter((n) => n.actif && n.batiment_id !== null && n.selectionnable)
			.map((n) => ({ val: n.code, label: n.libelle })),
	];

	$: _kanbanCtx = { isCS: $isCS, isAdmin: $isAdmin, canSeeAG, statut: $currentUser?.statut ?? '' };

	$: kanbanEvs = (() => {
		const baseEvents = evenements.filter(ev =>
			ev.statut_kanban && kanbanEvVisible(ev, _kanbanCtx)
		);
		return baseEvents.filter(ev => {
			if (!kanbanEvMatchesYear(ev, kanbanExercice)) return false;
			if (kanbanBatiment) {
				const p = ev.perimetre ?? '';
				if (!estPerimetreParDefaut(p) && !p.split(',').some((s: string) => s.trim() === kanbanBatiment)) return false;
			}
			return true;
		});
	})();

	$: kanbanCols = KANBAN_COLS
		.filter(col => kanbanColVisible(col.id, _kanbanCtx))
		.map(col => ({
		...col,
		items: kanbanEvs.filter(ev => {
			if (ev.archivee && ev.type === 'maintenance_recurrente' && ev.statut_kanban === 'fournisseur') {
				return col.id === 'termine';
			}
			return ev.statut_kanban === col.id;
		}),
	}));

	$: kanbanExerciceOptions = (() => {
		const years = new Set<number>();
		evenements.forEach(ev => { if (ev.statut_kanban) years.add(new Date(ev.debut).getFullYear()); });
		years.add(defaultExercice);
		return [...years].sort((a, b) => b - a);
	})();

	// Drag & drop
	let dragEvId: number | null = null;

	function onDragStart(ev: DragEvent, id: number) {
		dragEvId = id;
		if (ev.dataTransfer) {
			ev.dataTransfer.effectAllowed = 'move';
			ev.dataTransfer.setData('text/plain', String(id));
		}
	}

	function onDragOver(ev: DragEvent) {
		ev.preventDefault();
		if (ev.dataTransfer) ev.dataTransfer.dropEffect = 'move';
	}

	async function onDrop(ev: DragEvent, colId: string) {
		ev.preventDefault();
		if (dragEvId == null) return;
		const id = dragEvId;
		dragEvId = null;
		if (id <= 0) return;
		const item = evenements.find(e => e.id === id);
		if (!item || item.statut_kanban === colId) return;
		const old = item.statut_kanban;
		const shouldArchive = colId === 'termine';
		evenements = evenements.map(e => e.id === id ? { ...e, statut_kanban: colId, archivee: shouldArchive ? true : e.archivee } : e);
		try {
			await calApi.update(id, shouldArchive ? { statut_kanban: colId, archivee: true } : { statut_kanban: colId });
		} catch {
			evenements = evenements.map(e => e.id === id ? { ...e, statut_kanban: old } : e);
			toast('error', 'Erreur lors du déplacement');
		}
	}

	//  `PERIMETRE_SHORT` a disparu : le libellé court est un CHAMP de l'arbre
	//  (`libelle_court`), et c'est sa recopie ici qui l'avait fait diverger (#316).
	function perimetreTags(p: string): { label: string; color: string }[] {
		if (estPerimetreParDefaut(p)) return [{ label: '\u{1F3D8}️ ' + perimetreLabel(perimetreDefautListe()), color: '#6b7280' }];
		return p.split(',').map(s => s.trim()).filter(Boolean)
			.map(s => ({ label: noeudPerimetre(s)?.libelle_court ?? perimetreLabelUn(s), color: couleurPerimetre(s) }));
	}

	// Couleur dégradée par année : teinte HSL qui tourne de 52° par an à partir de 2024
	function yearColor(year: number): string {
		const hue = ((year - 2024) * 52 + 220) % 360;
		return `hsl(${hue},55%,32%)`;
	}

	// ── Init prestataires ────────────────────────────
	//  La DÉCISION vit dans `$lib/init-prestataires` : deux boucles quasi
	//  identiques la portaient ici, et elles avaient déjà divergé sur le
	//  périmètre (#605). Ce qui reste ici est l'entrée/sortie — lire, demander,
	//  écrire — et la résolution du périmètre, qui dépend des données chargées.
	let initLoading = false;

	/** Les événements déjà posés pour l'exercice, sous forme de clés. */
	function clesExistantes(exercice: number): Set<string> {
		return new Set(
			evenements
				.filter(
					(ev: any) =>
						ev.type === 'maintenance_recurrente' &&
						!ev.archivee &&
						new Date(ev.debut).getFullYear() === exercice,
				)
				.map((ev: any) => clePlanifiee(ev.titre, new Date(ev.debut).getMonth())),
		);
	}

	async function initPrestataires() {
		initLoading = true;
		try {
			const [contrats, prests] = await Promise.all([prestApi.contrats(), prestApi.list()]);
			const prestMap = new Map(prests.map((p: any) => [p.id, p.nom]));

			//  Les deux sources deviennent UNE liste normalisée : c'est ce qui
			//  supprime la seconde boucle, et avec elle la divergence du périmètre.
			const sources: SourceRecurrente[] = [
				...contrats.map((c: any) => ({
					titre: `${prestMap.get(c.prestataire_id) ?? 'Prestataire'} — ${c.libelle}`,
					frequence_type: c.frequence_type ?? null,
					frequence_valeur: c.frequence_valeur ?? null,
					prestataire_id: c.prestataire_id ?? null,
					perimetre: perimetreDuBatiment(c.batiment_id),
					description: c.notes ?? null,
				})),
				...evenements
					.filter((ev: any) => ev.type === 'maintenance' && ev.prestataire_id && !ev.archivee)
					.map((ev: any) => ({
						titre: ev.titre,
						frequence_type: ev.frequence_type ?? null,
						frequence_valeur: ev.frequence_valeur ?? null,
						prestataire_id: ev.prestataire_id ?? null,
						//  ⚠️ Ce repli est le correctif de #605 : la branche
						//  événement posait `ev.perimetre ?? ''`, donc une chaîne VIDE
						//  quand la source n'en portait pas, là où l'autre calculait
						//  celui du bâtiment. Les deux le calculent désormais.
						perimetre: ev.perimetre || perimetreDuBatiment(ev.batiment_id),
						description: ev.description ?? null,
					})),
			];

			const plan = planifier(sources, clesExistantes(kanbanExercice), kanbanExercice);
			const message = resumePlan(plan, kanbanExercice);
			if (plan.aCreer.length === 0) {
				toast('info', message);
				return;
			}
			if (!confirm(message)) return;

			for (const ev of plan.aCreer) await calApi.create(ev);
			evenements = await calApi.list();
			toast('success', `${plan.aCreer.length} événement(s) créé(s)`);
		} catch {
			toast('error', "Erreur lors de l'initialisation");
		} finally {
			initLoading = false;
		}
	}
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<!--  L'en-tête n'OUVRE plus : l'annulation vit à côté d'« Enregistrer » (norme du
      18/08/2026). La modale avait déjà perdu sa croix pour la même raison (#367). -->
<EntetePage titre={_pc.titre} icone={_pc.icone || 'calendar-days'}>
	{#if $isCS && !showForm}
		<button class="btn btn-primary page-header-btn" on:click={() => (showForm = true)}>
			+ Nouvel événement
		</button>
	{/if}
</EntetePage>
<div class="page-subtitle">{@html safeHtml(_pc.descriptif)}</div>

<!-- Onglets -->
<div class="tabs" role="tablist" style="margin-bottom:1.5rem">
	<button role="tab" class:active={onglet === 'liste'} on:click={() => onglet = 'liste'}>{_pc.onglets?.liste?.label ?? '\u{1F4CB} Liste'}</button>
	{#if !isLocataire}
	<button role="tab" class:active={onglet === 'kanban'} on:click={() => onglet = 'kanban'}>{_pc.onglets?.kanban?.label ?? '\u{1F5C3}️ Kanban'}</button>
	<button role="tab" class:active={onglet === 'archives'} on:click={() => onglet = 'archives'}>{_pc.onglets?.archives?.label ?? TITRE_ARCHIVES}</button>
	{/if}
</div>
{#if _pc.onglets?.[onglet]?.descriptif}
<p class="tab-descriptif">{@html safeHtml(_pc.onglets[onglet].descriptif)}</p>
{/if}

<!-- Filtres -->
<div class="filters">
	<button class="btn btn-sm" class:btn-primary={filtreType === ''} on:click={() => filtreType = ''}>Tous</button>
	{#each visibleTypes as t}
		<button class="btn btn-sm" class:btn-primary={filtreType === t.val} on:click={() => filtreType = t.val}>
			{t.label}
		</button>
	{/each}
</div>

<!-- Formulaire création/édition -->
{#if showForm && $isCS}
	<FormulaireCreation titre={editId ? 'Modifier l’événement' : 'Nouvel événement'}>
			<FormulaireEvenement bind:form bind:photosUrls bind:fichiersUrls
				bind:formPerimetreCible {types} {prestataires} {submitting}
				modeEdition={editId !== null}
				{epingleInitial} kanbanCols={KANBAN_COLS} onSubmit={save}
				on:annule={() => { showForm = false; resetForm(); }} />
	</FormulaireCreation>
{/if}

<!-- Contenu -->
{#if loading}
	<p style="color:var(--color-text-muted)">Chargement…</p>
{:else if onglet === 'archives'}
	<OngletArchivesCalendrier {allArchiveItems} {archiveByYear}
		bind:expandedArchiveYears {typeLabel} {formatDate}
		{deleteArchivedPub} {deleteEv} />

{:else if listItems.length === 0 && !recurringMaintenances.length && !kanbanEvs.length}
	<div class="empty-state">
		<h3>Aucun événement</h3>
		<p>Le calendrier de la résidence apparaîtra ici.</p>
	</div>
{:else if onglet === 'liste'}
	{#each groups as [annee, evs]}
		<div class="month-group">
			<div class="month-label">&#x1F4C5; {annee}</div>
			{#each evs as ev}
				{@const expanded = expandedEvId === ev.id}
				<CarteEvenement {ev} {expanded} colonnes={KANBAN_COLS} peutAgir={$isCS}
					suiviOuvert={evolOuverte === ev.id} editionOuverte={showForm && editId === ev.id} {typeLabel} formatDate={formatDate}
					on:basculer={() => (expandedEvId = expanded ? null : ev.id)}
					on:suivre={() => ouvrirSuivi(ev)}
					on:modifier={() => startEdit(ev)}
					on:archiver={() => archiveEv(ev.id)}
					on:evolue={recharger}
					on:fermer={() => (evolOuverte = null)} />
			{/each}
		</div>
	{/each}
	{#if recurringMaintenances.length > 0}
		<div class="recurring-section">
			<button class="recurring-toggle" on:click={() => showPeriodicSection = !showPeriodicSection}>
				🔄 Maintenances récurrentes
				<span style="font-size:.8rem;font-weight:400;color:var(--color-text-muted)">({recurringMaintenances.length})</span>
				<span class="chevron" class:open={showPeriodicSection} style="margin-left:auto">›</span>
			</button>
			{#if showPeriodicSection}
				{#each recurringMaintenances as ev}
					{@const col = ev.statut_kanban ? KANBAN_COLS.find(c => c.id === ev.statut_kanban) : undefined}
					<RangeeCalendrier
						typeTexte={typeLabel(ev.type)}
						titre={ev.titre}
						metas={[...(ev.prestataire_nom ? [`\u{1F3AF} ${ev.prestataire_nom}`] : []),
							...(ev.lieu ? [`\u{1F4CD} ${ev.lieu}`] : [])]}
						dates={[{ texte: formatDate(ev.debut) },
							...(ev.fin ? [{ texte: `→ ${formatDate(ev.fin)}`, attenue: true }] : [])]}
						perimetre={ev.perimetre}
						badgeKanban={col ? { texte: col.label, couleur: col.color } : null}
						avecActions={$isCS}>
						<svelte:fragment slot="actions">
							<button class="btn-icon-edit" aria-label="Modifier" title="Modifier" on:click={() => startEdit(ev)}>✏️</button>
						</svelte:fragment>
					</RangeeCalendrier>
				{/each}
			{/if}
		</div>
	{/if}
{:else}
	<!-- ── Kanban Trello-like ────────────────────────────────── -->
	<div class="kanban-toolbar">
		<label class="kanban-exercice-label">
			Exercice :
			<select bind:value={kanbanExercice} class="kanban-exercice-select">
				{#each kanbanExerciceOptions as y}<option value={y}>{y}</option>{/each}
			</select>
		</label>
		<label class="kanban-exercice-label">
			Bâtiment :
			<select bind:value={kanbanBatiment} class="kanban-exercice-select">
				{#each BATIMENT_OPTIONS as b}<option value={b.val}>{b.label}</option>{/each}
			</select>
		</label>
		<span class="kanban-count-total">{kanbanEvs.length} affaire{kanbanEvs.length > 1 ? 's' : ''}</span>
		{#if $isCS}
			<button class="btn btn-sm kanban-init-btn" on:click={initPrestataires} disabled={initLoading}>
				{initLoading ? '⏳ Création…' : '⚙️ Init. prestataires'}
			</button>
		{/if}
	</div>
	<div class="kanban">
		{#each kanbanCols as col}
			{@const items = col.items}
			<div class="kanban-col"
				on:dragover={onDragOver}
				on:drop={(e) => onDrop(e, col.id)}
				role="list">
				<div class="kanban-col-header" style="border-top-color:{col.color}">
					<span>{col.label}</span>
					<span class="kanban-count">{items.length}</span>
				</div>
				{#if items.length === 0}
					<p class="kanban-empty">Aucune affaire</p>
				{:else}
					{#each items as ev (ev.id)}
						<div class="kanban-card card"
							class:event-urgent={ev.type === 'coupure'}
							class:kanban-card-expanded={expandedKanbanId === ev.id}
							draggable={$isCS && expandedKanbanId !== ev.id ? 'true' : 'false'}
							on:dragstart={(e) => onDragStart(e, ev.id)}
							on:click={() => expandedKanbanId = expandedKanbanId === ev.id ? null : ev.id}
							on:keydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); expandedKanbanId = expandedKanbanId === ev.id ? null : ev.id; } }}
							role="button"
							tabindex="0">
							<!-- Tags périmètre + année (uniquement si année ≠ exercice sélectionné) -->
							<div class="kanban-card-tags">
								{#each perimetreTags(ev.perimetre) as tag}
									<span class="kb-tag" style="background:{tag.color}">{tag.label}</span>
								{/each}
								<span class="kb-tag" style="background:{yearColor(new Date(ev.debut).getFullYear())}" title="Événement de {new Date(ev.debut).getFullYear()}">{new Date(ev.debut).getFullYear()}</span>
							</div>
							{#if ev.prestataire_nom}<span class="kanban-card-prest">{ev.prestataire_nom}</span>{/if}
							<strong class="kanban-card-titre">{ev.titre}</strong>
							<div class="kanban-card-footer">
								<span class="kanban-card-type">{typeLabel(ev.type)}</span>
								{#if $isCS}
									<div class="kanban-card-actions" role="presentation" on:click|stopPropagation on:keydown|stopPropagation>
										<button class="btn-icon-edit" aria-label="Modifier" title="Modifier" on:click={() => startEdit(ev)}>✏️</button>
									{#if $isAdmin}
										<button class="btn-icon-danger" aria-label="Supprimer définitivement" title="Supprimer définitivement" on:click={() => deleteEv(ev.id)}>&#x1F5D1;️</button>
									{/if}
									</div>
								{/if}
							</div>
							{#if expandedKanbanId === ev.id}
								<div class="kanban-card-detail" role="presentation" on:click|stopPropagation on:keydown|stopPropagation>
									<div class="kanban-card-detail-row">📅 {formatDate(ev.debut)}{#if ev.fin} → {formatDate(ev.fin)}{/if}</div>
									{#if ev.lieu}<div class="kanban-card-detail-row">📍 {ev.lieu}</div>{/if}
									{#if ev.description}
										<div class="kanban-card-detail-desc rich-content">{@html safeHtml(ev.description)}</div>
									{/if}
								</div>
							{/if}
						</div>
					{/each}
				{/if}
			</div>
		{/each}
	</div>
{/if}

<style>
	/*  `.filters` vient d'`app.css` depuis #446 — la marge basse y est. */
	/*  ⚠️ `.form-grid` et `.form-grid .field` vivaient ici et ne s'appliquaient
	    plus à rien depuis que le formulaire est parti dans
	    `FormulaireEvenement.svelte` (15/08/2026) — `svelte-check` les signalait
	    « Unused CSS selector », et personne ne lit un avertissement qui existait
	    déjà la veille. La leçon qu'elles portaient (le sélecteur terminé par une
	    virgule qui fusionnait avec la règle suivante, #372) est partie AVEC la
	    règle, dans le composant qui la rend. Une explication qui reste où le code
	    n'est plus n'explique plus rien. */
	.month-group { margin-bottom: 1.5rem; }
	.month-label { font-size: .8rem; font-weight: 600; text-transform: uppercase; letter-spacing: .06em; color: var(--color-text-muted); margin-bottom: .5rem; }
	/*  ✅ Les règles `.event-*` et `.archive-*` sont parties dans
	    `RangeeCalendrier.svelte` (#432), AVEC le balisage qui les portait — la
	    seule façon qu'elles s'appliquent encore, Svelte scopant le style au
	    composant qui rend.

	    C'est ce que la version précédente de ce commentaire annonçait : elles
	    servaient QUATRE rangées écrites à la main ici et la carte de la liste
	    là-bas, et « les unifier suppose de reprendre ces deux blocs — c'est le
	    travail de #432 ». Reprendre les deux ENSEMBLE était la condition : n'en
	    extraire qu'un aurait emporté les règles et laissé l'autre nu, ce qui est
	    exactement la panne des pastilles de la v2.67.11. */

	.tabs { padding-bottom: .1rem; }  /* le reste vient de la charte (#607) */

	.kanban-toolbar { display: flex; align-items: center; gap: 1rem; margin-bottom: .75rem; flex-wrap: wrap; }
	.kanban-exercice-label { font-size: .85rem; font-weight: 600; display: flex; align-items: center; gap: .4rem; }
	.kanban-exercice-select { padding: .25rem .5rem; border: 1px solid var(--color-border); border-radius: var(--radius); background: var(--color-surface); font-size: .85rem; }
	.kanban-init-btn { margin-left: auto; font-size: .8rem; padding: .3rem .75rem; border: 1px solid var(--color-border); border-radius: var(--radius); background: var(--color-surface); cursor: pointer; white-space: nowrap; }
	.kanban-init-btn:hover:not(:disabled) { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
	.kanban-init-btn:disabled { opacity: .5; cursor: not-allowed; }
	/*  Les cinq règles `.archive-year-*` sont parties avec
	    `OngletArchivesCalendrier` : elles n'habillaient que son balisage. */
	/*  ⚠️ `.kanban-col` était défini DEUX fois, à quinze lignes d'intervalle, avec
	    les mêmes quatre propriétés — la seconde n'ajoutait rien et masquait le
	    `min-width` et le `flex` de la première à la lecture. Aucun contrôle ne dit
	    qu'une règle est écrite deux fois dans le même bloc `<style>` : seule la
	    relecture le voit. */
	/*  ⚠️ La SEULE variante locale du kanban : les tags du calendrier sont des
	    périmètres et des années, que la minuscule harmonise. Elle n'est PAS montée
	    dans `composants.css` parce que les tags des prestations portent un sigle —
	    « OS joint » deviendrait « os joint » (#453, 28/08/2026). */
	.kb-tag { text-transform: lowercase; }
	.kanban-card-expanded { cursor: default; box-shadow: 0 2px 8px rgba(0,0,0,.12); }
	.kanban-card-detail { border-top: 1px solid var(--color-border); margin-top: .3rem; padding-top: .35rem; }
	.kanban-card-detail-row { font-size: .72rem; color: var(--color-text-muted); line-height: 1.5; }
	.kanban-card-detail-desc { font-size: .72rem; line-height: 1.5; margin-top: .25rem; }
	.kanban-card:active { cursor: grabbing; }
	.kanban-card[draggable="true"]:hover { box-shadow: 0 2px 8px rgba(0,0,0,.12); }
	.kanban-card-type { font-size: .72rem; font-weight: 600; color: var(--color-text-muted); }
	.recurring-section { margin-top: 1.5rem; padding: .5rem 0; }
	.recurring-toggle {
		background: #f0f9ff; border: 1px solid #bae6fd; border-radius: var(--radius);
		cursor: pointer; font-size: .875rem; font-weight: 600;
		color: #0369a1; padding: .5rem .9rem;
		width: 100%; text-align: left;
		display: flex; align-items: center; gap: .5rem;
	}
	.recurring-toggle:hover { background: #e0f2fe; }
	/*  ⚠️ `.maintenance-archive-section` et `.maintenance-archive-toggle` vivaient
	    ici sans être posées sur aucun élément — signalées elles aussi par
	    `svelte-check`. Supprimées avec #432. */
</style>
