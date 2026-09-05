#!/bin/bash
# =============================================================================
#  lib-export-hors-site.sh — les DÉCISIONS de la copie hors site (module à sourcer)
#
#  POURQUOI ce module existe (05/09/2026, #775) :
#    `export-hors-site.sh` a reçu la passe de rattrapage sur le second nœud et le
#    relevé de continuité de la série — de la fonctionnalité, pas du gras. Il est
#    passé de 498 à 588 lignes, et le garde-fou de modularité (rang 1) a refusé
#    qu'il grossisse.
#
#    ⚠️ C'est un découpage de MODULARITÉ, et il faut l'appeler par son nom : il
#    ne supprime aucune duplication. La factorisation du même jour est ailleurs —
#    `transferer_archive`, écrite une fois pour les deux passes, et restée dans
#    le script parce qu'elle fait du réseau.
#
#  Ce module ne contient QUE des fonctions pures : ni SSH, ni docker, ni
#  écriture, ni lecture de fichier. C'est ce qui les rend éprouvables par
#  `--selftest` sans les deux RPi — le motif inauguré par `boot-role-guard.sh`
#  et étendu depuis à toute décision d'infra.
#
#  Usage :   source "$(dirname "$0")/../lib/lib-export-hors-site.sh"
#  Test  :   bash scripts/poste/export-hors-site.sh --selftest
#
#  ⚠️ CE MODULE N'A PAS DE `--selftest` À LUI, et ce n'est pas un oubli : ses
#  fonctions sont éprouvées par celui du script appelant, qui les source. Lui en
#  poser un vide — ou l'inscrire tel quel dans la CI — rendrait 0 sans rien
#  mesurer : un faux vert, exactement ce que `standards/04` §1 interdit. Le jour
#  où ce module servira à un second appelant, il prendra son propre bloc.
# =============================================================================

# ── Quel nœud sert réellement ? ──────────────────────────────────────────────
# Entrées : les codes HTTP obtenus sur http://<ip>/api/health de chaque nœud.
# On ne lit PAS `.active` : ce drapeau a déjà divergé en production (26/07/2026,
# neuf FAIL consécutifs), et il peut désigner un nœud qui ne sert rien. La
# sauvegarde de 03:00 est produite par le conteneur API — donc par le nœud qui
# RÉPOND, par définition. On interroge le fait, pas sa déclaration.
decider_source() { # $1=code_rpi1 $2=code_rpi2 → rpi1|rpi2|split-brain|aucun
  local c1="${1:-000}" c2="${2:-000}"
  if [ "$c1" = "200" ] && [ "$c2" = "200" ]; then echo "split-brain"; return 0; fi
  if [ "$c1" = "200" ]; then echo "rpi1"; return 0; fi
  if [ "$c2" = "200" ]; then echo "rpi2"; return 0; fi
  echo "aucun"
}

# ── L'archive contient-elle bien la base ? ───────────────────────────────────
# Prend le LISTING déjà produit, et ne fait aucune E/S — parce que la version
# « en ligne » de ce test était fausse de deux façons (04/08/2026) :
#   • `tar -tzf … | grep -qx app.db` : `grep -q` sort dès le premier match et
#     ferme le tube ; `tar` meurt alors en SIGPIPE, et `set -o pipefail` propage
#     cet échec. Le test rendait donc « absent » sur une archive qui contenait
#     app.db — un faux négatif silencieux sur le contrôle le plus important ;
#   • une comparaison par sous-chaîne ferait passer `uploads/app.db` pour la
#     base. Le nom doit correspondre à la ligne ENTIÈRE.
contient_app_db() { # $1=listing tar → oui|non
  case $'\n'"${1:-}"$'\n' in
    *$'\napp.db\n'*) echo "oui" ;;
    *)              echo "non" ;;
  esac
}

