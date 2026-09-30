"""Les DESTINATAIRES d'une affaire suivie (#1343) — qui les écrit, et quand.

Qui les LIT est éprouvé ailleurs, contre la pastille de lecture
(`test_lecture_pastille.py`, `donnees/lecture_pastille.json`). Ce fichier tient
ce qui l'y amène :

1. le conseil les pose depuis une Suite, sur une affaire comme sur une actualité ;
2. une actualité promue en affaire PERD son public visé — il déciderait qui la
   lit sans que personne l'ait choisi pour elle —, sauf s'il est renvoyé dans
   la même correction (l'écran montre les Destinataires, ce qu'il montre part) ;
3. vides, rien ne change : la règle par défaut décide.
"""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi import BackgroundTasks
from sqlmodel import Session, SQLModel

from app.database import engine
from app.models.core import StatutTicket, StatutUtilisateur, Ticket, Utilisateur
from app.routers.tickets.evolutions import add_evolution
from app.routers.tickets.mise_a_jour import update_ticket
from app.schemas import TicketEvolutionCreate, TicketUpdate
from app.utils.visibility import hors_du_hall, reservee_au_conseil, ticket_visible
from tests.purge_test import purger_ligne


def _compte(session, roles: str, statut=None) -> Utilisateur:
    u = Utilisateur(
        email=f"dest-{uuid.uuid4().hex[:8]}@exemple.test",
        mot_de_passe_hash="x",
        prenom="Camille",
        nom="Sorel",
        roles_json=roles,
        statut=statut,
        actif=True,
    )
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


@pytest.fixture()
def contexte(batiments):
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        cs = _compte(session, "conseil_syndical")
        locataire = _compte(session, "résident", StatutUtilisateur.locataire)
        locataire.batiment_id = batiments[0]
        session.add(locataire)
        session.commit()
        crees: list[Ticket] = []

        def affaire(
            categorie="nuisance", public=None
        ) -> Ticket:  # pas « panne » : sa lecture par défaut lui est propre (#1343)
            t = Ticket(
                numero=f"T-{uuid.uuid4().hex[:6]}",
                titre="Fuite au 3e",
                description="…",
                categorie=categorie,
                auteur_id=cs.id,
                statut=StatutTicket.publie if categorie == "actualite" else StatutTicket.ouvert,
                perimetre_cible=json.dumps(["résidence"], ensure_ascii=False),
                public_cible=json.dumps(public) if public else None,
            )
            session.add(t)
            session.commit()
            session.refresh(t)
            crees.append(t)
            return t

        yield session, cs, locataire, affaire
        for t in crees:
            purger_ligne(session, Ticket, t.id)
        for u in (cs, locataire):
            purger_ligne(session, Utilisateur, u.id)
        session.commit()


def test_sans_choix_une_affaire_suivie_reste_fermee_aux_locataires(contexte):
    session, _cs, locataire, affaire = contexte
    assert not ticket_visible(affaire(), locataire)


def test_le_conseil_pose_les_destinataires_d_une_affaire_depuis_une_suite(contexte):
    session, cs, locataire, affaire = contexte
    t = affaire()
    add_evolution(
        t.id,
        TicketEvolutionCreate(
            type="commentaire", contenu="Ouverte aux locataires.", public_cible=["locataires"]
        ),
        BackgroundTasks(),
        session=session,
        user=cs,
    )
    session.refresh(t)
    assert json.loads(t.public_cible) == ["locataires"]
    assert ticket_visible(t, locataire)


def test_revenir_au_defaut_depuis_une_suite_efface_le_choix(contexte):
    session, cs, locataire, affaire = contexte
    t = affaire(public=["locataires"])
    add_evolution(
        t.id,
        TicketEvolutionCreate(type="commentaire", contenu="Retour à la règle.", public_cible=[]),
        BackgroundTasks(),
        session=session,
        user=cs,
    )
    session.refresh(t)
    assert t.public_cible is None
    assert not ticket_visible(t, locataire)


def test_une_actualite_promue_perd_son_public_vise(contexte):
    """Le résidu que la migration 0228 efface en base, effacé aussi au geste."""
    session, cs, locataire, affaire = contexte
    t = affaire(categorie="actualite", public=["locataires"])
    update_ticket(
        t.id, TicketUpdate(categorie="nuisance"), BackgroundTasks(), session=session, user=cs
    )
    session.refresh(t)
    assert t.public_cible is None
    assert not ticket_visible(t, locataire)


