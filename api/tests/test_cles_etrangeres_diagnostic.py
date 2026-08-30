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
        #
        #  ⚠️ `expire_all()` est NÉCESSAIRE : la purge supprime des lignes par SQL
        #  direct, sans passer par la session. Les objets qu'elle tient en cache
        #  désignent alors des lignes disparues, et `session.delete()` lève
        #  `ObjectDeletedError` — une erreur de teardown qu'on lirait comme un
        #  échec du test.
        session.rollback()
        session.expire_all()
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


# ── La PURGE ─────────────────────────────────────────────────────────────────
#
#  🔴 Une opération irréversible sur la base de production. Ce que ces tests
#  doivent établir, dans l'ordre d'importance :
#
#    1. elle ne touche PAS les lignes saines — c'est le risque majeur ;
#    2. la simulation ne supprime rien — c'est le mode par défaut ;
#    3. elle supprime bien les orphelines, et rend un compte juste.
#
#  Le premier est le seul dont l'échec serait irrattrapable en production.


def _orpheliner(session, ticket_id: int) -> None:
    """Faire disparaître un ticket sans ses évolutions — le régime de la production."""
    session.commit()
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        try:
            conn.execute(text("DELETE FROM ticket WHERE id = :i"), {"i": ticket_id})
            conn.commit()
        finally:
            #  Cf. le commentaire du test plus haut : le PRAGMA vaut pour la
            #  connexion, et le pool de `:memory:` n'en a qu'une.
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.commit()


def test_la_simulation_ne_supprime_RIEN(admin_et_ticket):
    """Le mode par défaut. Il rend le compte de ce qui partirait, et laisse tout."""
    from app.utils.diagnostic_cles import purger_orphelins

    session, _admin, ticket, evol = admin_et_ticket
    #  ⚠️ Les identifiants sont relevés AVANT : `rollback()` expire les objets,
    #  et lire un attribut d'une ligne disparue déclenche un rafraîchissement
    #  qui lève `ObjectDeletedError` — une erreur de plomberie qu'on lirait
    #  comme un échec du test.
    evol_id = evol.id
    _orpheliner(session, ticket.id)

    resultat = purger_orphelins(engine)  # simuler=True par défaut
    assert resultat["simule"] is True
    assert resultat["supprimees"] == 0
    assert resultat["seraient_supprimees"] >= 1

    session.rollback()
    assert session.get(TicketEvolution, evol_id) is not None, (
        "la simulation a supprimé une ligne — le mode par défaut doit être inoffensif"
    )


def test_la_purge_supprime_les_orphelines_et_rend_un_compte_juste(admin_et_ticket):
    """Le cas nominal, avec le compte par table que l'écran affichera."""
    from app.utils.diagnostic_cles import compter_orphelins, purger_orphelins

    session, _admin, ticket, evol = admin_et_ticket
    evol_id = evol.id
    _orpheliner(session, ticket.id)
    avant = compter_orphelins(engine)["orphelins"]

    resultat = purger_orphelins(engine, simuler=False)
    assert resultat["simule"] is False
    assert resultat["supprimees"] == avant
    assert {t["table"] for t in resultat["par_table"]} >= {"ticket_evolution"}

    session.rollback()
    assert session.get(TicketEvolution, evol_id) is None
    #  Et la base est réellement assainie — vérifié par la MESURE, pas par le
    #  retour de la fonction qui vient de la modifier.
    assert compter_orphelins(engine)["orphelins"] == 0


def test_la_purge_NE_TOUCHE_PAS_les_lignes_saines(admin_et_ticket):
    """🔴 LE TEST QUI COMPTE — celui dont l'échec serait irrattrapable.

    Un second ticket, intact, avec son évolution. La purge doit l'ignorer
    complètement : elle ne supprime que les `rowid` que SQLite désigne, jamais
    « toutes les lignes qui ressemblent à des orphelines ».
    """
    from app.models.core import Ticket
    from app.utils.diagnostic_cles import purger_orphelins

    session, admin, ticket, evol = admin_et_ticket
    evol_id = evol.id

    sain = Ticket(
        numero="TK-SAIN-1", titre="T", description="d", categorie="panne", auteur_id=admin.id
    )
    session.add(sain)
    session.commit()
    session.refresh(sain)
    evol_saine = TicketEvolution(
        ticket_id=sain.id, auteur_id=admin.id, type="commentaire", contenu="intacte"
    )
    session.add(evol_saine)
    session.commit()
    session.refresh(evol_saine)
    sain_id, evol_saine_id = sain.id, evol_saine.id

    _orpheliner(session, ticket.id)
    purger_orphelins(engine, simuler=False)

    session.rollback()
    assert session.get(Ticket, sain_id) is not None, "un ticket sain a été supprimé"
    survivante = session.get(TicketEvolution, evol_saine_id)
    assert survivante is not None, "une évolution SAINE a été supprimée par la purge"
    assert survivante.contenu == "intacte"
    assert session.get(TicketEvolution, evol_id) is None, "l'orpheline, elle, devait partir"

    session.delete(survivante)
    session.commit()
    session.delete(session.get(Ticket, sain_id))
    session.commit()


def test_une_base_saine_ne_declenche_aucune_suppression(admin_et_ticket):
    """Le cas zéro : rien à purger ne doit pas produire d'écriture ni d'erreur."""
    from app.utils.diagnostic_cles import purger_orphelins

    resultat = purger_orphelins(engine, simuler=False)
    assert resultat["ok"] is True
    assert resultat["supprimees"] == 0
    assert resultat["par_table"] == []


def test_le_releve_dit_si_les_cles_sont_ACTIVES(admin_et_ticket):
    """Deux faits distincts, et les confondre a un coût.

    « Aucune ligne orpheline » décrit ce que la base CONTIENT. « Clés actives »
    décrit ce qu'elle REFUSERA demain. Un relevé à zéro sur une base sans clés
    n'est pas une victoire, c'est un sursis — et c'est exactement l'état dans
    lequel la production a vécu jusqu'au 30/08/2026.

    ⚠️ Sans ce champ, on ne pouvait pas vérifier que l'activation avait pris :
    `activer_cles_etrangeres` ne prend PAS effet s'il est appelé après le bloc
    d'amorçage, et rien ne le dit (cf. `app/database.py`).
    """
    from app.utils.diagnostic_cles import compter_orphelins

    resultat = compter_orphelins(engine)
    assert "cles_actives" in resultat, "le relevé doit dire dans quel RÉGIME il a mesuré"
    #  La suite tourne clés actives (conftest) : le champ doit le refléter, sinon
    #  il ne mesure pas ce qu'il prétend.
    assert resultat["cles_actives"] is True
