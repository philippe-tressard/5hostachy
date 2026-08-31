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
#  ## `--delete` : le mode « miroir », et pourquoi ce n'est pas une seconde fonction
#
#  La phase 4 (base) a besoin de `--delete` pour retirer les `app.db-wal` /
#  `app.db-shm` résiduels du peer — c'est la règle d'or anti-corruption : un WAL
#  orphelin laissé à côté d'une base fraîche est exactement ce qu'on ne veut pas
#  faire démarrer. Le geste équivalent est `find /dst -mindepth 1 -delete` puis
#  la même copie.
#
#  Ce mode est un ARGUMENT de `cmd_installer_volume`, et non une fonction
#  jumelle : deux fonctions qui ne diffèrent que par un préambule divergent au
#  premier correctif appliqué d'un seul côté — c'est le motif de tout ce
#  chantier (`standards/02` §1), et il vaut aussi pour son propre correctif.
#
#  🔴 UNE GARDE QUE `rsync --delete` N'AVAIT PAS. La commande vide la
#  destination : si la source était vide — rsync interrompu, temporaire nettoyé
#  par un tiers — elle effacerait la base du peer et n'y remettrait rien, et
#  `rsync -a --delete` d'une source vide faisait exactement cela, en silence.
#  Le mode miroir refuse donc de commencer sur une source vide (`find /src …
#  | grep -q .`), ce qui fait échouer la phase, donc déclenche le rollback, donc
#  laisse le site sur un nœud dont la base est intacte.
#
#  ⚠️ Ce que ce mode ne reproduit PAS de `rsync --delete` : rsync supprime au fil
#  du transfert, ici on supprime AVANT de copier. Une copie interrompue au milieu
#  laisse donc le volume du peer incomplet. C'est sans conséquence dans la
#  séquence de bascule — l'échec déclenche le rollback, le site reste sur l'actif
#  dont la base n'a pas bougé, et la bascule suivante réécrit tout — mais cela se
#  dit, parce qu'un appelant hors bascule n'aurait pas ce filet.
#
#  ## Ordre de conversion imposé par #582
#
#  Un appel à la fois, en observant une bascule entre chaque : uploads (fait et
#  observé le 28/08/2026), authentification WhatsApp (observée le 30/08/2026,
#  `→ WhatsApp auth synchronisé (conteneur jetable, sans sudo ; creds.json: 1883
#  octets, JSON valide)`), puis la base — convertie le 30/08/2026, à observer.
#  La règle sudo ne se retire qu'une fois cette dernière bascule CONSTATÉE, pas
#  à la conversion, et se vérifie par `durcir-sudoers.sh --etat`.
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
#   $3  mode : `ajout` (défaut) ou `miroir` — cf. l'en-tête pour `miroir`
#
# Rend une chaîne vide si un argument manque OU si le mode est inconnu :
# l'appelant doit traiter le cas comme INCONNU et s'abstenir, jamais construire
# une commande tronquée — `rm -rf ""` et un montage sur `/` sont exactement ce
# qu'on ne veut pas produire. Un mode mal orthographié ne doit surtout pas
# retomber silencieusement sur `ajout` : la phase 4 laisserait alors les WAL/SHM
# résiduels du peer en place, et rien ne le dirait.
cmd_installer_volume() {
    local volume="${1:-}" source="${2:-}" mode="${3:-ajout}" prelude=''
    [ -n "$volume" ] || return 1
    [ -n "$source" ] || return 1
    case "$mode" in
        ajout)  prelude='' ;;
        #  Vider la cible AVANT de copier. `find … -mindepth 1 -delete` plutôt
        #  qu'un glob : `rm -rf /dst/*` rate les fichiers cachés, et une chaîne
        #  contenant `*` serait développée par le `eval` de `run` avant même de
        #  partir en SSH.
        #  La garde de source non vide passe en premier : sans elle, la
        #  destination serait vidée pour rien (cf. en-tête).
        miroir) prelude='find /src -mindepth 1 -maxdepth 1 | grep -q . && find /dst -mindepth 1 -delete && ' ;;
        *)      return 1 ;;
    esac
    #  La source est montée en LECTURE SEULE : le conteneur n'a aucune raison
    #  d'écrire dans /tmp, et le lui interdire est gratuit.
    printf '%s' "docker run --rm -v ${volume}:/dst -v ${source}:/src:ro alpine sh -c \"${prelude}cp -a /src/. /dst/\" && rm -rf ${source}"
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
#  $4  mode d'installation : `ajout` (défaut) ou `miroir`
transferer_volume_vers_peer() {
    pousser_vers_temporaire_peer "$1" "$3" || return $?
    installer_volume_peer "$2" "$3" "${4:-ajout}"
}

