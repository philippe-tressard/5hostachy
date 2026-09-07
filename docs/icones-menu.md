# Icônes du menu de navigation

Ce document recense les icônes utilisées (et proposées) pour chaque entrée du menu principal de l'application 5Hostachy.

Les icônes proviennent de la bibliothèque **Lucide** (intégrée via le composant `Icon.svelte`).  
Référence complète : https://lucide.dev/icons/

---

## Icônes actuelles et alternatives proposées

| Route | Label FR | Label EN | Icône actuelle | Alternatives proposées | Justification |
|---|---|---|---|---|---|
| `/tableau-de-bord` | Accueil | Home | `layout-dashboard` | `house`, `home`, `gauge` | Dashboard = vue d'ensemble ; `gauge` si on veut insister sur les indicateurs |
| `/actualites` | Actualités | News | `megaphone` | `newspaper`, `rss`, `bell-ring` | `newspaper` plus classique ; `megaphone` express mieux la diffusion d'annonces |
| `/calendrier` | Calendrier | Calendar | `calendar` | `calendar-days`, `calendar-check` | `calendar-days` affiche la grille de jours, plus expressif |
| `/tickets` | Tickets | Requests | `ticket` | `message-square-text`, `clipboard-list`, `file-pen` | `ticket` peut être confondu avec billetterie ; `message-square-text` évoque mieux une demande écrite |
| `/annuaire` | Annuaire | Directory | `book-open` | `contact`, `users`, `address-book` | `contact` ou `users` plus explicites pour un annuaire de personnes |
| `/residence` | Résidence | Building | `building-2` | `building`, `landmark`, `home-modern` | `building-2` convient bien ; `landmark` si la résidence a un caractère patrimonial |
| `/mon-lot` | Mon lot | My unit | `home` | `door-closed`, `key`, `square-user` | `home` est ambigu avec Accueil ; `door-closed` distingue mieux l'appartement personnel |
| `/acces-securite` | Accès & badges | Access & badges | `key-round` | `shield-check`, `scan-line`, `badge` | `key-round` est clair ; `scan-line` évoquerait le passage de badge |
| `/prestataires` | Prestataires | Contractors | `wrench` | `hard-hat`, `briefcase`, `tool` | `hard-hat` reconnaissable pour les corps de métier bâtiment |
| `/sondages` | Communauté | Participation | `clipboard-list` | `users-round`, `vote`, `message-circle` | `users-round` met l'accent sur la communauté ; `vote` si sondages prioritaires |
| `/faq` | FAQ | FAQ | `help-circle` | `circle-help`, `book-marked`, `info` | `circle-help` = alias Lucide v3 de `help-circle` ; cohérent |
| `/espace-cs` | Espace CS | Board space | `settings` | `shield-half`, `users-cog`, `briefcase` | `settings` générique ; `shield-half` distingue mieux le rôle conseil syndical |
| `/admin` | Paramétrage | Settings | `shield-check` | `sliders-horizontal`, `settings-2`, `cog` | `shield-check` met l'accent sécurité/admin ; `sliders-horizontal` plus neutre pour "paramétrage" |

> **Note :** l'icône de la marque (logo dans la sidebar) utilise `building-2` — il est préférable de ne pas la réutiliser pour la route `/residence` afin d'éviter la confusion visuelle.

---

## Recommandations de cohérence

- **Accueil vs Mon lot** : `layout-dashboard` (accueil) et `door-closed` (mon lot) évitent la collision entre deux icônes de maison.
- **Paramétrage vs Espace CS** : garder `shield-check` pour l'Admin (rôle le plus élevé) et utiliser `shield-half` pour l'Espace CS.
- **Demandes** : préférer `message-square-text` à `ticket` pour éviter l'association avec la billetterie d'événements.
- **Communauté** : `users-round` est plus intuitif que `clipboard-list` si la page met en avant les sondages et interactions entre résidents.

---

## Palette finale recommandée

| Route | Icône recommandée |
|---|---|
| `/tableau-de-bord` | `layout-dashboard` ✅ (conserver) |
| `/actualites` | `newspaper` |
| `/calendrier` | `calendar-days` |
| `/tickets` | `message-square-text` |
| `/annuaire` | `users` |
| `/residence` | `building-2` ✅ (conserver) |
| `/mon-lot` | `door-closed` |
| `/acces-securite` | `key-round` ✅ (conserver) |
| `/prestataires` | `hard-hat` |
| `/sondages` | `users-round` |
| `/faq` | `help-circle` ✅ (conserver) |
| `/espace-cs` | `shield-half` |
| `/admin` | `sliders-horizontal` |

---

## Icônes actuellement en production (emojis)

Déployé le 2026-03-12 — remplacement des icônes Lucide par des emojis pour cohérence avec la page Prestataires.

| Menu | Route | Emoji |
|---|---|---|
| Accueil | `/tableau-de-bord` | 🏠 |
| Actualités | `/actualites` | 📢 |
| Calendrier | `/calendrier` | 📅 |
| Tickets | `/tickets` | 📝 |
| Annuaire | `/annuaire` | 📖 |
| Résidence | `/residence` | 🏢 |
| Mon lot | `/mon-lot` | 🏡 |
| Accès & badges | `/acces-securite` | 🔑 |
| Communauté | `/sondages` | 🗳️ |
| FAQ | `/faq` | ❓ |
| Prestataires | `/prestataires` | 🔧 |
| Espace CS | `/espace-cs` | ⚙️ |
| Paramétrage | `/admin` | 🛡️ |
| Profil | `/profil` | 👤 |
| Déconnexion | — | 🚪 |
| Logo (brand) | — | 🏢 |
