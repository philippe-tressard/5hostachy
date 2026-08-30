"""Les endpoints DELETE tiennent-ils sous `foreign_keys=ON` ? (#546, étape 3)

## Pourquoi ce fichier

Le 30/08/2026, l'instruction de l'étape 3 a mesuré ceci :

    62 lignes `session.delete(...)` dans app/  →   2 exécutées par la suite
    32 endpoints DELETE exposés                →   0 testés

🔴 **Aucun endpoint de suppression n'avait de test.** Les 880 tests verts sous
les clés (étape 2, 29/08) ne prouvaient donc rien sur l'activation en
production : ils établissaient que les *fixtures* sont propres, pas que les
*suppressions* passent.

C'est `standards/04` §2 appliqué au ticket lui-même — un vert qu'on peut obtenir
sans exercer ce qu'on croit exercer.

## Ce que ces tests sont, et pourquoi ils SONT l'étape 3

Le ticket demandait de « décider l'`ON DELETE` par relation ». Cette décision n'a
pas à être devinée : elle se **constate**. La suite tourne déjà sous
`foreign_keys=ON` ; il suffit donc d'appeler la suppression avec ses enfants en
place.

  • le test passe   ⇒ la suppression est sûre, la question est close ;
  • le test échoue  ⇒ SQLite **nomme la contrainte**, c'est-à-dire précisément la
    relation dont il fallait décider.

⚠️ Chaque cas monte **tous** les enfants que les métadonnées déclarent, y compris
ceux que le code de suppression pourrait avoir oubliés. Un test qui ne monterait
que les enfants déjà gérés confirmerait le code au lieu de l'éprouver.

## Les fonctions sont appelées DIRECTEMENT, pas par HTTP

Ce qu'on éprouve ici est le comportement transactionnel sous les clés, pas
l'authentification — laquelle a ses propres tests (`test_autorisation.py`,
`test_droits_editer_commenter.py`). Passer par un client HTTP ajouterait un
montage de session et de cookies sans rien mesurer de plus sur la question posée.
"""

from datetime import datetime

import pytest
from sqlmodel import Session, select

from app.database import engine
from app.models.core import (
    Ticket,
    TicketEvolution,
    Utilisateur,
)
from app.models.documents import Document

EMAIL = "suppression-546@test.fr"


def _purger(session: Session) -> None:
    """Nettoyage à l'ENTRÉE comme à la sortie.

    Une fixture qui ne nettoie qu'en sortie laisse ses lignes derrière elle dès
    qu'un test échoue — et c'est ce fichier-ci qui provoque des échecs. Le
    suivant tomberait alors sur une erreur de montage qui masque le vrai verdict.
    """
    for u in session.exec(select(Utilisateur).where(Utilisateur.email == EMAIL)).all():
        for d in session.exec(select(Document).where(Document.publie_par_id == u.id)).all():
            session.delete(d)
        for t in session.exec(select(Ticket).where(Ticket.auteur_id == u.id)).all():
            for e in session.exec(
                select(TicketEvolution).where(TicketEvolution.ticket_id == t.id)
            ).all():
                session.delete(e)
            for d in session.exec(select(Document).where(Document.ticket_id == t.id)).all():
                session.delete(d)
            session.delete(t)
        session.delete(u)
    session.commit()


@pytest.fixture()
def contexte():
    """Un administrateur — les suppressions les plus larges lui sont réservées."""
    from sqlmodel import SQLModel

    from app.models.core import RoleUtilisateur

    #  Ce fichier ne dépend d'aucune autre fixture : il doit donc créer le schéma
    #  lui-même, sinon il ne passe que lorsqu'un test qui le fait a trié avant —
    #  et un test dont le résultat dépend de l'ordre alphabétique n'est pas un
    #  test (leçon de `conftest.py`, 15/08/2026).
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _purger(session)
        admin = Utilisateur(
            email=EMAIL,
            hashed_password="x",
            prenom="Adèle",
            nom="Admin",
            role=RoleUtilisateur.admin,
            actif=True,
        )
        session.add(admin)
        session.commit()
        session.refresh(admin)
        yield session, admin
        _purger(session)


def _ticket(session: Session, admin: Utilisateur, suffixe: str) -> Ticket:
    t = Ticket(
        numero=f"TK-546-{suffixe}",
        titre="T",
        description="d",
        categorie="panne",
        auteur_id=admin.id,
    )
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def test_supprimer_un_ticket_qui_porte_une_evolution(contexte):
    """Le cas nominal : `delete_ticket` retire les évolutions avant le ticket."""
    from app.routers.tickets.crud import delete_ticket

    session, admin = contexte
    t = _ticket(session, admin, "evol")
    session.add(
        TicketEvolution(ticket_id=t.id, auteur_id=admin.id, type="commentaire", contenu="c")
    )
    session.commit()

    delete_ticket(t.id, session, admin)
    assert session.get(Ticket, t.id) is None


