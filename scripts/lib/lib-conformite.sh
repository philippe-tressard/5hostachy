#!/usr/bin/env bash
# =============================================================================
#  lib-conformite.sh — les contrôles de CONFORMITÉ de `check-reliability.sh`
#                      (C20 à C23)
#
#  Extrait le 20/08/2026, au fil de l'eau : `check-reliability.sh` a dépassé son
#  plafond en recevant C23 (les en-têtes de sécurité réellement servis), et le
#  garde-fou de modularité l'a refusé.
#
#  La coupe suit la NATURE des contrôles, pas leur numéro. Ceux-ci partagent une
#  question : *le nœud est-il conforme à ce qu'on croit qu'il est ?*
#
#    C20  les permissions élevées sont-elles les mêmes sur les deux nœuds ?
#    C21  une permission élevée vaut-elle mieux que la cible qu'elle désigne ?
#    C22  les points d'entrée du nœud sont-ils ceux du dépôt ?
#    C23  les en-têtes de sécurité sont-ils réellement servis ?
#
#  Les contrôles restés dans `check-reliability.sh` posent l'autre question :
#  *le service fonctionne-t-il ?* — la base, le rôle actif, le tunnel, la
#  maintenance. Deux raisons de changer, deux fichiers.
#
#  ⚠️ Ce module n'est PAS autonome. Il emploie `ok`, `warn`, `$SELF`, `$REPO` et
#  les `verdict_*` définis par son appelant : il est sourcé APRÈS eux, et appelé
#  par `conformite_verdicts`. Le sourcer seul ne produirait rien — et surtout
#  aucune erreur, ce pourquoi il ne s'exécute pas au chargement.
# =============================================================================

