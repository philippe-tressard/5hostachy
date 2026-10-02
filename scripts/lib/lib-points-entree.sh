#!/bin/bash
# =============================================================================
#  lib-points-entree.sh — Décisions pures de conformité des points d'entrée
#
#  Module SOURCÉ, jamais exécuté : pas de bit x (le job CI « Bits d'exécution
#  versionnés » attend 100644 sur les `lib-*.sh`).
#
#  POURQUOI CE MODULE. Ces trois fonctions vivaient dans
#  `scripts/poste/verifier-points-entree.sh`, qui ne tourne que sur le poste, au
#  moment d'une livraison. `check-reliability.sh` en a besoin pour surveiller le
#  même invariant EN CONTINU (#352) — et il tourne, lui, sur les nœuds.
#
#  Les recopier aurait été le geste évident et le mauvais : deux logiques de
#  normalisation de crontab qui divergent, c'est un contrôle qui dit OK là où
#  l'autre dit ECART, sans que personne sache lequel a raison. Elles vivent donc
#  ici, une fois, avec leur self-test — qui est leur contrat.
#
#  Ces fonctions sont PURES : aucun SSH, aucun sudo, aucune écriture — sauf
#  `points_entree_verdicts_locaux`, isolée plus bas et signalée comme telle, et
#  `scripts_a_mesurer` (C6), qui lit les fichiers du DÉPÔT et rien d'autre.
#
#  ── POURQUOI C22 EXISTE, ET POURQUOI IL EST EN WARN ─────────────────────────
#
#  C18 de `check-reliability.sh` compare les crontabs des deux nœuds ENTRE EUX :
#  deux crontabs identiquement périmés lui paraissent parfaits. Le point 17 du
#  pré-check comble ce trou en comparant au DÉPÔT — mais seulement au moment
#  d'une livraison, c'est-à-dire au moment où *je* risque de casser quelque
#  chose, jamais entre deux. Une modification manuelle faite un lundi n'était
#  donc constatée qu'à la livraison suivante, des jours plus tard.
#
#  Or c'est un invariant PERMANENT, pas un état de livraison — et la skill
#  `mep-precheck` pose exactement cette règle : ce qui est critique en continu ne
#  doit pas être vérifié seulement en MEP.
#
#  **WARN et non FAIL**, contrairement à la lettre de #352 qui demandait une
#  alerte e-mail. C'est un écart assumé, pour la raison que C18 et C20 — même
#  famille, même choix — donnent déjà : une dérive de point d'entrée ne coupe pas
#  la production, et l'alerte e-mail ne part que sur FAIL. À */15 avec une heure
#  de temporisation, un FAIL persistant enverrait 24 mails par jour jusqu'à
#  correction, c'est-à-dire une alerte qu'on apprend à ignorer — exactement le
#  mode d'échec de `check-stack.sh`, qui échouait 144 fois par jour dans un log
#  que personne ne lisait. Si l'on veut le mail, il faudra d'abord une
#  temporisation par contrôle, pas un FAIL de plus.
# =============================================================================

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

