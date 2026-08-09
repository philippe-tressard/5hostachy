#!/bin/bash
# =============================================================================
#  export-hors-site.sh — Copie hors site de la dernière sauvegarde 5Hostachy
#
#  POURQUOI ce script existe (constat du 04/08/2026) :
#    Les sauvegardes de 03:00 sont produites par APScheduler DANS le conteneur
#    API, donc uniquement sur le nœud ACTIF, dans le volume Docker `backups`
#    que `bascule.sh` ne réplique PAS (il ne synchronise que uploads, app_data
#    et whatsapp_auth). Le rôle alternant chaque nuit, chaque RPi n'accumulait
#    qu'un jour sur deux, et `_rotate_backups()` ne voit que les fichiers
#    LOCAUX : les 7 versions conservées couvraient ~14 jours À TROUS, et aucun
#    nœud n'avait la sauvegarde de la veille.
#    Surtout : 100 % des archives vivaient sur deux machines posées au même
#    endroit, sur la même box et la même alimentation. Un `docker volume rm`,
#    un rançongiciel ou un sinistre emportait la base, les uploads ET toutes
#    les sauvegardes d'un seul coup. Cf. standards/06-donnees-et-integrite.md
#    §6 : une sauvegarde qui partage le destin de la production n'en est pas une.
#
#  CE QU'IL FAIT — exécuté depuis le POSTE (Git Bash), pas depuis un RPi :
#    1. Détermine le nœud source par son COMPORTEMENT (qui répond réellement
#       sur /api/health en LAN), et non en lisant le drapeau `.active` — cf.
#       standards/04 §10. Un `.active` peut mentir ; une API qui répond, non.
#    2. Tire la plus récente archive de ce nœud par un CONTENEUR JETABLE monté
#       en lecture seule sur le volume des sauvegardes — ni sudo, ni règle
#       sudoers, ni installation sur les nœuds (ni rsync ni scp : Git for
#       Windows n'embarque pas rsync).
#    3. La VÉRIFIE : empreinte identique à la source, gzip intact, `app.db`
#       présent dans l'archive, et `PRAGMA integrity_check` sur la copie
#       extraite. Vérifier la copie extraite est sans danger : c'est un
#       fichier à nous, pas la base de production (règle d'or : interdiction
#       d'ouvrir `app.db` de PROD depuis un process tiers, pas d'ouvrir une
#       copie morte).
#    4. Fait tourner les copies locales (N versions).
#    5. Poste son rapport sur `POST /api/admin/maintenance/rapport`
#       (tache=export_hors_site) — le canal cron qui existe déjà, avec sa clé
#       `x-maintenance-key`. Aucun second canal, aucune seconde table.
#
#  CE QU'IL NE FAIT PAS — et c'est délibéré :
#    Il n'ouvre JAMAIS `app.db` sur le RPi, ni en lecture. Il ne lit que des
#    fichiers `.tar.gz` déjà clos. Cf. CLAUDE.md « Règle d'or anti-corruption ».
#
#  ⚠ PORTÉE DE CETTE PROTECTION : le poste est au MÊME DOMICILE que les deux
#    RPi. Cette copie protège de la perte d'un nœud, d'un `docker volume rm`
#    et d'un rançongiciel visant les RPi — PAS de l'incendie ni du vol. Une
#    seconde destination réellement distante reste à ajouter ; la variable
#    EXPORT_DEST et la boucle de vérification sont écrites pour l'accueillir
#    sans réécriture.
#
#  LANCEMENT — MANUEL, depuis le poste, quand il est allumé :
#    • double-clic sur `export-hors-site.cmd` (à la racine du dépôt), ou
#    • depuis Git Bash :   bash /c/Dev/5hostachy/export-hors-site.sh
#
#    Le poste n'étant pas allumé en permanence, ce script n'est PAS planifié :
#    une tâche quotidienne sur une machine éteinte échoue plus souvent qu'elle
#    ne réussit, et une alerte qui crie tous les jours finit ignorée — c'est
#    ainsi qu'un contrôle meurt (standards/07 §5). Le rythme est donc laissé à
#    l'utilisateur, et c'est l'ÂGE de la dernière copie que l'application
#    surveille : l'onglet Admin → Maintenance affiche la tâche
#    `export_hors_site`, et le contrôle de 06:00 alerte au-delà d'une semaine
#    sans copie fraîche. Un oubli se voit ; il ne se devine pas.
#
#  Configuration — variables d'environnement (toutes optionnelles) :
#    EXPORT_DEST      répertoire de destination   (défaut : /c/Backup → C:\Backup)
#    EXPORT_KEEP      versions conservées         (défaut : 14)
#    EXPORT_SSH_USER  compte SSH sur les RPi      (défaut : ptressard)
#
#  ⚠ NE PAS pointer EXPORT_DEST dans C:\Dev\5hostachy : c'est un dépôt git, et
#    une archive de plusieurs centaines de Mo dans l'arbre de travail pollue
#    chaque `git status` et chaque diff, gitignorée ou non.
#
#  Test sans effet de bord : bash export-hors-site.sh --selftest
# =============================================================================
set -uo pipefail