# Le contexte que les deux gestes ci-dessous empruntent à `bascule.sh`.
#
# 🔴 Un couplage implicite se découvre au pire moment : `$PEER_IP` vide produit
# `ptressard@:/tmp/…`, et un rsync vers une cible inconnue pendant une bascule
# n'est pas quelque chose qu'on veut déclencher pour le constater ensuite.
# Écrit une fois — les deux gestes le partagent, et un troisième appelant
# l'obtiendra sans y penser.
_contexte_peer_present() {  # $1 = nom de l'appelant, pour le message
    if ! declare -F run >/dev/null || [ -z "${SSH_CMD:-}" ] || [ -z "${PEER_IP:-}" ]; then
        echo "${1:-lib-volumes} : run/SSH_CMD/PEER_IP manquants — abandon." >&2
        return 2
    fi
}

# 1er temps — pousser le contenu local vers un temporaire du peer.
#
# Aucun privilège : `/tmp/…` appartient à `ptressard`. C'est l'installation dans
# le volume, au 2ᵉ temps, qui demandait `sudo` — et qui ne le demande plus.
#
#  $1  point de montage local     $2  temporaire du peer
pousser_vers_temporaire_peer() {
    local source="$1" tmp="$2"
    _contexte_peer_present pousser_vers_temporaire_peer || return $?
    [ -n "$source" ] && [ -n "$tmp" ] || {
        echo "pousser_vers_temporaire_peer : source ou temporaire vide — abandon." >&2
        return 1
    }
    run "rsync -az --delete -e '$SSH_CMD' '$source/' ptressard@$PEER_IP:$tmp/"
}

