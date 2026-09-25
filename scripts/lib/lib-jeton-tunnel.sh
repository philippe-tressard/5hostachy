#!/bin/bash
# =============================================================================
#  lib-jeton-tunnel.sh — Qu'est-ce qu'un jeton de tunnel Cloudflare (module à sourcer)
#
#  POURQUOI ce module existe (25/09/2026, #1318) :
#    Lors d'une rotation du jeton, l'IDENTIFIANT du tunnel (`91d1afa9-…`, affiché
#    en grand sur la page du tunnel) a été collé à la place du JETON (`eyJ…`,
#    caché dans la commande d'installation), sur les deux nœuds : site coupé,
#    deux failovers inutiles. Deux scripts reçoivent un jeton collé —
#    `changer-jeton-tunnel.sh` (rotation) et `install-cloudflared.sh`
#    (reconstruction d'un nœud) — et aucun ne regardait ce qu'on lui donnait.
#    La règle vit ici, une fois, pour les deux.
#
#  Un jeton est le base64 d'un JSON {"a":compte,"t":tunnel,"s":secret}.
#
#  Fonctions PURES : ni réseau, ni écriture, ni lecture de fichier. Elles rendent
#  toujours 0 (sauf `unite_avec_jeton`, qui refuse en 1) : sous `set -e`, un
#  `return 1` dans `X=$(…)` ferait avorter l'appelant avant son message.
#
#  Test : bash lib-jeton-tunnel.sh --selftest   (aucun effet de bord)
# =============================================================================

# ── Identifiant du tunnel porté par un jeton ─────────────────────────────────
# Rend l'identifiant `t`, ou rien si le texte n'est pas un jeton lisible.
jeton_tunnel_id() {
  local j="${1:-}" json
  [ -n "$j" ] || return 0
  j=$(printf '%s' "$j" | tr -- '-_' '+/')
  while [ $(( ${#j} % 4 )) -ne 0 ]; do j="$j="; done
  json=$(printf '%s' "$j" | base64 -d 2>/dev/null | tr -d '\0')
  printf '%s' "$json" | grep -q '"a":"' || return 0
  printf '%s' "$json" | grep -q '"s":"' || return 0
  printf '%s' "$json" | sed -n 's/.*"t":"\([^"]*\)".*/\1/p'
}

# ── Le tunnel installé : l'identifiant attendu ───────────────────────────────
# Depuis la valeur de `--token` dans l'unité : un jeton lisible donne son `t` ;
# un identifiant nu (l'erreur du 25/09) EST l'identifiant ; sinon rien à comparer.
tunnel_attendu() {
  local v="${1:-}" id
  id=$(jeton_tunnel_id "$v")
  if [ -n "$id" ]; then echo "$id"; return 0; fi
  if printf '%s' "$v" | grep -Eq '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'; then
    echo "$v"
  fi
}

# ── Verdict sur la chaîne collée ─────────────────────────────────────────────
# Args : jeton  identifiant_attendu (vide = pas de comparaison)
# Rend : "ok" ou "refuse:<raison>" — la phrase à afficher : `motif_refus`.
verdict_jeton() {
  local j="${1:-}" attendu="${2:-}" id
  [ -n "$j" ] || { echo "refuse:vide"; return 0; }
  case "$j" in eyJ*) ;; *) echo "refuse:format"; return 0 ;; esac
  id=$(jeton_tunnel_id "$j")
  [ -n "$id" ] || { echo "refuse:illisible"; return 0; }
  if [ -n "$attendu" ] && [ "$id" != "$attendu" ]; then echo "refuse:autre-tunnel"; return 0; fi
  echo "ok"
}

motif_refus() {  # verdict → phrase pour la personne qui a collé
  case "${1#refuse:}" in
    format)       echo "Ce n'est pas le jeton. Le jeton commence par eyJ et fait plus de 150 caractères ; un code de la forme 91d1afa9-… est l'IDENTIFIANT du tunnel." ;;
    illisible)    echo "Cette chaîne commence par eyJ mais n'est pas un jeton de tunnel (copie tronquée ?)." ;;
    autre-tunnel) echo "Ce jeton appartient à un AUTRE tunnel que celui installé sur ce nœud." ;;
    vide)         echo "Rien n'a été collé." ;;
    *)            echo "Jeton refusé (${1:-})." ;;
  esac
}

