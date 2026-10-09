"""Modifier UN membre d'un annuaire — conseil ou syndic — ne doit pas recréer les autres.

## 🔴 La récidive, signalée le 09/10/2026 (syndic)

Le correctif du 31/08 (ci-dessous) avait été écrit DANS le routeur du conseil.
Le syndic, quarante lignes plus bas, supprimait et recréait encore tous ses
membres : deux interlocutrices inchangées sont réapparues au fil comme
« Nouveau membre du syndic » le jour où un troisième changeait. La règle vit
désormais dans `utils/annuaire.reconcilier_membres`, et ce fichier éprouve les
DEUX annuaires. Le même jour, le titre du fil prend la civilité (« Mr »), que
la carte de l'annuaire portait déjà.

## 🔴 Le défaut, signalé le 31/08/2026

> *« je n'ai modifié que Christine VERDIÈRE et ça a ajouté tous les membres du
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
from app.models.core import GenreCivilite, MembreCS, MembreSyndic
from app.routers.admin.annuaire import (
    CompositionCSIn,
    SyndicIn,
    put_composition_cs,
    put_syndic_info,
)
from app.routers.flux import annuaire as flux_annuaire
from app.routers.flux.commun import ContexteFlux
from app.utils.horloge import maintenant


@pytest.fixture()
def session():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        _vider(s)
        yield s
        _vider(s)


def _vider(s) -> None:
    for modele in (MembreCS, MembreSyndic):
        for m in s.exec(select(modele)).all():
            s.delete(m)
    s.commit()


def _poser_le_conseil(session) -> list[MembreCS]:
    """Trois membres, entrés il y a longtemps."""
    ancien = datetime(2020, 1, 1)
    membres = [
        MembreCS(
            genre=GenreCivilite.mme,
            prenom="Christine",
            nom="VERDIERE",
            etage=3,
            ordre=0,
            cree_le=ancien,
        ),
        MembreCS(
            genre=GenreCivilite.mr, prenom="Marco", nom="ROSSI", etage=1, ordre=1, cree_le=ancien
        ),
        MembreCS(
            genre=GenreCivilite.mr,
            prenom="Paul",
            nom="DELMAS",
            etage=2,
            ordre=2,
            cree_le=ancien,
        ),
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
    corps["membres"][0]["etage"] = 4  # seule Christine change
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
    corps["membres"].append(
        {
            "id": None,
            "genre": "mr",
            "prenom": "Nouveau",
            "nom": "VENU",
            "batiment_id": None,
            "etage": 5,
            "est_president": False,
            "user_id": None,
        }
    )
    _enregistrer(session, corps)

    session.expire_all()
    apres = session.exec(select(MembreCS)).all()
    assert len(apres) == 4
    venu = next(m for m in apres if m.nom == "VENU")
    #  Son entrée date d'aujourd'hui : le fil a RAISON de l'annoncer.
    assert venu.cree_le > maintenant() - timedelta(minutes=5)


def test_un_membre_retire_de_la_liste_quitte_le_conseil(session):
    """L'autre moitié : réconcilier ne veut pas dire ne plus rien supprimer."""
    membres = _poser_le_conseil(session)
    corps = _corps(membres)
    parti = corps["membres"].pop(1)  # Marco s'en va
    _enregistrer(session, corps)

    session.expire_all()
    restants = session.exec(select(MembreCS)).all()
    assert len(restants) == 2
    assert all(m.id != parti["id"] for m in restants)


# ── Le syndic — la récidive du 09/10/2026 ─────────────────────────────────────


