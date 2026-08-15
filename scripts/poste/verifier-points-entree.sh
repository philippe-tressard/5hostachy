#!/usr/bin/env bash
# =============================================================================
#  Conformité des points d'entrée d'un nœud à ce que le dépôt attend.
#
#  POURQUOI. Les tâches cron et l'unité systemd qui lancent l'exploitation
#  n'étaient écrites nulle part : il fallait ouvrir un terminal sur chaque nœud
#  pour savoir ce qui tourne. `check-reliability.sh` C18 compare bien les deux
#  nœuds, mais ENTRE EUX — deux crontabs identiquement périmés lui paraissent
#  parfaits. Ce contrôle-ci compare au **dépôt**, ce qui attrape aussi la dérive
#  commune.
#
#  CE QU'IL NE FAIT PAS : écrire quoi que ce soit sur un nœud. Poser un crontab
#  reste un geste explicite, un nœud à la fois.
#
#  Usage : bash scripts/poste/verifier-points-entree.sh [ptressard@IP …]
#          bash scripts/poste/verifier-points-entree.sh --selftest
# =============================================================================
set -uo pipefail

RACINE_DEPOT="$(cd "$(dirname "$0")/../.." && pwd)"
ATTENDU="$RACINE_DEPOT/infra/points-entree"
NOEUDS_DEFAUT="ptressard@192.168.1.222 ptressard@192.168.1.223"

# ── Fonctions de décision PURES (aucun SSH, aucune écriture) ─────────────────

#  Ne garder d'un crontab que ce qui engage 5Hostachy.
#
#  Deux règles, et chacune vient d'un faux positif constaté le 15/08/2026 :
#   - retirer commentaires, lignes vides et espaces surnuméraires. Comparer des
#     empreintes de `crontab -l` brut fait diverger deux nœuds identiques : la
#     sortie porte un en-tête que l'on ne contrôle pas.
#   - ne garder que les lignes citant /opt/5hostachy. rpi2 héberge aussi
#     List-dons, dont la tâche cron est parfaitement légitime. Sans ce filtre, le
#     contrôle crierait tous les jours — et une alerte quotidienne ignorée est un
#     contrôle mort.
normaliser_cron() {
  sed -e 's/#.*$//' -e 's/[[:space:]]\{1,\}/ /g' -e 's/^ //' -e 's/ $//' \
    | grep -F '/opt/5hostachy/' \
    | sort
}

#  Une unité systemd : on retire commentaires et lignes vides, on garde le reste.
#  Pas de filtre par chemin ici — les sections [Unit]/[Service] comptent autant
#  que l'ExecStart.
normaliser_unit() {
  sed -e 's/^[[:space:]]*#.*$//' -e 's/[[:space:]]*$//' \
    | grep -v '^$' \
    | sort
}

#  Verdict de conformité. $1 = attendu (normalisé), $2 = installé (normalisé).
#
#  Un installé VIDE ne vaut pas « rien n'est configuré » : c'est très
#  probablement une lecture impossible (sudo refusé sur rpi2, hôte injoignable).
#  Il rend INCONNU, jamais ECART — un contrôle qui confond « je n'ai pas pu lire »
#  et « c'est faux » envoie corriger ce qui n'est pas cassé.
verdict_conformite() {
  local attendu="$1" installe="$2"
  if [ -z "$attendu" ]; then echo INCONNU; return; fi
  if [ -z "$installe" ]; then echo INCONNU; return; fi
  if [ "$attendu" = "$installe" ]; then echo OK; else echo ECART; fi
}

# ── Autotest ─────────────────────────────────────────────────────────────────

