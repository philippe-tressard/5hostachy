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
	import OptionsPublication from '$lib/components/OptionsPublication.svelte';
	import PiecesJointes from '$lib/components/PiecesJointes.svelte';
	import { fichiersDepuisUrls } from '$lib/fichiers';
	import RichEditor from '$lib/components/RichEditor.svelte';
	import { getPageConfig, configStore, siteNomStore } from '$lib/stores/pageConfig';
	import { defautsDePage } from '$lib/pages';
	import EvolForm from '$lib/components/EvolForm.svelte';
	import { safeHtml } from '$lib/sanitize';
	import { STATUT_LABELS, richEmpty } from '$lib/publications';
	import { fmtDatetime2d as fmtDatetime } from '$lib/date';

	$: _pc = getPageConfig($configStore, 'actualites', defautsDePage('actualites'));
	$: _siteNom = $siteNomStore;

	let pubList: Publication[] = [];
	$: compactPubs = pubList.length > 7;
	let loading = true;

	let showForm = false;
	let pubFilesMap: Record<number, any[]> = {};
	let loadedFilesFor = new Set<number>();
	let expandedPubs = new Set<number>();
	let expandedEvols = new Set<number>();

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

	// ── Édition ───────────────────────────────────────────────────────────────
	let editingPub: Publication | null = null;
	let editTitre = '';
	let editContenu = '';
	let editUrgente = false;
	let editEpingle = false;
	// Épinglage à l'ouverture du formulaire : évite que l'avertissement de
	// plafond compte une seconde fois une publication déjà épinglée.
	let editEpingleInitial = false;
	let editStatut = '';
	let editBrouillon = false;
	let editConfidentiel = false;
	let editSaving = false;

	// ── Évolutions ──────────────────────────────────────────────────────
	let showEvolForm: number | null = null;  // pub.id ouvert
	let evolSaving = false;
	let editingEvolId: number | null = null;
	let editingEvolPubId: number | null = null;
	let editEvolSaving = false;

	const PUB_STATUT_OPTIONS = [
		{ value: 'publie',   label: '🔵 Publié' },
		{ value: 'en_cours', label: '🟡 En cours' },
		{ value: 'resolu',   label: '🟢 Résolu' },
		{ value: 'annule',   label: '⚫ Annulé' },
	];

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
		editTitre = pub.titre;
		editContenu = pub.contenu;
		editUrgente = pub.urgente;
		editEpingle = pub.epingle;
		editEpingleInitial = pub.epingle;
		editStatut = pub.statut ?? 'publie';
		editBrouillon = pub.brouillon;
		editConfidentiel = pub.confidentiel ?? false;
		showEvolForm = null;
		expandedPubs = new Set([pub.id]);
	}

	function cancelEdit() { editingPub = null; }

	async function saveEdit() {
		if (!editingPub || !editTitre.trim() || richEmpty(editContenu)) return;
		editSaving = true;
		try {
			const updated = await pubsApi.update(editingPub.id, {
				titre: editTitre, contenu: editContenu,
				urgente: editUrgente, epingle: editEpingle,
				statut: editStatut || null,
				brouillon: editBrouillon,
				confidentiel: editConfidentiel,
			});
			pubList = pubList.map(p => p.id === updated.id ? updated : p);
			editingPub = null;
			toast('success', 'Publication mise à jour');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally { editSaving = false; }
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
					<button class="btn-icon" aria-label="Ajouter un commentaire / changer état" title="Commenter / état"
						on:click|stopPropagation={() => { showEvolForm = pub.id; editingPub = null; expandedPubs = new Set([pub.id]); }}>&#x1F4AC;</button>
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
					<!-- ── Formulaire d'édition ── -->
					<form on:submit|preventDefault={saveEdit} on:click|stopPropagation>
						<div class="field">
							<label for="edit-titre-{pub.id}">Titre *</label>
							<input id="edit-titre-{pub.id}" type="text" bind:value={editTitre} required maxlength="200" />
						</div>
						<div class="field">
							<label for="edit-contenu-{pub.id}">Description *</label>
							<RichEditor bind:value={editContenu} minHeight="100px" />
						</div>
						<div class="field">
							<label for="edit-statut-{pub.id}">État</label>
							<select id="edit-statut-{pub.id}" bind:value={editStatut}>
								<option value="publie">&#x1F535; Publié</option>
								<option value="en_cours">&#x1F7E1; En cours</option>
								<option value="resolu">&#x1F7E2; Résolu</option>
								<option value="annule">⚫ Annulé</option>
							</select>
						</div>
						<OptionsPublication
							perimetreCible={pub.perimetre_cible}
							dejaEpingle={editEpingleInitial}
							bind:epingle={editEpingle}
							bind:urgente={editUrgente}
							bind:brouillon={editBrouillon}
							bind:confidentiel={editConfidentiel}
						/>
						<div class="form-actions">
							<button type="button" class="btn btn-outline" on:click={cancelEdit}>Annuler</button>
							<button type="submit" class="btn btn-primary" disabled={editSaving}>{editSaving ? 'Enregistrement…' : 'Enregistrer'}</button>
						</div>
					</form>
				{:else if showEvolForm === pub.id}
					<!-- ── Formulaire d'évolution ── -->
					<div class="evol-form" on:click|stopPropagation on:keydown|stopPropagation>
						<h4 style="font-size:.875rem;font-weight:600;margin:0 0 .6rem">Ajouter une évolution</h4>
						{#key showEvolForm}
						<EvolForm
							idPrefixe="pub-evol-{pub.id}"
							statutOptions={PUB_STATUT_OPTIONS}
							statutLabels={STATUT_LABELS}
							currentStatut={pub.statut ?? ''}
							showNotifs={true}
							defaultPartagerWhatsapp={pub.partager_whatsapp ?? false}
							defaultEnvoyerSyndic={pub.envoyer_syndic ?? false}
							defaultEnvoyerCs={pub.envoyer_cs ?? false}
							showEmail={true}
							showFiles={true}
							separatePhotosAndDocs={false}
							saving={evolSaving}
							on:submit={(e) => addEvolFromForm(pub, e)}
							on:cancel={() => (showEvolForm = null)}
						/>
						{/key}
					</div>
				{/if}
			</svelte:fragment>

			<svelte:fragment slot="apres-corps">
				<!-- ── Évolutions / historique ── -->
				{#if pub.evolutions && pub.evolutions.length > 0}
					{@const evolsSorted = [...pub.evolutions].sort((a, b) => new Date(b.cree_le).getTime() - new Date(a.cree_le).getTime())}
					{@const evolCompact = evolsSorted.length > 7 && !expandedEvols.has(pub.id)}
					{@const evolsVisible = evolCompact ? evolsSorted.slice(0, 5) : evolsSorted}
					<div class="evol-list">
						{#each evolsVisible as evol, i (evol.id)}
							{#if i > 0}<hr class="evol-sep" />{/if}
							<div class="evol-item evol-{evol.type}">
								<span class="evol-icon">
									{#if evol.type === 'etat'}&#x1F504;{:else if evol.type === 'correction'}✏️{:else}&#x1F4AC;{/if}
								</span>
								<div class="evol-body">
									<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:.5rem">
										<span class="evol-meta">{fmtDatetime(evol.cree_le)}{#if evol.auteur_nom} · {evol.auteur_nom}{/if}</span>
										{#if (evol.type === 'commentaire' || (evol.type === 'etat' && evol.contenu)) && $isCS && editingEvolId !== evol.id}
											<button type="button" on:click|stopPropagation={() => { editingEvolId = evol.id; editingEvolPubId = pub.id; }}
												style="border:1px solid var(--color-border);background:var(--color-bg-alt);color:var(--color-text);cursor:pointer;padding:.15rem .4rem;font-size:.75rem;flex-shrink:0;border-radius:5px;line-height:1.4">✏️ Modifier</button>
										{/if}
									</div>
									{#if evol.type === 'etat'}
										<span class="evol-text">
											Statut : <strong>{STATUT_LABELS[evol.ancien_statut ?? ''] || 'Aucun'}</strong> → <strong>{STATUT_LABELS[evol.nouveau_statut ?? ''] || evol.nouveau_statut}</strong>
										</span>
									{/if}
									{#if evol.type === 'commentaire' || (evol.type === 'etat' && editingEvolId === evol.id)}
										<div style="margin:.4rem 0;border:1px solid var(--color-border);border-radius:8px;padding:.75rem;background:var(--color-bg)" on:click|stopPropagation on:keydown|stopPropagation>
											{#key editingEvolId}
											<EvolForm
												idPrefixe="pub-evol-edit-{evol.id}"
												editMode={true}
												initialContenu={evol.contenu || ''}
												initialFichiers={fichiersDepuisUrls(evol.fichiers_urls)}
												showFiles={true}
												separatePhotosAndDocs={false}
												saving={editEvolSaving}
												on:submit={saveEvolEdit}
												on:cancel={() => { editingEvolId = null; editingEvolPubId = null; }}
											/>
											{/key}
										</div>
									{:else if evol.contenu}
										<div class="evol-text rich-content" style="font-size:.875rem">{@html safeHtml(evol.contenu)}</div>
									{/if}
									{#if (evol.fichiers_urls?.length ?? 0) > 0 && editingEvolId !== evol.id}
										<div style="margin-top:.3rem">
											<PiecesJointes urls={evol.fichiers_urls} size={72} compact />
										</div>
									{/if}
								</div>
							</div>
						{/each}
						{#if evolCompact}
							<hr class="evol-sep" />
							<button class="evol-more" on:click|stopPropagation={() => { expandedEvols.add(pub.id); expandedEvols = expandedEvols; }}>
								Voir les {evolsSorted.length - 5} commentaires plus anciens
							</button>
						{/if}
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
	/* Évolutions */
	.evol-list { margin-top: .9rem; border: 1px solid var(--color-border); border-radius: 6px; overflow: hidden; }
	.evol-sep { margin: 0; border: none; border-top: 1px solid var(--color-border); }
	.evol-item { display: flex; gap: .5rem; padding: .5rem .75rem; font-size: .82rem; }
	.evol-icon { flex-shrink: 0; font-size: .9rem; margin-top: .1rem; }
	.evol-body { display: flex; flex-direction: column; gap: .15rem; }
	.evol-meta { font-size: .75rem; color: var(--color-text-muted); }
	.evol-text { color: var(--color-text); line-height: 1.5; }
	.evol-etat { background: #f0f9ff; }
	.evol-correction { background: #fefce8; }
	.evol-form { padding: .5rem 0; }
	.evol-more { width: 100%; background: none; border: none; padding: .45rem; font-size: .8rem; color: var(--color-primary); cursor: pointer; text-align: center; }
	.evol-more:hover { background: var(--color-bg); }

	/* Badges statut */
	:global(.badge-orange) { background: #fef3c7; color: #92400e; }
</style>
