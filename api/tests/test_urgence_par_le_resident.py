"""Un RÉSIDENT peut dire que son ticket presse — la catégorie le permettait (#820).

## 🔴 La régression que ce fichier ferme

Le 07/09/2026 au matin, la catégorie « Urgence » a été retirée : elle répondait à
la question du DÉLAI dans la liste qui pose celle de la NATURE. Le remplacement
désigné était l'option « Marquer urgent », qui pose `priorite = haute`.

Sauf que **la catégorie était ouverte à tout le monde et l'option était réservée
au conseil syndical** — `epingle`, `urgente` et `confidentiel` figuraient toutes
trois dans `OPTIONS_RESERVEES_AU_CS`, et la section de l'écran est sous
`{#if $isCS}`.

Un résident face à une inondation n'avait donc plus **aucun** moyen de dire que
ça pressait :

* pas de case à l'écran ;
* l'option refusée côté serveur même postée directement ;
* le conseil pas prévenu en urgence (`_notifier_cs_creation`) ;
* l'avertissement « 15 · 17 · 18 » jamais affiché ;
* le message WhatsApp parti en ordinaire.

⚠️ **Le motif écrit dans le code était juste, et il est devenu faux** : « épingler
et marquer urgent ordonnent la liste du conseil : même nature ». C'était vrai
tant que la catégorie portait le signalement en parallèle. En la retirant, cette
option est devenue le seul moyen de décrire sa propre situation — et une
description de sa situation appartient à l'auteur.

C'est la forme la plus discrète de régression : aucune erreur, aucun test rouge,
un formulaire qui s'enregistre normalement. Seule l'information disparaît.

## Ce qui reste réservé, et pourquoi

`epingle` ordonne la liste du conseil ; `confidentiel` décide qui a le droit de
lire (#710). Ni l'une ni l'autre n'est une description de la situation de
l'auteur — elles restent au conseil, et ce fichier le vérifie aussi.
"""
from __future__ import annotations

import uuid

import pytest
from sqlmodel import Session, SQLModel

from app.database import engine
from app.models.core import RoleUtilisateur, Ticket, Utilisateur
from app.routers.tickets.commun import OPTIONS_RESERVEES_AU_CS, OPTIONS_TICKET, appliquer_options
from app.utils.categories_ticket import ticket_urgent
from tests.purge_test import purger_ligne


class _Corps:
    """Le corps d'une requête, réduit aux options — `appliquer_options` ne lit que ça."""

    def __init__(self, **options):
        for cle in OPTIONS_TICKET:
            setattr(self, cle, options.get(cle))


@pytest.fixture()
def ticket() -> Ticket:
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        auteur = Utilisateur(
            email=f"resident-{uuid.uuid4().hex[:8]}@exemple.test",
            mot_de_passe_hash="x",
            prenom="Renée",
            nom="Sidente",
            role=RoleUtilisateur.résident,
        )
        session.add(auteur)
        session.commit()
        session.refresh(auteur)
        tk = Ticket(
            numero=f"T-{uuid.uuid4().hex[:6]}",
            titre="Inondation dans le hall",
            description="<p>L'eau monte.</p>",
            categorie="sinistre",
            auteur_id=auteur.id,
            perimetre_cible='["résidence"]',
        )
        session.add(tk)
        session.commit()
        session.refresh(tk)
        yield tk
        #  ⚠️ Rechargés avant la purge : le test a modifié `tk` dans SA session,
        #  et supprimer une instance devenue périmée fait échouer le teardown
        #  (`supports_sane_rowcount`) — un test vert accompagné d'une erreur, ce
        #  qui est le pire des deux mondes.
        session.rollback()
        for modele, cle in ((Ticket, tk.id), (Utilisateur, auteur.id)):
            purger_ligne(session, modele, cle)
        session.commit()


def test_un_resident_peut_marquer_son_ticket_urgent(ticket):
    """Le cœur du sujet : c'est ce que la catégorie « Urgence » permettait."""
    changees = appliquer_options(ticket, _Corps(urgente=True), est_cs=False)

    assert "urgente" in changees, (
        "Un résident doit pouvoir dire que son ticket presse. La catégorie "
        "« Urgence » le permettait à tout le monde ; l'option qui la remplace doit "
        "le permettre aussi, sinon le retrait a supprimé une capacité."
    )
    assert ticket_urgent(ticket), ticket.priorite


def test_un_resident_ne_peut_ni_epingler_ni_restreindre(ticket):
    """Le cas zéro : sans lui, ce fichier passerait au vert en ouvrant TOUT.

    Ouvrir `urgente` ne doit pas ouvrir les deux autres. `epingle` ordonne la
    liste du conseil, `confidentiel` décide de l'audience — deux décisions qui ne
    sont pas celles de l'auteur.
    """
    changees = appliquer_options(ticket, _Corps(epingle=True, confidentiel=True), est_cs=False)

    assert changees == [], f"un résident a pu poser : {changees}"
    assert not ticket.epingle
    assert not ticket.confidentiel


def test_le_conseil_garde_les_trois(ticket):
    changees = appliquer_options(
        ticket, _Corps(epingle=True, urgente=True, confidentiel=True), est_cs=True
    )
    assert set(changees) == {"epingle", "urgente", "confidentiel"}, changees


def test_la_table_des_reservees_dit_ce_que_les_tests_verifient():
    """Le contrat, écrit une fois — pas déduit du comportement observé.

    Sans cette assertion, quelqu'un pourrait remettre `urgente` dans la table et
    ne casser qu'un test dont le nom parle d'un résident : le lien avec la
    RÈGLE serait perdu, et c'est la règle qu'on protège.
    """
    assert "urgente" not in OPTIONS_RESERVEES_AU_CS, (
        "`urgente` a été rendue à l'auteur le 07/09/2026, en réparation de la "
        "régression du retrait de la catégorie « Urgence » (migration 0177)."
    )
    assert set(OPTIONS_RESERVEES_AU_CS) == {"epingle", "confidentiel"}
