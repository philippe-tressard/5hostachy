"""La réponse à une relance GROUPÉE — sortie de `courriel_boite` le 28/09/2026.

Elle y vivait à côté de la relève, qui dépassait 500 lignes en recevant le
journal des relèves (#1447). La coupure suit une notion, pas un compte : une
relance porte N dossiers et ne se ventile dans aucun fil — une décision à part,
avec sa table (`ReponseRelance`) et son destinataire (le conseil syndical).
La relève, elle, ne fait que l'appeler.
"""

from __future__ import annotations

import json

from sqlmodel import Session, select

from app.models.core import Ticket
from app.models.courriel import RelanceCourriel, ReponseRelance
from app.utils import horloge
from app.utils.cloche import sonner_systeme
from app.utils.courriel_decodage import _sans_citation
from app.utils.courriel_ingestion import RELANCE


def relance_de(session: Session, verdict) -> RelanceCourriel | None:
    """La relance groupée visée, s'il ne s'agit pas d'un ticket (#703)."""
    if not verdict.jeton:
        return None
    return session.exec(
        select(RelanceCourriel).where(RelanceCourriel.jeton == verdict.jeton)
    ).first()


def reponse_a_une_relance(session: Session, relance: RelanceCourriel, verdict, corps: str) -> str:
    """Ce qu'on fait d'une réponse à un envoi GROUPÉ.

    🔴 ELLE N'EST PAS VENTILÉE DANS LES FILS, et c'est la décision de fond.

    Le syndic écrit « pour le TK-123 on intervient jeudi, le TK-456 est clos ».
    Recopier ce texte dans quatre fils le rendrait faux dans trois d'entre eux.
    Aucune machine ne peut décider quelle phrase concerne quel dossier ; le faire
    serait faire semblant de savoir.

    Le conseil syndical la reçoit donc en entier, avec la liste des dossiers
    concernés, et la reporte là où c'est juste. Il est déjà en copie de la
    relance : c'est le bon récepteur, pas un pis-aller.
    """
    from app.utils.destinataires import membres_cs_ou_admin

    ids = []
    try:
        ids = [int(i) for i in json.loads(relance.tickets_json or "[]")]
    except (ValueError, TypeError):
        pass
    numeros = (
        [t.numero for t in session.exec(select(Ticket).where(Ticket.id.in_(ids))).all()]
        if ids
        else []
    )
    liste = ", ".join(f"#{n}" for n in numeros) or "aucun ticket retrouvé"

    texte = _sans_citation(corps)

    #  🔴 CONSERVÉE AVANT D'ÊTRE NOTIFIÉE (04/09/2026). La notification prévient ;
    #  elle ne conserve pas. Sans cette ligne, la réponse n'existait que dans un
    #  champ `corps` qu'on ne relit jamais — le défaut que ce chantier corrige,
    #  déplacé de la boîte aux lettres vers une table de notifications.
    session.add(
        ReponseRelance(
            relance_id=relance.id,
            expediteur=verdict.expediteur,
            contenu=texte,
            recue_le=horloge.maintenant(),
        )
    )

    for membre in membres_cs_ou_admin(session):
        sonner_systeme(
            session,
            "tache_du_conseil",
            destinataire_id=membre.id,
            type="ticket_update",
            titre="Réponse du syndic à la relance groupée",
            corps=(
                f"« {verdict.expediteur} » a répondu à la relance portant sur "
                f"{liste}.\n\n{texte or '(message sans texte lisible)'}\n\n"
                "Cette réponse n'a été ajoutée à aucun fil : elle parle de "
                "plusieurs dossiers à la fois. À reporter là où elle s'applique."
            ),
            #  Vers l'écran qui la CONSERVE, pas vers la liste des tickets : la
            #  notification se perd, la page se rouvre.
            lien="/espace-cs/reporting",
        )
    #  RELANCE et non REFUSE : la réponse est reçue, conservée et notifiée. Rien
    #  n'a été refusé — seulement pas ventilé, ce qui est la décision voulue.
    return RELANCE
