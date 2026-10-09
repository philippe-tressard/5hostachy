#!/bin/bash
# =============================================================================
#  lib-env-base.sh — Sur quelle base l'application écrit : `DATABASE_URL` dans
#  le `.env` des DEUX nœuds (module à sourcer, DI-7c, #1782)
#
#  Un AJUSTEMENT du `.env`, jamais sa régénération : une seule ligne change, et
#  l'ancienne valeur peut y rester en commentaire, datée (`# RETOUR_SQLITE=`).
#  Deux scripts s'en servent dans les deux sens — `basculer-donnees.sh` (SQLite →
#  PostgreSQL) et `retour-sqlite.sh` (l'inverse) — : la réécriture s'écrit ICI.
#
#  🔴 L'URL d'une base serveur porte son mot de passe : elle ne passe jamais par
#  une ligne de commande (lisible par `ps`). `awk` la lit dans l'environnement,
#  le `.env` du pair voyage par l'entrée standard de SSH, et y est réécrit en 600.
#
#  Test : bash lib-env-base.sh --selftest   (aucun effet de bord)
# =============================================================================

# ── PURE : le texte d'un `.env`, sa ligne DATABASE_URL réécrite ───────────────
#  $1 texte · $2 nouvelle URL · $3 ligne de retour (commentaire, vide sinon)
#  Une seule ligne DATABASE_URL ; la ligne de retour la précède, une fois ; toute
#  ancienne ligne de retour part.
reecrire_database_url() {
    printf '%s\n' "$1" | URL_NOUVELLE="$2" LIGNE_RETOUR="$3" awk '
        BEGIN { url = ENVIRON["URL_NOUVELLE"]; retour = ENVIRON["LIGNE_RETOUR"] }
        /^# RETOUR_SQLITE=/ { next }
        /^DATABASE_URL=/ { if (!fait) { if (retour != "") print retour; print "DATABASE_URL=" url; fait = 1 }; next }
        { print }
        END { if (!fait) { if (retour != "") print retour; print "DATABASE_URL=" url } }'
}

#  Le `.env` de ce dépôt ($REPO) — ses droits restent les siens (réécrit en place).
ecrire_database_url_local() {
    local t
    t=$(reecrire_database_url "$(cat "$REPO/.env")" "$1" "$2") && printf '%s\n' "$t" > "$REPO/.env"
}

#  Le `.env` du pair ($SSH_CMD, $PEER_IP) — lu et réécrit par l'entrée standard.
ecrire_database_url_pair() {
    local t
    t=$($SSH_CMD ptressard@"$PEER_IP" "cat /opt/5hostachy/.env") || return 1
    printf '%s\n' "$(reecrire_database_url "$t" "$1" "$2")" \
        | $SSH_CMD ptressard@"$PEER_IP" "umask 077 && cat > /opt/5hostachy/.env.tmp && chmod 600 /opt/5hostachy/.env.tmp && mv /opt/5hostachy/.env.tmp /opt/5hostachy/.env"
}

if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    st=0
    t() { [ "$3" = "$2" ] && echo "PASS  $1 → $3" || { echo "FAIL  $1  attendu=$2 obtenu=$3"; st=1; }; }
    compte() { printf '%s\n' "$1" | grep -cE "$2"; }
    env_av=$'A=1\nDATABASE_URL=sqlite:////app/data/app.db\nB=2'
    apres=$(reecrire_database_url "$env_av" "postgresql+psycopg://u:p@postgres:5432/b" "# RETOUR_SQLITE=sqlite:////app/data/app.db (bascule du 2026-10-09)")
    t "une seule ligne DATABASE_URL"        1 "$(compte "$apres" '^DATABASE_URL=')"
    t "elle désigne PostgreSQL"             1 "$(compte "$apres" '^DATABASE_URL=postgresql\+psycopg://')"
    t "la ligne de retour est posée"        1 "$(compte "$apres" '^# RETOUR_SQLITE=sqlite:')"
    t "les autres clés restent"             2 "$(compte "$apres" '^(A=1|B=2)$')"
    retour=$(reecrire_database_url "$apres" "sqlite:////app/data/app.db" "")
    t "retour : la ligne de retour part"    0 "$(compte "$retour" '^# RETOUR_SQLITE=')"
    t "retour : SQLite de nouveau"          1 "$(compte "$retour" '^DATABASE_URL=sqlite:')"
    t "un .env sans DATABASE_URL la reçoit" 1 "$(compte "$(reecrire_database_url 'A=1' 'sqlite://x' '')" '^DATABASE_URL=')"
    t "un mot de passe à caractères spéciaux passe intact" 1 \
      "$(compte "$(reecrire_database_url "$env_av" 'postgresql://u:a&b/c\d@h/b' '')" '^DATABASE_URL=postgresql://u:a&b/c\\d@h/b$')"
    [ "$st" -eq 0 ] && echo "lib-env-base : tous les cas passent."
    exit "$st"
fi
