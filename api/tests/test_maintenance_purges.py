"""Les purges hebdomadaires s'exécutent DANS l'API, derrière la clé (#1232).

`maintenance.sh` purgeait cinq tables chaque dimanche par `docker exec
hostachy_api python -c "from app.database import engine …"`, API en marche :
un process tiers qui ouvre `app.db`, la règle d'or enfreinte. Il appelle
désormais `POST /admin/maintenance/purges`, qui passe par `utils.maintenance.
purger` — la même fonction que la maintenance lancée depuis l'administration.

Ce que ces tests verrouillent :
1. sans clé, ou avec une mauvaise, la route refuse — et ne purge rien ;
2. avec la clé, elle purge VRAIMENT (un jeton expiré part, un valide reste)
   et rend les comptes que le script écrit dans son rapport.

`test_acces_base_scripts.py` tient l'autre moitié : plus aucun script
n'importe `app.database`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.config import get_settings
from app.main import app
from app.models.core import RoleUtilisateur, Utilisateur
from app.models.jetons import RefreshToken

CLE = "cle-de-test-des-purges"
ROUTE = "/admin/maintenance/purges"


@pytest.fixture(name="moteur")
def moteur_fixture(monkeypatch):
    moteur = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(moteur)
    #  `purger` lit le moteur du module : c'est lui qu'on remplace, pas une
    #  dépendance FastAPI — la fonction sert aussi hors requête.
    monkeypatch.setattr("app.utils.maintenance.engine", moteur)
    monkeypatch.setattr(get_settings(), "maintenance_key", CLE)
    return moteur


def _jetons(moteur) -> list[str]:
    with Session(moteur) as s:
        user = Utilisateur(
            email="m@test.fr",
            hashed_password="x",
            nom="M",
            prenom="M",
            roles_json=RoleUtilisateur.résident.value,
        )
        s.add(user)
        s.commit()
        s.refresh(user)
        maintenant = datetime.now(timezone.utc)
        s.add(
            RefreshToken(user_id=user.id, token="expire", expires_at=maintenant - timedelta(days=1))
        )
        s.add(
            RefreshToken(user_id=user.id, token="valide", expires_at=maintenant + timedelta(days=1))
        )
        s.commit()
    return ["expire", "valide"]


def _restants(moteur) -> set[str]:
    with Session(moteur) as s:
        return {t.token for t in s.exec(select(RefreshToken)).all()}


@pytest.mark.parametrize("entetes", [{}, {"x-maintenance-key": "mauvaise"}])
def test_sans_la_cle_rien_n_est_purge(moteur, entetes):
    _jetons(moteur)
    reponse = TestClient(app).post(ROUTE, headers=entetes)
    assert reponse.status_code == 403
    assert _restants(moteur) == {"expire", "valide"}


def test_avec_la_cle_les_purges_ont_lieu_et_rendent_leurs_comptes(moteur):
    _jetons(moteur)
    reponse = TestClient(app).post(ROUTE, headers={"x-maintenance-key": CLE})
    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    assert corps["erreurs"] == []
    assert corps["comptes"]["tokens"] == 1
    #  Les clés que `maintenance.sh` lit pour son rapport : les renommer côté
    #  API sans le script ferait des zéros silencieux dans l'historique.
    assert set(corps["comptes"]) == {
        "tokens",
        "prt",
        "notifications",
        "historique",
        "emails",
        "whatsapp",
        "evolutions",
    }
    assert _restants(moteur) == {"valide"}
