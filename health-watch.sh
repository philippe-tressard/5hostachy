#!/bin/bash
# =============================================================================
#  health-watch.sh — Surveillance site 5Hostachy + reprise automatique
#
#  Tourne toutes les 5 min sur les DEUX RPi via cron.
#  Si l'URL publique ne répond plus :
#    - RPi actif   → redémarre ses propres conteneurs + cloudflared
#    - RPi standby → confirme la panne, PUIS établit qu'elle vient bien du nœud
#                    actif (sondes LAN + edge, cf. decide_failover) avant de
#                    prendre le relais. Une panne de chemin public (WAN/DNS/
#                    Cloudflare) est signalée SANS bascule — incident du 30/07/2026.
#  Envoie un email d'alerte dans tous les cas (via Python3 standalone).
#
#  Test de la logique de décision (sans effet de bord) : ./health-watch.sh --selftest
#
#  Cron (sudo crontab sur chaque RPi) :
#    */5 * * * * /opt/5hostachy/health-watch.sh >> /var/log/hostachy-health-watch.log 2>&1
# =============================================================================
set -uo pipefail

REPO=/opt/5hostachy
PUBLIC_URL="https://5hostachy.fr/api/health"
# Sonde « puis-je servir le public ? » : exerce DNS + TLS vers l'edge Cloudflare,
# c'est-à-dire exactement ce dont le tunnel a besoin (cf. decide_failover).
EDGE_URL="https://www.cloudflare.com/cdn-cgi/trace"
ALERT_EMAIL="ptressard@icloud.com"
# Noms attendus par lib-alert.sh (cf. plus bas). `COOLDOWN_FILE` reste défini
# séparément car il est aussi purgé quand le site redevient OK.
COOLDOWN_FILE="/tmp/health-watch-cooldown"
ALERT_COOLDOWN_FILE="$COOLDOWN_FILE"
ALERT_COOLDOWN_SECONDS=1800   # 30 min entre deux alertes email pour éviter le spam
LOCK_MAX_AGE_S=900      # 15 min : au-delà, .bascule-lock est considéré orphelin

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# ── Sonde HTTP — UNE valeur, toujours ────────────────────────────────────────
# `curl -w '%{http_code}'` écrit DÉJÀ « 000 » quand la requête échoue ; le
# `|| echo 000` historique en ajoutait une seconde, d'où les « HTTP 000000 »
# des logs et des alertes de la nuit du 30/07/2026. Cosmétique ici, mais la
# même construction rendait un contrôle de check-reliability.sh faussement vert
# (comparaison d'entiers sur « 0\n0 ») : une sonde ne doit rendre qu'une valeur.
http_code() {  # $1 = URL, $2 = timeout (défaut 10) → code HTTP ou 000
    local code
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time "${2:-10}" "$1" 2>/dev/null)
    echo "${code:-000}"
}

ip_of() { case "$1" in rpi1) echo 192.168.1.222 ;; rpi2) echo 192.168.1.223 ;; *) echo "" ;; esac; }