# ── Masquer tout jeton dans un texte (filtre stdin → stdout) ─────────────────
# Pour citer un journal de cloudflared dans une alerte ou à l'écran sans y
# recopier le secret.
masquer_jeton() { sed -E 's/eyJ[A-Za-z0-9+\/=_-]*/<jeton masqué>/g'; }

# ── L'unité systemd avec le nouveau jeton ────────────────────────────────────
# Rend le texte de l'unité avec le jeton remplacé, ou échoue (code 1) si elle ne
# porte pas exactement UN `--token` : deviner où l'écrire, c'est ce qui casse.
unite_avec_jeton() {
  local texte="$1" jeton="$2" n
  n=$(printf '%s\n' "$texte" | grep -o -- '--token [^ ]*' | wc -l)
  [ "$n" -eq 1 ] || return 1
  # Délimiteur `|` : absent du base64, qui contient `/` `+` `=`.
  printf '%s\n' "$texte" | sed "s|--token [^ ]*|--token $jeton|"
}

# ── Self-test ────────────────────────────────────────────────────────────────
# Garde `BASH_SOURCE = $0` : sourcé depuis un script lancé avec `--selftest`,
# ce bloc ne doit pas s'exécuter à sa place (cf. lib-role.sh).
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
  fail=0
  eq() { if [ "$2" = "$3" ]; then echo "PASS  $1"; else echo "FAIL  $1  attendu=[$3] obtenu=[$2]"; fail=1; fi; }
  ID=11111111-2222-3333-4444-555555555555
  BON=$(printf '{"a":"compte","t":"%s","s":"c2VjcmV0"}' "$ID" | base64 | tr -d '\n=')
  AUTRE=$(printf '{"a":"compte","t":"99999999-2222-3333-4444-555555555555","s":"eA=="}' | base64 | tr -d '\n')
  echo "== self-test lib-jeton-tunnel =="
  eq "jeton lisible → identifiant (sans remplissage =)" "$(jeton_tunnel_id "$BON")" "$ID"
  eq "jeton_tunnel_id sur un identifiant nu → rien"     "$(jeton_tunnel_id "$ID")"  ""
  eq "tunnel attendu : jeton installé"                  "$(tunnel_attendu "$BON")"  "$ID"
  eq "tunnel attendu : identifiant installé (25/09)"    "$(tunnel_attendu "$ID")"   "$ID"
  eq "tunnel attendu : valeur quelconque → rien"        "$(tunnel_attendu "abc")"   ""
  eq "verdict : bon jeton, bon tunnel"                  "$(verdict_jeton "$BON" "$ID")"     "ok"
  eq "verdict : bon jeton, rien à comparer"             "$(verdict_jeton "$BON" "")"        "ok"
  eq "verdict : l'identifiant collé (25/09)"            "$(verdict_jeton "$ID" "$ID")"      "refuse:format"
  eq "verdict : rien collé"                             "$(verdict_jeton "" "$ID")"         "refuse:vide"
  eq "verdict : eyJ tronqué"                            "$(verdict_jeton "eyJhIjoi" "$ID")" "refuse:illisible"
  eq "verdict : jeton d'un autre tunnel"                "$(verdict_jeton "$AUTRE" "$ID")"   "refuse:autre-tunnel"
  eq "masquage : le jeton disparaît" "$(printf 'x --token %s y' "$BON" | masquer_jeton)" "x --token <jeton masqué> y"
  eq "motif : l'identifiant est nommé" "$(motif_refus refuse:format | grep -c IDENTIFIANT)" "1"
  UNITE="[Service]
ExecStart=/usr/bin/cloudflared --no-autoupdate tunnel run --token $ID
Restart=on-failure"
  eq "unité : le jeton remplace l'ancienne valeur" \
     "$(unite_avec_jeton "$UNITE" "$BON" | grep ExecStart)" \
     "ExecStart=/usr/bin/cloudflared --no-autoupdate tunnel run --token $BON"
  eq "unité : le reste est intact" "$(unite_avec_jeton "$UNITE" "$BON" | grep -c Restart=on-failure)" "1"
  unite_avec_jeton "[Service]
ExecStart=/usr/bin/cloudflared tunnel run" "$BON" >/dev/null; eq "unité sans --token → refus" "$?" "1"
  unite_avec_jeton "$UNITE
ExecStartPost=/bin/true --token x" "$BON" >/dev/null; eq "unité à deux --token → refus" "$?" "1"
  [ $fail -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
  exit $fail
fi