EXPORT_DEST="${EXPORT_DEST:-/c/Backup}"
EXPORT_KEEP="${EXPORT_KEEP:-14}"
EXPORT_SSH_USER="${EXPORT_SSH_USER:-ptressard}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# ─────────────────────────────────────────────────────────────────────────────
#  FONCTIONS PURES — aucune E/S : ni SSH, ni écriture, ni réseau.
#  C'est le seul moyen de tester une décision d'infra sans les deux RPi
#  (pattern inauguré par boot-role-guard.sh, cf. CLAUDE.md § job CI test-scripts).
# ─────────────────────────────────────────────────────────────────────────────

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

# ─────────────────────────────────────────────────────────────────────────────
#  SELF-TEST — exécuté en CI (job test-scripts), aucun effet de bord.
# ─────────────────────────────────────────────────────────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
  st_fail=0
  check() { # description attendu obtenu
    if [ "$3" = "$2" ]; then echo "PASS  $1  → '$3'"
    else echo "FAIL  $1  attendu='$2' obtenu='$3'"; st_fail=1; fi
  }
  echo "== self-test export-hors-site =="

  check "rpi1 seul répond"          "rpi1"        "$(decider_source 200 000)"
  check "rpi2 seul répond"          "rpi2"        "$(decider_source 000 200)"
  check "les deux répondent"        "split-brain" "$(decider_source 200 200)"
  check "aucun ne répond"           "aucun"       "$(decider_source 000 000)"
  check "503 n'est pas un actif"    "rpi2"        "$(decider_source 503 200)"
  check "codes absents → aucun"     "aucun"       "$(decider_source)"

  # Le faux négatif du 04/08/2026 : `tar | grep -q` sous pipefail rendait
  # « absent » sur une archive contenant app.db. Le listing est désormais
  # analysé hors de tout tube, et ces cas verrouillent l'analyse.
  LISTING_OK=$'app.db\nuploads/\nuploads/doc.pdf'
  check "app.db en tête de listing"  "oui"        "$(contient_app_db "$LISTING_OK")"
  check "app.db seul"                "oui"        "$(contient_app_db 'app.db')"
  check "listing sans base"          "non"        "$(contient_app_db $'uploads/\nuploads/doc.pdf')"
  check "listing vide"               "non"        "$(contient_app_db '')"
  # Le piège de la sous-chaîne : un fichier nommé app.db DANS uploads n'est pas
  # la base. Une comparaison naïve l'accepterait.
  check "uploads/app.db ne compte pas" "non"      "$(contient_app_db $'uploads/app.db\nuploads/x')"
  check "suffixe app.db2 ne compte pas" "non"     "$(contient_app_db 'app.db2')"

  # ── Liste blanche du nom d'archive ─────────────────────────────────────────
  # Le nom vient du nœud distant et repart dans une commande exécutée là-bas.
  tn() { local r=refuse; nom_valide "$2" && r=ok
         [ "$r" = "$3" ] && echo "PASS  $1" || { echo "FAIL  $1 : attendu=$3 obtenu=$r"; st=1; }; }
  tn "nom d'archive normal"      "hostachy_backup_2026-08-09_030000.tar.gz" ok
  tn "nom vide"                  ""                                          refuse
  tn "chemin absolu"             "/etc/shadow"                               refuse
  tn "remontée de répertoire"    "hostachy_backup_../../etc/shadow.tar.gz"   refuse
  tn "sous-répertoire"           "hostachy_backup_a/b.tar.gz"                refuse
  tn "la base elle-même"         "app.db"                                    refuse
  tn "substitution de commande"  'hostachy_backup_$(id).tar.gz'              refuse

  check "archive saine"             "succes"      "$(verdict_archive 1024 oui oui ok | cut -d'|' -f1)"
  check "archive vide"              "erreur"      "$(verdict_archive 0 oui oui ok | cut -d'|' -f1)"
  check "empreinte différente"      "erreur"      "$(verdict_archive 1024 non oui ok | cut -d'|' -f1)"
  check "app.db absent"             "erreur"      "$(verdict_archive 1024 oui non ok | cut -d'|' -f1)"
  check "base corrompue"            "erreur"      "$(verdict_archive 1024 oui oui 'malformed' | cut -d'|' -f1)"
  # Le cas qui a coûté l'incident du 26/07 ailleurs : l'absence de contrôle
  # lue comme un succès. Ici, ne pas savoir vaut échec.
  check "intégrité non vérifiable"  "erreur"      "$(verdict_archive 1024 oui oui inconnue | cut -d'|' -f1)"

  LISTE=$'a\nb\nc\nd\ne'
  check "rotation garde 3"          $'a\nb'       "$(echo "$LISTE" | archives_a_supprimer 3)"
  check "rotation garde tout"       ""            "$(echo "$LISTE" | archives_a_supprimer 5)"
  check "rotation keep > total"     ""            "$(echo "$LISTE" | archives_a_supprimer 99)"
  # Garde-fou : une config aberrante ne doit pas vider la destination.
  check "keep=0 ne supprime rien"   ""            "$(echo "$LISTE" | archives_a_supprimer 0)"
  check "keep négatif ne fait rien" ""            "$(echo "$LISTE" | archives_a_supprimer -1)"
  check "liste vide"                ""            "$(printf '' | archives_a_supprimer 3)"

  [ $st_fail -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
  exit $st_fail
fi

# ─────────────────────────────────────────────────────────────────────────────
#  EXÉCUTION RÉELLE
# ─────────────────────────────────────────────────────────────────────────────

# Table d'adresses : aucune recopie ici — lib-role.sh est la source unique.
# shellcheck source=lib-role.sh
source "$SCRIPT_DIR/lib-role.sh"

SSH_CMD="ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new"
STATUT="succes"
MESSAGE=""
DEBUT=$(date -u +%Y-%m-%dT%H:%M:%S)
T0=$SECONDS
ARCHIVE=""
OCTETS=0
INTEGRITE="inconnue"
SOURCE_NOEUD=""

log "===== Export hors site ====="

# ── 1. Quel nœud sert réellement ? ───────────────────────────────────────────
IP1=$(role_ip rpi1); IP2=$(role_ip rpi2)
# curl écrit déjà `000` quand la connexion échoue : un `|| echo "000"` en plus
# concaténait les deux et produisait `000000` dans le journal (vu le 04/08/2026).
# Trompeur à lire, et fragile — la comparaison se fait sur la chaîne exacte.
sonde() { curl -s -o /dev/null -w '%{http_code}' --max-time 8 "http://$1/api/health" 2>/dev/null; }
CODE1=$(sonde "$IP1"); CODE2=$(sonde "$IP2")
SOURCE_NOEUD=$(decider_source "$CODE1" "$CODE2")
log "  Sonde LAN : rpi1=$CODE1 rpi2=$CODE2 → source = $SOURCE_NOEUD"

case "$SOURCE_NOEUD" in
  aucun)
    log "ERREUR: aucun nœud ne répond en LAN — rien à exporter."
    log "  → Le site est probablement HS. Voir .claude/skills/infra-rpi."
    exit 1 ;;
  split-brain)
    # Deux nœuds qui servent = deux bases qui divergent. Choisir l'un des deux
    # reviendrait à sauvegarder au hasard une moitié de la vérité, et à écraser
    # la précédente par rotation. On s'abstient, bruyamment.
    log "ERREUR: SPLIT-BRAIN — les deux nœuds répondent. Export annulé."
    log "  → Traiter le split-brain AVANT toute sauvegarde (docker ps sur les 2)."
    exit 1 ;;
