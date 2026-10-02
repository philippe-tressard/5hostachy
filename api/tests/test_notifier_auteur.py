"""Prévenir l'AUTEUR d'une affaire qu'une Suite y a été ajoutée — courriel et cloche (#1569).

`routers/tickets/notifier_auteur.py` (sorti d'`evolutions.py` le 26/09/2026) n'était
nommé par aucun test. Il décide ce qu'on écrit à l'auteur, et quand :

| La Suite | Courriel | Cloche |
|---|---|---|
| un changement d'état | `ticket_statut_change`, libellés d'état en français | « Ticket #N — statut : … » |
| un commentaire avec texte | `ticket_nouveau_message`, 300 caractères au plus | « Nouveau commentaire … », 200 au plus |
| un commentaire sans texte | aucun | « Nouveau commentaire … », corps vide |
| (auteur sans adresse) | aucun | oui |

Le garde « l'auteur n'est pas prévenu de ce qu'il fait lui-même » et « 🔕 n'avertir
personne » vit dans l'appelant (`add_evolution`) : le dernier groupe de tests le tient
de bout en bout, par la vraie route de Suite.

Les courriels ne partent pas : `BackgroundTasks` les garde, et on lit ce qui est
EN FILE — le code, le destinataire, le contexte —, sans jamais les envoyer.
"""

from __future__ import annotations

import itertools

import pytest
from fastapi import BackgroundTasks
from sqlmodel import select

from app.models.core import Notification, RoleUtilisateur, Ticket
from app.routers.tickets import evolutions
from app.routers.tickets.notifier_auteur import _notifier_auteur
from app.schemas_tickets import TicketEvolutionCreate
from app.utils.email import send_email
from app.utils.liens import lien_ticket
from tests.aides_base import compte

_numero = itertools.count(1)


@pytest.fixture()
def scene(session):
    auteur = compte(session, prefixe="auteur", prenom="Alice", nom="Martin")
    conseil = compte(
        session,
        prefixe="conseil",
        prenom="Camille",
        nom="Durand",
        roles_json=RoleUtilisateur.conseil_syndical.value,
    )
    t = Ticket(
        numero=f"N-{next(_numero):04d}",
        titre="Porte du garage",
        description="Elle ne ferme plus.",
        categorie="panne",
        statut="ouvert",
        auteur_id=auteur.id,
        perimetre_cible='["résidence"]',
    )
    session.add(t)
    session.commit()
    session.refresh(t)
    return auteur, conseil, t


def _notifier(session, scene, **corps):
    auteur, conseil, ticket = scene
    taches = BackgroundTasks()
    ancien = corps.pop("ancien_statut", None)
    _notifier_auteur(
        session,
        taches,
        ticket=ticket,
        user=conseil,
        body=TicketEvolutionCreate(**corps),
        ancien_statut=ancien,
    )
    session.commit()
    return taches.tasks


def _cloches(session, destinataire_id):
    return session.exec(
        select(Notification).where(Notification.destinataire_id == destinataire_id)
    ).all()


# ── Un changement d'état ────────────────────────────────────────────────────


def test_un_changement_d_etat_ecrit_a_l_auteur_avec_les_libelles_en_francais(session, scene):
    auteur, conseil, ticket = scene

    [tache] = _notifier(
        session, scene, type="etat", nouveau_statut="en_cours", ancien_statut="ouvert"
    )

    assert tache.func is send_email
    assert tache.kwargs["code"] == "ticket_statut_change"
    assert tache.kwargs["to"] == auteur.email
    assert tache.kwargs["destinataire_id"] == auteur.id
    contexte = tache.kwargs["context"]
    assert contexte["ticket"]["statut"] == "Chez le syndic"
    assert contexte["ticket"]["ancien_statut"] == "Ouvert"
    assert contexte["ticket"]["numero"] == ticket.numero
    assert contexte["destinataire"] == {"prenom": "Alice", "nom": "Martin"}
    #  Les blocs que tous les modèles d'e-mail attendent.
    assert {"residence", "app", "auteur_action"} <= set(contexte)


def test_sans_ancien_statut_le_courriel_dit_aucun(session, scene):
    [tache] = _notifier(session, scene, type="etat", nouveau_statut="résolu")
    assert tache.kwargs["context"]["ticket"]["ancien_statut"] == "Aucun"


