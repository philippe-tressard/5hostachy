"""Un fil TRANSFÉRÉ par le conseil, versé dans une affaire — ce qui reste en base.

Demandé le 29/09/2026 : le conseil transfère à l'adresse des affaires les
courriels reçus dans sa boîte personnelle. Le fil rejoint l'affaire qu'il
désigne (« TK-… »), celle d'un transfert précédent du même fil, ou une affaire
neuve — Étude & travaux, conseil syndical seul, au nom de l'auteur du premier
message. Un message déjà versé ne l'est jamais deux fois.

Le découpage lui-même est éprouvé sans base : `test_courriel_fil.py`.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from sqlmodel import select

from app.models.core import Notification, StatutTicket, Ticket, TicketEvolution, Utilisateur
from app.models.courriel import FilCourriel, MessageVerse
from app.utils import courriel_transfert
from app.utils.courriel_boite import traiter
from app.utils.courriel_ingestion import ACCEPTE, IGNORE, REFUSE
from tests.purge_test import purger_ligne
from tests.test_courriel_reponse_ticket import _AUTH_OK
from tests.test_courriel_reponse_ticket_bout_en_bout import _evolutions, _notifs, scene  # noqa: F401

_RELEVE = datetime(2026, 9, 29, 12, 0)


def _fil(syndic: str, objet: str, *, plus_recent: str = "") -> str:
    """Le fil de l'exemple du 29/09/2026 — noms et adresses fictifs."""
    return (
        f"{plus_recent}"
        "Début du message réexpédié :\n\n"
        f"De: Gestion Syndic <{syndic}>\n"
        f"Objet: RE: {objet}\n"
        "Date: 29 septembre 2026 à 10:12:34 UTC+2\n"
        "À: Jean Dupont <jean.dupont@exemple.test>\n\n"
        "Bonjour Monsieur Dupont,\n\n"
        "Nous nous chargeons de lancer un ordre de service à l'électricien.\n\n"
        "Cordialement\n\n"
        "De : Jean Dupont <jean.dupont@exemple.test>\n"
        "Envoyé : mardi 29 septembre 2026 08:43\n"
        f"À : Gestion Syndic <{syndic}>\n"
        f"Objet : Re: {objet}\n\n"
        "Bonjour Madame,\n\n"
        "A ce jour l'entreprise ne répond pas à notre demande d'intervention urgente.\n\n"
        "Le sam. 26 sept. 2026, 08:58, Jean Dupont <\n"
        "jean.dupont@exemple.test> a écrit :\n\n"
        "> Bonjour Monsieur,\n>\n"
        "> Le portillon électrique ne fonctionne plus, les résidents ne peuvent plus rentrer.\n"
    )


#: Un transfert plus récent du même fil : Jean a répondu une fois de plus.
_RELANCE_DE_JEAN = (
    "Début du message réexpédié :\n\n"
    "De: Jean Dupont <jean.dupont@exemple.test>\n"
    "Objet: RE: {objet}\n"
    "Date: 29 septembre 2026 à 11:30\n\n"
    "Merci Madame, nous attendons la date de passage de l'électricien avec impatience.\n\n"
    "De : Gestion Syndic <{syndic}>\n"
    "Envoyé : mardi 29 septembre 2026 10:12\n"
    "Objet : RE: {objet}\n\n"
)


def _entetes(de: str, sujet: str) -> dict:
    return {"From": de, "To": "affaire@5hostachy.fr", "Subject": sujet}


@pytest.fixture()
def monde(scene, monkeypatch):  # noqa: F811
    """La scène des réponses par courriel, un objet de fil unique, et la purge
    de tout ce que les transferts créent."""
    session, ticket, syndic, cs = scene
    monkeypatch.setattr(courriel_transfert, "domaines_du_site", lambda _session: {"5hostachy.fr"})
    objet = f"Portillon bloqué {uuid.uuid4().hex[:8]}"
    yield session, ticket, syndic, cs, objet
    crees = session.exec(
        select(Ticket).where(Ticket.auteur_id == cs.id, Ticket.id != ticket.id)
    ).all()
    for t in [*crees, ticket]:
        for modele in (TicketEvolution, MessageVerse, FilCourriel):
            for ligne in session.exec(select(modele).where(modele.ticket_id == t.id)).all():
                purger_ligne(session, modele, ligne.id)
    for t in crees:
        purger_ligne(session, Ticket, t.id)
    session.commit()


def _affaires(session, objet):
    return session.exec(select(Ticket).where(Ticket.titre == objet)).all()


def _transferer(session, cs, objet, corps, *, sujet=None, auth=_AUTH_OK):
    return traiter(
        session,
        _entetes(cs.email, sujet or f"TR: RE: {objet}"),
        corps,
        _RELEVE,
        authentification=auth,
    )


# ── Une affaire neuve ─────────────────────────────────────────────────────────


