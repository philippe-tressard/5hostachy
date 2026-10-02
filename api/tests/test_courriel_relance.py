"""La réponse à une relance GROUPÉE — `courriel_relance`, ses deux fonctions (#1569).

Le module (sorti de `courriel_boite` le 28/09/2026) n'était nommé par aucun test :
`test_reponse_relance.py` l'éprouve de bout en bout, par la relève de la boîte
(`traiter`). Ce fichier tient les deux fonctions ISOLÉES, avec les cas limites que la
relève ne présente pas :

1. `relance_de` — un verdict sans jeton ne désigne aucune relance ; un jeton inconnu non plus ;
2. `reponse_a_une_relance` — la réponse est CONSERVÉE avant d'être notifiée, jamais
   ventilée dans les fils, notifiée à chaque membre du conseil et de l'administration
   avec la liste des dossiers ;
3. les cas limites : liste de dossiers illisible, dossiers disparus, message sans texte,
   citation du syndic retirée.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlmodel import select

from app.models.core import Notification, Ticket, TicketEvolution
from app.models.courriel import RelanceCourriel, ReponseRelance
from app.utils.courriel_ingestion import RELANCE
from app.utils.courriel_relance import relance_de, reponse_a_une_relance
from tests.aides_base import compte

_numero = [0]


def _verdict(jeton="tok-1", expediteur="gestion@syndic.exemple.test"):
    return SimpleNamespace(jeton=jeton, expediteur=expediteur)


def _relance(session, *, jeton="tok-1", tickets="[]") -> RelanceCourriel:
    r = RelanceCourriel(jeton=jeton, tickets_json=tickets)
    session.add(r)
    session.commit()
    session.refresh(r)
    return r


def _ticket(session, auteur, numero=None) -> Ticket:
    _numero[0] += 1
    t = Ticket(
        numero=numero or f"R-{_numero[0]:04d}",
        titre="Fuite",
        description="…",
        auteur_id=auteur.id,
        perimetre_cible='["résidence"]',
    )
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


@pytest.fixture()
def conseil(session):
    return {
        "cs": compte(session, prefixe="cs", roles_json="conseil_syndical"),
        "admin": compte(session, prefixe="adm", roles_json="admin"),
        "resident": compte(session, prefixe="res", roles_json="résident"),
    }


def _notifs(session, user) -> list[Notification]:
    return session.exec(select(Notification).where(Notification.destinataire_id == user.id)).all()


# ── relance_de ──────────────────────────────────────────────────────────────


def test_le_jeton_retrouve_sa_relance(session):
    r = _relance(session, jeton="tok-abc")

    assert relance_de(session, _verdict("tok-abc")).id == r.id


@pytest.mark.parametrize("jeton", [None, ""])
def test_un_verdict_sans_jeton_ne_designe_aucune_relance(session, jeton):
    _relance(session, jeton="tok-abc")

    assert relance_de(session, _verdict(jeton)) is None


def test_un_jeton_inconnu_ne_designe_aucune_relance(session):
    _relance(session, jeton="tok-abc")

    assert relance_de(session, _verdict("tok-autre")) is None


def test_le_jeton_ne_s_epuise_pas(session):
    """Le syndic peut répondre plusieurs fois : chaque réponse retrouve la même relance."""
    r = _relance(session, jeton="tok-abc")

    assert relance_de(session, _verdict("tok-abc")).id == r.id
    assert relance_de(session, _verdict("tok-abc")).id == r.id


# ── reponse_a_une_relance ───────────────────────────────────────────────────


def test_la_reponse_est_conservee_avec_son_expediteur(session, conseil):
    r = _relance(session)

    reponse_a_une_relance(session, r, _verdict(expediteur="syndic@exemple.test"), "On passe jeudi.")
    session.commit()

    [gardee] = session.exec(select(ReponseRelance)).all()
    assert (gardee.relance_id, gardee.expediteur, gardee.contenu) == (
        r.id,
        "syndic@exemple.test",
        "On passe jeudi.",
    )
    assert gardee.recue_le is not None


def test_la_decision_rendue_est_relance_pas_refuse(session, conseil):
    """Reçue, conservée, notifiée : rien n'a été refusé — seulement pas ventilé."""
    assert reponse_a_une_relance(session, _relance(session), _verdict(), "Bien reçu.") == RELANCE


