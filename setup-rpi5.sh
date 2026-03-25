#!/usr/bin/env bash
# =============================================================================
#  setup-rpi5.sh â€” Installation & configuration du serveur 5Hostachy
#  Cible : Raspberry Pi 5 â€” Raspberry Pi OS Lite 64-bit (Debian Bookworm)
#  Usage : sudo bash setup-rpi5.sh [--domain parc.local] [--cloudflare]
# =============================================================================
set -euo pipefail

# â”€â”€â”€ Couleurs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
die()     { echo -e "${RED}[ERREUR]${RESET} $*" >&2; exit 1; }

# â”€â”€â”€ ParamÃ¨tres â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
DOMAIN="<RPi-IP>"
ENABLE_CLOUDFLARE=false
ENABLE_WATCHTOWER=false
INSTALL_DIR="/opt/5hostachy"
DATA_DIR="/data/5hostachy"
VERSION="1.3.0"
BACKUP_DIR="${DATA_DIR}/backups"
APP_USER="hostachy"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain)       DOMAIN="$2";           shift 2 ;;
    --cloudflare)   ENABLE_CLOUDFLARE=true; shift   ;;
    --watchtower)   ENABLE_WATCHTOWER=true; shift   ;;
    --dir)          INSTALL_DIR="$2";      shift 2 ;;
    *) die "Argument inconnu : $1" ;;
  esac
done

[[ $EUID -ne 0 ]] && die "Ce script doit Ãªtre exÃ©cutÃ© en root (sudo)."

echo -e "\n${BOLD}=========================================================${RESET}"
echo -e "${BOLD}   5Hostachy â€” Setup Raspberry Pi 5${RESET}"
echo -e "${BOLD}   Version  : ${CYAN}${VERSION}${RESET}"
echo -e "${BOLD}   Domaine  : ${CYAN}${DOMAIN}${RESET}"
echo -e "${BOLD}   Dossier  : ${CYAN}${INSTALL_DIR}${RESET}"
echo -e "${BOLD}=========================================================${RESET}\n"

# =============================================================================
# 1. MISE Ã€ JOUR SYSTÃˆME
# =============================================================================
info "Mise Ã  jour du systÃ¨me..."
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq \
  curl wget git ca-certificates gnupg lsb-release \
  ufw fail2ban unattended-upgrades \
  cron sqlite3 rsync
success "SystÃ¨me mis Ã  jour."

# Node.js 22 LTS (nÃ©cessaire pour scaffolder SvelteKit)
if ! command -v node &>/dev/null || [[ "$(node -v)" < "v22" ]]; then
  info "Installation de Node.js 22 LTS..."
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash - -qq
  apt-get install -y -qq nodejs
  success "Node.js $(node -v) / npm $(npm -v) installÃ©s."
else
  success "Node.js dÃ©jÃ  installÃ© : $(node -v)"
fi

# =============================================================================
# 2. DOCKER ENGINE + DOCKER COMPOSE V2
# =============================================================================
if ! command -v docker &>/dev/null; then
  info "Installation de Docker Engine (ARM64)..."

  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/debian/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg

  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/debian \
    $(lsb_release -cs) stable" \
    > /etc/apt/sources.list.d/docker.list

  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
  success "Docker $(docker --version) installÃ©."
else
  success "Docker dÃ©jÃ  installÃ© : $(docker --version)"
fi

# VÃ©rification Docker Compose v2
docker compose version &>/dev/null || die "docker compose v2 introuvable."

# =============================================================================
# 3. UTILISATEUR APPLICATIF
# =============================================================================
if ! id "${APP_USER}" &>/dev/null; then
  info "CrÃ©ation de l'utilisateur ${APP_USER}..."
  useradd -r -m -s /bin/bash "${APP_USER}"
  usermod -aG docker "${APP_USER}"
  success "Utilisateur ${APP_USER} crÃ©Ã©."
else
  usermod -aG docker "${APP_USER}" 2>/dev/null || true
  success "Utilisateur ${APP_USER} dÃ©jÃ  existant."
fi

# =============================================================================
# 4. ARBORESCENCE
# =============================================================================
info "CrÃ©ation de l'arborescence..."
mkdir -p "${INSTALL_DIR}"/{caddy,front,api,scripts}
mkdir -p "${DATA_DIR}"/{db,backups}
chown -R "${APP_USER}:${APP_USER}" "${INSTALL_DIR}" "${DATA_DIR}"
success "Arborescence crÃ©Ã©e."

# =============================================================================
# 5. FICHIERS DE CONFIGURATION
# =============================================================================

