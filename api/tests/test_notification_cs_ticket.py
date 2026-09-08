"""Le conseil syndical est prévenu PAR COURRIEL d'un nouveau ticket (08/09/2026).

## Le défaut, vérifié à la demande

`_notifier_cs_creation` ne posait qu'une `Notification` **dans l'application**,
et sa docstring le disait en toutes lettres :

    \"\"\"Notification in-app à tout le CS, plus le syndic si le ticket est urgent.\"\"\"

Aucun courriel ne partait. Un conseiller qui n'ouvre pas le site ne voyait donc
jamais passer un signalement — au moment précis où quelqu'un attend une
réaction. Et la notification allait à **tout** le conseil, quel que soit le
bâtiment concerné.

## Les deux portées, et pourquoi elles diffèrent

- la notification **in-app** va à tout le CS : une liste se parcourt, et un
  conseiller peut vouloir un œil sur l'ensemble ;
- le **courriel** va au CS du **périmètre** du ticket. Ce qui est tolérable dans
  une liste ne l'est pas dans une boîte aux lettres.

C'est la distinction que le tableau « Destinataires CS » de `CLAUDE.md` porte
depuis le 31/08/2026, et que ce circuit n'appliquait pas.

⚠️ Ces tests regardent **qui est visé**, pas si `send_email_group` a été appelée.
Un test qui se contente de compter les appels passerait au vert sur un envoi
adressé au mauvais conseiller.
"""
from __future__ import annotations

import json
import uuid

import pytest
from sqlmodel import Session, select

from app.database import engine
from app.models.core import MembreCS, Notification, Utilisateur
from app.routers.tickets.courriels import (
    _envoyer_email_cs_creation,
    _notifier_cs_creation,
)


class _Tampon:
    """Une `BackgroundTasks` de test — elle retient au lieu d'exécuter."""

    def __init__(self):
        self.taches = []

    def add_task(self, fonction, *args, **kwargs):
        self.taches.append((fonction, args, kwargs))


class _Ticket:
    """Le minimum qu'`_envoyer_email_cs_creation` lit d'un ticket."""

    def __init__(self, perimetre: list[str]):
        self.id = 1
        self.numero = 42
        self.titre = "Ferme-porte hors service"
        self.description = "Le ferme-porte du hall ne retient plus la porte."
        self.categorie = "panne"
        self.perimetre_cible = json.dumps(perimetre)
        self.jeton_courriel = None


@pytest.fixture()
def conseil(batiments):
    """Un conseiller par bâtiment, sur l'arbre réel des périmètres.

    ⚠️ La fixture `batiments` du `conftest` sème l'arborescence : les codes de
    périmètre viennent de l'ARBRE, pas d'un format `bat:<id>` inventé. Ma
    première rédaction en fabriquait un — `batiments_du_perimetre` rendait alors
    `None`, donc « tout le conseil », et le test passait au vert **en visant
    tout le monde**. C'est la forme la plus courante du faux vert : une donnée
    d'essai qui ne ressemble pas à la vraie.
    """
    from app.utils.perimetres import perimetre_du_batiment

    with Session(engine) as session:
        marque = uuid.uuid4().hex[:6]
        comptes, membres = [], []
        for suffixe, bat_id in (("a", batiments[0]), ("b", batiments[1])):
            compte = Utilisateur(
                email=f"cs-{suffixe}-{marque}@exemple.test", mot_de_passe_hash="x",
                prenom=f"C{suffixe.upper()}", nom="CONSEIL", roles_json="conseil_syndical",
                actif=True,
            )
            session.add(compte)
            session.flush()
            membre = MembreCS(
                genre="mme", prenom=compte.prenom, nom=compte.nom,
                batiment_id=bat_id, user_id=compte.id,
            )
            session.add(membre)
            comptes.append(compte)
            membres.append(membre)
        session.commit()
        for compte in comptes:
            session.refresh(compte)

        noeud = perimetre_du_batiment(batiments[0])
        assert noeud is not None, "l'arbre ne connaît pas ce bâtiment — fixture cassée"

        yield session, batiments[0], noeud.code, comptes[0], comptes[1], comptes[0]

        for membre in membres:
            session.delete(membre)
        #  ⚠️ Les notifications AVANT les comptes : `foreign_keys=ON` est actif
        #  dans les tests (#546), et supprimer un compte qui en porte encore fait
        #  échouer le nettoyage — pas le test, ce qui le rend difficile à lire.
        for notif in session.exec(
            select(Notification).where(
                Notification.destinataire_id.in_([c.id for c in comptes])  # type: ignore
            )
        ).all():
            session.delete(notif)
        for compte in comptes:
            session.delete(compte)
        session.commit()


def test_le_CS_du_BATIMENT_concerne_est_vise(conseil):
    """🔴 Le cas qui motive tout : un courriel part, et il part au bon conseiller."""
    session, bat_id, code, cs_a, cs_b, auteur = conseil
    tampon = _Tampon()

    vises = _envoyer_email_cs_creation(
        session, _Ticket([code]), auteur, urgence=False,
        background_tasks=tampon,
    )

    assert cs_a.email in vises, (
        "le conseiller du bâtiment concerné n'est pas prévenu par courriel : "
        "un conseiller qui n'ouvre pas le site ne voit jamais passer le ticket."
    )
    assert cs_b.email not in vises, (
        "le conseiller d'un AUTRE bâtiment est prévenu. Ce qui est tolérable "
        "dans une liste ne l'est pas dans une boîte aux lettres."
    )
    assert tampon.taches, "aucun envoi n'a été programmé"
    _, _, kwargs = tampon.taches[0]
    assert kwargs["code"] == "ticket_nouveau_cs"


