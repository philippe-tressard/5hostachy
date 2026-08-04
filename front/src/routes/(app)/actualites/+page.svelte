<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import { onMount } from 'svelte';
	import { cibleDuHash, revelerCible } from '$lib/deepLink';
	import { isCS, isAdmin, currentUser, setUser } from '$lib/stores/auth';
	import { publications as pubsApi, uploads as uploadsApi, documents as docsApi, fichiersApi, ApiError, type Publication, auth as authApi } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import AlerteEpinglage from '$lib/components/AlerteEpinglage.svelte';
	import ImageUpload from '$lib/components/ImageUpload.svelte';
	import PiecesJointes from '$lib/components/PiecesJointes.svelte';
	import { fichiersDepuisUrls } from '$lib/fichiers';
	import RichEditor from '$lib/components/RichEditor.svelte';
	import PerimetrePicker from '$lib/components/PerimetrePicker.svelte';
	import DestinatairePicker from '$lib/components/DestinatairePicker.svelte';
	import { getPageConfig, configStore, siteNomStore } from '$lib/stores/pageConfig';
	import EvolForm from '$lib/components/EvolForm.svelte';
	import { safeHtml } from '$lib/sanitize';
	import { fmtDate2d as fmtDate, fmtDateLong, fmtDatetime2d as fmtDatetime, isNouveau } from '$lib/date';

	$: _pc = getPageConfig($configStore, 'actualites', { titre: 'Actualités', navLabel: 'Actualités', icone: 'newspaper', descriptif: 'Publications officielles du conseil syndical : informations importantes, travaux et actualités de la résidence.' });
	$: _siteNom = $siteNomStore;

	let pubList: Publication[] = [];
	$: compactPubs = pubList.length > 7;
	let loading = true;

	// ── Statut ────────────────────────────────────────────────────────────────
	const STATUT_LABELS: Record<string, string> = { publie: 'Publié', en_cours: 'En cours', resolu: 'Résolu', annule: 'Annulé' };
	const STATUT_BADGE: Record<string, string> = { publie: 'badge-blue', en_cours: 'badge-orange', resolu: 'badge-green', annule: 'badge-gray' };

	// ── Nouvelle publication (CS) ─────────────────────────────────────────────
	let showForm = false;
	let newTitre = '';
	let newContenu = '';
	let newUrgente = false;
	let newEpingle = false;
	let newBrouillon = false;
	let newPartagerWhatsapp = false;
	let newEnvoyerSyndic = false;
	let newEnvoyerCs = false;
	let newAnnonceHall = false;
	let newStatut: string = 'publie';
	let saving = false;
	let pendingImage: File | null = null;
	let pendingPreview: string | undefined;
	let uploadingImg = false;
	let pendingFiles: File[] = [];
	let pubFilesMap: Record<number, any[]> = {};
	let loadedFilesFor = new Set<number>();
	let fileInputKey = 0;
	let expandedPubs = new Set<number>();
	let expandedEvols = new Set<number>();

	// ── Historique (publications archivées) ─────────────────────────────────
	let archivedPubs: Publication[] = [];
	let archivedPubsLoaded = false;
	let historyExpanded = false;
	let expandedHistoryYears = new Set<number>();
	let expandedHistoryItems = new Set<number>();

	async function loadArchivedPubs() {
		if (archivedPubsLoaded) return;
		archivedPubsLoaded = true;
		try { archivedPubs = await pubsApi.list(true); } catch { /* silencieux */ }
	}

	$: if (historyExpanded) loadArchivedPubs();

	$: historyByYear = (() => {
		const groups = new Map<number, Publication[]>();
		for (const p of archivedPubs) {
			const year = new Date(p.mis_a_jour_le ?? p.cree_le).getFullYear();
			if (!groups.has(year)) groups.set(year, []);
			groups.get(year)!.push(p);
		}
		return [...groups.entries()].sort(([a], [b]) => b - a);
	})();

	function toggleHistoryItem(id: number) {
		expandedHistoryItems = expandedHistoryItems.has(id) ? new Set() : new Set([id]);
	}

	async function deleteArchivedPub(pub: Publication) {
		if (!confirm(`Supprimer définitivement « ${pub.titre} » ?`)) return;
		try {
			await pubsApi.delete(pub.id);
			archivedPubs = archivedPubs.filter(p => p.id !== pub.id);
			toast('success', 'Publication supprimée');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Impossible de supprimer');
		}
	}

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

	function handleFilesChange(e: Event) {
		const input = e.currentTarget as HTMLInputElement;
		pendingFiles = input.files ? Array.from(input.files) : [];
	}

	async function loadPubFiles(pubId: number) {
		if (loadedFilesFor.has(pubId)) return;
		loadedFilesFor.add(pubId);
		try {
			const docs = await docsApi.listByPublication(pubId);
			pubFilesMap = { ...pubFilesMap, [pubId]: docs };
		} catch { /* silencieux */ }
	}
	let newPerimetreCible: string[] = ['résidence'];
	let newPublicCible: string[] = ['résidents'];

	function handleImageChange(e: CustomEvent<File>) {
		pendingImage = e.detail;
		pendingPreview = URL.createObjectURL(e.detail);
	}

	onMount(async () => {
		try {
			pubList = await pubsApi.list();
			// Lien profond `#pub-<id>` (fil d'activité, notification, e-mail)
			const idPub = cibleDuHash('pub');
			if (idPub !== null) {
				expandedPubs = new Set([idPub]);
				revelerCible(`pub-${idPub}`);
			} else if (pubList.length > 0) {
				expandedPubs = new Set([pubList[0].id]);
			}
			// Persist last-seen timestamp server-side
			const now = new Date().toISOString();
			authApi.updateMe({ last_seen_actualites: now }).then((u: any) => setUser(u)).catch(() => {});
		} finally {
			loading = false;
		}
	});

	const richEmpty = (html: string) => !html || html.replace(/<[^>]+>/g, '').trim() === '';

	function perimètreLabel(items: string[]) {
		const map: Record<string, string> = {
			'résidence': 'Copropriété entière',
			'bat:1': 'Bât. 1', 'bat:2': 'Bât. 2', 'bat:3': 'Bât. 3', 'bat:4': 'Bât. 4',
			parking: 'Parking', cave: 'Cave', aful: 'AFUL',
		};
		return items.map(i => map[i] ?? i).join(' · ');
	}

	async function publish() {
		if (!newTitre.trim() || richEmpty(newContenu)) return;
		saving = true;
		try {
			// Image et pièces jointes sont envoyées après création : on retarde la publication
			// réelle pour que WhatsApp et l'affiche de hall disposent bien des visuels.
			const shouldPublishAfterImageUpload = !newBrouillon && (
				(!!pendingImage && (newPartagerWhatsapp || newAnnonceHall))
				|| (newAnnonceHall && pendingFiles.length > 0)
			);
			let pub = await pubsApi.create({
				titre: newTitre, contenu: newContenu, urgente: newUrgente, epingle: newEpingle,
				perimetre_cible: newPerimetreCible, public_cible: newPublicCible,
				brouillon: shouldPublishAfterImageUpload ? true : newBrouillon,
				statut: newStatut || 'publie',
				partager_whatsapp: newPartagerWhatsapp,
				envoyer_syndic: newEnvoyerSyndic,
				envoyer_cs: newEnvoyerCs,
				annonce_hall: newAnnonceHall,
			});
			if (pendingImage) {
				uploadingImg = true;
				try {
					const { url } = await uploadsApi.publication(pub.id, pendingImage);
					pub.image_url = url;
				} finally { uploadingImg = false; }
			}
			if (pendingFiles.length > 0) {
				for (const f of pendingFiles) {
					try { await docsApi.uploadForPublication(f.name, pub.id, f); } catch { /* ignoré */ }
				}
			}
			if (shouldPublishAfterImageUpload) {
				pub = await pubsApi.update(pub.id, { brouillon: false });
			}
			pubList = [pub, ...pubList];
			showForm = false;
			newTitre = ''; newContenu = ''; newUrgente = false; newEpingle = false;
			newBrouillon = false; newStatut = 'publie'; newPartagerWhatsapp = false; newEnvoyerSyndic = false; newEnvoyerCs = false; newAnnonceHall = false;
			newPerimetreCible = ['résidence'];
			pendingImage = null; pendingPreview = undefined;
			pendingFiles = []; fileInputKey++;
			toast('success', pub.brouillon ? 'Brouillon enregistré' : 'Publication créée');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally { saving = false; }
	}

	async function archivePub(pub: Publication) {
		if (!confirm(`Archiver « ${pub.titre} » ?`)) return;
		try {
			await pubsApi.archive(pub.id);
			pubList = pubList.filter((p) => p.id !== pub.id);
			toast('success', 'Publication archivée');
		} catch (e: any) {
			toast('error', e instanceof ApiError ? e.message : 'Impossible d\u2019archiver');
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

	async function renvoyerEmailPub(pub: Publication) {
		if (!confirm(`Renvoyer l'email de « ${pub.titre} » au syndic/CS ?`)) return;
		try {
			await pubsApi.renvoyerEmail(pub.id);
			toast('success', 'Email renvoyé');
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

<div class="page-header">
	<h1 style="display:flex;align-items:center;gap:.4rem"><Icon name={_pc.icone || 'newspaper'} size={20} />{_pc.titre}</h1>
	<div style="display:flex;gap:.5rem;align-items:center">
		{#if $isCS}
			<button class="btn btn-primary page-header-btn" on:click={() => (showForm = !showForm)}>
				{showForm ? '✕ Annuler' : '+ Nouvelle publication'}
			</button>
		{/if}
	</div>
</div>
<div class="page-subtitle">{@html safeHtml(_pc.descriptif)}</div>

{#if showForm && $isCS}
	<div class="card" style="margin-bottom:1.5rem">
		<h2 style="font-size:1rem;font-weight:600;margin-bottom:1rem">Nouvelle publication</h2>
		<form on:submit|preventDefault={publish}>
			<div class="field">
				<label for="new-titre">Titre *</label>
				<input id="new-titre" type="text" bind:value={newTitre} required maxlength="200" />
			</div>
			<div class="field">
				<label id="perimetre-label">Périmètre *</label>
				<PerimetrePicker bind:value={newPerimetreCible} />
			</div>
			<div class="field">
				<label>Destinataires *</label>
				<DestinatairePicker bind:value={newPublicCible} />
			</div>
			<div class="field">
				<label for="actualite-contenu">Contenu *</label>
				<RichEditor id="actualite-contenu" bind:value={newContenu} placeholder="Contenu de l'actualité…" minHeight="120px" />
			</div>
			<div class="field">
				<label for="actualite-photo">Photo (optionnel)</label>
				<ImageUpload id="actualite-photo" currentUrl={pendingPreview} placeholder="&#x1F5BC;️" label="Ajouter une photo"
					shape="rect" previewSize="200px" uploading={uploadingImg} on:change={handleImageChange} />
			</div>
			<div class="field">
				<label>Pièces jointes (optionnel)</label>
				{#key fileInputKey}
					<input type="file" multiple accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png,.zip,.txt" on:change={handleFilesChange} style="font-size:.85rem" />
				{/key}
				{#if pendingFiles.length > 0}
					<span style="font-size:.8rem;color:var(--color-text-muted)">📎 {pendingFiles.length} fichier{pendingFiles.length > 1 ? 's' : ''} sélectionné{pendingFiles.length > 1 ? 's' : ''}</span>
				{/if}
			</div>
			<div class="field">
				<label for="new-statut">État</label>
				<select id="new-statut" bind:value={newStatut}>
					<option value="publie">&#x1F535; Publié</option>
					<option value="en_cours">&#x1F7E1; En cours</option>
					<option value="resolu">&#x1F7E2; Résolu</option>
					<option value="annule">⚫ Annulé</option>
				</select>
			</div>
			<div style="display:flex;gap:1.5rem;flex-wrap:wrap;margin-bottom:1rem">
				<label class="checkbox-field"><input type="checkbox" bind:checked={newEpingle} /> Épingler</label>
				<label class="checkbox-field"><input type="checkbox" bind:checked={newUrgente} /> &#x1F6A8; Urgent</label>
				<label class="checkbox-field"><input type="checkbox" bind:checked={newBrouillon} /> ✏️ Brouillon (invisible pour les résidents)</label>
			</div>
			<AlerteEpinglage coche={newEpingle} />
			<div style="margin-bottom:1rem;display:flex;flex-wrap:wrap;gap:1rem">
				<label class="checkbox-field">
					<input type="checkbox" bind:checked={newPartagerWhatsapp} />
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="#25D366" style="flex-shrink:0;vertical-align:middle" aria-label="WhatsApp">
						<path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51a12.66 12.66 0 0 0-.57-.01c-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 0 1-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 0 1-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 0 1 2.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0 0 12.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 0 0 5.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 0 0-3.48-8.413Z"/>
					</svg>
					<span>Partager sur le groupe</span>
				</label>
				<label class="checkbox-field">
					<input type="checkbox" bind:checked={newEnvoyerSyndic} />
					<span style="font-size:1.1em;line-height:1">✉️</span>
					<span>Envoyer au syndic</span>
				</label>
				<label class="checkbox-field">
					<input type="checkbox" bind:checked={newEnvoyerCs} />
					<span style="font-size:1.1em;line-height:1">✉️</span>
					<span>Envoyer au Conseil Syndical</span>
				</label>
				<label class="checkbox-field" title="Génère l'affiche PDF à afficher dans le hall et l'envoie au CS du périmètre">
					<input type="checkbox" bind:checked={newAnnonceHall} />
					<span style="font-size:1.1em;line-height:1">&#x1F4C4;</span>
					<span>Créer une annonce Hall</span>
				</label>
			</div>
			{#if newAnnonceHall}
				<p style="font-size:.78rem;color:var(--color-text-muted);margin:-.5rem 0 1rem;line-height:1.45">
					&#x1F4C4; Une affiche PDF sera générée à partir du titre, du contenu, du périmètre et de
					l'image de cette actualité, puis envoyée aux membres du CS du périmètre. Elle sera
					consultable dans <strong>Espace CS → Annonces Hall</strong>. Un brouillon ne déclenche
					rien tant qu'il n'est pas publié.
				</p>
			{/if}
			<div class="form-actions">
				<button type="submit" class="btn btn-primary" disabled={saving || uploadingImg}>
					{saving ? 'Envoi…' : (newBrouillon ? 'Enregistrer brouillon' : 'Publier')}
				</button>
			</div>
		</form>
	</div>
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
		<div class="pub-expand" class:expanded class:urgent={pub.urgente} class:brouillon={pub.brouillon} class:epingle={pub.epingle} id="pub-{pub.id}"
			role="button" tabindex="0"
			on:click={() => togglePub(pub.id)}
			on:keydown={(e) => { if ((e.key === 'Enter' || e.key === ' ') && e.target === e.currentTarget) togglePub(pub.id); }}>

			{#if pub.epingle}<span class="pin-badge">&#x1F4CC;</span>{/if}

			<div class="pub-row">
				<div class="pub-row-inner">
					{#if pub.brouillon}<span class="badge badge-gray" style="flex-shrink:0">✏️ Brouillon</span>{/if}
					<span class="pub-row-titre">{pub.titre}
					{#if isNouveau(pub.cree_le, pub.mis_a_jour_le)}<span class="badge badge-gray" style="margin-left:.5em;font-size:.82em;font-weight:500;vertical-align:middle">New</span>{/if}
					</span>
					{#if pub.statut && pub.statut !== 'publie'}<span class="badge {STATUT_BADGE[pub.statut] ?? 'badge-gray'}" style="flex-shrink:0">{STATUT_LABELS[pub.statut] ?? pub.statut}</span>{/if}
{#if pub.perimetre_cible && !(pub.perimetre_cible.length === 1 && pub.perimetre_cible[0] === 'résidence')}<span class="badge badge-gray" style="flex-shrink:0">&#x1F539; {perimètreLabel(pub.perimetre_cible)}</span>{/if}
				</div>
				<div class="pub-row-right">
					<span class="pub-row-date">{fmtDate(pub.mis_a_jour_le ?? pub.cree_le)}</span>
					{#if $isCS}
						<button class="btn-icon-edit" aria-label="Modifier" title="Modifier"
							on:click|stopPropagation={() => startEdit(pub)}>✏️</button>
					<button class="btn-icon" aria-label="Ajouter un commentaire / changer état" title="Commenter / état"
						on:click|stopPropagation={() => { showEvolForm = pub.id; editingPub = null; expandedPubs = new Set([pub.id]); }}>&#x1F4AC;</button>

					{#if pub.statut === 'resolu'}
					<button class="btn-icon" aria-label="Archiver" title="Archiver"
						on:click|stopPropagation={() => archivePub(pub)}>&#x1F4E6;</button>
					{/if}
					{/if}				{#if $isAdmin}
				{#if (pub.envoyer_syndic || pub.envoyer_cs) && !pub.brouillon}
				<button class="btn-icon" aria-label="Renvoyer l'email" title="Renvoyer l'email au syndic/CS"
					on:click|stopPropagation={() => renvoyerEmailPub(pub)}>✉️</button>
				{/if}
				<button class="btn-icon" aria-label="Supprimer" title="Supprimer définitivement" style="color:var(--color-danger)"
					on:click|stopPropagation={() => deletePub(pub)}>🗑️</button>
				{/if}					<span class="chevron" class:open={expanded}>›</span>
				</div>
			</div>

			{#if !expanded && !compactPubs}
				<div class="pub-preview rich-content clamp-5">{@html safeHtml(pub.contenu)}</div>
			{/if}

			{#if expanded}
				<div class="pub-body" on:keydown|stopPropagation>

					{#if editingPub?.id === pub.id}
						<!-- ── Formulaire d'édition ── -->
						<form on:submit|preventDefault={saveEdit} on:click|stopPropagation>
							<div class="field">
								<label for="edit-titre-{pub.id}">Titre *</label>
								<input id="edit-titre-{pub.id}" type="text" bind:value={editTitre} required maxlength="200" />
							</div>
							<div class="field">
								<label for="edit-contenu-{pub.id}">Contenu *</label>
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
							<div style="display:flex;gap:1.5rem;flex-wrap:wrap;margin-bottom:.75rem">
								<label class="checkbox-field"><input type="checkbox" bind:checked={editEpingle} /> Épingler</label>
								<label class="checkbox-field"><input type="checkbox" bind:checked={editUrgente} /> &#x1F6A8; Urgent</label>
								<label class="checkbox-field"><input type="checkbox" bind:checked={editBrouillon} /> ✏️ Brouillon</label>
							</div>
							<AlerteEpinglage coche={editEpingle} dejaEpingle={editEpingleInitial} />
							<div class="form-actions" style="gap:.5rem">
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

				{:else}
						<!-- ── Corps normal ── -->
						{#if pub.image_url}
							<img class="pub-img" src={pub.image_url} alt={pub.titre} />
						{/if}
						<div class="rich-content" style="font-size:.875rem;line-height:1.6;margin-bottom:.5rem">{@html safeHtml(pub.contenu)}</div>
						{#if pubFilesMap[pub.id]?.length > 0}
							<div class="pub-attachments">
								{#each pubFilesMap[pub.id] as doc}
									<a href={docsApi.downloadUrl(doc.id)} target="_blank" class="pub-attachment-link">
										📎 {doc.titre || doc.fichier_nom}
									</a>
								{/each}
							</div>
						{/if}
						<small style="color:var(--color-text-muted);font-size:.78rem">
						{#if pub.mis_a_jour_le}Mise à jour le {fmtDateLong(pub.mis_a_jour_le)}{:else}Publié le {fmtDateLong(pub.cree_le)}{/if}{#if pub.auteur_nom} · {pub.auteur_nom}{/if}
						</small>

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
					{/if}
				</div>
			{/if}
		</div>
	{/each}
{/if}

{#if !loading}
	<div class="history-section">
		<button class="history-header" on:click={() => (historyExpanded = !historyExpanded)} aria-expanded={historyExpanded}>
			<span class="history-title">&#x1F4C1; Historique</span>
			{#if archivedPubsLoaded}<span class="history-count">{archivedPubs.length}</span>{/if}
			<span class="history-chevron">{historyExpanded ? '▲' : '▼'}</span>
		</button>
		{#if historyExpanded}
			<div class="history-content">
				{#if archivedPubsLoaded && archivedPubs.length === 0}
					<p style="color:var(--color-text-muted);font-size:.875rem;margin:.5rem 0 0">Aucune publication archivée.</p>
				{:else}
					{#each historyByYear as [year, yearPubs]}
						<div class="history-year">
							<button class="history-year-header" on:click|stopPropagation={() => { if (expandedHistoryYears.has(year)) { expandedHistoryYears.delete(year); } else { expandedHistoryYears.add(year); } expandedHistoryYears = expandedHistoryYears; }} aria-expanded={expandedHistoryYears.has(year)}>
								<span class="history-year-label">{year}</span>
								<span class="history-count" style="font-size:.7rem">{yearPubs.length}</span>
								<span class="history-chevron">{expandedHistoryYears.has(year) ? '▲' : '▼'}</span>
							</button>
							{#if expandedHistoryYears.has(year)}
								{#each yearPubs as pub (pub.id)}
									{@const expanded = expandedHistoryItems.has(pub.id)}
									<div class="pub-expand history-item" class:expanded id="hist-pub-{pub.id}"
										role="button" tabindex="0"
										on:click={() => toggleHistoryItem(pub.id)}
										on:keydown={(e) => { if ((e.key === 'Enter' || e.key === ' ') && e.target === e.currentTarget) toggleHistoryItem(pub.id); }}>
										<div class="pub-row">
											<div class="pub-row-inner">
												<span class="pub-row-titre">{pub.titre}</span>
												{#if pub.statut && pub.statut !== 'publie'}<span class="badge {STATUT_BADGE[pub.statut] ?? 'badge-gray'}" style="flex-shrink:0">{STATUT_LABELS[pub.statut] ?? pub.statut}</span>{/if}
												{#if pub.perimetre_cible && !(pub.perimetre_cible.length === 1 && pub.perimetre_cible[0] === 'résidence')}<span class="badge badge-gray" style="flex-shrink:0">&#x1F539; {perimètreLabel(pub.perimetre_cible)}</span>{/if}
											</div>
											<div class="pub-row-right">
												<span class="pub-row-date">{fmtDate(pub.mis_a_jour_le ?? pub.cree_le)}</span>
												{#if $isAdmin}
													<button class="btn-icon" aria-label="Supprimer" title="Supprimer définitivement" style="color:var(--color-danger)"
														on:click|stopPropagation={() => deleteArchivedPub(pub)}>🗑️</button>
												{/if}
												<span class="chevron" class:open={expanded}>›</span>
											</div>
										</div>
										{#if !expanded}
											<div class="pub-preview rich-content clamp-5">{@html safeHtml(pub.contenu)}</div>
										{:else}
											<div class="pub-body" on:click|stopPropagation on:keydown|stopPropagation>
												{#if pub.image_url}<img class="pub-img" src={pub.image_url} alt={pub.titre} />{/if}
												<div class="rich-content" style="font-size:.875rem;line-height:1.6;margin-bottom:.5rem">{@html safeHtml(pub.contenu)}</div>
												<small style="color:var(--color-text-muted);font-size:.78rem">
												{#if pub.mis_a_jour_le}Mise à jour le {fmtDateLong(pub.mis_a_jour_le)}{:else}Publié le {fmtDateLong(pub.cree_le)}{/if}{#if pub.auteur_nom} · {pub.auteur_nom}{/if}
												</small>
											</div>
										{/if}
									</div>
								{/each}
							{/if}
						</div>
					{/each}
				{/if}
			</div>
		{/if}
	</div>
{/if}

<style>
	.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
	.page-header h1 { font-size: 1.4rem; font-weight: 700; }

	/* Publication expansible */
	.pub-expand { margin-bottom: .3rem; border-left: 4px solid var(--color-border); border-radius: var(--radius); overflow: visible; position: relative; background: var(--color-surface); transition: border-left-color .12s; }
	.pub-expand:hover, .pub-expand.expanded { border-left-color: var(--color-primary); }
	.pub-expand.urgent { border-left-color: var(--color-danger); }
	.pub-expand.brouillon { opacity: .7; border-left-style: dashed; }
	.pub-expand.epingle { margin-top: 10px; }
	.pin-badge { position: absolute; top: -9px; left: 8px; display: inline-flex; align-items: center; background: var(--color-primary); color: #fff; font-size: .65rem; padding: .1rem .35rem; border-radius: 8px; line-height: 1.6; z-index: 1; pointer-events: none; }

	.pub-row { display: flex; align-items: center; gap: .6rem; padding: .6rem .9rem; cursor: pointer; user-select: none; transition: background .12s; }
	.pub-row:hover { background: var(--color-bg); }
	.pub-row-inner { display: flex; align-items: center; gap: .4rem; flex: 1; min-width: 0; overflow: hidden; }
	.pub-row-titre { font-size: .9rem; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.pub-row-right { display: flex; align-items: center; gap: .3rem; flex-shrink: 0; }
	.pub-row-date { font-size: .78rem; color: var(--color-text-muted); margin-right: .3rem; white-space: nowrap; }

	.pub-preview { padding: .4rem 1rem .6rem; font-size: .875rem; line-height: 1.6; color: var(--color-text-muted); }
	.pub-preview :global(p) { margin: 0 0 .4em; }
	.pub-body { padding: .75rem 1rem 1rem; border-top: 1px solid var(--color-border); }
	.pub-img { width: 100%; max-height: 280px; object-fit: cover; display: block; border-radius: calc(var(--radius) - 2px); margin-bottom: .75rem; }
	.pub-attachments { display: flex; flex-wrap: wrap; gap: .4rem; margin: .5rem 0 .25rem; }
	.pub-attachment-link { display: inline-flex; align-items: center; gap: .3rem; font-size: .82rem; padding: .25rem .55rem; background: var(--color-bg); border: 1px solid var(--color-border); border-radius: 4px; color: var(--color-primary); text-decoration: none; }
	.pub-attachment-link:hover { background: var(--color-border); }

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

	.chevron { font-size: 1.1rem; color: var(--color-text-muted); transition: transform .15s; display: inline-block; line-height: 1; }
	.chevron.open { transform: rotate(90deg); }

	.checkbox-field { display: flex; align-items: center; gap: .4rem; font-size: .875rem; cursor: pointer; }
	.form-actions { display: flex; justify-content: flex-end; }

	/* Section historique */
	.history-section { margin-top: 2rem; padding-top: 1.5rem; border-top: 2px solid var(--color-border); }
	.history-header { display: flex; align-items: center; gap: .5rem; width: 100%; background: none; border: none; padding: 0; cursor: pointer; font-size: 1rem; font-weight: 600; color: var(--color-text); text-align: left; }
	.history-header:hover { color: var(--color-primary); }
	.history-title { flex: 1; }
	.history-count { display: inline-flex; align-items: center; justify-content: center; background: var(--color-primary); color: white; font-size: .75rem; font-weight: 700; padding: .15rem .5rem; border-radius: 12px; min-width: 1.5rem; }
	.history-chevron { font-size: .8rem; color: var(--color-text-muted); flex-shrink: 0; transition: transform .2s; }
	.history-header[aria-expanded="true"] .history-chevron { transform: scaleY(-1); }
	.history-content { margin-top: 1rem; display: flex; flex-direction: column; gap: 0; }
	.history-year { margin-bottom: .5rem; }
	.history-year-header { display: flex; align-items: center; gap: .5rem; width: 100%; background: var(--color-bg); border: 1px solid var(--color-border); border-radius: var(--radius); padding: .5rem .75rem; cursor: pointer; font-size: .9rem; font-weight: 600; color: var(--color-text); margin-bottom: .3rem; }
	.history-year-header:hover { border-color: var(--color-primary); color: var(--color-primary); }
	.history-year-label { flex: 1; text-align: left; }
	.history-item { opacity: .8; transition: opacity .15s; margin-bottom: .3rem; }
	.history-item:hover, .history-item.expanded { opacity: 1; }
</style>

