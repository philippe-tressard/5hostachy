#!/usr/bin/env bash
#  Point 19 du pré-check — les liens que les E-MAILS envoient répondent-ils ?
#
#  🔴 POURQUOI (11/09/2026, signalé à l'écran) : un e-mail de ticket adressé au
#  syndic portait `https://5hostachy.fr//tickets/34` — double barre, **404**.
#  La valeur de `site_url` en base se terminait par « / », et tous les modèles
#  écrivent `{{ app.url }}/tickets/…`.
#
#  ⚠️ Aucun test de CI ne pouvait l'attraper, et c'est tout l'objet de ce point :
#  la CI vérifie le CODE, elle ne connaît pas la valeur que la production a en
#  base. Les deux moitiés du défaut — un modèle correct, une donnée sale — ne se
#  rencontrent qu'au moment de l'envoi. C'est `standards/04` §10 : deux sondes
#  indépendantes, et celle-ci mesure le RÉEL.
#
#  Ce que le point fait :
#    1. lit `site_url` tel que la PRODUCTION le sert (`GET /api/config`, public) ;
#    2. compose les liens exactement comme les modèles d'e-mail les composent ;
#    3. demande chaque URL et refuse un 404.
#
#  Un 302 vers la connexion est un SUCCÈS : la page existe, elle est simplement
#  derrière une session. Ce qu'on cherche est la route qui n'existe pas.

#: Les chemins littéraux écrits dans les modèles (`app/seed/emails/*.py`), sous
#: la forme exacte qu'ils y prennent : `{{ app.url }}` + ce qui suit.
#:
#: ⚠️ Les identifiants sont des exemples — ce qui est mesuré est la ROUTE, pas
#: l'existence de l'élément. Un ticket inexistant rend la page, pas un 404 de
#: routage : c'est le front qui affiche « introuvable ».
CHEMINS_COURRIEL=(
  "/tickets/1"
  "/actualites"
  "/calendrier"
  "/admin"
)

#  Rend le code HTTP, ou « ? » si l'appel n'aboutit pas. Jamais vide : une sortie
#  vide se lit comme un succès (`standards/04` §1).
code_http() {
  curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$1" 2>/dev/null || echo '?'
}

#  Le verdict, isolé pour être testable sans réseau (`--selftest`).
#  $1 = site_url servi par la production · $2… = les codes relevés, "chemin=code"
verdict_liens_courriel() {
  local base="$1"; shift
  [ -z "$base" ] && { echo INCONNU; return; }
  #  🔴 Le cas zéro (`standards/04` §2) : sans relevé, il n'y a rien de mesuré.
  #  Rendre OK ici ferait d'une extraction cassée un feu vert — et c'est
  #  l'auto-test ci-dessous qui me l'a rappelé, en refusant ma première écriture.
  [ "$#" -eq 0 ] && { echo INCONNU; return; }
  local paire code
  for paire in "$@"; do
    code="${paire##*=}"
    case "$code" in
      404) echo FAIL; return ;;
      '?'|000|'') echo INCONNU; return ;;
    esac
  done
  #  ⚠️ ÉCART, pas FAIL, et la nuance compte. Le produit normalise l'adresse à la
  #  lecture (`utils/liens.base_site`, même lot) : une barre finale en base ne
  #  casse plus le lien, donc bloquer une MEP dessus serait un faux rouge. Elle
  #  reste une donnée sale, et le prochain lecteur qui oubliera la normalisation
  #  repartira de là — c'est exactement ce qui s'est passé onze fois. On le DIT.
  case "$base" in */) echo ECART; return ;; esac
  echo OK
}

precheck_point_liens() {
  local base releves="" chemin url code detail
  base=$(curl -s --max-time 10 "$SITE/api/config" 2>/dev/null \
         | python -c "import json,sys; print((json.load(sys.stdin).get('site_url') or '').strip())" 2>/dev/null)

  for chemin in "${CHEMINS_COURRIEL[@]}"; do
    #  La concaténation est celle des modèles, à l'octet près : c'est elle qu'on
    #  éprouve, pas une version nettoyée au passage.
    #  Normalisée comme le produit le fait — sinon on mesurerait une URL que
    #  personne n'envoie, et un 404 inventé bloquerait la MEP.
    url="${base%/}${chemin}"
    code=$(code_http "$url")
    releves="$releves $chemin=$code"
  done

  # shellcheck disable=SC2086
  local v; v=$(verdict_liens_courriel "$base" $releves)
  detail="site_url=${base:-?} —$releves"
  case "$v" in
    ECART)   detail="site_url=« $base » se termine par « / » — sans effet (le produit normalise), mais à nettoyer en administration" ;;
    INCONNU) detail="$detail (site injoignable, ou site_url absent de la configuration publique)" ;;
  esac
  rapporter 19 "$v" "Liens des courriels servis par la production" "$detail"
}

#  ── Auto-test : la décision se vérifie sans réseau ─────────────────────────
if [ "${1:-}" = "--selftest" ]; then
  echecs=0
  attendu() {
    local att="$1"; shift
    local obtenu; obtenu=$(verdict_liens_courriel "$@")
    if [ "$obtenu" != "$att" ]; then
      echo "✗ attendu $att, obtenu $obtenu  (args: $*)"; echecs=$((echecs + 1))
    fi
  }
  #  Le défaut du 11/09/2026 : la barre finale se DIT, sans bloquer — le produit
  #  la neutralise désormais à la lecture.
  attendu ECART   'https://5hostachy.fr/' '/tickets/1=200'
  #  ⚠️ Mais un 404 l'emporte sur l'écart : c'est le fait, l'autre est un indice.
  attendu FAIL    'https://5hostachy.fr/' '/tickets/1=404'
  attendu OK      'https://5hostachy.fr'  '/tickets/1=200' '/actualites=200'
  #  Une route qui n'existe pas — le défaut de juillet 2026 (`/documents`).
  attendu FAIL    'https://5hostachy.fr'  '/tickets/1=200' '/documents=404'
  #  Derrière une session : la page EXISTE, ce n'est pas ce qu'on cherche.
  attendu OK      'https://5hostachy.fr'  '/tickets/1=302'
  #  Injoignable ou configuration absente → INCONNU, jamais OK.
  attendu INCONNU ''                      '/tickets/1=200'
  attendu INCONNU 'https://5hostachy.fr'  '/tickets/1=?'
  attendu INCONNU 'https://5hostachy.fr'  '/tickets/1=000'
  #  ⚠️ Le cas zéro : aucun relevé ne doit PAS rendre OK — il n'y aurait rien
  #  de mesuré (`standards/04` §2).
  attendu INCONNU 'https://5hostachy.fr'
  if [ "$echecs" -eq 0 ]; then
    echo "✓ verdict_liens_courriel : barre finale, 404, session, injoignable et cas zéro."
    exit 0
  fi
  exit 1
fi