def test_la_cloche_d_un_changement_d_etat_nomme_le_statut(session, scene):
    auteur, _, ticket = scene
    _notifier(session, scene, type="etat", nouveau_statut="résolu", ancien_statut="ouvert")

    [cloche] = _cloches(session, auteur.id)

    assert cloche.titre == f"Ticket #{ticket.numero} — statut : Résolu"
    assert cloche.type == "ticket_update"
    assert cloche.lien == lien_ticket(ticket.id)
    assert cloche.lue is False


# ── Un commentaire ──────────────────────────────────────────────────────────


def test_un_commentaire_ecrit_a_l_auteur_le_debut_du_message(session, scene):
    auteur, _, ticket = scene
    [tache] = _notifier(session, scene, type="commentaire", contenu="<p>Le syndic passe lundi.</p>")

    assert tache.kwargs["code"] == "ticket_nouveau_message"
    assert tache.kwargs["to"] == auteur.email
    assert tache.kwargs["context"]["message"] == {"contenu": "<p>Le syndic passe lundi.</p>"}
    assert tache.kwargs["context"]["ticket"] == {
        "id": ticket.id,
        "numero": ticket.numero,
        "titre": ticket.titre,
    }


def test_le_message_du_courriel_est_borne_a_300_caracteres_celui_de_la_cloche_a_200(session, scene):
    auteur, _, _ = scene
    long = "x" * 500

    [tache] = _notifier(session, scene, type="commentaire", contenu=long)

    assert len(tache.kwargs["context"]["message"]["contenu"]) == 300
    [cloche] = _cloches(session, auteur.id)
    assert len(cloche.corps) == 200
    assert cloche.titre == f"Nouveau commentaire sur le ticket #{scene[2].numero}"


def test_un_commentaire_sans_texte_n_ecrit_pas_mais_la_cloche_sonne(session, scene):
    auteur, _, _ = scene

    assert _notifier(session, scene, type="commentaire", contenu=None) == []
    assert _notifier(session, scene, type="commentaire", contenu="") == []

    cloches = _cloches(session, auteur.id)
    assert len(cloches) == 2
    assert all(c.corps == "" for c in cloches)


def test_un_auteur_sans_adresse_n_a_pas_de_courriel_mais_a_sa_cloche(session, scene):
    auteur, _, _ = scene
    auteur.email = ""
    session.add(auteur)
    session.commit()

    assert _notifier(session, scene, type="commentaire", contenu="Bonjour") == []
    assert len(_cloches(session, auteur.id)) == 1


def test_seul_l_auteur_de_l_affaire_est_prevenu(session, scene):
    _, conseil, _ = scene
    _notifier(session, scene, type="commentaire", contenu="Bonjour")
    assert _cloches(session, conseil.id) == []


def test_la_cloche_obeit_au_profil_de_l_auteur(session, scene):
    """Le profil décide : un auteur qui a coupé la cloche de son bâtiment n'est pas sonné."""
    import json

    auteur, _, _ = scene
    auteur.preferences_notifications = json.dumps({"mon_batiment_app": False})
    session.add(auteur)
    session.commit()

    _notifier(session, scene, type="commentaire", contenu="Bonjour")

    assert _cloches(session, auteur.id) == []


# ── Par la vraie route de Suite : qui n'est pas prévenu ─────────────────────


def _suite(session, ticket_id, user, **champs):
    corps = TicketEvolutionCreate(type="commentaire", contenu="<p>Point d'étape.</p>", **champs)
    return evolutions.add_evolution(ticket_id, corps, BackgroundTasks(), session=session, user=user)


def test_la_route_previent_l_auteur_quand_un_autre_ecrit(session, scene):
    auteur, conseil, ticket = scene
    _suite(session, ticket.id, conseil)

    assert len(_cloches(session, auteur.id)) == 1


def test_la_route_ne_previent_pas_l_auteur_de_ce_qu_il_ecrit_lui_meme(session, scene):
    auteur, _, ticket = scene
    _suite(session, ticket.id, auteur)

    assert _cloches(session, auteur.id) == []


def test_la_route_n_avertit_personne_quand_le_conseil_coupe_les_notifications(session, scene):
    """🔕 `notifier=False` : pas même l'auteur."""
    auteur, conseil, ticket = scene
    _suite(session, ticket.id, conseil, notifier=False)

    assert _cloches(session, auteur.id) == []