conformite_verdicts() {
  # ── C20. Les permissions élevées sont-elles les MÊMES sur les 2 nœuds ? ───────
  # Jumeau de C18, né du même défaut : une divergence que personne ne pouvait voir,
  # chaque nœud ayant l'air normal vu de lui-même. C18 a rendu vraie la phrase
  # « cron root identique sur les 2 nœuds » ; celui-ci fait le même travail pour
  # les règles `sudo`, posées à la main nœud par nœud — donc divergentes par
  # construction, ce qu'a établi #302.
  #
  # La divergence n'est pas un détail d'hygiène : c'est elle qui a fait échouer la
  # copie hors site UNE NUIT SUR DEUX (09/08/2026), la permission n'existant que
  # sur le nœud actif un jour sur deux. Un nœud plus permissif que l'autre, c'est
  # aussi une surface d'attaque qui dépend du jour de la semaine.
  #
  # WARN et non FAIL : cela ne coupe pas la production, et un FAIL à */15 enverrait
  # un mail par heure jusqu'à correction — c'est-à-dire une alerte qu'on apprend à
  # ignorer, le défaut exact qu'on a retiré de C16 le 06/08.
  if [ "$PEER_OK" -eq 0 ]; then
    case "$(sudo_parite "${S_sudofiles:-}" "${P_sudofiles:-}")" in
      OK)         ok "Permissions élevées identiques sur les 2 nœuds" ;;
      DIVERGENCE) warn "Permissions élevées DIVERGENTES entre $SELF et $PEER — écarts : $(sudo_ecarts "${S_sudofiles:-}" "${P_sudofiles:-}") ; une règle posée d'un seul côté ne vaut qu'un jour sur deux, et rend un nœud plus permissif que l'autre (#302)" ;;
      *)          warn "Permissions élevées INCONNUES ($SELF='${S_sudofiles:-vide}' $PEER='${P_sudofiles:-vide}') — comparaison impossible, ni vert ni rouge" ;;
    esac
  fi

  # ── C21. Une permission élevée vaut-elle mieux que sa cible ? ─────────────────
  # `standards/03-securite.md` §8 bis : une permission élevée ne vaut que ce que
  # vaut la cible qu'elle désigne. Une règle qui a l'air bornée à un script précis
  # ne borne rien si le compte appelant peut réécrire ce script — la permission
  # porte sur un CHEMIN, pas sur le code qu'il contiendra à l'exécution.
  #
  # Analyse locale (root). Sur le peer le champ est vide et vaut INCONNU : c'est
  # assumé, puisque le contrôle tourne des deux côtés et que chaque nœud examine
  # donc les siennes. Ne jamais rabattre ce vide sur OK — ce serait le nœud le
  # moins surveillé qui rassurerait le plus.
  case "$(verdict_sudo_risque "${S_sudorisk:-}")" in
    OK)     ok "Permissions élevées de $SELF : aucune cible réinscriptible par son appelant" ;;
    RISQUE) warn "Permissions élevées de $SELF : cible(s) réinscriptible(s) par l'appelant ou règle sans borne →${S_sudorisk#ok:} — qui obtient ce compte obtient root (#302)" ;;
    *)      warn "Permissions élevées de $SELF : non mesurables (exige root) — ni vert ni rouge" ;;
  esac

  # ── C22. Les points d'entrée de CE nœud sont-ils conformes au DÉPÔT ? ─────────
  # C18 compare les deux nœuds ENTRE EUX : deux crontabs identiquement périmés lui
  # paraissent parfaits. Ici on compare au dépôt, et en continu (#352). Le pourquoi
  # détaillé, la priorité ECART > INCONNU et le choix du WARN : lib-points-entree.sh.
  PE=$(points_entree_verdicts_locaux "$REPO" | agreger_points_entree)
  case "${PE%%|*}" in
    OK)      ok   "Points d'entrée de $SELF conformes au dépôt (crons root et ptressard, unité role-guard)" ;;
    ECART)   warn "Points d'entrée de $SELF NON conformes au dépôt : ${PE#*|} — le nœud ne lance pas ce que infra/points-entree/ décrit" ;;
    *)       warn "Points d'entrée de $SELF non lisibles : ${PE#*|} — ni vert ni rouge (sudo -n refusé, ou nœud non provisionné)" ;;
  esac

  # ── C23. Les en-têtes de sécurité sont-ils RÉELLEMENT servis ? ────────────────
  # 🔴 Un contrôle des en-têtes existait — dans `check-stack.sh`, RETIRÉ du cron de
  # rpi2 le 06/08/2026 parce qu'il y échouait 144 fois par jour. Il échouait parce
  # qu'il attendait `X-Frame-Options: SAMEORIGIN` là où le Caddyfile dit `DENY`.
  #
  # Le seul contrôle des en-têtes portait donc une attente FAUSSE, il criait, on
  # l'a fait taire — et depuis, plus rien ne regarde. Un en-tête de sécurité peut
  # disparaître d'un Caddyfile sans que personne ne le sache.
  #
  # ⚠️ Celui-ci lit ce qui est SERVI, pas ce que le fichier déclare : c'est la
  # différence entre vérifier le fait et vérifier son intention. Et il ne regarde
  # que la PRÉSENCE — une attente de valeur se périme au premier ajustement, et
  # c'est exactement ce qui a tué le précédent.
  #
  # WARN et non FAIL : un en-tête manquant n'interrompt pas le service, il retire
  # une protection. Le distinguer d'une panne évite de noyer les FAIL.
  ENTETES_ATTENDUS="X-Content-Type-Options X-Frame-Options Referrer-Policy Strict-Transport-Security Content-Security-Policy"
  ENTETES_RECUS=$(curl -sI --max-time 8 http://localhost/ 2>/dev/null)
  case "$(verdict_entetes_securite "$ENTETES_RECUS" "$ENTETES_ATTENDUS")" in
    OK)          ok   "En-têtes de sécurité servis (${ENTETES_ATTENDUS// /, })" ;;
    MANQUANT:*)  V23=$(verdict_entetes_securite "$ENTETES_RECUS" "$ENTETES_ATTENDUS")
                 warn "En-tête(s) de sécurité ABSENT(S) de la réponse : ${V23#MANQUANT:} — la protection correspondante ne s'applique plus, et le Caddyfile peut dire le contraire" ;;
    *)           warn "En-têtes de sécurité non mesurables (aucune réponse locale) — ni vert ni rouge" ;;
  esac
}
