# CLAUDE.md — 5Hostachy

Règles de développement à appliquer dans toutes les sessions sur ce projet.

## Principe fondamental

Avant toute implémentation : **grep le pattern existant**. Si le pattern existe ≥ 2 fois → l'appliquer à l'identique. Si une demande contredit un pattern établi → signaler le conflit et demander confirmation.

Les références canoniques sont dans `.github/skills/`.

---

## Stack

- **Backend** : FastAPI + SQLModel + SQLite WAL + Alembic (`api/`)
- **Frontend** : SvelteKit v2 + TypeScript strict + Vite + PWA (`front/`)
- **Infra** : Docker Compose + Caddy + Raspberry Pi 5
- **Langue** : français exclusif (interface + nommage des champs)

---

## Patterns UX établis

### Carte expansible
- **Une seule** carte ouverte à la fois : `expandedItems = new Set([id])`
- Méta (lieu, périmètre, auteur) : toujours visible en état collapsé ET expandé
- Prévisualisation : `.clamp-5` (5 lignes max, `-webkit-line-clamp: 5`)
- `role="button"` + `tabindex="0"` + `on:keydown` (Enter/Space) obligatoires
- `on:click|stopPropagation` sur les actions secondaires dans le corps
- Border-left : `var(--color-border)` → `var(--color-primary)` au hover/expand
- Urgence : `border-left-color: var(--color-danger)` — **jamais de badge texte 🚨**

### Icônes de contexte
- 📍 = lieu physique (adresse, salle) — texte inline, pas de badge
- 🔹 = périmètre logique (Parking, Bât.) — badge `.badge-gray` ou `.badge-blue`
- **Ne jamais mélanger** les deux

### Périmètre
- Ne pas afficher si valeur = `'résidence'`
- Séparateur multi-périmètre : ` · ` (espace · espace)
- Labels : `'résidence'→'Copropriété entière'`, `'bat:1'→'Bât. 1'`, `parking→'Parking'`, `cave→'Cave'`

### Ligne de publication
Ordre : `[📌 coin absolu] [Brouillon?] Titre [Statut] [🔹 Périmètre]`
Badges **toujours après** le titre, jamais avant.

### Onglets (Tabs)
- `role="tablist"` sur le conteneur, `role="tab"` sur chaque bouton
- CSS : `.tabs` + `.tabs button.active`
- **Ne jamais** utiliser le pattern `view-toggle` / `view-btn` (supprimé)

### Pill buttons
- `≤ 8 options`, libellés courts, `type="button"` obligatoire
- Classes : `.perimetre-pills`, `.pill`, `.pill-active`

### Visibilité Kanban (calendrier + widget dashboard)

Filtre colonnes : `if (col.id === 'ag' || col.id === 'cs') return canSeeAG;`

| Colonne     | Locataire        | Copropriétaire   | CS / Admin  |
| ----------- | ---------------- | ---------------- | ----------- |
| AG          | ✗                | ✓                | ✓           |
| CS          | ✗                | ✓                | ✓           |
| Syndic      | ✓                | ✓                | ✓           |
| Prestataire | ✓                | ✓                | ✓           |
| Terminé     | ✓ (affichables)  | ✓ (affichables)  | ✓ (tout)    |
| Annulé      | masqué dashboard | masqué dashboard | masqué      |

Items non-affichables : masqués aux non-CS/admin (sauf `maintenance_recurrente`).

### Archiver vs Supprimer
- Archiver (📦) : CS + admin → `PATCH { archivee: true }` — vue principale
- Supprimer (🗑️) : admin seul → `DELETE` — vue Archives uniquement
- Jamais de bouton Supprimer sur la vue principale

### Champs de formulaire
- Requis : label suivi de ` *` (`Titre *`)
- Pas de mention "(optionnel)" — l'absence de `*` suffit
- Actions : bouton secondaire/Annuler **à gauche**, action primaire **à droite**

---

## Conventions Svelte / TypeScript

### Imports standard d'une page
```svelte
<script lang="ts">
    import Icon from '$lib/components/Icon.svelte';
    import { onMount } from 'svelte';
    import { isCS, isAdmin, currentUser } from '$lib/stores/auth';
    import { getPageConfig, configStore, siteNomStore } from '$lib/stores/pageConfig';
    import { safeHtml } from '$lib/sanitize';
    import { toast } from '$lib/components/Toast.svelte';
</script>
```

### Sécurité XSS — OBLIGATOIRE
```svelte
<!-- INTERDIT -->
{@html contenu}

<!-- CORRECT -->
{@html safeHtml(contenu)}
```
Seule exception : `Icon.svelte` (SVG hardcodé côté serveur).

### Accessibilité
- `role="button"` + `tabindex="0"` + `on:keydown` sur éléments cliquables non-`<button>`
- `role="tablist"` / `role="tab"` sur les onglets
- `aria-modal="true"` + `role="dialog"` sur les modales
- `aria-label` + `title` sur tous les boutons icône-seule

### Variables CSS disponibles
```css
var(--color-primary)        /* Bleu Seine #1E3A5F */
var(--color-primary-light)  /* Bleu clair fond */
var(--color-danger)         /* Rouge urgence/erreur */
var(--color-success)        /* Vert */
var(--color-warning)        /* Orange */
var(--color-border)
var(--color-text)
var(--color-text-muted)
var(--color-bg)
var(--color-surface)
var(--radius)
var(--shadow)
```

