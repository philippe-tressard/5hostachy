"""Le document DÉSIGNÉ par un contrat — et la garde qui manquait (#989).

## L'incident (17/09/2026, signalé à l'écran)

La synthèse d'un contrat d'ascenseur annonçait, dans son encart de provenance,
avoir lu deux fichiers : celui du contrat, et « Entretien toitures Bat 2 ». La
carte du contrat n'en montrait qu'un, et c'était l'écran qui avait raison.

`ContratEntretien.document_id` désigne « le document du contrat ». Rien ne
vérifiait qu'il **appartient** à ce contrat : la synthèse insérait le document
désigné en tête de sa matière, quel qu'il soit. Un pointeur hérité vers le
document d'un autre contrat suffisait donc à faire lire ce contrat-là par le
modèle, et à le faire nommer dans l'encart.

🔴 Deux conséquences, et la seconde est la grave : l'encart devenait faux, et
surtout **un document étranger au contrat partait au service d'IA** — ce que
l'en-tête de `synthese_contrat` interdit en toutes lettres.

## La règle, écrite une fois

Un document n'est le document d'un contrat que s'il **porte le lien** vers ce
contrat (`Document.contrat_id`). C'est déjà la règle que l'écran applique — il
liste par `contrat_id`, sans autre filtre pour le conseil syndical — et c'est
donc celle des deux vues, non deux règles à tenir d'accord.

⚠️ Un pointeur incohérent n'est **pas nettoyé** ici : on ne détruit pas la seule
copie d'une donnée pour faire taire un symptôme (`standards/06` §5). Il cesse
simplement d'être suivi, des deux côtés — la synthèse et la fiche copropriété.

## Ce que ce module ne fait pas

Il ne dit pas quels documents un contrat porte : c'est une requête, et elle vit
chez son appelant (`synthese_contrat.documents_du_contrat`). Il répond à une
seule question, celle qui n'était posée nulle part.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlmodel import Session

from app.models.documents import Document
from app.models.prestataires import ContratEntretien

logger = logging.getLogger("hostachy.contrat")


def document_designe(session: Session, contrat: ContratEntretien) -> Optional[Document]:
    """Le document que ce contrat désigne, **s'il est bien le sien**.

    Rend `None` quand aucun document n'est désigné, quand le pointeur ne mène à
    rien, ou quand le document désigné appartient à un autre contrat — ou à
    aucun, un document de la bibliothèque n'étant pas un document de contrat.

    Le dernier cas est journalisé : c'est une incohérence de DONNÉE, et la taire
    reviendrait à masquer ce que l'incident du 17/09/2026 a rendu visible.
    """
    if not contrat.document_id:
        return None
    designe = session.get(Document, contrat.document_id)
    if designe is None:
        return None
    if designe.contrat_id != contrat.id:
        logger.warning(
            "Contrat %s : document désigné %s rattaché au contrat %s — ignoré",
            contrat.id,
            designe.id,
            designe.contrat_id,
        )
        return None
    return designe


def id_document_designe(session: Session, contrat: ContratEntretien) -> Optional[int]:
    """L'identifiant du document désigné, pour les écrans qui n'en font qu'un lien.

    La fiche copropriété propose « Télécharger le document du contrat » à partir
    de cet identifiant : sans la garde, elle offrait le fichier d'un autre
    contrat, avec la même cause et sans que rien ne le dise.
    """
    designe = document_designe(session, contrat)
    return designe.id if designe else None


__all__ = ["document_designe", "id_document_designe"]
