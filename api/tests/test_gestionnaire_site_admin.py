"""Le gestionnaire du site est un ADMINISTRATEUR, ou personne (#1505, 01/10/2026).

Ce qu'il reçoit — comptes à valider, alertes système, badges à relire — renvoie
à `/admin`, que le front réserve aux administrateurs. Admin › Site laissait le
choisir parmi tous les comptes dotés d'une adresse : un gestionnaire sans le
rôle recevait des boutons qui le renvoyaient au tableau de bord.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.models.core import ConfigSite, RoleUtilisateur
from app.routers.config import save_config
from app.utils.destinataires import site_manager_user_id
from app.utils.email import get_site_manager_notification_email
from tests.aides_base import compte


def _poser(session, gestionnaire_id) -> None:
    session.add(ConfigSite(cle="site_email", valeur="secours@exemple.test"))
    session.add(ConfigSite(cle="site_manager_user_id", valeur=str(gestionnaire_id)))
    session.commit()


def test_un_administrateur_est_lu(session):
    admin = compte(session, prefixe="admin", role=RoleUtilisateur.admin)
    _poser(session, admin.id)
    assert site_manager_user_id(session) == admin.id
    assert get_site_manager_notification_email(session)[0] == admin.email


def test_un_gestionnaire_sans_le_role_retombe_sur_l_adresse_de_secours(session):
    conseiller = compte(session, prefixe="cs", role=RoleUtilisateur.conseil_syndical)
    _poser(session, conseiller.id)
    assert site_manager_user_id(session) is None
    assert get_site_manager_notification_email(session)[0] == "secours@exemple.test"


def test_l_enregistrement_refuse_un_gestionnaire_sans_le_role(session):
    admin = compte(session, prefixe="admin", role=RoleUtilisateur.admin)
    resident = compte(session, prefixe="resident")
    with pytest.raises(HTTPException) as refus:
        save_config({"site_manager_user_id": str(resident.id)}, user=admin, session=session)
    assert refus.value.status_code == 422
    assert session.get(ConfigSite, "site_manager_user_id") is None


@pytest.mark.parametrize("valeur", ["", "admin"])
def test_l_enregistrement_admet_un_administrateur_ou_personne(session, valeur):
    admin = compte(session, prefixe="admin", role=RoleUtilisateur.admin)
    choisi = str(admin.id) if valeur == "admin" else ""
    assert save_config({"site_manager_user_id": choisi}, user=admin, session=session) == {
        "ok": True
    }
    assert session.get(ConfigSite, "site_manager_user_id").valeur == choisi
