"""Un schéma de sortie se lit SUR le modèle, il ne recopie pas ses colonnes (#1563).

## Le défaut

Construire un schéma champ par champ depuis un objet :

    return LotRead(id=lot.id, numero=lot.numero, etage=lot.etage, …)

Tout champ déclaré au schéma et oublié dans l'appel prend sa valeur par défaut,
sans un mot. #1092 l'a corrigé pour `TicketRead` (`debut`, `fin`, `suivi_kanban`,
`epingle`, `assiste_ia` perdus) et n'a gardé que lui
(`test_ticket_read_rend_le_modele.py`, qui relit le modèle en vrai). L'audit du
02/10/2026 a trouvé huit autres lectures de la même forme — dont deux écrites
deux fois —, et l'une perdait déjà `assiste_ia` et `contenu_origine`.

## Ce que ce contrôle refuse

Un appel à un **schéma de l'application** (classe Pydantic définie sous `app/`,
qui n'est pas une table) portant au moins `SEUIL` mots-clés de la forme
`champ=objet.champ` tirés d'un MÊME objet. La forme attendue est
`utils/lecture.lire_objet(Schema, objet, **champs_dérivés)` — ou
`Schema.model_validate(objet)` quand rien ne se calcule.

## Pourquoi cinq

C'est le relevé de l'audit. Sous ce seuil, les appels trouvés assemblent une
réponse à partir d'un CALCUL (un résultat de recherche, une proposition de
l'assistant) et non un objet stocké qu'on rend : les signaler apprendrait à
ignorer le contrôle. Une table construite depuis un corps de requête
(`Ticket(titre=body.titre, …)`) n'est pas concernée : c'est une écriture.

⚠️ Ce contrôle lit la FORME. Il ne voit pas une recopie par `getattr` ou par
un dictionnaire ; ce que la lecture rend vraiment, c'est
`test_lectures_rendent_le_modele.py` qui le relit.
"""

from __future__ import annotations

import ast
from collections import Counter

from tests.aides_sources import modules_app

SEUIL = 5

#: Les constructions colonne par colonne ADMISES, par `"module::Schéma"`, avec
#: leur raison. Vide : chaque entrée doit servir, ou le test échoue.
EXCEPTIONS: dict[str, str] = {}

_RACINES = {"BaseModel", "SQLModel"}


def _nom(noeud: ast.expr) -> str | None:
    if isinstance(noeud, ast.Name):
        return noeud.id
    if isinstance(noeud, ast.Attribute):
        return noeud.attr
    return None


def _est_table(classe: ast.ClassDef) -> bool:
    return any(
        k.arg == "table" and isinstance(k.value, ast.Constant) and k.value.value is True
        for k in classe.keywords
    )


def schemas_definis(arbres) -> set[str]:
    """Les noms des classes Pydantic NON-tables définies dans ces modules.

    Une classe est un schéma si l'une de ses bases est `BaseModel`, `SQLModel`
    ou un schéma, et si elle ne se déclare pas `table=True`. Un nom défini deux
    fois n'est un schéma que si aucune de ses définitions n'est une table.
    """
    bases: dict[str, set[str]] = {}
    tables: set[str] = set()
    for arbre in arbres:
        for n in ast.walk(arbre):
            if isinstance(n, ast.ClassDef):
                bases.setdefault(n.name, set()).update(filter(None, map(_nom, n.bases)))
                if _est_table(n):
                    tables.add(n.name)

    connus: dict[str, bool] = {}

    def est_schema(nom: str, en_cours: frozenset = frozenset()) -> bool:
        if nom in connus:
            return connus[nom]
        if nom in tables or nom not in bases or nom in en_cours:
            return False
        r = any(b in _RACINES or est_schema(b, en_cours | {nom}) for b in bases[nom])
        connus[nom] = r
        return r

    return {nom for nom in bases if est_schema(nom)}


