#!/bin/bash
# =============================================================================
#  lib-ci-replay.sh — Extraction PURE des étapes de `.github/workflows/ci.yml`
#
#  Module SOURCÉ, jamais exécuté : pas de bit x (le job CI « Bits d'exécution
#  versionnés » attend 100644 sur les `lib-*.sh`).
#
#  POURQUOI. Le 12/08/2026 la CI est passée rouge sur `Lint Python (Ruff)` alors
#  que pytest, svelte-check, le build, les six lints du front et les self-tests
#  des scripts avaient tous été rejoués : **le seul job non lancé est le seul qui
#  a échoué** (#319). La consigne de tout rejouer existe — skill `avant-commit`
#  §7 — et elle n'a pas suffi. Une consigne ne se maintient pas seule.
#
#  RÈGLE DE CONCEPTION, celle qui décide de l'utilité du contrôle : les commandes
#  sont EXTRAITES de `ci.yml`, jamais recopiées. Une seconde liste divergerait au
#  premier job ajouté, et c'est précisément le job ajouté qu'on oublie de rejouer.
#
#  Les fonctions d'ici sont pures : texte en entrée, texte en sortie. Aucun SSH,
#  docker, écriture ni sudo. L'exécution vit dans `rejouer-ci.sh`.
#
#  PROTOCOLE DE SORTIE de `ci_extraire` — lignes de commande rendues BRUTES, sans
#  échappement (un `\xef` ou un `\` de continuation ne survivrait à aucun aller-
#  retour d'échappement) :
#
#      @@STEP<TAB>job<TAB>nom du job<TAB>nom de l'étape<TAB>genre<TAB>rép<TAB>uses<TAB>with
#      @@ENV<TAB>CLE: valeur                        (0..n)
#      @@RUN
#      …lignes de commande, telles quelles…
#      @@END
#
#  Le préfixe `@@` est le seul point de fragilité : une ligne de commande qui
#  commencerait par `@@` casserait le protocole. Le parseur la signale par
#  `@@ERREUR`, et l'appelant refuse alors de conclure — jamais un vert.
# =============================================================================