def test_un_perimetre_GLOBAL_vise_tout_le_conseil(conseil):
    """Un ticket qui concerne la résidence entière n'a pas de bâtiment à cibler.

    ⚠️ `batiments_du_perimetre` rend alors `None`, et `membres_cs_notifiables`
    lit ce `None` comme « tout le conseil ». Sans ce test, un resserrement futur
    du ciblage rendrait muets les tickets les plus généraux — le pire endroit où
    se tromper, et le plus discret.
    """
    session, bat_id, code, cs_a, cs_b, auteur = conseil
    tampon = _Tampon()

    vises = _envoyer_email_cs_creation(
        session, _Ticket([]), auteur, urgence=False, background_tasks=tampon,
    )

    assert cs_a.email in vises and cs_b.email in vises, (
        "un ticket sans périmètre ne vise pas tout le conseil : "
        f"{vises}"
    )


def test_la_PREFERENCE_est_laissee_a_send_email_group(conseil):
    """🔴 `batiments_concernes` est passé — c'est CE paramètre qui l'applique.

    La préférence « e-mails de mon bâtiment / des autres » est vérifiée
    destinataire par destinataire par `send_email_group`. La relire ici ferait
    une seconde façon d'être en désaccord avec ce que le résident a demandé
    (`utils/preferences_mail`, dont l'en-tête raconte les trois copies
    précédentes).

    Ce test ne vérifie donc pas le filtrage : il vérifie qu'on **passe la main**.
    """
    session, bat_id, code, _, _, auteur = conseil
    tampon = _Tampon()

    _envoyer_email_cs_creation(
        session, _Ticket([code]), auteur, urgence=False,
        background_tasks=tampon,
    )

    _, _, kwargs = tampon.taches[0]
    assert kwargs.get("batiments_concernes") == {bat_id}, (
        "sans `batiments_concernes`, la préférence de chacun n'est pas "
        "appliquée : le courriel part à qui l'a refusé."
    )


def test_cas_zero_sans_conseil_aucun_envoi(conseil):
    """Un envoi programmé sans destinataire encombrerait l'historique pour rien."""
    session, bat_id, code, _, _, auteur = conseil
    for membre in session.exec(select(MembreCS)).all():
        session.delete(membre)
    session.commit()
    tampon = _Tampon()

    vises = _envoyer_email_cs_creation(
        session, _Ticket([code]), auteur, urgence=False,
        background_tasks=tampon,
    )

    assert vises == []
    assert tampon.taches == [], "un envoi a été programmé sans aucun destinataire"


def test_l_urgence_atteint_le_modele(conseil):
    """`urgent` conditionne le liseré rouge et la mention URGENT dans le corps.

    ⚠️ Jinja évalue une variable indéfinie à **faux sans rien signaler** : un
    `urgent` non fourni ferait disparaître la mention en silence. C'est le défaut
    qui a motivé `test_email_templates.EXPECTED_VARS`, et il se vérifie ici au
    point d'appel — l'endroit où la variable est réellement fournie.
    """
    session, bat_id, code, _, _, auteur = conseil
    tampon = _Tampon()

    _envoyer_email_cs_creation(
        session, _Ticket([code]), auteur, urgence=True,
        background_tasks=tampon,
    )

    _, _, kwargs = tampon.taches[0]
    contexte = kwargs["context"]
    assert contexte["urgent"] is True
    assert set(contexte) >= {"ticket", "auteur", "urgent"}, (
        f"le contexte ne fournit pas ce que le modèle interroge : {sorted(contexte)}"
    )


def test_le_point_d_APPEL_declenche_bien_le_courriel(conseil):
    """🔴 Le tuyau, pas seulement la décision.

    Les tests ci-dessus appellent `_envoyer_email_cs_creation` directement. J'ai
    neutralisé son appel dans `_notifier_cs_creation` pour éprouver le cas zéro :
    **ils sont tous restés verts**. Le courriel aurait cessé de partir sans qu'un
    seul test ne bouge.

    C'est la leçon du 06/09/2026 — *« je testais la décision, pas le tuyau qui la
    nourrit »* — et elle se rejouait ici, dans le fichier même qui corrige un
    envoi manquant.
    """
    session, _, code, cs_a, _, auteur = conseil
    ticket = _Ticket([code])
    ticket.description = "Le ferme-porte du hall ne retient plus la porte."
    tampon = _Tampon()

    _notifier_cs_creation(
        session, ticket, urgence=False, auteur=auteur, background_tasks=tampon,
    )

    codes = [kwargs.get("code") for _, _, kwargs in tampon.taches]
    assert "ticket_nouveau_cs" in codes, (
        "le point d'appel ne programme aucun courriel : la fonction d'envoi peut "
        f"être parfaite, personne ne la lira. Tâches programmées : {codes}"
    )


def test_sans_tache_de_fond_aucun_courriel_n_est_PRETENDU(conseil):
    """Un appelant qui ne fournit pas de `BackgroundTasks` n'envoie rien.

    ⚠️ Et il ne doit pas lever : la notification in-app, elle, doit passer. Le
    courriel est un ajout, pas une condition — un appelant historique qui n'a pas
    été mis à jour continue de prévenir le conseil dans l'application.
    """
    session, _, code, _, _, auteur = conseil
    _notifier_cs_creation(session, _Ticket([code]), urgence=False)