### Helpers de formatage (à réutiliser)
```typescript
fmtDate(d: string)          // DD Mon YYYY
fmtDateHeure(d: string)     // DD Mon YYYY HH:mm
perimetreLabel(items)       // 'bat:1,parking' → 'Bât. 1 · Parking'
renderDesc(c: string)       // texte ou HTML → HTML sanitisé
```

### Emojis non-BMP (U+10000+)
```typescript
// JS/TS : encoder \u{HEX}
const icon = '\u{1F6E0}'; // 🔧

// HTML/Svelte template : encoder &#xHEX;
// &#x1F539; pour 🔹
```

---

## Conventions Backend (Python / FastAPI)

### Modèle SQLModel
- `__tablename__` = snake_case français
- Champs en français snake_case : `statut_validation`, `date_debut`
- Timestamps : suffixe `_le` → `cree_le`, `mis_a_jour_le`
- FK : `{modele}_id = Field(default=None, foreign_key="table.id")`
- Soft delete : `actif: bool = Field(default=True)` (pas de suppression physique sauf admin)
- Enums : `class MonEnum(str, Enum)` → slugs français lowercase

### Schémas Pydantic (3 par entité)
- `EntiteCreate` : champs d'entrée, pas d'id ni timestamps
- `EntiteRead` : sortie complète avec id + timestamps, `class Config: from_attributes = True`
- `EntiteUpdate` : tous les champs `Optional` pour PATCH partiel

### Migrations Alembic
- ID séquentiel 4 chiffres : `0087`, `0088`…
- **Jamais** modifier une migration existante — créer une nouvelle
- **Jamais** de f-string dans `op.execute()` → `text(...).bindparams(...)`
- SQLite : pas de `ALTER TYPE`, pas de `CREATE TYPE`
- `start.sh` a `set -e` : une migration qui crash = conteneur bloqué

### Dépendances d'auth
| Dependency | Usage |
|-----------|-------|
| `get_current_user` | Tout utilisateur connecté |
| `require_cs_or_admin` | Création/modification de contenu |
| `require_admin` | Suppression définitive, config système |
| `require_proprietaire` | Fonctions propriétaires |
| `get_acting_user` | Délégation (header `X-Acting-As`) |

### Sécurité
- JWT HS256 en cookies `httponly=True`, `secure=settings.cookie_secure`, `samesite="strict"`
- CORS : allowlist explicite, jamais `["*"]` avec `credentials=True`
- Rate limiting slowapi sur `/auth/*`
- Uploads : UUID-prefix + `os.path.basename()` + `re.sub(r"[^\w.\-]", "_", ...)`

---

## Checklist avant commit

### Frontend
- [ ] Pattern existant réutilisé (pas de variante ad hoc)
- [ ] Méta toujours visible en mode collapsé
- [ ] `.clamp-5` sur les aperçus
- [ ] `safeHtml()` sur tout `{@html}`
- [ ] Accessibilité : `role`, `tabindex`, `aria-label`, `on:keydown`
- [ ] Périmètre : pas affiché si `'résidence'`
- [ ] Archiver (pas supprimer) sur la vue principale
- [ ] Champs requis : label + ` *`

### Backend (nouveau endpoint)
- [ ] Modèle dans `models/core.py`
- [ ] Schémas Create/Read/Update dans `schemas.py`
- [ ] Migration créée avec bon numéro séquentiel
- [ ] Router créé + enregistré dans `main.py`
- [ ] Client TypeScript ajouté dans `front/src/lib/api.ts`

### Manuel utilisateur
- [ ] `docs/manuel-utilisateur.html` mis à jour dans le même commit
- [ ] Synchronisé : `Copy-Item docs/manuel-utilisateur.html front/static/manuel-utilisateur.html`

---

## Infrastructure & Monitoring

### Serveurs
- **RPi 1** `192.168.1.222` (PhT-RB5) · **RPi 2** `192.168.1.223` (PhT-RB5i2)
- RPi actif : `cat /opt/5hostachy/.active` — conteneurs uniquement sur le RPi actif
- En cas de site HS : SSH sur le RPi actif → `cd /opt/5hostachy && docker compose up -d`

### Crontabs (sudo root — identiques sur les 2 RPi)
```
0 2 * * *   bascule.sh        # bascule active/standby
0 3 * * 0   maintenance.sh    # purge, VACUUM, rotation logs (dimanche)
*/5 * * * * health-watch.sh   # failover automatique si site HS
```

### Monitoring APScheduler (tourne dans le conteneur API)
| Heure | Job | Alerte email si… |
|-------|-----|-----------------|
| 03:00 | backup | — |
| 09:00 | **health_check** | WhatsApp déconnecté · backup > 25h · disque < 15% |
| 18:00 | whatsapp_scheduled | — |
| 02:00 | telemetry_aggregation | — |

### WhatsApp bridge
- Reconnexion QR : Admin → WhatsApp → **bouton Statut** (affiche le QR si déconnecté)
- Session corrompue (`creds.json` vide) : vider le volume + redémarrer le bridge
  ```bash
  docker run --rm -v 5hostachy_whatsapp_auth:/data alpine sh -c 'rm -rf /data/*'
  cd /opt/5hostachy && docker compose up -d whatsapp-bridge
  ```
- `bascule.sh` ne propage jamais un `creds.json` vide vers le peer

---

## Git & MEP

- `main` = production protégé — toutes les modifications via PR vers `dev`
- Prefixes commits : `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `perf:`
- MEP : `MaJ-Hostachy.sh` (pull + reset + sync docs + rebuild Docker + health check)
- `.env` non versionné · `SECRET_KEY` min 32 chars · `ENABLE_API_DOCS=false` en prod
