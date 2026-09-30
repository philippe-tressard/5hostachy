"""`horloge.maintenant()` rend ce que rendait `datetime.utcnow` — ni plus, ni moins (#1047).

🔴 Le piège que ce test verrouille : `datetime.now(timezone.utc)`, le
remplacement que suggère la documentation de Python, rend une date CONSCIENTE.
Toutes les dates lues en base sont NAÏVES, et Python refuse de comparer les
deux — la première comparaison « expiré ? » aurait levé une `TypeError`, en
production, sur un geste que les tests unitaires n'exercent pas tous.
"""

from datetime import datetime, timedelta, timezone

from app.models.core import Utilisateur
from app.utils import horloge
from tests.aides_sources import modules_app


def test_maintenant_est_naif():
    """Pas de fuseau : c'est la forme de toutes les dates en base."""
    assert horloge.maintenant().tzinfo is None


def test_maintenant_est_en_utc():
    """Naïf, mais UTC — pas l'heure locale du serveur."""
    reference = datetime.now(timezone.utc).replace(tzinfo=None)
    assert abs(horloge.maintenant() - reference) < timedelta(seconds=5)


def test_maintenant_se_compare_a_une_date_de_modele():
    """Le cas qui aurait levé : comparer « maintenant » à un `default_factory`."""
    u = Utilisateur(nom="N", prenom="P", email="n@p.fr")
    assert u.cree_le <= horloge.maintenant()


def test_aucune_reference_a_utcnow_dans_app():
    """Ruff `DTZ003` ne voit que les APPELS — pas `default_factory=datetime.utcnow`.

    Sur les 162 écritures remplacées, 51 étaient des références sans
    parenthèses, en `default_factory` de modèle : exactement celles que le
    prochain modèle recopiera, et que Ruff laisserait passer. Ce test lit l'arbre
    et refuse toute mention de l'attribut `utcnow`, appelé ou non.
    """
    import ast

    fautes = []
    for module in modules_app():
        for noeud in ast.walk(module.arbre):
            if isinstance(noeud, ast.Attribute) and noeud.attr in ("utcnow", "utcfromtimestamp"):
                fautes.append(f"app/{module.rel}:{noeud.lineno}")
    assert not fautes, (
        "`datetime.utcnow` est déprécié (Python 3.12) — `horloge.maintenant` :\n"
        + "\n".join(f"  {f}" for f in fautes)
    )


def test_toute_colonne_de_date_est_naive():
    """Chaque colonne de date d'une table est `DateTime(timezone=False)` (#1412).

    Depuis sqlmodel 0.0.45, un champ annoté `datetime` devient une colonne
    CONSCIENTE du fuseau, qui REFUSE à l'écriture la date naïve que rend
    `horloge.maintenant()` — « Datetime values must have timezone information ».
    Un champ oublié ne se verrait qu'au premier enregistrement, en production.
    La date d'un modèle s'annote donc `NaiveDatetime` (pydantic).
    """
    import app.models.core  # noqa: F401 — enregistre toutes les tables
    from sqlalchemy import DateTime
    from sqlmodel import SQLModel

    conscientes = [
        f"{table.name}.{colonne.name}"
        for table in SQLModel.metadata.tables.values()
        for colonne in table.columns
        if isinstance(colonne.type, DateTime) and colonne.type.timezone
    ]
    dates = [
        colonne
        for table in SQLModel.metadata.tables.values()
        for colonne in table.columns
        if isinstance(colonne.type, DateTime)
    ]
    assert dates, "aucune colonne de date lue : le contrôle ne mesure rien"
    assert not conscientes, f"colonnes de date conscientes du fuseau : {conscientes}"