esac

SOURCE_IP=$(role_ip "$SOURCE_NOEUD")
SSH_CIBLE="$EXPORT_SSH_USER@$SOURCE_IP"

# ── 2. Repérer et tirer la plus récente archive ──────────────────────────────
# Le point de montage du volume Docker appartient à root : `ptressard` ne peut ni
# le lister ni le lire. On passe par un script root à CHEMIN FIXE, qui n'expose
# que trois verbes et détermine le volume lui-même — voir `export-source.sh`.
#
# ⚠️ Pourquoi pas `NOPASSWD` sur `ls`/`cat`/`sha256sum` : ce serait la lecture de
# n'importe quel fichier en root (`sudo cat /etc/shadow`). Et pourquoi le script
# vit dans /usr/local/sbin et non /opt/5hostachy : ce dernier appartient à
# `ptressard` et `auto-deploy` y réécrit tout — une règle NOPASSWD sur un fichier
# que l'appelant peut réécrire est un accès root complet, pas une permission.
#
# ── Comment on lit les archives : un conteneur jetable, PAS `sudo` ───────────
# Le point de montage du volume appartient à root, mais `ptressard` est déjà dans
# le groupe `docker` sur les deux nœuds — c'est ce qui fait tourner auto-deploy et
# la bascule. Un conteneur monté en LECTURE SEULE sur le volume lit donc les
# archives sans le moindre privilège supplémentaire, et sans mot de passe.
#
# C'est ce qui remplace la dépendance à `sudo` : elle n'existait que sur rpi1
# (règle `010_pi-nopasswd` par défaut de Raspberry Pi OS) et manquait sur rpi2, si
# bien que la copie échouait UNE NUIT SUR DEUX — celles où rpi2 est actif
# (constaté le 09/08/2026, dernière copie réussie le 06/08). La corriger en
# ajoutant une règle sudoers demandait une installation manuelle sur chaque nœud ;
# ceci ne demande rien et vaut pour tout nœud présent ou futur.
#
# Aucun privilège n'est élargi : l'appartenance au groupe `docker` équivaut déjà à
# root, elle est antérieure et nécessaire au modèle de déploiement. On en RETIRE
# une (la règle sudoers devient inutile). Le montage est `:ro` et ne porte que le
# volume des sauvegardes : ni `app_data`, ni `app.db` — cf. la règle d'or.
LIRE="docker run --rm -v 5hostachy_backups:/b:ro alpine"