# â”€â”€ 5a. .env â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
info "GÃ©nÃ©ration du fichier .env..."
SECRET_KEY=$(openssl rand -hex 32)
cat > "${INSTALL_DIR}/.env" <<EOF
# â”€â”€ Application â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
APP_ENV=production
SECRET_KEY=${SECRET_KEY}
DOMAIN=${DOMAIN}

# â”€â”€ Base de donnÃ©es â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
DATABASE_URL=sqlite:////data/db/app.db

# â”€â”€ Authentification JWT â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# â”€â”€ Email (SMTP) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
MAIL_SERVER=smtp.example.com
MAIL_PORT=587
MAIL_USERNAME=noreply@example.com
MAIL_PASSWORD=change_me
MAIL_FROM=noreply@${DOMAIN}
MAIL_TLS=true

# â”€â”€ SvelteKit â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
PUBLIC_API_URL=http://${DOMAIN}/api
ORIGIN=http://${DOMAIN}

# â”€â”€ RÃ©seau local â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
PI_IP=<RPi-IP>

# â”€â”€ Cloudflare Tunnel (optionnel) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# CLOUDFLARE_TUNNEL_TOKEN=votre_token_ici
EOF
chmod 600 "${INSTALL_DIR}/.env"
success ".env gÃ©nÃ©rÃ© (SECRET_KEY alÃ©atoire incluse)."

# â”€â”€ 5b. Caddyfile â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
info "GÃ©nÃ©ration du Caddyfile..."
cat > "${INSTALL_DIR}/caddy/Caddyfile" <<EOF
{
    admin off
}

