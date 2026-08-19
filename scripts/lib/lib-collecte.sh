#!/bin/bash
# =============================================================================
#  lib-collecte.sh — le snippet exécuté sur CHAQUE nœud par check-reliability.sh
#
#  Module SOURCÉ (mode 100644), jamais exécuté directement. Extrait de
#  `check-reliability.sh` le 11/08/2026 : ce fichier repassait au-dessus du
#  plafond de modularité de 500 lignes en recevant le motif d'extraction des
#  rapports, et le garde-fou de rang 1 refuse qu'il grossisse.
#
#  Dépend de constantes définies par l'APPELANT, avant le source :
#    $LOG_WARN_MB · $MAINT_LOG · $RAPPORTS_MOTIF (ce dernier vient de
#    lib-verdicts.sh, qui doit donc être sourcé en premier).
#
#  ⚠️ Ce fichier définit du CODE SOUS FORME DE CHAÎNE. `bash -n lib-collecte.sh`
#  ne vérifie donc PAS ce que les nœuds exécuteront — il ne voit qu'une chaîne.
#  C'est `verdicts_selftest` qui passe `bash -n` sur la chaîne ASSEMBLÉE, et
#  c'est le seul contrôle qui regarde ce code-là. Ne pas le retirer.
# =============================================================================

