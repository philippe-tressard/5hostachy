#!/usr/bin/env bash
# =============================================================================
#  lib-precheck-infra.sh — les points d'EXPLOITATION du pré-check MEP (12 à 18)
#
#  Extrait de `precheck-mep.sh` le 20/08/2026, au fil de l'eau : le point 18
#  (parité des IMAGES du standby, #511) l'aurait porté au-dessus de 500 lignes.
#
#  ⚠️ Ce module n'est PAS autonome. Il utilise `sur`, `rapporter`, les
#  `verdict_*` et les seuils définis par son appelant — il est sourcé APRÈS eux,
#  et appelé par `precheck_points_infra`. Le sourcer seul ne produirait rien
#  d'exploitable, et surtout aucune erreur : c'est pourquoi il ne s'exécute pas
#  au chargement.
#
#  Ce qu'il porte : l'image de l'actif face à son commit (12), la vivacité du
#  canal d'alerte (13), l'hygiène disque des deux nœuds (14), la conformité des
#  points d'entrée au dépôt (17) et la parité des IMAGES du standby (18).
# =============================================================================

precheck_points_infra() {
  # 12 — image du service touché reconstruite après le commit
  IMG=$(sur "$ACTIF" 'docker inspect hostachy_api --format "{{.Created}}" 2>/dev/null')
  CMT=$(sur "$ACTIF" 'git -C /opt/5hostachy log -1 --format=%cI 2>/dev/null')
  if [ -z "$IMG" ] || [ -z "$CMT" ]; then V12=INCONNU
  elif [ "$(date -d "$IMG" +%s 2>/dev/null)" -ge "$(date -d "$CMT" +%s 2>/dev/null)" ]; then V12=OK
  else V12=FAIL; fi
  #  Les deux instants s'affichent dans le MÊME référentiel — celui du poste.
  #  Tronquer à 19 caractères supprimait justement ce qui portait le fuseau : le
  #  `Z` de Docker (UTC) d'un côté, le `+02:00` de git (local) de l'autre. Le
  #  détail montrait alors « image=…20:24:29 commit=…22:19:39 » à côté d'un verdict
  #  OK — deux chiffres incomparables qui contredisaient leur propre conclusion,
  #  alors que la comparaison, elle, était juste (#313). Un contrôle dont le détail
  #  dément le verdict pousse à ignorer le détail.
  horodate() { date -d "$1" '+%d/%m %H:%M:%S' 2>/dev/null || echo "?"; }
  rapporter 12 "$V12" "Image postérieure au commit déployé" \
            "image=$(horodate "$IMG") commit=$(horodate "$CMT") (heure du poste)"

  # 13 — le canal d'alerte a-t-il émis ? On croise la dernière ALERTE et le dernier
  #      ÉCHEC, tous deux horodatés. Les « Email KO » ne le sont pas : les compter
  #      donnait 7 depuis toujours, indatables (mémoire du 02/08/2026).
  age_ligne() {  # $1 = hôte, $2 = motif, $3 = fichier — âge en minutes, vide si absent
    sur "$1" "d=\$(grep \"$2\" $3 2>/dev/null | grep -oE '^\[[0-9-]+ [0-9:]+' | tail -1 | tr -d '[');             [ -n \"\$d\" ] && echo \$(( ( \$(date +%s) - \$(date -d \"\$d\" +%s) ) / 60 ))"
  }
  AGE_ALERTE=$(age_ligne "$ACTIF" "Alerte envoyée" /var/log/hostachy-reliability.log)
  AGE_FAIL=$(age_ligne "$ACTIF" "^\[FAIL\]" /var/log/hostachy-reliability.log)
  #  Vivacité du PRODUCTEUR de FAIL. Sans elle, un script mort rend ce point vert :
  #  zéro FAIL au journal se lit « rien à signaler » alors que plus rien n'écrit.
  #  Vécu le 11/08/2026 — deux MEP autorisées pendant que check-reliability était
  #  mort sur l'actif (#306). L'horodatage est celui de l'en-tête de chaque
  #  exécution, le même repère que C15 utilise pour surveiller le peer.
  CR_MAX_AGE_MIN=40   # 2 ticks de 15 min manqués, aligné sur C15
  AGE_CR=$(sur "$ACTIF" "d=\$(grep -oE 'check-reliability \([0-9-]{10} [0-9:]{8}\)' /var/log/hostachy-reliability.log 2>/dev/null | tail -1 | tr -d '()' | cut -d' ' -f2-);             [ -n \"\$d\" ] && echo \$(( ( \$(date +%s) - \$(date -d \"\$d\" +%s) ) / 60 ))")
  if [ -n "${AGE_FAIL:-}" ]; then
    DETAIL13="dernier échec il y a ${AGE_FAIL} min, alerte ${AGE_ALERTE:-jamais envoyée}"
  elif [ -z "${AGE_CR:-}" ] || [ "${AGE_CR:-999}" -gt "$CR_MAX_AGE_MIN" ] 2>/dev/null; then
    DETAIL13="check-reliability muet depuis ${AGE_CR:-?} min — son silence ne prouve rien"
  else
    DETAIL13="aucun échec à signaler, et le contrôle tourne (il y a ${AGE_CR} min)"
  fi
  rapporter 13 "$(verdict_alerte "${AGE_ALERTE:-}" "${AGE_FAIL:-}" "${AGE_CR:-}" "$CR_MAX_AGE_MIN")" \
            "Canal d'alerte non muet" "$DETAIL13"

  # 14 — hygiène disque sur les DEUX nœuds
  for h in "$RPI1" "$RPI2"; do
    CACHE=$(sur "$h" "docker system df 2>/dev/null | awk '/^Build Cache/ {print \$5}'")
    GROS=$(sur "$h" "find /var/log -name 'hostachy-*.log' -size +${LOG_MAX_MO}M 2>/dev/null | wc -l")
    V14=$(verdict_cache "${CACHE:-}")
    [ "$V14" = OK ] && [ -n "$GROS" ] && [ "$GROS" -gt 0 ] 2>/dev/null && V14=FAIL
    [ -z "$GROS" ] && V14=INCONNU
    rapporter 14 "$V14" "Hygiène disque (${h##*@})" "cache=${CACHE:-?}  logs>${LOG_MAX_MO}Mo=${GROS:-?}"
  done

  # 17 — les points d'entrée des nœuds sont-ils ceux que le dépôt attend ?
  #
  #      Ajouté le 15/08/2026. Les tâches cron et l'unité systemd désignent les
  #      scripts par CHEMIN ABSOLU, et n'étaient écrites nulle part : déplacer un
  #      script coupait la bascule, le failover et les alertes sur les deux nœuds
  #      dans les cinq minutes suivant la fusion — sans rien signaler, puisque le
  #      producteur d'alertes fait partie de ce qui ne démarre plus.
  #
  #      C'est le seul contrôle qui compare les nœuds au DÉPÔT. `check-reliability`
  #      C18 les compare entre eux, ce qui laisse passer la dérive commune.
  PE=$(bash "$RACINE_DEPOT/scripts/poste/verifier-points-entree.sh" 2>&1)
  case "$?" in
    0) V17=OK;      D17="cron et systemd conformes sur les 2 nœuds" ;;
    2) V17=INCONNU; D17="au moins un point non lisible (sudo refusé ? hôte injoignable ?)" ;;
    *) V17=FAIL;    D17=$(printf '%s' "$PE" | grep -m1 -E '^\s+(cron|hostachy)' | sed 's/^ *//') ;;
  esac
  rapporter 17 "$V17" "Points d'entrée conformes au dépôt" "$D17"

  # ── 18 — les IMAGES du standby sont-elles bâties sur SON code ? (#511) ───────
  #  Le point 10 compare deux HEAD git. Il rend OK sur un standby dont le
  #  `docker compose build` a échoué : son CODE est à jour, ses IMAGES ne le sont
  #  pas — et ce sont elles qu'un failover démarre. C'est le seul état du système
  #  où tous les contrôles sont verts et où la bascule sert une version antérieure.
  STANDBY_H=$([ "$ACTIF" = "$RPI1" ] && echo "$RPI2" || echo "$RPI1")
  H18=$(sur "$STANDBY_H" 'git -C /opt/5hostachy rev-parse --short HEAD')
  I18=$(sur "$STANDBY_H" "tr -d ' \t\r\n' < /opt/5hostachy/.images-construites 2>/dev/null")
  rapporter 18 "$(verdict_images_standby "$H18" "$I18")" "Images du standby bâties sur son code"           "code=${H18:-?} images=${I18:-absent} (marqueur posé par auto-deploy après un build RÉUSSI)"

  echo
  echo "───────────────────────────────────────────────────────────────"
  printf "OK=%d  ÉCART=%d  INCONNU=%d  ÉCHEC=%d\n" "$NB_OK" "$NB_ECART" "$NB_INCONNU" "$NB_FAIL"

  if [ "$NB_FAIL" -gt 0 ]; then
    echo "✗ MEP NON AUTORISÉE — diagnostiquer les échecs, corriger, relancer."
    exit 1
  fi
  if [ "$NB_INCONNU" -gt 1 ]; then
    echo "? Trop de points non mesurables : un INCONNU n'est pas un vert (socle 04 §1)."
    exit 2
  fi

  #  Le marqueur porte le commit couvert : le hook refusera un push d'autre chose.
  mkdir -p "$(dirname "$MARQUEUR")"
  printf '%s %s\n' "$(git rev-parse HEAD)" "$(date +%s)" > "$MARQUEUR"
  echo "✓ Pré-check passé pour $(git rev-parse --short HEAD) — push autorisé."
  #  Le message nommait le point 9 en dur : n'importe quel INCONNU était donc
  #  présenté comme normal et attribué à une limite connue. Constaté le 14/08/2026,
  #  le point 9 étant OK et le 16 (CI rejouée) INCONNU : le script disait le
  #  contraire de ce qu'il avait mesuré. Un contrôle qui ne sait pas dire CE QU'IL
  #  n'a pas mesuré fabrique la confiance qu'il devrait retirer (socle 04 §1).
  [ "$NB_INCONNU" -gt 0 ] && echo "  (non mesuré : point(s) $POINTS_INCONNUS — un INCONNU n'est pas un vert.)"
  exit 0
}
