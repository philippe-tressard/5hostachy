#!/bin/bash
# =============================================================================
#  export-source.sh — accès root MINIMAL aux archives de sauvegarde, pour que
#  `export-hors-site.sh` puisse les tirer depuis le poste sans mot de passe.
#
#  POURQUOI CE SCRIPT EXISTE
#  Le point de montage du volume Docker `5hostachy_backups` appartient à root :
#  `ptressard` ne peut ni le lister ni le lire. La copie hors site échouait donc
#  une nuit sur deux — exactement les nuits où **rpi2** est actif, car rpi1 porte
#  la règle NOPASSWD globale de Raspberry Pi OS (`010_pi-nopasswd`) et rpi2 non.
#  Constaté le 09/08/2026 : « sudo: a password is required », dernière copie
#  réussie le 06/08 depuis rpi1. Les deux nœuds n'étaient pas configurés à
#  l'identique — même classe que les crontabs divergents du 06/08.
#
#  POURQUOI PAS `NOPASSWD: /usr/bin/cat`
#  Cela donnerait à `ptressard` la lecture de **n'importe quel fichier en root**
#  (`sudo cat /etc/shadow`). Ce script n'expose que trois verbes, sur un volume
#  qu'il détermine LUI-MÊME, et n'accepte du client qu'un **nom d'archive** —
#  jamais un chemin. La liste blanche est le motif, pas la liste noire.
#
#  ⚠️ INSTALLATION — hors de l'arbre git, et c'est essentiel
#  /opt/5hostachy appartient à `ptressard` et `auto-deploy` y réécrit tout à
#  chaque déploiement. Une règle NOPASSWD pointant vers un fichier que
#  `ptressard` peut réécrire n'est pas une permission restreinte : c'est un accès
#  root complet. Ce script doit donc vivre dans un répertoire root :
#
#    sudo install -o root -g root -m 0755 \
#         /opt/5hostachy/export-source.sh /usr/local/sbin/hostachy-export-source
#    printf 'ptressard ALL=(ALL) NOPASSWD: /usr/local/sbin/hostachy-export-source\n' \
#      | sudo tee /etc/sudoers.d/hostachy-export >/dev/null
#    sudo chmod 0440 /etc/sudoers.d/hostachy-export
#    sudo visudo -c        # ⚠️ OBLIGATOIRE : un sudoers malformé verrouille sudo
#
#  Usage (appelé par export-hors-site.sh, via ssh + sudo) :
#    hostachy-export-source liste            → un nom d'archive par ligne
#    hostachy-export-source sha   <archive>  → empreinte SHA-256
#    hostachy-export-source flux  <archive>  → contenu sur stdout
#    hostachy-export-source --selftest       → contrôles de la validation (CI)
#
#  Ce script ne lit QUE des .tar.gz clos. Il n'ouvre jamais `app.db` ni le volume
#  `app_data` — cf. la règle d'or anti-corruption DB (standards/06 §1).
# =============================================================================
set -euo pipefail

VOLUME_NOM=5hostachy_backups
#  Liste blanche du nom d'archive. Ancrée aux deux bouts : c'est elle qui empêche
#  qu'un nom devienne un chemin. `standards/03-securite.md` §2.
MOTIF='^hostachy_backup_[A-Za-z0-9._-]+\.tar\.gz$'

nom_valide() {  # $1 = nom candidat → 0 si acceptable
    local n=${1:-}
    [ -n "$n" ] || return 1
    [[ "$n" =~ $MOTIF ]] || return 1
    #  Ceinture et bretelles : aucun séparateur, aucune remontée. Le motif les
    #  exclut déjà, mais un futur assouplissement du motif ne doit pas rouvrir
    #  la traversée de répertoire sans faire échouer l'auto-test.
    case "$n" in */*|*'\'*|*..*) return 1 ;; esac
    return 0
}

# ── Auto-test (job CI `test-scripts`) — la validation, seule partie pure ──────
if [ "${1:-}" = "--selftest" ]; then
    st=0
    t() {  # $1 = libellé · $2 = nom · $3 = attendu (ok|refuse)
        local r=refuse; nom_valide "$2" && r=ok
        [ "$r" = "$3" ] && echo "PASS  $1" || { echo "FAIL  $1 : attendu=$3 obtenu=$r"; st=1; }
    }
    t "archive normale"            "hostachy_backup_2026-08-09_030000.tar.gz" ok
    t "nom vide"                   ""                                          refuse
    t "chemin absolu"              "/etc/shadow"                               refuse
    t "remontée de répertoire"     "hostachy_backup_../../etc/shadow.tar.gz"   refuse
    t "sous-répertoire"            "hostachy_backup_a/b.tar.gz"                refuse
    t "préfixe non conforme"       "autre_backup_2026.tar.gz"                  refuse
    t "extension non conforme"     "hostachy_backup_2026.tar.gz.sh"            refuse
    t "espace puis commande"       "hostachy_backup_2026.tar.gz ; id"          refuse
    t "substitution de commande"   'hostachy_backup_$(id).tar.gz'              refuse
    [ $st -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
    exit $st
fi

[ "$(id -u)" = "0" ] || { echo "export-source: doit être lancé en root (via sudo)." >&2; exit 1; }

#  Le volume est déterminé ICI, jamais reçu du client : un chemin fourni par
#  l'appelant rendrait la règle NOPASSWD équivalente à `cat` sur tout le disque.
VOL=$(docker volume inspect "$VOLUME_NOM" --format '{{.Mountpoint}}' 2>/dev/null) || VOL=""
[ -n "$VOL" ] && [ -d "$VOL" ] || {
    echo "export-source: volume $VOLUME_NOM introuvable." >&2; exit 3; }

VERBE=${1:-}
case "$VERBE" in
    liste)
        #  Aucune archive n'est un RÉSULTAT légitime (code 0) : c'est à l'appelant
        #  de distinguer « rien à copier » de « je n'ai pas pu regarder », et il
        #  ne le peut que si l'échec de droits, lui, sort en non-zéro.
        find "$VOL" -maxdepth 1 -type f -name 'hostachy_backup_*.tar.gz' -printf '%f\n' | sort
        ;;
    sha)
        nom_valide "${2:-}" || { echo "export-source: nom d'archive refusé." >&2; exit 2; }
        [ -f "$VOL/$2" ] || { echo "export-source: archive absente." >&2; exit 4; }
        sha256sum "$VOL/$2" | awk '{print $1}'
        ;;
    flux)
        nom_valide "${2:-}" || { echo "export-source: nom d'archive refusé." >&2; exit 2; }
        [ -f "$VOL/$2" ] || { echo "export-source: archive absente." >&2; exit 4; }
        cat "$VOL/$2"
        ;;
    *)
        echo "export-source: verbe inconnu ('${VERBE}'). Attendu : liste | sha | flux." >&2
        exit 2
        ;;
esac
