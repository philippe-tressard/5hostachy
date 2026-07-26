"""Garde-fou préventif : aucun endpoint sans autorisation, aucun passe-droit.

L'exigence : **toutes** les règles de sécurité vivent dans `app/auth/deps.py`, et
tout endpoint y passe. Ce test échoue si un endpoint apparaît sans dépendance
d'autorisation, ou si un contrôle de rôle contourne le module central.

POURQUOI (audit du 26/07/2026) — l'exigence était respectée dans les grandes
lignes (276 endpoints, aucun contrôle sur `user.role`, tout via `has_role()`), mais
trois dérives s'étaient installées sans que rien ne les signale :

1. `GET /config` filtrait par liste NOIRE : toute clé de configuration non
   explicitement interdite était publiée **sans authentification**. 31 clés
   fuyaient, dont la configuration SMTP, l'URL interne du bridge WhatsApp et un
   lien d'invitation fonctionnel au groupe privé des résidents.
2. `bailleur.py` définissait `_require_bailleur`, doublon exact de
   `require_proprietaire`, hors du module central — 17 endpoints s'appuyaient
   dessus. Un durcissement de la règle centrale ne les aurait pas atteints.
3. Deux contrôles utilisaient des chaînes littérales (`has_role("admin")`) au lieu
   de l'enum `RoleUtilisateur`.

Aucune de ces dérives n'était détectable autrement qu'à la relecture. D'où ce test.
"""
import ast
import pathlib

_API_DIR = pathlib.Path(__file__).resolve().parents[1]
_ROUTERS = _API_DIR / "app" / "routers"

# Dépendances d'autorisation — TOUTES définies dans app/auth/deps.py.
_DEPS_AUTORISATION = {
    "get_current_user", "get_acting_user", "require_role",
    "require_proprietaire", "require_cs_or_admin", "require_admin",
}

_VERBES = {"get", "post", "put", "patch", "delete"}

# ─────────────────────────────────────────────────────────────────────────────
#  Endpoints VOLONTAIREMENT publics. Chaque entrée doit rester justifiable en une
#  phrase. Ajouter une ligne ici est une DÉCISION DE SÉCURITÉ : elle expose un
#  endpoint à Internet. Ne pas l'utiliser pour faire taire le test.
# ─────────────────────────────────────────────────────────────────────────────
_PUBLICS_ASSUMES = {
    # Pré-authentification : impossible d'exiger une session pour se connecter.
    ("auth.py", "login"), ("auth.py", "register"), ("auth.py", "refresh"),
    ("auth.py", "logout"), ("auth.py", "request_password_reset"),
    ("auth.py", "reset_password"), ("auth.py", "verify_email"),
    ("auth.py", "resend_verification"),
    # Liste des bâtiments : alimente le formulaire d'inscription.
    ("auth.py", "list_batiments"),
    # Coquille d'interface et pages légales, filtrées par LISTE BLANCHE
    # (cf. `_PUBLIC_KEYS` dans routers/config.py) — vérifié plus bas.
    ("config.py", "get_config"), ("config.py", "get_legal_config"),
    # Télémétrie par `sendBeacon`, visiteurs anonymes inclus : rate-limité
    # (60/min), plafonné à 50 événements, champs tronqués, opt-out RGPD honoré.
    ("telemetry.py", "collect"),
    # Rapport de maintenance machine-à-machine : authentifié par secret partagé
    # (en-tête `x-maintenance-key`), et refuse tout si la clé n'est pas configurée.
    ("admin.py", "maintenance_rapport"),
}


def _noms(node) -> set[str]:
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            out.add(n.id)
        elif isinstance(n, ast.Attribute):
            out.add(n.attr)
    return out


def _endpoints():
    """Itère sur (fichier, ligne, verbe, chemin, nom_fonction, a_autorisation)."""
    for f in sorted(_ROUTERS.glob("*.py")):
        if f.name == "__init__.py":
            continue
        arbre = ast.parse(f.read_text(encoding="utf-8-sig"))
        for node in ast.walk(arbre):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            deco = next(
                (d for d in node.decorator_list
                 if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
                 and d.func.attr in _VERBES),
                None,
            )
            if deco is None:
                continue
            trouve = any(
                kw.arg == "dependencies" and _noms(kw.value) & _DEPS_AUTORISATION
                for kw in deco.keywords
            )
            if not trouve:
                defauts = list(node.args.defaults) + [
                    d for d in node.args.kw_defaults if d is not None
                ]
                trouve = any(_noms(d) & _DEPS_AUTORISATION for d in defauts)
            chemin = (
                deco.args[0].value
                if deco.args and isinstance(deco.args[0], ast.Constant)
                else ""
            )
            yield f.name, node.lineno, deco.func.attr.upper(), chemin, node.name, trouve