:80 {
    # HTTP pur â€” suffisant pour un usage LAN local
    # (tls internal sur une IP brute cause ERR_SSL_PROTOCOL_ERROR)

    # Compression (br/Brotli non disponible dans caddy:2-alpine)
    encode zstd gzip

    # Headers de sÃ©curitÃ©
    header {
        X-Content-Type-Options "nosniff"
        X-Frame-Options        "SAMEORIGIN"
        Referrer-Policy        "strict-origin-when-cross-origin"
        -Server
    }

    # API back-end
    handle /api/* {
        uri strip_prefix /api
        reverse_proxy api:8000
    }

    # WebSocket
    handle /ws/* {
        reverse_proxy api:8000
    }

    # Front-end SvelteKit
    handle {
        reverse_proxy front:3000
    }

    # Logs
    log {
        output file /data/logs/caddy_access.log {
            roll_size 10mb
            roll_keep 5
        }
        format json
    }
}
EOF
success "Caddyfile gÃ©nÃ©rÃ©."

# â”€â”€ 5c. docker-compose.yml â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
info "GÃ©nÃ©ration du docker-compose.yml..."
cat > "${INSTALL_DIR}/docker-compose.yml" <<'EOF'
# =============================================================================
#  5Hostachy â€” Docker Compose
#  3 services : caddy / front / api
# =============================================================================
name: 5hostachy

services:

  # â”€â”€ Reverse proxy TLS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  caddy:
    image: caddy:2-alpine
    container_name: caddy
    restart: unless-stopped
    ports:
      - "80:80"
    volumes:
      - ./caddy/Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
      - app_data:/data/logs
    networks:
      - hostachy
    depends_on:
      - front
      - api

  # â”€â”€ Front-end SvelteKit â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  front:
    build:
      context: ./front
      dockerfile: Dockerfile
    container_name: front
    restart: unless-stopped
    env_file: .env
    environment:
      - NODE_ENV=production
    networks:
      - hostachy
    depends_on:
      - api

  # â”€â”€ API FastAPI â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  api:
    build:
      context: ./api
      dockerfile: Dockerfile
    container_name: api
    restart: unless-stopped
    env_file: .env
    volumes:
      - app_data:/data
    networks:
      - hostachy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3

networks:
  hostachy:
    driver: bridge

volumes:
  caddy_data:
  caddy_config:
  app_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /data/5hostachy
EOF
success "docker-compose.yml gÃ©nÃ©rÃ©."

# â”€â”€ 5d. Dockerfile front (SvelteKit Node Alpine ARM64) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
info "GÃ©nÃ©ration du Dockerfile front-end..."
cat > "${INSTALL_DIR}/front/Dockerfile" <<'EOF'
# â”€â”€ Build â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# â”€â”€ Runtime â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/build ./build
COPY --from=build /app/package.json package-lock.json ./
RUN npm ci --omit=dev && addgroup -S app && adduser -S app -G app
USER app
EXPOSE 3000
CMD ["node", "build/index.js"]
EOF
success "Dockerfile front gÃ©nÃ©rÃ©."

# â”€â”€ 5g. Scaffold projet SvelteKit â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
info "Initialisation du projet SvelteKit dans front/..."

# package.json
cat > "${INSTALL_DIR}/front/package.json" <<'EOF'
{
  "name": "5hostachy-front",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev":   "vite dev",
    "build": "vite build",
    "preview": "vite preview"
  },
  "devDependencies": {
    "@sveltejs/adapter-node":       "^5.2.12",
    "@sveltejs/kit":                "^2.16.0",
    "@sveltejs/vite-plugin-svelte": "^5.0.3",
    "svelte":                       "^5.20.2",
    "typescript":                   "^5.8.2",
    "vite":                         "^6.2.0"
  },
  "dependencies": {
    "lucide-svelte": "^0.468.0"
  },
  "type": "module"
}
EOF

# svelte.config.js
cat > "${INSTALL_DIR}/front/svelte.config.js" <<'EOF'
import adapter from '@sveltejs/adapter-node';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({ out: 'build' })
  }
};

export default config;
EOF

# vite.config.ts
cat > "${INSTALL_DIR}/front/vite.config.ts" <<'EOF'
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

// PWA : installer @vite-pwa/sveltekit et dÃ©commenter le bloc ci-dessous
// import { SvelteKitPWA } from '@vite-pwa/sveltekit';

export default defineConfig({
  plugins: [
    sveltekit()
    // SvelteKitPWA({
    //   registerType: 'autoUpdate',
    //   manifest: {
    //     name: '5Hostachy',
    //     short_name: 'Hostachy',
    //     description: 'Portail de la copropriÃ©tÃ©',
    //     theme_color: '#ffffff',
    //     icons: [
    //       { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
    //       { src: '/icon-512.png', sizes: '512x512', type: 'image/png' }
    //     ]
    //   }
    // })
  ]
});
EOF

# tsconfig.json
cat > "${INSTALL_DIR}/front/tsconfig.json" <<'EOF'
{
  "extends": "./.svelte-kit/tsconfig.json",
  "compilerOptions": {
    "strict": true
  }
}
EOF

# src/app.html
mkdir -p "${INSTALL_DIR}/front/src"
cat > "${INSTALL_DIR}/front/src/app.html" <<'EOF'
<!doctype html>
<html lang="fr">
  <head>
    <meta charset="utf-8" />
    <link rel="icon" href="%sveltekit.assets%/favicon.png" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="theme-color" content="#ffffff" />
    %sveltekit.head%
  </head>
  <body data-sveltekit-preload-data="hover">
    <div style="display: contents">%sveltekit.body%</div>
  </body>
</html>
EOF

# src/app.css
cat > "${INSTALL_DIR}/front/src/app.css" <<'EOF'
/* Variables CSS â€” charte graphique 5Hostachy */
:root {
  --color-primary:    #2563eb;
  --color-secondary:  #64748b;
  --color-bg:         #f8fafc;
  --color-surface:    #ffffff;
  --color-text:       #0f172a;
  --color-muted:      #94a3b8;
  --radius:           0.5rem;
  --font-sans:        system-ui, sans-serif;
}

*, *::before, *::after { box-sizing: border-box; }
body { margin: 0; font-family: var(--font-sans); background: var(--color-bg); color: var(--color-text); }
EOF

# src/routes/+layout.svelte
mkdir -p "${INSTALL_DIR}/front/src/routes"
cat > "${INSTALL_DIR}/front/src/routes/+layout.svelte" <<'EOF'
<script lang="ts">
  import '../app.css';
  let { children } = $props();
</script>
{@render children()}
EOF

# src/routes/+page.svelte
cat > "${INSTALL_DIR}/front/src/routes/+page.svelte" <<'EOF'
<script lang="ts">
  import { Home } from 'lucide-svelte';
</script>

<main>
  <Home size={32} />
  <h1>5Hostachy</h1>
  <p>Portail de la copropriÃ©tÃ© â€” en cours de dÃ©veloppement.</p>
</main>

<style>
  main { display: flex; flex-direction: column; align-items: center;
         justify-content: center; min-height: 100vh; gap: 1rem; }
</style>
EOF

# static/
mkdir -p "${INSTALL_DIR}/front/static"
touch "${INSTALL_DIR}/front/static/.gitkeep"

# GÃ©nÃ©ration du package-lock.json (requis par npm ci dans Docker)
info "GÃ©nÃ©ration du package-lock.json (npm install)..."
cd "${INSTALL_DIR}/front"
sudo -u "${APP_USER}" npm install --prefer-offline 2>&1 | tail -5
cd -
success "Projet SvelteKit initialisÃ© avec package-lock.json."

# â”€â”€ 5e. Dockerfile API (FastAPI Python 3.12 ARM64) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
info "GÃ©nÃ©ration du Dockerfile API..."
cat > "${INSTALL_DIR}/api/Dockerfile" <<'EOF'
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# DÃ©pendances systÃ¨me minimales
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gcc libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# DÃ©pendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code applicatif
COPY . .

# Migrations Alembic au dÃ©marrage + lancement Gunicorn
RUN addgroup --system app && adduser --system --group app
USER app

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && gunicorn main:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers 2 \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -"]
EOF
success "Dockerfile API gÃ©nÃ©rÃ©."

# â”€â”€ 5f. requirements.txt API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
cat > "${INSTALL_DIR}/api/requirements.txt" <<'EOF'
fastapi==0.115.*
uvicorn[standard]==0.34.*
gunicorn==23.*
sqlmodel==0.0.*
alembic==1.14.*
pydantic[email]==2.*
passlib[bcrypt]==1.7.*
python-jose[cryptography]==3.3.*
fastapi-mail==1.4.*
python-multipart==0.0.*
httpx==0.28.*
EOF
success "requirements.txt API gÃ©nÃ©rÃ©."

# =============================================================================
# 6. SCRIPT DE BACKUP SQLite
# =============================================================================
info "CrÃ©ation du script de backup..."
cat > "${INSTALL_DIR}/scripts/backup.sh" <<EOF
#!/usr/bin/env bash
# Backup journalier de la base SQLite
set -euo pipefail

DB_FILE="${DATA_DIR}/db/app.db"
BACKUP_DIR="${BACKUP_DIR}"
TIMESTAMP=\$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="\${BACKUP_DIR}/app_\${TIMESTAMP}.db"
KEEP_DAYS=30

if [[ ! -f "\${DB_FILE}" ]]; then
  echo "Base de donnÃ©es introuvable : \${DB_FILE}"
  exit 1
fi

# Backup atomique SQLite
sqlite3 "\${DB_FILE}" ".backup '\${BACKUP_FILE}'"
gzip "\${BACKUP_FILE}"

# Nettoyage des backups > KEEP_DAYS jours
find "\${BACKUP_DIR}" -name "*.db.gz" -mtime +\${KEEP_DAYS} -delete

echo "Backup crÃ©Ã© : \${BACKUP_FILE}.gz"
EOF
chmod +x "${INSTALL_DIR}/scripts/backup.sh"
success "Script de backup crÃ©Ã©."

# Cron journalier Ã  3h du matin
CRON_JOB="0 3 * * * ${APP_USER} ${INSTALL_DIR}/scripts/backup.sh >> /var/log/5hostachy-backup.log 2>&1"
if ! grep -qF "5hostachy-backup" /etc/crontab 2>/dev/null; then
  echo "${CRON_JOB}" >> /etc/crontab
  success "Cron backup configurÃ© (tous les jours Ã  03h00)."
fi

# =============================================================================
# 7. SCRIPT DE DÃ‰PLOIEMENT
# =============================================================================
cat > "${INSTALL_DIR}/scripts/deploy.sh" <<'EOF'
#!/usr/bin/env bash
# Mise Ã  jour et redÃ©ploiement de l'application
set -euo pipefail
cd "$(dirname "$0")/.."
echo "[$(date)] DÃ©ploiement dÃ©marrÃ©..."
git pull --rebase
docker compose pull
docker compose up -d --build --remove-orphans
docker image prune -f
echo "[$(date)] DÃ©ploiement terminÃ©."
EOF
chmod +x "${INSTALL_DIR}/scripts/deploy.sh"
success "Script de dÃ©ploiement crÃ©Ã©."

# =============================================================================
# 8. PARE-FEU (UFW)
# =============================================================================
info "Configuration du pare-feu UFW..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow from 192.168.1.0/24 to any port 22 proto tcp  # SSH â€” rÃ©seau local uniquement
ufw allow 80/tcp    # HTTP  â†’ Caddy
ufw allow 443/tcp   # HTTPS â†’ Caddy
ufw allow 443/udp   # HTTP/3 (QUIC)
ufw --force enable
success "Pare-feu UFW configurÃ©."

# =============================================================================
# 9. FAIL2BAN
# =============================================================================
info "Configuration de fail2ban..."
cat > /etc/fail2ban/jail.d/5hostachy.conf <<'EOF'
[sshd]
enabled  = true
port     = ssh
maxretry = 5
bantime  = 1h

[caddy-auth]
enabled  = false
# Ã€ activer quand le filtre Caddy sera dÃ©fini
EOF
systemctl enable --now fail2ban
success "fail2ban activÃ©."

# =============================================================================
# 10. CLOUDFLARE TUNNEL (optionnel)
# =============================================================================
if [[ "${ENABLE_CLOUDFLARE}" == "true" ]]; then
  info "Installation de cloudflared..."
  curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg \
    | gpg --dearmor -o /usr/share/keyrings/cloudflare-main.gpg
  echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] \
    https://pkg.cloudflare.com/cloudflared $(lsb_release -cs) main" \
    > /etc/apt/sources.list.d/cloudflared.list
  apt-get update -qq && apt-get install -y -qq cloudflared

  warn "Action manuelle requise : configurez le tunnel avec :"
  echo "  cloudflared tunnel login"
  echo "  cloudflared tunnel create 5hostachy"
  echo "  cloudflared tunnel route dns 5hostachy ${DOMAIN}"
  echo "  # Puis ajoutez CLOUDFLARE_TUNNEL_TOKEN dans .env"
  success "cloudflared installÃ©."
