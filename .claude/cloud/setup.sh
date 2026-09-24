#!/usr/bin/env bash
# =============================================================================
#  setup.sh — Prépare une session cloud Claude Code (claude.ai/code) pour
#  5Hostachy : l'outillage de la CI, les dépendances du dépôt, les hooks git et,
#  quand il est accessible, le socle `claude-config`.
#
#  POURQUOI CE FICHIER (24/09/2026). L'environnement cloud se configure dans
#  l'interface claude.ai — nom, réseau, variables, script de setup. Un script
#  écrit là-bas n'est versionné nulle part : il diverge du dépôt au premier job
#  de CI ajouté, et personne ne le relit. L'interface ne porte donc qu'un appel
#  à ce fichier (`.claude/cloud/LISEZMOI.md`), et c'est ici qu'il évolue.
#
#  SOURCE UNIQUE : ce script n'a pas de liste. Les paquets système, les outils
#  Python et le navigateur des tests sont EXTRAITS de `.github/workflows/ci.yml`.
#  Une liste recopiée divergerait au premier outil ajouté à la CI — c'est la
#  raison d'être de `scripts/poste/rejouer-ci.sh`, et elle vaut ici aussi.
#
#  RÈGLES (socle 04) :
#   - une étape qui échoue est DITE (⚠️), jamais tue ;
#   - le script sort pourtant en 0 : un setup en échec empêche toute session,
#     y compris celle qui viendrait le réparer. Le contrôle qui compte est
#     `.claude/env-report.sh`, relancé à CHAQUE session : il déclare ABSENT ce
#     qui manque, au lieu de laisser croire que le setup a tout posé.
#
#  CE QU'IL NE FAIT PAS, et ne peut pas faire : aucun accès SSH aux RPi (réseau
#  local injoignable depuis le cloud), donc ni pré-check complet, ni MEP, ni
#  post-check. Aucun secret : les variables de l'environnement sont visibles de
#  tous ses utilisateurs (socle 03).
#
#  Usage : bash .claude/cloud/setup.sh     (idempotent — relançable en session)
# =============================================================================
set -uo pipefail

DEPOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
CI="$DEPOT/.github/workflows/ci.yml"
ECARTS=0

signaler() { echo "⚠️  $*"; ECARTS=$((ECARTS + 1)); }

# root dans le setup ; `sudo` seulement s'il existe et qu'on ne l'est pas.
SUDO=""
[ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1 && SUDO="sudo"

[ -f "$CI" ] || { echo "⚠️  $CI introuvable : rien à extraire, setup abandonné."; exit 0; }

# ── 1. Bibliothèques système du rendu PDF (WeasyPrint) ──────────────────────
PAQUETS=$(sed -nE 's/^[[:space:]]*PAQUETS="([^"]+)".*/\1/p' "$CI" | head -1)
if [ -z "$PAQUETS" ]; then
    signaler "liste PAQUETS introuvable dans ci.yml — rendu PDF non installé"
elif command -v apt-get >/dev/null 2>&1; then
    # shellcheck disable=SC2086  # liste de paquets : le découpage est voulu
    { $SUDO apt-get update -qq && $SUDO apt-get install -y --no-install-recommends $PAQUETS; } >/dev/null \
        && echo "✓ bibliothèques PDF : $PAQUETS" \
        || signaler "installation apt échouée ($PAQUETS)"
else
    signaler "apt-get absent : bibliothèques PDF non installées"
fi

# ── 2. Outils Python de la CI, puis dépendances de l'API ────────────────────
#  `--break-system-packages` : Ubuntu 24.04 refuse sinon un pip hors venv. La
#  VM est jetable et ne sert qu'à ce dépôt — l'isolation n'y protège rien.
pip_installer() {
    python3 -m pip install -q --break-system-packages "$@" 2>/dev/null \
        || python3 -m pip install -q "$@"
}
OUTILS=$(sed -nE 's/.*pip install ([A-Za-z][A-Za-z0-9_.-]*)[[:space:]]*$/\1/p' "$CI" | sort -u | tr '\n' ' ')
if [ -z "$OUTILS" ]; then
    signaler "aucun outil Python extrait de ci.yml"
else
    # shellcheck disable=SC2086
    pip_installer $OUTILS && echo "✓ outils Python : $OUTILS" || signaler "pip : échec sur $OUTILS"
fi
pip_installer -r "$DEPOT/api/requirements.txt" \
    && echo "✓ dépendances de l'API" || signaler "pip : échec sur api/requirements.txt"

# ── 3. Front : Node de la CI, dépendances, navigateur des tests e2e ─────────
NODE_CI=$(sed -nE 's/.*node-version:[[:space:]]*"?([0-9]+)"?.*/\1/p' "$CI" | head -1)
NODE_ICI=$(node -v 2>/dev/null | sed -E 's/^v([0-9]+).*/\1/')
[ -n "$NODE_CI" ] && [ "$NODE_ICI" != "$NODE_CI" ] \
    && signaler "Node ${NODE_ICI:-absent} ici, Node $NODE_CI en CI"
( cd "$DEPOT/front" && npm ci --no-audit --no-fund >/dev/null ) \
    && echo "✓ dépendances du front (npm ci)" || signaler "npm ci a échoué"
NAVIGATEUR=$(sed -nE 's/.*npx playwright install (.*)$/\1/p' "$CI" | head -1)
if [ -n "$NAVIGATEUR" ]; then
    # shellcheck disable=SC2086
    ( cd "$DEPOT/front" && npx playwright install $NAVIGATEUR >/dev/null 2>&1 ) \
        && echo "✓ navigateur e2e ($NAVIGATEUR)" \
        || signaler "playwright install a échoué — domaines de téléchargement hors du réseau autorisé ?"
fi

# ── 4. Hooks git du dépôt (pre-commit : retard sur l'upstream ; pre-push) ───
git -C "$DEPOT" config core.hooksPath .githooks
git -C "$DEPOT" config pull.ff only
echo "✓ hooks git armés (.githooks)"

# ── 5. Socle commun `claude-config` — seulement s'il est attaché ─────────────
#  Le proxy GitHub du cloud ne donne accès qu'aux dépôts ATTACHÉS à la session :
#  sans cela le clone rend 403, et c'est attendu. Le socle est alors absent, et
#  `env-report.sh` le dit à chaque session — dont le garde-fou `git reset --hard`.
#  Le clone vit HORS de `~/.claude`, que le cloud ne lit pas ; les liens posés
#  font seulement résoudre les chemins `~/.claude/standards/…` cités partout.
SOCLE="$HOME/claude-config"
if [ -d "$SOCLE/.git" ]; then
    git -C "$SOCLE" pull -q --ff-only 2>/dev/null || signaler "claude-config : mise à jour impossible"
else
    git clone -q --depth 1 https://github.com/philippe-tressard/claude-config.git "$SOCLE" 2>/dev/null \
        || signaler "claude-config inaccessible (dépôt non attaché à la session ?) — socle ABSENT"
fi
if [ -d "$SOCLE/standards" ]; then
    mkdir -p "$HOME/.claude"
    for d in standards skills; do
        [ -e "$HOME/.claude/$d" ] || ln -s "$SOCLE/$d" "$HOME/.claude/$d"
    done
    echo "✓ socle claude-config dans $SOCLE"
fi

echo ""
[ "$ECARTS" -eq 0 ] && echo "Setup 5Hostachy terminé sans écart." \
    || echo "Setup 5Hostachy terminé avec $ECARTS écart(s) — voir les ⚠️ ci-dessus."
exit 0
