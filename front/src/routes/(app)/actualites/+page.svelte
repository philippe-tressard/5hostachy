<script lang="ts">
	import EntetePage from '$lib/components/EntetePage.svelte';
	import { onMount } from 'svelte';
	import { cibleDuHash, revelerCible } from '$lib/deepLink';
	import { isCS, isAdmin, setUser } from '$lib/stores/auth';
	import { publications as pubsApi, documents as docsApi, ApiError, type Publication, auth as authApi } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import CarteActualite from '$lib/components/CarteActualite.svelte';
	import FormulaireActualite from '$lib/components/FormulaireActualite.svelte';
	import HistoriqueActualites from '$lib/components/HistoriqueActualites.svelte';
	import RubriqueHistorique from '$lib/components/RubriqueHistorique.svelte';
	import { fichiersDepuisUrls } from '$lib/fichiers';
	import { getPageConfig, configStore, siteNomStore, defautsDePage } from '$lib/stores/pageConfig';
	import EvolForm from '$lib/components/EvolForm.svelte';
	import { safeHtml } from '$lib/sanitize';
	import { STATUT_LABELS, STATUT_PUBLICATION_OPTIONS } from '$lib/publications';

	$: _pc = getPageConfig($configStore, 'actualites', defautsDePage('actualites'));
	$: _siteNom = $siteNomStore;

	let pubList: Publication[] = [];
	$: compactPubs = pubList.length > 7;
	let loading = true;

	let showForm = false;
	let pubFilesMap: Record<number, any[]> = {};
	let loadedFilesFor = new Set<number>();
	let expandedPubs = new Set<number>();

	function togglePub(id: number) {
		if (expandedPubs.has(id)) {
			expandedPubs.delete(id);
			expandedPubs = new Set(expandedPubs);
			if (showEvolForm === id) showEvolForm = null;
		} else {
			expandedPubs = new Set([id]);
			showEvolForm = null;
			loadPubFiles(id);
		}
	}

	async function loadPubFiles(pubId: number) {
		if (loadedFilesFor.has(pubId)) return;
		loadedFilesFor.add(pubId);
		try {
			const docs = await docsApi.listByPublication(pubId);
			pubFilesMap = { ...pubFilesMap, [pubId]: docs };
		} catch { /* silencieux */ }
	}

	onMount(async () => {
		try {
			pubList = await pubsApi.list();
			// Lien profond `#pub-<id>` (fil d'activité, notification, e-mail)
			const idPub = cibleDuHash('pub');
			if (idPub !== null) {
				expandedPubs = new Set([idPub]);
				revelerCible(`pub-${idPub}`);
			}
			//  Rien n'est déplié d'office : la page s'ouvre sur une LISTE. La branche du dessus reste — un lien `#pub-<id>` doit ouvrir l'article visé.
			// Persist last-seen timestamp server-side
			const now = new Date().toISOString();
			authApi.updateMe({ last_seen_actualites: now }).then((u: any) => setUser(u)).catch(() => {});
		} finally {
			loading = false;
		}
	});

	function publicationCreee(e: CustomEvent<Publication>) {
		pubList = [e.detail, ...pubList];
		showForm = false;
	}

	async function archivePub(pub: Publication) {
		if (!confirm(`Archiver « ${pub.titre} » ?`)) return;
		try {
			await pubsApi.archive(pub.id);
			pubList = pubList.filter((p) => p.id !== pub.id);
			toast('success', 'Publication archivée');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Impossible d’archiver');
		}
	}

	async function deletePub(pub: Publication) {
		if (!confirm(`Supprimer définitivement « ${pub.titre} » ?`)) return;
		try {
			await pubsApi.delete(pub.id);
			pubList = pubList.filter((p) => p.id !== pub.id);
			toast('success', 'Publication supprimée');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Impossible de supprimer');
		}
	}

	//  Un seul gestionnaire pour les deux canaux : le second aurait été la copie
	//  du premier à trois mots près, et c'est ainsi que deux boutons finissent par
	//  ne plus se comporter pareil.
	const CANAUX = {
		email: { quoi: "l'email au syndic/CS", ok: 'Email renvoyé', envoi: pubsApi.renvoyerEmail },
		whatsapp: { quoi: "l'annonce sur le groupe WhatsApp", ok: 'Annonce renvoyée', envoi: pubsApi.renvoyerWhatsapp },
	} as const;

	async function renvoyerPub(pub: Publication, canal: keyof typeof CANAUX) {
		const c = CANAUX[canal];
		if (!confirm(`Renvoyer ${c.quoi} pour « ${pub.titre} » ?`)) return;
		try {
			await c.envoi(pub.id);
			toast('success', c.ok);
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Impossible de renvoyer');
		}
	}

	//  ── Édition ───────────────────────────────────────────────────────────────
	//  La page ne porte plus QUE l'identité de la publication en cours de
	//  correction : le formulaire lui-même est `FormulaireActualite`, le même
	//  qu'à la création (#433). Les onze variables `edit*` qui vivaient ici
	//  dupliquaient à la main un état que le composant tient déjà — et elles
	//  avaient déjà divergé : cinq notions manquantes, une en trop.
	let editingPub: Publication | null = null;

	// ── Évolutions ──────────────────────────────────────────────────────
	let showEvolForm: number | null = null;  // pub.id ouvert
	//  Le geste vient du bouton cliqué — `💬` commenter, `🔄` changer l'état — et
	//  il n'est plus redemandé une fois le formulaire ouvert (#426).
	let gesteEvol: 'commentaire' | 'etat' = 'commentaire';
	let evolSaving = false;

	function ouvrirEvolution(pub: Publication, geste: 'commentaire' | 'etat') {
		showEvolForm = pub.id;
		gesteEvol = geste;
		editingPub = null;
		expandedPubs = new Set([pub.id]);
	}
	let editingEvolId: number | null = null;
	let editingEvolPubId: number | null = null;
	let editEvolSaving = false;

	async function addEvolFromForm(pub: Publication, e: CustomEvent) {
		const data = e.detail;
		evolSaving = true;
		try {
			const evol = await pubsApi.addEvolution(pub.id, {
				type: data.type,
				contenu: data.contenu || undefined,
				nouveau_statut: data.nouveau_statut,
				partager_whatsapp: data.partager_whatsapp,
				envoyer_syndic: data.envoyer_syndic,
				envoyer_cs: data.envoyer_cs,
				fichiers_urls: data.fichiers_urls,
				email_externe: data.email_externe || undefined,
			});
			pubList = pubList.map(p => {
				if (p.id !== pub.id) return p;
				const updated = { ...p, evolutions: [...(p.evolutions ?? []), evol] };
				if (data.type === 'etat') updated.statut = evol.nouveau_statut as any;
				return updated;
			});
			showEvolForm = null;
			toast('success', data.type === 'etat' ? 'Statut mis à jour' : 'Commentaire ajouté');
		} catch (err: any) {
			toast('error', err instanceof ApiError ? err.message : 'Erreur');
		} finally { evolSaving = false; }
	}

	async function saveEvolEdit(e: CustomEvent) {
		if (editingEvolId === null || editingEvolPubId === null) return;
		editEvolSaving = true;
		try {
			const updated = await pubsApi.updateEvolution(editingEvolPubId, editingEvolId, {
				contenu: e.detail.contenu || undefined,
				fichiers_urls: e.detail.fichiers_urls,
			});
			pubList = pubList.map(p => {
				if (p.id !== editingEvolPubId) return p;
				return { ...p, evolutions: (p.evolutions ?? []).map(ev => ev.id === editingEvolId ? updated as any : ev) };
			});
			editingEvolId = null; editingEvolPubId = null;
			toast('success', 'Commentaire mis à jour');
		} catch { toast('error', 'Erreur de mise à jour'); }
		finally { editEvolSaving = false; }
	}

	function startEdit(pub: Publication) {
		editingPub = pub;
		showEvolForm = null;
		expandedPubs = new Set([pub.id]);
	}

	//  Le formulaire annonce ce qu'il a enregistré ; la page range. Elle ne
	//  reconstruit rien : `modifie` porte la publication telle que le serveur l'a
	//  relue, pièces jointes et corrections comprises.
	function publicationModifiee(e: CustomEvent<Publication>) {
		pubList = pubList.map((p) => (p.id === e.detail.id ? e.detail : p));
		editingPub = null;
	}