# ── Extraction ───────────────────────────────────────────────────────────────
#  Le parseur ne prétend PAS lire YAML : il lit la forme que ce fichier-ci a, et
#  il est strict dessus. Toute étape qu'il ne sait pas reconnaître est perdue —
#  d'où le contrôle de parité de `ci_parite`, qui compare ce qu'il a extrait au
#  nombre de `run:` réellement présents. Un parseur silencieusement partiel
#  rendrait un vert sur ce qu'il n'a pas regardé (socle 04 §1).
ci_extraire() {            # ci.yml sur stdin → protocole sur stdout
  awk '
    function trim(s) { sub(/^[[:space:]]+/,"",s); sub(/[[:space:]]+$/,"",s); return s }
    #  Aucun champ vide dans la sortie : `read` avec IFS=tabulation FUSIONNE les
    #  séparateurs consécutifs (la tabulation est un blanc), si bien qu’un
    #  `working-directory` absent décalerait toutes les colonnes suivantes — le
    #  corps d’une étape serait exécuté depuis le mauvais répertoire.
    function nz(s) { return s == "" ? "-" : s }
    function reset(   ) {
      stepname=""; uses=""; workdir=""; withs=""; hasrun=0
      split("", body); nb=0; split("", envs); ne=0; have=0
    }
    function flush(   i, kind) {
      if (!have) { reset(); return }
      kind = hasrun ? "run" : (uses != "" ? "uses" : "")
      if (kind == "") { reset(); return }
      printf "@@STEP\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n", nz(jobid), nz(jobname), nz(stepname), kind, nz(workdir), nz(uses), nz(withs)
      for (i = 0; i < ne; i++) printf "@@ENV\t%s\n", envs[i]
      if (hasrun) {
        print "@@RUN"
        for (i = 0; i < nb; i++) {
          if (body[i] ~ /^@@/) print "@@ERREUR\tligne de commande commençant par @@ : " stepname
          print body[i]
        }
        print "@@END"
      }
      reset()
    }
    BEGIN { injobs=0; insteps=0; inrun=0; inenv=0; inwith=0; runind=-1; reset() }
    {
      match($0, /^ */); ind = RLENGTH; txt = substr($0, ind + 1)

      if (!injobs) { if ($0 ~ /^jobs:/) injobs = 1; next }

      if (inrun) {
        if ($0 ~ /^[[:space:]]*$/) { body[nb++] = ""; next }
        if (ind > 8) {
          if (runind < 0) runind = ind
          body[nb++] = substr($0, (ind >= runind ? runind : ind) + 1)
          next
        }
        inrun = 0
      }

      if (ind == 2 && txt ~ /^[A-Za-z0-9_-]+:[[:space:]]*$/) {
        flush(); jobid = txt; sub(/:.*$/, "", jobid)
        jobname = ""; insteps = 0; inenv = 0; inwith = 0; next
      }
      if (ind == 4) {
        inenv = 0; inwith = 0
        if (txt ~ /^name:/)  { jobname = trim(substr(txt, 6)); next }
        if (txt ~ /^steps:/) { insteps = 1 }
        next
      }
      if (insteps && ind == 6 && txt ~ /^- /) { flush(); have = 1; txt = substr(txt, 3); ind = 8 }

      if (insteps && ind == 8) {
        if (txt ~ /^#/) next
        inenv = 0; inwith = 0
        if (txt ~ /^name:/)              { stepname = trim(substr(txt, 6)); next }
        if (txt ~ /^uses:/)              { uses     = trim(substr(txt, 6)); next }
        if (txt ~ /^working-directory:/) { workdir  = trim(substr(txt, 19)); next }
        if (txt ~ /^env:/)               { inenv = 1; next }
        if (txt ~ /^with:/)              { inwith = 1; next }
        if (txt ~ /^run:/) {
          hasrun = 1
          rest = trim(substr(txt, 5))
          if (rest == "|" || rest == "|-") { inrun = 1; runind = -1 }
          else if (rest != "")             { body[nb++] = rest }
          next
        }
        next
      }
      if (ind == 10) {
        if (inenv  && txt ~ /^[A-Za-z_]/) { envs[ne++] = txt; next }
        #  Le commentaire YAML de fin de ligne est retiré : sans cela la version
        #  épinglée devient « 3.12  # aligné sur… », ce qui noie le seul chiffre
        #  que ce champ existe pour comparer à celui du poste.
        #  ⚠️ APOSTROPHES TYPOGRAPHIQUES obligatoires dans ce bloc awk : il est
        #  entre quotes simples, et une apostrophe droite le terminerait.
        if (inwith && txt ~ /^[a-z]/)     { sub(/[[:space:]]+#.*$/, "", txt)
                                            withs = withs (withs == "" ? "" : " ") txt; next }
      }
    }
    END { flush() }
  '
}

# ── Parité : ce qui a été extrait couvre-t-il ce qui est écrit ? ──────────────
#  Cas zéro de `standards/04-fiabilite-des-controles.md` §2 : « 0 étape extraite »
#  n'est pas « rien à rejouer », c'est « le parseur n'a rien compris ». L'appelant
#  doit refuser de conclure, pas afficher OK.
ci_parite() {              # $1 = fichier ci.yml → "<écrit> <extrait>"
  local ecrit extrait
  ecrit=$(grep -cE '^[[:space:]]+run:' "$1")
  extrait=$(ci_extraire < "$1" | grep -c '^@@RUN$')
  printf '%s %s\n' "$ecrit" "$extrait"
}

# ── Substitution des expressions GitHub ──────────────────────────────────────
#  Table VOLONTAIREMENT close : tout ce qui n'y figure pas laisse un `${{` dans
#  le corps, et `ci_classer` rend alors INCONNU. Deviner la valeur d'une
#  expression inconnue reviendrait à rejouer autre chose que la CI en croyant
#  l'avoir rejouée.
ci_substituer() {          # $1 = sha local ; corps sur stdin
  sed -e "s/\${{ *github\.base_ref *|| *'main' *}}/main/g" \
      -e "s/\${{ *github\.base_ref *}}/main/g" \
      -e "s/\${{ *github\.sha *}}/$1/g"
}

# ── Classement d'un corps de commandes ───────────────────────────────────────
#  Trois genres, et le troisième est le seul qui compte vraiment :
#    PREPARATION — installation de dépendances : ce n'est pas un contrôle, et
#                  l'exécuter écraserait l'environnement du poste. AFFICHÉ, donc
#                  jamais escamoté ;
#    INCONNU     — expression GitHub non résolue : non rejouable ici ;
#    CONTROLE    — tout le reste, à exécuter.
ci_classer() {             # corps sur stdin → "PREPARATION" | "INCONNU <motif>" | "CONTROLE"
  local joint
  #  Les continuations `\` sont recollées AVANT le classement : sans cela la
  #  seconde ligne d'un `apt-get install … \` ne ressemble plus à une
  #  installation, et l'étape entière serait exécutée sur le poste.
  joint=$(sed -e :a -e '/\\$/N; s/\\\n//; ta')
  case "$joint" in *'${{'*) echo "INCONNU expression GitHub non résolue"; return ;; esac
  local ligne reste=0
  while IFS= read -r ligne; do
    ligne=$(printf '%s' "$ligne" | sed 's/^[[:space:]]*//')
    [ -z "$ligne" ] && continue
    case "$ligne" in
      '#'*) continue ;;
      'sudo apt-get '*|'apt-get '*|'pip install '*|'pip3 install '*|'npm install'*|'npm ci'*) ;;
      *) reste=1 ;;
    esac
  done <<EOF
