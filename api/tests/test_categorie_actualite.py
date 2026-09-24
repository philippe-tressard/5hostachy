"""« Actualité » devient une CATÉGORIE d'affaire (#1091, lot 3a — 23/09/2026).

Arbitrages de l'utilisateur, 22 et 23/09/2026 : un seul objet, l'Affaire ;
« Actualité » est une catégorie réservée au conseil, **sans cycle de vie** — ni
statut ni numéro visibles, hors kanban —, qui périme au lieu de se clore ; la
liste se filtre Tous / Actualité / Affaire / Événement, la nature se DÉDUIT.

Chaque règle est éprouvée là où elle vit, et une fois : ces tests en sont la
spécification (conception dans #1091).
"""

from __future__ import annotations

import ast
import pathlib
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlmodel import Session

from app.auth.deps import peut_editer
from app.database import engine
from app.models.core import (
    STATUTS_TICKET_ACTIFS,
    RoleUtilisateur,
    StatutUtilisateur,
    Ticket,
    Utilisateur,
)
from app.models.tickets import CategorieTicket, StatutTicket
from app.routers.tickets import crud, mise_a_jour
from app.routers.tickets.commun import ticket_read
from app.schemas import TicketCreate, TicketUpdate
from app.utils.archivage import est_archivable
from app.utils.kanban_tickets import colonne_du_ticket
from app.utils.nature_affaire import natures
from app.utils.perimetres import arbre
from app.utils.visibility import ticket_visible

_APP = pathlib.Path(__file__).resolve().parents[1] / "app"


@pytest.fixture()
def session(monkeypatch, batiments):
    #  Les envois ont leurs propres tests : ici, les règles.
    monkeypatch.setattr(crud, "_notifier_cs_creation", lambda *a, **k: None, raising=False)
    arbre()  # chargé AVANT les transactions (base `:memory:` à connexion unique)
    with Session(engine) as s:
        yield s


def _compte(session, *, role=None, statut=StatutUtilisateur.copropriétaire_résident):
    u = Utilisateur(
        email=f"act-{uuid.uuid4().hex[:8]}@exemple.test",
        mot_de_passe_hash="x",
        prenom="P",
        nom="N",
        actif=True,
        statut=statut,
        roles_json=role.value if role else "résident",
    )
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


def _creer(session, user, **champs):
    corps = TicketCreate(titre="Coupure d'eau", description="Jeudi matin.", **champs)
    return crud.create_ticket(corps, BackgroundTasks(), session=session, user=user)


# ── La catégorie, et qui la pose ────────────────────────────────────────────


def test_la_categorie_existe():
    assert CategorieTicket("actualite") is CategorieTicket.actualite


def test_un_resident_ne_publie_pas_d_actualite(session):
    resident = _compte(session)
    with pytest.raises(HTTPException) as refus:
        _creer(session, resident, categorie="actualite")
    assert refus.value.status_code == 403


def test_une_actualite_nait_sans_cycle(session):
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    lu = _creer(session, cs, categorie="actualite")
    assert lu.statut == StatutTicket.publie.value
    #  Et le conseil ne peut pas lui imposer un état de suivi à la création.
    lu2 = _creer(session, cs, categorie="actualite", statut="en_cours")
    assert lu2.statut == StatutTicket.publie.value


def test_une_affaire_ne_nait_jamais_publiee(session):
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    assert _creer(session, cs, categorie="panne", statut="publie").statut == "ouvert"


# ── « Sans cycle » : hors des suivis, par construction ─────────────────────


def test_publie_n_est_pas_un_etat_actif_ni_une_colonne_du_kanban():
    assert "publie" not in STATUTS_TICKET_ACTIFS
    assert colonne_du_ticket("publie") is None


def test_personne_ne_selectionne_plus_par_non_clos():
    """`notin_(STATUTS_TICKET_CLOS)` ramassait tout ce qui n'est pas clos — les
    actualités comprises. Ce qui demande un suivi se sélectionne par
    `STATUTS_TICKET_ACTIFS`, qui l'énumère."""
    fautes = []
    for p in _APP.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if (
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and n.func.attr == "notin_"
                and "STATUTS_TICKET_CLOS" in ast.unparse(n)
            ):
                fautes.append(f"{p.relative_to(_APP)}:{n.lineno}")
    assert not fautes, f"Sélection « non clos » — employer STATUTS_TICKET_ACTIFS : {fautes}"


