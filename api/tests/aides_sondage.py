"""La base des tests de sondage — patrimoine semé, puis tout ce qu'ils écrivent purgé.

`test_sondage_cloture_unique.py` et `test_sondage_correction.py` portaient la
même fixture `base`, recopiée à l'identique à la liste des modèles purgés près,
et chacun sa fabrique de compte. Un fichier de tests ne s'importe pas depuis un
autre — `test_aides_de_tests_source_unique.py` le refuse — : ce qu'ils
partagent vit ici (#1495). Les comptes passent par `aides_base.compte`.

`base` est une fixture : un fichier de tests l'IMPORTE pour que pytest la
trouve (même forme qu'`aides_affaire.session`).
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel

from app.database import engine
from app.models.communaute import OptionSondage, Sondage, VoteSondage
from app.models.core import Batiment, Copropriete, Lot, Utilisateur
from app.seed.patrimoine import poser_arborescence
from app.utils import perimetres as P
from tests.aides_purge import vider_patrimoine

#: Ce que les tests de sondage écrivent, et que la fixture purge avant et après.
#: Votes et options d'abord : ils référencent le sondage.
MODELES_ECRITS = (VoteSondage, OptionSondage, Sondage, Lot, Utilisateur)


@pytest.fixture()
def base():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        vider_patrimoine(session, MODELES_ECRITS)
        copro = Copropriete(nom="Test sondage", adresse="1 rue Test")
        session.add(copro)
        session.flush()
        session.add(Batiment(copropriete_id=copro.id, numero="1"))
        session.commit()
        poser_arborescence(session)
        session.commit()
        P.invalider_cache()
        yield session
        vider_patrimoine(session, MODELES_ECRITS)
    P.invalider_cache()
