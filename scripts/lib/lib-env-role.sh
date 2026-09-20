#!/bin/bash
# =============================================================================
#  lib-env-role.sh — Ce que le `.env` doit dire selon le RÔLE du nœud
#
#  Module SOURCÉ, jamais exécuté (hors `--selftest`) : pas de bit x, le job CI
#  « Bits d'exécution versionnés » attend 100644 sur les `lib-*.sh`.
#
#  ── POURQUOI CE MODULE (#1077, 20/09/2026) ──────────────────────────────────
#
#  Deux réglages du `.env` dépendent du rôle, et d'eux seuls :
#
#    | Réglage         | Nœud ACTIF              | Nœud STANDBY            |
#    |-----------------|-------------------------|-------------------------|
#    | `ORIGIN`        | https://5hostachy.fr    | http://<IP du nœud>     |
#    | `COOKIE_SECURE` | ABSENT (défaut = true)  | false                   |
#
#  Le standby s'atteint en HTTP clair sur son IP : un cookie `Secure` n'y
#  repartirait pas. L'actif sert le public par le tunnel, en HTTPS : le drapeau
#  y est obligatoire — et il est obtenu en RETIRANT la ligne, pour que ce soit le
#  défaut de `config.py` (`cookie_secure: bool = True`) qui s'applique, et non
#  une valeur recopiée ici qui pourrait un jour dire le contraire de lui.
#
#  🔴 Cette règle était écrite QUATRE fois, dans trois scripts :
#     `bascule.sh:383` (promotion du peer), `bascule.sh:443-446` (soi-même en
#     standby), `health-watch.sh:294` (failover) et `boot-role-guard.sh:182`
#     (promotion au démarrage). Le commentaire de ce dernier disait, en toutes
#     lettres, « identique à bascule.sh phase 5 et health-watch.sh failover » :
#     la duplication était CONNUE et documentée, jamais supprimée. Un commentaire
#     qui décrit une copie ne l'empêche pas de diverger — il note seulement
#     qu'elle existe.
#
#     Et elle avait déjà coûté : le « gap .env du 15/07 » cité par
#     `boot-role-guard.sh` est précisément le jour où une promotion HORS bascule
#     n'a pas appliqué ces `sed`, et a servi le public avec `ORIGIN` sur une IP
#     locale — site cassé.
#
#  ── LA PARTIE PURE, ET CELLE QUI ÉCRIT ──────────────────────────────────────
#
#  `env_role_transformer` ne touche à rien : elle reçoit le TEXTE du `.env` et
#  rend le texte voulu. C'est elle que `--selftest` éprouve, sans les deux RPi —
#  le motif inauguré par `boot-role-guard.sh --selftest` (15/07/2026).
#  `env_role_appliquer` est la seule à écrire, et elle tient en trois lignes.
#
#  Test : bash lib-env-role.sh --selftest   (aucun effet de bord)
# =============================================================================

#: L'origine publique servie par le nœud actif — une seule écriture.
ENV_ROLE_ORIGINE_PUBLIQUE="https://5hostachy.fr"

# ---------------------------------------------------------------------------
#  env_role_transformer <texte du .env> <actif|standby> [ip du nœud]
#
#  Rend sur la sortie standard le `.env` tel qu'il doit être pour ce rôle.
#  PURE : ni lecture, ni écriture, ni réseau. Idempotente.
# ---------------------------------------------------------------------------
env_role_transformer() {
  local texte=$1 role=$2 ip=${3:-}
  local origine

  case "$role" in
    actif)   origine="$ENV_ROLE_ORIGINE_PUBLIQUE" ;;
    standby)
      [ -n "$ip" ] || { echo "env_role_transformer: IP requise pour standby" >&2; return 2; }
      origine="http://$ip"
      ;;
    *) echo "env_role_transformer: rôle inconnu « $role »" >&2; return 2 ;;
  esac

  #  ORIGIN : remplacée si elle existe, ajoutée sinon. Le `.env` d'un nœud neuf
  #  vient de `.env.example`, qui la porte — mais un `.env` restauré à la main
  #  peut l'avoir perdue, et un site sans ORIGIN refuse les envois de formulaire.
  local sortie
  sortie=$(printf '%s' "$texte" | sed "s|^ORIGIN=.*|ORIGIN=${origine}|")
  if ! printf '%s' "$sortie" | grep -q '^ORIGIN='; then
    sortie=$(printf '%s\nORIGIN=%s' "$sortie" "$origine")
  fi

  #  COOKIE_SECURE : RETIRÉE pour l'actif (le défaut de config.py vaut `true`),
  #  posée à `false` pour le standby. On retire d'abord dans les deux cas, ce
  #  qui rend la fonction idempotente quelle que soit la valeur déjà présente.
  sortie=$(printf '%s' "$sortie" | sed '/^COOKIE_SECURE=/d')
  if [ "$role" = "standby" ]; then
    sortie=$(printf '%s\nCOOKIE_SECURE=false' "$sortie")
  fi

  printf '%s\n' "$sortie"
}

