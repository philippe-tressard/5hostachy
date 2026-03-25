# Stack technique

> Architecture pensÃ©e pour un dÃ©ploiement autonome sur **Raspberry Pi 5** (ARM64, 4 ou 8 Go RAM).
> PrioritÃ© : simplicitÃ© d'installation, faible consommation de ressources, maintenance minimale.

Contrainte : Le choix des logiciels est Opensource avec des licences non copyleft forte.

---

## Vue d'ensemble

```
[Navigateur / PWA]
       â”‚  HTTPS
  [Caddy] â† reverse proxy + TLS automatique (Let's Encrypt)
       â”‚
  â”Œâ”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
  â”‚  SvelteKit (SSR/SPA)    â”‚  â† front-end
  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€-â”˜
       â”‚  HTTP interne
  â”Œâ”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
  â”‚  FastAPI (Python 3.12)  â”‚  â† API REST + WebSocket
  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
       â”‚
  â”Œâ”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
  â”‚  SQLite (fichier local) â”‚  â† base de donnÃ©es
  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

Orchestration : Docker Compose (3 services : caddy / front / api)
```

---

## Front-end web

- **Framework :** [SvelteKit](https://kit.svelte.dev/) v2
- **Langage :** TypeScript
- **Build :** Vite 5
- **CSS :** CSS natif + variables CSS (tokens charte graphique) â€” pas de framework CSS lourd
- **IcÃ´nes :** Lucide Svelte
- **PWA :** `@vite-pwa/sveltekit` â€” service worker + manifest gÃ©nÃ©rÃ© automatiquement
- **HTTP client :** `fetch` natif (pas de dÃ©pendance Axios)
- **Justification :** Bundle minimal (<150 Ko gzippÃ©), SSR natif, gÃ©nÃ¨re la PWA sans surcoÃ»t, tourne facilement dans un container Node Alpine sur ARM64.

---

## Application mobile

- **Approche : Progressive Web App (PWA)** â€” pas d'application native sÃ©parÃ©e
- **Plateformes :** iOS 16.4+ (Safari), Android 10+ (Chrome)
- **Installation :** ajout Ã  l'Ã©cran d'accueil via le navigateur (A2HS)
- **Fonctionnement hors-ligne :** Workbox (intÃ©grÃ© via vite-pwa) â€” cache des pages statiques et des donnÃ©es essentielles
- **Notifications push :** Web Push API (optionnel, phase 2)
- **Justification :** une seule codebase front = zÃ©ro complexitÃ© iOS/Android, aucun App Store requis, adaptÃ© Ã  une audience fermÃ©e (rÃ©sidents identifiÃ©s).

---

## Back-end / API

- **Langage :** Python 3.12
- **Framework :** [FastAPI](https://fastapi.tiangolo.com/) â€” async, OpenAPI auto-gÃ©nÃ©rÃ©, lÃ©ger
- **Serveur ASGI :** Uvicorn (avec Gunicorn en mode worker sur le Pi)
- **Authentification :**
  - JWT (access token 15 min + refresh token 7 jours)
  - Mots de passe hashÃ©s bcrypt via `passlib`
  - Invitation par lien unique pour l'onboarding des rÃ©sidents (pas d'inscription publique)
- **Validation :** Pydantic v2 (intÃ©grÃ© FastAPI)
- **Emails :** `fastapi-mail` + SMTP local (ou relay Brevo/Mailgun) â€” templates renduÃ© via **Jinja2** (dÃ©jÃ  dÃ©pendance de FastAPI), contenu stockÃ© en base et Ã©ditable sans redÃ©ploiement
- **Justification :** Python est disponible nativement sur RPi, FastAPI dÃ©marre en < 1 s, consomme < 50 Mo RAM au repos.

---

## Base de donnÃ©es

- **SGBD :** SQLite 3 (fichier `app.db` persistÃ© dans un volume Docker)
- **ORM :** [SQLModel](https://sqlmodel.tiangolo.com/) (combine SQLAlchemy + Pydantic â€” alignÃ© avec FastAPI)
- **Migrations :** Alembic
- **Backup :** sauvegarde pÃ©riodique paramÃ©trable depuis l'interface admin (EF-WEB-015) â€” frÃ©quence quotidienne / **hebdomadaire (dÃ©faut)** / mensuelle, **3 versions historisÃ©es par dÃ©faut** (1â€“30 configurable), rotation automatique. PÃ©rimÃ¨tre : `app.db` + rÃ©pertoire fichiers uploadÃ©s. Archive `.tar.gz` dans le volume `/backups`. Cron gÃ©rÃ© par **APScheduler** (dÃ©pendance FastAPI). Restauration via l'UI avec confirmation par mot de passe admin. Notification email en cas dâ€™Ã©chec.
- **Ã‰volution possible :** migration vers PostgreSQL 16 (image ARM64 disponible) si > 100 utilisateurs actifs ou besoin de concurrence Ã©levÃ©e
- **Justification :** SQLite est sans serveur, zÃ©ro configuration, parfaitement suffisant pour une copropriÃ©tÃ© de taille humaine (< 200 rÃ©sidents, < 50 connexions simultanÃ©es).

---

## Infrastructure / HÃ©bergement

### MatÃ©riel cible

| Composant     | SpÃ©cification recommandÃ©e                        |
|---------------|--------------------------------------------------|
| Carte         | Raspberry Pi 5 â€” 8 Go RAM                       |
| Stockage OS   | Carte microSD A2 â‰¥ 64 Go (ou SSD NVMe via HAT)  |
| Stockage data | SSD USB 3 externe â‰¥ 128 Go (volumes Docker)     |
| OS            | Raspberry Pi OS Lite 64-bit (Debian Bookworm)    |
| Alimentation  | Alimentation officielle 5V/5A USB-C              |

### Orchestration

- **Docker Engine** 26+ (ARM64) + **Docker Compose** v2
- Fichier unique `docker-compose.yml` Ã  la racine du projet :

```yaml
# aperÃ§u â€” 3 services
services:
  caddy:      # reverse proxy TLS
  front:      # SvelteKit (node:22-alpine)
  api:        # FastAPI (python:3.12-slim)
volumes:
  caddy_data:
  app_data:   # contient app.db + backups
```

### Reverse proxy

- **Caddy 2** : TLS automatique Let's Encrypt, configuration en 5 lignes (Caddyfile), support HTTP/3, compression Brotli native.
- Domaine : sous-domaine dédié (ex. `parc.local` en LAN ou `example.com` avec DynDNS si accès externe).

### AccÃ¨s rÃ©seau

- **LAN uniquement (option 1) :** accÃ¨s via IP fixe locale (ex. `<RPi-IP>`) â€” le Pi n'est pas exposÃ© sur Internet. Simple et sÃ©curisÃ©.
- **AccÃ¨s externe (option 2) :** tunnel [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) (gratuit, sans ouvrir de port sur la box) â€” recommandÃ© si les rÃ©sidents accÃ¨dent depuis l'extÃ©rieur.

### Pare-feu (UFW)

| RÃ¨gle | Ports | Source |
|-------|-------|--------|
| SSH | 22/tcp | LAN `192.168.x.0/24` uniquement |
| HTTP | 80/tcp | toutes sources |
| HTTPS | 443/tcp + 443/udp | toutes sources |
| Tout le reste | â€” | **bloquÃ©** |

### CI/CD

- **DÃ©ploiement :** `git pull` + `docker compose up -d --build` sur le Pi (dÃ©clenchÃ© manuellement ou via webhook GitHub/Gitea).
- **Gitea** (optionnel) : instance Git auto-hÃ©bergÃ©e sur le Pi si l'Ã©quipe ne veut pas dÃ©pendre de GitHub.
- **Watchtower** (optionnel) : mise Ã  jour automatique des images Docker en production.

---

## PrÃ©requis d'installation (rÃ©sumÃ©)

```bash
# 1. Sur le Pi (Raspberry Pi OS 64-bit)
sudo apt update && sudo apt install -y docker.io docker-compose-plugin

# 2. Cloner le dÃ©pÃ´t
git clone https://github.com/[org]/5hostachy.git
cd 5hostachy

# 3. Configurer l'environnement
cp .env.example .env
# Ã©diter .env : SECRET_KEY, domaine, SMTP...

# 4. Lancer
docker compose up -d
```

---

## Contraintes et limites connues

| Contrainte | Impact | Mitigation |
|---|---|---|
| SQLite mono-Ã©criture | Pas de concurrence d'Ã©criture Ã©levÃ©e | Suffisant pour l'usage cible ; migrer PostgreSQL si besoin |
| Coupure de courant | Perte de donnÃ©es non persistÃ©es | Volume SSD + UPS (alimentation sans coupure) recommandÃ© |
| Pas de CDN | Latence lÃ©gÃ¨rement plus haute si accÃ¨s distant | Cloudflare Tunnel inclut un cache CDN gratuit |
| Mises Ã  jour manuelles | Intervention humaine requise | Watchtower ou cron `git pull` automatisable |