def test_un_fil_sans_repere_cree_une_affaire_du_conseil_au_nom_du_premier_auteur(monde):
    session, _ticket, syndic, cs, objet = monde
    assert _transferer(session, cs, objet, _fil(syndic.email, objet)) == ACCEPTE

    (affaire,) = _affaires(session, objet)
    assert affaire.categorie == "etude_travaux"
    assert affaire.public_cible == '["conseil_syndical"]', "conseil syndical seul, choisi"
    assert affaire.auteur_id == cs.id
    assert (affaire.saisi_pour_nom, affaire.saisi_pour_email) == (
        "Jean Dupont",
        "jean.dupont@exemple.test",
    )
    #  Décrite par le plus ANCIEN message, et datée de lui.
    assert affaire.description.startswith(
        "<p><em>Mail reçu de Jean Dupont le 26 septembre 2026 à 08:58, transféré par C S</em></p>"
    ), affaire.description
    assert "portillon électrique ne fonctionne plus" in affaire.description
    assert affaire.cree_le == datetime(2026, 9, 26, 6, 58)

    jean, syndic_suite = sorted(_evolutions(session, affaire), key=lambda e: e.cree_le)
    assert "Mail reçu de Jean Dupont le 29 septembre 2026 à 08:43" in jean.contenu
    assert "ordre de service" in syndic_suite.contenu
    #  Le syndic a répondu : l'affaire est chez lui (règle du 28/09/2026).
    assert (syndic_suite.type, syndic_suite.nouveau_statut) == ("etat", "en_cours")
    assert affaire.statut == StatutTicket.en_cours
    assert {jean.auteur_id, syndic_suite.auteur_id} == {cs.id}

    (notif,) = [n for n in _notifs(session, cs) if affaire.numero in n.titre]
    assert "créée" in notif.titre and "2 suite(s) ajoutée(s)" in notif.corps


def test_une_affaire_nee_d_un_message_du_SYNDIC_est_chez_le_syndic(monde):
    """Demandé le 29/09/2026 : le syndic a répondu, l'affaire est chez lui."""
    session, _ticket, syndic, cs, objet = monde
    seul = _fil(syndic.email, objet).split("De : Jean Dupont", 1)[0]
    assert _transferer(session, cs, objet, seul) == ACCEPTE
    (affaire,) = _affaires(session, objet)
    assert affaire.statut == StatutTicket.en_cours
    assert _evolutions(session, affaire) == []


def test_l_auteur_qui_a_un_compte_est_saisi_POUR_lui(monde):
    session, _ticket, syndic, cs, objet = monde
    jean = Utilisateur(
        email="jean.dupont@exemple.test",
        mot_de_passe_hash="x",
        prenom="Jean",
        nom="Dupont",
        roles_json="résident",
        actif=True,
    )
    session.add(jean)
    session.commit()
    try:
        _transferer(session, cs, objet, _fil(syndic.email, objet))
        (affaire,) = _affaires(session, objet)
        assert (affaire.saisi_pour_user_id, affaire.saisi_pour_nom) == (jean.id, None)
    finally:
        purger_ligne(session, Utilisateur, jean.id)
        session.commit()


def test_son_PROPRE_message_transfere_ne_dit_pas_transfere_par_soi(monde):
    session, _ticket, syndic, cs, objet = monde
    corps = _fil(syndic.email, objet).replace(
        "De : Jean Dupont <jean.dupont@exemple.test>\nEnvoyé",
        f"De : C S <{cs.email}>\nEnvoyé",
    )
    _transferer(session, cs, objet, corps)
    (affaire,) = _affaires(session, objet)
    (du_cs,) = [e for e in _evolutions(session, affaire) if "Mail reçu de C S" in e.contenu]
    assert "transféré par" not in du_cs.contenu
    assert "transféré par C S" in affaire.description, "Jean, lui, a été transféré"


# ── Le même fil, transféré de nouveau ─────────────────────────────────────────


def test_le_transfert_suivant_du_meme_fil_rejoint_l_affaire_sans_repere(monde):
    session, _ticket, syndic, cs, objet = monde
    _transferer(session, cs, objet, _fil(syndic.email, objet))
    (affaire,) = _affaires(session, objet)
    avant = len(_evolutions(session, affaire))

    corps = _RELANCE_DE_JEAN.format(objet=objet, syndic=syndic.email) + (
        "Bonjour Monsieur Dupont,\n\n"
        "Nous nous chargeons de lancer un ordre de service à l'électricien.\n"
    )
    assert _transferer(session, cs, objet, corps) == ACCEPTE

    assert len(_affaires(session, objet)) == 1, "le fil ne crée pas une seconde affaire"
    nouvelles = _evolutions(session, affaire)[avant:]
    assert len(nouvelles) == 1 and "date de passage" in nouvelles[0].contenu


def test_un_fil_RENVOYE_ne_double_rien(monde):
    session, _ticket, syndic, cs, objet = monde
    _transferer(session, cs, objet, _fil(syndic.email, objet))
    (affaire,) = _affaires(session, objet)
    avant = len(_evolutions(session, affaire))

    assert _transferer(session, cs, objet, _fil(syndic.email, objet)) == IGNORE
    assert len(_evolutions(session, affaire)) == avant
    assert any("déjà versé" in n.titre for n in _notifs(session, cs))


