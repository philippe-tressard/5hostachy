"""Un lien de vérification déjà servi ne dit pas « invalide » à qui l'a reçu.

POURQUOI CE TEST (29/09/2026) :

Un compte de test créé en production n'a jamais pu « valider » son adresse :
la page affichait en rouge « Lien de vérification invalide ou expiré. ». Le
journal de Caddy disait pourquoi — trois appels à `/api/auth/verifier-email`
avec le même jeton :

    17:10:10  Azure (Microsoft)   200   ← le scanner de la messagerie
    17:11:09  Cisco Umbrella      400
    17:12:01  le destinataire     400

Les messageries ouvrent les liens reçus dans un vrai navigateur, qui exécute la
page : le jeton, à usage unique, était consommé avant le premier clic humain.
L'adresse ÉTAIT vérifiée ; la page affirmait le contraire. Tout résident sur
Outlook ou Hotmail recevait ce message.

La classe : **un lien à usage unique rejoué par son destinataire légitime**. Ce
test éprouve le rejeu, et le cas zéro — un jeton inconnu reste refusé.
"""

import uuid
from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, select

from app.auth.empreinte_jeton import empreinte
from app.database import engine
from app.models.core import EmailVerificationToken
from app.routers.auth import verify_email
from app.utils import horloge
from tests.aides_base import compte
from tests.conftest import requete_de_test


def _compte_et_lien(session, *, expire_dans=timedelta(hours=24)):
    user = compte(session, prefixe="rejeu", prenom="Test", nom="Rejeu", actif=False)
    brut = uuid.uuid4().hex
    session.add(
        EmailVerificationToken(
            user_id=user.id,
            token=empreinte(brut),
            expires_at=horloge.maintenant() + expire_dans,
        )
    )
    session.commit()
    return user, brut


def _verifier(session, brut):
    return verify_email(requete_de_test("/auth/verifier-email", "GET"), brut, session)


def test_le_second_passage_dit_deja_verifiee():
    """Le défaut exact : le scanner passe, puis le destinataire."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        user, brut = _compte_et_lien(session)
        _verifier(session, brut)  # le scanner
        reponse = _verifier(session, brut)  # le destinataire
        session.refresh(user)

    assert user.email_verifie
    assert "déjà vérifiée" in reponse["message"]


def test_un_lien_expire_d_une_adresse_verifiee_ne_la_dement_pas():
    """Le destinataire qui revient au courriel le lendemain lit la vérité."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _user, brut = _compte_et_lien(session)
        _verifier(session, brut)
        evt = session.exec(
            select(EmailVerificationToken).where(EmailVerificationToken.token == empreinte(brut))
        ).one()
        evt.expires_at = horloge.maintenant() - timedelta(hours=1)
        session.add(evt)
        session.commit()
        reponse = _verifier(session, brut)

    assert "déjà vérifiée" in reponse["message"]


def test_un_lien_expire_non_servi_reste_refuse():
    """Ce que le correctif ne relâche pas : l'expiration d'une adresse NON vérifiée."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        user, brut = _compte_et_lien(session, expire_dans=timedelta(hours=-1))
        with pytest.raises(HTTPException) as exc:
            _verifier(session, brut)
        session.refresh(user)

    assert exc.value.status_code == 400
    assert not user.email_verifie


def test_un_jeton_inconnu_reste_refuse():
    """Le cas zéro : « déjà vérifiée » ne se dit qu'au porteur d'un vrai lien."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        with pytest.raises(HTTPException) as exc:
            _verifier(session, "jeton-que-personne-n-a-recu")

    assert exc.value.status_code == 400