# ── Collecte LOCALE — IMPURE, non éprouvée par le self-test ──────────────────
#
#  Compare les points d'entrée du nœud COURANT à ce que le dépôt attend, et
#  imprime une ligne `VERDICT|libellé` par point. Utilisée par C22 de
#  `check-reliability.sh`, qui tourne sur les nœuds ; le vérificateur du poste,
#  lui, interroge les nœuds par SSH et n'en a pas besoin.
#
#  ⚠️ Cette fonction LIT le système (crontab, /etc/systemd). Le self-test plus bas
#  ne l'éprouve donc pas — il n'éprouve que les décisions qu'elle appelle. C'est
#  le même avertissement que `lib-collecte.sh` : ce qui n'est pas pur n'est pas
#  testable sans la machine, et il faut le dire plutôt que le laisser croire.
#
#  Trois lectures, trois façons d'échouer, et toutes rendent INCONNU (chaîne vide
#  → `verdict_conformite`), jamais OK ni ECART :
#   - crontab root : lisible directement quand on est root (c'est le cas sous le
#     cron root), sinon par `sudo -n` — refusé sur rpi2 (#302) ;
#   - crontab utilisateur : `crontab -u ptressard -l` exige root ;
#   - unité systemd : lisible par tous, mais absente si le nœud n'a pas été
#     provisionné.
points_entree_verdicts_locaux() {  # $1 = racine du dépôt
  local racine="$1" att ins
  local base="$racine/infra/points-entree"

  att=$(normaliser_cron < "$base/cron-root.crontab" 2>/dev/null)
  if [ "$(id -u)" -eq 0 ]; then ins=$(crontab -l 2>/dev/null | normaliser_cron)
  else ins=$(sudo -n crontab -l 2>/dev/null | normaliser_cron); fi
  echo "$(verdict_conformite "$att" "$ins")|cron root"

  att=$(normaliser_cron < "$base/cron-ptressard.crontab" 2>/dev/null)
  if [ "$(id -u)" -eq 0 ]; then ins=$(crontab -u ptressard -l 2>/dev/null | normaliser_cron)
  else ins=$(crontab -l 2>/dev/null | normaliser_cron); fi
  echo "$(verdict_conformite "$att" "$ins")|cron ptressard"

  att=$(normaliser_unit < "$base/hostachy-role-guard.service" 2>/dev/null)
  ins=$(normaliser_unit < /etc/systemd/system/hostachy-role-guard.service 2>/dev/null)
  echo "$(verdict_conformite "$att" "$ins")|unité role-guard"
}

#  L'état d'un service (`systemctl is-enabled`) en verdict — PURE.
#  Une sortie VIDE veut dire qu'on n'a rien lu (SSH refusé, nœud injoignable) :
#  c'est INCONNU. Seul un état LU et différent d'`enabled` est un écart (#1302 —
#  le poste concluait à un ÉCART quand il n'avait rien mesuré).
verdict_etat_service() {  # $1 = sortie de `systemctl is-enabled`
  case "$1" in
    "")      echo INCONNU ;;
    enabled) echo OK ;;
    *)       echo ECART ;;
  esac
}

#  Agrège les lignes `VERDICT|libellé` en UN verdict : `ECART|liste`,
#  `INCONNU|liste` ou `OK|`. PURE (lit stdin), donc éprouvée par le self-test.
#
#  L'ordre de priorité est une décision, pas un détail : un écart AVÉRÉ prime sur
#  un point illisible. L'inverse ferait taire une dérive réelle dès qu'un autre
#  point d'entrée n'est pas lisible — c'est-à-dire en permanence sur rpi2, où
#  `sudo -n` est refusé (#302).
agreger_points_entree() {
  local v nom ecart="" inconnu=""
  while IFS='|' read -r v nom; do
    case "$v" in ECART) ecart+="$nom, " ;; INCONNU) inconnu+="$nom, " ;; esac
  done
  if   [ -n "$ecart" ];   then echo "ECART|${ecart%, }"
  elif [ -n "$inconnu" ]; then echo "INCONNU|${inconnu%, }"
  else echo "OK|"; fi
}

# ── C6 (#1546) — les scripts que lancent les points d'entrée sont exécutables ─
#
#  🔴 POURQUOI ICI. C6 mesurait une liste RECOPIÉE de sept relais à la racine du
#  dépôt ; six ont été retirés le 16/08/2026, la liste n'a pas suivi, et
#  `[ -f ] && [ ! -x ]` faux sur six noms rendait « ok » : faux vert sur les deux
#  nœuds jusqu'à l'audit du 02/10/2026. La liste se DÉRIVE donc désormais des
#  fichiers de ce répertoire-ci (`infra/points-entree/`), qui disent ce que les
#  nœuds lancent — et un chemin attendu qui manque se dit, il ne se tait plus.

#  Les chemins de scripts 5Hostachy cités par un texte (crontab, unité systemd),
#  un par ligne. Lignes commentées et vides écartées. PURE (stdin → stdout).
#  C'est la SEULE écriture pure du motif : `crontab_scripts` (C18) s'en sert, et
#  `verdicts_selftest` la compare au jumeau inline de `lib-collecte.sh`.
scripts_cites() {
  grep -vE '^\s*(#|$)' | grep -oE '/opt/5hostachy/[A-Za-z0-9_./-]+\.sh'
}

