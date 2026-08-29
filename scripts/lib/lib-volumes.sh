#!/bin/bash
# =============================================================================
#  lib-volumes.sh — Installer un contenu dans un volume Docker SANS sudo (#582)
#
#  Module IMPORTÉ, jamais exécuté par un cron : pas de bit x, versionné en 100644.
#
#  ## Le fait
#
#  `bascule.sh` installe trois fois du contenu dans un volume du peer — uploads,
#  état d'authentification WhatsApp, base. La cible est à chaque fois le point de
#  montage d'un volume Docker, que seul root peut écrire. Le geste employé était :
#
#      ssh peer 'sudo rsync -a /tmp/… $(docker volume inspect … )/'
#
#  autorisé par une règle sudo `NOPASSWD: /usr/bin/rsync`.
#
#  🔴 **Cette règle n'est pas scopée, elle en a seulement l'air.** Sans borne de
#  chemin, rsync écrit où il veut — `/etc/sudoers.d/`, `/root/.ssh/authorized_keys`
#  — donc la règle vaut un accès root complet et permanent pour `ptressard`.
#  `standards/03` §8 bis : une permission nommée par l'OUTIL n'est pas une
#  permission bornée ; seul le CHEMIN borne.
#
#  ## Le remède, et ce qu'il n'apporte pas
#
#  Un conteneur jetable ne monte QUE le volume visé. Il n'ouvre **aucun privilège
#  nouveau** : l'appartenance au groupe `docker` est déjà un équivalent root, et
#  elle est antérieure et nécessaire au modèle de déploiement. Ce module ne
#  prétend donc pas supprimer le pouvoir root du compte — il supprime **une
#  seconde voie**, qui restait ouverte sans que rien ne l'utilise pour autre chose
#  que ces trois copies. Prétendre l'inverse serait un faux vert.
#
#  Même canal que `durcir-sudoers.sh`, qui écrit dans `/etc/sudoers.d` ainsi
#  depuis le 27/08/2026, et que la conversion de v2.46.11.
#
#  ## Pourquoi `cp -a` et non `rsync -a`
#
#  Aucune image du parc ne porte rsync, et un `apk add` à chaque bascule ferait
#  dépendre la bascule du réseau — au moment précis où le réseau est ce qu'on
#  vient d'éprouver. `cp -a` couvre exactement `rsync -a` sans `--delete` :
#  récursif, préserve mode, propriétaire, horodatage et liens symboliques.
#
#  Équivalence **vérifiée**, pas supposée — le 28/08/2026 sur le standby, volumes
#  jetables, contre la sortie de `sudo rsync -a` sur la même source : mode,
#  uid:gid, mtime, taille, liens symboliques et noms à espaces identiques,
#  contenus identiques octet à octet.
#
#  ⚠️ `--delete` n'est PAS couvert. La phase 4 (base) en a besoin pour retirer les
#  `app.db-wal` / `app.db-shm` résiduels du peer — c'est la règle d'or
#  anti-corruption, et ce n'est pas la même fonction. Elle s'ajoutera ici quand
#  cette phase-là sera convertie, avec son propre self-test.
#
#  ## Ordre de conversion imposé par #582
#
#  Un appel à la fois, en observant une bascule entre chaque : uploads (fait,
#  28/08/2026), puis authentification WhatsApp, puis la base. La règle sudo ne se
#  retire qu'une fois les trois convertis, et se vérifie par
#  `durcir-sudoers.sh --etat`.
#
#  Test : bash scripts/lib/lib-volumes.sh --selftest
# =============================================================================