$joint
EOF
  [ "$reste" -eq 0 ] && echo PREPARATION || echo CONTROLE
}

# ── Requalification d'un échec ───────────────────────────────────────────────
#  Un outil absent du poste n'est PAS un échec du lot : c'est une mesure qu'on
#  n'a pas pu prendre. La confondre avec un échec ferait bloquer un push correct,
#  et un contrôle qui crie au loup finit contourné (socle 04 §18).
ci_requalifier() {         # $1 = code de sortie, sortie de l'étape sur stdin
  local sortie; sortie=$(cat)
  if [ "$1" -eq 0 ]; then echo OK; return; fi
  case "$sortie" in
    *"command not found"*|*"not recognized"*|*": No such file or directory"*"sh:"*)
      echo "INCONNU outil absent du poste" ;;
    #  🔴 UN CONTRÔLE QUI SE DÉCLARE NON MESURÉ (04/09/2026).
    #
    #  `lint:audit` sort en code 2 et écrit « INCONNU — `npm audit` a renvoyé une
    #  erreur » quand le registre npm ne répond pas. Ce n'est ni un succès ni un
    #  échec DU LOT : c'est une mesure qu'on n'a pas pu prendre, et le contrôle
    #  le dit lui-même, exactement comme `standards/04` le demande.
    #
    #  Le compter FAIL bloquait le push d'un lot sain — quatre fois dans la
    #  matinée du 04/09 — et poussait vers `SKIP_PRECHECK=1`, c'est-à-dire à
    #  désarmer soixante-dix étapes pour en contourner une. C'est le défaut que
    #  #318 avait déjà corrigé sur le point 0c, reproduit un cran plus bas.
    #
    #  ⚠️ Le motif est étroit : le mot doit venir du contrôle LUI-MÊME, en tête
    #  de sa ligne de verdict. Un contrôle qui échoue vraiment n'écrit pas
    #  « INCONNU » — et s'il le faisait, ce serait son défaut, pas celui d'ici.
    *"INCONNU —"*|*"INCONNU -"*)
      echo "INCONNU le contrôle se déclare non mesuré" ;;
    *) echo FAIL ;;
  esac
}

