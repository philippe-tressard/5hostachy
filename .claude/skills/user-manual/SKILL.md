---
name: user-manual
description: "Update the 5Hostachy user manual (manuel-utilisateur.html) when a feature is added or modified. Use when: adding a new feature visible to users, modifying UI behavior, adding a new page or section, updating navigation or workflows. Do NOT use for purely technical changes (migrations, refactor, backend-only security)."
argument-hint: "Describe the feature to document (e.g. 'new fournisseurs page with list and detail')"
---

# Manuel Utilisateur — 5Hostachy

Met à jour `docs/manuel-utilisateur.html` et synchronise vers `front/static/manuel-utilisateur.html`.

## Règle obligatoire

Toute modification UX ou fonctionnalité visible **doit** être documentée dans le manuel utilisateur dans le **même commit** que la fonctionnalité. Après modification :

```powershell
Copy-Item 5hostachy/docs/manuel-utilisateur.html 5hostachy/front/static/manuel-utilisateur.html
```

## Structure du document

```
docs/manuel-utilisateur.html
├── <head> : CSS variables, styles, responsive
├── <nav class="sidebar"> : Navigation latérale sticky
├── <header class="topbar"> : Titre + badge version
├── <main class="main">
│   ├── <section class="hero"> : Introduction
│   └── <section class="chapter" id="..." data-section="..."> : Chapitres
└── <footer class="doc-footer"> : Copyright
```

## Ajouter un nouveau chapitre

### 1. Définir la couleur dans `:root`

```css
--c-nouveau: #hexcolor;
```

### 2. Ajouter le lien dans la sidebar

```html
<div class="nav-section">
  <a class="nav-item" href="#nouveau">
    <span class="dot nav-dot-nouveau"></span>
    Nouveau Chapitre
  </a>
</div>
```

### 3. Ajouter le style du dot de navigation

```css
.nav-dot-nouveau { background: var(--c-nouveau); }
```

### 4. Ajouter le style de la card (border-top)

```css
.chapter[data-section="nouveau"] .card { border-top: 3px solid var(--c-nouveau); }
```

### 5. Créer la section dans `<main>`

```html
<section class="chapter" id="nouveau" data-section="nouveau">
  <div class="chapter-header">
    <div class="chapter-icon" style="background:#eef6ff; color:var(--c-nouveau)">
      🆕
    </div>
    <div>
      <h2>Titre du chapitre</h2>
      <p>Description courte du chapitre.</p>
    </div>
  </div>

  <div class="card">
    <h3>Sous-section</h3>
    <ul class="steps">
      <li class="step">
        <span class="step-num" style="background:var(--c-nouveau)">1</span>
        <div class="step-content">
          <strong>Titre de l'étape</strong>
          <p>Description détaillée de l'étape.</p>
        </div>
      </li>
      <li class="step">
        <span class="step-num" style="background:var(--c-nouveau)">2</span>
        <div class="step-content">
          <strong>Étape suivante</strong>
          <p>Description.</p>
        </div>
      </li>
    </ul>
  </div>
</section>
```

## Éléments de contenu disponibles

### Card (bloc principal)

```html
<div class="card">
  <h3>Titre de la card</h3>
  <p>Contenu texte...</p>
</div>
```

### Étapes numérotées

```html
<ul class="steps">
  <li class="step">
    <span class="step-num" style="background:var(--c-section)">1</span>
    <div class="step-content">
      <strong>Action à effectuer</strong>
      <p>Explication détaillée.</p>
    </div>
  </li>
</ul>
```

### Captures d'écran

```html
<div class="capture-grid">
  <div class="capture-card">
    <img src="img/capture.png" alt="Description de la capture" />
    <h3>Légende</h3>
    <p>Description de ce que montre la capture.</p>
    <span class="capture-tag">Catégorie</span>
  </div>
</div>
```

### Callouts (info, tip, warning, danger)

```html
<div class="callout info">
  <strong>ℹ️ Information</strong>
  <p>Texte informatif.</p>
</div>

<div class="callout tip">
  <strong>💡 Astuce</strong>
  <p>Conseil utile.</p>
</div>

<div class="callout warning">
  <strong>⚠️ Attention</strong>
  <p>Point de vigilance.</p>
</div>

<div class="callout danger">
  <strong>🚫 Important</strong>
  <p>Risque ou interdiction.</p>
</div>
```

### Badges de statut

```html
<div class="status-chip">
  <span class="dot" style="background:#22c55e"></span>
  Actif
</div>
```

### FAQ / Accordéon

```html
<details class="faq-item">
  <summary>Question fréquente ?</summary>
  <div class="faq-body">
    <p>Réponse détaillée.</p>
  </div>
</details>
```

## Couleurs des sections existantes

| Section | Variable CSS | Couleur | Emoji |
|---------|-------------|---------|-------|
| Connexion | `--c-login` | `#7c3aed` | 🔐 |
| Mes lots | `--c-lot` | `#0284c7` | 🏠 |
| Tickets | `--c-ticket` | `#ea580c` | 🎫 |
| Actualités | `--c-news` | `#059669` | 📰 |
| Calendrier | `--c-cal` | `#4f46e5` | 📅 |
| Badges | `--c-badges` | `#dc2626` | 🔴 |
| FAQ | `--c-faq` | `#0f766e` | ❓ |
| Résidence | `--c-residence` | `#0f766e` | 🏢 |
| Annuaire | `--c-annuaire` | `#0369a1` | 📇 |
| Profil | `--c-profil` | `#6d28d9` | 👤 |
| Prestataires | `--c-presta` | `#b45309` | 🔧 |
| Délégation | `--c-delegation` | `#d97706` | 🤝 |

## Checklist

- [ ] Chapitre ajouté/modifié dans `docs/manuel-utilisateur.html`
- [ ] Couleur CSS ajoutée si nouveau chapitre
- [ ] Lien sidebar ajouté si nouveau chapitre
- [ ] Style `.chapter[data-section="..."] .card` ajouté si nouveau chapitre
- [ ] Étapes numérotées pour les workflows
- [ ] Callouts pour les points importants
- [ ] Synchronisé : `Copy-Item docs/manuel-utilisateur.html front/static/manuel-utilisateur.html`
- [ ] Inclus dans le même commit que la fonctionnalité
