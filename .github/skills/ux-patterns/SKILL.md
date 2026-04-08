---
name: ux-patterns
description: "Apply and enforce 5Hostachy UX patterns: expand cards, tabs, pills, badges, pagination, accessibility, archiving, perimeter display, urgency, pinned items. Use when: implementing a new UI feature, reviewing UX consistency, checking if a pattern is correctly applied across all pages."
argument-hint: "Describe the UX element to implement or review (e.g. 'add tabs to page fournisseurs', 'review badge consistency')"
---

# UX Patterns — 5Hostachy

Guide de référence des patterns UX établis. Tout pattern utilisé ≥ 2 fois doit être uniforme sur **toutes** les occurrences du site.

## Règle d'uniformisation

1. **Avant** d'implémenter, vérifier si un pattern similaire existe déjà (grep / semantic search)
2. Si le pattern existe ≥ 2 fois → c'est un **pattern établi** → l'appliquer à l'identique
3. Si la demande contredit un pattern → **signaler le conflit** et demander confirmation
4. Après implémentation → mettre à jour `/memories/repo/ui-patterns.md`

## 1. Icônes de contexte

| Icône | Signification | Usage |
|-------|--------------|-------|
| 📍 | Lieu physique (adresse, salle) | Texte inline, pas de badge |
| 🔹 | Périmètre logique (Parking, Bât.) | Badge `.badge-gray` ou `.badge-blue` |

**Ne JAMAIS utiliser** 📍 pour un périmètre logique.

## 2. Affichage du périmètre

**Condition** : ne jamais afficher si valeur = `'résidence'` (c'est le défaut).

Labels canoniques :
```typescript
const PERIMETRE_LABELS = {
    'résidence': 'Copropriété entière',
    'bat:1': 'Bât. 1', 'bat:2': 'Bât. 2', 'bat:3': 'Bât. 3', 'bat:4': 'Bât. 4',
    parking: 'Parking', cave: 'Cave',
};
```

Séparateur multi-périmètre : ` · ` (espace · espace).

Rendus par page :
- Actualités : `<span class="badge badge-gray">📍 {label}</span>`
- Calendrier : `<span class="badge badge-blue">📍 {label}</span>`
- Tickets : `<p style="font-size:.8rem;color:var(--color-text-muted)">📍 {label}</p>`

## 3. Carte expansible (Expand Card)

**Le pattern principal** pour les listes (tickets, publications, événements, prestataires).

### Structure 2 lignes
- **Ligne 1** : icône + titre + badges clé
- **Ligne 2 (méta)** : lieu + périmètre + auteur — **toujours visible** (collapsé ET expandé)

### Règles
- **Une seule** carte ouverte à la fois
- Chargement lazy des détails au premier clic
- Prévisualisation `.clamp-5` (5 lignes max)
- Border-left : `4px solid var(--color-border)` → `var(--color-primary)` (hover/expanded)
- Urgence : `border-left-color: var(--color-danger)` — **pas de badge texte 🚨**
- `margin-bottom: .5rem` entre chaque item
- `box-shadow: 0 1px 2px rgba(30,58,95,.04)`
- Accessibilité : `role="button"` + `tabindex="0"` + `on:keydown`

### Préfixes par page
| Page | Préfixe CSS | Référence |
|------|------------|-----------|
| Actualités | `.pub-` | `actualites/+page.svelte` |
| Tickets | `.tk-` | `tickets/+page.svelte` |
| Calendrier | `.ev-` | `calendrier/+page.svelte` |
| Tableau de bord | `.pub-`, `.ev-`, `.tk-` | `tableau-de-bord/+page.svelte` |

## 4. Onglets (Tabs)

**Quand** : page avec 2+ vues ou sections distinctes.

- État : `let onglet: 'a' | 'b' = 'a'`
- `role="tablist"` sur le conteneur, `role="tab"` sur chaque bouton
- Descriptif par onglet : `_pc.onglets?.[onglet]?.descriptif`
- CSS : `.tabs` + `.tabs button.active`
- **Ne jamais utiliser** le pattern `view-toggle` / `view-btn` (pattern non-standard, supprimé)

Pages implémentées : `mon-lot`, `sondages`, `espace-cs`, `admin`, `calendrier`

## 5. Pill Buttons

**Quand** : choix exclusif ou multiple, ≤ 8 options, libellés courts.
**Préférer à** : `<select>`, `radio` en colonne, `checkbox` en colonne.

- Classes : `.perimetre-pills` (conteneur), `.pill`, `.pill-active`
- `type="button"` obligatoire (éviter soumission formulaire)
- Sélection multiple : toggle + reset auto vers défaut si aucun actif

Pages implémentées : `actualites`, `calendrier`

## 6. Ligne de publication

**Ordre** : `[📌 coin absolu] [Brouillon?] Titre [Statut] [📍 Périmètre]`

- Badges : toujours **après** le titre
- Urgence : bord gauche rouge uniquement (pas de badge texte)
- Épingle : badge absolu coin haut-gauche (`.pin-badge`)

## 7. Prévisualisation 5 lignes

Tout bloc expansible affiche **exactement 5 lignes** en état replié.

```css
.clamp-5 {
    display: -webkit-box;
    -webkit-line-clamp: 5;
    -webkit-box-orient: vertical;
    overflow: hidden;
}
```

Pages implémentées : `actualites`, `tableau-de-bord`, `faq`, `calendrier`, `sondages`

## 8. Archiver vs Supprimer

| Action | Qui | Où | API |
|--------|-----|-----|-----|
| 📦 Archiver | CS + admin | Vue principale | `PATCH { archivee: true }` |
| 🗑️ Supprimer | Admin seul | Vue Archives seule | `DELETE` (require_admin) |

Vue archives unifiée dans `calendrier/+page.svelte` (onglet Archives).

## 9. Champs obligatoires

Tout label de champ requis suivi de ` *` : `Titre *`, `Périmètre *`.

## 10. Fil d'évolutions

Structure pour les tickets/publications avec historique :

- `.evol-list` : border autour, séparateurs `<hr class="evol-sep">`
- `.evol-item` : `.evol-icon` + `.evol-body` (`.evol-meta` + `.evol-text`)
- Pagination : si > 7 → afficher 5 + bouton `.evol-more`
- Formulaire inline : pills type + textarea + select statut → `.evol-form`

## Checklist UX (à vérifier avant commit)

- [ ] Pattern existant réutilisé (pas de variante ad hoc)
- [ ] Méta toujours visible en mode collapsé
- [ ] `.clamp-5` sur les aperçus
- [ ] `safeHtml()` sur tout `{@html}`
- [ ] Accessibilité : `role`, `tabindex`, `aria-label`, `on:keydown`
- [ ] Périmètre : pas affiché si `'résidence'`
- [ ] Archiver (pas supprimer) sur la vue principale
- [ ] Champs requis : label + ` *`
- [ ] Labels en français