# ── Snippet de collecte exécuté sur chaque nœud (local + peer) ───────────────
# ⚠ Assemblé AVANT le gate --selftest, et ce n'est pas un rangement cosmétique.
# Le 11/08/2026 ce bloc a référencé $R en sortant des quotes ('"$R"'), c'est-à-dire
# dans le shell qui ASSEMBLE la chaîne — où $R n'existe pas, n'ayant jamais existé
# ailleurs que dans le snippet lui-même. Sous `set -u`, l'assemblage tue le script
# avant son premier contrôle : check-reliability n'a plus tourné du tout sur le
# nœud actif, et seule la version périmée du standby a pu le signaler. `bash -n` ne
# voyait rien (la syntaxe est valide) et `--selftest` rendait la main avant d'y
# arriver : CI verte sur un script mort. Le gate est donc passé APRÈS, pour que la
# CI paie le prix de l'assemblage exactement comme la production.
# Émet des lignes key=value. Tout est tolérant aux erreurs (jamais d'exit ≠ 0).
#
# 🔴 CETTE CHAÎNE EST ENTRE GUILLEMETS SIMPLES : une apostrophe écrite à
# l'intérieur, même dans un commentaire, la ferme. L'assemblage reste du shell
# valide côté local et devient invalide côté distant — le défaut du 11/08/2026,
# reproduit à l'identique le 19/08 en y ajoutant un commentaire en français.
# `verdicts_selftest` l'attrape (« COLLECT assemblé est du shell INVALIDE »).
# Toute explication va donc ICI, au-dessus ; en dessous, on écrit sans apostrophe.
#
# ── Le motif d'extraction des scripts planifiés (C18) ────────────────────────
# Il doit rester IDENTIQUE à celui de `crontab_scripts()` dans `lib-verdicts.sh`,
# qui est la version pure et testée. `verdicts_selftest` échoue si les deux
# divergent — il ne s'agit pas d'un vœu, mais d'un contrôle.
#
# ⚠️ Pourquoi la barre oblique est dans la classe : #337 a rangé les scripts dans
# `/opt/5hostachy/scripts/exploitation/` le 15/08/2026, et la classe ne l'admettait
# pas. L'extraction rendait donc du VIDE sur les deux nœuds, et C18 a répondu
# « Crontabs root INCONNUS » quatre jours durant. Il l'a dit — INCONNU jamais OK,
# la règle a tenu — mais un INCONNU répété se lit « pas cette fois », jamais
# « mort depuis quatre jours ».
COLLECT='
R=/opt/5hostachy
echo "host=$(hostname)"
echo "active=$(cat $R/.active 2>/dev/null | tr -d "[:space:]")"
echo "containers=$(docker ps -q --filter name=hostachy 2>/dev/null | wc -l | tr -d " ")"
echo "cf_active=$(systemctl is-active cloudflared 2>/dev/null)"
echo "cf_enabled=$(systemctl is-enabled cloudflared 2>/dev/null)"
echo "head=$(git -C $R rev-parse --short HEAD 2>/dev/null)"
echo "origin_head=$(git -C $R rev-parse --short origin/main 2>/dev/null)"
echo "git_root_ok=$(git -C $R rev-parse HEAD >/dev/null 2>&1 && echo yes || echo no)"
BITS=ok; for s in bascule.sh health-watch.sh maintenance.sh auto-deploy.sh MaJ-Hostachy.sh check-reliability.sh boot-role-guard.sh; do [ -f "$R/$s" ] && [ ! -x "$R/$s" ] && BITS="manque:$s"; done
echo "exec_bits=$BITS"
echo "disk=$(df / | awk "NR==2{print \$5}" | tr -d %)"
echo "ntp=$(timedatectl show -p NTPSynchronized --value 2>/dev/null)"
echo "epoch=$(date +%s)"
echo "lock=$([ -f $R/.bascule-lock ] && stat -c %Y $R/.bascule-lock || echo 0)"
BIG=""; for l in /var/log/hostachy-*.log; do [ -f "$l" ] || continue; sz=$(( $(stat -c %s "$l")/1048576 )); [ "$sz" -ge '"$LOG_WARN_MB"' ] && BIG="$BIG $(basename $l):${sz}M"; done
echo "biglogs=$BIG"
echo "deploylog_owner=$(stat -c %U /var/log/hostachy-deploy.log 2>/dev/null || echo missing)"
echo "reliability_last=$(tail -3000 /var/log/hostachy-reliability.log 2>/dev/null | grep -oE "check-reliability \([0-9-]{10} [0-9:]{8}\)" | tail -1 | tr -d "()" | cut -d" " -f2-)"
echo "buildcache=$(docker system df --format "{{.Type}}|{{.Size}}" 2>/dev/null | grep -i "^Build Cache" | cut -d"|" -f2 | tr -d " ")"
# Motif SANS accent volontairement : ce bloc traverse SSH, et « Hygiène » y
# dépendrait de la locale des deux bouts. « Garde-fou » est aussi distinctif.
echo "maint_last=$(grep "Garde-fou" '"$MAINT_LOG"' 2>/dev/null | grep -oE "^\[[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}\]" | tail -1 | tr -d "[]")"
# Date du dernier rapport de maintenance EN BASE, pour ce nœud — la seconde sonde
# de C19. Lue par l'\''API in-process (jamais en ouvrant app.db : règle d'\''or), donc
# elle ne répond que sur l'\''ACTIF. Sur le standby la chaîne est vide, et C19 le
# traduit en INCONNU au lieu de conclure à une divergence.
# $R reste DANS les quotes : il appartient au snippet (défini plus haut), pas au
# shell qui assemble. Seules les CONSTANTES du script (LOG_WARN_MB, MAINT_LOG)
# justifient une sortie de quotes : elles ne vivent que côté assembleur.
# Et aucune apostrophe dans ces commentaires : ils sont DANS la chaîne, et une
# apostrophe nue la referme — sinon écrire le motif échappé, comme plus haut.
MK=$(grep -E "^MAINTENANCE_KEY=" $R/.env 2>/dev/null | cut -d= -f2- | tr -d "\"'"'"' \r")
REP=""
if [ -n "$MK" ]; then
  REP=$(curl -s --max-time 8 -w "|%{http_code}" -H "x-maintenance-key: $MK" \
    "http://localhost/api/admin/maintenance/dernier-rapport?tache=maintenance" 2>/dev/null)
fi
# Le marqueur `ok:` est posé UNIQUEMENT quand le curl a rendu 200. Sans lui, une
# carte vide se confond avec « demande impossible » — et cette confusion a rendu
# C19 muet le 11/08/2026 sur le cas meme que ce contrôle devait attraper (#305).
#
# Le motif vient de lib-verdicts.sh, injecté ici depuis le shell assembleur : une
# SEULE definition sert la collecte et son self-test. Ecrit a la main, il oubliait
# le Z final des horodatages ISO et ne pouvait jamais correspondre — la carte
# revenait vide quoi que rende API. Un motif recopie est un motif qui diverge.
# (Aucune apostrophe ici : ce bloc vit DANS une chaîne à quotes simples.)
case "$REP" in
  *"|200") echo "rapports=ok:$(echo "$REP" | tr -d "\" " | grep -oE "'"$RAPPORTS_MOTIF"'" | tr "\n" ";")" ;;
  *)       echo "rapports=" ;;
