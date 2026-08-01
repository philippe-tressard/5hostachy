"""Garde-fou : le `context` passé à send_email fournit-il les variables du template ?

`test_email_templates.py` verrouille le **template** ; sa docstring assumait de
ne pas couvrir le **point d'appel**, laissé à une inspection *a posteriori* de
`historique_email`. C'est précisément par là que le bug est revenu une troisième
fois : le 28/07/2026, `calendrier_evenement_cree` a échoué en
`'evenement' is undefined` pour six membres du CS — le contexte avait été repris
du mail de ticket, avec la clé `ticket` jamais renommée. Découvert au pré-check
du 01/08, cinq jours plus tard, comme les deux fois précédentes
(`reinitialisation_mdp` le 03/06, `ticket_statut_change` le 15/06).

Les envois partent en `BackgroundTask` : l'échec ne laisse aucune trace dans les
logs de l'API ni à l'écran. Rien ne le signale, donc rien ne le corrige.

Ce test lit `app/` en AST, retrouve chaque envoi dont le contexte est un
dictionnaire littéral analysable, et vérifie qu'il couvre le contrat du template.
Un contexte trop riche est permis (fournir plus qu'il n'en faut ne casse rien) ;
un contexte incomplet échoue.
"""
import ast
from pathlib import Path

import pytest
from jinja2 import BaseLoader, nodes
from jinja2.sandbox import SandboxedEnvironment

from app.seed import EMAIL_TEMPLATES
from tests.test_email_templates import BASE_CTX_VARS

_APP_DIR = Path(__file__).resolve().parents[1] / "app"
_FONCTIONS_ENVOI = {"send_email", "send_email_group"}

_env_jinja = SandboxedEnvironment(loader=BaseLoader())


def _variables_qui_font_echouer(sujet: str | None, corps: str | None) -> set[str]:
    """Variables dont l'ABSENCE lève une `UndefinedError` à l'envoi.

    `send_email` utilise un `SandboxedEnvironment` par défaut, donc l'`Undefined`
    permissif : un `{{ x }}` seul rend une chaîne vide et ne casse rien. Seuls
    lèvent l'accès à un attribut ou à une clé (`{{ x.y }}`, `{{ x['y'] }}`),
    l'itération (`{% for i in x %}`).

    Les filtres sont volontairement HORS du critère : `{{ commentaire | safe }}`
    sur une variable absente rend une chaîne vide sans lever, et deux templates
    du dépôt s'appuient dessus. Seuls quelques filtres (`| length`) échoueraient
    — les inclure tous ferait crier au loup là où rien ne casse.

    Exiger davantage produirait de faux positifs : plusieurs contextes du dépôt
    omettent des variables seulement affichées, sans que l'envoi échoue.
    """
    arbre = _env_jinja.parse(f"{sujet or ''} {corps or ''}")
    risquees: set[str] = set()

    # `{% for m in messages %}` définit `m` (et `loop`) : ce sont des variables
    # locales au template, que le contexte n'a évidemment pas à fournir.
    locales: set[str] = {"loop"}

    def _noms_cibles(cible):
        """`find_all` de Jinja ne renvoie PAS le nœud lui-même : sans ce cas,
        `{% for m in … %}` (cible simple) laissait `m` passer pour une variable
        de contexte manquante."""
        if isinstance(cible, nodes.Name):
            yield cible.name
        for n in cible.find_all(nodes.Name):
            yield n.name

    for n in arbre.find_all(nodes.For):
        locales.update(_noms_cibles(n.target))
    for n in arbre.find_all(nodes.Assign):
        locales.update(_noms_cibles(n.target))

    def _nom(node) -> str | None:
        return node.name if isinstance(node, nodes.Name) else None

    for n in arbre.find_all((nodes.Getattr, nodes.Getitem)):
        if (nom := _nom(n.node)):
            risquees.add(nom)
    for n in arbre.find_all(nodes.For):
        if (nom := _nom(n.iter)):
            risquees.add(nom)
    # Variables testées par un `{% if %}` quelque part dans le template : leur
    # absence rend la condition fausse, donc le bloc qui les déréférence n'est
    # jamais atteint. `ticket_syndic` protège ainsi `messages` et `historique`
    # (`{% if is_commentaire and messages %}`), et ses envois qui ne les
    # fournissent pas fonctionnent — les signaler serait crier au loup.
    #
    # Approximation assumée : la garde est cherchée dans TOUT le template, pas
    # seulement sur le bloc englobant. Elle ne peut donc produire que des faux
    # négatifs (une variable gardée ici et déréférencée ailleurs sans garde
    # passerait), jamais de faux positifs — le bon sens pour un garde-fou dont
    # personne ne doit apprendre à ignorer les alertes.
    gardees: set[str] = set()
    for n in arbre.find_all(nodes.If):
        gardees.update(x.name for x in _tous_les_noms(n.test))

    return risquees - BASE_CTX_VARS - locales - gardees


