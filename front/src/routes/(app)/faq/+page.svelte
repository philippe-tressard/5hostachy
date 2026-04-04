<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
import { onMount } from 'svelte';
	import { faq as faqApi } from '$lib/api';
	import { isCS, isAdmin, currentUser } from '$lib/stores/auth';
	import RichEditor from '$lib/components/RichEditor.svelte';
	import { toast } from '$lib/components/Toast.svelte';
	import { getPageConfig, configStore, siteNomStore } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';

	$: _pc = getPageConfig($configStore, 'faq', { titre: 'FAQ', navLabel: 'FAQ', icone: 'help-circle', descriptif: 'Réponses aux questions fréquentes sur la vie en résidence, les services et la réglementation de la copropriété.' });
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
		// Ouvre et scrolle vers la question badge-prix si le hash est présent
		if (typeof window !== 'undefined' && window.location.hash === '#badge-prix') {
			const badgeItem = items.find((i) => isBadgePrixQuestion(i.question));
			if (badgeItem) {
				open = { [badgeItem.id]: true };
				await new Promise((r) => setTimeout(r, 80));
				document.getElementById('badge-prix')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
			}
		}
	});

	async function loadFaq() {
		loading = true;
		try {
			items = canEdit
				? await faqApi.listAll()
				: await faqApi.list();
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
		try { existingCategories = await faqApi.categories(); } catch { /* conserve le cache précédent */ }
		showForm = true;
	}

	async function openEdit(it: any) {
		editingItem = it;
		formQuestion = it.question;
		formReponse = it.reponse;
		try { existingCategories = await faqApi.categories(); } catch { /* conserve le cache précédent */ }
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
			const catItems = items.filter((i) => normalizeCategorieLabel(i.categorie) === normalizeCategorieLabel(categorie));
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
		newCatItems.forEach((it, idx) => { it.ordre = idx; });
		// Replace in reorderItems
		const otherItems = reorderItems.filter((i) => normalizeCategorieLabel(i.categorie ?? 'Général') !== category);
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
		newCatItems.forEach((it, i) => { it.ordre = i; });
		const otherItems = reorderItems.filter((i) => normalizeCategorieLabel(i.categorie ?? 'Général') !== category);
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

	function onCategorieSelectChange() {
		formIsNewCategorie = formCategorie === '__new__';
		if (formIsNewCategorie) formNewCategorie = '';
	}
</script>

<svelte:head><title>{_pc.titre} — {_siteNom}</title></svelte:head>

<div class="page-header" style="margin: 0">
	<h1 style="display:flex;align-items:center;gap:.4rem;font-size:1.4rem;font-weight:700;margin:0"><Icon name={_pc.icone || 'help-circle'} size={20} />{_pc.titre}</h1>
	{#if canEdit}
		<div style="display:flex;gap:.5rem">
			{#if !reorderMode}
				<button class="btn btn-outline page-header-btn" on:click={enterReorderMode}><Icon name="move" size={15} /> Réorganiser</button>
			{/if}
			<button class="btn btn-primary page-header-btn" on:click={openNew} disabled={reorderMode}>+ Nouvelle question</button>
		</div>
	{/if}
</div>
<div class="page-subtitle">{@html safeHtml(_pc.descriptif)}</div>

{#if loading}
	<p style="color:var(--color-text-muted)">Chargement…</p>
{:else if items.length === 0}
	<div class="card" style="padding:2rem;text-align:center;color:var(--color-text-muted)">
		Aucune question pour l'instant.
	</div>
{:else if reorderMode}
	<div class="reorder-bar">
		<span style="font-size:.875rem;color:var(--color-text-muted)">Glissez les questions pour les réorganiser, ou utilisez les flèches ↑↓</span>
		<div style="display:flex;gap:.5rem">
			<button class="btn btn-outline" on:click={cancelReorder} disabled={reorderSaving}>Annuler</button>
			<button class="btn btn-primary" on:click={saveReorder} disabled={reorderSaving}>
				{reorderSaving ? 'Enregistrement…' : 'Sauvegarder l\'ordre'}
			</button>
		</div>
	</div>
	{#each Object.entries(reorderGrouped) as [categorie, catItems]}
		<h2 class="categorie-title">{categorie}</h2>
		{#each catItems as item, idx (item.id)}
			<div
				class="faq-item card reorder-item"
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
					<button class="btn-icon-edit" disabled={idx === 0} on:click={() => moveItem(categorie, item, -1)} title="Monter" aria-label="Monter">↑</button>
					<button class="btn-icon-edit" disabled={idx === catItems.length - 1} on:click={() => moveItem(categorie, item, 1)} title="Descendre" aria-label="Descendre">↓</button>
				</div>
			</div>
		{/each}
	{/each}
{:else}
	{#each Object.entries(filteredGrouped) as [categorie, catItems]}
        {@const compact = catItems.length > 7}
		<div style="display:flex;justify-content:space-between;align-items:center">
			<h2 class="categorie-title">{categorie}</h2>
		</div>
		{#each catItems as item (item.id)}
			<div id={isBadgePrixQuestion(item.question) ? 'badge-prix' : undefined}
				class="faq-item card" class:item-inactive={!item.actif} role="button" tabindex="0" on:click={() => toggle(item.id)} on:keydown={(e) => (e.key === "Enter" || e.key === " ") && toggle(item.id)}>
				<div class="faq-header">
					<button
						class="faq-q" tabindex="-1" aria-expanded={!!open[item.id]}
					>
						<span>{item.question}</span>
						<span class="chevron" class:open={open[item.id]}>›</span>
					</button>
					{#if canEdit}
						<div class="faq-actions">
						<button class="btn-icon-edit" aria-label="Modifier" title="Modifier" on:click|stopPropagation={() => openEdit(item)}>✏️</button>
						<button
							class={item.actif ? 'btn-icon-warn' : 'btn-icon-edit'}
							aria-label={item.actif ? 'Masquer' : 'Afficher'}
							title={item.actif ? 'Masquer' : 'Afficher'}
							on:click|stopPropagation={() => toggleActif(item)}
						>
							{item.actif ? '\u{1F648}' : '\u{1F441}️'}
						</button>
						<button class="btn-icon-danger" aria-label="Supprimer" title="Supprimer" on:click|stopPropagation={() => deleteItem(item)}>&#x1F5D1;️</button>
						</div>
					{/if}
				</div>
				{#if open[item.id]}
						<div class="faq-a rich-content" on:click|stopPropagation>
							{@html safeHtml(item.reponse)}
							{#if isBadgePrixQuestion(item.question)}
								<div class="faq-cta-row">
									<a class="btn btn-primary btn-sm" href="/acces-securite#nouvelle-demande">Faire une nouvelle demande d'accès</a>
									<a class="btn btn-outline btn-sm" href="/acces-securite">Voir Accès &amp; badges</a>
								</div>
							{/if}
						</div>
				{/if}
			</div>
		{/each}
	{/each}
{/if}

<div class="still-need-help card">
	<strong>Vous ne trouvez pas la réponse ?</strong>
	<p>Créez un ticket via la rubrique <a href="/tickets">Signalements & tickets</a> et le conseil syndical vous répondra dans les meilleurs délais.</p>
	<p style="margin-top:.75rem;padding-top:.75rem;border-top:1px solid var(--color-border)"><Icon name="book-open" size={15} style="vertical-align:middle;margin-right:.3rem" />Consultez le <a href="/manuel-utilisateur.html" target="_blank" rel="noopener">Manuel utilisateur complet</a> pour un guide pas à pas de toutes les fonctionnalités.</p>
</div>

<!-- Modal ajout / édition -->
{#if showForm}
<div class="modal-overlay" on:click|self={() => (showForm = false)} role="dialog" aria-modal="true" tabindex="-1">
	<div class="modal-box card">
		<h2 style="font-size:1rem;font-weight:700;margin-bottom:1rem">
			{editingItem ? 'Modifier la question' : 'Nouvelle question'}
		</h2>
		<div class="form-grid">
			<label class="field-label" for="faq-categorie">Catégorie *</label>
			<select id="faq-categorie" class="input-field" bind:value={formCategorie} on:change={onCategorieSelectChange}>
				<option value="" disabled>— Choisir une catégorie —</option>
				{#each existingCategories as cat}
					<option value={cat}>{cat}</option>
				{/each}
				<option value="__new__">➕ Nouvelle catégorie…</option>
			</select>
			{#if formIsNewCategorie}
				<label class="field-label" for="faq-new-categorie">Nom de la nouvelle catégorie *</label>
				<input id="faq-new-categorie" class="input-field" type="text" bind:value={formNewCategorie} placeholder="Ex : 🗑️ Tri des déchets" />
			{/if}

			<label class="field-label" for="faq-question">Question *</label>
			<input id="faq-question" class="input-field" type="text" bind:value={formQuestion} placeholder="La question…" />

			<label class="field-label" for="faq-reponse">Réponse *</label>
			<!-- RichEditor n'est pas un input natif, on ne peut pas utiliser for, mais on garde le label pour l'accessibilité -->
			<RichEditor id="faq-reponse" bind:value={formReponse} placeholder="La réponse…" minHeight="120px" />
		</div>
		<div style="display:flex;gap:.5rem;justify-content:flex-end;margin-top:1rem">
			<button class="btn btn-outline" on:click={() => (showForm = false)} disabled={saving}>Annuler</button>
			<button class="btn btn-primary" on:click={saveItem} disabled={saving}>
				{saving ? 'Enregistrement…' : 'Enregistrer'}
			</button>
		</div>
	</div>
</div>
{/if}

<style>
	.categorie-title { font-size: .85rem; font-weight: 700; text-transform: uppercase; letter-spacing: .05em; color: var(--color-text-muted); margin: 1.5rem 0 .5rem; }
	.faq-item { cursor: pointer; margin-bottom: .35rem; overflow: visible; padding: 0; }
	.item-inactive { opacity: .55; }
	.faq-header { display: flex; align-items: center; }
	.faq-q { user-select: none; flex: 1; display: flex; justify-content: space-between; align-items: center; padding: .875rem 1rem; background: none; border: none; cursor: pointer; font-size: .925rem; font-weight: 500; text-align: left; gap: 1rem; color: var(--color-text); }
	.faq-q:hover { background: var(--color-bg-subtle); }
	.chevron { font-size: 1.1rem; line-height: 1; transform: rotate(0deg); transition: transform .18s ease; flex-shrink: 0; }
	.chevron.open { transform: rotate(90deg); }
	.faq-a { padding: .5rem 1rem .9rem; font-size: .875rem; color: var(--color-text-muted); line-height: 1.55; border-top: 1px solid var(--color-border); }
	.faq-cta-row { display:flex; gap:.5rem; flex-wrap:wrap; margin-top:.8rem; padding-top:.75rem; border-top:1px dashed var(--color-border); }
	.faq-actions { display: flex; gap: .15rem; padding-right: .5rem; }
	.still-need-help { margin-top: 2rem; padding: 1.25rem; }
	.still-need-help p { margin: .5rem 0 0; font-size: .875rem; color: var(--color-text-muted); }
	.modal-overlay { position: fixed; top: 0; right: 0; bottom: 0; left: 0; background: rgba(0,0,0,.45); display: flex; align-items: center; justify-content: center; z-index: 200; }
	.modal-box { max-width: 500px; width: 92%; padding: 1.5rem; }
	.form-grid { display: flex; flex-direction: column; gap: .5rem; }
	.field-label { font-size: .8rem; font-weight: 500; color: var(--color-text-muted); margin-top: .25rem; }
	.input-field { padding: .45rem .65rem; border: 1px solid var(--color-border); border-radius: 6px; font-size: .875rem; font-family: inherit; width: 100%; box-sizing: border-box; resize: vertical; }
	.req { color: var(--color-danger); }
	.btn-outline { background: none; border: 1px solid var(--color-border); border-radius: var(--radius); padding: .4rem .9rem; cursor: pointer; font-size: .875rem; }
	.reorder-bar { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: .5rem; padding: .75rem 1rem; margin-bottom: .5rem; background: var(--color-bg-subtle); border-radius: var(--radius); border: 1px dashed var(--color-border); }
	.reorder-item { display: flex; align-items: center; gap: .5rem; padding: .5rem .75rem; cursor: grab; user-select: none; }
	.reorder-item:active { cursor: grabbing; }
	.reorder-handle { font-size: 1.2rem; color: var(--color-text-muted); cursor: grab; flex-shrink: 0; }
	.reorder-question { flex: 1; font-size: .9rem; }
	.reorder-arrows { display: flex; gap: .15rem; flex-shrink: 0; }
	.drag-over { outline: 2px dashed var(--color-primary); outline-offset: -2px; background: var(--color-bg-subtle); }
</style>
