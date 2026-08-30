"""L'endpoint de diagnostic voit-il vraiment les lignes orphelines ? (#546, étape 2 bis)

## Ce qu'il faut prouver, et l'ordre compte

Un endpoint qui rend `orphelins: 0` sur une base saine ne prouve **rien** : il
rendrait le même chiffre s'il ne regardait nulle part. C'est le cas zéro de
`standards/04` §2, et il est particulièrement traître ici parce que le résultat
NORMAL est justement zéro.

Ces tests posent donc de vrais orphelins et vérifient que l'endpoint les compte,
les nomme, et sait dire qu'il n'a pas pu mesurer.

## Comment on fabrique un orphelin

En désactivant les clés le temps d'une suppression — exactement le régime de la
production aujourd'hui. C'est la seule façon honnête : sous
`foreign_keys=ON` (le régime de la suite), la base refuserait de les créer.
"""

import pytest
from sqlalchemy import text
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models.core import RoleUtilisateur, Ticket, TicketEvolution, Utilisateur
from app.routers.admin.exploitation import db_cles_etrangeres

EMAIL = "orphelin-546@test.fr"


@pytest.fixture()
def admin_et_ticket():
    """Un ticket avec une évolution — dont on fera un orphelin."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.rollback()
        for u in session.exec(select(Utilisateur).where(Utilisateur.email == EMAIL)).all():
            for t in session.exec(select(Ticket).where(Ticket.auteur_id == u.id)).all():
                for e in session.exec(
                    select(TicketEvolution).where(TicketEvolution.ticket_id == t.id)
                ).all():
                    session.delete(e)
                session.delete(t)
            session.delete(u)
        session.commit()

        admin = Utilisateur(
            email=EMAIL,
            hashed_password="x",
            prenom="Odile",
            nom="Orpheline",
            role=RoleUtilisateur.admin,
            actif=True,
        )
        session.add(admin)
        session.commit()
        session.refresh(admin)
        ticket = Ticket(
            numero="TK-ORPH-1",
            titre="T",
            description="d",
            categorie="panne",
            auteur_id=admin.id,
        )
        session.add(ticket)
        session.commit()
        session.refresh(ticket)
        evol = TicketEvolution(
            ticket_id=ticket.id, auteur_id=admin.id, type="commentaire", contenu="c"
        )
        session.add(evol)
        session.commit()
        session.refresh(evol)
        yield session, admin, ticket, evol

        #  Nettoyage : l'orphelin éventuel d'abord, sinon le ticket ne part pas.
        session.rollback()
        for e in session.exec(select(TicketEvolution).where(TicketEvolution.auteur_id == admin.id)).all():
            session.delete(e)
        for t in session.exec(select(Ticket).where(Ticket.auteur_id == admin.id)).all():
            session.delete(t)
        session.commit()
        session.delete(admin)
        session.commit()


def test_une_base_saine_ne_signale_rien(admin_et_ticket):
    """Le témoin — sans lui, on ne saurait pas distinguer « rien trouvé » de « rien vu »."""
    resultat = db_cles_etrangeres(None)
    assert resultat["inconnu"] is False
    assert resultat["ok"] is True
    assert resultat["orphelins"] == 0


def test_un_orphelin_est_compte_ET_nomme(admin_et_ticket):
    """🔴 LE CAS QUI COMPTE : une évolution dont le ticket a disparu.

    C'est exactement ce que `delete_evenement` a produit en production pendant
    des mois, transposé sur une table que ce test peut monter.

    L'endpoint doit dire **quelle colonne** est en cause — un `fkid` brut ne
    permettrait pas de décider quoi que ce soit.
    """
    session, _admin, ticket, evol = admin_et_ticket

    #  Fabriquer l'orphelin sous le régime de la production : clés désactivées le
    #  temps de la suppression. Sous `foreign_keys=ON`, la base refuserait.
    session.commit()
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        try:
            conn.execute(text("DELETE FROM ticket WHERE id = :i"), {"i": ticket.id})
            conn.commit()
        finally:
            #  🔴 REMETTRE LES CLÉS, ET DANS UN `finally`.
            #
            #  `PRAGMA foreign_keys` vaut pour la CONNEXION, et le pool de
            #  `sqlite:///:memory:` n'en a qu'une : la laisser désactivée
            #  désarmerait les clés pour **tous les tests suivants** — soit
            #  exactement le régime que l'étape 2 de #546 a mis quatre lots à
            #  établir, défait par une ligne de diagnostic.
            #
            #  Trouvé par `test_integrite_referentielle`, qui existe pour ça et
            #  qui a mordu dès la première exécution complète de la suite. Le
            #  test isolé, lui, passait : c'est la preuve qu'un garde-fou
            #  transversal voit ce qu'un test ne voit pas.
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.commit()

    resultat = db_cles_etrangeres(None)
    assert resultat["inconnu"] is False
    assert resultat["ok"] is False, "une base qui porte un orphelin n'est pas ok"
    assert resultat["orphelins"] >= 1

    relations = {
        (r["table"], r["colonne"], r["table_parente"]) for r in resultat["par_relation"]
    }
    assert ("ticket_evolution", "ticket_id", "ticket") in relations, (
        "la relation fautive doit être nommée par sa COLONNE, pas par un index de clé. "
        f"Obtenu : {resultat['par_relation']}"
    )
    assert evol.id is not None


def test_une_mesure_impossible_rend_INCONNU_et_non_zero(monkeypatch):
    """Un contrôle qui ne peut pas s'exécuter ne rend jamais « rien à signaler ».

    Sans ce champ, une base injoignable produirait `orphelins: 0` — le faux vert
    exact que `standards/04` §1 interdit, et celui qui a coûté le plus cher à ce
    projet.
    """
    import app.database

    class MoteurCasse:
        def connect(self):
            raise RuntimeError("base injoignable")

    #  L'endpoint importe `engine` DANS son corps : remplacer l'attribut du
    #  module suffit, et c'est ce qui rend ce cas testable sans toucher la base.
    monkeypatch.setattr(app.database, "engine", MoteurCasse())
    resultat = db_cles_etrangeres(None)
    assert resultat["inconnu"] is True
    assert resultat["ok"] is False
    assert "orphelins" not in resultat, "ne pas rendre un compte qu'on n'a pas mesuré"