def _tous_les_noms(node):
    """`find_all` de Jinja n'inclut pas le nœud lui-même."""
    if isinstance(node, nodes.Name):
        yield node
    yield from node.find_all(nodes.Name)


_VARS_CRITIQUES: dict[str, set[str]] = {
    row[0]: _variables_qui_font_echouer(row[2], row[3]) for row in EMAIL_TEMPLATES
}


def _nom_appele(node: ast.Call) -> str | None:
    f = node.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return None


def _cibles_assignees(node):
    """Noms affectés par `node`, qu'il soit annoté ou non.

    `ctx: dict[str, Any] = {...}` est un `AnnAssign`, pas un `Assign` : les deux
    écritures cohabitent dans `app/` et seule la seconde était reconnue. C'est ce
    qui rendait opaques les contextes de `vigik_*` et `compte_*` — quatre envois
    silencieusement non couverts.
    """
    if isinstance(node, ast.Assign):
        cibles = node.targets
    elif isinstance(node, ast.AnnAssign) and node.value is not None:
        cibles = [node.target]
    else:
        return
    for c in cibles:
        if isinstance(c, ast.Name):
            yield c


def _codes_possibles(node, portee: ast.AST, module: ast.AST, ligne: int) -> set[str] | None:
    """Codes que `node` peut valoir, ou None si l'expression reste opaque.

    Un `code=` littéral n'est pas la seule écriture du dépôt : le choix du
    modèle dépend souvent de l'issue traitée, et s'écrit alors en ternaire
    (`"vigik_accepte" if accepte else "vigik_refuse"`), en variable locale
    (`email_code`) ou en constante de module (`REPONSE_EMAIL_CODE`). Ces trois
    formes étaient purement et simplement **ignorées** — quatre envois, dont
    les deux couples accepté/refusé, sortaient du garde-fou sans que rien ne le
    signale. Or ce sont précisément les envois les plus exposés : la branche de
    refus fournit une variable (`motif`) que la branche d'acceptation n'a pas.

    Un ternaire rend les DEUX codes : le contexte doit satisfaire l'un et
    l'autre, puisque l'exécution empruntera l'une ou l'autre branche.
    """
    if isinstance(node, ast.Constant):
        return {node.value} if isinstance(node.value, str) else None
    if isinstance(node, ast.IfExp):
        gauche = _codes_possibles(node.body, portee, module, ligne)
        droite = _codes_possibles(node.orelse, portee, module, ligne)
        return None if gauche is None or droite is None else gauche | droite
    if isinstance(node, ast.Name):
        # Assignation la plus proche AVANT l'appel dans la fonction englobante,
        # à défaut une constante de module (portée sans contrainte de ligne).
        for source, borne in ((portee, ligne), (module, None)):
            valeur = None
            for n in ast.walk(source):
                if borne is not None and getattr(n, "lineno", 0) >= borne:
                    continue
                if any(c.id == node.id for c in _cibles_assignees(n)):
                    valeur = n.value
            if valeur is not None:
                return _codes_possibles(valeur, portee, module, ligne)
    return None


def _envois(arbre: ast.AST, module: ast.AST):
    """Rend (code, node_context, ligne) pour chaque envoi d'email trouvé.

    Couvre les deux écritures du dépôt : l'appel direct `send_email(...)` et
    l'appel différé `background_tasks.add_task(send_email_group, code=..., ...)`.
    Un envoi dont le code se résout à plusieurs modèles est rendu une fois par
    modèle : chacun doit tenir avec le même contexte.
    """
    for node in ast.walk(arbre):
        if not isinstance(node, ast.Call):
            continue
        nom = _nom_appele(node)
        est_envoi = nom in _FONCTIONS_ENVOI
        if nom == "add_task" and node.args:
            premier = node.args[0]
            est_envoi = isinstance(premier, ast.Name) and premier.id in _FONCTIONS_ENVOI
        if not est_envoi:
            continue
        kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
        codes = _codes_possibles(kwargs.get("code"), arbre, module, node.lineno)
        if not codes:
            continue  # code réellement indéterminable statiquement
        for code in sorted(codes):
            yield code, kwargs.get("context"), node.lineno


