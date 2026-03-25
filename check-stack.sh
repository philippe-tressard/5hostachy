#!/usr/bin/env bash
# =============================================================================
#  check-stack.sh — Vérification de la configuration SERVEUR 5Hostachy
#
#  Valide uniquement la config réseau/routage (Caddy, Docker).
#  Aucun code applicatif requis : 1 seul container Caddy avec respond.
#
#  Prérequis : Docker Engine + Docker Compose v2
#  Usage     : bash check-stack.sh [--keep]
#              --keep : conserver le container après le test
# =============================================================================
set -euo pipefail

# --- Couleurs ----------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()  { echo -e "${CYAN}[INFO]${RESET}  $*"; }
ok()    { echo -e "${GREEN}[ OK ]${RESET}  $*"; PASS=$((PASS+1)); }
fail()  { echo -e "${RED}[FAIL]${RESET}  $*"; FAIL=$((FAIL+1)); }
die()   { echo -e "${RED}[ERREUR]${RESET} $*" >&2; exit 1; }

PASS=0; FAIL=0
KEEP=false
WORK_DIR="/tmp/5hostachy-check"
VERSION="1.4.1"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --keep) KEEP=true; shift ;;
    *) die "Argument inconnu : $1" ;;
  esac
done

command -v docker &>/dev/null || die "Docker non trouve. Lancez d'abord setup-rpi5.sh"

# Detection automatique sudo
if docker info &>/dev/null 2>&1; then
  DOCKER="docker"
elif sudo docker info &>/dev/null 2>&1; then
  DOCKER="sudo docker"
  info "Docker necessite sudo — utilisation automatique de 'sudo docker'."
else
  die "Impossible d'acceder a Docker. Verifiez que Docker est demarre."
fi

${DOCKER} compose version &>/dev/null || die "docker compose v2 non trouve."

echo -e "\n${BOLD}=========================================================${RESET}"
echo -e "${BOLD}   5Hostachy - Verification configuration serveur${RESET}"
echo -e "${BOLD}   1 seul container Caddy - reponses directes (respond)${RESET}"
echo -e "${BOLD}   Version : ${CYAN}${VERSION}${RESET}"
echo -e "${BOLD}=========================================================${RESET}"

# Versions
DOCKER_VER=$(${DOCKER} version --format '{{.Server.Version}}' 2>/dev/null || echo "?")
COMPOSE_VER=$(${DOCKER} compose version --short 2>/dev/null || echo "?")
CADDY_VER=$(${DOCKER} run --rm caddy:2-alpine caddy version 2>/dev/null | head -1 || echo "?")
echo -e "  Docker Engine  : ${CYAN}${DOCKER_VER}${RESET}"
echo -e "  Docker Compose : ${CYAN}${COMPOSE_VER}${RESET}"
echo -e "  Caddy image    : ${CYAN}${CADDY_VER}${RESET}"
echo ""

cleanup() {
  if [[ "${KEEP}" == "false" ]]; then
    info "Nettoyage..."
    ${DOCKER} compose -f "${WORK_DIR}/docker-compose.yml" down --volumes --remove-orphans 2>/dev/null || true
    rm -rf "${WORK_DIR}"
  else
    echo -e "\n${YELLOW}[KEEP]${RESET}  Pour nettoyer : ${DOCKER} compose -f ${WORK_DIR}/docker-compose.yml down"
  fi
}
trap cleanup EXIT

# =============================================================================
# 1. ARBORESCENCE
# =============================================================================
info "Creation de l'arborescence temporaire..."
rm -rf "${WORK_DIR}"
mkdir -p "${WORK_DIR}/caddy"

# =============================================================================
# 2. CADDYFILE — respond natif (aucun backend requis)
# =============================================================================
info "Generation du Caddyfile..."
cat > "${WORK_DIR}/caddy/Caddyfile" <<'CADDYEOF'
{
    admin off
}

