#!/bin/bash
# =============================================================================
#  lib-sudoers.sh — Composition et vérification de la règle sudo des nœuds
#
#  Module SOURCÉ, jamais exécuté : pas de bit x (le job CI « Bits d'exécution
#  versionnés » attend 100644 sur les `lib-*.sh`).
#
#  POURQUOI CE MODULE. Les règles `sudo` des deux nœuds ont été posées à la main,
#  nœud par nœud — donc elles ont divergé, et personne ne pouvait le voir : chaque
#  nœud a l'air normal vu de lui-même (#302). Cette divergence a un coût mesuré :
#  la copie hors site échouait UNE NUIT SUR DEUX (09/08/2026), la permission dont
#  elle dépendait n'existant que sur un nœud, et le rôle alternant chaque nuit.
#
#  La règle vit désormais ICI, versionnée, et `durcir-sudoers.sh` l'installe à
#  l'identique partout. C'est la seule façon de rendre vraie la phrase « les deux
#  nœuds sont configurés pareil » — la même leçon que C18 pour les crontabs.
#
#  ⚠️ CE QUE CE MODULE NE FAIT PAS, et qu'il ne faut pas croire qu'il fait.
#  Il ne ferme PAS l'escalade de privilèges. `ptressard` appartient au groupe
#  `docker` sur les deux nœuds, ce qui est déjà un équivalent root
#  (`docker run -v /:/host`), antérieur et nécessaire au modèle de déploiement —
#  c'est écrit noir sur blanc dans `export-hors-site.sh`. Ce module réduit la
#  surface et rétablit la symétrie ; annoncer autre chose serait un faux vert.
# =============================================================================

#: Fichier unique qui portera la règle, sur les deux nœuds.
SUDOERS_CIBLE=/etc/sudoers.d/5hostachy

#: Fichiers hérités à retirer APRÈS installation de la règle unique.
#:   010_pi-nopasswd  — livré par Raspberry Pi OS, `NOPASSWD: ALL` (rpi1)
#:   bascule          — la règle qui a donné son nom à #302 (rpi2), et qui ne
#:                      correspondait même pas à l'usage documenté : `sudo bash
#:                      <script>` exécute /usr/bin/bash, pas le script.
#:   ptressard, ptressard-extra — posés à la main, contenu divergent (rpi2)
SUDOERS_HERITES="010_pi-nopasswd bascule ptressard ptressard-extra"

# ── La règle, composée à partir du besoin RÉEL des scripts ───────────────────
# Chaque ligne est justifiée par un appelant versionné. Une permission sans
# appelant se retire ; une permission dont l'appelant disparaît doit être
# retirée avec lui (`standards/02` §5).
#
# `systemctl` est borné à l'unité `cloudflared` : sans cette borne, la règle
# autoriserait `systemctl start` de n'importe quelle unité, donc l'exécution de
# n'importe quel service — une escalade complète sous couvert de « redémarrer le
# tunnel ».
#
# ⚠️ `rsync` est là par nécessité, et c'est la surface qui reste à retirer.
# `bascule.sh` l'appelle trois fois via SSH pour installer uploads, WhatsApp auth
# et la base dans les volumes Docker du peer. `sudo rsync` sans borne de chemin
# EST une escalade root complète — rsync écrit où il veut. Le remède est connu et
# éprouvé (v2.46.11 : un conteneur jetable au lieu de sudo), mais il touche la
# phase de synchronisation de la BASE, où le `--delete` supprime les WAL/SHM
# résiduels du peer. C'est la règle d'or, et cela ne se modifie pas sans pouvoir
# observer une bascule réelle. Décision assumée, tracée dans #302.
# ⚠️ Le heredoc ci-dessous n'est PAS quoté — il doit substituer $u. Donc aucun
# accent grave dans son corps : il y ouvrirait une substitution de commande.
# Vécu le 12/08/2026, « is-active: command not found » à chaque appel — et le
# fichier composé s'en trouvait tronqué sans que rien ne le signale.
sudoers_regle() {  # $1 = compte visé (défaut : ptressard)
  local u="${1:-ptressard}"
  cat <<REGLE
# 5Hostachy — permissions élevées des nœuds. NE PAS ÉDITER À LA MAIN.
# Source unique : lib-sudoers.sh, installé par durcir-sudoers.sh.
# Toute modification faite ici sera écrasée, et divergera d'un nœud à l'autre —
# c'est précisément ce que ce fichier existe pour empêcher (#302).

# Tunnel Cloudflare — bascule.sh, health-watch.sh, boot-role-guard.sh.
# Borné à l'unité : sans cela, toute unité systemd serait démarrable en root.
$u ALL=(root) NOPASSWD: /usr/bin/systemctl start cloudflared
$u ALL=(root) NOPASSWD: /usr/bin/systemctl stop cloudflared
$u ALL=(root) NOPASSWD: /usr/bin/systemctl restart cloudflared
$u ALL=(root) NOPASSWD: /usr/bin/systemctl enable cloudflared
$u ALL=(root) NOPASSWD: /usr/bin/systemctl disable cloudflared
#  Pas de is-active ni is-enabled : ils sont appelés SANS sudo (bascule.sh
#  l. 92, boot-role-guard.sh, lib-collecte.sh) — l'état d'une unité se lit sans
#  privilège. Les autoriser serait une permission sans appelant.

# Lecture du crontab root — lib-collecte.sh (C18 compare les deux nœuds).
# En LECTURE seule : « crontab -l » et rien d'autre, sinon on autoriserait
# « crontab <fichier> », donc l'exécution de n'importe quoi en root.
$u ALL=(root) NOPASSWD: /usr/bin/crontab -l

# Installation des volumes sur le peer — bascule.sh, phases 1, 2 et 4.
# ⚠️ Surface la plus large de ce fichier, et la prochaine à retirer (#302).
$u ALL=(root) NOPASSWD: /usr/bin/rsync
REGLE
}