#  Un relais (`boot-role-guard.sh` à la racine, que vise l'unité systemd) exécute
#  sa cible par `exec` : la cible doit donc AUSSI porter son bit x, sinon le
#  garde-fou anti-split-brain échoue au démarrage — le seul moment où il sert.
#  Rend le chemin de la cible relatif au relais, ou rien. PURE (stdin → stdout).
cible_relais() {
  grep -oE '^exec "\$\(dirname "\$0"\)/[A-Za-z0-9_./-]+\.sh"' | head -1 \
    | sed -E 's#^.*\)/##; s#"$##'
}

#  La liste à mesurer, dérivée du dépôt : chemins absolus séparés par des espaces.
#  ⚠️ LIT des fichiers du dépôt (jamais le système) : ni SSH, ni sudo, ni écriture.
#  Un répertoire introuvable rend une liste VIDE — jamais une liste par défaut —,
#  que `verdict_bits_exec` traduit en INCONNU. Les chemins ne contiennent que
#  `[A-Za-z0-9_./-]` (les deux motifs ci-dessus) : c'est ce qui permet de les
#  injecter tels quels dans le code exécuté sur les nœuds.
scripts_a_mesurer() {  # $1 = racine du dépôt
  local racine="$1" base="$1/infra/points-entree" p cible
  for p in $(cat "$base"/*.crontab "$base"/*.service 2>/dev/null | scripts_cites | sort -u); do
    echo "$p"
    cible=$(cible_relais < "$racine/${p#/opt/5hostachy/}" 2>/dev/null)
    [ -n "$cible" ] && echo "$(dirname "$p")/$cible"
  done | sort -u | tr '\n' ' ' | sed 's/ $//'
}

#  Le code de mesure exécuté sur CHAQUE nœud (local et pair), sous forme de
#  chaîne : `lib-collecte.sh` l'ajoute à COLLECT. Il rapporte des FAITS BRUTS,
#  `chemin:x|nx|absent`, derrière un marqueur `ok:` qui distingue « mesuré » de
#  « pas pu mesurer » ; c'est `verdict_bits_exec` qui conclut. PURE (rend du texte).
fragment_bits_exec() {  # $1 = chemins séparés par des espaces
  printf '\n%s\n%s\n' \
    "BITS=ok:; for _bx in $1; do if [ ! -e \"\$_bx\" ]; then _be=absent; elif [ -x \"\$_bx\" ]; then _be=x; else _be=nx; fi; BITS=\"\$BITS\$_bx:\$_be,\"; done" \
    'echo "exec_bits=$BITS"'
}

#  La décision de C6. PURE. Rend `OK|n`, `FAIL|détail` ou `INCONNU|raison`.
#  Un défaut AVÉRÉ (bit perdu) prime sur tout le reste, comme dans
#  `agreger_points_entree`. Trois façons de ne RIEN savoir, toutes INCONNU :
#  relevé absent (collecte muette, pair injoignable), liste vide (zéro fichier
#  mesuré n'est pas zéro fichier fautif), et aucun chemin attendu présent — la
#  racine elle-même manque, c'est le cas exact où l'ancienne boucle disait « ok ».
verdict_bits_exec() {  # $1 = relevé « ok:chemin:état,… »
  local releve="$1" e chemin n=0 presents=0 nx="" absent="" illisible=""
  local -a entrees=()
  case "$releve" in
    ok:*) releve=${releve#ok:} ;;
    *)    echo "INCONNU|relevé absent"; return ;;
  esac
  IFS=, read -r -a entrees <<< "$releve"
  for e in ${entrees[@]+"${entrees[@]}"}; do
    [ -n "$e" ] || continue
    n=$((n+1)); chemin=${e%:*}; chemin=${chemin#/opt/5hostachy/}
    case "${e##*:}" in
      x)      presents=$((presents+1)) ;;
      nx)     presents=$((presents+1)); nx+=" $chemin" ;;
      absent) absent+=" $chemin" ;;
      *)      illisible+=" $chemin" ;;
    esac
  done
  if   [ "$n" -eq 0 ]; then echo "INCONNU|aucun script mesuré"
  elif [ -n "$nx" ];   then echo "FAIL|sans bit x :${nx}${absent:+ ; absent :$absent}"
  elif [ "$presents" -eq 0 ] && [ -z "$illisible" ]; then echo "INCONNU|aucun script attendu présent"
  elif [ -n "$absent" ];    then echo "FAIL|absent :$absent"
  elif [ -n "$illisible" ]; then echo "INCONNU|état illisible :$illisible"
  else echo "OK|$n"; fi
}

#  Les constats de C6, un par nœud — appelée par check-reliability, dont elle
#  emploie `ok`/`warn`/`fail`, `$SELF`, `$PEER`, `$PEER_OK` et les champs
#  `S_exec_bits`/`P_exec_bits` (comme `healthwatch_verdicts`, #1586).
bits_exec_verdicts() {
  local _n _v
  for _n in "$SELF:${S_exec_bits:-}" "$PEER:${P_exec_bits:-}"; do
    [ "${_n%%:*}" = "$PEER" ] && [ "$PEER_OK" -ne 0 ] && continue
    _v=$(verdict_bits_exec "${_n#*:}")
    case "${_v%%|*}" in
      OK)   ok "Bits exec OK sur ${_n%%:*} (${_v#*|} scripts lancés par crons et unité)" ;;
      FAIL) fail "Scripts lancés NON exécutables sur ${_n%%:*} — ${_v#*|}" ;;
      *)    warn "Bits exec INCONNUS sur ${_n%%:*} — ${_v#*|} — ni vert ni rouge" ;;
    esac
  done
}

# ── Self-test — le contrat des trois fonctions ───────────────────────────────
points_entree_selftest() {
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
  echo "== self-test points d'entrée =="
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

  #  Ajouté avec C22 (#352) : une unité systemd dont seul l'ExecStart change.
  #  `normaliser_unit` ne filtre par aucun chemin — si ce cas passait OK, le
  #  contrôle continu ne verrait pas un service repointé vers un autre binaire.
  a=$(printf '%s\n' '[Service]' 'ExecStart=/opt/5hostachy/scripts/exploitation/boot-role-guard.sh' | normaliser_unit)
  b=$(printf '%s\n' '[Service]' 'ExecStart=/opt/5hostachy/boot-role-guard.sh'                      | normaliser_unit)
  t "unité repointée vers un autre chemin"   "$a" "$b" ECART

  #  L'agrégateur (C22) — sa priorité est une décision, donc elle se teste.
  ta() {  # $1 = libellé, $2 = lignes, $3 = attendu
    local obtenu; obtenu=$(printf '%s\n' "$2" | agreger_points_entree)
    if [ "$obtenu" = "$3" ]; then echo "PASS  $1"
    else echo "ÉCHEC $1 — attendu [$3], obtenu [$obtenu]"; echecs=$((echecs+1)); fi
  }
  ta "tout conforme"                "OK|cron root
OK|unité role-guard"                                    "OK|"
  ta "un écart seul"                "OK|cron root
ECART|unité role-guard"                                 "ECART|unité role-guard"
  ta "un illisible seul"            "OK|cron root
INCONNU|cron ptressard"                                 "INCONNU|cron ptressard"
  #  Le cas qui compte : sur rpi2 `sudo -n` est refusé en PERMANENCE. Si INCONNU
  #  primait, une dérive réelle y serait masquée tous les jours.
  ta "écart ET illisible → l'écart prime" "INCONNU|cron root
ECART|unité role-guard"                                 "ECART|unité role-guard"
  #  #1302 : l'ordre des nœuds ne change rien — un écart LU puis un INCONNU.
  ta "écart PUIS illisible → l'écart prime" "ECART|rpi1 cron root
INCONNU|rpi2 cron root"                                 "ECART|rpi1 cron root"
  ta "deux écarts, listés"          "ECART|cron root
ECART|unité role-guard"                                 "ECART|cron root, unité role-guard"

  #  L'état du service (#1302) : rien lu n'est pas un écart.
  te() {  # $1 = libellé, $2 = sortie de systemctl, $3 = attendu
    local obtenu; obtenu=$(verdict_etat_service "$2")
    if [ "$obtenu" = "$3" ]; then echo "PASS  $1"
    else echo "ÉCHEC $1 — attendu $3, obtenu $obtenu"; echecs=$((echecs+1)); fi
  }
  te "service activé"                 "enabled"  OK
  te "service désactivé"              "disabled" ECART
  te "état illisible (SSH refusé)"    ""         INCONNU

  bits_exec_selftest || echecs=$((echecs+1))

  [ "$echecs" -eq 0 ] && echo "== TOUS OK ==" || echo "== $echecs ÉCHEC(S) =="
  return $((echecs > 0))
}

# ── C6 (#1546) — les scripts que lancent les points d'entrée sont exécutables ─
#
#  Le contrat de `scripts_cites`, `cible_relais`, `scripts_a_mesurer`,
#  `verdict_bits_exec` et `fragment_bits_exec`. Appelé par
#  `points_entree_selftest`, donc par les DEUX self-tests qui le lancent :
#  `check-reliability.sh --selftest` et `verifier-points-entree.sh --selftest`.
#
#  🔴 Le cas qui l'a fait naître : C6 mesurait sept relais de la racine du dépôt,
#  dont six avaient été retirés le 16/08/2026. `[ -f ]` faux sur six noms, la
#  boucle ne mesurait rien et le relevé restait « ok » — vert sur les deux nœuds
#  pendant que les crons visaient `scripts/exploitation/`, que personne ne
#  regardait (audit du 02/10/2026).
bits_exec_selftest() {
  local echecs=0 obtenu tmp
  teq() {  # $1 = libellé, $2 = attendu, $3 = obtenu
    if [ "$3" = "$2" ]; then echo "PASS  $1"
    else echo "ÉCHEC $1 — attendu [$2], obtenu [$3]"; echecs=$((echecs+1)); fi
  }
  echo "== self-test C6 : bits d'exécution des scripts lancés =="

  echo "-- scripts_cites : les chemins que citent crontabs et unité --"
  obtenu=$(printf '%s\n' '# 0 2 * * * /opt/5hostachy/scripts/exploitation/vieux.sh' '' \
    '0 2 * * * /opt/5hostachy/scripts/exploitation/bascule.sh >> /var/log/hostachy-bascule.log 2>&1' \
    'ExecStart=/opt/5hostachy/boot-role-guard.sh' | scripts_cites | paste -sd' ' -)
  teq "ligne commentée écartée, cron et ExecStart retenus" \
    "/opt/5hostachy/scripts/exploitation/bascule.sh /opt/5hostachy/boot-role-guard.sh" "$obtenu"
  teq "texte sans script 5Hostachy → rien" "" "$(printf '%s\n' '0 5 * * * /usr/bin/autre' | scripts_cites)"

  echo "-- cible_relais : un relais désigne le script qu'il exécute --"
  teq "relais de la racine" "scripts/exploitation/boot-role-guard.sh" \
    "$(printf '%s\n' '#!/bin/bash' 'exec "$(dirname "$0")/scripts/exploitation/boot-role-guard.sh" "$@"' | cible_relais)"
  teq "script ordinaire : aucune cible" "" "$(printf '%s\n' '#!/bin/bash' 'echo bonjour' | cible_relais)"

  echo "-- scripts_a_mesurer : la liste DÉRIVÉE du dépôt réel --"
  local racine liste s
  racine="$(dirname "${BASH_SOURCE[0]}")/../.."
  liste=$(scripts_a_mesurer "$racine")
  for s in scripts/exploitation/bascule.sh scripts/exploitation/health-watch.sh \
           scripts/exploitation/maintenance.sh scripts/exploitation/check-reliability.sh \
           scripts/exploitation/auto-deploy.sh boot-role-guard.sh \
           scripts/exploitation/boot-role-guard.sh; do
    case " $liste " in
      *" /opt/5hostachy/$s "*) echo "PASS  mesuré : $s" ;;
      *) echo "ÉCHEC $s absent de la liste dérivée [$liste]"; echecs=$((echecs+1)) ;;
    esac
  done
  #  Chaque chemin mesuré existe DANS LE DÉPÔT : un point d'entrée qui vise un
  #  script disparu échoue ici, en CI, avant d'échouer sur les nœuds.
  for s in $liste; do
    [ -f "$racine/${s#/opt/5hostachy/}" ] \
      || { echo "ÉCHEC point d'entrée vers un script absent du dépôt : $s"; echecs=$((echecs+1)); }
  done
  #  Cas zéro : pas de répertoire `infra/points-entree` → liste VIDE, jamais
  #  une liste par défaut recopiée ici.
  teq "dépôt introuvable → liste vide" "" "$(scripts_a_mesurer /chemin/inexistant)"

  echo "-- verdict_bits_exec : la décision --"
  local P=/opt/5hostachy/scripts/exploitation
  teq "tous exécutables"            "OK|2" \
    "$(verdict_bits_exec "ok:$P/bascule.sh:x,$P/health-watch.sh:x,")"
  teq "un bit x perdu"              "FAIL|sans bit x : scripts/exploitation/bascule.sh" \
    "$(verdict_bits_exec "ok:$P/bascule.sh:nx,$P/health-watch.sh:x,")"
  teq "un script attendu absent"    "FAIL|absent : scripts/exploitation/maintenance.sh" \
    "$(verdict_bits_exec "ok:$P/bascule.sh:x,$P/maintenance.sh:absent,")"
  #  🔴 LE CAS DU TICKET : aucun des chemins listés n'existe. L'ancienne boucle
  #  rendait « ok » ; c'est la racine elle-même qui manque — on ne sait rien.
  teq "aucun chemin listé n'existe" "INCONNU|aucun script attendu présent" \
    "$(verdict_bits_exec "ok:$P/bascule.sh:absent,$P/health-watch.sh:absent,")"
  teq "relevé vide (collecte muette)" "INCONNU|relevé absent" "$(verdict_bits_exec "")"
  teq "pair injoignable (unknown)"  "INCONNU|relevé absent" "$(verdict_bits_exec "unknown")"
  #  Zéro fichier mesuré n'est PAS « zéro fichier fautif ».
  teq "liste vide : rien mesuré"    "INCONNU|aucun script mesuré" "$(verdict_bits_exec "ok:")"
  teq "état illisible"              "INCONNU|état illisible : scripts/exploitation/bascule.sh" \
    "$(verdict_bits_exec "ok:$P/bascule.sh:??,")"
  #  Un défaut AVÉRÉ prime sur un état illisible — même règle que C22.
  teq "bit perdu ET état illisible" "FAIL|sans bit x : scripts/exploitation/bascule.sh" \
    "$(verdict_bits_exec "ok:$P/bascule.sh:nx,$P/health-watch.sh:??,")"

  echo "-- fragment_bits_exec : le code EXÉCUTÉ sur les nœuds, exécuté ici --"
  local releve
  tmp=$(mktemp -d)
  printf '#!/bin/sh\n' > "$tmp/x.sh";  chmod +x "$tmp/x.sh"
  printf 'texte\n'     > "$tmp/nx.sh"; chmod -x "$tmp/nx.sh"
  releve=$(bash -c "$(fragment_bits_exec "$tmp/x.sh")" 2>/dev/null)
  teq "relevé d'un script exécutable" "exec_bits=ok:$tmp/x.sh:x," "$releve"
  releve=$(bash -c "$(fragment_bits_exec "$tmp/x.sh $tmp/nx.sh $tmp/absent.sh")" 2>/dev/null)
  teq "x, sans x et absent, relevés tels quels" \
    "exec_bits=ok:$tmp/x.sh:x,$tmp/nx.sh:nx,$tmp/absent.sh:absent," "$releve"
  case "$(verdict_bits_exec "${releve#exec_bits=}")" in
    FAIL\|*) echo "PASS  …et rendus FAIL de bout en bout" ;;
    *) echo "ÉCHEC un bit perdu doit finir en FAIL"; echecs=$((echecs+1)) ;;
  esac
  releve=$(bash -c "$(fragment_bits_exec "")" 2>/dev/null)
  teq "liste vide : marqueur seul, donc INCONNU en aval" "exec_bits=ok:" "$releve"
  rm -rf "$tmp"

  [ "$echecs" -eq 0 ] && echo "== C6 : TOUS OK ==" || echo "== C6 : $echecs ÉCHEC(S) =="
  return $((echecs > 0))
}