# Rend la commande d'installation à exécuter SUR LE PEER, sans l'exécuter.
#
# Fonction PURE : aucune écriture, aucun docker, aucun SSH. C'est ce qui la rend
# éprouvable sans les deux RPi — et ce qui permet au self-test de vérifier la
# FORME du geste, seule chose qu'on puisse contrôler avant 02:00 (les phases de
# bascule écrivent, leur seule preuve est le journal du lendemain).
#
#   $1  nom du volume Docker cible          ex. 5hostachy_uploads
#   $2  répertoire temporaire source        ex. /tmp/sync_uploads
#
# Rend une chaîne vide si un argument manque : l'appelant doit traiter le cas
# comme INCONNU et s'abstenir, jamais construire une commande tronquée —
# `rm -rf ""` et un montage sur `/` sont exactement ce qu'on ne veut pas produire.
cmd_installer_volume() {
    local volume="${1:-}" source="${2:-}"
    [ -n "$volume" ] || return 1
    [ -n "$source" ] || return 1
    #  La source est montée en LECTURE SEULE : le conteneur n'a aucune raison
    #  d'écrire dans /tmp, et le lui interdire est gratuit.
    printf '%s' "docker run --rm -v ${volume}:/dst -v ${source}:/src:ro alpine sh -c \"cp -a /src/. /dst/\" && rm -rf ${source}"
}

# Transférer un volume local vers le volume homonyme du peer, en deux temps :
# rsync vers un temporaire du peer (que `ptressard` peut écrire), puis
# installation dans le volume par conteneur jetable.
#
# Cet enchaînement était écrit DEUX FOIS à l'identique dans `bascule.sh`, phases
# 1 et 2 — et une troisième était en vue, la phase 4 le fera le jour où
# `--delete` sera couvert. Une copie diverge : c'est le motif de tout ce
# chantier, et il valait aussi pour son propre correctif.
#
# ⚠️ CETTE FONCTION N'EST PAS PURE, contrairement à `cmd_installer_volume` : elle
# EXÉCUTE. Elle s'appuie sur `run`, `$SSH_CMD` et `$PEER_IP`, définis par
# `bascule.sh` — c'est le motif habituel du bash sourcé, mais un couplage
# implicite se découvre au pire moment. Elle le vérifie donc et refuse
# bruyamment plutôt que de lancer une commande tronquée sur la production.
#
#  $1  point de montage local     $2  nom du volume     $3  temporaire du peer
transferer_volume_vers_peer() {
    local source="$1" volume="$2" tmp="$3"
    #  Cas zéro : sans ces trois-là, `run` n'existe pas ou la cible est vide, et
    #  la commande construite viserait `ptressard@:/` — INCONNU, jamais OK.
    if ! declare -F run >/dev/null || [ -z "${SSH_CMD:-}" ] || [ -z "${PEER_IP:-}" ]; then
        echo "transferer_volume_vers_peer : run/SSH_CMD/PEER_IP manquants — abandon." >&2
        return 2
    fi
    local cmd
    cmd=$(cmd_installer_volume "$volume" "$tmp") || return 1
    run "rsync -az --delete -e '$SSH_CMD' '$source/' ptressard@$PEER_IP:$tmp/"
    run "$SSH_CMD ptressard@$PEER_IP '$cmd'"
}

