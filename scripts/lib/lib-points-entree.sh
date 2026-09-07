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
#  `points_entree_verdicts_locaux`, isolée plus bas et signalée comme telle.
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
  ta "deux écarts, listés"          "ECART|cron root
ECART|unité role-guard"                                 "ECART|cron root, unité role-guard"

  [ "$echecs" -eq 0 ] && echo "== TOUS OK ==" || echo "== $echecs ÉCHEC(S) =="
  return $((echecs > 0))
}
