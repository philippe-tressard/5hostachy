#!/bin/bash
# =============================================================================
#  lib-rapport.sh — Rapport d'exécution d'une tâche planifiée (module à sourcer)
#
#  POURQUOI ce module existe (04/08/2026) :
#    `maintenance.sh` savait rendre compte à l'application ; `bascule.sh`, non.
#    Résultat : la ligne « Bascule actif/standby » de l'écran Admin → Maintenance
#    était rouge « Jamais exécutée » EN PERMANENCE, alors que la bascule tournait
#    parfaitement chaque nuit. Un rouge permanent n'apprend rien et, pire, ne
#    peut plus rien signaler : si la bascule s'arrêtait vraiment, l'écran serait
#    identique. C'est le « battement manquant » de standards/04 §4, doublé d'une
#    alerte qu'on apprend à ignorer (standards/07 §5).
#
#    Plutôt que de recopier `envoyer_rapport()` dans un second script — ce que la
#    règle de non-duplication interdit, et ce qui aurait figé deux formats de
#    charge utile destinés à diverger — la fonction est extraite ici.
#
#  CE QU'IL CORRIGE AU PASSAGE : l'échappement JSON. L'implémentation d'origine
#    ne protégeait que les guillemets (`sed 's/"/\\"/g'`). Un message d'erreur
#    contenant une barre oblique inverse ou un SAUT DE LIGNE — ce que produit
#    n'importe quelle sortie de commande capturée — fabriquait un JSON invalide :
#    l'API répondait 422, le rapport était perdu, et le script se contentait de
#    journaliser « rapport non enregistré ». Une panne rendue muette par le
#    message d'erreur qui devait la décrire.
#
#  Usage :
#    source /opt/5hostachy/lib-rapport.sh
#    cle=$(rapport_cle /opt/5hostachy) || exit 0
#    charge=$(rapport_payload bascule rpi1 applicative succes 42 '{"vers":"rpi2"}' '' "$debut" "$fin")
#    rapport_envoyer "http://192.168.1.223" "$cle" "$charge" "bascule"
#
#  Les fonctions de CONSTRUCTION sont pures (aucune E/S) et couvertes par
#  `bash lib-rapport.sh --selftest`, lancé en intégration continue.
#  ⚠ L'autotest couvre la construction, jamais l'envoi : cf. standards/04 §11.
#
#  Ce module est SOURCÉ, jamais exécuté par cron → mode 100644 (le job CI
#  `test-scripts` le vérifie ; un bit d'exécution ici serait trompeur).
# =============================================================================

# ── Échappement d'une chaîne pour insertion dans un littéral JSON ────────────
# Ordre imposé : la barre oblique inverse d'ABORD, sinon on échapperait les
# séquences que l'on vient soi-même d'introduire.
rapport_echapper() { # $1=texte brut → texte sûr pour un "…" JSON
    printf '%s' "${1:-}" \
        | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e 's/\t/ /g' \
        | tr '\n\r' '  ' \
        | sed -e 's/  *$//'
}

# ── Construction de la charge utile ──────────────────────────────────────────
# Pure : ne lit aucun fichier, n'ouvre aucune connexion. `details` est un
# fragment JSON déjà formé (chaque tâche a ses propres chiffres, une colonne par
# chiffre serait ingérable — cf. le commentaire de HistoriqueMaintenance).
rapport_payload() { # tache noeud portee statut duree details erreur debut fin [tokens] [taille_db]
    local tache="${1:-}" noeud="${2:-}" portee="${3:-applicative}" statut="${4:-succes}"
    local duree="${5:-0}" details="${6:-null}" erreur="${7:-}" debut="${8:-}" fin="${9:-}"
    local tokens="${10:-0}" taille="${11:-null}"
    printf '{"tache":"%s","noeud":"%s","portee":"%s","statut":"%s","tokens_supprimes":%s,"taille_db_octets":%s,"duree_secondes":%s,"details":%s,"erreur":"%s","cree_le":"%s","terminee_le":"%s"}' \
        "$tache" "$noeud" "$portee" "$statut" "$tokens" "$taille" "$duree" \
        "${details:-null}" "$(rapport_echapper "$erreur")" "$debut" "$fin"
}