# 2ᵉ temps — installer le temporaire du peer dans son volume, sans sudo.
#
# Séparé du 1er temps parce que la phase 4 s'intercale entre les deux : elle
# lance `PRAGMA integrity_check` sur la base poussée AVANT de l'installer, et
# renonce si elle est corrompue. Une phase qui doit s'intercaler ne peut pas
# appeler l'enchaînement complet — sans cette séparation elle réécrivait le
# `docker run` à la main, et c'est très exactement la duplication que ce module
# existe pour empêcher.
#
#  $1  nom du volume     $2  temporaire du peer     $3  mode (`ajout`|`miroir`)
installer_volume_peer() {
    local volume="$1" tmp="$2" mode="${3:-ajout}" cmd
    _contexte_peer_present installer_volume_peer || return $?
    #  Cas zéro : argument manquant ou mode inconnu → aucune commande. On
    #  s'abstient, on ne devine pas.
    cmd=$(cmd_installer_volume "$volume" "$tmp" "$mode") || {
        echo "installer_volume_peer : volume/temporaire/mode invalides ($volume, $tmp, $mode) — abandon." >&2
        return 1
    }
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
    contient() { # description motif [mode]
        local cmd; cmd=$(cmd_installer_volume 5hostachy_uploads /tmp/sync_uploads "${3:-ajout}")
        case "$cmd" in *"$2"*) echo "PASS  $1" ;; *) echo "FAIL  $1 — absent : $2"; fail=1 ;; esac
    }
    absent() { # description motif [mode]
        local cmd; cmd=$(cmd_installer_volume 5hostachy_uploads /tmp/sync_uploads "${3:-ajout}")
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
    #  Le mode par défaut n'efface RIEN : c'est ce qui distingue les phases 1 et
    #  2 de la phase 4, et une inversion silencieuse viderait un volume.
    #  ⚠️ Aucun accent grave dans les libellés : entre guillemets doubles, bash y
    #  ouvre une substitution de commande. Le test passait, son nom était vide,
    #  et « ajout: command not found » s'imprimait au milieu du relevé — même
    #  piège que le heredoc de `lib-sudoers.sh` (12/08/2026).
    absent   "mode ajout : aucune suppression"             "find /dst"

    echo "-- mode miroir (phase 4, base) : ce que faisait \`--delete\` --"
    contient "la cible est vidée avant la copie"  "find /dst -mindepth 1 -delete" miroir
    #  🔴 La garde que `rsync -a --delete` n'avait pas : une source vide vidait
    #  la base du peer sans rien y remettre, en silence.
    contient "refus de vider sur une source vide" "find /src -mindepth 1 -maxdepth 1 | grep -q ." miroir
    contient "puis la même copie qu'en mode ajout" "cp -a /src/. /dst/" miroir
    absent   "toujours aucun sudo en mode miroir" "sudo" miroir
    #  ⚠️ `rm -rf /dst/*` raterait les fichiers cachés — et le `*` serait
    #  développé par le `eval` de `run` AVANT de partir en SSH, donc sur le nœud
    #  actif et non sur le peer.
    absent   "pas de glob dans la suppression"    "/dst/*" miroir
    #  L'ORDRE compte : la garde d'abord, la suppression ensuite. Inversés, on
    #  viderait la cible avant de découvrir que la source est vide.
    case "$(cmd_installer_volume v /tmp/s miroir)" in
        *"grep -q . && find /dst -mindepth 1 -delete && cp -a"*)
            echo "PASS  l'ordre est : garde, purge, copie" ;;
        *) echo "FAIL  l'ordre garde/purge/copie n'est pas celui attendu"; fail=1 ;;
    esac
    #  🔴 CAS ZÉRO DU MODE : un mode mal orthographié ne doit PAS retomber sur
    #  `ajout`. La phase 4 laisserait alors les WAL/SHM résiduels du peer en
    #  place — le défaut exact que ce mode existe pour supprimer — et la
    #  commande produite serait parfaitement valide, donc muette.
    check "mode inconnu → aucune commande" "" "$(cmd_installer_volume v /tmp/s supprimer || true)"
    if cmd_installer_volume v /tmp/s miroirr >/dev/null 2>&1; then
        echo "FAIL  un mode inconnu doit rendre un code d'erreur"; fail=1
    else
        echo "PASS  un mode inconnu rend un code d'erreur"
    fi

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
    #      2 → étape 1/3, uploads          — observée le 29/08/2026 02:02
    #      1 → étape 2/3, WhatsApp auth    — observée le 30/08/2026 02:02
    #      0 → étape 3/3, base (`--delete`) — convertie le 30/08/2026
    #
    #  ⚠️ Ce chiffre ne se baisse QUE lorsqu'un appel est réellement converti.
    #  Le baisser pour faire passer le test rendrait ce contrôle mensonger, ce
    #  qui est pire que son absence.
    #
    #  ✅ TERMINÉ le 31/08/2026 — et « zéro appel » ne l'a jamais suffi à lui
    #  seul. « Zéro appel dans le code » et « zéro appel exécuté » sont deux
    #  faits différents : la phase 4 ne tourne qu'à 02:00. La règle sudo est
    #  restée en place jusqu'à ce que le journal montre la ligne attendue —
    #  chemin de repli conservé pour la seule phase non éprouvée, et la plus
    #  délicate des trois (c'est elle qui porte le `--delete` sur la base) :
    #
    #      [2026-08-31 02:02:26]   → DB installée dans le volume peer
    #                                (conteneur jetable, sans sudo).
    #      [2026-08-31 02:02:53] ===== Bascule terminée =====
    #
    #  ⚠️ Ce compteur RESTE à zéro et reste utile : il refuse le retour d'un
    #  `sudo rsync` dans `bascule.sh`, que plus rien n'autoriserait côté sudoers
    #  — donc une bascule qui échouerait au pire moment, à 02:00, sans personne.
    APPELS_SUDO_ATTENDUS=0

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

        #  Chaque phase convertie doit passer par ce module. Trois aujourd'hui :
        #  uploads et WhatsApp auth par l'enchaînement complet, la base par les
        #  deux temps séparés (elle vérifie l'intégrité entre les deux).
        #
        #  ⚠️ On compte l'ENSEMBLE des points d'entrée, pas `transferer_…` seul :
        #  la première version de ce contrôle comptait un seul nom et a échoué
        #  le jour où les phases ont été factorisées derrière un appelant commun
        #  — le jour où le code s'est AMÉLIORÉ. Découper `transferer_…` en deux
        #  temps l'aurait fait échouer une seconde fois, pour la même raison.
        appels=$(grep -cE '^ *(transferer_volume_vers_peer|installer_volume_peer) ' "$bascule" || true)
        check "phases installées via lib-volumes" "3" "$appels"

        #  Et la phase 4 doit demander le mode `miroir` — en mode `ajout`, les
        #  `app.db-wal` / `app.db-shm` résiduels du peer survivraient à côté
        #  d'une base fraîche. La commande produite resterait valide : rien,
        #  hors ce contrôle, ne dirait que la purge n'a pas eu lieu.
        if grep -q '^ *installer_volume_peer 5hostachy_app_data /tmp/sync_app_data miroir$' "$bascule"; then
            echo "PASS  la base est installée en mode miroir (WAL/SHM du peer purgés)"
        else
            echo "FAIL  la phase 4 n'installe pas la base en mode miroir"; fail=1
        fi
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

    # ─────────────────────────────────────────────────────────────────────────
    #  Les deux temps séparés — ce dont la phase 4 se sert
    # ─────────────────────────────────────────────────────────────────────────
    #  Le garde de contexte est écrit UNE fois et partagé : on vérifie donc qu'il
    #  protège bien les deux points d'entrée, et pas seulement celui par lequel
    #  il est arrivé.
    for f in pousser_vers_temporaire_peer installer_volume_peer; do
        sortie=$(bash -c 'source '"${BASH_SOURCE[0]}"'; '"$f"' a b' 2>&1; echo "code=$?")
        case "$sortie" in
            *"code=2"*) echo "PASS  $f : contexte absent → refus (code 2)" ;;
            *) echo "FAIL  $f : attendu un refus, obtenu : $sortie"; fail=1 ;;
        esac
    done

    #  🔴 Le 1er temps ne doit RIEN installer, et le 2ᵉ ne doit RIEN pousser.
    #  Si l'un faisait le travail de l'autre, la phase 4 vérifierait l'intégrité
    #  d'une base DÉJÀ installée dans le volume du peer — c'est-à-dire trop tard.
    sortie=$(bash -c 'source '"${BASH_SOURCE[0]}"'; run() { echo "RUN:$*"; }; SSH_CMD="ssh"; PEER_IP="10.0.0.1"; pousser_vers_temporaire_peer /mnt/s /tmp/t' 2>&1)
    case "$sortie" in
        *"docker run"*) echo "FAIL  le 1er temps installe déjà : $sortie"; fail=1 ;;
        *"RUN:rsync -az --delete"*"ptressard@10.0.0.1:/tmp/t/"*)
            echo "PASS  1er temps : pousse vers le temporaire, et rien d'autre" ;;
        *) echo "FAIL  1er temps inattendu : $sortie"; fail=1 ;;
    esac

    sortie=$(bash -c 'source '"${BASH_SOURCE[0]}"'; run() { echo "RUN:$*"; }; SSH_CMD="ssh"; PEER_IP="10.0.0.1"; installer_volume_peer 5hostachy_app_data /tmp/t miroir' 2>&1)
    case "$sortie" in
        *"RUN:rsync"*) echo "FAIL  le 2e temps pousse encore : $sortie"; fail=1 ;;
        *"RUN:ssh ptressard@10.0.0.1 'docker run"*"find /dst -mindepth 1 -delete"*)
            echo "PASS  2e temps : installe en miroir, et rien d'autre" ;;
        *) echo "FAIL  2e temps inattendu : $sortie"; fail=1 ;;
    esac

    #  Cas zéro des deux temps : un mode inconnu ne doit rien lancer du tout.
    #  Sans ce refus, `cmd_installer_volume` rendrait une chaîne vide et
    #  `run "ssh peer ''"` ouvrirait un shell distant sans commande — vert au
    #  journal, et la base jamais installée.
    sortie=$(bash -c 'source '"${BASH_SOURCE[0]}"'; run() { echo "RUN:$*"; }; SSH_CMD="ssh"; PEER_IP="10.0.0.1"; installer_volume_peer v /tmp/t supprimer' 2>&1; echo "code=$?")
    case "$sortie" in
        *"RUN:"*) echo "FAIL  mode inconnu : une commande a été lancée — $sortie"; fail=1 ;;
        *"code=1"*) echo "PASS  mode inconnu → aucune commande lancée, code 1" ;;
        *) echo "FAIL  mode inconnu inattendu : $sortie"; fail=1 ;;
    esac

    [ $fail -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
    exit $fail
fi