def test_promue_avec_ses_destinataires_renvoyes_elle_les_garde(contexte):
    session, cs, locataire, affaire = contexte
    t = affaire(categorie="actualite", public=["locataires"])
    update_ticket(
        t.id,
        TicketUpdate(categorie="nuisance", public_cible=["locataires"]),
        BackgroundTasks(),
        session=session,
        user=cs,
    )
    session.refresh(t)
    assert json.loads(t.public_cible) == ["locataires"]
    assert ticket_visible(t, locataire)


#  ── Rien ne sort d'une affaire fermée par sa catégorie (#1436) ───────────────
#
#  « Résident concerné » ou « Conseil syndical seul » PAR DÉFAUT ferment
#  l'affaire au voisinage comme la case cochée : ni groupe WhatsApp, ni hall.
#  Un choix du conseil prime — il rouvre ce que la catégorie fermait.


def _nue(categorie: str, public=None, confidentiel=False) -> Ticket:
    """L'objet tel que la règle le lit — jamais enregistré."""
    return Ticket(
        numero="T-1436",
        titre="Défaut",
        description="…",
        categorie=categorie,
        auteur_id=1,
        perimetre_cible='["résidence"]',
        public_cible=json.dumps(public, ensure_ascii=False) if public else None,
        confidentiel=confidentiel,
    )


@pytest.mark.parametrize(
    "categorie",
    ["nuisance", "acces_accueil", "sinistre", "question", "bug", "etude_travaux"],
)
def test_une_affaire_fermee_par_sa_categorie_ne_sort_pas(categorie):
    assert reservee_au_conseil(_nue(categorie))
    assert hors_du_hall(_nue(categorie))


@pytest.mark.parametrize("categorie", ["espaces_verts", "panne", "entretien"])
def test_une_affaire_ouverte_par_sa_categorie_peut_sortir(categorie):
    assert not reservee_au_conseil(_nue(categorie))
    assert not hors_du_hall(_nue(categorie))


def test_chaque_categorie_a_son_defaut():
    """Aucune catégorie ne retombe sur `DEFAUT_INCONNU` (29/09/2026).

    La règle historique — les copropriétaires, sans choix du conseil — a quitté
    `ticket_visible` avec sa dernière catégorie, Étude & travaux. Une catégorie
    ajoutée sans entrée dans la table serait lue du conseil seul, en silence :
    fermé, donc sûr, mais pas décidé. La Panne a sa règle, l'Actualité la sienne.
    """
    from app.models.tickets import CategorieTicket
    from app.utils.visibility import DEFAUT_PAR_CATEGORIE

    #  L'énumération porte aussi les anciennes priorités (basse, normale, haute).
    categories = {c.value for c in CategorieTicket} - {"basse", "normale", "haute"}
    assert categories - {"panne", "actualite"} == set(DEFAUT_PAR_CATEGORIE)


def test_etude_travaux_est_lue_du_seul_conseil_sans_choix():
    """Arbitré le 29/09/2026 : une étude est le dossier du conseil."""
    from app.utils.visibility import destinataires_par_defaut

    assert destinataires_par_defaut(_nue("etude_travaux")) == ["conseil_syndical"]


def test_entretien_est_lu_des_coproprietaires_sans_choix():
    """Arbitré le 30/09/2026 : occupants et bailleurs — ni locataires, ni mandataires.

    Il était au conseil seul depuis #1436. Les codes sont ceux que proposent les
    pastilles : `copropriétaires` n'en est plus un depuis #1301.
    """
    from app.utils.visibility import destinataires_par_defaut

    assert destinataires_par_defaut(_nue("entretien")) == ["copropriétaires_occupants", "bailleurs"]


def test_un_choix_du_conseil_referme_un_entretien():
    assert reservee_au_conseil(_nue("entretien", public=["conseil_syndical"]))
    assert reservee_au_conseil(_nue("entretien", confidentiel=True))


def test_un_choix_du_conseil_rouvre_ce_que_la_categorie_fermait():
    assert not reservee_au_conseil(_nue("nuisance", public=["locataires"]))
    assert not reservee_au_conseil(_nue("etude_travaux", public=["copropriétaires_occupants"]))
    assert reservee_au_conseil(_nue("etude_travaux", public=["conseil_syndical"]))
    assert reservee_au_conseil(_nue("espaces_verts", confidentiel=True))
