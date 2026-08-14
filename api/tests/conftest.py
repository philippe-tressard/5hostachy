"""Configuration pytest — variables d'environnement minimales avant import de l'app.

L'import de `app.config` exige un SECRET_KEY ≥ 32 caractères et `app.database`
instancie un engine depuis `database_url`. On fournit des valeurs neutres pour
que les tests s'exécutent sans .env ni base réelle (aucun test ici ne se
connecte à la base : ils lisent les templates et la chaîne de migrations).
"""
import os
import tempfile

os.environ.setdefault("SECRET_KEY", "x" * 40)
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ENABLE_API_DOCS", "false")

#  Importer `app.main` monte `/uploads` en statique et crée le répertoire au
#  passage. Sans redirection, ce `mkdir` vise un chemin absolu de conteneur —
#  il échoue sur un poste Windows comme sur un exécuteur d'intégration continue,
#  et rendait l'application entière intestable. Cf. tests/test_demarrage.py.
os.environ.setdefault(
    "UPLOADS_DIR", os.path.join(tempfile.gettempdir(), "hostachy-tests-uploads")
)

import pytest  # noqa: E402  (après les variables d'environnement, par construction)


# ── Patrimoine de test ────────────────────────────────────────────────────────
#
#  Monter une copropriété de quatre bâtiments et semer l'arbre des périmètres :
#  ce montage était écrit **deux fois** à l'identique (`test_perimetres_arbre.py`
#  et `test_perimetres_router.py`), et un troisième fichier venait d'en avoir
#  besoin (14/08/2026). Une fixture recopiée diverge comme n'importe quel autre
#  code — les deux `_vider` avaient d'ailleurs déjà divergé sur les modèles
#  qu'ils purgent.
#
#  Les imports sont **différés dans le corps** et non en tête de ce fichier :
#  `conftest.py` est chargé avant tous les tests, y compris ceux qui ne touchent
#  jamais la base, et importer l'application ici changerait leur ordre d'import.


def vider_patrimoine(session, modeles_sup=()) -> None:
    """Purge copropriété, bâtiments et périmètres — plus les modèles demandés.

    Le marqueur de semis part avec : sans lui, `poser_arborescence` se croirait
    déjà passée et laisserait les tests sur une base vide.
    """
    from sqlmodel import select

    from app.models.core import Batiment, ConfigSite, Copropriete
    from app.models.perimetre import Perimetre
    from app.seed.patrimoine import CLE_SEMEE

    marqueur = session.get(ConfigSite, CLE_SEMEE)
    if marqueur:
        session.delete(marqueur)
    for modele in (*modeles_sup, Perimetre, Batiment, Copropriete):
        for ligne in session.exec(select(modele)).all():
            session.delete(ligne)
    session.commit()


@pytest.fixture()
def batiments() -> list[int]:
    """Arbre semé sur quatre bâtiments réels. Renvoie leurs identifiants."""
    from sqlmodel import Session, SQLModel, select

    from app.database import engine
    from app.models.core import Batiment, Copropriete
    from app.seed.patrimoine import poser_arborescence
    from app.utils import perimetres as P

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        vider_patrimoine(session)
        copro = Copropriete(nom="Test", adresse="1 rue Test")
        session.add(copro)
        session.flush()
        for numero in ("1", "2", "3", "4"):
            session.add(Batiment(copropriete_id=copro.id, numero=numero))
        session.commit()
        ids = list(session.exec(select(Batiment.id).order_by(Batiment.id)).all())
        poser_arborescence(session)
        session.commit()
    P.invalider_cache()
    yield ids
    #  Le patrimoine repart AUSSI à la sortie. Il ne partait qu'à l'entrée, si
    #  bien que la copropriété et ses quatre bâtiments survivaient au test et
    #  attendaient le suivant : `test_copropriete_fiche.py` supprime toutes les
    #  copropriétés dans sa propre fixture, et SQLAlchemy dénoue alors les
    #  bâtiments orphelins (`UPDATE batiment SET copropriete_id = NULL`) — la
    #  colonne est NOT NULL, six tests tombaient en erreur de montage.
    #  Le défaut ne s'est vu qu'en ajoutant un fichier qui trie AVANT
    #  `test_copropriete_fiche` (15/08/2026) : jusque-là, les deux seuls usagers
    #  de cette fixture passaient après lui. Un test dont le résultat dépend de
    #  l'ordre alphabétique des fichiers n'est pas un test.
    with Session(engine) as session:
        vider_patrimoine(session)
    P.invalider_cache()


@pytest.fixture()
def arbre_vide():
    """Aucun périmètre configuré — l'état d'une copropriété qui n'a rien saisi.

    C'est un état **valide** et non une panne : le produit doit servir une
    copropriété qui n'a ni AFUL, ni quatre bâtiments. Tout ce qui lit l'arbre doit
    donc se comporter correctement quand il est vide.
    """
    from sqlmodel import Session, SQLModel

    from app.database import engine
    from app.utils import perimetres as P

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        vider_patrimoine(session)
    P.invalider_cache()
    yield
    P.invalider_cache()