# ── Le nom d'archive annoncé par le nœud est-il acceptable ? ─────────────────
# Ce nom vient d'une machine distante et repart dans une commande exécutée là-bas :
# il est validé en LISTE BLANCHE ancrée (standards/03-securite.md §2), jamais par
# liste noire. Sans cette borne, un nom fabriqué deviendrait un chemin ou une
# commande. C'est aussi ce qui garantit qu'on ne lira jamais autre chose qu'une
# archive de sauvegarde close — jamais `app.db`.
nom_valide() { # $1 = nom candidat → 0 si acceptable
  local n=${1:-}
  [ -n "$n" ] || return 1
  [[ "$n" =~ ^hostachy_backup_[A-Za-z0-9._-]+\.tar\.gz$ ]] || return 1
  case "$n" in */*|*'\'*|*..*) return 1 ;; esac
  return 0
}

# ── L'archive tirée est-elle exploitable ? ───────────────────────────────────
# Quatre conditions, toutes nécessaires. Une archive qu'on n'a pas su vérifier
# n'est PAS déclarée saine : elle renvoie `erreur`, jamais `succes` — un
# contrôle qui ne peut pas s'exécuter rend INCONNU (standards/04 §1), et une
# sauvegarde qu'on croit bonne à tort est pire que pas de sauvegarde du tout.
verdict_archive() { # $1=octets $2=empreintes_identiques $3=contient_db $4=integrite → statut|message
  local octets="${1:-0}" empreintes="${2:-non}" contient="${3:-non}" integrite="${4:-inconnue}"
  if [ "${octets:-0}" -le 0 ] 2>/dev/null || [ -z "$octets" ]; then
    echo "erreur|Archive vide ou absente après transfert."; return 0
  fi
  if [ "$empreintes" != "oui" ]; then
    echo "erreur|Empreinte SHA-256 différente de la source — transfert tronqué ou altéré."; return 0
  fi
  if [ "$contient" != "oui" ]; then
    echo "erreur|L'archive ne contient pas app.db — sauvegarde inexploitable."; return 0
  fi
  if [ "$integrite" = "inconnue" ]; then
    echo "erreur|Intégrité NON vérifiée (ni sqlite3 ni python disponibles) — copie non validée."; return 0
  fi
  if [ "$integrite" != "ok" ]; then
    echo "erreur|Base corrompue dans l'archive (integrity_check : $integrite)."; return 0
  fi
  echo "succes|Copie hors site vérifiée ($octets octets, integrity_check : ok)."
}

# ── Quelles copies locales supprimer ? ───────────────────────────────────────
# Reçoit la liste des noms DÉJÀ TRIÉE par ordre chronologique croissant (le nom
# porte l'horodatage : hostachy_backup_YYYYmmdd_HHMMSS.tar.gz — même convention
# que _rotate_backups() côté API). Rend les noms excédentaires, les plus anciens
# d'abord. `keep <= 0` ne supprime RIEN : une valeur de configuration aberrante
# ne doit jamais effacer les sauvegardes.
archives_a_supprimer() { # $1=keep, liste sur stdin → noms à supprimer
  local keep="${1:-0}" total=0
  local -a noms=()
  while IFS= read -r n; do [ -n "$n" ] && noms+=("$n"); done
  total=${#noms[@]}
  if [ "$keep" -le 0 ] 2>/dev/null; then return 0; fi
  [ "$total" -le "$keep" ] && return 0
  local i
  for ((i = 0; i < total - keep; i++)); do echo "${noms[$i]}"; done
}

# ── Quels jours manquent dans la copie hors site ? ───────────────────────────
# 🔴 #775 (05/09/2026) : la bascule de 02:00 change le nœud actif chaque nuit,
# donc la série d'archives est RÉPARTIE sur les deux volumes — relevé ce jour-là,
# rpi1 portait 31/08, 02/09, 04/09 et rpi2 03/09, 05/09. La passe de rattrapage
# va chercher ce qui manque ; cette fonction dit S'IL manque quelque chose.
#
# ⚠️ PURE — aucune E/S : c'est ce qui la rend éprouvable par `--selftest`, sans
# les deux RPi. Le motif du projet pour toute décision d'infra.
jours_manquants() { # $1=jours_a_couvrir $2=date_du_jour(AAAAMMJJ) puis noms sur stdin
  local fenetre="${1:-14}" aujourdhui="${2:-}" noms manquants=""
  noms=$(cat)
  [ -n "$aujourdhui" ] || aujourdhui=$(date +%Y%m%d)
  local i jour
  # On remonte le temps jour par jour, en partant de la VEILLE : l'archive du
  # jour même n'existe qu'après 02:00, et l'exiger ferait crier le contrôle
  # chaque matin pour un fait normal.
  for ((i = 1; i <= fenetre; i++)); do
    jour=$(date -d "$aujourdhui -$i day" +%Y%m%d 2>/dev/null) || return 0
    case "$noms" in
      *"hostachy_backup_${jour}_"*) ;;
      *) manquants="$manquants $jour" ;;
    esac
  done
  echo "${manquants# }"
}
