#!/bin/bash
# =============================================================================
#  lib-horloge.sh — C11 : la dérive d'horloge entre les deux nœuds (#1127)
#
#  Module SOURCÉ par `check-reliability.sh` (mode 100644).
#
#  ## Ce que C11 mesurait, et pourquoi c'était faux
#
#  Il comparait deux `date +%s` pris à deux MOMENTS différents : l'un au début
#  de la collecte locale, l'autre au bout de la collecte distante — séparés par
#  tout le travail local (git, df, docker…) et l'ouverture de la session SSH.
#  Le 21/09/2026 à 23:36 il a crié « 11 s » sur deux nœuds synchronisés à la
#  seconde près : il mesurait sa propre durée, et alertait quand le nœud était
#  lent. Un contrôle qui dit une chose vraie sur une autre question que celle
#  qu'on lui pose (`standards/04`).
#
#  ## Ce qu'il mesure maintenant
#
#  L'heure du pair, ENCADRÉE par deux relevés locaux dans le même aller-retour :
#
#      t0 (ici)  →  pe (là-bas)  →  t1 (ici)
#
#  Le pair a lu son horloge quelque part entre t0 et t1. La dérive est l'écart
#  entre `pe` et le milieu de l'intervalle ; l'INCERTITUDE est le
#  demi-aller-retour. On ne conclut que ce que l'intervalle permet :
#
#    | dérive + incertitude ≤ seuil | OK      — même au pire, sous le seuil  |
#    | dérive − incertitude > seuil | DERIVE  — même au mieux, au-dessus     |
#    | entre les deux               | INCONNU — l'aller-retour est trop long |
#
#  Test : bash lib-horloge.sh --selftest   (aucun effet de bord)
# =============================================================================

#  L'heure de l'autre nœud, encadrée par deux relevés locaux, en millisecondes.
#  Émet « t0 pe t1 » ; « - » à la place de pe si la mesure a échoué — le verdict
#  dira INCONNU, jamais OK. Un champ VIDE décalerait les suivants d'un cran.
#  Seule fonction à effet (SSH) : elle ne décide rien.
#  $1 = commande SSH complète, $2 = cible (utilisateur@hôte).
horloge_mesurer() {
  local ssh_cmd=$1 cible=$2 t0 pe t1
  t0=$(date +%s%3N)
  pe=$($ssh_cmd "$cible" 'date +%s%3N' 2>/dev/null | tr -dc '0-9')
  t1=$(date +%s%3N)
  echo "$t0 ${pe:--} $t1"
}

#  PURE. $1 t0, $2 pe, $3 t1 (ms), $4 seuil (s).
#  Émet « OK|DERIVE|INCONNU <dérive ms> <incertitude ms> ».
verdict_derive_horloge() {
  local t0=${1:-} pe=${2:-} t1=${3:-} seuil_s=${4:-}
  local nombre='^[0-9]+$'
  if ! [[ $t0 =~ $nombre && $pe =~ $nombre && $t1 =~ $nombre && $seuil_s =~ $nombre ]] ||
    [ "$t1" -lt "$t0" ]; then
    echo "INCONNU"
    return
  fi
  #  Arrondi de l'incertitude VERS LE HAUT : sur un aller-retour impair,
  #  l'arrondir vers le bas ferait conclure une milliseconde trop tôt.
  local incert=$(((t1 - t0 + 1) / 2))
  local derive=$((pe - (t0 + t1) / 2))
  derive=${derive#-}
  local seuil=$((seuil_s * 1000))
  if [ $((derive + incert)) -le "$seuil" ]; then
    echo "OK $derive $incert"
  elif [ $((derive - incert)) -gt "$seuil" ]; then
    echo "DERIVE $derive $incert"
  else
    echo "INCONNU $derive $incert"
  fi
}

#  Les lignes C11 de check-reliability. Dépend de ok/warn de l'appelant.
#  $1 nœud local, $2 pair, $3 commande SSH, $4 cible SSH, $5 seuil (s).
horloge_verdicts() {
  local self=$1 peer=$2 seuil=$5 mesure verdict derive incert
  mesure=$(horloge_mesurer "$3" "$4")
  #  « t0 pe t1 » se découpe volontairement en trois arguments.
  # shellcheck disable=SC2086
  read -r verdict derive incert <<<"$(verdict_derive_horloge $mesure "$seuil")"
  case "$verdict" in
    OK) ok "Dérive d'horloge entre les 2 = ${derive} ms (± ${incert} ms)" ;;
    DERIVE) warn "Dérive d'horloge ${derive} ms (± ${incert} ms) entre $self et $peer (> ${seuil} s)" ;;
    *) warn "Dérive d'horloge entre $self et $peer INCONNUE (aller-retour SSH trop long ou mesure échouée) — son silence ne prouve rien" ;;
  esac
}