# 🔴 `${BASH_SOURCE[0]}` = `$0` : le bloc ne s'exécute QUE si ce fichier est
# lancé directement. Sans ce garde, un script qui fait `source lib-volumes.sh`
# en ayant reçu `--selftest` verrait ses propres tests s'exécuter à sa place.
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    fail=0
    check() { # description attendu obtenu
        if [ "$3" = "$2" ]; then echo "PASS  $1"
        else echo "FAIL  $1"; echo "      attendu : $2"; echo "      obtenu  : $3"; fail=1; fi
    }
    contient() { # description motif
        local cmd; cmd=$(cmd_installer_volume 5hostachy_uploads /tmp/sync_uploads)
        case "$cmd" in *"$2"*) echo "PASS  $1" ;; *) echo "FAIL  $1 — absent : $2"; fail=1 ;; esac
    }
    absent() { # description motif
        local cmd; cmd=$(cmd_installer_volume 5hostachy_uploads /tmp/sync_uploads)
        case "$cmd" in *"$2"*) echo "FAIL  $1 — présent : $2"; fail=1 ;; *) echo "PASS  $1" ;; esac
    }

    echo "== self-test lib-volumes.cmd_installer_volume =="

    #  🔴 LE cas du ticket : c'est la disparition de `sudo` qui EST le correctif.
    #  Un remaniement qui le réintroduirait rouvrirait l'escalade root sans que
    #  rien d'autre ne le dise — le journal de bascule, lui, resterait vert.
    absent   "aucun sudo dans la commande produite"        "sudo"
    absent   "aucun rsync : l'image du parc n'en a pas"    "rsync"
    contient "le volume visé est monté en écriture"        "-v 5hostachy_uploads:/dst"
    #  La source montée en écriture serait un privilège gratuit.
    contient "la source est montée en LECTURE SEULE"       "/tmp/sync_uploads:/src:ro"
    contient "la copie préserve les attributs"             "cp -a /src/. /dst/"
    contient "le temporaire est nettoyé"                   "rm -rf /tmp/sync_uploads"
    #  ⚠️ `cp -a /src/ /dst/` (sans le point) crée `/dst/src` au lieu de copier le
    #  CONTENU. Le volume du peer recevrait un sous-répertoire, les uploads
    #  seraient introuvables, et la bascule n'aurait rien à signaler.
    absent   "pas de copie du répertoire au lieu du contenu" "cp -a /src/ /dst/"

    #  Cas zéro : un argument manquant ne doit pas produire une commande
    #  tronquée. `rm -rf ""` et un montage `-v :/src` sont exactement les deux
    #  gestes qu'une chaîne partielle fabriquerait.
    check "volume absent → aucune commande"  "" "$(cmd_installer_volume ''  /tmp/x || true)"
    check "source absente → aucune commande" "" "$(cmd_installer_volume vol ''     || true)"
    check "les deux absents → aucune commande" "" "$(cmd_installer_volume '' '' || true)"

    #  Le code de retour doit être non nul, sinon un appelant en `set -e` ne
    #  verrait rien et enchaînerait sur la chaîne vide.
    if cmd_installer_volume '' '' >/dev/null 2>&1; then
        echo "FAIL  un argument manquant doit rendre un code d'erreur"; fail=1
    else
        echo "PASS  un argument manquant rend un code d'erreur"
    fi

    #  Le nom du volume et le temporaire ne sont pas codés en dur : les deux
    #  conversions restantes (WhatsApp auth, base) passeront par la même fonction.
    check "la fonction sert un autre volume" \
        "docker run --rm -v 5hostachy_whatsapp_auth:/dst -v /tmp/sync_wa_auth:/src:ro alpine sh -c \"cp -a /src/. /dst/\" && rm -rf /tmp/sync_wa_auth" \
        "$(cmd_installer_volume 5hostachy_whatsapp_auth /tmp/sync_wa_auth)"

    # ─────────────────────────────────────────────────────────────────────────
    #  L'ÉTAT DU CHANTIER, vérifié sur `bascule.sh` et non sur ce commentaire
    # ─────────────────────────────────────────────────────────────────────────
    #
    #  🔴 Les contrôles ci-dessus vérifient la FORME de la commande produite. Ils
    #  resteraient tous verts si quelqu'un rétablissait `sudo rsync` dans
    #  `bascule.sh` : la fonction serait toujours correcte, simplement plus
    #  appelée. C'est exactement le faux vert que `standards/04` §3 nomme —
    #  vérifier le fait, pas le symptôme attendu.
    #
    #  On compte donc les APPELS restants dans `bascule.sh`, en excluant les
    #  commentaires. `APPELS_SUDO_ATTENDUS` descend à chaque étape convertie :
    #
    #      3 → étape 0 (avant #582)
    #      2 → étape 1/3, uploads          — observée le 28/08/2026
    #      1 → étape 2/3, WhatsApp auth    — observée le 29/08/2026
    #      0 → étape 3/3, base (`--delete`) — la règle sudo peut alors partir
    #
    #  ⚠️ Ce chiffre ne se baisse QUE lorsqu'un appel est réellement converti.
    #  Le baisser pour faire passer le test rendrait ce contrôle mensonger, ce
    #  qui est pire que son absence.
    APPELS_SUDO_ATTENDUS=1

    bascule="$(dirname "${BASH_SOURCE[0]}")/../exploitation/bascule.sh"
    if [ ! -f "$bascule" ]; then
        #  Cas zéro : un contrôle qui ne peut pas s'exécuter rend INCONNU, jamais
        #  OK (`standards/04` §1). Sans ce garde, un déplacement de fichier ferait
        #  compter zéro appel et le test féliciterait un chantier non fait.
        echo "FAIL  bascule.sh introuvable — état du chantier INCONNU, pas OK"
        fail=1
    else
        restants=$(grep -c "run \"\$SSH_CMD.*sudo rsync" "$bascule" || true)
        check "appels \`sudo rsync\` restants dans bascule.sh"             "$APPELS_SUDO_ATTENDUS" "$restants"

        #  Et l'inverse : la commande d'installation ne doit être écrite NULLE
        #  PART ailleurs qu'ici. Un `docker run -v …:/dst` réécrit à la main dans
        #  `bascule.sh` échapperait à tous les contrôles de forme ci-dessus — et
        #  c'est précisément la duplication que ce module existe pour éviter.
        #
        #  ⚠️ On ne compte PAS les appels à `cmd_installer_volume` : la première
        #  version de ce contrôle le faisait, et elle a échoué le jour où les
        #  deux phases ont été factorisées derrière un appelant commun — c'est-à-
        #  dire le jour où le code s'est AMÉLIORÉ. Un contrôle qui punit la
        #  factorisation mesure la forme, pas le fait.
        ecrit_a_la_main=$(grep -c 'docker run .*:/dst' "$bascule" || true)
        if [ "$ecrit_a_la_main" -eq 0 ]; then
            echo "PASS  aucune commande d'installation réécrite dans bascule.sh"
        else
            echo "FAIL  $ecrit_a_la_main commande(s) d'installation écrites hors de cmd_installer_volume"
            fail=1
        fi

        #  Chaque phase convertie doit passer par l'appelant commun. Deux
        #  aujourd'hui (uploads, WhatsApp auth) ; trois quand la base suivra.
        appels=$(grep -c '^ *transferer_volume_vers_peer ' "$bascule" || true)
        check "phases transférées par l'appelant commun" "2" "$appels"
    fi

    # ─────────────────────────────────────────────────────────────────────────
    #  `transferer_volume_vers_peer` — ses dépendances implicites
    # ─────────────────────────────────────────────────────────────────────────
    #  Elle EXÉCUTE, donc elle ne se teste pas comme la fonction pure : on lui
    #  substitue un `run` qui se contente d'imprimer. Ce qu'on vérifie, c'est
    #  qu'elle refuse quand son contexte manque — sans ce garde, `$PEER_IP` vide
    #  produirait `ptressard@:/tmp/…`, et un rsync vers une cible inconnue est
    #  exactement ce qu'on ne veut pas déclencher pendant une bascule.
    sortie=$(bash -c 'source '"${BASH_SOURCE[0]}"'; transferer_volume_vers_peer /a v /b' 2>&1; echo "code=$?")
    case "$sortie" in
        *"code=2"*) echo "PASS  dépendances absentes → refus (code 2)" ;;
        *) echo "FAIL  dépendances absentes : attendu un refus, obtenu : $sortie"; fail=1 ;;
    esac

    sortie=$(bash -c 'source '"${BASH_SOURCE[0]}"'; run() { :; }; SSH_CMD=s; transferer_volume_vers_peer /a v /b' 2>&1; echo "code=$?")
    case "$sortie" in
        *"code=2"*) echo "PASS  PEER_IP vide → refus, pas de cible tronquée" ;;
        *) echo "FAIL  PEER_IP vide : attendu un refus, obtenu : $sortie"; fail=1 ;;
    esac

    #  Nominal : les deux commandes, dans l'ordre, avec la bonne cible.
    sortie=$(bash -c 'source '"${BASH_SOURCE[0]}"'; run() { echo "RUN:$*"; }; SSH_CMD="ssh"; PEER_IP="10.0.0.1"; transferer_volume_vers_peer /mnt/s 5hostachy_uploads /tmp/t' 2>&1)
    case "$sortie" in
        *"RUN:rsync -az --delete"*"ptressard@10.0.0.1:/tmp/t/"*"RUN:ssh ptressard@10.0.0.1 'docker run"*)
            echo "PASS  nominal : transfert puis installation, dans cet ordre" ;;
        *) echo "FAIL  nominal inattendu : $sortie"; fail=1 ;;
    esac

    [ $fail -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
    exit $fail
fi
