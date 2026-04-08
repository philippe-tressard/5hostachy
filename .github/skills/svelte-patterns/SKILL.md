---
name: svelte-patterns
description: "Create SvelteKit pages and components following 5Hostachy conventions: page structure, data loading, stores, API client, CSS variables, accessibility. Use when: creating a new page, creating a new component, refactoring a Svelte page, adding a frontend feature."
argument-hint: "Describe the page or component to create (e.g. 'page fournisseurs with list + detail modal')"
---

# Svelte Patterns — 5Hostachy

Conventions et patterns pour créer des pages et composants SvelteKit dans le projet.

## Structure d'une page standard

### Imports obligatoires

```svelte
<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import { onMount } from 'svelte';
	import { isCS, isAdmin, currentUser } from '$lib/stores/auth';
	import { entity as entityApi, ApiError, type Entity } from '$lib/api';
	import { getPageConfig, configStore, siteNomStore } from '$lib/stores/pageConfig';
	import { safeHtml } from '$lib/sanitize';
	import { toast } from '$lib/components/Toast.svelte';
</script>
```

### Page Config (titre dynamique via admin)

```svelte
<script lang="ts">
	$: _pc = getPageConfig($configStore, 'page-id', {
		titre: 'Titre par défaut',
		navLabel: 'Label nav',
		icone: 'nom-icone-lucide',
		descriptif: 'Description par défaut de la page.'
	});
	$: _siteNom = $siteNomStore;
</script>

<svelte:head>
	<title>{_pc.titre} · {_siteNom}</title>
</svelte:head>

<h1><Icon name={_pc.icone} size="28" /> {_pc.titre}</h1>
{#if _pc.descriptif}
	<p class="page-desc">{_pc.descriptif}</p>
{/if}
```

### Chargement des données

```svelte
<script lang="ts">
	let items: Entity[] = [];
	let loading = true;

	onMount(async () => {
		try {
			items = await entityApi.list();
		} finally {
			loading = false;
		}
	});
</script>

{#if loading}
	<p>Chargement…</p>
{:else if items.length === 0}
	<p class="empty">Aucun élément pour le moment.</p>
{:else}
	{#each items as item (item.id)}
		<!-- contenu -->
	{/each}
{/if}
```

### Gestion d'erreurs API

```svelte
<script lang="ts">
	async function save() {
		try {
			await entityApi.create(formData);
			toast.success('Enregistré');
		} catch (e) {
			if (e instanceof ApiError) {
				toast.error(e.message);
			}
		}
	}
</script>
```

## Pattern: Onglets (Tabs)

```svelte
<script lang="ts">
	let onglet: 'liste' | 'archives' = 'liste';
</script>

<div class="tabs" role="tablist" style="margin-bottom:1.5rem">
	<button role="tab" class:active={onglet === 'liste'} on:click={() => onglet = 'liste'}>
		Liste
	</button>
	<button role="tab" class:active={onglet === 'archives'} on:click={() => onglet = 'archives'}>
		Archives
	</button>
</div>

{#if _pc.onglets?.[onglet]?.descriptif}
	<p class="tab-descriptif">{_pc.onglets[onglet].descriptif}</p>
{/if}

{#if onglet === 'liste'}
	<!-- contenu liste -->
{:else if onglet === 'archives'}
	<!-- contenu archives -->
{/if}

<style>
	.tabs { display: flex; gap: .4rem; border-bottom: 2px solid var(--color-border); padding-bottom: .1rem; }
	.tabs button { padding: .45rem 1rem; border: none; background: none; cursor: pointer; font-size: .9rem; color: var(--color-text-muted); border-bottom: 2px solid transparent; margin-bottom: -2px; border-radius: var(--radius) var(--radius) 0 0; }
	.tabs button:hover { color: var(--color-text); background: var(--color-bg); }
	.tabs button.active { color: var(--color-primary); font-weight: 600; border-bottom-color: var(--color-primary); }
</style>
```

## Pattern: Carte expansible (Expand Card)

```svelte
<script lang="ts">
	let expandedItems = new Set<number>();

	function toggleItem(id: number) {
		if (expandedItems.has(id)) {
			expandedItems = new Set();
		} else {
			expandedItems = new Set([id]); // Une seule ouverte à la fois
		}
	}
</script>

{#each items as item (item.id)}
	{@const expanded = expandedItems.has(item.id)}
	<div class="ev-expand" class:expanded class:ev-urgent={item.urgent}
		role="button" tabindex="0"
		on:click={() => toggleItem(item.id)}
		on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && toggleItem(item.id)}>
		<div class="ev-row">
			<div class="ev-row-inner">
				<div class="ev-row-main">
					<span class="ev-type-icon">{item.emoji}</span>
					<span class="ev-row-titre">{item.titre}</span>
					{#if item.badge}<span class="badge badge-blue">{item.badge}</span>{/if}
				</div>
				{#if item.lieu || item.perimetre}
				<div class="ev-row-meta">
					{#if item.lieu}<span class="ev-meta-item">📍 {item.lieu}</span>{/if}
					{#if item.perimetre && item.perimetre !== 'résidence'}
						<span class="badge badge-blue ev-meta-badge">🔹 {perimetreLabel(item.perimetre)}</span>
					{/if}
				</div>
				{/if}
			</div>
			<div class="ev-row-right">
				<span class="ev-row-date">{fmtDate(item.cree_le)}</span>
				<span class="chevron" class:open={expanded}>›</span>
			</div>
		</div>
		{#if !expanded}
			<div class="ev-preview rich-content clamp-5">{@html safeHtml(item.description)}</div>
		{/if}
		{#if expanded}
			<div class="ev-body" on:click|stopPropagation>
				<!-- Corps complet + fil d'évolutions -->
				<div class="rich-content">{@html safeHtml(item.description)}</div>
			</div>
		{/if}
	</div>
{/each}
```