def _cles_du_contexte(node_context, portee: ast.AST, ligne_appel: int) -> set[str] | None:
    """Clés de premier niveau du contexte, ou None s'il n'est pas analysable.

    `portee` est la **fonction englobante**, et seule une assignation située
    AVANT l'appel est retenue. Chercher sur tout le module donnait le dernier
    `ctx = {...}` du fichier, quelle que soit la fonction : `relance_syndic` se
    voyait attribuer les clés du mail `ticket_syndic` et trois faux positifs
    apparaissaient dans `tickets.py`.
    """
    if node_context is None:
        return set()
    dictionnaire = node_context
    if isinstance(node_context, ast.Name):
        dictionnaire = None
        for n in ast.walk(portee):
            if (
                isinstance(getattr(n, "value", None), ast.Dict)
                and getattr(n, "lineno", 0) < ligne_appel
                and any(c.id == node_context.id for c in _cibles_assignees(n))
            ):
                dictionnaire = n.value
        if dictionnaire is None:
            return None
    if not isinstance(dictionnaire, ast.Dict):
        return None

    cles = {
        c.value for c in dictionnaire.keys
        if isinstance(c, ast.Constant) and isinstance(c.value, str)
    }
    # `ctx["x"] = …` et `ctx.update({...})` après la déclaration.
    if isinstance(node_context, ast.Name):
        for n in ast.walk(portee):
            if isinstance(n, ast.Assign):
                for cible in n.targets:
                    if (
                        isinstance(cible, ast.Subscript)
                        and isinstance(cible.value, ast.Name)
                        and cible.value.id == node_context.id
                        and isinstance(cible.slice, ast.Constant)
                        and isinstance(cible.slice.value, str)
                    ):
                        cles.add(cible.slice.value)
            if (
                isinstance(n, ast.Call)
                and _nom_appele(n) == "update"
                and isinstance(n.func, ast.Attribute)
                and isinstance(n.func.value, ast.Name)
                and n.func.value.id == node_context.id
            ):
                for arg in n.args:
                    if isinstance(arg, ast.Dict):
                        cles |= {
                            c.value for c in arg.keys
                            if isinstance(c, ast.Constant) and isinstance(c.value, str)
                        }
                    else:
                        return None  # mise à jour opaque : on ne conclut pas
    return cles


def _portees(arbre: ast.AST):
    """Fonctions du module, plus le module lui-même pour les envois hors fonction."""
    yield arbre
    for n in ast.walk(arbre):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield n


def _collecter() -> tuple[list[tuple[str, str, set[str]]], list[tuple[str, str]]]:
    analysables: list[tuple[str, str, set[str]]] = []
    opaques: list[tuple[str, str]] = []
    for chemin in sorted(_APP_DIR.rglob("*.py")):
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        relatif = chemin.relative_to(_APP_DIR).as_posix()
        vus: set[tuple[str, int]] = set()
        # Des portées imbriquées voient le même appel : on retient la plus
        # étroite, c'est-à-dire celle qui déclare le moins de `ctx` candidats.
        for portee in sorted(_portees(arbre), key=lambda p: -getattr(p, "lineno", 0)):
            for code, node_context, ligne in _envois(portee, arbre):
                if (code, ligne) in vus:
                    continue
                vus.add((code, ligne))
                cles = _cles_du_contexte(node_context, portee, ligne)
                if cles is None:
                    opaques.append((code, relatif))
                else:
                    analysables.append((code, relatif, cles))
    return analysables, opaques


_ANALYSABLES, _OPAQUES = _collecter()


def test_des_envois_sont_analysables():
    """Cas zéro : si plus rien n'est analysable, ce test ne prouve plus rien."""
    assert _ANALYSABLES, (
        "Aucun envoi d'email analysable trouvé dans app/ — l'analyse AST ne "
        "reconnaît plus les écritures du dépôt, ce test est devenu aveugle."
    )


def test_aucun_envoi_hors_de_portee():
    """Un envoi que l'analyse n'atteint pas est INCONNU, jamais OK.

    Les envois opaques étaient collectés puis jetés : `vigik_accepte`,
    `vigik_refuse`, `compte_active` et `compte_refuse` sont restés hors du
    garde-fou sans qu'aucune ligne rouge ne le dise. C'est la règle 1 du
    CLAUDE.md — « un contrôle qui ne peut pas s'exécuter renvoie INCONNU » —
    appliquée à ce test lui-même.

    Pour lever un blocage : déclarer le contexte en dictionnaire littéral dans
    la fonction d'envoi, plutôt que de le construire de façon indirecte.
    """
    assert not _OPAQUES, (
        "Envois dont le `context` échappe à l'analyse statique : "
        + ", ".join(f"{code} ({fichier})" for code, fichier in sorted(_OPAQUES))
        + ". Ces envois ne sont couverts par AUCUN garde-fou et échoueront en "
        "silence si le contexte diverge du template."
    )


@pytest.mark.parametrize(
    "code,fichier,cles",
    _ANALYSABLES,
    ids=[f"{c}@{f}" for c, f, _ in _ANALYSABLES],
)
def test_le_contexte_fournit_les_variables_du_template(code, fichier, cles):
    attendues = _VARS_CRITIQUES.get(code)
    if attendues is None:
        pytest.skip("template inconnu — couvert par test_email_templates")
    # `annee`, `app` et `residence` sont injectées d'office par send_email.
    manquantes = attendues - cles - BASE_CTX_VARS
    assert not manquantes, (
        f"{fichier} envoie `{code}` sans fournir {sorted(manquantes)} dans son "
        f"`context` (clés présentes : {sorted(cles)}).\n"
        "L'envoi partira en BackgroundTask et échouera en silence : "
        "`'<variable>' is undefined` n'apparaîtra que dans la table "
        "`historique_email`. Aligner le contexte sur le template."
    )
