"""Le tableau de bord de télémétrie rend ce que les données disent — par portée (#1564).

Les trois portées (`jour`, `mois`, `annee`) et `users-active` recopiaient chacune
leur requête « top utilisateurs » et « uniques par jour ». Ce test fige ce que
l'administrateur voit **avant** de factoriser, sur une base minuscule dont chaque
chiffre se compte à la main : une factorisation qui changerait une réponse le dit.

L'horloge est figée : les libellés de jour et d'heure en dépendent.
"""

from datetime import datetime

import pytest

from app.models.core import RoleUtilisateur, TelemetryDaily, TelemetryEvent, TelemetryMonthly
from app.utils import horloge
from sqlmodel import Session
from tests.aides_http import base_http, client_http

#: Un jeudi d'automne, 12 h UTC (14 h à Paris, heure d'été).
MAINTENANT = datetime(2026, 10, 1, 12, 0, 0)


@pytest.fixture()
def admin_http(monkeypatch):
    with base_http() as moteur:
        #  Le jeton est émis AVANT de figer l'horloge : sinon il expire dans le passé.
        http, _ = client_http(moteur, RoleUtilisateur.admin)
        monkeypatch.setattr(horloge, "maintenant", lambda: MAINTENANT)
        with Session(moteur) as s:
            #  Aujourd'hui : l'utilisateur 7 voit deux pages, le 8 une seule.
            for user_id, page, heure in [
                (7, "/actualites", 9),
                (7, "/tickets", 10),
                (7, "/tickets", 11),
                (8, "/actualites", 9),
                (None, "/connexion", 8),
            ]:
                s.add(
                    TelemetryEvent(
                        user_id=user_id, page=page, cree_le=MAINTENANT.replace(hour=heure)
                    )
                )
            #  Il y a dix jours : l'utilisateur 8 seul, et 9 (qui n'a rien fait aujourd'hui).
            for user_id in (8, 9):
                s.add(
                    TelemetryEvent(
                        user_id=user_id,
                        page="/documents",
                        cree_le=datetime(2026, 9, 21, 10, 0, 0),
                    )
                )
            #  Agrégats : un jour qui n'a PLUS d'évènements bruts, et son total.
            s.add(
                TelemetryDaily(jour="2026-09-15", page="/tickets", utilisateurs_uniques=3, total=9)
            )
            s.add(
                TelemetryDaily(jour="2026-09-15", page="__total__", utilisateurs_uniques=3, total=9)
            )
            s.add(
                TelemetryMonthly(mois="2026-08", page="/tickets", utilisateurs_uniques=5, total=20)
            )
            s.add(
                TelemetryMonthly(mois="2026-08", page="__total__", utilisateurs_uniques=5, total=20)
            )
            s.commit()
        yield http


def _palmares(reponse) -> list[tuple]:
    return [(u["total"], u["pages"]) for u in reponse["top_users"]]


def test_jour_ne_compte_que_aujourd_hui(admin_http):
    r = admin_http.get("/telemetry/dashboard?scope=jour")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["scope"] == "jour"
    assert d["kpi"]["utilisateurs"] == 2 and d["kpi"]["vues"] == 5
    #  7 : trois vues sur deux pages ; 8 : une vue sur une page ; l'anonyme n'en est pas un.
    assert _palmares(d) == [(3, 2), (1, 1)]


def test_mois_remonte_trente_jours_et_les_uniques_de_chaque_jour(admin_http):
    r = admin_http.get("/telemetry/dashboard?scope=mois")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["scope"] == "mois"
    #  Sur trente jours : 7 (3 vues), 8 (2 vues : aujourd'hui et il y a dix jours), 9 (1 vue).
    assert _palmares(d) == [(3, 2), (2, 2), (1, 1)]
    #  Les uniques du 15/09 ne viennent d'aucun évènement brut : c'est le repli sur le
    #  total agrégé qui en fait le jour de pointe, devant le 21/09 (deux uniques).
    assert d["kpi"]["jour_pointe"] == {"jour": "2026-09-15", "uniques": 3}


def test_annee_garde_le_meilleur_jour_toutes_periodes(admin_http):
    r = admin_http.get("/telemetry/dashboard?scope=annee")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["scope"] == "annee"
    #  Le 15/09 (3 uniques, repli sur l'agrégat) bat le 21/09 (2) et aujourd'hui (2).
    assert d["kpi"]["record_jour"] == {"jour": "2026-09-15", "uniques": 3}
    assert d["kpi"]["record_mois"] == {"mois": "2026-08", "uniques": 5}


def test_users_active_rend_le_meme_palmares_que_le_mois(admin_http):
    mois = admin_http.get("/telemetry/dashboard?scope=mois").json()
    lignes = admin_http.get("/telemetry/users-active").json()
    assert [(ligne["total"], ligne["pages"]) for ligne in lignes] == _palmares(mois)
    assert [ligne["user_id"] for ligne in lignes] == [7, 8, 9]
