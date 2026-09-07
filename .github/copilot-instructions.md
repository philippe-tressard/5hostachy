# Copilot Instructions — Projet Hostachy

## Convention datetime — OBLIGATOIRE

Toutes les dates et heures DOIVENT respecter le fuseau `Europe/Paris`.

### Backend (Python / FastAPI)

- **Stocker en UTC** : utiliser `datetime.utcnow()`, jamais `datetime.now()` sans timezone
- **Sérialisation** : toutes les réponses passent par `UTCJSONResponse` (dans `main.py`) qui ajoute le suffixe `Z` aux datetimes naïves
- Si retour manuel d'un dict avec `.isoformat()`, ajouter `+ "Z"` explicitement
- **Requêtes SQLite groupées par jour/mois** : ajouter le décalage Paris avec `func.strftime("%Y-%m-%d", col, paris_offset_str)` où `paris_offset_str = f"+{offset} hours"`
- **Calculs bornes jour/mois** : utiliser `ZoneInfo("Europe/Paris")` pour obtenir minuit Paris et le convertir en UTC naïf pour la requête DB
- **Schedulers** : utiliser `datetime.now(ZoneInfo("Europe/Paris"))` ou configurer `timezone="Europe/Paris"`

### Frontend (Svelte / TypeScript)

- **Formater les dates** : TOUJOURS importer depuis `$lib/date.ts` (`fmtDate`, `fmtDateShort`, `fmtDatetime`, `fmtTime`, etc.)
- **Interdit** : utiliser `new Date(x).toLocaleDateString(...)`, `.toLocaleTimeString(...)` ou `.toLocaleString(...)` en inline pour les dates
- Les fonctions de `$lib/date.ts` utilisent toutes `timeZone: 'Europe/Paris'` et le locale `'fr-FR'`
- `.getTime()` est OK pour tri/comparaison (millisecondes UTC)
- Si besoin d'un nouveau format non couvert par `$lib/date.ts`, l'ajouter dans ce fichier avec `timeZone: 'Europe/Paris'`

### Docker

- Les containers `front` et `api` ont `TZ=Europe/Paris` dans `docker-compose.yml`

## Stack technique

- **Frontend** : SvelteKit (Svelte 4), TypeScript, adapter-node
- **Backend** : FastAPI 0.115.6, SQLModel 0.0.22 (Pydantic v2), SQLite
- **Infra** : Docker Compose, Caddy reverse proxy, RPi 5
- **Langue** : interface et code métier en français

## Conventions de code

- Variables, fonctions et commentaires en français
- Commits en français, format : `type: description` (ex: `fix: corriger l'affichage des dates`)
- Branche de travail : `dev` (jamais push direct sur `main`)
