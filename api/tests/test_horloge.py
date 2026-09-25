"""`horloge.maintenant()` rend ce que rendait `utcnow()` — ni plus, ni moins (#1047).

🔴 Le piège que ce test verrouille : `datetime.now(timezone.utc)`, le
remplacement que suggère la documentation de Python, rend une date CONSCIENTE.
Toutes les dates lues en base sont NAÏVES, et Python refuse de comparer les
deux — la première comparaison « expiré ? » aurait levé une `TypeError`, en
production, sur un geste que les tests unitaires n'exercent pas tous.
"""

from datetime import datetime, timedelta, timezone

from app.models.core import Utilisateur
from app.utils import horloge


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
    from pathlib import Path

    racine = Path(__file__).resolve().parents[1] / "app"
    fautes = []
    for fichier in sorted(racine.rglob("*.py")):
        arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Attribute) and noeud.attr in ("utcnow", "utcfromtimestamp"):
                fautes.append(f"app/{fichier.relative_to(racine).as_posix()}:{noeud.lineno}")
    assert not fautes, (
        "`datetime.utcnow` est déprécié (Python 3.12) — `horloge.maintenant` :\n"
        + "\n".join(f"  {f}" for f in fautes)
    )