def test_supprimer_un_ticket_qui_porte_un_document(contexte):
    """🔴 LE CAS QUE LE CODE N'A PAS PRÉVU.

    `document.ticket_id` référence `ticket`, et `delete_ticket` retire les
    évolutions et les messages — **pas les documents**. Sous les clés, la
    suppression doit donc échouer.

    Ce test est écrit pour ÉCHOUER tant que le code n'a pas décidé du sort de
    cette relation. C'est ce que #546 appelle « décider par relation » : ici, un
    document attaché à un ticket supprimé n'a plus d'objet — il part avec lui.
    """
    from app.routers.tickets.crud import delete_ticket

    session, admin = contexte
    t = _ticket(session, admin, "doc")
    session.add(
        Document(
            titre="Devis",
            fichier_nom="devis.pdf",
            fichier_chemin="/tmp/devis.pdf",
            ticket_id=t.id,
            publie_par_id=admin.id,
        )
    )
    session.commit()

    delete_ticket(t.id, session, admin)
    assert session.get(Ticket, t.id) is None, "le ticket doit être supprimé"
    restants = session.exec(select(Document).where(Document.ticket_id == t.id)).all()
    assert restants == [], "les documents du ticket doivent partir avec lui"


# ── Les autres entités à risque ──────────────────────────────────────────────
#
#  🔴 CE QUE LE PREMIER CAS A APPRIS, et qui vaut pour tous les suivants :
#  SQLAlchemy n'ordonne les DELETE d'un même `commit()` que selon les
#  `Relationship` DÉCLARÉES. Une clé étrangère seule ne suffit pas — l'unité de
#  travail émet alors le DELETE du parent en premier, et la contrainte échoue
#  bien que l'enfant soit marqué pour suppression.
#
#  Relevé automatique des relations dans ce cas (30/08/2026) : **13**, dont
#  celles éprouvées ci-dessous. Les autres attendent leur test.


def _sondage(session: Session, admin: Utilisateur):
    from app.models.communaute import CommentaireSondage, OptionSondage, Sondage, VoteSondage

    s = Sondage(question="Q ?", auteur_id=admin.id)
    session.add(s)
    session.commit()
    session.refresh(s)
    o = OptionSondage(sondage_id=s.id, libelle="Oui")
    session.add(o)
    session.commit()
    session.refresh(o)
    session.add(VoteSondage(sondage_id=s.id, option_id=o.id, user_id=admin.id))
    session.add(CommentaireSondage(sondage_id=s.id, auteur_id=admin.id, contenu="c"))
    session.commit()
    return s


def test_supprimer_un_sondage_avec_ses_options_votes_et_commentaires(contexte):
    """Trois références entrantes, **toutes NOT NULL** — l'échec y serait certain.

    `commentaire_sondage` n'a pas de `Relationship` vers `Sondage` : c'est le
    même montage que `document` → `ticket`, donc le même piège d'ordre.
    """
    from app.models.communaute import Sondage
    from app.routers.sondages.crud import supprimer_sondage

    session, admin = contexte
    s = _sondage(session, admin)
    supprimer_sondage(s.id, session, admin)
    assert session.get(Sondage, s.id) is None


def _evenement(session: Session, admin: Utilisateur, avec_document: bool):
    from app.models.evenement import Evenement, EvenementEvolution

    ev = Evenement(titre="AG", debut=datetime(2026, 9, 1, 10, 0), auteur_id=admin.id)
    session.add(ev)
    session.commit()
    session.refresh(ev)
    session.add(EvenementEvolution(evenement_id=ev.id, type="commentaire", auteur_id=admin.id))
    if avec_document:
        session.add(
            Document(
                titre="CR",
                fichier_nom="cr.pdf",
                fichier_chemin="/tmp/cr-546.pdf",
                evenement_id=ev.id,
                publie_par_id=admin.id,
            )
        )
    session.commit()
    return ev


def test_supprimer_un_evenement_avec_son_historique(contexte):
    """`evenement_evolution.evenement_id` est NOT NULL et sans `Relationship`."""
    from app.models.evenement import Evenement
    from app.routers.calendrier import delete_evenement

    session, admin = contexte
    ev = _evenement(session, admin, avec_document=False)
    delete_evenement(ev.id, session, admin)
    assert session.get(Evenement, ev.id) is None


def test_supprimer_un_evenement_qui_porte_un_document(contexte):
    """Même famille que le ticket : `document.evenement_id` référence l'événement."""
    from app.models.evenement import Evenement
    from app.routers.calendrier import delete_evenement

    session, admin = contexte
    ev = _evenement(session, admin, avec_document=True)
    delete_evenement(ev.id, session, admin)
    assert session.get(Evenement, ev.id) is None
    restants = session.exec(select(Document).where(Document.evenement_id == ev.id)).all()
    assert restants == [], "les documents de l'événement doivent partir avec lui"