# ── Décisions PURES, éprouvées par --selftest ────────────────────────────────

# Une règle installée est-elle conforme à la règle attendue ?
# Rend OK · DIFFERENT · ABSENT · INCONNU — jamais un vert par défaut.
sudoers_conformite() {  # $1 = contenu lu sur le nœud, $2 = contenu attendu
  [ -z "${2:-}" ] && { echo INCONNU; return; }      # rien à comparer : on ne sait pas
  case "${1:-}" in
    "__ABSENT__") echo ABSENT; return ;;
    "__ILLISIBLE__"|"") echo INCONNU; return ;;
  esac
  [ "$1" = "$2" ] && echo OK || echo DIFFERENT
}

# Peut-on retirer les fichiers hérités ? SEULEMENT si la règle unique est en
# place et conforme. L'ordre n'est pas un détail de style : retirer d'abord
# `010_pi-nopasswd` sur un nœud dont la nouvelle règle n'est pas installée rend
# le compte incapable de piloter cloudflared — donc la bascule de 02:00 échoue,
# et le tunnel peut rester éteint des deux côtés (incident du 30/07).
sudoers_peut_nettoyer() {  # $1 = verdict de conformité
  [ "${1:-}" = "OK" ] && echo oui || echo non
}

sudoers_selftest() {
  local st=0 got
  c() {  # $1 = libellé, $2 = attendu, $3 = lu, $4 = attendu(contenu)
    got=$(sudoers_conformite "$3" "$4")
    if [ "$got" = "$2" ]; then echo "PASS  $1 → $got"
    else echo "FAIL  $1  attendu=$2 obtenu=$got"; st=1; fi
  }
  echo "== self-test lib-sudoers =="
  c "règle conforme"                 OK        "abc" "abc"
  c "règle divergente"               DIFFERENT "abc" "abd"
  c "fichier absent du nœud"         ABSENT    "__ABSENT__" "abc"
  #  LE CAS ZÉRO : une lecture qui échoue rend une chaîne vide. Sans ce
  #  traitement, deux vides seraient ÉGAUX et le contrôle dirait « conforme »
  #  sur un nœud qu'il n'a pas pu lire (`standards/04` §2).
  c "lecture impossible"             INCONNU   "__ILLISIBLE__" "abc"
  c "lecture vide"                   INCONNU   "" "abc"
  c "règle attendue non composable"  INCONNU   "abc" ""

  n() {  # $1 = libellé, $2 = attendu, $3 = verdict
    got=$(sudoers_peut_nettoyer "$3")
    if [ "$got" = "$2" ]; then echo "PASS  $1 → $got"
    else echo "FAIL  $1  attendu=$2 obtenu=$got"; st=1; fi
  }
  #  On ne retire les anciens fichiers QUE sur une règle installée et conforme.
  n "nettoyage après règle conforme" oui "OK"
  n "règle divergente : on ne touche à rien" non "DIFFERENT"
  n "règle absente : on ne touche à rien"    non "ABSENT"
  n "état inconnu : on ne touche à rien"     non "INCONNU"

  echo "-- la règle composée est-elle valide et complète ? --"
  local regle; regle=$(sudoers_regle ptressard)
  for besoin in "systemctl start cloudflared" "systemctl stop cloudflared" \
                "crontab -l" "/usr/bin/rsync"; do
    if printf '%s' "$regle" | grep -q -- "$besoin"; then
      echo "PASS  besoin couvert : $besoin"
    else
      echo "FAIL  besoin NON couvert : $besoin"; st=1
    fi
  done
  #  Une règle sans borne d'unité autoriserait toute unité systemd : c'est le
  #  défaut que ce fichier existe pour ne pas reproduire.
  if printf '%s' "$regle" | grep -qE '^[a-z]+ ALL=\(root\) NOPASSWD: /usr/bin/systemctl (start|stop|restart|enable|disable)$'; then
    echo "FAIL  une règle systemctl n est bornée à AUCUNE unité"; st=1
  else
    echo "PASS  toute règle systemctl est bornée à une unité"
  fi
  #  `NOPASSWD: ALL` ne doit jamais réapparaître dans la règle composée.
  if printf '%s' "$regle" | grep -qE 'NOPASSWD:[[:space:]]*ALL'; then
    echo "FAIL  la règle contient NOPASSWD: ALL"; st=1
  else
    echo "PASS  aucune règle sans borne de commande"
  fi

  [ $st -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
  return $st
}