esac
# Crontab ROOT, et root seulement. Le test sur l'\''uid n'\''est pas une précaution
# de style : ce bloc tourne en root en local (cron root) mais en `ptressard` sur le
# peer (SSH). Un `crontab -l` nu y rendrait le crontab de `ptressard` — qui existe,
# donc la commande RÉUSSIRAIT en donnant la mauvaise réponse. Un faux vert par
# succès, le pire des cas.
if [ "$(id -u)" = "0" ]; then CRONRAW=$(crontab -l 2>/dev/null); else CRONRAW=$(sudo -n crontab -l 2>/dev/null); fi
# Motif jumeau de crontab_scripts() dans lib-verdicts.sh — voir la note au-dessus
# de COLLECT. La barre oblique dans la classe est indispensable depuis #337.
echo "cronscripts=$(echo "$CRONRAW" | grep -vE "^\s*(#|$)" | grep -oE "/opt/5hostachy/[A-Za-z0-9_./-]+\.sh" | sed "s#.*/##" | sort -u | paste -sd, - | tr -d " \n")"
# ── C20. Inventaire des permissions élevées — METADONNEES SEULES ─────────────
# Nom, taille et mode de chaque fichier, JAMAIS son contenu. Le repertoire est
# traversable par tous, donc ceci se lit sans le moindre privilege : c est ce qui
# permet de comparer les deux noeuds alors que le snippet tourne en root ici et
# en ptressard sur le peer. Lire le contenu a distance supposerait un NOPASSWD
# sur cat, cest-a-dire /etc/shadow — la faille meme quon surveille.
# Le marqueur ok: distingue « mesure faite, rien trouve » de « pas pu mesurer » :
# sans lui, deux repertoires illisibles rendraient deux chaines EGALES, donc un
# faux « identiques » (cas zero, deja vecu sur C14 et C18).
echo "sudofiles=$([ -x /etc/sudoers.d ] && { printf "ok:"; for f in /etc/sudoers.d/*; do [ -e "$f" ] || continue; printf "%s:%s:%s," "$(basename "$f")" "$(stat -c %s "$f" 2>/dev/null)" "$(stat -c %a "$f" 2>/dev/null)"; done; })"
# ── C21. Une permission elevee ne vaut que ce que vaut sa cible ──────────────
# Analyse LOCALE, en root : le peer ne rend rien et son champ vaut INCONNU. Le
# controle couvre quand meme les deux noeuds, puisquil tourne sur chacun deux.
# On rapporte des FAITS BRUTS (les cibles douteuses) ; cest lib-verdicts.sh qui
# conclut, et cest ce qui rend la decision testable sans les deux RPi.
if [ "$(id -u)" = "0" ]; then
  RISK=""
  RULES=$(grep -rhE "NOPASSWD" /etc/sudoers.d/ /etc/sudoers 2>/dev/null | grep -vE "^[[:space:]]*#")
  # Une regle bornee a aucune commande : le cas le plus grave, et le plus discret.
  case "$RULES" in *NOPASSWD:*ALL*) RISK="ALL" ;; esac
  for c in $(echo "$RULES" | grep -oE "/[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)+" | sort -u); do
    [ -e "$c" ] || continue
    M=$(stat -c %A "$c" 2>/dev/null); O=$(stat -c %U "$c" 2>/dev/null); D=$(stat -c %U "$(dirname "$c")" 2>/dev/null)
    BAD=""
    # Cible ou repertoire hors de root : lappelant peut remplacer le code execute.
    [ "$O" = "root" ] || BAD=1
    [ "$D" = "root" ] || BAD=1
    # %A rend 10 caracteres : position 6 = w du groupe, position 9 = w des autres.
    case "$M" in ?????w*) BAD=1 ;; esac
    case "$M" in ????????w*) BAD=1 ;; esac
    [ -n "$BAD" ] && RISK="$RISK $(basename "$c")"
  done
  echo "sudorisk=ok:$RISK"
else
  echo "sudorisk="
fi
'