# On établit d'abord qu'on a PU regarder. Sans cette étape, une panne d'accès rend
# une liste vide, qui se lit comme « aucune sauvegarde » — un KO déguisé en
# constat, exactement ce qu'interdit standards/04 §1. Vécu deux fois : le
# 04/08/2026 (motif développé avant sudo) et le 09/08/2026 (sudo absent sur rpi2).
if ! $SSH_CMD "$SSH_CIBLE" "$LIRE true" >/dev/null 2>&1; then
  if ! $SSH_CMD "$SSH_CIBLE" "docker info" >/dev/null 2>&1; then
    log "ERREUR: docker inaccessible pour $EXPORT_SSH_USER sur $SOURCE_NOEUD — état INCONNU."
    log "        Le compte doit appartenir au groupe docker (id -nG)."
  elif ! $SSH_CMD "$SSH_CIBLE" "docker image inspect alpine" >/dev/null 2>&1; then
    log "ERREUR: image alpine absente sur $SOURCE_NOEUD et non téléchargeable — état INCONNU."
  else
    log "ERREUR: lecture du volume 5hostachy_backups impossible sur $SOURCE_NOEUD — état INCONNU."
  fi
  exit 1
fi

# Ici seulement une liste vide est un FAIT : la lecture a réussi.
ARCHIVE=$($SSH_CMD "$SSH_CIBLE"   "$LIRE sh -c 'ls -1 /b/hostachy_backup_*.tar.gz 2>/dev/null'" 2>/dev/null   | tr -d '
' | sed 's#.*/##' | sort | tail -1)
if [ -z "$ARCHIVE" ]; then
  log "ERREUR: aucune archive sur $SOURCE_NOEUD — la sauvegarde de 03:00 ne produit rien."
  exit 1
fi
# Le nom vient d'une machine distante et repart dans une commande : il est validé
# avant, jamais après. standards/03-securite.md §2 — liste blanche, ancrée.
if ! nom_valide "$ARCHIVE"; then
  log "ERREUR: nom d'archive inattendu sur $SOURCE_NOEUD ('$ARCHIVE') — abandon."
  exit 1
fi
log "  Archive la plus récente sur $SOURCE_NOEUD : $ARCHIVE"

mkdir -p "$EXPORT_DEST" || { log "ERREUR: destination inaccessible ($EXPORT_DEST)."; exit 1; }
LOCAL="$EXPORT_DEST/$ARCHIVE"

# Empreinte à la source AVANT transfert : c'est elle qui prouvera que la copie
# est fidèle. Sans elle, un transfert tronqué produit un fichier plausible.
SHA_SRC=$($SSH_CMD "$SSH_CIBLE" "$LIRE sha256sum '/b/$ARCHIVE'" 2>/dev/null | awk '{print $1}')

if [ -f "$LOCAL" ] && [ "$(sha256sum "$LOCAL" 2>/dev/null | awk '{print $1}')" = "$SHA_SRC" ]; then
  log "  → Déjà présente et identique — transfert ignoré."
else
  log "  Transfert en cours…"
  # Flux via ssh plutôt que rsync/scp : Git for Windows n'embarque pas rsync, et
  # scp ne sait pas élever ses droits sur la source.
  if ! $SSH_CMD "$SSH_CIBLE" "$LIRE cat '/b/$ARCHIVE'" > "$LOCAL.partiel" 2>/dev/null; then
    log "ERREUR: transfert interrompu."
    rm -f "$LOCAL.partiel"
    exit 1
  fi
  # Renommage seulement après transfert complet : jamais de fichier tronqué
  # portant un nom définitif, qu'une rotation prendrait ensuite pour une
  # sauvegarde valide.
  mv -f "$LOCAL.partiel" "$LOCAL"
fi

OCTETS=$(stat -c%s "$LOCAL" 2>/dev/null || echo 0)
SHA_DST=$(sha256sum "$LOCAL" 2>/dev/null | awk '{print $1}')
EMPREINTES="non"; [ -n "$SHA_SRC" ] && [ "$SHA_SRC" = "$SHA_DST" ] && EMPREINTES="oui"

# ── 3. Vérifier la copie (sur le POSTE — jamais sur la base de production) ───
LISTING=$(tar -tzf "$LOCAL" 2>/dev/null || true)
CONTIENT=$(contient_app_db "$LISTING")

if [ "$CONTIENT" = "oui" ]; then
  TMP=$(mktemp -d 2>/dev/null || echo "/tmp/export-hs-$$")
  mkdir -p "$TMP"
  if tar -xzf "$LOCAL" -C "$TMP" app.db 2>/dev/null; then
    # Ordre de préférence : sqlite3 s'il existe, sinon le module stdlib de
    # Python (présent sur ce poste de dev bien plus sûrement que la CLI).
    if command -v sqlite3 >/dev/null 2>&1; then
      INTEGRITE=$(sqlite3 "$TMP/app.db" "PRAGMA integrity_check;" 2>&1 | head -1)
    else
      # Python est un binaire Windows NATIF : il ne sait pas ouvrir un chemin
      # MSYS (`/c/…`). Sans cette conversion, il rend FileNotFoundError et
      # l'intégrité resterait « inconnue » — donc un échec — sur une archive
      # pourtant saine. Vérifié le 04/08/2026.
      CHEMIN_DB="$TMP/app.db"
      command -v cygpath >/dev/null 2>&1 && CHEMIN_DB=$(cygpath -w "$TMP/app.db")
      for PY in python3 python py; do
        if command -v "$PY" >/dev/null 2>&1; then
          INTEGRITE=$("$PY" -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print(c.execute('PRAGMA integrity_check').fetchone()[0]); c.close()" "$CHEMIN_DB" 2>&1 | head -1)
          break
        fi
      done
    fi
  fi
  rm -rf "$TMP"
fi
log "  Vérification : empreintes=$EMPREINTES app.db=$CONTIENT intégrité=$INTEGRITE"

VERDICT=$(verdict_archive "$OCTETS" "$EMPREINTES" "$CONTIENT" "$INTEGRITE")
STATUT="${VERDICT%%|*}"
MESSAGE="${VERDICT#*|}"
log "  → $STATUT : $MESSAGE"

# Une copie non validée ne doit pas rester dans la destination : au prochain
# sinistre, elle se présenterait comme une sauvegarde disponible.
if [ "$STATUT" != "succes" ] && [ -f "$LOCAL" ]; then
  mv -f "$LOCAL" "$LOCAL.invalide" 2>/dev/null || true
  log "  → Copie écartée sous $ARCHIVE.invalide (ne pas la prendre pour une sauvegarde)."
fi

# ── 4. Rotation des copies locales ───────────────────────────────────────────
if [ "$STATUT" = "succes" ]; then
  SUPPRIMEES=0
  while IFS= read -r vieux; do
    [ -n "$vieux" ] || continue
    rm -f "$EXPORT_DEST/$vieux" && SUPPRIMEES=$((SUPPRIMEES + 1))
  done < <(ls -1 "$EXPORT_DEST"/hostachy_backup_*.tar.gz 2>/dev/null | xargs -r -n1 basename | sort | archives_a_supprimer "$EXPORT_KEEP")
  log "  Rotation : $SUPPRIMEES ancienne(s) copie(s) supprimée(s), $EXPORT_KEEP conservée(s)."
fi

# ── 5. Rapport à l'API (canal cron existant) ─────────────────────────────────
# La clé est lue sur le nœud, pas recopiée sur le poste : un secret dupliqué est
# un secret à faire tourner deux fois.
# Le dépouillement se fait ICI, pas dans la commande distante : imbriquer des
# apostrophes et des guillemets dans un `tr` passé à ssh produisait une commande
# invalide, et la clé revenait vide alors qu'elle est bien dans le .env
# (04/08/2026). Les codes octaux \042 \047 évitent toute quote dans la source.
LIGNE_CLE=$($SSH_CMD "$SSH_CIBLE" "grep -m1 '^MAINTENANCE_KEY=' /opt/5hostachy/.env" 2>/dev/null || true)
MAINTENANCE_KEY=$(printf '%s' "${LIGNE_CLE#MAINTENANCE_KEY=}" | tr -d '\042\047\r')
if [ -z "$MAINTENANCE_KEY" ]; then
  log "  ⚠ MAINTENANCE_KEY illisible — rapport non enregistré (l'export, lui, a bien eu lieu)."
else
  FIN=$(date -u +%Y-%m-%dT%H:%M:%S)
  # `archive` porte l'horodatage dans son nom : c'est ce que le contrôle de
  # santé relit pour distinguer « l'export tourne » de « la copie est fraîche ».
  # Un export quotidien qui recopie fidèlement la même archive périmée est un
  # faux vert — c'est exactement ce cas que le champ permet de démasquer.
  DETAILS=$(printf '{"archive":"%s","taille_octets":%s,"integrite":"%s","empreinte_verifiee":"%s","destination":"%s","versions_conservees":%s}' \
    "$ARCHIVE" "${OCTETS:-0}" "${INTEGRITE//\"/}" "$EMPREINTES" "${EXPORT_DEST//\"/}" "${EXPORT_KEEP:-0}")

  # Construction et envoi mutualisés (lib-rapport.sh) : trois scripts rendent
  # compte, un seul sait fabriquer la charge utile. La clé, elle, est lue par
  # SSH sur le nœud ci-dessus et non dans un `.env` local — ce script tourne sur
  # le poste, qui n'en a pas.
  source "$SCRIPT_DIR/lib-rapport.sh"
  rapport_envoyer "http://$SOURCE_IP" "$MAINTENANCE_KEY" \
    "$(rapport_payload export_hors_site "$SOURCE_NOEUD" applicative "$STATUT" \
        "$((SECONDS - T0))" "$DETAILS" \
        "$([ "$STATUT" = "succes" ] || printf '%s' "$MESSAGE")" "$DEBUT" "$FIN")" \
    "Rapport"
fi

# ── 6. Résumé lisible ────────────────────────────────────────────────────────
# Ce script est lancé à la main, par un humain qui regarde la console : le
# dernier écran doit répondre sans effort à « est-ce que ma sauvegarde est là,
# et est-elle bonne ? ». Un code de sortie ne se lit pas dans une fenêtre qui
# se referme.
echo
if [ "$STATUT" = "succes" ]; then
  echo "  ✅ SAUVEGARDE HORS SITE À JOUR"
  echo "     Archive     : $ARCHIVE"
  echo "     Taille      : $(awk -v o="${OCTETS:-0}" 'BEGIN{printf "%.1f Mo", o/1048576}')"
  echo "     Emplacement : $EXPORT_DEST"
  echo "     Vérifiée    : empreinte identique à la source, integrity_check : ok"
  echo "     Source      : $SOURCE_NOEUD ($SOURCE_IP)"
else
  echo "  ❌ EXPORT ÉCHOUÉ — AUCUNE COPIE FIABLE N'A ÉTÉ PRODUITE"
  echo "     Motif : $MESSAGE"
  echo "     Ne pas considérer $EXPORT_DEST comme à jour."
fi
echo
log "===== Export hors site terminé : $STATUT ====="
[ "$STATUT" = "succes" ] || exit 1
exit 0