# ── La nature, pour le filtre — dérivée, jamais saisie ────────────────────


def _t(categorie="panne", debut=None) -> Ticket:
    return Ticket(
        numero="TK-1", titre="T", description="D", categorie=categorie, auteur_id=1, debut=debut
    )


def test_la_nature_se_deduit():
    assert natures(_t("actualite")) == ["actualite"]
    assert natures(_t("panne")) == ["activite"]
    #  Une date fait paraître au filtre « Calendrier », quelle que soit la
    #  catégorie — et une affaire datée N'EST PLUS « Activité » (#1092, 23/09 :
    #  « Calendrier : si une date est définie ; Activité : le reste »).
    date = datetime(2026, 10, 1, 9, 0)
    assert natures(_t("panne", date)) == ["calendrier"]
    assert natures(_t("actualite", date)) == ["actualite", "calendrier"]
    assert natures(_t(CategorieTicket.actualite)) == ["actualite"], "l'énumération aussi"


# ── La visibilité : celle de l'ACTUALITÉ, pas celle de l'affaire ─────────


def test_un_locataire_lit_une_actualite_mais_pas_une_affaire(session):
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    locataire = _compte(session, statut=StatutUtilisateur.locataire)
    actu = session.get(Ticket, _creer(session, cs, categorie="actualite").id)
    affaire = session.get(Ticket, _creer(session, cs, categorie="panne").id)
    assert ticket_visible(actu, locataire), "une actualité s'adresse à la copropriété"
    assert not ticket_visible(affaire, locataire), "la règle des affaires ne bouge pas"


def test_une_actualite_reservee_au_conseil_ne_se_lit_pas(session):
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    resident = _compte(session)
    actu = session.get(Ticket, _creer(session, cs, categorie="actualite", confidentiel=True).id)
    assert not ticket_visible(actu, resident)
    assert ticket_visible(actu, cs)


# ── L'édition : par le conseil, tant qu'elle est publiée ─────────────────


def test_le_conseil_corrige_une_actualite_qu_il_n_a_pas_ecrite(session):
    auteur = _compte(session, role=RoleUtilisateur.conseil_syndical)
    autre_cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    resident = _compte(session)
    actu = session.get(Ticket, _creer(session, auteur, categorie="actualite").id)
    assert peut_editer(actu, autre_cs)
    assert not peut_editer(actu, resident)
    corps = TicketUpdate(titre="Coupure d'eau — reportée")
    lu = mise_a_jour.update_ticket(
        actu.id, corps, BackgroundTasks(), session=session, user=autre_cs
    )
    assert lu.titre == "Coupure d'eau — reportée"


def test_l_arrivant_corrige_son_annonce_sans_decider_qui_la_lit(session):
    """#821 : l'arrivant est l'auteur de sa propre annonce, pour la corriger.

    Il en corrige le TEXTE ; à qui l'on parle et l'Accès restent au conseil —
    ignorés pour lui, comme les options, et non refusés.
    """
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    arrivant = _compte(session)
    actu = session.get(Ticket, _creer(session, cs, categorie="actualite").id)
    #  L'annonce d'arrivée est écrite AU NOM de l'arrivant (`utils/annonce_arrivee`).
    actu.auteur_id = arrivant.id
    session.add(actu)
    session.commit()
    assert peut_editer(actu, arrivant)
    corps = TicketUpdate(
        titre="Bienvenue à Alix", public_cible=["conseil_syndical"], reserve_perimetre=True
    )
    lu = mise_a_jour.update_ticket(
        actu.id, corps, BackgroundTasks(), session=session, user=arrivant
    )
    assert lu.titre == "Bienvenue à Alix"
    relue = session.get(Ticket, actu.id)
    assert relue.public_cible is None and relue.reserve_perimetre is False


# ── Changer de catégorie : la promotion, sans conversion ─────────────────