selftest() {
  local echecs=0
  t() {  # $1 = libellé, $2 = attendu, $3 = installé, $4 = verdict voulu
    local obtenu
    obtenu=$(verdict_conformite "$2" "$3")
    if [ "$obtenu" = "$4" ]; then
      echo "PASS  $1"
    else
      echo "ÉCHEC $1 — attendu $4, obtenu $obtenu"; echecs=$((echecs+1))
    fi
  }
  t "identiques"                       "a
b"  "a
b"  OK
  t "ligne manquante côté nœud"        "a
b"  "a"       ECART
  t "ligne en trop côté nœud"          "a"  "a
b"       ECART
  t "installé illisible (sudo refusé)" "a
b"  ""        INCONNU
  t "attendu vide (fichier absent)"    ""   "a"       INCONNU

  # Les normaliseurs — c'est là que vivent les faux positifs du 15/08/2026.
  local n
  n=$(printf '%s\n' '0 2 * * * /opt/5hostachy/bascule.sh' '# un commentaire' '' \
      '15 4 * * * /home/ptressard/list-dons/deploy/backup-listdons.sh' | normaliser_cron)
  if [ "$n" = "0 2 * * * /opt/5hostachy/bascule.sh" ]; then
    echo "PASS  normalisation : commentaire, ligne vide et tâche d'un autre projet écartés"
  else
    echo "ÉCHEC normalisation — obtenu : [$n]"; echecs=$((echecs+1))
  fi

  local a b
  a=$(printf '%s\n' '0  2 * * *   /opt/5hostachy/bascule.sh' | normaliser_cron)
  b=$(printf '%s\n' '0 2 * * * /opt/5hostachy/bascule.sh'    | normaliser_cron)
  t "espaces surnuméraires sans effet" "$a" "$b" OK

  a=$(printf '%s\n' 'x /opt/5hostachy/a.sh' 'y /opt/5hostachy/b.sh' | normaliser_cron)
  b=$(printf '%s\n' 'y /opt/5hostachy/b.sh' 'x /opt/5hostachy/a.sh' | normaliser_cron)
  t "ordre des lignes sans effet"      "$a" "$b" OK

  #  Le cas qui compte vraiment : un script déplacé sans mise à jour du crontab.
  a=$(printf '%s\n' '0 2 * * * /opt/5hostachy/bascule.sh'          | normaliser_cron)
  b=$(printf '%s\n' '0 2 * * * /opt/5hostachy/scripts/bascule.sh'  | normaliser_cron)
  t "script déplacé, crontab non mis à jour" "$a" "$b" ECART

  [ "$echecs" -eq 0 ] && echo "== TOUS OK ==" || echo "== $echecs ÉCHEC(S) =="
  return $((echecs > 0))
}

if [ "${1:-}" = "--selftest" ]; then selftest; exit $?; fi

# ── Exécution ────────────────────────────────────────────────────────────────

sur() { timeout 25 ssh -o BatchMode=yes -o ConnectTimeout=8 "$1" "$2" 2>/dev/null; }

global=0
for noeud in ${*:-$NOEUDS_DEFAUT}; do
  echo "═══ $noeud ═══"

  #  `sudo -n` est refusé sur rpi2 (#302) : la sortie sera vide, et le verdict
  #  INCONNU le dira au lieu de prétendre à un écart.
  for couple in "cron-root.crontab:sudo -n crontab -l" \
                "cron-ptressard.crontab:crontab -l"; do
    fichier="${couple%%:*}"; commande="${couple#*:}"
    att=$(normaliser_cron < "$ATTENDU/$fichier")
    ins=$(sur "$noeud" "$commande" | normaliser_cron)
    v=$(verdict_conformite "$att" "$ins")
    printf "  %-26s %s\n" "$fichier" "$v"
    [ "$v" = "ECART" ] && { diff <(printf '%s\n' "$att") <(printf '%s\n' "$ins") | sed 's/^/      /'; global=1; }
    [ "$v" = "INCONNU" ] && global=2
  done

  att=$(normaliser_unit < "$ATTENDU/hostachy-role-guard.service")
  ins=$(sur "$noeud" 'cat /etc/systemd/system/hostachy-role-guard.service' | normaliser_unit)
  v=$(verdict_conformite "$att" "$ins")
  printf "  %-26s %s\n" "hostachy-role-guard.service" "$v"
  [ "$v" = "ECART" ] && { diff <(printf '%s\n' "$att") <(printf '%s\n' "$ins") | sed 's/^/      /'; global=1; }
  [ "$v" = "INCONNU" ] && global=2

  #  Le fichier peut être conforme et le service désactivé : la conformité du
  #  texte ne dit rien de l'état. Ni l'un ni l'autre ne prouve qu'il FONCTIONNE —
  #  cela ne s'observe qu'au démarrage (redémarrer le standby, qui ne sert rien).
  etat=$(sur "$noeud" 'systemctl is-enabled hostachy-role-guard.service')
  printf "  %-26s %s\n" "  → service activé" "${etat:-INCONNU}"
  [ "$etat" = "enabled" ] || global=1
done

case "$global" in
  0) echo; echo "✓ Points d'entrée conformes au dépôt." ;;
  2) echo; echo "? Au moins un point n'a pas pu être lu — INCONNU, pas OK." ;;
  *) echo; echo "✗ Écart entre le dépôt et un nœud : corriger le nœud, ou le dépôt s'il a raison." ;;
esac
exit "$global"
