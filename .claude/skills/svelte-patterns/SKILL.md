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
	import { fmtDate, fmtDatetime } from '$lib/date';
	import { fmtMontant, perimetreLabel } from '$lib/utils';
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

## Pattern: Onglets (Tabs) — un onglet est une ADRESSE

🔴 Depuis le 05/09/2026, un onglet n'est plus un état local : c'est une **route**.
On ne l'affecte pas, on y navigue. Le détail (forme des URL, redirection des
anciennes, masquage vs redirection) est dans `ux-patterns` §4.

```svelte
<!-- src/routes/(app)/calendrier/+page.ts — la page ne bouge pas -->
import { resoudreOnglet } from '$lib/deepLink';

export const load = ({ url }) => resoudreOnglet('calendrier', url);
```

`/calendrier/kanban` arrive sur cette même route : `reroute` (`src/hooks.ts`) l'y
envoie, et `url` reste l'adresse demandée.

```svelte
<!-- src/routes/(app)/calendrier/+page.svelte -->
<script lang="ts">
	import BarreOnglets from '$lib/components/BarreOnglets.svelte';

	export let data: { onglet: string; sous: string | null };
	$: onglet = data.onglet;
</script>

<BarreOnglets pageId="calendrier" actif={onglet} />

{#if onglet === 'liste'}
	<!-- contenu liste -->
{:else if onglet === 'archives'}
	<!-- contenu archives -->
{/if}
```

⚠️ **Ne pas écrire la rangée à la main** : `BarreOnglets` lit la liste, l'ordre, les
libellés (configurables en administration) et les routes dans `$lib/pages.ts`, et
rend chaque onglet en `<a>`. Un `<div class="tabs">` local rouvre les cinq
divergences que ce composant vient de fermer.

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

## Helpers de formatage — **à importer, jamais à réécrire**

Les formats de date et de montant sont **centralisés**. Une page qui redéfinit
`fmtDate` localement casse la cohérence et **échoue en CI**.

```svelte
<script lang="ts">
	// $lib/date.ts — TOUTES les dates affichées (locale fr-FR + TZ Europe/Paris figés)
	import { fmtDate, fmtDateLong, fmtDateShort, fmtDatetime, fmtTime, fmtMonthYear } from '$lib/date';
	// $lib/utils.ts — montants, périmètre, extraits HTML
	import { fmtMontant, perimetreLabel, stripHtml, htmlPreview } from '$lib/utils';
</script>
```

| Helper | Entrée → sortie |
|---|---|
| `fmtDate(d)` | `'2026-07-25'` → `25/07/2026` |
| `fmtDatetime(d)` | horodatage → date + heure de Paris |
| `fmtMontant(v)` | `1234` → `1 234 €` · `1234.5` → `1 234,50 €` · `null` → `—` |
| `perimetreLabel(items)` | `['bat:1','parking']` → `Bât. 1 · Parking` |

**Interdits, vérifiés par `npm run lint:dates`** (sur `front/src/` **et**
`vite.config.ts`) : `toLocaleDateString`, `toLocaleTimeString`,
`Intl.DateTimeFormat` et `new Date(…).toLocaleString` **sans `timeZone`**. Restent
autorisés : `toISOString()` seul (sérialisation UTC d'un payload d'API) et
`toLocaleString()` sur un **nombre** — ce n'est pas une date.

Un alias local qui délègue au helper partagé (`const formatDate = fmtDatetimeShort`)
est une indirection inutile : appeler directement le helper.

🔴 **Et il n'y a plus d'exception.** Cette section en déclarait une — le rendu
d'une description mixte texte/HTML, « le seul helper qui reste légitimement
local » — dont le corps était :

```svelte
	function renderDesc(c: string) {          // ⚠️ NE PLUS ÉCRIRE CECI
		const t = c.trimStart();
		return safeHtml(t.startsWith('<') ? c : `<p>${c.replace(/
/g, '<br>')}</p>`);
	}
```

C'est **exactement** `safeDescription`, exportée par `$lib/sanitize.ts` — laquelle
a été créée pour supprimer ce helper, alors écrit en double sous le nom `renderDesc`
dans deux pages. **La consigne a survécu à la factorisation qu'elle décrivait.**

Le résultat était prévisible : `tickets/[id]` en portait une **troisième** copie,
sous le nom `renderContent`, jusqu'au 19/08/2026 (#429). Une skill qui enseigne un
motif supprimé le fait réapparaître — c'est la duplication qui se reproduit par sa
propre documentation.

```svelte
	import { safeDescription } from '$lib/sanitize';
	…
	{@html safeDescription(contenu)}
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

**OBLIGATOIRE** : tout `{@html}` passe par une fonction de `$lib/sanitize.ts`.
Elles sont **trois**, toutes adossées à DOMPurify — cette section n'en nommait
qu'une alors que les trois étaient en service, ce qui faisait lire 19 usages
conformes comme autant d'écarts (#429) :

| Fonction | Quand |
|---|---|
| `safeHtml` | contenu déjà en HTML riche |
| `safeRichContent` | riche **ou** texte simple, **sans** enveloppe — à l'intérieur d'un `<p>` |
| `safeDescription` | riche **ou** texte simple, **avec** enveloppe `<p>` |

```svelte
<!-- ✗ INTERDIT -->
{@html contenu}

<!-- ✗ INTERDIT AUSSI : une fonction locale, même correcte, même homonyme -->
{@html monRenduLocal(contenu)}

<!-- ✓ CORRECT -->
{@html safeDescription(contenu)}
```

🔒 **`npm run lint:html` le vérifie en CI** depuis le 19/08/2026 : il lit la liste
des assainisseurs **dans `sanitize.ts`** (une liste recopiée diverge au premier
ajout) et exige que le nom vienne de l'**import**. Deux exceptions nommées,
`Icon.svelte` et `QRCode.svelte`, déclarées dans le contrôle avec leur raison — et
une exception qui ne sert plus le fait échouer.

## Emojis non-BMP (U+10000 et au-delà)

Écrits littéralement, ils survivent mal aux allers-retours d'encodage sous Windows.
Les encoder :

```typescript
// JS / TS : échappement \u{HEX}
const icon = '\u{1F6E0}'; // 🔧
```

```svelte
<!-- Template HTML / Svelte : entité &#xHEX; -->
&#x1F539; <!-- 🔹 -->
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