def test_chaque_membre_du_conseil_et_de_l_administration_est_notifie(session, conseil):
    r = _relance(session)

    reponse_a_une_relance(session, r, _verdict(), "On passe jeudi.")
    session.commit()

    for membre in (conseil["cs"], conseil["admin"]):
        [notif] = _notifs(session, membre)
        assert notif.titre == "Réponse du syndic à la relance groupée"
        assert notif.lien == "/espace-cs/reporting"
        assert "On passe jeudi." in notif.corps
        assert "n'a été ajoutée à aucun fil" in notif.corps


def test_un_simple_resident_n_est_pas_notifie(session, conseil):
    reponse_a_une_relance(session, _relance(session), _verdict(), "Texte.")
    session.commit()

    assert _notifs(session, conseil["resident"]) == []


def test_la_notification_nomme_l_expediteur_et_les_dossiers(session, conseil):
    auteur = conseil["resident"]
    t1, t2 = _ticket(session, auteur, "TK-100"), _ticket(session, auteur, "TK-200")
    r = _relance(session, tickets=f"[{t1.id}, {t2.id}]")

    reponse_a_une_relance(
        session, r, _verdict(expediteur="syndic@exemple.test"), "Intervention jeudi."
    )
    session.commit()

    [notif] = _notifs(session, conseil["cs"])
    assert "« syndic@exemple.test » a répondu" in notif.corps
    assert "#TK-100" in notif.corps and "#TK-200" in notif.corps


def test_la_reponse_n_est_ventilee_dans_aucun_fil(session, conseil):
    """La décision de fond : une phrase sur deux dossiers serait fausse dans l'un d'eux."""
    t = _ticket(session, conseil["resident"])
    r = _relance(session, tickets=f"[{t.id}]")

    reponse_a_une_relance(session, r, _verdict(), "Pour ce dossier : jeudi. L'autre est clos.")
    session.commit()

    assert session.exec(select(TicketEvolution)).all() == []


@pytest.mark.parametrize("brut", ["pas du json", "null", '"texte"', "{}", '["a"]'])
def test_une_liste_de_dossiers_illisible_n_empeche_pas_de_conserver_la_reponse(
    session, conseil, brut
):
    r = _relance(session, tickets=brut)

    reponse_a_une_relance(session, r, _verdict(), "Message utile.")
    session.commit()

    assert len(session.exec(select(ReponseRelance)).all()) == 1
    assert "aucun ticket retrouvé" in _notifs(session, conseil["cs"])[0].corps


def test_des_dossiers_disparus_ne_sont_pas_nommes(session, conseil):
    r = _relance(session, tickets="[9991, 9992]")

    reponse_a_une_relance(session, r, _verdict(), "Message.")
    session.commit()

    assert "aucun ticket retrouvé" in _notifs(session, conseil["cs"])[0].corps


def test_une_relance_sans_dossier_dit_aucun_ticket_retrouve(session, conseil):
    reponse_a_une_relance(session, _relance(session, tickets="[]"), _verdict(), "Message.")
    session.commit()

    assert "portant sur aucun ticket retrouvé" in _notifs(session, conseil["cs"])[0].corps


def test_la_citation_du_syndic_est_retiree(session, conseil):
    """Recopier tout l'échange précédent ferait une copie de la relance à chaque réponse."""
    corps = "On passe jeudi.\n\n> Bonjour, voici nos 4 dossiers en attente\n> TK-100"

    reponse_a_une_relance(session, _relance(session), _verdict(), corps)
    session.commit()

    [gardee] = session.exec(select(ReponseRelance)).all()
    assert gardee.contenu == "On passe jeudi."
    assert "4 dossiers" not in _notifs(session, conseil["cs"])[0].corps


def test_un_message_sans_texte_lisible_est_dit_comme_tel(session, conseil):
    reponse_a_une_relance(session, _relance(session), _verdict(), "> tout est cité")
    session.commit()

    [gardee] = session.exec(select(ReponseRelance)).all()
    assert gardee.contenu == ""
    assert "(message sans texte lisible)" in _notifs(session, conseil["cs"])[0].corps


def test_plusieurs_reponses_a_la_meme_relance_sont_toutes_conservees(session, conseil):
    r = _relance(session)

    reponse_a_une_relance(session, r, _verdict(), "Première.")
    reponse_a_une_relance(session, r, _verdict(), "Précision le lendemain.")
    session.commit()

    gardees = session.exec(select(ReponseRelance).order_by(ReponseRelance.id)).all()
    assert [x.contenu for x in gardees] == ["Première.", "Précision le lendemain."]
    assert len(_notifs(session, conseil["cs"])) == 2
