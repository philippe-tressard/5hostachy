#!/usr/bin/env bash
# =============================================================================
#  lib-images-servies.sh — les IMAGES qu'un nœud sert sont-elles celles de son
#  code ? Décisions PURES des points 12 et 18 du pré-check MEP.
#
#  Module IMPORTÉ, jamais exécuté par un cron : pas de bit x, versionné en 100644.
#  Il a besoin de `verdict_parite_servie` (`lib-parite.sh`), sourcé avant lui
#  par `lib-verdicts-mep.sh`.
#
#  Extrait de `lib-verdicts-mep.sh` le 04/10/2026, au fil de l'eau : ce fichier
#  était à 500 lignes, et le point 12 avait besoin de sa propre décision.
# =============================================================================

verdict_images_standby() { # $1 = HEAD du standby, $2 = son .images-construites
  #  🔴 La parité de CODE n'est pas la parité d'IMAGES (#511). `verdict_parite`
  #  compare deux `git rev-parse` : il rend OK sur un standby dont le
  #  `docker compose build` a échoué, parce que son code EST à jour. Ce sont ses
  #  images qui ne le sont pas, et ce sont elles qu'un failover démarre.
  #
  #  ⚠️ C'est le seul état du système où tous les contrôles sont verts et où la
  #  bascule sert quand même une version antérieure. Il est resté invisible parce
  #  qu'aucun contrôle ne regardait autre chose que git.
  #
  #  FAIL et non ECART : un écart de code se rattrape seul en moins de cinq
  #  minutes (auto-deploy, #448) ; des images périmées ne se rattrapent PAS —
  #  auto-deploy ne relance le build que si le commit change.
  case "$(verdict_parite_servie "$1" "$2")" in
    a-jour)          echo OK ;;
    images-perimees) echo FAIL ;;
    *)               echo INCONNU ;;
  esac
}

verdict_image_service() {  # $1 = création du conteneur, $2 = dernier commit de SON répertoire
  #  🔴 Le point 12 comparait le conteneur de l'API au DERNIER commit du dépôt,
  #  quel qu'il soit (04/10/2026). Une MEP qui ne touche que le front ne
  #  reconstruit pas l'API — `docker compose up -d` ne recrée que ce qui a
  #  changé — et le point rendait FAIL sur une production parfaitement servie :
  #  deux MEP de suite l'ont rencontré le même jour (#1658, v2.102.1). Un faux
  #  rouge qui revient à chaque lot front pousse vers `SKIP_PRECHECK=1`, qui
  #  désarme TOUS les points (socle 04 §25).
  #
  #  La question juste est celle du service : son conteneur a-t-il été créé
  #  APRÈS le dernier commit qui touche ce dont son image est faite ?
  #  Un répertoire qu'aucun commit ne touche (chemin faux) ne prouve rien.
  [ -z "$1" ] || [ -z "$2" ] && { echo INCONNU; return; }
  local cree commit
  cree=$(date -d "$1" +%s 2>/dev/null) || { echo INCONNU; return; }
  commit=$(date -d "$2" +%s 2>/dev/null) || { echo INCONNU; return; }
  [ "$cree" -ge "$commit" ] && echo OK || echo FAIL
}