def recopies(arbre: ast.AST, schemas: set[str], seuil: int = SEUIL):
    """`(ligne, schéma, objet, nombre)` pour chaque construction colonne par colonne."""
    for n in ast.walk(arbre):
        if not isinstance(n, ast.Call) or _nom(n.func) not in schemas:
            continue
        par_objet = Counter(
            k.value.value.id
            for k in n.keywords
            if k.arg
            and isinstance(k.value, ast.Attribute)
            and k.value.attr == k.arg
            and isinstance(k.value.value, ast.Name)
        )
        for objet, nombre in par_objet.items():
            if nombre >= seuil:
                yield n.lineno, _nom(n.func), objet, nombre


def _releve() -> tuple[set[str], list[tuple[str, str]]]:
    modules = modules_app()
    schemas = schemas_definis(m.arbre for m in modules)
    trouves = sorted(
        (
            f"{m.rel}::{schema}",
            f"{m.rel}:{ligne} — {schema}(…) recopie {nombre} champs de `{objet}`",
        )
        for m in modules
        for ligne, schema, objet, nombre in recopies(m.arbre, schemas)
    )
    return schemas, trouves


# ── Cas zéro et cas témoin : le contrôle mesure quelque chose ─────────────────


def test_le_releve_porte_sur_les_schemas_de_l_application():
    schemas, _ = _releve()
    assert len(schemas) >= 100, f"{len(schemas)} schéma(s) reconnus : la résolution a cassé."
    #  Des schémas connus, et une table qui ne doit PAS en être.
    assert {"TicketRead", "LotRead", "PerimetreRead", "AccesOut", "LocataireInfo"} <= schemas
    assert "Ticket" not in schemas and "Lot" not in schemas


_TEMOIN = """
from pydantic import BaseModel
from sqlmodel import SQLModel

class Base(BaseModel):
    pass

class ChoseRead(Base):
    pass

class Chose(SQLModel, table=True):
    pass

def lire(c, body):
    a = ChoseRead(id=c.id, nom=c.nom, code=c.code, ordre=c.ordre, actif=c.actif, x=f(c))
    b = ChoseRead(id=c.id, nom=c.nom, code=c.code, ordre=c.ordre, actif=c.autre)
    t = Chose(id=body.id, nom=body.nom, code=body.code, ordre=body.ordre, actif=body.actif)
    d = lire_objet(ChoseRead, c, x=f(c))
    return a, b, t, d
"""


def test_le_temoin_est_vu_et_le_reste_ne_l_est_pas():
    arbre = ast.parse(_TEMOIN)
    schemas = schemas_definis([arbre])
    assert schemas == {"Base", "ChoseRead"}, schemas
    #  Seul `a` : `b` n'en recopie que quatre (`actif=c.autre` n'est pas une
    #  recopie), `t` construit une table, `d` est la forme attendue.
    assert [(s, o, n) for _, s, o, n in recopies(arbre, schemas)] == [("ChoseRead", "c", 5)]


# ── La règle ──────────────────────────────────────────────────────────────────


def test_aucun_schema_construit_colonne_par_colonne():
    _, trouves = _releve()
    fautifs = [ligne for cle, ligne in trouves if cle not in EXCEPTIONS]
    assert not fautifs, (
        "Schéma(s) construit(s) en recopiant les colonnes d'un objet :\n  "
        + "\n  ".join(fautifs)
        + "\n\n  Un champ oublié part à sa valeur par défaut sans un mot (#1092, #1563). "
        "Lire sur l'objet : `lire_objet(Schema, objet, **champs_dérivés)` "
        "(`app/utils/lecture.py`), et ne nommer que ce qui se CALCULE."
    )


def test_chaque_exception_sert_encore():
    _, trouves = _releve()
    vus = {cle for cle, _ in trouves}
    mortes = sorted(set(EXCEPTIONS) - vus)
    assert not mortes, f"Exception(s) qui ne servent plus — les retirer : {mortes}"