# ---------------------------------------------------------------------------
#  env_role_appliquer <chemin du .env> <actif|standby> [ip]
#
#  La seule fonction qui écrit. L'écriture passe par un fichier temporaire du
#  même répertoire puis `mv` : une coupure de courant pendant une bascule ne
#  doit pas laisser un `.env` tronqué, qui empêcherait la stack de démarrer.
# ---------------------------------------------------------------------------
env_role_appliquer() {
  local fichier=$1 role=$2 ip=${3:-} tmp
  [ -f "$fichier" ] || { echo "env_role_appliquer: $fichier introuvable" >&2; return 1; }
  tmp="${fichier}.tmp.$$"
  env_role_transformer "$(cat "$fichier")" "$role" "$ip" > "$tmp" || { rm -f "$tmp"; return 2; }
  chmod --reference="$fichier" "$tmp" 2>/dev/null || chmod 600 "$tmp"
  mv "$tmp" "$fichier"
}

# ---------------------------------------------------------------------------
#  Self-test — le contrat du module, exécuté par le job CI `test-scripts`.
# ---------------------------------------------------------------------------
_env_role_selftest() {
  local echecs=0 obtenu

  _cas() {
    local titre=$1 attendu=$2 obtenu=$3
    if [ "$attendu" = "$obtenu" ]; then
      echo "  ✓ $titre"
    else
      echo "  ✗ $titre"
      echo "      attendu : $(printf '%s' "$attendu" | tr '\n' '|')"
      echo "      obtenu  : $(printf '%s' "$obtenu" | tr '\n' '|')"
      echecs=$((echecs + 1))
    fi
  }

  echo "lib-env-role.sh --selftest"

  #  1. Actif : origine publique, et COOKIE_SECURE RETIRÉE (pas mise à true —
  #     une valeur recopiée ici pourrait un jour contredire config.py).
  obtenu=$(env_role_transformer "$(printf 'A=1\nORIGIN=http://192.168.1.222\nCOOKIE_SECURE=false\nB=2')" actif)
  _cas "actif : origine publique, COOKIE_SECURE retirée" \
       "$(printf 'A=1\nORIGIN=https://5hostachy.fr\nB=2')" "$obtenu"

  #  2. Standby : origine sur son IP, COOKIE_SECURE=false.
  obtenu=$(env_role_transformer "$(printf 'A=1\nORIGIN=https://5hostachy.fr\nB=2')" standby 192.168.1.223)
  _cas "standby : origine locale, COOKIE_SECURE=false" \
       "$(printf 'A=1\nORIGIN=http://192.168.1.223\nB=2\nCOOKIE_SECURE=false')" "$obtenu"

  #  3. Idempotence : rejouer une bascule interrompue ne doit rien empiler.
  obtenu=$(env_role_transformer "$(env_role_transformer "$(printf 'ORIGIN=x')" standby 192.168.1.223)" standby 192.168.1.223)
  _cas "standby appliqué deux fois : une seule ligne COOKIE_SECURE" \
       "$(printf 'ORIGIN=http://192.168.1.223\nCOOKIE_SECURE=false')" "$obtenu"

  #  4. Le cas ZÉRO du passage standby → actif : la ligne doit DISPARAÎTRE, pas
  #     être laissée à `false`. C'est la faute que ce module existe pour rendre
  #     impossible — elle servirait le public sans drapeau `Secure`.
  obtenu=$(env_role_transformer "$(env_role_transformer "$(printf 'ORIGIN=x')" standby 192.168.1.222)" actif)
  _cas "standby → actif : plus aucune ligne COOKIE_SECURE" \
       "$(printf 'ORIGIN=https://5hostachy.fr')" "$obtenu"

  #  5. `.env` restauré sans ORIGIN : elle est AJOUTÉE, pas silencieusement
  #     absente — un site sans ORIGIN refuse les envois de formulaire.
  obtenu=$(env_role_transformer "$(printf 'A=1')" actif)
  _cas "ORIGIN absente : ajoutée" "$(printf 'A=1\nORIGIN=https://5hostachy.fr')" "$obtenu"

  #  6. Une valeur inattendue ne passe pas pour un succès.
  if env_role_transformer "ORIGIN=x" cuisinier >/dev/null 2>&1; then
    echo "  ✗ rôle inconnu accepté"; echecs=$((echecs + 1))
  else
    echo "  ✓ rôle inconnu refusé"
  fi
  if env_role_transformer "ORIGIN=x" standby >/dev/null 2>&1; then
    echo "  ✗ standby sans IP accepté"; echecs=$((echecs + 1))
  else
    echo "  ✓ standby sans IP refusé"
  fi

  if [ "$echecs" -eq 0 ]; then
    echo "✓ lib-env-role : tous les cas passent."
    return 0
  fi
  echo "✗ lib-env-role : $echecs cas en échec."
  return 1
}

if [ "${1:-}" = "--selftest" ]; then
  _env_role_selftest
  exit $?
fi
