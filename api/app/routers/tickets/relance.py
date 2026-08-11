"""Tickets — relance groupée du syndic.

Extrait de `tickets.py` le 08/08/2026. Voir `__init__.py` pour la règle de découpage.

Domaine à part entière : c'est le seul endroit qui écrit au syndic **au nom du
conseil syndical**, avec sa civilité, l'ancienneté réelle des dossiers et
l'historique de chaque ticket.
"""
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import ConfigSite, GenreCivilite, Ticket, TicketEvolution, Utilisateur
from app.schemas import TicketRead
from app.utils.dates_fr import date_courte, formule_anciennete, mois_ecoules
from app.utils.destinataires import formule_appel, interlocuteurs_syndic
from app.utils.perimetres import perimetre_label_json

from .commun import (
    STATUT_LABELS,
    compter_relances,
    config_site,
    destinataires_syndic_cs,
    libelle_evolution,
    syndic_principal,
    ticket_read,
)

router = APIRouter()

#: Délai par défaut, en jours, avant qu'un ticket syndic soit relançable.
_DELAI_DEFAUT_J = 30


class RelanceSyndicRequest(BaseModel):
    ticket_ids: list[int]


class RelanceSyndicResponse(BaseModel):
    delai_jours: int
    tickets: list[TicketRead]


def _delai_jours(session: Session) -> int:
    cfg = session.exec(
        select(ConfigSite).where(ConfigSite.cle == "relance_syndic_delai_jours")
    ).first()
    return int(cfg.valeur) if cfg else _DELAI_DEFAUT_J


@router.get("/relance-syndic", response_model=RelanceSyndicResponse)
def list_relance_syndic(
    session: Session = Depends(get_session),
    _user: Utilisateur = Depends(require_cs_or_admin),
):
    """Tickets ouverts susceptibles de relance syndic.

    Non résolus/annulés/fermés, hors catégorie « bug » (technique/site, du
    ressort admin), et non tagués `non_relancable`. Le frontend distingue les
    tickets éligibles (passé le délai) des candidats (pas encore au délai).
    """
    tickets = session.exec(
        select(Ticket).where(
            Ticket.categorie != "bug",
            Ticket.statut.notin_(["résolu", "annulé", "fermé"]),
            Ticket.non_relancable == False,  # noqa: E712
        ).order_by(Ticket.mis_a_jour_le)
    ).all()
    return RelanceSyndicResponse(
        delai_jours=_delai_jours(session),
        tickets=[ticket_read(t, session) for t in tickets],
    )


def _contexte_ticket(session: Session, ticket: Ticket) -> dict:
    """Un ticket tel que le tableau de l'e-mail de relance l'affiche."""
    evols = session.exec(
        select(TicketEvolution)
        .where(TicketEvolution.ticket_id == ticket.id)
        .order_by(TicketEvolution.cree_le)
    ).all()
    historique = [{
        "date": date_courte(ticket.cree_le),
        "label": f"Création du ticket (statut : {STATUT_LABELS.get(ticket.statut, ticket.statut)})",
    }]
    historique += [
        {"date": date_courte(e.cree_le), "label": libelle_evolution(e)} for e in evols
    ]
    return {
        "numero": ticket.numero,
        "titre": ticket.titre,
        "categorie": ticket.categorie,
        "priorite": ticket.priorite,
        #  `vide=""` : un ticket sans périmètre n'affiche aucune ligne, là où le
        #  fil d'activité afficherait « Copropriété entière ». Cf. utils/perimetres.
        "perimetre": perimetre_label_json(ticket.perimetre_cible),
        "description": ticket.description,
        # La relance qui vient d'être enregistrée ne se compte pas elle-même.
        "relance_count": compter_relances(session, ticket.id) - 1,
        "historique": historique,
    }


@router.post("/relance-syndic", status_code=200)
def envoyer_relance_syndic(
    body: RelanceSyndicRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Mail de relance groupé au syndic principal, en copie des membres du CS.

    Chaque ticket relancé reçoit une évolution « relance », ce qui le date et le
    rend traçable.
    """
    from app.utils.email import send_email_group

    if not body.ticket_ids:
        raise HTTPException(422, "Aucun ticket sélectionné")

    tickets_relance: list[Ticket] = []
    for tid in body.ticket_ids:
        t = session.get(Ticket, tid)
        if not t:
            raise HTTPException(404, f"Ticket {tid} introuvable")
        if t.categorie == "bug":
            raise HTTPException(
                422, f"Ticket {tid} (catégorie bug) non concerné par la relance syndic"
            )
        tickets_relance.append(t)

    now = datetime.utcnow()
    for ticket in tickets_relance:
        session.add(TicketEvolution(
            ticket_id=ticket.id,
            type="relance",
            contenu=f"Relance syndic n°{compter_relances(session, ticket.id) + 1}",
            auteur_id=user.id,
            cree_le=now,
        ))
        ticket.mis_a_jour_le = now
        #  Relancer un ticket l'escalade au syndic (utile pour ceux pas encore
        #  explicitement adressés au syndic) → cohérence avec le mail envoyé.
        ticket.destinataire_syndic = True
        session.add(ticket)

    session.flush()

    principal = syndic_principal(session)
    if not principal or not principal.email:
        raise HTTPException(422, "Aucun gestionnaire syndic principal avec email configuré")

    cfg = config_site(session)

    #  Ancienneté réelle des dossiers relancés : le préambule annonçait « plus
    #  d'un mois » quelle que soit la situation, y compris pour des tickets en
    #  souffrance depuis cinq mois. Mesurée sur `mis_a_jour_le`, c'est-à-dire sur
    #  la dernière avancée — le même repère que celui qui rend un ticket
    #  relançable.
    anciennete = formule_anciennete(
        [mois_ecoules(t.mis_a_jour_le or t.cree_le, now) for t in tickets_relance]
    )

    ctx = {
        #  La formule d'appel s'adresse à la gestionnaire ET à l'assistante de
        #  gestion : le cabinet fonctionne en binôme, l'une supplée l'autre en son
        #  absence. Les personnes viennent de l'annuaire, choisies par leur
        #  FONCTION — écrire les noms en dur ne survivrait pas au premier
        #  changement de personnel.
        "interlocuteurs": formule_appel(interlocuteurs_syndic(session)),
        #  Les deux variables historiques restent fournies : le modèle déjà en
        #  base les utilise encore tant que la migration 0127 n'a pas tourné, et
        #  une variable absente rend une chaîne vide sans rien signaler.
        "civilite": "Monsieur" if principal.genre == GenreCivilite.mr else "Madame",
        "nom_gestionnaire": f"{principal.prenom} {principal.nom}".strip(),
        "residence": {"nom": cfg.get("site_nom", "5Hostachy")},
        "anciennete": anciennete,
        "tickets": [_contexte_ticket(session, t) for t in tickets_relance],
    }

    to_recipients = [(principal.user_id, principal.email)]
    #  Le CS passe en copie, sans le syndic qui est déjà destinataire principal.
    cc_recipients = destinataires_syndic_cs(
        session, syndic=False, cs=True, deja_vus={principal.email.lower()}
    )

    session.commit()

    #  Pas de session= : la tâche de fond crée sa propre SessionLocal (celle de
    #  l'endpoint est fermée une fois la réponse envoyée).
    background_tasks.add_task(
        send_email_group,
        code="relance_syndic",
        to_recipients=to_recipients,
        context=ctx,
        cc_recipients=cc_recipients or None,
    )

    return {"sent": len(tickets_relance), "relance_to": principal.email}
