"""La liste des prestataires se lit par ordre alphabétique (#1145, 22/09/2026).

« Si lors de la sélection d'un prestataire (tri par ordre alphabétique) celui-ci
n'existe pas… » — on cherche une entreprise par son nom ; l'ordre d'insertion
n'aidait personne. Sans tenir compte de la casse.
"""

from __future__ import annotations

import uuid

from app.models.prestataires import Prestataire
from app.routers.prestataires import list_prestataires
from tests.aides_badges import _compte, session  # noqa: F401 — `session` est une fixture


def test_la_liste_est_alphabetique_sans_tenir_compte_de_la_casse(session):
    suffixe = uuid.uuid4().hex[:6]
    noms = [f"zeta {suffixe}", f"Alpha {suffixe}", f"mu {suffixe}"]
    for nom in noms:
        session.add(Prestataire(nom=nom, specialite="plomberie"))
    session.commit()
    lus = [
        p.nom
        for p in list_prestataires(session=session, _=_compte(session, "Cs"))
        if p.nom.endswith(suffixe)
    ]
    #  Témoin : les trois sont bien là, sinon l'ordre d'une liste vide passerait.
    assert sorted(lus) == sorted(noms)
    assert lus == sorted(noms, key=str.lower)
