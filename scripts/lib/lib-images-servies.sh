#!/usr/bin/env bash
# =============================================================================
#  lib-images-servies.sh — les IMAGES qu'un nœud sert sont-elles celles de son
#  code ? Décisions PURES des points 12 et 18 du pré-check MEP, et le relevé
#  du point 12 (un texte à exécuter sur l'actif, éprouvé sur un docker simulé).
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

# ── Point 12 : le CONTENU servi, pas deux dates (#1675) ──────────────────────
#
#  🔴 Le point comparait la date de création de chaque conteneur à celle du
#  dernier commit de son service. Il jugeait l'ARTEFACT (standards/04) :
#    • faux rouge — le 04/10/2026, `FROM caddy:2` → `caddy:2.11` (même digest)
#      a été bâti depuis le cache : même contenu, Compose ne recrée pas Caddy,
#      et le point a rendu FAIL jusqu'à bloquer la MEP suivante ;
#    • faux vert possible — un conteneur recréé APRÈS le commit sur une image
#      bâtie AVANT (build échoué) passait.
#
#  Ce qu'on a mesuré sur rpi1 le 04/10/2026 (Docker 29.8, Compose v5.6.0,
#  magasin d'images containerd) : l'ID d'une image (`docker image inspect … .Id`)
#  est le digest de son INDEX OCI, qui porte le manifeste de l'image ET une
#  attestation de provenance horodatée par BuildKit. Chaque build change donc
#  l'index — même servi entièrement par le cache —, jamais le manifeste. Compose
#  compare le MANIFESTE (étiquette `com.docker.compose.image`), et il a raison :
#  caddy et whatsapp « Running » sur un autre index tournaient sur le manifeste
#  de l'image étiquetée. Ni non-convergence de Compose, ni build non
#  déterministe : un identifiant qui change sans que le contenu change.
#
#  Le point pose donc DEUX questions, chacune sur un fait :
#    1. les images étiquetées sont-elles bâties sur un code qui CONTIENT le
#       dernier commit du service ? — `inclus`, lu au marqueur
#       `.images-construites` qu'auto-deploy écrit après un build RÉUSSI ;
#    2. le conteneur tourne-t-il sur le MANIFESTE de l'image étiquetée ? — le
#       manifeste que le démon a retenu à la création du conteneur
#       (`ImageManifestDescriptor`), face à celui de l'image pour sa plateforme.
#
#  Relevé à exécuter SUR L'ACTIF (`sur "$ACTIF" "$(collecte_images_servies)"`).
#  Une ligne par service : « service inclus manifeste_conteneur
#  manifeste_étiqueté commit_du_service marqueur » ; « - » pour une mesure
#  absente — la position de chaque champ ne bouge jamais.
#  Aucun accès à la base, aucun argument de processus : `docker inspect` et git.
collecte_images_servies() {  # $1 = racine du dépôt (défaut /opt/5hostachy)
  printf '%s' '
cd '"${1:-/opt/5hostachy}"' 2>/dev/null || exit 0
_mk=$(tr -d " \t\r\n" < .images-construites 2>/dev/null)
for _p in hostachy_api:api:api hostachy_front:front:front hostachy_whatsapp:whatsapp-bridge:whatsapp-bridge hostachy_caddy:caddy:Dockerfile.caddy; do
_c=${_p%%:*}; _r=${_p#*:}; _s=${_r%%:*}; _d=${_r#*:}
_cm=$(docker inspect "$_c" --format "{{if .ImageManifestDescriptor}}{{.ImageManifestDescriptor.Digest}}{{else}}{{.Image}}{{end}}" 2>/dev/null)
_pl=$(docker inspect "$_c" --format "{{with .ImageManifestDescriptor}}{{with .Platform}}{{.OS}}/{{.Architecture}}{{end}}{{end}}" 2>/dev/null)
_ci=$(docker inspect "$_c" --format "{{.Config.Image}}" 2>/dev/null)
_em=""; [ -n "$_ci" ] && _em=$(docker image inspect ${_pl:+--platform "$_pl"} "$_ci" --format "{{.Id}}" 2>/dev/null)
_sc=$(git log -1 --format=%h -- "$_d" 2>/dev/null)
_in=""
if [ -n "$_sc" ] && [ -n "$_mk" ]; then
git merge-base --is-ancestor "$_sc" "$_mk" 2>/dev/null
case $? in 0) _in=oui ;; 1) _in=non ;; esac
fi
echo "$_s ${_in:--} ${_cm:--} ${_em:--} ${_sc:--} ${_mk:--}"
done
'
}

#  PURE. $1 = inclus (oui | non | - ), $2 = manifeste du conteneur, $3 =
#  manifeste de l'image étiquetée → OK | PERIMEE | NON_RECREE | INCONNU.
#    PERIMEE    les images ne contiennent pas le commit du service : recréer
#               ne suffirait pas, c'est le BUILD qui manque — il prime ;
#    NON_RECREE le conteneur tourne sur un autre contenu que l'image étiquetée.
#               Compose l'aurait recréé (il compare ce même manifeste) : un
#               `up -d` n'a pas eu lieu ou a été interrompu, et rien ne le
#               rattrape seul — auto-deploy ne relance `up -d` que sur un
#               commit nouveau ;
#    INCONNU    une mesure manque et aucun écart n'a été mesuré — jamais OK.
#  Un écart MESURÉ se dit même quand l'autre mesure manque.
verdict_image_service() {
  local in=${1:--} c=${2:--} e=${3:--}
  [ "$in" = non ] && { echo PERIMEE; return; }
  [ "$c" != - ] && [ "$e" != - ] && [ "$c" != "$e" ] && { echo NON_RECREE; return; }
  [ "$in" = oui ] && [ "$c" != - ] && [ "$e" != - ] && { echo OK; return; }
  echo INCONNU
}