# ── Une affaire désignée ──────────────────────────────────────────────────────


def test_le_repere_TK_seul_designe_l_affaire_et_une_copie_manuelle_n_est_pas_doublee(monde):
    """L'exemple du 29/09/2026 : TK-109008 avait perdu son numéro dans l'objet.

    Le premier message avait été recopié À LA MAIN : il n'a pas d'empreinte,
    mais son texte est déjà dans l'affaire.
    """
    session, ticket, syndic, cs, objet = monde
    ticket.description = (
        "<p>Bonjour Monsieur,</p><p>Le portillon électrique ne fonctionne plus, "
        "les résidents ne peuvent plus rentrer.</p>"
    )
    session.add(ticket)
    session.commit()

    corps = f"{ticket.numero}\n\n" + _fil(syndic.email, objet)
    assert _transferer(session, cs, objet, corps) == ACCEPTE

    assert _affaires(session, objet) == []
    assert len(_evolutions(session, ticket)) == 2, "Jean le 29/09, puis le syndic"
    lien = session.exec(select(FilCourriel).where(FilCourriel.ticket_id == ticket.id)).first()
    assert lien is not None, "le fil est retenu pour les transferts suivants"


def test_un_repere_inconnu_est_refuse_et_rien_n_est_cree(monde):
    session, _ticket, syndic, cs, objet = monde
    sujet = f"TR: RE: {objet} TK-000000"
    assert _transferer(session, cs, objet, _fil(syndic.email, objet), sujet=sujet) == REFUSE
    assert _affaires(session, objet) == []
    assert any("TK-000000 n'existe pas" in n.corps for n in _notifs(session, cs))


def test_une_affaire_CLOSE_designee_ne_recoit_rien_et_on_le_dit(monde):
    session, ticket, syndic, cs, objet = monde
    ticket.statut = StatutTicket.résolu
    session.add(ticket)
    session.commit()
    sujet = f"TR: RE: {objet} {ticket.numero}"
    assert _transferer(session, cs, objet, _fil(syndic.email, objet), sujet=sujet) == IGNORE
    assert _evolutions(session, ticket) == []
    assert any("est close" in n.corps for n in _notifs(session, cs))


def test_un_fil_dont_l_affaire_est_close_en_ouvre_une_autre(monde):
    session, _ticket, syndic, cs, objet = monde
    _transferer(session, cs, objet, _fil(syndic.email, objet))
    (premiere,) = _affaires(session, objet)
    premiere.statut = StatutTicket.résolu
    session.add(premiere)
    session.commit()

    corps = _RELANCE_DE_JEAN.format(objet=objet, syndic=syndic.email) + "Bonjour.\n"
    assert _transferer(session, cs, objet, corps) == ACCEPTE
    assert len(_affaires(session, objet)) == 2


# ── Ce qui n'entre pas ────────────────────────────────────────────────────────


def test_un_transfert_NON_AUTHENTIFIE_ne_cree_rien(monde):
    session, _ticket, syndic, cs, objet = monde
    corps = _fil(syndic.email, objet)
    assert _transferer(session, cs, objet, corps, auth=(False, "non signé")) == REFUSE
    assert _affaires(session, objet) == []
    assert any("authentifié" in n.corps for n in _notifs(session, cs))


def test_un_fil_illisible_est_refuse_en_entier(monde):
    session, _ticket, syndic, cs, objet = monde
    corps = _fil(syndic.email, objet).replace("mardi 29 septembre 2026 08:43", "hier soir")
    assert _transferer(session, cs, objet, corps) == REFUSE
    assert _affaires(session, objet) == []
    assert any("ne se découpe pas" in n.corps for n in _notifs(session, cs))


def test_un_transfert_NON_RECONNU_le_dit_au_conseil(monde):
    """🔴 29/09/2026 : faute de reconnaître le transfert, la relève ordinaire
    répondait « rien ne permet de dire à quel ticket » — sans rapport."""
    session, _ticket, _syndic, cs, objet = monde
    assert _transferer(session, cs, objet, "Voir plus bas.\n\nMerci") == REFUSE
    assert any("message transféré n'a pas été trouvé" in n.corps for n in _notifs(session, cs))


def test_un_RESIDENT_qui_transfere_sans_repere_ne_cree_rien(monde):
    """Créer une affaire du conseil est un geste du conseil."""
    session, _ticket, syndic, _cs, objet = monde
    resident = Utilisateur(
        email=f"resident-{uuid.uuid4().hex[:8]}@exemple.test",
        mot_de_passe_hash="x",
        prenom="R",
        nom="R",
        roles_json="résident",
        actif=True,
    )
    session.add(resident)
    session.commit()
    try:
        assert _transferer(session, resident, objet, _fil(syndic.email, objet)) == IGNORE
        assert _affaires(session, objet) == []
    finally:
        for n in _notifs(session, resident):
            purger_ligne(session, Notification, n.id)
        purger_ligne(session, Utilisateur, resident.id)
        session.commit()