</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<!--  `alignerSaisie` quand le formulaire est ouvert : sans lui, « ✕ Annuler » se
      pose au bord DROIT DE LA PAGE, à plusieurs centaines de pixels de la boîte
      qu'il annule, laquelle s'arrête à 720 px (#367). -->
<EntetePage titre={_pc.titre} icone={_pc.icone || 'newspaper'} alignerSaisie={showForm}>
	{#if $isCS}
		<button class="btn btn-primary page-header-btn" on:click={() => (showForm = !showForm)}>
			{showForm ? '✕ Annuler' : '+ Nouvelle publication'}
		</button>
	{/if}
</EntetePage>
<div class="page-subtitle">{@html safeHtml(_pc.descriptif)}</div>

{#if showForm && $isCS}
	<FormulaireActualite on:cree={publicationCreee} />
{/if}

{#if loading}
	<p style="color:var(--color-text-muted)">Chargement…</p>
{:else if pubList.length === 0}
	<div class="empty-state">
		<h3>Aucune actualité</h3>
		<p>Les annonces du conseil syndical apparaîtront ici.</p>
	</div>
{:else}
	{#each pubList as pub (pub.id)}
		{@const expanded = expandedPubs.has(pub.id)}
		<CarteActualite {pub} {expanded}
			apercu={!compactPubs}
			documents={pubFilesMap[pub.id] ?? []}
			formulaireOuvert={editingPub?.id === pub.id || showEvolForm === pub.id}
			on:toggle={() => togglePub(pub.id)}>

			<svelte:fragment slot="actions">
				{#if $isCS}
					<button class="btn-icon-edit" aria-label="Modifier" title="Modifier"
						on:click|stopPropagation={() => startEdit(pub)}>✏️</button>
					<!--  DEUX points d'entrée : le geste se déclare ici, une fois. Le
					      formulaire le redemandait en pastilles alors que ce bouton
					      venait de le dire (#426). -->
					<button class="btn-icon" aria-label="Commenter" title="Commenter"
						on:click|stopPropagation={() => ouvrirEvolution(pub, 'commentaire')}>&#x1F4AC;</button>
					<button class="btn-icon" aria-label="Changer l’état" title="Changer l’état"
						on:click|stopPropagation={() => ouvrirEvolution(pub, 'etat')}>&#x1F504;</button>
					{#if pub.statut === 'resolu'}
						<button class="btn-icon" aria-label="Archiver" title="Archiver"
							on:click|stopPropagation={() => archivePub(pub)}>&#x1F4E6;</button>
					{/if}
				{/if}
				{#if $isAdmin}
					{#if (pub.envoyer_syndic || pub.envoyer_cs) && !pub.brouillon}
						<button class="btn-icon" aria-label="Renvoyer l'email" title="Renvoyer l'email au syndic/CS"
							on:click|stopPropagation={() => renvoyerPub(pub, 'email')}>✉️</button>
					{/if}
					{#if pub.partager_whatsapp && !pub.brouillon}
						<button class="btn-icon" aria-label="Renvoyer sur WhatsApp" title="Renvoyer l'annonce sur le groupe WhatsApp"
							on:click|stopPropagation={() => renvoyerPub(pub, 'whatsapp')}>💬</button>
					{/if}
					<button class="btn-icon" aria-label="Supprimer" title="Supprimer définitivement" style="color:var(--color-danger)"
						on:click|stopPropagation={() => deletePub(pub)}>🗑️</button>
				{/if}
			</svelte:fragment>

			<svelte:fragment slot="formulaire">
				{#if editingPub?.id === pub.id}
					<!--  ── Correction ──  LE MÊME formulaire qu'à la création, paramétré
					      par la publication (#433). Il y en avait un second, écrit à la
					      main sur 31 lignes, qui perdait cinq notions et en gagnait une
					      que la création n'avait pas. `{#key}` : le mode et les valeurs
					      initiales sont figés à la construction — passer d'une
					      publication à l'autre doit remonter le composant à neuf. -->
					{#key pub.id}
						<FormulaireActualite
							publication={pub}
							on:modifie={publicationModifiee}
							on:annule={() => (editingPub = null)}
						/>
					{/key}
				{:else if showEvolForm === pub.id}
					<!--  ── Commenter / changer l'état ──
					      `role="presentation"` dit que ce conteneur n'est qu'un relais :
					      il arrête la propagation pour que saisir dans le formulaire ne
					      referme pas la carte, il n'est pas lui-même interactif. Même
					      geste que `CarteTicket`, qui portait déjà le rôle — ici
					      l'avertissement d'accessibilité traînait depuis l'origine. -->
					<div class="evol-form" role="presentation"
						on:click|stopPropagation on:keydown|stopPropagation>
						{#key showEvolForm}
						<!--  ⚠️ Les pièces jointes sont DEUX sections, 7 et 8, jamais
						      fusionnées : c'est cet écran qui portait le mode « unifié »
						      d'`EvolForm`, et le mode a disparu avec son dernier appelant
						      (#433). *Une variante ajoutée pour accueillir un écart
						      existant ne factorise pas, elle entérine.* -->
						<EvolForm idPrefixe="pub-evol-{pub.id}"
							evolType={gesteEvol}
							statutOptions={STATUT_PUBLICATION_OPTIONS}
							statutLabels={STATUT_LABELS}
							currentStatut={pub.statut ?? ''}
							showNotifs={true}
							defaultPartagerWhatsapp={pub.partager_whatsapp ?? false}
							defaultEnvoyerSyndic={pub.envoyer_syndic ?? false}
							defaultEnvoyerCs={pub.envoyer_cs ?? false}
							showEmail={true}
							showFiles={true}
							saving={evolSaving}
							on:submit={(e) => addEvolFromForm(pub, e)}
							on:cancel={() => (showEvolForm = null)}
						/>
						{/key}
					</div>
				{/if}
			</svelte:fragment>

			<svelte:fragment slot="apres-corps">
				<!--  ── L'HISTORIQUE ──  Le fil était écrit à la main ici, sur 58
				      lignes : quatrième des six recopies relevées par #431, et déjà
				      divergente — « Voir les N *commentaires* plus anciens » là où les
				      tickets disent « entrées », un `<button>` habillé par six
				      déclarations en ligne, et une branche pour un type `correction`
				      que le serveur n'a JAMAIS écrit.
				      La rubrique porte tout cela une fois, avec ses styles (Svelte les
				      scope au composant qui rend le balisage — les laisser ici ne les
				      atteindrait pas). -->
				{#if pub.evolutions?.length}
					<div class="pub-fil">
						<RubriqueHistorique
							evolutions={pub.evolutions}
							statutLabels={STATUT_LABELS}
							peutModifier={$isCS}
							enEdition={editingEvolId}
							on:modifier={(e) => { editingEvolId = e.detail; editingEvolPubId = pub.id; }}
						>
							<svelte:fragment slot="edition" let:evol>
								{#key editingEvolId}
									<EvolForm idPrefixe="pub-evol-edit-{evol.id}"
										editMode={true}
										initialContenu={evol.contenu || ''}
										initialFichiers={fichiersDepuisUrls(evol.fichiers_urls)}
										showFiles={true}
										saving={editEvolSaving}
										on:submit={saveEvolEdit}
										on:cancel={() => { editingEvolId = null; editingEvolPubId = null; }}
									/>
								{/key}
							</svelte:fragment>
						</RubriqueHistorique>
					</div>
				{/if}
			</svelte:fragment>
		</CarteActualite>
	{/each}
{/if}

{#if !loading}
	<HistoriqueActualites />
{/if}

<style>
	/*  Le fil et son habillage vivent dans `RubriqueHistorique.svelte`, avec le
	    balisage qui les porte (#433). Ne reste ici que ce que CETTE page rend :
	    la marge qui sépare le fil de ce qu'il suit — le parent seul sait ce qu'il
	    y a au-dessus. */
	.pub-fil { margin-top: .9rem; }
	.evol-form { padding: .5rem 0; }

	/* Badges statut */
	:global(.badge-orange) { background: #fef3c7; color: #92400e; }
</style>
