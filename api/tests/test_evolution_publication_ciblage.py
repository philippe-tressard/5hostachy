"""Une entrée du fil d'une ACTUALITÉ porte aussi son ciblage et ses options.

## Le besoin (05/09/2026, demandé à l'écran)

> « Pour Actualité, les sections "Options de publication", "Périmètre" et
>   "Destinataires" doivent être visibles même pour chaque commentaire. Tu remets
>   le dernier état pour chacun, et le nouveau sauvegardé deviendra validé. »

Une actualité vit : elle s'épingle quand elle devient urgente, se dépingle quand
elle ne l'est plus, et le moment où on la commente est précisément celui où on
s'en aperçoit. Obliger à rouvrir un autre formulaire pour cela faisait deux
gestes d'un seul.

🔴 **Le risque couvert ici est l'inverse du besoin** — c'est la leçon de
`test_evolution_perimetre.py`, et elle vaut mot pour mot : le besoin est qu'une
valeur enregistrée s'applique ; le risque est qu'un commentaire ordinaire, qui ne
parle de rien de tout cela, vienne **effacer** le ciblage de la publication. Un
`[]` envoyé au lieu d'un `None`, et l'actualité repart à « tout le monde » sans
que personne ne comprenne pourquoi.

⚠️ Ces tests relisent la BASE après l'appel, jamais le code de retour
(`standards/04` §14 — observer la chose, pas son enregistrement).
"""
from __future__ import annotations

import json
import uuid

import pytest
from fastapi import BackgroundTasks
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models.core import (
    Publication,
    PublicationEvolution,
    RoleUtilisateur,
    Utilisateur,
)
from app.routers.publications.evolutions import add_evolution
from app.schemas import EvolutionCreate
from tests.purge_test import purger_ligne

BAT_2 = ["bat:2"]


@pytest.fixture()
def cs() -> Utilisateur:
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        membre = Utilisateur(
            email=f"cs-{uuid.uuid4().hex[:8]}@exemple.test",
            mot_de_passe_hash="x",
            prenom="Camille",
            nom="Sorel",
            role=RoleUtilisateur.conseil_syndical,
        )
        session.add(membre)
        session.commit()
        session.refresh(membre)
        yield membre
        purger_ligne(session, Utilisateur, membre.id)
        session.commit()


def _publication(session: Session, auteur_id: int) -> Publication:
    pub = Publication(
        titre="Coupure d'eau mardi",
        contenu="<p>De 9 h à 12 h.</p>",
        perimetre="residence",
        auteur_id=auteur_id,
        perimetre_cible=json.dumps(BAT_2, ensure_ascii=False),
        public_cible=json.dumps(["résidents"], ensure_ascii=False),
        epingle=False,
        urgente=False,
    )
    session.add(pub)
    session.commit()
    session.refresh(pub)
    return pub


def _nettoyer(session: Session, pub_id: int) -> None:
    for e in session.exec(
        select(PublicationEvolution).where(PublicationEvolution.publication_id == pub_id)
    ).all():
        session.delete(e)
    purger_ligne(session, Publication, pub_id)
    session.commit()


def test_un_commentaire_ordinaire_n_efface_ni_le_ciblage_ni_les_options(cs):
    """🔴 Le cas qui casserait tout : le commentaire qui ne parle de rien.

    Il n'envoie aucun de ces champs. Rien ne doit bouger — ni le périmètre, ni le
    public visé, ni l'épinglage.
    """
    with Session(engine) as session:
        pub = _publication(session, cs.id)
        try:
            add_evolution(
                pub.id,
                EvolutionCreate(type="commentaire", contenu="Merci pour l'info."),
                BackgroundTasks(),
                session=session,
                user=cs,
            )
            relue = session.get(Publication, pub.id)
            assert json.loads(relue.perimetre_cible) == BAT_2
            assert json.loads(relue.public_cible) == ["résidents"]
            assert relue.epingle is False
        finally:
            _nettoyer(session, pub.id)


def test_le_ciblage_enregistre_sur_l_entree_devient_celui_de_la_publication(cs):
    """« Le nouveau sauvegardé deviendra validé » — c'est cette phrase, testée."""
    with Session(engine) as session:
        pub = _publication(session, cs.id)
        try:
            add_evolution(
                pub.id,
                EvolutionCreate(
                    type="commentaire",
                    contenu="Le bâtiment 3 est concerné aussi.",
                    perimetre_cible=["bat:2", "bat:3"],
                    public_cible=["résidents", "copropriétaires"],
                    epingle=True,
                    urgente=True,
                ),
                BackgroundTasks(),
                session=session,
                user=cs,
            )
            relue = session.get(Publication, pub.id)
            assert json.loads(relue.perimetre_cible) == ["bat:2", "bat:3"]
            assert json.loads(relue.public_cible) == ["résidents", "copropriétaires"]
            assert relue.epingle is True
            assert relue.urgente is True
        finally:
            _nettoyer(session, pub.id)


def test_l_invariant_du_confidentiel_est_bien_APPELE_sur_ce_chemin(cs, monkeypatch):
    """Le chemin de l'entrée n'est pas un trou dans la règle du confidentiel.

    Cocher « Confidentiel » sur un périmètre à **portée globale** ne retirerait la
    publication à personne : le drapeau doit se décocher, ici comme dans le
    `PATCH`. La règle elle-même vit dans `appliquer_confidentialite` et elle a ses
    propres tests ; ce qui se vérifie ICI est qu'on l'appelle — c'est le
    branchement qui manquait, pas la règle.

    ⚠️ On ne teste pas son EFFET sur cette base : il dépend de l'arborescence des
    périmètres, qu'un dépôt de test n'a pas forcément. Un test qui dépend d'une
    donnée de référence absente ne prouve rien et finit par être désarmé.
    """
    appels: list[int] = []
    import app.routers.publications.evolutions as module

    monkeypatch.setattr(
        module, "appliquer_confidentialite", lambda pub, session: appels.append(pub.id)
    )
    with Session(engine) as session:
        pub = _publication(session, cs.id)
        try:
            add_evolution(
                pub.id,
                EvolutionCreate(
                    type="commentaire", contenu="À réserver au conseil.", confidentiel=True
                ),
                BackgroundTasks(),
                session=session,
                user=cs,
            )
            assert appels == [pub.id], (
                "sans cet appel, cocher « Confidentiel » depuis un commentaire "
                "afficherait un cadenas sur une publication que tout le monde voit"
            )
        finally:
            _nettoyer(session, pub.id)