# ── Décision de failover (PURE — aucun effet de bord, testable) ──────────────
# Args : actif_en_lan  edge_joignable   (valeurs "ok" / autre)
#   actif_en_lan   : l'API du nœud ACTIF répond-elle en LAN (http://<actif>/api/health) ?
#   edge_joignable : CE nœud atteint-il l'edge Cloudflare (DNS + TLS) ?
# Échoit : "failover" ou "abstain:<raison>"
#
# POURQUOI (incident du 30/07/2026, 00:52→01:46) : une panne DNS/WAN a coupé le
# tunnel Cloudflare des DEUX nœuds (« lookup … on 1.0.0.1:53: server misbehaving »).
# Chacun sondait UNIQUEMENT l'URL publique, chacun a conclu « l'autre est HS » :
# 12 failovers croisés en 55 min, stack arrêtée/redémarrée alternativement sur les
# deux nœuds, rôle actif changé 12 fois SANS synchronisation de base (un failover
# ne sync pas la DB), et à trois reprises `systemctl start cloudflared` a échoué
# sur le nouvel actif juste avant que l'ancien soit démoté → cloudflared inactif
# sur AUCUN nœud. Le site n'a évidemment jamais été rétabli par ces bascules :
# le nœud actif servait parfaitement, c'est le chemin public qui était coupé.
#
# Règle : ne pas basculer quand le nœud actif PROUVE qu'il sert encore (LAN) et
# que nous-mêmes ne pouvons pas atteindre l'edge — nous ne ferions pas mieux.
# Le chemin critique « nœud actif réellement mort » est INCHANGÉ : dès que la
# sonde LAN ne répond pas, on bascule comme avant, edge joignable ou non.
decide_failover() {
    local lan="$1" edge="$2"
    if [ "$lan" = "ok" ] && [ "$edge" != "ok" ]; then
        echo "abstain:chemin-public-coupe"; return
    fi
    echo "failover"
}

