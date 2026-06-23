#!/bin/bash
# =============================================================================
#  boot-role-guard.sh — Garde-fou anti-split-brain au DÉMARRAGE
#
#  Lancé une fois au boot par hostachy-role-guard.service (oneshot), APRÈS
#  docker + cloudflared. But : empêcher qu'un nœud qui redémarre se remette à
#  servir le public alors que le peer est déjà l'actif → SPLIT-BRAIN.
#
#  POURQUOI ce garde existe (incident du 23/06/2026) :
#    rpi2 (actif) a gelé → health-watch a basculé sur rpi1 → mais rpi2 était
#    injoignable, donc son cloudflared est resté `enabled`. Au reboot de rpi2 :
#    cloudflared redémarre tout seul + docker compose (restart: unless-stopped)
#    → les 2 tunnels actifs en même temps = split-brain (les 2 DB divergent).
#    Les couches bascule.sh/health-watch.sh maintiennent l'invariant
#    enabled/disabled quand le nœud démoté est JOIGNABLE ; ce garde est le
#    backstop pour le cas où il était gelé/éteint pendant la démotion.
#
#  RÈGLE : la vérité = « qui sert réellement le public ». Si le PEER tourne
#  (conteneurs + cloudflared actif), alors CE nœud doit être standby — quoi que
#  dise son propre .active (qui peut être périmé s'il a gelé pendant un failover).
#
#  Installation (one-shot, root, sur les 2 RPi) :
#    cp /opt/5hostachy/systemd/hostachy-role-guard.service /etc/systemd/system/
#    systemctl daemon-reload && systemctl enable hostachy-role-guard.service
#
#  Log : /var/log/hostachy-role-guard.log (via le service)
# =============================================================================
set -uo pipefail

REPO=/opt/5hostachy
PUBLIC_URL="https://5hostachy.fr/api/health"
FLAG="$REPO/.active"
SSH_CMD="ssh -i /root/.ssh/id_ed25519_bascule -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

case "$(hostname)" in
  PhT-RB5)   SELF="rpi1"; PEER="rpi2"; PEER_IP="192.168.1.223" ;;
  PhT-RB5i2) SELF="rpi2"; PEER="rpi1"; PEER_IP="192.168.1.222" ;;
  *) log "Hostname inconnu ($(hostname)) — abandon (aucune action)."; exit 0 ;;
esac

LOCAL_ACTIVE=$(cat "$FLAG" 2>/dev/null | tr -d '[:space:]' || echo "")
log "Boot role-guard sur $SELF — .active local='$LOCAL_ACTIVE'."

# ── État du peer (vérité terrain, pas le flag) ───────────────────────────────
# Une seule session SSH : conteneurs en cours, cloudflared actif, son .active.
PEER_RAW=$($SSH_CMD ptressard@"$PEER_IP" '
  echo "c=$(docker ps -q 2>/dev/null | wc -l | tr -d " ")"
  echo "cf=$(systemctl is-active cloudflared 2>/dev/null)"
  echo "act=$(cat /opt/5hostachy/.active 2>/dev/null | tr -d "[:space:]")"
' 2>/dev/null)
PEER_REACH=$?
PEER_C=0; PEER_CF=""; PEER_ACT=""
if [ $PEER_REACH -eq 0 ] && [ -n "$PEER_RAW" ]; then
  PEER_C=$(echo "$PEER_RAW"  | sed -n 's/^c=//p')
  PEER_CF=$(echo "$PEER_RAW" | sed -n 's/^cf=//p')
  PEER_ACT=$(echo "$PEER_RAW"| sed -n 's/^act=//p')
  log "Peer $PEER joignable — conteneurs=$PEER_C cloudflared=$PEER_CF .active=$PEER_ACT."
else
  log "Peer $PEER injoignable en SSH."
fi

# ── Actions ──────────────────────────────────────────────────────────────────
stand_down() {  # $1 = nom de l'actif réel (le peer)
  log "→ STANDBY : $SELF se retire (actif réel = $1)."
  sudo systemctl stop cloudflared    2>/dev/null && log "  cloudflared stoppé."  || log "  ⚠ stop cloudflared."
  sudo systemctl disable cloudflared 2>/dev/null && log "  cloudflared disabled." || log "  ⚠ disable cloudflared."
  ( cd "$REPO" && docker compose stop >/dev/null 2>&1 ) && log "  conteneurs stoppés." || log "  ⚠ stop conteneurs."
  echo "$1" > "$FLAG" && log "  .active corrigé → $1."
}

become_active() {
  log "→ ACTIF : $SELF assume le rôle actif."
  echo "$SELF" > "$FLAG" && log "  .active → $SELF."
  sudo systemctl enable cloudflared 2>/dev/null && log "  cloudflared enabled (survit au reboot)." || log "  ⚠ enable cloudflared."
  sudo systemctl start cloudflared  2>/dev/null && log "  cloudflared démarré (idempotent)."        || log "  ⚠ start cloudflared."
}

# Cas 1 — le peer SERT réellement (conteneurs + tunnel) → on se retire.
# Couvre le cas du 23/06 : .active local périmé (=$SELF) mais peer = vrai actif.
if [ "${PEER_C:-0}" -gt 0 ] && [ "$PEER_CF" = "active" ]; then
  stand_down "$PEER"
  exit 0
fi

# Cas 2 — départage cold-boot (coupure secteur : les 2 redémarrent ensemble).
# Le peer n'est pas (encore) servant. Si les DEUX flags désignent le peer comme
# actif et que le peer est joignable, on lui laisse la priorité (il démarre) au
# lieu de risquer un double-actif. Sinon, on prend le rôle actif.
if [ $PEER_REACH -eq 0 ] && [ "$LOCAL_ACTIVE" = "$PEER" ] && [ "$PEER_ACT" = "$PEER" ]; then
  log "Cold-boot : les 2 flags désignent $PEER comme actif — $SELF défère (anti double-actif)."
  stand_down "$PEER"
  exit 0
fi

become_active
exit 0