_horloge_selftest() {
  local echecs=0
  _cas() {
    if [ "$2" = "$3" ]; then echo "  ✓ $1"; else
      echo "  ✗ $1 — attendu « $2 », obtenu « $3 »"
      echecs=$((echecs + 1))
    fi
  }
  echo "lib-horloge.sh --selftest"
  local T=1790027790000

  #  🔴 LE CAS DU 21/09/2026 : horloges alignées, mais le pair a répondu au bout
  #  d'un aller-retour de 11 s (collecte lente, SSH lent). L'ancienne formule
  #  comparait des relevés pris à 11 s d'écart et criait « 11 s ».
  _cas "horloges alignées, aller-retour de 11 s → pas une dérive" \
    "INCONNU 0 5500" "$(verdict_derive_horloge $T $((T + 5500)) $((T + 11000)) 5)"
  _cas "horloges alignées, aller-retour de 300 ms" \
    "OK 0 150" "$(verdict_derive_horloge $T $((T + 150)) $((T + 300)) 5)"
  _cas "pair en avance de 8 s, aller-retour court" \
    "DERIVE 8000 100" "$(verdict_derive_horloge $T $((T + 8100)) $((T + 200)) 5)"
  _cas "pair en RETARD de 8 s : la dérive est une distance" \
    "DERIVE 8000 100" "$(verdict_derive_horloge $T $((T - 7900)) $((T + 200)) 5)"
  _cas "4,9 s de dérive ± 200 ms : on ne peut pas jurer du seuil" \
    "INCONNU 4900 200" "$(verdict_derive_horloge $T $((T + 5100)) $((T + 400)) 5)"
  _cas "4 s de dérive ± 100 ms : sous le seuil même au pire" \
    "OK 4000 100" "$(verdict_derive_horloge $T $((T + 4100)) $((T + 200)) 5)"

  #  CAS ZÉRO : une mesure qui n'a pas eu lieu n'est jamais un vert.
  _cas "pair muet (SSH échoué)" "INCONNU" "$(verdict_derive_horloge $T '' $((T + 200)) 5)"
  _cas "pair muet, tel que horloge_mesurer le rend" "INCONNU" "$(verdict_derive_horloge $T - $((T + 200)) 5)"
  _cas "réponse non numérique" "INCONNU" "$(verdict_derive_horloge $T 'Permission denied' $((T + 200)) 5)"
  _cas "horloge locale recalée pendant la mesure (t1 < t0)" \
    "INCONNU" "$(verdict_derive_horloge $T $T $((T - 1000)) 5)"
  _cas "seuil absent" "INCONNU" "$(verdict_derive_horloge $T $T $T '')"

  if [ "$echecs" -eq 0 ]; then echo "✓ lib-horloge : tous les cas passent."; return 0; fi
  echo "✗ lib-horloge : $echecs cas en échec."
  return 1
}

#  Garde « exécuté, pas sourcé » — exigée de tout module de `check-reliability`
#  par `lib-modules-sources.sh --selftest` (22/09/2026).
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
  _horloge_selftest
  exit $?
fi