# ── Lecture de la clé partagée ───────────────────────────────────────────────
# Codes octaux \042 (guillemet) et \047 (apostrophe) : écrire ces caractères
# littéralement dans un `tr` finit toujours par casser au premier niveau
# d'imbrication supplémentaire.
rapport_cle() { # $1=repo → clé sur stdout, code 1 si absente
    local repo="${1:-/opt/5hostachy}" ligne
    ligne=$(grep -m1 '^MAINTENANCE_KEY=' "$repo/.env" 2>/dev/null) || return 1
    ligne=$(printf '%s' "${ligne#MAINTENANCE_KEY=}" | tr -d '\042\047\r')
    [ -n "$ligne" ] || return 1
    printf '%s' "$ligne"
}

# ── Envoi ────────────────────────────────────────────────────────────────────
# Ne fait JAMAIS échouer l'appelant : quand cette fonction s'exécute, le travail
# a déjà eu lieu. Perdre le rapport ne doit pas transformer un succès en échec.
rapport_envoyer() { # $1=url_base $2=clé $3=charge $4=libellé
    local base="${1:-}" cle="${2:-}" charge="${3:-}" libelle="${4:-rapport}" http
    if [ -z "$base" ] || [ -z "$cle" ]; then
        log "  ⚠ $libelle non enregistré (cible ou clé manquante)"
        return 0
    fi
    http=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 \
        -X POST "$base/api/admin/maintenance/rapport" \
        -H "Content-Type: application/json" \
        -H "x-maintenance-key: $cle" \
        -d "$charge" 2>/dev/null) || http="000"
    if [ "$http" = "201" ]; then
        log "  → $libelle enregistré sur $base (HTTP $http)"
    else
        log "  ⚠ $libelle non enregistré sur $base (HTTP $http)"
    fi
    return 0
}

# Journalisation : réutilise le log() de l'appelant s'il en définit un.
if ! declare -f log >/dev/null 2>&1; then
    log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
fi

# ── Self-test ────────────────────────────────────────────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    st_fail=0
    check() { if [ "$3" = "$2" ]; then echo "PASS  $1"
              else echo "FAIL  $1"; echo "        attendu = $2"; echo "        obtenu  = $3"; st_fail=1; fi }
    echo "== self-test lib-rapport =="

    check "texte simple inchangé"    'tout va bien'      "$(rapport_echapper 'tout va bien')"
    check "guillemet échappé"        'il a dit \"non\"'  "$(rapport_echapper 'il a dit "non"')"
    # Le cas qui cassait le JSON en silence : une sortie de commande capturée.
    check "saut de ligne aplati"     'ligne1 ligne2'     "$(rapport_echapper 'ligne1
ligne2')"
    check "barre oblique échappée"   'C:\\\\chemin'      "$(rapport_echapper 'C:\\chemin')"
    check "chaîne vide"              ''                  "$(rapport_echapper '')"

    attendu='{"tache":"bascule","noeud":"rpi1","portee":"applicative","statut":"succes","tokens_supprimes":0,"taille_db_octets":null,"duree_secondes":42,"details":{"vers":"rpi2"},"erreur":"","cree_le":"D","terminee_le":"F"}'
    check "charge utile nominale" "$attendu" \
        "$(rapport_payload bascule rpi1 applicative succes 42 '{"vers":"rpi2"}' '' D F)"

    check "details omis → null" \
        '{"tache":"t","noeud":"","portee":"applicative","statut":"succes","tokens_supprimes":0,"taille_db_octets":null,"duree_secondes":0,"details":null,"erreur":"","cree_le":"","terminee_le":""}' \
        "$(rapport_payload t)"

    # Le JSON produit doit être *analysable*, pas seulement ressemblant : c'est
    # la seule vérification qui aurait attrapé le défaut d'échappement d'origine.
    if command -v python3 >/dev/null 2>&1; then
        for cas in 'erreur simple' 'guillemet " dedans' 'multi
ligne' 'anti\slash'; do
            if printf '%s' "$(rapport_payload t n applicative erreur 1 null "$cas" D F)" \
                 | python3 -c 'import json,sys; json.load(sys.stdin)' 2>/dev/null; then
                echo "PASS  JSON analysable — cas « $(printf '%s' "$cas" | tr '\n' ' ') »"
            else
                echo "FAIL  JSON invalide — cas « $(printf '%s' "$cas" | tr '\n' ' ') »"; st_fail=1
            fi
        done
    else
        # standards/04 §1 : un contrôle qui ne peut pas s'exécuter rend INCONNU.
        echo "FAIL  python3 absent — validité JSON NON vérifiée (INCONNU, pas OK)"; st_fail=1
    fi

    [ $st_fail -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
    exit $st_fail
fi
