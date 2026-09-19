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
	import EtatListe from '$lib/components/EtatListe.svelte';

	let items: Entity[] = [];
	let chargement = true;
	let erreur = '';

	onMount(async () => {
		try {
			items = await entityApi.list();
		} catch (e) {
			erreur = messageErreur(e);
		} finally {
			chargement = false;
		}
	});
</script>

<EtatListe {chargement} {erreur} vide={items.length === 0}>
	{#each items as item (item.id)}
		<!-- contenu -->
	{/each}
</EtatListe>
```

🔴 **Cet exemple portait le motif à deux branches** — `{#if loading}` puis
`{:else if items.length === 0}` — que `npm run lint:etat-liste` refuse. Il
laissait toujours un état de côté, et c'était l'**erreur** : un appel en échec
s'affichait comme une liste vide, donc comme « il n'y a rien » au lieu de « je
n'ai pas pu regarder ».

C'est le **cas zéro** de `standards/04` appliqué à un écran : une absence
d'information ne se rend pas comme une information d'absence. `EtatListe`
(24 écrans) porte les trois états, et `messageErreur` (`$lib/erreurs.ts`, 45
fichiers) porte le texte.

### Gestion d'erreurs API

Un message d'erreur ne se rédige pas dans un écran : il vient de
**`$lib/erreurs.ts`** (`messageErreur`), employé par 45 fichiers. Deux écrans qui
formulent le même échec autrement apprennent deux choses différentes à
l'utilisateur pour un seul fait.

🔒 `npm run lint:message-erreur` refuse la formulation locale, et
`npm run lint:catch-vide` refuse un `catch` qui avale l'erreur sans rien dire.

⚠️ **L'API de `toast` est `toast('error', message)`**, jamais `toast.error(…)` :
cette section enseignait la seconde forme, qui n'existe nulle part
(`Toast.svelte`). Une consigne qui décrit une API absente fait écrire du code qui
ne compile pas — et, pire, fait douter du composant plutôt que de la consigne.

### Chargement et listes vides

**`EtatListe`** (24 écrans) porte les trois états d'une liste : en cours, vide,
en erreur. Une page ne compose plus ces états elle-même.

🔒 `npm run lint:etat-liste` refuse le motif à deux branches
(`{#if chargement}…{:else if !items.length}…`) qui laissait toujours un état de
côté — le plus souvent l'erreur, affichée comme une liste vide. Et
`npm run lint:apercu` tient l'aperçu d'une carte.

⚠️ `<p>Chargement…</p>` écrit à la main n'existe plus nulle part, et cette
section l'enseignait encore. `$lib/chargement.ts` porte les libellés, et
`ChargementPartiel` le cas d'un bloc qui se recharge seul.

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

## Pattern: Carte de liste — **trois composants, aucun balisage à écrire**

🔴 Cette section décrivait un motif écrit à la main — conteneur
`role="button"`, `.ev-expand`, `expandedItems = new Set()`, `.clamp-5`. **Il n'en
reste aucune occurrence**, et trois linters refusent de le voir revenir.

| Ce qu'il faut | Composant / module | Contrôle |
|---|---|---|
| l'en-tête d'une carte (titre, icônes, chevron) | `EnteteCarte` (16 écrans) | `lint:entete-carte` — **exceptions vides** |
| l'aperçu du contenu, coupé à 3 lignes | `ApercuCarte` | `lint:apercu` |
| l'ouverture / fermeture d'un élément de liste | `$lib/listeDepliable.ts` | `lint:liste-depliable` |
| les pastilles d'état | `Pastille` (39 écrans) | `lint:statuts`, `lint:etats` |
| le périmètre affiché | `BadgePerimetre` (13 écrans) | `lint:libelle-perimetre`, `lint:teinte` |

⚠️ **`role="presentation"`, pas `role="button"`** sur le conteneur : le geste
d'ouverture appartient au chevron d'`EnteteCarte`, qui porte déjà son nom
accessible et son `keydown`. Un conteneur cliquable annonçait « bouton » un bloc
qui contient lui-même des boutons.

La **densité** d'une carte (ce qui va sur quelle ligne, et ce qui est masqué en
collapsé) est arbitrée dans `ux-patterns` §13 bis — elle a été validée à l'écran,
elle ne se redécide pas ici.

## Pattern: Où s'ouvre un formulaire — **c'est arbitré, pas au choix**

🔴 Cette section enseignait un `<div class="modal-overlay">` écrit à la main,
avec `showModal` et `.modal-actions`. **`npm run lint:modales` le refuse**, et
`.modal-actions` n'existe pas.

Le **cadre du geste** est tranché (`ux-patterns` §14, validé à l'écran après
quatre positions essayées) :

| Geste | Où |
|---|---|
| **créer** | en place, dans la page — **jamais** une modale |
| **modifier** | dans une fenêtre `Modale` (19 écrans) |
| **faire évoluer** | `EvolForm`, qui reçoit son `entite: EntiteDeclaree` |

🔒 `npm run lint:cadre-geste` et `npm run lint:geste-edition` tiennent cette
règle ; `lint:pied-formulaire` impose `PiedFormulaire` (28 écrans) pour les
boutons, `lint:ordre-sections` l'ordre des sections, `lint:champs` le libellé
d'un champ, et `lint:section-formulaire` leur découpe.

Un formulaire ne compose donc plus ni son enveloppe, ni son pied, ni l'ordre de
ses sections : il déclare son contenu.

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

## CSS : où vivent les règles

🔴 **`app.css` ne porte plus aucune règle** depuis le 27/08/2026 (#453) : il n'a
gardé que ses `@import` vers `src/styles/*.css`. Les deux skills l'annonçaient
encore comme « le fichier des règles globales », à onze endroits.

| Fichier | Ce qu'il porte |
|---|---|
| `src/styles/socle.css` | les **variables** (couleurs, rayon, ombre) et la base |
| `src/styles/ecrans.css` | les classes partagées entre écrans |
| les autres `src/styles/*.css` | par domaine — voir les `@import` d'`app.css` |

**La liste des variables n'est pas recopiée ici** : elle se lit dans
`socle.css`, où chacune porte son usage en commentaire. Cette section en listait
douze alors que le fichier en déclare **dix-huit** — une liste recopiée est
fausse dès qu'on en ajoute une, et personne ne relit une consigne qu'on n'a pas
touchée.

🔒 `npm run lint:styles`, `lint:classes-nues`, `lint:css-duplique`,
`lint:css-orphelin` et `lint:charte` tiennent l'usage des couleurs et des
classes. `lint:points-rupture` impose les points de rupture de l'échelle
déclarée, et `lint:largeur-saisie` interdit d'écrire une largeur dans un écran —
`--largeur-saisie` est **généralisée** depuis le 18/08/2026, et la constante
`ROUTES_LARGEUR_PLEINE` qui la limitait à une route n'existe plus.

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

**On archive, on ne supprime pas** : la vue principale masque ce qui est
archivé, et `ListeEtArchives` / `ArchivesParAnnee` en donnent l'accès.
`npm run lint:archives` tient cette règle.

⚠️ **Il n'y a pas de bouton 📦 « Archiver ».** L'archivage suit l'**état** de
l'objet — un ticket résolu, un événement passé — et le geste explicite n'existe
que là où l'utilisateur doit trancher lui-même. Cette section enseignait le
bouton ; `ux-patterns` §16 l'interdisait au même moment. **Une skill qui se
contredit avec l'autre n'enseigne rien** : c'est `ux-patterns` §16 qui fait foi,
et la divergence de `CarteEvenement` y est déclarée.

La **suppression définitive** reste possible pour un administrateur, et c'est le
seul cas : `require_admin` côté API.