def test_une_actualite_promue_en_affaire_s_ouvre(session):
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    actu = _creer(session, cs, categorie="actualite")
    lu = mise_a_jour.update_ticket(
        actu.id, TicketUpdate(categorie="panne"), BackgroundTasks(), session=session, user=cs
    )
    assert (lu.categorie, lu.statut) == ("panne", "ouvert")
    lu = mise_a_jour.update_ticket(
        actu.id, TicketUpdate(categorie="actualite"), BackgroundTasks(), session=session, user=cs
    )
    assert (lu.categorie, lu.statut) == ("actualite", "publie")


def test_un_resident_ne_fait_pas_de_son_affaire_une_actualite(session):
    resident = _compte(session)
    affaire = _creer(session, resident, categorie="panne")
    with pytest.raises(HTTPException) as refus:
        mise_a_jour.update_ticket(
            affaire.id,
            TicketUpdate(categorie="actualite"),
            BackgroundTasks(),
            session=session,
            user=resident,
        )
    assert refus.value.status_code == 403


# ── L'archivage : la péremption de l'actualité ───────────────────────────


def test_une_actualite_datee_perimee_s_archive_meme_epinglee():
    passee = datetime.utcnow() - timedelta(days=3)
    actu = _t("actualite", passee)
    actu.statut, actu.fin, actu.epingle = "publie", passee, True
    actu.cree_le = actu.mis_a_jour_le = datetime.utcnow()
    assert est_archivable("ticket", actu, seuil_jours=30)


def test_une_actualite_permanente_epinglee_reste():
    actu = _t("actualite")
    actu.statut, actu.epingle = "publie", True
    actu.cree_le = actu.mis_a_jour_le = datetime.utcnow() - timedelta(days=90)
    assert not est_archivable("ticket", actu, seuil_jours=30)


def test_une_affaire_ouverte_ne_perime_jamais():
    passee = datetime.utcnow() - timedelta(days=3)
    affaire = _t("panne", passee)
    affaire.statut, affaire.fin = "ouvert", passee
    affaire.cree_le = affaire.mis_a_jour_le = datetime.utcnow()
    assert not est_archivable("ticket", affaire, seuil_jours=30)


# ── La lecture rend ce qu'il faut pour filtrer ──────────────────────────


def test_la_lecture_rend_la_nature_et_le_public(session, batiments):
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    lu = _creer(
        session,
        cs,
        categorie="actualite",
        public_cible=["locataires"],
        reserve_perimetre=True,
        perimetre_cible=[f"bat:{batiments[0]}"],
    )
    relu = ticket_read(session.get(Ticket, lu.id), session)
    assert relu.natures == ["actualite"]
    assert relu.public_cible == ["locataires"]
    assert relu.reserve_perimetre is True


def test_reserve_au_perimetre_sur_la_copropriete_entiere_est_retire(session):
    """🔒 sur un périmètre global ne retire la lecture à personne : le drapeau
    mentirait. Il est retiré à l'écriture (`actualite.appliquer_acces`)."""
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    lu = _creer(session, cs, categorie="actualite", reserve_perimetre=True)
    assert lu.reserve_perimetre is False


# ── Une actualité n'a pas d'état : ni par une Suite, ni par le PATCH ──────


def test_une_suite_ne_fait_pas_avancer_une_actualite(session):
    from app.routers.tickets import evolutions
    from app.schemas_tickets import TicketEvolutionCreate

    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    actu = _creer(session, cs, categorie="actualite")
    with pytest.raises(HTTPException) as refus:
        evolutions.add_evolution(
            actu.id,
            TicketEvolutionCreate(type="etat", nouveau_statut="résolu"),
            BackgroundTasks(),
            session=session,
            user=cs,
        )
    assert refus.value.status_code == 422
    #  Une parole, elle, passe : une actualité se commente.
    evolutions.add_evolution(
        actu.id,
        TicketEvolutionCreate(type="commentaire", contenu="Report à mardi."),
        BackgroundTasks(),
        session=session,
        user=cs,
    )


def test_publie_ne_s_atteint_par_aucune_transition(session):
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    affaire = _creer(session, cs, categorie="panne")
    with pytest.raises(HTTPException) as refus:
        mise_a_jour.update_ticket(
            affaire.id, TicketUpdate(statut="publie"), BackgroundTasks(), session=session, user=cs
        )
    assert refus.value.status_code == 422