**Règles carte expansible :**
- Une seule carte ouverte à la fois (`expandedItems = new Set([id])`)
- Méta (lieu, périmètre, auteur) : toujours visible, jamais uniquement dans le corps
- `role="button"` + `tabindex="0"` + `on:keydown` obligatoires
- `on:click|stopPropagation` sur le corps et les boutons d'action
- Prévisualisation : `.clamp-5` (5 lignes max)
- Urgence : `border-left-color: var(--color-danger)`

## Pattern: Pill Buttons (sélection filtre)

```svelte
<div class="perimetre-pills">
	{#each options as opt}
		<button type="button" class="pill" class:pill-active={selected === opt.value}
			on:click={() => selected = opt.value}>
			{opt.label}
		</button>
	{/each}
</div>

<style>
	.perimetre-pills { display: flex; flex-wrap: wrap; gap: .4rem; margin-bottom: 1rem; }
	.pill { padding: .3rem .8rem; border: 1px solid var(--color-border); border-radius: 999px; background: var(--color-surface); cursor: pointer; font-size: .85rem; }
	.pill-active { background: var(--color-primary); color: white; border-color: var(--color-primary); }
</style>
```

## Pattern: Formulaire modal

```svelte
<script lang="ts">
	let showModal = false;
	let form = { titre: '', description: '' };

	async function submit() {
		try {
			await entityApi.create(form);
			toast.success('Créé');
			showModal = false;
			items = await entityApi.list(); // rafraîchir
		} catch (e) {
			if (e instanceof ApiError) toast.error(e.message);
		}
	}
</script>

{#if showModal}
<div class="modal-overlay" on:click={() => showModal = false}
	on:keydown={(e) => e.key === 'Escape' && (showModal = false)}>
	<div class="modal" on:click|stopPropagation role="dialog" aria-modal="true">
		<h2>Nouveau</h2>
		<form on:submit|preventDefault={submit}>
			<label>Titre *<input bind:value={form.titre} required /></label>
			<label>Description<textarea bind:value={form.description}></textarea></label>
			<div class="modal-actions">
				<button type="button" class="btn-secondary" on:click={() => showModal = false}>Annuler</button>
				<button type="submit" class="btn-primary">Enregistrer</button>
			</div>
		</form>
	</div>
</div>
{/if}
```

## Helpers de formatage

```svelte
<script lang="ts">
	function fmtDate(d: string) {
		return new Date(d).toLocaleDateString('fr-FR', {
			day: 'numeric', month: 'short', year: 'numeric'
		});
	}

	function fmtDateHeure(d: string) {
		return new Date(d).toLocaleDateString('fr-FR', {
			day: 'numeric', month: 'short', year: 'numeric',
			hour: '2-digit', minute: '2-digit'
		});
	}

	function renderDesc(c: string) {
		const t = c.trimStart();
		return safeHtml(t.startsWith('<') ? c : `<p>${c.replace(/\n/g, '<br>')}</p>`);
	}

	const PERIMETRE_LABELS: Record<string, string> = {
		'résidence': 'Copropriété entière',
		'bat:1': 'Bât. 1', 'bat:2': 'Bât. 2', 'bat:3': 'Bât. 3', 'bat:4': 'Bât. 4',
		parking: 'Parking', cave: 'Cave',
	};

	function perimetreLabel(items: string | string[]) {
		const arr = Array.isArray(items) ? items : items.split(',').map(s => s.trim());
		return arr.filter(i => i !== 'résidence').map(i => PERIMETRE_LABELS[i] ?? i).join(' · ');
	}
</script>
```

## CSS : Variables globales disponibles

```css
var(--color-primary)       /* Bleu principal */
var(--color-primary-light) /* Bleu clair (fond) */
var(--color-danger)        /* Rouge erreur/urgence */
var(--color-success)       /* Vert succès */
var(--color-warning)       /* Orange avertissement */
var(--color-border)        /* Bordure grise */
var(--color-text)          /* Texte principal */
var(--color-text-muted)    /* Texte secondaire */
var(--color-bg)            /* Fond page */
var(--color-surface)       /* Fond carte/modal */
var(--radius)              /* Border-radius standard */
var(--shadow)              /* Box-shadow standard */
```

## Sécurité XSS

**OBLIGATOIRE** : tout `{@html}` doit utiliser `safeHtml()` :
```svelte
<!-- ✗ INTERDIT -->
{@html contenu}

<!-- ✓ CORRECT -->
{@html safeHtml(contenu)}
```

## Accessibilité

- `role="button"` + `tabindex="0"` sur les éléments cliquables non-bouton
- `on:keydown` (Enter/Space) sur tous les `role="button"`
- `role="tablist"` / `role="tab"` sur les onglets
- `aria-modal="true"` + `role="dialog"` sur les modales
- Labels : `Titre *` (astérisque pour les champs requis)
- `aria-label` sur les boutons icône-seule

## Archivage vs Suppression

- **Archiver** (📦) : CS + admin → `PATCH { archivee: true }`
- **Supprimer** (🗑️) : admin uniquement, vue Archives seulement → `DELETE`
- Jamais de bouton Supprimer sur la vue principale
