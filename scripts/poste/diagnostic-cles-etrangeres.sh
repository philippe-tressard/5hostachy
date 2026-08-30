#!/bin/bash
# =============================================================================
#  diagnostic-cles-etrangeres.sh — Combien de lignes orphelines la base porte-t-elle ?
#
#  ## Pourquoi ce script (#546, étape 2 bis)
#
#  La production tourne à `foreign_keys=OFF` : aucune clé étrangère n'est
#  vérifiée. Des suppressions incomplètes ont donc laissé des lignes qui
#  référencent un parent disparu — six endpoints le faisaient encore le
#  30/08/2026, dont `delete_evenement`, qui ne nettoyait RIEN.
#
#  Activer les clés n'effacera pas ces lignes ; il faut donc les COMPTER avant,
#  et décider quoi en faire. C'est ce que ce script demande à l'API.
#
#  ## 🔴 Il n'ouvre JAMAIS la base
#
#  Ouvrir `app.db` depuis un process tiers pendant que l'API tourne a corrompu
#  la base trois fois (05 et 17/06, 17/07/2026). La règle d'or ne souffre aucune
#  exception, **pas même en lecture**.
#
#  Ce script ne fait donc qu'un appel HTTP : la mesure s'exécute DANS le process
#  uvicorn (`app/utils/diagnostic_cles.py`), comme le checkpoint et
#  `quick_check`. Il ne lit du fichier `.env` que la clé partagée des scripts.
#
#  ## Ce qu'il rend
#
#  Le compte total et le détail par relation — table, colonne, table parente.
#  Jamais un `rowid` : l'API ne l'expose pas, ce canal étant borné à « aucune
#  donnée de copropriétaire ».
#
#  Usage :
#    bash scripts/poste/diagnostic-cles-etrangeres.sh [ip-du-noeud]
#    bash scripts/poste/diagnostic-cles-etrangeres.sh --selftest
# =============================================================================
set -uo pipefail

RPI1=192.168.1.222
RPI2=192.168.1.223
SSH="ssh -o BatchMode=yes -o ConnectTimeout=8"

#  Décision PURE : que conclure de ce que l'API a rendu ?
#
#  ⚠️ Le résultat NORMAL de ce diagnostic est ZÉRO. Un script qui confondrait
#  « aucun orphelin » avec « je n'ai pas pu demander » rendrait exactement le
#  même message dans les deux cas — c'est le faux vert que `standards/04` §1
#  interdit, et il est ici particulièrement facile à produire.
verdict_orphelins() {  # $1 = code HTTP, $2 = corps de la réponse
  local code="${1:-}" corps="${2:-}"
  [ "$code" = "200" ] || { echo "INCONNU"; return; }
  case "$corps" in
    *'"inconnu":true'*|*'"inconnu": true'*) echo "INCONNU" ;;
    *'"orphelins":0'*|*'"orphelins": 0'*)   echo "SAIN" ;;
    *'"orphelins"'*)                        echo "ORPHELINS" ;;
    *)                                      echo "INCONNU" ;;
  esac
}

if [ "${1:-}" = "--selftest" ]; then
  fail=0
  c() { if [ "$3" = "$2" ]; then echo "PASS  $1"; else echo "FAIL  $1 attendu=$2 obtenu=$3"; fail=1; fi; }
  echo "== self-test diagnostic-cles-etrangeres =="
  c "base saine"                 SAIN      "$(verdict_orphelins 200 '{"ok":true,"inconnu":false,"orphelins":0,"par_relation":[]}')"
  c "des orphelins"              ORPHELINS "$(verdict_orphelins 200 '{"ok":false,"inconnu":false,"orphelins":12,"par_relation":[]}')"
  #  🔴 LES TROIS FAÇONS DE NE PAS SAVOIR, et aucune ne doit ressembler à « sain ».
  c "l API dit qu elle n a pas pu" INCONNU "$(verdict_orphelins 200 '{"ok":false,"inconnu":true,"erreur":"x"}')"
  c "HTTP non 200"               INCONNU   "$(verdict_orphelins 403 '{"detail":"Cle maintenance invalide"}')"
  c "aucune reponse"             INCONNU   "$(verdict_orphelins 000 '')"
  c "corps illisible"            INCONNU   "$(verdict_orphelins 200 'pas du json')"
  #  Le cas zéro du motif lui-même : un corps SANS le champ attendu ne doit pas
  #  passer pour sain sous prétexte qu il ne dit pas le contraire.
  c "corps sans le champ"        INCONNU   "$(verdict_orphelins 200 '{"ok":true}')"
  [ $fail -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
  exit $fail
fi

# ── Le nœud à interroger : celui qui SERT, pas celui que `.active` déclare ────
#  Deux sondes valent mieux qu un fichier : `.active` a déjà été trouvé
#  incohérent avec la réalité (26/07/2026), et interroger un nœud standby
#  rendrait 000 sans que rien ne dise pourquoi.
CIBLE="${1:-}"
if [ -z "$CIBLE" ]; then
  for ip in "$RPI2" "$RPI1"; do
    if [ "$($SSH "ptressard@$ip" "curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://localhost/api/health" 2>/dev/null)" = "200" ]; then
      CIBLE="$ip"; break
    fi
  done
fi
[ -n "$CIBLE" ] || { echo "✗ INCONNU : aucun nœud ne répond sur /api/health."; exit 2; }

echo "Nœud interrogé : $CIBLE"
REP=$($SSH "ptressard@$CIBLE" '
  MK=$(grep -E "^MAINTENANCE_KEY=" /opt/5hostachy/.env 2>/dev/null | cut -d= -f2- | tr -d "\"'"'"' \r")
  [ -n "$MK" ] || { echo "|000"; exit 0; }
  curl -s -w "|%{http_code}" --max-time 20 -H "x-maintenance-key: $MK" \
    http://localhost/api/admin/maintenance/cles-etrangeres' 2>/dev/null)

CODE="${REP##*|}"
CORPS="${REP%|*}"

case "$(verdict_orphelins "$CODE" "$CORPS")" in
  SAIN)
    #  Deux faits DISTINCTS, et les confondre a un coût : « rien d'orphelin »
    #  décrit ce que la base contient, « clés actives » ce qu'elle refusera
    #  demain. Un relevé à zéro sur une base sans clés n'est pas une victoire,
    #  c'est un sursis.
    case "$CORPS" in
      *'"cles_actives":true'*|*'"cles_actives": true'*)
        echo "✓ Aucune ligne orpheline, et les clés étrangères sont ACTIVES." ;;
      *'"cles_actives"'*)
        echo "⚠ Aucune ligne orpheline, mais les clés étrangères sont INACTIVES."
        echo "  La base est saine et rien ne la maintiendra ainsi." ;;
      *)
        echo "✓ Aucune ligne orpheline — état des clés non rendu par l'API." ;;
    esac
    ;;
  ORPHELINS)
    echo "🔴 Des lignes orphelines subsistent — à traiter AVANT d'activer les clés :"
    echo "$CORPS" | python -c "
import json,sys
d=json.load(sys.stdin)
print(f\"   total : {d['orphelins']}\")
for r in d['par_relation']:
    print(f\"   {r['lignes']:6d}  {r['table']}.{r['colonne']} -> {r['table_parente']}\")
" 2>/dev/null || echo "$CORPS"
    exit 1
    ;;
  *)
    #  INCONNU, jamais OK : un contrôle qui n a pas pu mesurer ne rassure pas.
    echo "✗ INCONNU : la mesure n'a pas pu avoir lieu (HTTP $CODE)."
    echo "  $CORPS"
    exit 2
    ;;
esac
