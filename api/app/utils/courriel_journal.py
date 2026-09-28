"""Le journal des messages relevés — ce que la relève a décidé, et pourquoi (#1447).

Une ligne par message traité (`courriel_boite.traiter`), écrite dans la même
transaction que le verdict. Elle se lit dans Admin › Paramétrage › SMTP, sous la
réception des réponses, et se purge chaque dimanche (`maintenance.purger`).

🔴 Ce qu'elle ne porte pas : le corps du message. Le journal dit ce qu'on a
DÉCIDÉ ; le texte vit dans le fil de l'affaire ou dans la boîte de réception.
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from app.models.courriel import CourrielReleve

#: Combien de jours une ligne est gardée. Assez pour qu'un « je vous ai
#: répondu il y a trois semaines » se vérifie, pas davantage : l'adresse de
#: l'expéditeur est une donnée personnelle. La politique de confidentialité
#: le dit (`seed/contenus_legaux.CONSERVATION_RELEVES`).
CONSERVATION_RELEVES_JOURS = 90

#: Un objet s'arrête là : un sujet sans fin n'apprend rien de plus.
_OBJET_MAX = 300


def journaliser_releve(
    session: Session,
    entetes: dict,
    envoye_le: datetime | None,
    decision: str,
    motif: str,
    ticket=None,
) -> None:
    """Ajoute la ligne à la session — c'est l'appelant qui valide, avec le verdict."""
    lire = {k.lower(): v for k, v in entetes.items()}
    session.add(
        CourrielReleve(
            envoye_le=envoye_le,
            expediteur=(lire.get("from") or "")[:_OBJET_MAX],
            objet=(lire.get("subject") or "")[:_OBJET_MAX],
            decision=decision,
            motif=motif or "motif non renseigné",
            ticket_id=ticket.id if ticket is not None else None,
            affaire=ticket.numero if ticket is not None else None,
        )
    )


def derniers_releves(session: Session, limite: int = 50) -> list[CourrielReleve]:
    """Les lignes les plus récentes d'abord."""
    return session.exec(
        select(CourrielReleve)
        .order_by(CourrielReleve.releve_le.desc(), CourrielReleve.id.desc())
        .limit(limite)
    ).all()
