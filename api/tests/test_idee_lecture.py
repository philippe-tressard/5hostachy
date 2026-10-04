# SPDX-FileCopyrightText: 2026 Philippe Tressard
# SPDX-License-Identifier: LicenseRef-5Hostachy
"""La liste des idées rend CE QUE LA TABLE PORTE (#1660).

## Le défaut

`GET /idees` assemblait chaque idée dans un dictionnaire écrit à la main
(`_enrich`) : `assiste_ia`, posé à la création et à la correction, n'en sortait
pas. L'écran (`ListeIdees`) lit pourtant `idee.assiste_ia` pour afficher la marque
« rédigé avec l'assistant » — qui ne s'est donc **jamais** affichée. Rien ne
l'a signalé : une clé absente d'un dictionnaire vaut `undefined`, pas une erreur.

`test_lecture_colonne_par_colonne` ne le voyait pas : il lit la FORME d'un appel
à un schéma Pydantic, et un dictionnaire n'en est pas un. `test_assiste_ia`
affirmait en commentaire que l'idée « rend le modèle » — sans le vérifier.

## Ce que ce test refuse

Une colonne de `Idee` que la lecture ne rend pas. La seule colonne qui n'y est
pas est déclarée avec sa raison, et le test échoue si l'exception cesse de servir.
"""

from __future__ import annotations

import pytest

from app.models.core import Idee, RoleUtilisateur
from app.routers.idees import IdeeCreate, create_idee, list_idees
from tests.aides_base import compte

#: Les colonnes de la table que la liste ne porte pas, avec leur raison.
NON_RENDUES: dict[str, str] = {
    "statut_change_le": (
        "interne : elle ne sert qu'à dater l'archivage, dont la liste ne rend "
        "que la conséquence (`archivee`)"
    ),
}


@pytest.fixture()
def conseiller(session):
    return compte(session, prefixe="conseil", role=RoleUtilisateur.conseil_syndical)


def _lire(session, user) -> dict:
    lues = list_idees(session=session, user=user)
    assert len(lues) == 1, lues
    return lues[0]


def test_la_liste_rend_chaque_colonne_de_la_table(session, conseiller):
    create_idee(
        IdeeCreate(titre="Local vélos", description="<p>À couvrir.</p>", assiste_ia=True),
        session=session,
        user=conseiller,
    )
    lue = _lire(session, conseiller)
    manquantes = sorted(set(Idee.model_fields) - set(NON_RENDUES) - set(lue))
    assert not manquantes, (
        f"colonne(s) de `idee` absente(s) de GET /idees : {manquantes} — "
        "l'écran les lit comme `undefined`, sans erreur (#1660)"
    )


def test_la_marque_assistee_par_l_ia_atteint_la_liste(session, conseiller):
    create_idee(
        IdeeCreate(titre="Avec l'assistant", description="<p>Texte.</p>", assiste_ia=True),
        session=session,
        user=conseiller,
    )
    assert _lire(session, conseiller)["assiste_ia"] is True


def test_une_idee_sans_assistant_n_a_pas_la_marque(session, conseiller):
    create_idee(
        IdeeCreate(titre="À la main", description="<p>Texte.</p>"),
        session=session,
        user=conseiller,
    )
    assert _lire(session, conseiller)["assiste_ia"] is False


def test_les_exceptions_servent_encore():
    inutiles = sorted(set(NON_RENDUES) - set(Idee.model_fields))
    assert not inutiles, f"exception(s) sur une colonne qui n'existe plus : {inutiles}"