def _poser_le_syndic(session) -> list[MembreSyndic]:
    """Trois interlocuteurs, entrés il y a longtemps."""
    ancien = datetime(2020, 1, 1)
    membres = [
        MembreSyndic(
            genre=GenreCivilite.mme,
            prenom="Elise",
            nom="MERCIER",
            fonction="Comptable de copropriété",
            telephone="0102030405",
            ordre=0,
            cree_le=ancien,
        ),
        MembreSyndic(
            genre=GenreCivilite.mme,
            prenom="Odile",
            nom="SOREL",
            fonction="Assistante de gestion",
            telephone="0102030406",
            ordre=1,
            cree_le=ancien,
        ),
        MembreSyndic(
            genre=GenreCivilite.mr,
            prenom="Bruno",
            nom="RENARD",
            fonction="Gestionnaire",
            telephone="0102030407",
            est_principal=True,
            ordre=2,
            cree_le=ancien,
        ),
    ]
    for m in membres:
        session.add(m)
    session.commit()
    for m in membres:
        session.refresh(m)
    return membres


def _corps_syndic(membres) -> dict:
    """Le corps que `AnnuaireSyndic.svelte` envoie, identifiant compris."""
    return {
        "nom_syndic": "",
        "adresse": "",
        "site_web": None,
        "membres": [
            {
                "id": m.id,
                "genre": m.genre.value if hasattr(m.genre, "value") else m.genre,
                "prenom": m.prenom,
                "nom": m.nom,
                "fonction": m.fonction,
                "email": m.email,
                "telephone": m.telephone,
                "est_principal": m.est_principal,
                "user_id": m.user_id,
            }
            for m in membres
        ],
    }


def _enregistrer_syndic(session, corps: dict) -> None:
    put_syndic_info(SyndicIn(**corps), session=session, _=None)


def test_syndic_remplacer_UN_membre_ne_recree_pas_les_autres(session):
    """Le cas exact du 09/10/2026 : le gestionnaire change, ses deux collègues non."""
    membres = _poser_le_syndic(session)
    gardes = {m.id: m.cree_le for m in membres[:2]}

    corps = _corps_syndic(membres)
    corps["membres"][2] = {
        "id": None,
        "genre": "Mr",
        "prenom": "",
        "nom": "LEROY",
        "fonction": "Gestionnaire de copropriétés",
        "email": None,
        "telephone": "0102030408",
        "est_principal": True,
        "user_id": None,
    }
    _enregistrer_syndic(session, corps)

    session.expire_all()
    apres = {m.id: m for m in session.exec(select(MembreSyndic)).all()}
    assert len(apres) == 3
    for id_, cree_le in gardes.items():
        assert id_ in apres, "un membre inchangé a été recréé : son entrée au fil reviendra"
        assert apres[id_].cree_le == cree_le, "`cree_le` réécrit : le fil le lira comme une arrivée"
    assert membres[2].id not in apres, "le membre remplacé n'a pas quitté l'annuaire"
    venu = next(m for m in apres.values() if m.nom == "LEROY")
    assert venu.cree_le > maintenant() - timedelta(minutes=5)


def test_syndic_modifier_UN_membre_le_met_a_jour_en_place(session):
    membres = _poser_le_syndic(session)
    corps = _corps_syndic(membres)
    corps["membres"][1]["fonction"] = "Assistante de copropriété"
    _enregistrer_syndic(session, corps)

    session.expire_all()
    apres = session.exec(select(MembreSyndic).order_by(MembreSyndic.ordre)).all()
    assert [m.id for m in apres] == [m.id for m in membres]
    assert apres[1].fonction == "Assistante de copropriété"
    assert all(m.cree_le == datetime(2020, 1, 1) for m in apres)


def test_le_fil_n_annonce_que_l_arrivee_et_porte_la_civilite(session):
    """Ce que le résident voit : une seule carte, « Mr LEROY »."""
    membres = _poser_le_syndic(session)
    corps = _corps_syndic(membres)
    corps["membres"][2] = {**corps["membres"][2], "id": None, "prenom": "", "nom": "Leroy"}
    _enregistrer_syndic(session, corps)

    maintenant_ = maintenant()
    ctx = ContexteFlux(
        session=session, user=None, now=maintenant_, since=maintenant_ - timedelta(days=7)
    )
    cartes = flux_annuaire.collecter(ctx)
    assert [c.titre for c in cartes] == ["Mr LEROY"], (
        "le fil doit n'annoncer que le membre arrivé, civilité comprise"
    )
