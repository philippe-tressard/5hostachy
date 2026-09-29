"""Une Suite qui change QUI LIT l'affaire le dit, dans le fil (29/09/2026).

Arbitré à l'écran après TK-124285 : les droits de lecture appartiennent à
l'affaire, jamais à une Suite — celle qui les change les change pour tout le
fil, messages antérieurs compris. Un changement rétroactif qui ne laisserait
aucune trace serait invisible de ceux qu'il ouvre ou qu'il ferme.
"""

from __future__ import annotations

import json

from fastapi import BackgroundTasks

from app.models.core import RoleUtilisateur, Ticket, TicketEvolution
from app.routers.tickets import evolutions
from app.schemas_tickets import TicketEvolutionCreate
from app.utils.visibility import trace_droits
from tests.test_intervenant_affaire import _compte, _creer, session  # noqa: F401

_VIDE = "par défaut de la catégorie"


def _suite(session, user, ticket_id, **champs):
    corps = TicketEvolutionCreate(
        type="commentaire", contenu="<p>Point d'étape.</p>", notifier=False, **champs
    )
    return evolutions.add_evolution(ticket_id, corps, BackgroundTasks(), session=session, user=user)


def _derniere(session, ticket_id) -> TicketEvolution:
    return max(
        session.exec(
            evolutions.select(TicketEvolution).where(TicketEvolution.ticket_id == ticket_id)
        ).all(),
        key=lambda e: e.id,
    )


# ── La règle, pure ────────────────────────────────────────────────────────────


def test_rien_ne_change_rien_ne_s_ecrit():
    """Cas zéro : le formulaire renvoie TOUJOURS les Destinataires affichés."""
    assert trace_droits(None, None, False, False, vide=_VIDE) == []
    assert trace_droits("[]", None, False, False, vide=_VIDE) == []
    #  L'ordre des pastilles n'est pas un changement.
    assert (
        trace_droits(
            '["locataires","bailleurs"]', '["bailleurs","locataires"]', False, False, vide=_VIDE
        )
        == []
    )


def test_les_libelles_sont_ceux_de_l_ecran():
    (ligne,) = trace_droits(None, '["conseil_syndical","locataires"]', False, False, vide=_VIDE)
    assert ligne == "🔒 Destinataires : par défaut de la catégorie → Conseil syndical, Locataires"


def test_l_acces_se_trace_aussi():
    assert trace_droits(None, None, False, True, vide="Tous") == ["🔒 Accès : réservé au périmètre"]
    assert trace_droits(None, None, True, False, vide="Tous") == [
        "🔓 Accès : ouvert à toute la copropriété"
    ]


def test_un_code_inconnu_ne_rejoint_pas_le_html_tel_quel():
    (ligne,) = trace_droits(None, '["<b>x</b>"]', False, False, vide=_VIDE)
    assert "<b>" not in ligne and "&lt;b&gt;" in ligne


# ── Par la route ──────────────────────────────────────────────────────────────


def test_la_suite_du_conseil_qui_change_les_destinataires_le_dit(session):
    #  Étude & travaux : ouverte par le conseil, lue par les copropriétaires.
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    t = _creer(session, cs, categorie="etude_travaux")
    _suite(session, cs, t.id, public_cible=["conseil_syndical"])
    assert json.loads(session.get(Ticket, t.id).public_cible) == ["conseil_syndical"]
    assert "🔒 Destinataires : par défaut de la catégorie → Conseil syndical" in (
        _derniere(session, t.id).contenu
    )


def test_la_suite_qui_renvoie_les_memes_destinataires_ne_dit_rien(session):
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    t = _creer(session, cs, categorie="etude_travaux")
    _suite(session, cs, t.id, public_cible=[])
    assert "Destinataires" not in _derniere(session, t.id).contenu
