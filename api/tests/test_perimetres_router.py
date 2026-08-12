"""`GET /perimetres` — le router, qui n'était couvert par aucun test.

Livré sans test dans la v2.55.0, il a répondu **500 en production** dès le premier
appel : `_codes_cites` dépaquetait `(valeur,)` alors que
`session.exec(select(<colonne>))` rend des scalaires. `ValueError: too many values
to unpack` tombait sur toute chaîne de plus d'un caractère — donc sur toutes.

Le lot portait 23 tests sur les RÈGLES (voir `test_perimetres_arbre.py`) et aucun
sur le chemin qui les sert. Fichier séparé pour que cette distinction reste
visible : les règles d'un côté, le point d'entrée de l'autre.

La vérification en navigateur, elle, avait bien exercé l'écran — mais sur une base
fraîchement semée où aucun contenu ne citait de périmètre, si bien que la boucle
fautive n'était jamais atteinte. Ces tests écrivent donc du contenu AVANT de lire.
"""
from datetime import datetime

import pytest
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models.core import (
    Batiment,
    Copropriete,
    Evenement,
    Publication,
    TypeEvenement,
    Utilisateur,
)
from app.models.perimetre import Perimetre
from app.routers.patrimoine import _codes_cites, _en_lecture
from app.seed.patrimoine import poser_arborescence
from app.utils import perimetres as P


def _vider(session: Session) -> None:
    for modele in (Publication, Evenement, Perimetre, Batiment, Copropriete):
        for ligne in session.exec(select(modele)).all():
            session.delete(ligne)
    session.commit()


@pytest.fixture()
def batiments() -> list[int]:
    """Arbre semé sur quatre bâtiments réels. Renvoie leurs identifiants."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _vider(session)
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
    P.invalider_cache()


def _auteur(session: Session) -> int:
    """`Publication.auteur_id` et `Evenement.auteur_id` sont NOT NULL."""
    existant = session.exec(
        select(Utilisateur).where(Utilisateur.email == "auteur@test.fr")
    ).first()
    if existant:
        return existant.id
    u = Utilisateur(nom="A", prenom="B", email="auteur@test.fr", actif=True)
    session.add(u)
    session.commit()
    return u.id


def test_lecture_de_l_arborescence_par_le_router(batiments):
    """`GET /perimetres` rend l'arbre — le contrôle qui manquait.

    Livré sans test, ce router a répondu **500 en production** dès le premier
    appel : `_codes_cites` dépaquetait `(valeur,)` alors que
    `session.exec(select(<colonne>))` rend des scalaires, et `ValueError: too many
    values to unpack` tombait sur toute chaîne de plus d'un caractère — donc sur
    toutes. L'écran d'administration restait vide et les libellés retombaient sur
    leur calcul de repli.

    Les tests portaient sur les règles, jamais sur le chemin qui les sert : un
    module entier était hors de portée, et rien ne le signalait.
    """

    with Session(engine) as session:
        auteur = _auteur(session)
        #  Un contenu qui cite deux périmètres, pour que `utilise` ait à les trouver
        #  dans les deux formats stockés (JSON et CSV).
        session.add(Publication(titre="T", contenu="C", auteur_id=auteur,
                                perimetre_cible='["aful", "bat:%d"]' % batiments[0]))
        session.commit()

        cites = _codes_cites(session)
        assert "aful" in cites
        assert f"bat:{batiments[0]}" in cites

        lus = _en_lecture(list(session.exec(select(Perimetre)).all()), cites)

    assert len(lus) == 63, f"63 nœuds semés, {len(lus)} rendus"

    par_code = {n.code: n for n in lus}
    #  L'ordre est un parcours en profondeur : un enfant suit son parent.
    assert lus[0].code == "résidence"
    assert par_code["bat:%d/hall" % batiments[0]].profondeur == 2
    assert par_code["bat:%d/hall" % batiments[0]].parent == f"bat:{batiments[0]}"
    #  Héritage de la portée : le portail du parking concerne tout le monde.
    assert par_code["parking/portail"].concerne_tous is True
    assert par_code["parking/portail"].portee_globale is False
    #  Un espace de bâtiment ne concerne pas tout le monde.
    assert par_code["bat:%d/hall" % batiments[0]].concerne_tous is False
    #  `utilise` distingue ce qui est cité de ce qui ne l'est pas.
    assert par_code["aful"].utilise is True
    assert par_code["cheminements"].utilise is False


def test_codes_cites_lit_les_trois_formats_de_stockage(batiments):
    """JSON, CSV et champ vide : les cinq entités n'écrivent pas pareil."""

    with Session(engine) as session:
        auteur = _auteur(session)
        session.add(Publication(titre="J", contenu="C", auteur_id=auteur,
                                perimetre_cible='["parking"]'))
        session.add(Evenement(titre="E", type=TypeEvenement.travaux, auteur_id=auteur,
                              debut=datetime(2026, 8, 12, 9, 0),
                              perimetre="espaces-verts,cheminements"))
        session.commit()
        cites = _codes_cites(session)

    assert {"parking", "espaces-verts", "cheminements"} <= cites