# ── Self-test ────────────────────────────────────────────────────────────────
ci_replay_selftest() {
  local st=0 got
  t() { [ "$2" = "$3" ] && echo "PASS  $1" || { echo "FAIL  $1  attendu=[$3] obtenu=[$2]"; st=1; }; }

  #  Un gabarit réduit, mais qui porte les cinq formes réellement présentes dans
  #  ci.yml : `uses` seul, bloc `run: |`, `run:` sur une ligne, `working-directory`
  #  et `env`. Le vrai fichier n'est pas utilisé ici : un self-test qui change de
  #  résultat quand la CI évolue ne dit plus rien de la fonction qu'il éprouve.
  local sortie
  sortie=$(ci_extraire <<'YAML'
name: CI
env:
  GLOBAL: 'ignoré'
jobs:
  # un commentaire de job
  lint:
    name: Lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-python@v7
        with:
          python-version: '3.11'
      # un commentaire d'étape
      - name: Ruff
        run: |
          ruff check api/app/
          ruff check api/alembic/
  test:
    name: Tests
    steps:
      - name: Pytest
        working-directory: api
        run: pytest tests/ -q
        env:
          SECRET_KEY: "x"
YAML
)
  t "2 jobs, 3 étapes extraites"  "$(printf '%s' "$sortie" | grep -c '^@@STEP')" "3"
  t "2 corps de commandes"        "$(printf '%s' "$sortie" | grep -c '^@@RUN$')" "2"
  t "le bloc garde ses 2 lignes"  "$(printf '%s' "$sortie" | grep -c '^ruff check')" "2"
  t "le run d'une ligne est lu"   "$(printf '%s' "$sortie" | grep -c '^pytest tests/ -q$')" "1"
  t "working-directory conservé"  "$(printf '%s' "$sortie" | awk -F'\t' '/^@@STEP/ && $4=="Pytest" {print $6}')" "api"
  t "env conservé"                "$(printf '%s' "$sortie" | grep -c '^@@ENV.SECRET_KEY')" "1"
  t "version épinglée conservée"  "$(printf '%s' "$sortie" | grep -c "python-version: '3.11'")" "1"
  t "commentaires non pris pour des étapes" "$(printf '%s' "$sortie" | grep -c '^@@ERREUR')" "0"

  #  Le contrôle qui a manqué le 12/08 : une étape que le parseur ne sait pas
  #  lire doit se VOIR. On la fabrique en cassant la forme attendue.
  got=$(ci_extraire <<'YAML' | grep -c '^@@RUN$'
jobs:
  j:
    steps:
      - name: lisible
        run: echo ok
YAML
)
  t "parité sur un cas minimal" "$got" "1"

  t "classement — installation pure" "$(printf 'pip install -r requirements.txt\npip install pytest\n' | ci_classer)" "PREPARATION"
  t "classement — apt multiligne"    "$(printf 'sudo apt-get update -qq\nsudo apt-get install -y \\\n  libcairo2\n' | ci_classer)" "PREPARATION"
  t "classement — contrôle réel"     "$(printf 'ruff check api/app/\n' | ci_classer)" "CONTROLE"
  t "classement — expression GitHub" "$(printf 'bash x.sh origin/${{ github.ref }}\n' | ci_classer)" "INCONNU expression GitHub non résolue"
  t "classement — commentaire seul n'est pas un contrôle" "$(printf '# rien\npip install x\n' | ci_classer)" "PREPARATION"

  t "substitution base_ref" "$(printf "bash m.sh origin/\${{ github.base_ref || 'main' }}\n" | ci_substituer abc123)" "bash m.sh origin/main"
  t "substitution sha"      "$(printf 'VITE=${{ github.sha }}\n' | ci_substituer abc123)" "VITE=abc123"

  t "requalification — succès"       "$(printf '' | ci_requalifier 0)" "OK"
  t "requalification — outil absent" "$(printf 'bash: ruff: command not found\n' | ci_requalifier 127)" "INCONNU outil absent du poste"
  t "requalification — vrai échec"   "$(printf 'F401 unused import\n' | ci_requalifier 1)" "FAIL"
  #  Le cas du 04/09/2026 : `lint:audit` quand le registre npm ne répond pas —
  #  code 2, et le contrôle DIT lui-même qu'il n'a pas mesuré.
  t "requalification — non mesuré" \
    "$(printf 'INCONNU — audit npm injoignable\n' | ci_requalifier 2)" \
    "INCONNU le contrôle se déclare non mesuré"
  #  🔴 Et sa réciproque, qui rend la requalification sûre : un échec qui parle
  #  d'un INCONNU AILLEURS reste un échec. Sans ce cas, le motif pourrait
  #  s'élargir sans qu'on s'en aperçoive.
  t "requalification — le mot seul ne suffit pas" \
    "$(printf 'le point 9 reste INCONNU par construction\n' | ci_requalifier 1)" "FAIL"

  #  Éprouvé sur le VRAI fichier quand il est là : c'est le seul contrôle qui
  #  verrait un `ci.yml` réécrit dans une forme que le parseur ne sait plus lire.
  #  Absent → on le DIT, on ne conclut pas.
  if [ -f .github/workflows/ci.yml ]; then
    local p; p=$(ci_parite .github/workflows/ci.yml)
    t "parité sur le ci.yml réel (${p% *} écrits)" "${p#* }" "${p% *}"
  else
    echo "?     parité sur le ci.yml réel — fichier absent, non mesuré"
  fi

  [ $st -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
  return $st
}
