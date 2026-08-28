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


def _fichiers_routers() -> list[pathlib.Path]:
    """Tous les modules de routers, **sous-paquets compris**.

    ⚠️ Cette fonction est la PORTÉE du contrôle, donc une partie du contrôle
    (`standards/05-tests-et-garde-fous.md` §9). Les quatre tests de ce fichier
    parcouraient `glob("*.py")`, sans récursion. Le jour où `admin.py` est devenu
    le paquet `admin/` (06/08/2026, 2057 lignes → 8 modules), ses **45 endpoints**
    sont sortis du champ d'un coup — et le test serait resté VERT en vérifiant
    simplement moins de choses. Un contrôle qui rétrécit sans le dire est pire
    qu'un contrôle absent : il continue de rassurer.

    C'est le test des endpoints orphelins qui a levé le lièvre, parce que sa liste
    d'exceptions est vérifiée dans les deux sens. Ce test-ci n'avait pas cette
    chance ; d'où le contrôle de couverture minimale ci-dessous.
    """
    fichiers = [
        f for f in sorted(_ROUTERS.rglob("*.py"))
        if "__pycache__" not in f.parts
    ]
    #  Garde-fou du garde-fou : un glob cassé rendrait une liste vide, et tous les
    #  tests de ce fichier passeraient sans rien examiner.
    assert len(fichiers) >= 25, (
        f"Seulement {len(fichiers)} module(s) de router trouvé(s) sous {_ROUTERS} — "
        "la portée du contrôle est cassée, ne pas lire les tests suivants comme verts."
    )
    return fichiers

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
    ("auth.py", "logout"), ("auth.py", "verify_email"),
    ("auth.py", "resend_verification"),
    #  Le bloc « mot de passe » a quitté `auth.py` le 14/08/2026 (modularité) : ces
    #  deux exemptions ont suivi le code, sans changer de nature. Qui a perdu son
    #  mot de passe ne peut pas prouver qui il est — c'est le jeton envoyé par
    #  courriel qui le fait, et sa vérification est dans l'endpoint lui-même.
    ("auth_mot_de_passe.py", "request_password_reset"),
    ("auth_mot_de_passe.py", "reset_password"),
    # Liste des bâtiments : alimente le formulaire d'inscription.
    ("auth.py", "list_batiments"),
    # Coquille d'interface et pages légales, filtrées par LISTE BLANCHE
    # (cf. `_PUBLIC_KEYS` dans routers/config.py) — vérifié plus bas.
    ("config.py", "get_config"), ("config.py", "get_legal_config"),
    # Télémétrie par `sendBeacon`, visiteurs anonymes inclus : rate-limité
    # (60/min), plafonné à 50 événements, champs tronqués, opt-out RGPD honoré.
    ("telemetry.py", "collect"),
    #  Rapport de violation CSP : le NAVIGATEUR le poste, sans cookie ni en-tête
    #  d'authentification — c'est la spécification, pas un choix. Ce point n'existe
    #  que pour MESURER avant de poser une CSP bloquante (#536).
    #
    #  Ses bornes, chacune éprouvée par `test_csp_report.py` : limite de débit
    #  60/min, plafond de 200 clés distinctes, URL tronquées, AUCUNE écriture en
    #  base, et rien qui soit renvoyé à l'appelant. Le relevé, lui, est réservé
    #  aux administrateurs — il expose des URL de pages visitées.
    ("csp.py", "recevoir_rapport"),
    # Rapport de maintenance machine-à-machine : authentifié par secret partagé
    # (en-tête `x-maintenance-key`), et refuse tout si la clé n'est pas configurée.
    ("rapports_scripts.py", "maintenance_rapport"),
    # Même canal, en lecture : `check-reliability.sh` C19 y compare la date du
    # dernier rapport en base avec ce que dit le journal du nœud. Tourne en cron,
    # donc sans session. Ne rend que des dates d'exécution de tâches — aucune
    # donnée de copropriétaire — et la clé qui l'ouvre autorise déjà l'ÉCRITURE
    # de ces mêmes lignes : la lecture est strictement moins sensible.
    ("rapports_scripts.py", "maintenance_dernier_rapport"),
    # Même canal, même clé : COMBIEN d'e-mails ont échoué ces derniers jours, et
    # de quels modèles. Rend des comptes et des codes de gabarits — **jamais une
    # adresse ni un sujet**, alors que l'écran d'administration en montre. C'est
    # ce qui rend le point 9 du pré-check mesurable au lieu d'`INCONNU` à chaque
    # exécution : un contrôle que personne ne fait ne protège rien.
    ("rapports_scripts.py", "emails_echecs_recents"),
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
    for f in _fichiers_routers():
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
    for f in _fichiers_routers():
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
    for f in _fichiers_routers() + sorted((_API_DIR / "app" / "utils").glob("*.py")):
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


def test_aucune_regle_de_visibilite_ne_vit_dans_un_router():
    """Les règles de visibilité vivent dans `app/utils/visibility.py`, et nulle part ailleurs.

    L'en-tête de ce module l'énonce depuis toujours : « Toute logique de filtrage par
    rôle/périmètre/profil doit passer par ce module. Ne jamais dupliquer ces règles
    dans les routers. » La règle documents, elle, était restée dans
    `routers/documents.py` sous le nom `_user_can_read`, et `flux.py` l'importait
    depuis ce router.

    Ce n'est pas un détail d'organisation : une règle hors du module central est une
    règle qu'un durcissement ultérieur peut manquer. C'est exactement ce qui est
    arrivé aux pièces jointes d'actualité — autorisées sans consulter l'actualité
    porteuse, donc téléchargeables par n'importe quel compte authentifié
    (cf. `test_documents_acces.py`), pendant que les trois chemins d'accès concernés
    partageaient la même fonction fautive et se confirmaient mutuellement.

    Deux interdits, donc : définir une règle de visibilité dans un router, et
    importer une règle depuis un router plutôt que depuis le module central.
    """
    import re

    central = _API_DIR / "app" / "utils" / "visibility.py"
    # Une règle de visibilité se reconnaît à son nom : `*_visible`, `*_accessible`,
    # `can_see_*`, ou l'ancien `_user_can_read`.
    motif_def = re.compile(
        r"^def\s+(\w*_visible|\w*_accessible|can_see_\w*|_user_can_read)\s*\(",
        re.MULTILINE,
    )
    # `from app.routers.x import ... visible/accessible/can_read ...`
    motif_import = re.compile(
        r"^from\s+app\.routers\.[\w.]+\s+import\s+[^\n]*"
        r"(?:_visible|_accessible|can_see|can_read)",
        re.MULTILINE,
    )

    egarees, imports_croises = [], []
    for f in _fichiers_routers():
        src = f.read_text(encoding="utf-8-sig")
        for m in motif_def.finditer(src):
            egarees.append(f"  {f.name} définit {m.group(1)}()")
        for m in motif_import.finditer(src):
            imports_croises.append(f"  {f.name} : {m.group(0).strip()}")

    assert not egarees, (
        "Règle(s) de visibilité définie(s) dans un router — à déplacer dans "
        f"{central.relative_to(_API_DIR.parent)} :\n" + "\n".join(egarees)
    )
    assert not imports_croises, (
        "Règle(s) de visibilité importée(s) depuis un router au lieu du module "
        "central — le jour où le router change, l'appelant ne le saura pas :\n"
        + "\n".join(imports_croises)
    )