# ── Self-test de decide_failover() (aucun effet de bord) ─────────────────────
if [ "${1:-}" = "--selftest" ]; then
    fail=0
    check() { # description attendu lan edge
        local desc="$1" exp="$2"; shift 2
        local got; got=$(decide_failover "$@")
        if [ "$got" = "$exp" ]; then echo "PASS  $desc  → $got"
        else echo "FAIL  $desc  attendu=$exp obtenu=$got"; fail=1; fi
    }
    echo "== self-test health-watch.decide_failover =="
    check "actif mort, edge OK (cas nominal)"          "failover"                  ko  ok
    check "actif mort + WAN KO (on prend le rôle)"     "failover"                  ko  ko
    check "actif vivant en LAN, edge KO (30/07/2026)"  "abstain:chemin-public-coupe" ok  ko
    check "actif vivant en LAN, edge OK (tunnel HS)"   "failover"                  ok  ok
    # Une sonde qui n'a PAS pu s'exécuter ne vaut pas « actif vivant » : sans preuve
    # que l'actif sert, on ne bloque pas le failover (disponibilité > économie de bascule).
    check "sonde LAN indisponible → pas de blocage"    "failover"                  ""  ko
    [ $fail -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
    exit $fail
fi

# Déploiement/bascule réellement en cours ? .bascule-lock est posé par bascule.sh
# et MaJ-Hostachy.sh. MAIS si la machine gèle/reboote pendant (cas du 17/06 : rpi2
# bloqué pendant la MAJ, reboot manuel), le trap de nettoyage ne s'exécute jamais →
# lock orphelin dans $REPO (persiste au reboot) → health-watch ne basculerait PLUS
# JAMAIS. On le rend donc auto-expirant : au-delà de LOCK_MAX_AGE_S, on l'ignore
# et on le supprime (bascule ~40s, MAJ ~2-5 min → 15 min = forcément orphelin).
deploy_in_progress() {
    local f="$REPO/.bascule-lock"
    [ -f "$f" ] || return 1
    local age=$(( $(date +%s) - $(stat -c %Y "$f" 2>/dev/null || echo 0) ))
    if [ "$age" -gt "$LOCK_MAX_AGE_S" ]; then
        log "  ⚠ .bascule-lock orphelin (âge ${age}s > ${LOCK_MAX_AGE_S}s) — ignoré + supprimé (MAJ/bascule interrompue ?). Failover autorisé."
        rm -f "$f"
        return 1
    fi
    return 0
}

# ── Identité de ce RPi ───────────────────────────────────────────────────────
CUR_HOSTNAME=$(hostname)
# Sourcé APRÈS le bloc --selftest (la CI l'exécute hors de /opt/5hostachy).
source "$REPO/lib-role.sh"
SELF=$(role_of "$CUR_HOSTNAME")
[ -n "$SELF" ] || { log "Hostname inconnu ($CUR_HOSTNAME) — abandon."; exit 1; }

# ── Verrou anti-concurrence — robuste ────────────────────────────────────────
# Historique : un /tmp/health-watch.lock créé par un autre utilisateur (run manuel
# vs cron root) rendait `exec 9>` impossible → "Permission denied" + "flock: 9:
# Bad file descriptor" en boucle. On tente le lock partagé, puis on retombe sur un
# lock par utilisateur, et on n'avorte JAMAIS le script à cause du seul verrou.
LOCK_FILE="/tmp/health-watch.lock"
if ! exec 9>"$LOCK_FILE" 2>/dev/null; then
    LOCK_FILE="/tmp/health-watch-${SELF}-$(id -u).lock"
    exec 9>"$LOCK_FILE" 2>/dev/null || { log "Verrou inaccessible ($LOCK_FILE) — abandon."; exit 0; }
fi
chmod 666 "$LOCK_FILE" 2>/dev/null || true   # accessible root ET ptressard pour les prochains runs
flock -n 9 || { log "Autre instance en cours — abandon."; exit 0; }

# ── Nettoyage proactif d'un .bascule-lock orphelin (même site UP) ────────────
# Un lock laissé par une MAJ/bascule interrompue (reboot) bloquerait aussi
# auto-deploy.sh indéfiniment. On le purge dès qu'il dépasse LOCK_MAX_AGE_S.
if [ -f "$REPO/.bascule-lock" ]; then
    _lock_age=$(( $(date +%s) - $(stat -c %Y "$REPO/.bascule-lock" 2>/dev/null || echo 0) ))
    if [ "$_lock_age" -gt "$LOCK_MAX_AGE_S" ]; then
        log "⚠ .bascule-lock orphelin (âge ${_lock_age}s) — suppression proactive (MAJ/bascule interrompue ?)."
        rm -f "$REPO/.bascule-lock"
    fi
fi

# ── Check URL publique ────────────────────────────────────────────────────────
HTTP_CODE=$(http_code "$PUBLIC_URL")

if [ "$HTTP_CODE" = "200" ]; then
    # Site OK — supprimer le cooldown si présent (reset pour la prochaine panne)
    rm -f "$COOLDOWN_FILE"
    exit 0
fi

log "⚠ Site HS (HTTP $HTTP_CODE) — RPi: $SELF"

# ── Identité du RPi actif ─────────────────────────────────────────────────────
FLAG="$REPO/.active"
ACTIVE=$(cat "$FLAG" 2>/dev/null | tr -d '[:space:]' || echo "")

# ── Alertes e-mail : module partagé ──────────────────────────────────────────
# `send_email` + `alert_if_not_in_cooldown` vivaient ici en dur (~49 lignes) et
# ont été dupliqués à l'identique le jour où check-reliability.sh a eu besoin
# d'alerter. Factorisés dans lib-alert.sh.
#
# Le `source` est GARDÉ : ce script est sur le chemin du failover, un fichier
# absent ne doit jamais l'empêcher de basculer. Sans le module, les alertes
# deviennent des no-op journalisés — la bascule, elle, fonctionne toujours.
ALERT_REPO="$REPO"
if [ -r "$REPO/lib-alert.sh" ]; then
    # shellcheck source=/dev/null
    source "$REPO/lib-alert.sh"
else
    log "⚠ lib-alert.sh introuvable — alertes désactivées (le failover reste opérationnel)."
    alert_if_not_in_cooldown() { log "  (alerte non envoyée, lib-alert.sh absent) : $1"; }
fi

# ── Bascule OU déploiement en cours ? Éviter d'interférer ────────────────────
# .bascule-lock est posé par bascule.sh ET par MaJ-Hostachy.sh : pendant un
# déploiement, l'API est brièvement down (rebuild) → sans ce garde-fou le standby
# basculait et créait un split-brain (incident du 17/06/2026).
if deploy_in_progress; then
    log "  Bascule/déploiement en cours (.bascule-lock récent) — pas d'intervention."
    exit 0
fi

# ── Ce RPi est-il le standby ? ───────────────────────────────────────────────
# Seul le standby surveille et bascule. Si ce RPi est l'actif et qu'il peut
# encore exécuter ce script, le problème vient d'ailleurs (réseau, Cloudflare)
# et non d'un freeze — on laisse Docker restart: unless-stopped gérer ça.
if [ "$ACTIVE" = "$SELF" ]; then
    log "  Ce RPi ($SELF) est l'actif — pas d'intervention (surveillance assurée par le standby)."
    exit 0
fi

# ── Double vérification (évite les faux positifs sur coupure réseau courte) ──
log "  Standby $SELF surveille. Vérification secondaire dans 30s..."
sleep 30
# Re-tester le lock de bascule/déploiement : il a pu être posé pendant l'attente.
if deploy_in_progress; then
    log "  Bascule/déploiement détecté pendant l'attente — pas d'intervention."
    exit 0
fi
HTTP_CODE2=$(http_code "$PUBLIC_URL")
if [ "$HTTP_CODE2" = "200" ]; then
    log "  Site revenu entre les deux checks (HTTP $HTTP_CODE2) — faux positif, pas d'action."
    exit 0
fi
log "  Confirmation panne (HTTP $HTTP_CODE2) — le site public ne répond pas."

# ── Le nœud ACTIF est-il en cause, ou seulement le chemin public ? ───────────
# Deux sondes indépendantes de l'URL publique (cf. decide_failover ci-dessus) :
#   • l'API de l'actif via son Caddy en LAN — le port 8000 n'est PAS publié,
#     `http://<actif>/api/health` est le seul accès direct ; il ne touche pas
#     app.db (simple GET traité in-process par l'API) ;
#   • l'edge Cloudflare depuis CE nœud — même chaîne de dépendances que le
#     tunnel (résolution DNS + TLS), donc « pourrais-je seulement servir ? ».
ACTIVE_IP=$(ip_of "$ACTIVE")
LAN_STATE=ko; EDGE_STATE=ko
[ -n "$ACTIVE_IP" ] && [ "$(http_code "http://$ACTIVE_IP/api/health" 8)" = "200" ] && LAN_STATE=ok
[ "$(http_code "$EDGE_URL" 8)" = "200" ] && EDGE_STATE=ok
log "  Sondes : API $ACTIVE en LAN=$LAN_STATE · edge Cloudflare depuis $SELF=$EDGE_STATE"

if [ "$(decide_failover "$LAN_STATE" "$EDGE_STATE")" != "failover" ]; then
    log "  ⛔ Pas de failover : $ACTIVE sert toujours en LAN et $SELF n'atteint pas l'edge"
    log "     → panne de chemin (WAN/DNS/Cloudflare), pas de panne de nœud. Basculer"
    log "     ne rétablirait rien et ferait tourner le rôle actif sans sync de base."
    alert_if_not_in_cooldown \
        "[5Hostachy] ⚠ Site public HS — panne réseau, PAS de bascule" \
        "Le site public ne répond plus (HTTP $HTTP_CODE2), mais le RPi actif ($ACTIVE) répond
normalement sur le réseau local et $SELF n'atteint pas l'edge Cloudflare.

Diagnostic : la panne est sur le CHEMIN public (WAN, DNS ou Cloudflare), pas sur le
nœud actif. Aucun failover n'a été déclenché — il n'aurait rien rétabli.

À vérifier : box/opérateur, résolution DNS, état du tunnel cloudflared.
  systemctl status cloudflared
  journalctl -u cloudflared --since '-30 min'

Date : $(date '+%d/%m/%Y à %H:%M')"
    exit 0
fi
log "  → Failover vers $SELF."

# ── Failover : ce RPi standby prend le relais ────────────────────────────────
cd "$REPO"

# Poser le lock pour éviter qu'une bascule cron se déclenche en parallèle
touch "$REPO/.bascule-lock"
trap 'rm -f "$REPO/.bascule-lock"' EXIT

sed -i "s|^ORIGIN=.*|ORIGIN=https://5hostachy.fr|" "$REPO/.env"
sed -i "/^COOKIE_SECURE=/d" "$REPO/.env"

docker compose up -d >> /dev/null 2>&1 && log "  → Conteneurs $SELF démarrés." || log "  ⚠ Échec démarrage conteneurs."
sudo systemctl start cloudflared 2>/dev/null && log "  → Cloudflared $SELF démarré." || log "  ⚠ Échec démarrage cloudflared."
# Nouvel actif = enabled → survit à un reboot (sinon health-watch laissait l'actif
# en 'disabled' et l'ancien actif en 'enabled' → split-brain au reboot, cf 23/06/2026).
sudo systemctl enable cloudflared 2>/dev/null && log "  → Cloudflared $SELF enabled." || log "  ⚠ Échec enable cloudflared."

# Best-effort : démoter l'ancien actif s'il est (re)joignable (il est probablement
# gelé/HS — d'où le failover — mais s'il répond, on évite qu'il reste 'enabled').
# Le vrai backstop si gelé reste boot-role-guard.sh au prochain reboot de l'ancien actif.
# Le .active de l'ancien actif est corrigé DANS la même session SSH : sans ça il
# continue de se croire actif, et comme ce script ne bascule que s'il se croit
# standby, les deux nœuds s'abstiennent en pensant que l'autre surveille → failover
# neutralisé (incident du 26/07/2026 : ~50 min de site HS sans bascule, flags en
# désaccord depuis un failover partiel à 06:53).
OLD_IP="$ACTIVE_IP"
if [ -n "$OLD_IP" ]; then
    ssh -i /root/.ssh/id_ed25519_bascule -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no \
        ptressard@"$OLD_IP" "printf '%s\n' '$SELF' > /opt/5hostachy/.active; cd /opt/5hostachy && docker compose stop 2>/dev/null; sudo systemctl disable --now cloudflared 2>/dev/null" \
        >/dev/null 2>&1 && log "  → Ancien actif $ACTIVE démoté (.active → $SELF + cloudflared disabled + conteneurs stoppés)." \
        || log "  ⚠ Ancien actif $ACTIVE injoignable (normal s'il est gelé) — son .active le désigne ENCORE actif, donc failover neutralisé jusqu'à son reboot ; boot-role-guard prendra le relais."
fi

echo "$SELF" > "$FLAG"
log "  → Flag actif mis à jour : $SELF"

# Re-check après failover
sleep 20
HTTP_AFTER=$(http_code "$PUBLIC_URL")

if [ "$HTTP_AFTER" = "200" ]; then
    log "  ✅ Failover réussi — $SELF est maintenant actif (HTTP 200)."
    alert_if_not_in_cooldown \
        "[5Hostachy] ⚠ Failover automatique : $ACTIVE HS → $SELF actif" \
        "Le RPi actif ($ACTIVE) ne répondait plus.
Failover automatique effectué vers $SELF.

Le site répond à nouveau (HTTP 200).
La base de données est celle de $SELF au moment du failover (sans sync depuis $ACTIVE).

Action recommandée dès que $ACTIVE est de retour :
  Vérifier les données et relancer une bascule manuelle.

Date : $(date '+%d/%m/%Y à %H:%M')"
else
    log "  ❌ Failover échoué — site toujours HS (HTTP $HTTP_AFTER)."
    alert_if_not_in_cooldown \
        "[5Hostachy] ❌ Site HS — failover échoué ($ACTIVE et $SELF inopérants)" \
        "Le site ne répond plus (HTTP $HTTP_AFTER).
Le RPi actif ($ACTIVE) est HS et la tentative de failover vers $SELF a aussi échoué.

Intervention manuelle requise sur les deux machines.

Date : $(date '+%d/%m/%Y à %H:%M')"
fi
