"""Modifier UN membre du conseil syndical ne doit pas en « recréer » sept.

## 🔴 Le défaut, signalé le 31/08/2026

> *« je n'ai modifié que Christine LONGUÈVE et ça a ajouté tous les membres du
> CS qui n'ont pas été modifiés »*

Sept entrées « Nouveau membre du conseil syndical » au fil d'actualité, pour une
correction d'étage.

`PUT /admin/annuaire/cs` supprimait **toutes** les lignes `membre_cs` et les
recréait, à chaque enregistrement. Deux conséquences, et la seconde est la pire :

  * `cree_le` était remis à l'instant présent — et c'est lui que
    `flux/annuaire.py` compare à `ctx.since` pour décider ce qui est nouveau ;
  * l'`id` de chaque membre changeait à chaque sauvegarde. Rien ne le référence
    aujourd'hui ; toute clé étrangère qui le ferait demain deviendrait orpheline
    sans qu'aucun geste ne l'explique.

⚠️ Le front renvoyait **déjà** l'identifiant : il repasse la liste telle que le
GET la lui a donnée. C'est le schéma `MembreCSIn` qui le jetait. Le défaut n'était
donc pas « on ne peut pas savoir qui est qui » — c'était qu'on refusait de
l'écouter.

## Ce que ce fichier verrouille

Le fil doit dire **ce qui s'est passé** : une modification est une modification,
une arrivée est une arrivée. Un test qui ne vérifierait que « la liste finale est
juste » laisserait revenir le remplacement — c'est bien pour cela qu'aucun des
909 tests existants ne l'a vu.

⚠️ Le gestionnaire est appelé **directement**, sans passer par HTTP : ce qu'on
éprouve est la réconciliation, pas l'authentification (couverte ailleurs). Un
client authentifié n'existe pas dans ce dépôt, et en fabriquer un ici ferait
dépendre ce test d'une chaîne qu'il ne cherche pas à vérifier.
"""
from datetime import datetime, timedelta

import pytest
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models.core import GenreCivilite, MembreCS
from app.routers.admin.annuaire import CompositionCSIn, put_composition_cs


@pytest.fixture()
def session():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        for m in s.exec(select(MembreCS)).all():
            s.delete(m)
        s.commit()
        yield s
        for m in s.exec(select(MembreCS)).all():
            s.delete(m)
        s.commit()


def _poser_le_conseil(session) -> list[MembreCS]:
    """Trois membres, entrés il y a longtemps."""
    ancien = datetime(2020, 1, 1)
    membres = [
        MembreCS(genre=GenreCivilite.mme, prenom="Christine", nom="LONGUEVE",
                 etage=3, ordre=0, cree_le=ancien),
        MembreCS(genre=GenreCivilite.mr, prenom="Marco", nom="RICCI",
                 etage=1, ordre=1, cree_le=ancien),
        MembreCS(genre=GenreCivilite.mr, prenom="Philippe", nom="TRESSARD",
                 etage=2, ordre=2, cree_le=ancien),
    ]
    for m in membres:
        session.add(m)
    session.commit()
    for m in membres:
        session.refresh(m)
    return membres


def _corps(membres) -> dict:
    """Le corps que l'écran renvoie : la liste telle que le GET la lui a rendue."""
    return {
        "ag_annee": 2026,
        "ag_date": None,
        "whatsapp_url": None,
        "membres": [
            {
                "id": m.id,
                "genre": m.genre.value if hasattr(m.genre, "value") else m.genre,
                "prenom": m.prenom,
                "nom": m.nom,
                "batiment_id": m.batiment_id,
                "etage": m.etage,
                "est_president": m.est_president,
                "user_id": m.user_id,
            }
            for m in membres
        ],
    }


def _enregistrer(session, corps: dict) -> None:
    put_composition_cs(CompositionCSIn(**corps), session=session, _=None)


def test_modifier_UN_membre_n_en_recree_aucun_autre(session):
    """Le cas exact du 31/08/2026 : un étage corrigé, les voisins intacts."""
    membres = _poser_le_conseil(session)
    ids_avant = [m.id for m in membres]
    dates_avant = {m.id: m.cree_le for m in membres}

    corps = _corps(membres)
    corps["membres"][0]["etage"] = 4          # seule Christine change
    _enregistrer(session, corps)

    session.expire_all()
    apres = session.exec(select(MembreCS).order_by(MembreCS.ordre)).all()
    assert [m.id for m in apres] == ids_avant, (
        "Les identifiants ont changé : les lignes ont été recréées, pas mises à "
        "jour. C'est ce qui produisait sept « nouveau membre » au fil."
    )
    assert apres[0].etage == 4, "la modification demandée n'a pas été écrite"
    for m in apres:
        assert m.cree_le == dates_avant[m.id], (
            f"`cree_le` de {m.prenom} a été réécrit : le fil d'actualité le lira "
            "comme une arrivée du jour."
        )


def test_un_membre_VRAIMENT_nouveau_est_bien_cree(session):
    """La réconciliation ne doit pas empêcher une arrivée d'exister.

    ⚠️ Sans ce test, on pourrait « corriger » le défaut en ne créant plus jamais
    personne — et le fil serait calme parce qu'il ne se passerait plus rien.
    """
    membres = _poser_le_conseil(session)
    corps = _corps(membres)
    corps["membres"].append({
        "id": None, "genre": "mr", "prenom": "Nouveau", "nom": "VENU",
        "batiment_id": None, "etage": 5, "est_president": False, "user_id": None,
    })
    _enregistrer(session, corps)

    session.expire_all()
    apres = session.exec(select(MembreCS)).all()
    assert len(apres) == 4
    venu = next(m for m in apres if m.nom == "VENU")
    #  Son entrée date d'aujourd'hui : le fil a RAISON de l'annoncer.
    assert venu.cree_le > datetime.utcnow() - timedelta(minutes=5)


def test_un_membre_retire_de_la_liste_quitte_le_conseil(session):
    """L'autre moitié : réconcilier ne veut pas dire ne plus rien supprimer."""
    membres = _poser_le_conseil(session)
    corps = _corps(membres)
    parti = corps["membres"].pop(1)            # Marco s'en va
    _enregistrer(session, corps)

    session.expire_all()
    restants = session.exec(select(MembreCS)).all()
    assert len(restants) == 2
    assert all(m.id != parti["id"] for m in restants)