def test_tout_endpoint_porte_une_autorisation():
    """Aucun endpoint sans dépendance d'autorisation, hors publics assumés."""
    manquants = [
        f"{fichier}:{ligne} {verbe} {chemin or '/'} -> {fn}()"
        for fichier, ligne, verbe, chemin, fn, ok in _endpoints()
        if not ok and (fichier, fn) not in _PUBLICS_ASSUMES
    ]
    assert not manquants, (
        "Endpoint(s) sans autorisation. Ajouter une dépendance de `app/auth/deps.py` "
        "(get_current_user, require_cs_or_admin, require_admin…). Si l'endpoint doit "
        "vraiment être public, l'inscrire dans `_PUBLICS_ASSUMES` AVEC sa "
        "justification — c'est une décision de sécurité :\n" + "\n".join(manquants)
    )


def test_pas_de_public_assume_obsolete():
    """`_PUBLICS_ASSUMES` ne doit pas conserver d'entrées périmées.

    Une exemption qui survit à la disparition ou à la protection de son endpoint
    devient un trou prêt à se rouvrir sous le même nom de fonction.
    """
    reels = {(fichier, fn) for fichier, _, _, _, fn, ok in _endpoints() if not ok}
    obsoletes = sorted(_PUBLICS_ASSUMES - reels)
    assert not obsoletes, (
        "Exemption(s) devenue(s) inutile(s) dans `_PUBLICS_ASSUMES` — à retirer :\n"
        + "\n".join(f"  {f} -> {fn}()" for f, fn in obsoletes)
    )


def test_aucune_dependance_d_autorisation_locale():
    """Les règles de sécurité vivent dans `app/auth/deps.py`, nulle part ailleurs.

    Attrape la dérive de `_require_bailleur` : un doublon local de
    `require_proprietaire`, invisible depuis le module central.
    """
    locales = []
    for f in sorted(_ROUTERS.glob("*.py")):
        arbre = ast.parse(f.read_text(encoding="utf-8-sig"))
        for node in ast.walk(arbre):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.lstrip("_").startswith("require"):
                continue
            locales.append(f"{f.name}:{node.lineno} {node.name}()")
    assert not locales, (
        "Dépendance d'autorisation définie hors de `app/auth/deps.py` : la règle "
        "doit être centralisée, sinon un durcissement du module central ne "
        "l'atteindra pas.\n" + "\n".join(locales)
    )


def test_controles_de_role_via_l_enum():
    """`has_role()` doit recevoir l'enum `RoleUtilisateur`, pas des chaînes.

    Une chaîne échoue en silence sur une faute de frappe. Le comportement est
    heureusement fail-closed (accès refusé), mais la protection devient illisible
    et le renommage d'un rôle casse le contrôle sans erreur.
    """
    fautifs = []
    for f in sorted(list(_ROUTERS.glob("*.py")) + list((_API_DIR / "app" / "utils").glob("*.py"))):
        for num, ligne in enumerate(f.read_text(encoding="utf-8-sig").splitlines(), 1):
            if "has_role(" in ligne and '"' in ligne.split("has_role(", 1)[1][:60]:
                fautifs.append(f"{f.name}:{num}: {ligne.strip()}")
    assert not fautifs, (
        "Contrôle de rôle par chaîne littérale — utiliser `RoleUtilisateur.<role>` :\n"
        + "\n".join(fautifs)
    )


def test_config_publique_filtree_par_liste_blanche():
    """`GET /config` est public : son filtre doit être une liste BLANCHE.

    Une liste noire échoue en s'ouvrant — toute nouvelle clé de configuration
    devient publique par défaut. C'est ainsi que 31 clés ont fuité, dont la
    configuration SMTP et un lien d'invitation au groupe WhatsApp privé.
    """
    import re

    src = (_ROUTERS / "config.py").read_text(encoding="utf-8-sig")
    assert "_PUBLIC_KEYS" in src, "config.py doit définir une liste blanche `_PUBLIC_KEYS`"
    # On cherche une AFFECTATION en début de ligne, pas une mention : le commentaire
    # du module cite `_PRIVATE_KEYS` pour expliquer d'où venait la fuite.
    assert not re.search(r"^_PRIVATE_KEYS\s*=", src, re.MULTILINE), (
        "config.py contient encore une liste noire `_PRIVATE_KEYS` : "
        "le filtre doit être une liste blanche (fail-closed)"
    )
    # La liste blanche ne doit contenir aucune clé manifestement sensible.
    bloc = re.search(r"^_PUBLIC_KEYS\s*=\s*\{(.*?)\}", src, re.DOTALL | re.MULTILINE)
    assert bloc, "impossible de lire `_PUBLIC_KEYS`"
    contenu = bloc.group(1)
    for interdit in ("smtp", "api_key", "password", "secret", "token",
                     "group_jid", "community_url", "manager_user_id"):
        assert interdit not in contenu, (
            f"`_PUBLIC_KEYS` contient une clé sensible ('{interdit}') : "
            "cet endpoint est lisible sans authentification"
        )