:80 {
    encode zstd gzip

    header {
        X-Content-Type-Options "nosniff"
        X-Frame-Options        "SAMEORIGIN"
        Referrer-Policy        "strict-origin-when-cross-origin"
        -Server
    }

    handle /api/health {
        respond `{"status":"ok","service":"api"}` 200
    }
    handle /api/db-check {
        respond `{"status":"ok","sqlite":"stub OK"}` 200
    }
    handle /api/* {
        respond `{"message":"5Hostachy API stub"}` 200
    }
    handle /health {
        respond `{"status":"ok","service":"front"}` 200
    }
    handle {
        respond `<html><body><h1>5Hostachy - Front OK</h1></body></html>` 200
    }

    log {
        output stdout
        format console
    }
}
CADDYEOF

# =============================================================================
# 3. DOCKER COMPOSE — 1 seul service Caddy
# =============================================================================
info "Generation du docker-compose.yml..."
cat > "${WORK_DIR}/docker-compose.yml" <<'COMPOSEEOF'
name: 5hostachy-check
services:
  caddy:
    image: caddy:2-alpine
    container_name: check-caddy
    ports:
      - "8080:80"
    volumes:
      - ./caddy/Caddyfile:/etc/caddy/Caddyfile:ro
COMPOSEEOF

# =============================================================================
# 4. DEMARRAGE
# =============================================================================
info "Pull de l'image caddy:2-alpine..."
${DOCKER} compose -f "${WORK_DIR}/docker-compose.yml" pull --quiet

info "Demarrage de Caddy..."
${DOCKER} compose -f "${WORK_DIR}/docker-compose.yml" up -d

# =============================================================================
# 5. ATTENTE
# =============================================================================
info "Attente du demarrage (max 30s)..."
echo ""
MAX=6; COUNT=0
while [[ $COUNT -lt $MAX ]]; do
  if curl -sf --max-time 2 "http://localhost:8080/health" &>/dev/null; then
    ok "Caddy demarre et accessible sur :8080"
    break
  fi
  sleep 5; COUNT=$((COUNT+1))
  echo -ne "  attente Caddy [${COUNT}/${MAX}]...\r"
done
if [[ $COUNT -eq $MAX ]]; then
  fail "Caddy inaccessible apres 30s"
  info "Logs Caddy :"
  ${DOCKER} logs check-caddy --tail=30
  exit 1
fi

# =============================================================================
# 6. TESTS HTTP
# =============================================================================
echo ""
info "Tests de routage (http://localhost:8080)..."

check() {
  local label=$1 url=$2 pattern=$3
  local body
  body=$(curl -sf --max-time 5 "$url" 2>/dev/null || echo "")
  if echo "$body" | grep -qi "$pattern"; then
    ok  "${label}"
  else
    fail "${label}  (reponse: $(echo "$body" | head -c 120))"
  fi
}

check "Route /             -> front HTML"       "http://localhost:8080/"             "Front OK"
check "Route /health       -> front JSON"       "http://localhost:8080/health"       '"service":"front"'
check "Route /api/health   -> api JSON"         "http://localhost:8080/api/health"   '"service":"api"'
check "Route /api/db-check -> sqlite stub"      "http://localhost:8080/api/db-check" '"sqlite"'

HEADERS=$(curl -sI --max-time 5 "http://localhost:8080/")

echo "$HEADERS" | grep -qi "x-content-type-options: nosniff" \
  && ok  "Header X-Content-Type-Options -> nosniff" \
  || fail "Header X-Content-Type-Options manquant"

echo "$HEADERS" | grep -qi "x-frame-options: sameorigin" \
  && ok  "Header X-Frame-Options -> SAMEORIGIN" \
  || fail "Header X-Frame-Options manquant"

echo "$HEADERS" | grep -qi "referrer-policy" \
  && ok  "Header Referrer-Policy present" \
  || fail "Header Referrer-Policy manquant"

echo "$HEADERS" | grep -qi "^server:" \
  && fail "Header Server expose (devrait etre supprime)" \
  || ok  "Header Server supprime (-Server OK)"

# =============================================================================
# 7. RAPPORT FINAL
# =============================================================================
echo ""
echo -e "${BOLD}---------------------------------------------------------${RESET}"
TOTAL=$((PASS+FAIL))
if [[ $FAIL -eq 0 ]]; then
  echo -e "${BOLD}  Resultat : ${GREEN}${PASS}/${TOTAL} OK${RESET}  --  Configuration Caddy validee"
else
  echo -e "${BOLD}  Resultat : ${GREEN}${PASS} OK${RESET}  /  ${RED}${FAIL} ECHEC${RESET}  (sur ${TOTAL} tests)"
fi
echo -e "${BOLD}---------------------------------------------------------${RESET}"
echo ""

if [[ $FAIL -gt 0 ]]; then
  info "Logs Caddy :"
  ${DOCKER} logs check-caddy --tail=30
  exit 1
fi

echo -e "  URL de test : ${CYAN}http://localhost:8080${RESET}"
echo -e "  Image Caddy : ${CYAN}caddy:2-alpine${RESET}"
echo ""