fi

# =============================================================================
# 11. WATCHTOWER (optionnel â€” mises Ã  jour automatiques)
# =============================================================================
if [[ "${ENABLE_WATCHTOWER}" == "true" ]]; then
  info "Ajout de Watchtower au docker-compose..."
  cat >> "${INSTALL_DIR}/docker-compose.yml" <<'EOF'

  # â”€â”€ Mises Ã  jour automatiques â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  watchtower:
    image: containrrr/watchtower
    container_name: watchtower
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    command: --cleanup --schedule "0 0 4 * * *"   # tous les jours Ã  04h00
    networks:
      - hostachy
EOF
  success "Watchtower ajoutÃ© (mise Ã  jour quotidienne Ã  04h00)."
fi

# =============================================================================
# 12. MISE Ã€ JOUR AUTOMATIQUE DES PAQUETS DEBIAN
# =============================================================================
cat > /etc/apt/apt.conf.d/50unattended-upgrades-hostachy <<'EOF'
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}-security";
};
Unattended-Upgrade::Automatic-Reboot "false";
Unattended-Upgrade::Mail "root";
EOF
systemctl enable --now unattended-upgrades
success "Mises Ã  jour de sÃ©curitÃ© automatiques activÃ©es."

# =============================================================================
# RÃ‰SUMÃ‰ FINAL
# =============================================================================
echo ""
echo -e "${BOLD}${GREEN}=========================================================${RESET}"
echo -e "${BOLD}${GREEN}   Installation terminÃ©e !${RESET}"
echo -e "${BOLD}${GREEN}=========================================================${RESET}"
echo ""
echo -e "  RÃ©pertoire projet  : ${CYAN}${INSTALL_DIR}${RESET}"
echo -e "  DonnÃ©es & backups  : ${CYAN}${DATA_DIR}${RESET}"
echo -e "  Adresse IP LAN     : ${CYAN}<RPi-IP>${RESET}"
echo -e "  Domaine            : ${CYAN}${DOMAIN}${RESET}"
echo ""
echo -e "${YELLOW}Prochaines Ã©tapes :${RESET}"
echo "  1. DÃ©posez le code de l'application dans ${INSTALL_DIR}/front/ et ${INSTALL_DIR}/api/"
echo "  2. Ã‰ditez ${INSTALL_DIR}/.env (MAIL_*, DOMAIN, etc.)"
if [[ "${ENABLE_CLOUDFLARE}" == "true" ]]; then
  echo "  3. Configurez le tunnel Cloudflare (voir instructions ci-dessus)"
  echo "  4. Lancez : cd ${INSTALL_DIR} && docker compose up -d"
else
  echo "  3. Lancez : cd ${INSTALL_DIR} && docker compose up -d"
fi
echo ""
echo -e "  Acc\u00e8s local        : ${CYAN}https://<RPi-IP>${RESET}  (certificat auto-sign\u00e9 \u00e0 accepter)"
echo -e "  Logs en temps r\u00e9el : ${CYAN}docker compose -f ${INSTALL_DIR}/docker-compose.yml logs -f${RESET}"
echo -e "  Statut des services: ${CYAN}docker compose -f ${INSTALL_DIR}/docker-compose.yml ps${RESET}"
echo ""
