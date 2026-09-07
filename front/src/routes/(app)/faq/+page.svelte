<script lang="ts">
	import FormulaireFaq from '$lib/components/FormulaireFaq.svelte';
	import CarteFaq from '$lib/components/CarteFaq.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import EntetePage from '$lib/components/EntetePage.svelte';
	import { onMount } from 'svelte';
	import { cibleDuHash, revelerCible } from '$lib/deepLink';
	import { faq as faqApi } from '$lib/api';
	import { isCS, isAdmin, currentUser } from '$lib/stores/auth';
	import { toast } from '$lib/components/Toast.svelte';
	import { getPageConfig, configStore, siteNomStore, defautsDePage } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';

	$: _pc = getPageConfig($configStore, 'faq', defautsDePage('faq'));
	$: _siteNom = $siteNomStore;

	let open: Record<number, boolean> = {};
	let items: any[] = [];
	let loading = true;

	// ---- edition ----
	let showForm = false;
	let editingItem: any | null = null;
	let formCategorie = '';
	let formNewCategorie = '';
	let formIsNewCategorie = false;
	let formQuestion = '';
	let formReponse = '';
	let saving = false;
	let existingCategories: string[] = [];

	// ---- reorder mode ----
	let reorderMode = false;
	let reorderItems: any[] = [];
	let dragItem: any | null = null;
	let dragOverItem: any | null = null;
	let dragCategory: string | null = null;
	let reorderSaving = false;

	$: canEdit = $isCS || $isAdmin;

	function normalizeText(input: string | null | undefined): string {
		return (input ?? '')
			.toLowerCase()
			.normalize('NFD')
			.replace(/[\u0300-\u036f]/g, '');
	}

	function normalizeCategorieLabel(cat: string | null | undefined): string {
		const original = cat ?? 'Général';
		const n = normalizeText(original);
		if (n.includes('coproprietaire') && n.includes('mandataire')) {
			return '📋 Copropriétaire bailleur';
		}
		return original;
	}

	function isLocataireCategory(cat: string): boolean {
		const n = normalizeText(cat);
		return n.includes('locataire');
	}

	function isCoproBailleurCategory(cat: string): boolean {
		const n = normalizeText(cat);
		return n.includes('coproprietaire') && (n.includes('bailleur') || n.includes('mandataire'));
	}

	function isCoproResidentCategory(cat: string): boolean {
		const n = normalizeText(cat);
		return n.includes('coproprietaire') && n.includes('resident');
	}

	function isCoproprietaireStatus(statut: string): boolean {
		const n = normalizeText(statut);
		return n.includes('coproprietaire');
	}

	function isCoproBailleurStatus(statut: string): boolean {
		const n = normalizeText(statut);
		return isCoproprietaireStatus(statut) && (n.includes('bailleur') || n.includes('mandataire'));
	}

	function isCoproResidentStatus(statut: string): boolean {
		const n = normalizeText(statut);
		return isCoproprietaireStatus(statut) && n.includes('resident');
	}

	$: grouped = items.reduce((acc: Record<string, any[]>, it) => {
		const cat = normalizeCategorieLabel(it.categorie ?? 'Général');
		if (!acc[cat]) acc[cat] = [];
		acc[cat].push(it);
		return acc;
	}, {});

	// Masquer les catégories FAQ non pertinentes selon le statut
	$: filteredGrouped = (() => {
		const statut = $currentUser?.statut;
		if (!statut || canEdit) return grouped;

		const out: Record<string, any[]> = {};
		for (const [cat, catItems] of Object.entries(grouped)) {
			if (normalizeText(statut) === 'locataire') {
				if (isCoproResidentCategory(cat) || isCoproBailleurCategory(cat)) continue;
				out[cat] = catItems;
				continue;
			}

			if (isCoproResidentStatus(statut)) {
				if (isLocataireCategory(cat) || isCoproBailleurCategory(cat)) continue;
				out[cat] = catItems;
				continue;
			}

			if (isCoproBailleurStatus(statut)) {
				if (isLocataireCategory(cat) || isCoproResidentCategory(cat)) continue;
				out[cat] = catItems;
				continue;
			}

			if (isCoproprietaireStatus(statut)) {
				if (isLocataireCategory(cat)) continue;
				out[cat] = catItems;
				continue;
			}

			out[cat] = catItems;
		}
		return out;
	})();

	onMount(async () => {
		await loadFaq();
		// `#faq-<id>` : question visée par le fil d'activité ou une notification.
		const idFaq = cibleDuHash('faq');
		if (idFaq !== null) {
			open = { [idFaq]: true };
			revelerCible(`faq-${idFaq}`);
		}

		// `#badge-prix` : raccourci historique, documenté dans le manuel et utilisé
		// depuis /acces-securite — il vise la question par son libellé, pas par son
		// id, qui varie d'une instance à l'autre.
		if (typeof window !== 'undefined' && window.location.hash === '#badge-prix') {
			const badgeItem = items.find((i) => isBadgePrixQuestion(i.question));
			if (badgeItem) {
				open = { [badgeItem.id]: true };
				revelerCible(`faq-${badgeItem.id}`);
			}
		}
	});

	async function loadFaq() {
		loading = true;
		try {
			items = canEdit ? await faqApi.listAll() : await faqApi.list();
		} catch {
			items = [];
		} finally {
			loading = false;
		}
	}

	function toggle(id: number) {
		const wasOpen = open[id];
		open = { [id]: !wasOpen };
	}

	async function openNew() {
		editingItem = null;
		formCategorie = '';
		formNewCategorie = '';
		formIsNewCategorie = false;
		formQuestion = '';
		formReponse = '';
		try {
			existingCategories = await faqApi.categories();
		} catch {
			/* conserve le cache précédent */
		}
		showForm = true;
	}

	async function openEdit(it: any) {
		editingItem = it;
		formQuestion = it.question;
		formReponse = it.reponse;
		try {
			existingCategories = await faqApi.categories();
		} catch {
			/* conserve le cache précédent */
		}
		if (existingCategories.includes(it.categorie ?? '')) {
			formCategorie = it.categorie ?? '';
			formIsNewCategorie = false;
			formNewCategorie = '';
		} else {
			formCategorie = '__new__';
			formIsNewCategorie = true;
			formNewCategorie = it.categorie ?? '';
		}
		showForm = true;
	}

	function isBadgePrixQuestion(question: string | null | undefined) {
		if (!question) return false;
		return /quel\s+prix.*badge|prix.*badge|badge.*prix/i.test(question);
	}

	const richEmpty = (html: string) => !html || html.replace(/<[^>]+>/g, '').trim() === '';

	async function saveItem() {
		if (!formQuestion.trim() || richEmpty(formReponse)) {
			toast('error', 'Question et réponse sont obligatoires.');
			return;
		}
		const categorie = formIsNewCategorie ? formNewCategorie.trim() : formCategorie.trim();
		if (!categorie) {
			toast('error', 'La catégorie est obligatoire.');
			return;
		}
		saving = true;
		try {
			// Calcul auto de l'ordre : dernier de la catégorie + 1
			const catItems = items.filter(
				(i) => normalizeCategorieLabel(i.categorie) === normalizeCategorieLabel(categorie),
			);
			const maxOrdre = catItems.length ? Math.max(...catItems.map((i) => i.ordre ?? 0)) : -1;
			const ordre = editingItem ? editingItem.ordre : maxOrdre + 1;

			const payload = {
				categorie,
				question: formQuestion.trim(),
				reponse: formReponse.trim(),
				ordre,
				actif: true,
			};
			if (editingItem) {
				const updated = await faqApi.update(editingItem.id, payload);
				items = items.map((i) => (i.id === editingItem.id ? updated : i));
				toast('success', 'Élément mis à jour.');
			} else {
				const created = await faqApi.create(payload);
				items = [...items, created];
				toast('success', 'Élément ajouté.');
			}
			showForm = false;
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		} finally {
			saving = false;
		}
	}

	async function deleteItem(it: any) {
		if (!confirm(`Supprimer "${it.question}" ?`)) return;
		try {
			await faqApi.delete(it.id);
			items = items.filter((i) => i.id !== it.id);
			toast('info', 'Élément supprimé.');
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		}
	}

	async function toggleActif(it: any) {
		try {
			const updated = await faqApi.update(it.id, { actif: !it.actif });
			items = items.map((i) => (i.id === it.id ? updated : i));
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		}
	}

	// ---- reorder ----
	function enterReorderMode() {
		reorderItems = items.map((i) => ({ ...i }));
		reorderMode = true;
	}

	function cancelReorder() {
		reorderMode = false;
		reorderItems = [];
		dragItem = null;
		dragOverItem = null;
		dragCategory = null;
	}

	$: reorderGrouped = reorderItems.reduce((acc: Record<string, any[]>, it) => {
		const cat = normalizeCategorieLabel(it.categorie ?? 'Général');
		if (!acc[cat]) acc[cat] = [];
		acc[cat].push(it);
		return acc;
	}, {});

	function handleDragStart(item: any, category: string) {
		dragItem = item;
		dragCategory = category;
	}

	function handleDragOver(e: DragEvent, item: any, category: string) {
		if (dragCategory !== category) return;
		e.preventDefault();
		dragOverItem = item;
	}

	function handleDrop(e: DragEvent, category: string) {
		e.preventDefault();
		if (!dragItem || !dragOverItem || dragCategory !== category) return;
		const catItems = reorderGrouped[category];
		if (!catItems) return;
		const fromIndex = catItems.findIndex((i: any) => i.id === dragItem.id);
		const toIndex = catItems.findIndex((i: any) => i.id === dragOverItem.id);
		if (fromIndex === -1 || toIndex === -1 || fromIndex === toIndex) return;
		// Reorder within category
		const newCatItems = [...catItems];
		const [moved] = newCatItems.splice(fromIndex, 1);
		newCatItems.splice(toIndex, 0, moved);
		// Update ordre values
		newCatItems.forEach((it, idx) => {
			it.ordre = idx;
		});
		// Replace in reorderItems
		const otherItems = reorderItems.filter(
			(i) => normalizeCategorieLabel(i.categorie ?? 'Général') !== category,
		);
		reorderItems = [...otherItems, ...newCatItems];
		dragItem = null;
		dragOverItem = null;
		dragCategory = null;
	}

	function handleDragEnd() {
		dragItem = null;
		dragOverItem = null;
		dragCategory = null;
	}

	function moveItem(category: string, item: any, direction: -1 | 1) {
		const catItems = reorderGrouped[category];
		if (!catItems) return;
		const idx = catItems.findIndex((i: any) => i.id === item.id);
		const targetIdx = idx + direction;
		if (targetIdx < 0 || targetIdx >= catItems.length) return;
		const newCatItems = [...catItems];
		[newCatItems[idx], newCatItems[targetIdx]] = [newCatItems[targetIdx], newCatItems[idx]];
		newCatItems.forEach((it, i) => {
			it.ordre = i;
		});
		const otherItems = reorderItems.filter(
			(i) => normalizeCategorieLabel(i.categorie ?? 'Général') !== category,
		);
		reorderItems = [...otherItems, ...newCatItems];
	}

	async function saveReorder() {
		reorderSaving = true;
		try {
			const changes = reorderItems
				.filter((ri) => {
					const orig = items.find((i) => i.id === ri.id);
					return orig && orig.ordre !== ri.ordre;
				})
				.map((ri) => ({ id: ri.id, ordre: ri.ordre }));
			if (changes.length) {
				await faqApi.reorder(changes);
				items = reorderItems.map((i) => ({ ...i }));
				toast('success', 'Ordre mis à jour.');
			}
			reorderMode = false;
			reorderItems = [];
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		} finally {
			reorderSaving = false;
		}
	}

	// ---- rename category ----
	let editingCategory: string | null = null;
	let editCategoryName = '';
	let savingCategory = false;

	function startEditCategory(cat: string) {
		editingCategory = cat;
		editCategoryName = cat;
	}

	function cancelEditCategory() {
		editingCategory = null;
		editCategoryName = '';
	}

	async function saveCategory() {
		if (!editCategoryName.trim() || !editingCategory) return;
		if (editCategoryName.trim() === editingCategory) {
			cancelEditCategory();
			return;
		}
		savingCategory = true;
		try {
			await faqApi.renameCategory(editingCategory, editCategoryName.trim());
			// Mettre à jour localement
			const oldName = editingCategory;
			const newName = editCategoryName.trim();
			items = items.map((i) => (i.categorie === oldName ? { ...i, categorie: newName } : i));
			toast('success', 'Catégorie renommée.');
			cancelEditCategory();
		} catch (e: any) {
			toast('error', e.message ?? 'Erreur');
		} finally {
			savingCategory = false;
		}
	}
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<EntetePage titre={_pc.titre} icone={_pc.icone || 'help-circle'}>
	{#if canEdit}
		{#if !reorderMode}
			<button class="btn btn-outline page-header-btn" on:click={enterReorderMode}
				><Icon name="move" size={15} /> Réorganiser</button
			>
		{/if}
		<button class="btn btn-primary page-header-btn" on:click={openNew} disabled={reorderMode}
			>+ Nouvelle question</button
		>
	{/if}
</EntetePage>
<div class="page-subtitle">{@html safeHtml(_pc.descriptif)}</div>

{#if loading}
	<p style="color:var(--color-text-muted)">Chargement…</p>
{:else if items.length === 0}
	<div class="card" style="padding:2rem;text-align:center;color:var(--color-text-muted)">
		Aucune question pour l'instant.
	</div>
{:else if reorderMode}
	<div class="reorder-bar">
		<span style="font-size:.875rem;color:var(--color-text-muted)"
			>Glissez les questions pour les réorganiser, ou utilisez les flèches ↑↓</span
		>
		<div style="display:flex;gap:.5rem">
			<button class="btn btn-outline" on:click={cancelReorder} disabled={reorderSaving}
				>Annuler</button
			>
			<button class="btn btn-primary" on:click={saveReorder} disabled={reorderSaving}>
				{reorderSaving ? 'Enregistrement…' : "Sauvegarder l'ordre"}
			</button>
		</div>
	</div>
	{#each Object.entries(reorderGrouped) as [categorie, catItems] (categorie)}
		<h2 class="categorie-title">{categorie}</h2>
		{#each catItems as item, idx (item.id)}
			<div
				class="card reorder-item"
				class:drag-over={dragOverItem?.id === item.id}
				draggable="true"
				on:dragstart={() => handleDragStart(item, categorie)}
				on:dragover={(e) => handleDragOver(e, item, categorie)}
				on:drop={(e) => handleDrop(e, categorie)}
				on:dragend={handleDragEnd}
				role="listitem"
			>
				<div class="reorder-handle" title="Glisser pour réorganiser">⠿</div>
				<span class="reorder-question">{item.question}</span>
				<div class="reorder-arrows">
					<button
						class="btn-icon-edit"
						disabled={idx === 0}
						on:click={() => moveItem(categorie, item, -1)}
						title="Monter"
						aria-label="Monter">↑</button
					>
					<button
						class="btn-icon-edit"
						disabled={idx === catItems.length - 1}
						on:click={() => moveItem(categorie, item, 1)}
						title="Descendre"
						aria-label="Descendre">↓</button
					>
				</div>
			</div>
		{/each}
	{/each}
{:else}
	{#each Object.entries(filteredGrouped) as [categorie, catItems] (categorie)}
		<div style="display:flex;justify-content:space-between;align-items:center">
			{#if canEdit && editingCategory === categorie}
				<div class="categorie-edit">
					<input
						class="input-field categorie-input"
						type="text"
						bind:value={editCategoryName}
						on:keydown={(e) => {
							if (e.key === 'Enter') saveCategory();
							if (e.key === 'Escape') cancelEditCategory();
						}}
					/>
					<button
						class="btn-icon-edit"
						on:click={saveCategory}
						disabled={savingCategory}
						title="Valider"
						aria-label="Valider">✅</button
					>
					<button
						class="btn-icon-edit"
						on:click={cancelEditCategory}
						disabled={savingCategory}
						title="Annuler"
						aria-label="Annuler">✖️</button
					>
				</div>
			{:else}
				<h2 class="categorie-title">{categorie}</h2>
				{#if canEdit}
					<button
						class="btn-icon-edit btn-edit-cat"
						on:click={() => startEditCategory(categorie)}
						title="Renommer la catégorie"
						aria-label="Renommer la catégorie">✏️</button
					>
				{/if}
			{/if}
		</div>
		{#each catItems as item (item.id)}
			<CarteFaq
				{item}
				ouvert={!!open[item.id]}
				{canEdit}
				avecCta={isBadgePrixQuestion(item.question)}
				on:basculer={() => toggle(item.id)}
				on:modifier={() => openEdit(item)}
				on:basculerActif={() => toggleActif(item)}
				on:supprimer={() => deleteItem(item)}
			/>
		{/each}
	{/each}
{/if}

<div class="still-need-help card">
	<strong>Vous ne trouvez pas la réponse ?</strong>
	<p>
		Créez un ticket via la rubrique <a href="/tickets">Signalements & tickets</a> et le conseil syndical
		vous répondra dans les meilleurs délais.
	</p>
	<p style="margin-top:.75rem;padding-top:.75rem;border-top:1px solid var(--color-border)">
		<span style="vertical-align:middle;margin-right:.3rem;display:inline-flex"
			><Icon name="book-open" size={15} /></span
		>Le <a href="/manuel-utilisateur.html" target="_blank" rel="noopener">Manuel utilisateur</a>
		vous guide pas à pas, et existe
		<a href="/api/manuel/pdf" target="_blank" rel="noopener">en PDF</a>.
	</p>
</div>

<!--  Le formulaire est un COMPOSANT, comme pour les six autres entités du site.
      Il porte son cadre : boîte pour créer, modale pour corriger (`ux-patterns`
      §14 bis). Cet écran ouvrait une modale pour les DEUX — voir le composant. -->
{#if showForm}
	<FormulaireFaq
		modeEdition={editingItem !== null}
		bind:categorie={formCategorie}
		bind:nouvelleCategorie={formNewCategorie}
		bind:estNouvelleCategorie={formIsNewCategorie}
		bind:question={formQuestion}
		bind:reponse={formReponse}
		categories={existingCategories}
		enregistrement={saving}
		onEnregistrer={saveItem}
		on:annule={() => (showForm = false)}
	/>
{/if}

<style>
	.categorie-title {
		font-size: 0.85rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-text-muted);
		margin: 1.5rem 0 0.5rem;
	}
	.btn-edit-cat {
		opacity: 0.4;
		font-size: 0.75rem;
		transition: opacity 0.15s;
		margin-top: 0.75rem;
	}
	.btn-edit-cat:hover {
		opacity: 1;
	}
	.categorie-edit {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		margin: 1.25rem 0 0.35rem;
	}
	.categorie-input {
		font-size: 0.85rem;
		font-weight: 700;
		padding: 0.3rem 0.5rem;
		max-width: 300px;
	}
	.still-need-help {
		margin-top: 2rem;
		padding: 1.25rem;
	}
	.still-need-help p {
		margin: 0.5rem 0 0;
		font-size: 0.875rem;
		color: var(--color-text-muted);
	}
	/*  Ne sert plus qu'au renommage de catégorie EN LIGNE. Fond explicite : son absence rendait les champs blancs (#413). */
	.input-field {
		padding: 0.45rem 0.65rem;
		border: 1px solid var(--color-border);
		border-radius: 6px;
		font-size: 0.875rem;
		font-family: inherit;
		width: 100%;
		box-sizing: border-box;
		resize: vertical;
		background: var(--color-bg);
		color: var(--color-text);
	}
	.btn-outline {
		padding: 0.4rem 0.9rem;
	} /* le reste vient de la charte (#607) */
	.reorder-bar {
		display: flex;
		justify-content: space-between;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.5rem;
		padding: 0.75rem 1rem;
		margin-bottom: 0.5rem;
		background: var(--color-bg-subtle);
		border-radius: var(--radius);
		border: 1px dashed var(--color-border);
	}
	.reorder-item {
		/*  L'espacement venait de `.faq-item`, partie avec la carte dans
		    `CarteFaq.svelte` : une ligne de réorganisation n'est pas une carte de
		    question, elle n'a que son interligne en commun. */
		margin-bottom: 0.35rem;
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem;
		cursor: grab;
		user-select: none;
	}
	.reorder-item:active {
		cursor: grabbing;
	}
	.reorder-handle {
		font-size: 1.2rem;
		color: var(--color-text-muted);
		cursor: grab;
		flex-shrink: 0;
	}
	.reorder-question {
		flex: 1;
		font-size: 0.9rem;
	}
	.reorder-arrows {
		display: flex;
		gap: 0.15rem;
		flex-shrink: 0;
	}
	.drag-over {
		outline: 2px dashed var(--color-primary);
		outline-offset: -2px;
		background: var(--color-bg-subtle);
	}
</style>
