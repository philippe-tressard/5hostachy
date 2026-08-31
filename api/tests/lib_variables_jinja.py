"""Quelles variables d'un gabarit d'e-mail FONT ÉCHOUER l'envoi si elles manquent.

Extrait de `test_email_contexte_appel.py` le 31/08/2026, quand le contrôle de
modularité a refusé que ce fichier grossisse. Ce n'est pas un découpage de
confort : il portait **deux analyses de natures différentes** —

  * celle du **gabarit** (Jinja) : ce que le template exige ;
  * celle du **point d'appel** (AST Python) : ce que l'envoi fournit.

La première est ici. Elle ne connaît rien de `app/`, et se relit seule.

⚠️ Le critère est étroit à dessein : `send_email` emploie un `Undefined`
permissif, donc un `{{ x }}` seul rend une chaîne vide et ne casse rien. Seuls
lèvent l'accès à un attribut ou à une clé, et l'itération. Exiger davantage
ferait crier au loup là où rien ne casse — et un garde-fou dont on apprend à
ignorer les alertes ne protège plus rien.
"""
from jinja2 import BaseLoader, nodes
from jinja2.sandbox import SandboxedEnvironment

from tests.test_email_templates import BASE_CTX_VARS

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
    # Sujet et corps sont analysés SÉPARÉMENT puis réunis. Les concaténer
    # laissait un `{% if x %}` du corps « garder » un `{{ x.y }}` du sujet, qui
    # n'est protégé par rien — le sujet est rendu à part, avant le corps.
    # Trouvé le 03/08/2026 : `acces_apparies_auto` déréférence `utilisateur` dans
    # son sujet et le teste dans une condition du corps ; sa clé manquante ne
    # faisait rougir aucun test alors que l'envoi levait bien `UndefinedError`.
    return (
        _risquees_dans(sujet or "")
        | _risquees_dans(corps or "")
    )


def _risquees_dans(source: str) -> set[str]:
    """Variables dont l'absence lève, dans UN fragment de template."""
    arbre = _env_jinja.parse(source)
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
