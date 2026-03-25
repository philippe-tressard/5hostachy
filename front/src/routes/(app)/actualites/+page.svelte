<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import { onMount } from 'svelte';
	import { isCS, isAdmin, currentUser, setUser } from '$lib/stores/auth';
	import { publications as pubsApi, uploads as uploadsApi, ApiError, type Publication, auth as authApi } from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import ImageUpload from '$lib/components/ImageUpload.svelte';
	import RichEditor from '$lib/components/RichEditor.svelte';
	import { getPageConfig, configStore, siteNomStore } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';

	$: _pc = getPageConfig($configStore, 'actualites', { titre: 'Actualités', navLabel: 'Actualités', icone: 'newspaper', descriptif: 'Publications officielles du conseil syndical : informations importantes, travaux et actualités de la résidence.' });
	$: _siteNom = $siteNomStore;

	let pubList: Publication[] = [];
	$: compactPubs = pubList.length > 7;
	let loading = true;

	// ── Statut ────────────────────────────────────────────────────────────────
	const STATUT_LABELS: Record<string, string> = { en_cours: 'En cours', resolu: 'Résolu', annule: 'Annulé' };
	const STATUT_BADGE: Record<string, string> = { en_cours: 'badge-orange', resolu: 'badge-green', annule: 'badge-gray' };

	// ── Nouvelle publication (CS) ─────────────────────────────────────────────
	let showForm = false;
	let newTitre = '';
	let newContenu = '';
	let newUrgente = false;
	let newEpingle = false;
	let newBrouillon = false;
	let newPartagerWhatsapp = false;
	let newStatut: string = '';
	let saving = false;
	let pendingImage: File | null = null;
	let pendingPreview: string | undefined;
	let uploadingImg = false;
	let newPerimetre: 'résidence' | 'specifique' = 'résidence';
	let newLieux = new Set<string>();

	function perimetreCibleValue() {
		if (newPerimetre === 'résidence') return ['résidence'];
		return newLieux.size > 0 ? [...newLieux] : ['résidence'];
	}

	function handleImageChange(e: CustomEvent<File>) {
		pendingImage = e.detail;
		pendingPreview = URL.createObjectURL(e.detail);
	}

	onMount(async () => {
		try {
			pubList = await pubsApi.list();
			if (pubList.length > 0) { expandedPubs = new Set([pubList[0].id]); }
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
			parking: 'Parking', cave: 'Cave',
		};
		return items.map(i => map[i] ?? i).join(' · ');
	}

	function fmtDate(d: string) {
		return new Date(d).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' });
	}
	function fmtDateLong(d: string) {
		return new Date(d).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });
	}
	function fmtDatetime(d: string) {
		return new Date(d).toLocaleString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
	}

	async function publish() {
		if (!newTitre.trim() || richEmpty(newContenu)) return;
		saving = true;
		try {
			const shouldPublishAfterImageUpload = !!pendingImage && newPartagerWhatsapp && !newBrouillon;
			let pub = await pubsApi.create({
				titre: newTitre, contenu: newContenu, urgente: newUrgente, epingle: newEpingle,
				perimetre_cible: perimetreCibleValue(), public_cible: ['résidents'],
				brouillon: shouldPublishAfterImageUpload ? true : newBrouillon,
				statut: newStatut || null,
				partager_whatsapp: newPartagerWhatsapp,
			});
			if (pendingImage) {
				uploadingImg = true;
				try {
					const { url } = await uploadsApi.publication(pub.id, pendingImage);
					pub.image_url = url;
				} finally { uploadingImg = false; }
			}
			if (shouldPublishAfterImageUpload) {
				pub = await pubsApi.update(pub.id, { brouillon: false });
			}
			pubList = [pub, ...pubList];
			showForm = false;
			newTitre = ''; newContenu = ''; newUrgente = false; newEpingle = false;
			newBrouillon = false; newStatut = ''; newPartagerWhatsapp = false;
			newPerimetre = 'résidence'; newLieux = new Set();
			pendingImage = null; pendingPreview = undefined;
			toast('success', pub.brouillon ? 'Brouillon enregistré' : 'Publication créée');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally { saving = false; }
	}

	async function archivePub(pub: Publication) {
		if (!confirm(`Archiver « ${pub.titre} » ?`)) return;
		try {
			await pubsApi.archive(pub.id);
			pubList = pubList.filter((p) => p.id !== pub.id);
			toast('success', 'Publication archivée');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Impossible d\u2019archiver');
		}
	}

	async function deletePub(pub: Publication) {
		if (!confirm(`Supprimer définitivement « ${pub.titre} » ?`)) return;
		try {
			await pubsApi.delete(pub.id);
			pubList = pubList.filter((p) => p.id !== pub.id);
			toast('success', 'Publication supprimée');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Impossible de supprimer');
		}
	}

	// ── Édition ───────────────────────────────────────────────────────────────
	let editingPub: Publication | null = null;
	let editTitre = '';
	let editContenu = '';
	let editUrgente = false;
	let editEpingle = false;
	let editStatut = '';
	let editBrouillon = false;
	let editSaving = false;

	// ── Évolutions ────────────────────────────────────────────────────────────
	let showEvolForm: number | null = null;  // pub.id ouvert
	let evolType: 'commentaire' | 'etat' = 'commentaire';
	let evolContenu = '';
	let evolNouveauStatut = '';
	let evolSaving = false;

	// ── Expansion ─────────────────────────────────────────────────────────────
	let expandedPubs = new Set<number>();
	let expandedEvols = new Set<number>();
	function togglePub(id: number) {
		expandedPubs = expandedPubs.has(id) ? new Set() : new Set([id]);
	}

	function startEdit(pub: Publication) {
		editingPub = pub;
		editTitre = pub.titre;
		editContenu = pub.contenu;
		editUrgente = pub.urgente;
		editEpingle = pub.epingle;
		editStatut = pub.statut ?? '';
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
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally { editSaving = false; }
	}

	function openEvolForm(pubId: number) {
		showEvolForm = pubId;
		evolType = 'commentaire';
		evolContenu = '';
		evolNouveauStatut = '';
		editingPub = null;
		expandedPubs = new Set([pubId]);
	}

	async function addEvolution(pub: Publication) {
		if (evolType === 'etat' && !evolNouveauStatut) return;
		if (evolType === 'commentaire' && !evolContenu.trim()) return;
		evolSaving = true;
		try {
			const evol = await pubsApi.addEvolution(pub.id, {
				type: evolType,
				contenu: evolContenu.trim() || undefined,
				nouveau_statut: evolType === 'etat' ? evolNouveauStatut : undefined,
			});
			pubList = pubList.map(p => {
				if (p.id !== pub.id) return p;
				const updated = { ...p, evolutions: [...(p.evolutions ?? []), evol] };
				if (evolType === 'etat') updated.statut = evol.nouveau_statut as any;
				return updated;
			});
			showEvolForm = null;
			toast('success', evolType === 'etat' ? 'Statut mis à jour' : 'Commentaire ajouté');
		} catch (e) {
			toast('error', e instanceof ApiError ? e.message : 'Erreur');
		} finally { evolSaving = false; }
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
	<div class="card" style="margin-bottom:1.5rem;max-width:640px">
		<h2 style="font-size:1rem;font-weight:600;margin-bottom:1rem">Nouvelle publication</h2>
		<form on:submit|preventDefault={publish}>
			<div class="field">
				<label for="new-titre">Titre *</label>
				<input id="new-titre" type="text" bind:value={newTitre} required maxlength="200" />
			</div>
			<div class="field">
				<label id="perimetre-label">Périmètre *</label>
				<div class="perimetre-pills" aria-labelledby="perimetre-label">
					<button type="button" class="pill" class:pill-active={newPerimetre === 'résidence'}
						on:click={() => { newPerimetre = 'résidence'; newLieux = new Set(); }}>
						&#x1F3E7; Copropriété entière
					</button>
					{#each [['bat:1','Bât. 1'],['bat:2','Bât. 2'],['bat:3','Bât. 3'],['bat:4','Bât. 4'],['parking','Parking'],['cave','Cave'],['aful','AFUL']] as [val, lbl]}
						<button type="button" class="pill" class:pill-active={newLieux.has(val)}
							on:click={() => { if (newLieux.has(val)) { newLieux.delete(val); } else { newLieux.add(val); } newLieux = newLieux; newPerimetre = newLieux.size > 0 ? 'specifique' : 'résidence'; }}>
							{lbl}
						</button>
					{/each}
				</div>
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
				<label for="new-statut">État (optionnel)</label>
				<select id="new-statut" bind:value={newStatut}>
					<option value="">— Aucun état —</option>
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
			<div style="margin-bottom:1rem">
				<label class="checkbox-field">
					<input type="checkbox" bind:checked={newPartagerWhatsapp} />
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="#25D366" style="flex-shrink:0;vertical-align:middle" aria-label="WhatsApp">
						<path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51a12.66 12.66 0 0 0-.57-.01c-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 0 1-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 0 1-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 0 1 2.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0 0 12.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 0 0 5.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 0 0-3.48-8.413Z"/>
					</svg>
					<span>Partager sur le groupe</span>
				</label>
			</div>
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
			on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && togglePub(pub.id)}>

			{#if pub.epingle}<span class="pin-badge">&#x1F4CC;</span>{/if}

			<div class="pub-row">
				<div class="pub-row-inner">
					{#if pub.brouillon}<span class="badge badge-gray" style="flex-shrink:0">✏️ Brouillon</span>{/if}
					<span class="pub-row-titre">{pub.titre}</span>
					{#if pub.statut}<span class="badge {STATUT_BADGE[pub.statut] ?? 'badge-gray'}" style="flex-shrink:0">{STATUT_LABELS[pub.statut] ?? pub.statut}</span>{/if}
{#if pub.perimetre_cible && !(pub.perimetre_cible.length === 1 && pub.perimetre_cible[0] === 'résidence')}<span class="badge badge-gray" style="flex-shrink:0">&#x1F539; {perimètreLabel(pub.perimetre_cible)}</span>{/if}
				</div>
				<div class="pub-row-right">
					<span class="pub-row-date">{fmtDate(pub.mis_a_jour_le ?? pub.cree_le)}</span>
					{#if $isCS}
						<button class="btn-icon-edit" aria-label="Modifier" title="Modifier"
							on:click|stopPropagation={() => startEdit(pub)}>✏️</button>
					<button class="btn-icon" aria-label="Ajouter un commentaire / changer état" title="Commenter / état"
						on:click|stopPropagation={() => openEvolForm(pub.id)}>&#x1F4AC;</button>

					{#if pub.statut === 'resolu'}
					<button class="btn-icon" aria-label="Archiver" title="Archiver"
						on:click|stopPropagation={() => archivePub(pub)}>&#x1F4E6;</button>
					{/if}
					{/if}				{#if $isAdmin}
				<button class="btn-icon" aria-label="Supprimer" title="Supprimer définitivement" style="color:var(--color-danger)"
					on:click|stopPropagation={() => deletePub(pub)}>🗑️</button>
				{/if}					<span class="chevron" class:open={expanded}>›</span>
				</div>
			</div>

			{#if !expanded && !compactPubs}
				<div class="pub-preview rich-content clamp-5">{@html safeHtml(pub.contenu)}</div>
			{/if}

			{#if expanded}
				<div class="pub-body">

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
									<option value="">— Aucun état —</option>
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
							<div class="form-actions" style="gap:.5rem">
								<button type="button" class="btn btn-outline" on:click={cancelEdit}>Annuler</button>
								<button type="submit" class="btn btn-primary" disabled={editSaving}>{editSaving ? 'Enregistrement…' : 'Enregistrer'}</button>
							</div>
						</form>

					{:else if showEvolForm === pub.id}
						<!-- ── Formulaire d'évolution ── -->
						<div class="evol-form" on:click|stopPropagation>
							<h4 style="font-size:.875rem;font-weight:600;margin:0 0 .6rem">Ajouter une évolution</h4>
							<div style="display:flex;gap:.5rem;margin-bottom:.6rem;flex-wrap:wrap">
								<button type="button" class="pill" class:pill-active={evolType === 'commentaire'}
									on:click={() => (evolType = 'commentaire')}>&#x1F4AC; Commentaire</button>
								<button type="button" class="pill" class:pill-active={evolType === 'etat'}
									on:click={() => (evolType = 'etat')}>&#x1F504; Changement d'état</button>
							</div>
							{#if evolType === 'etat'}
								<div class="field">
									<label for="evol-statut-{pub.id}">Nouvel état *</label>
									<select id="evol-statut-{pub.id}" bind:value={evolNouveauStatut}>
										<option value="">— Choisir —</option>
										<option value="en_cours">&#x1F7E1; En cours</option>
										<option value="resolu">&#x1F7E2; Résolu</option>
										<option value="annule">⚫ Annulé</option>
									</select>
								</div>
							{/if}
							<div class="field">
								<label for="evol-contenu-{pub.id}">{evolType === 'etat' ? 'Commentaire (optionnel)' : 'Commentaire *'}</label>
								<textarea id="evol-contenu-{pub.id}" bind:value={evolContenu} rows="3"
									placeholder={evolType === 'etat' ? 'Précisions sur ce changement…' : 'Ajoutez un commentaire…'}
									style="width:100%;padding:.4rem .6rem;border:1px solid var(--color-border);border-radius:6px;font-size:.875rem;resize:vertical"
								></textarea>
							</div>
							<div class="form-actions" style="gap:.5rem">
								<button type="button" class="btn btn-outline" on:click={() => (showEvolForm = null)}>Annuler</button>
								<button type="button" class="btn btn-primary"
									disabled={evolSaving || (evolType === 'etat' && !evolNouveauStatut) || (evolType === 'commentaire' && !evolContenu.trim())}
									on:click={() => addEvolution(pub)}>
									{evolSaving ? 'Envoi…' : 'Valider'}
								</button>
							</div>
						</div>

					{:else}
						<!-- ── Corps normal ── -->
						{#if pub.image_url}
							<img class="pub-img" src={pub.image_url} alt={pub.titre} />
						{/if}
						<div class="rich-content" style="font-size:.875rem;line-height:1.6;margin-bottom:.5rem">{@html safeHtml(pub.contenu)}</div>
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
											<span class="evol-meta">{fmtDatetime(evol.cree_le)}{#if evol.auteur_nom} · {evol.auteur_nom}{/if}</span>
											{#if evol.type === 'etat'}
												<span class="evol-text">
													Statut : <strong>{STATUT_LABELS[evol.ancien_statut ?? ''] || 'Aucun'}</strong> → <strong>{STATUT_LABELS[evol.nouveau_statut ?? ''] || evol.nouveau_statut}</strong>
												</span>
											{/if}
											{#if evol.contenu}
												<span class="evol-text">{evol.contenu}</span>
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
	.perimetre-pills { display: flex; flex-wrap: wrap; gap: .4rem; margin-top: .4rem; }
	.pill { padding: .3rem .85rem; border-radius: 999px; border: 1.5px solid var(--color-border); background: var(--color-bg); font-size: .85rem; cursor: pointer; transition: background .15s, border-color .15s, color .15s; white-space: nowrap; line-height: 1.6; }
	.pill:hover { border-color: var(--color-primary); color: var(--color-primary); }
	.pill-active { background: var(--color-primary); border-color: var(--color-primary); color: #fff; }
	.form-actions { display: flex; justify-content: flex-end; }
</style>

