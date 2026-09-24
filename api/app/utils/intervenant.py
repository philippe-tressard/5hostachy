"""L'intervenant d'une affaire, son équipement et la récurrence d'un Entretien — une écriture, deux chemins.

## Pourquoi (#1092, lot 5, arbitré le 23/09/2026)

Les événements du calendrier deviennent des affaires. Seize portent un
prestataire, et une maintenance récurrente sa fréquence. La section 6 du cadre,
« Intervenant », était déclarée « pas encore construite » (#1097) : ce lot la
construit, et la récurrence la rejoint pour la seule catégorie Entretien.

## La règle, ici et nulle part ailleurs

- **Le conseil seul** désigne l'intervenant et règle la récurrence. Un résident
  qui envoie ces champs est **ignoré**, comme pour les autres options réservées
  (`appliquer_options`) : sa correction de texte doit passer.
- Le prestataire désigné doit **exister** (`ou_404`) : un identifiant inventé
  afficherait un intervenant fantôme sur la fiche et dans le carnet.
- L'intervenant n'a de sens que pour une catégorie du **bâti**
  (`carnet_entretien.CATEGORIES_BATI`), la récurrence que pour un
  **Entretien** : hors de là, ils sont effacés — sinon une affaire
  recatégorisée garderait en base ce qu'aucun écran ne montre plus (« sans
  données », arbitré le 23/09/2026).

## L'équipement (#1097, 24/09/2026)

« Sur quoi » : la **valeur** de `TypeEquipement`, posée par le conseil et jamais
demandée au résident — il voit une flaque, il ne sait pas si c'est la plomberie,
la toiture ou la VMC. Mêmes règles que l'intervenant (conseil seul, bâti seul,
effacé ailleurs), plus une liste blanche : `assurance` et `syndic` classent des
**contrats**, pas un équipement sur lequel on intervient.

C'est lui qui RANGE une affaire résolue au carnet d'entretien
(`carnet_entretien._entrees_incidents`) ; sans lui, elle y figure sous « Sans
équipement rattaché » — et non plus exclue, arbitré à l'écran le 24/09/2026.

Création (`crud.py`) et correction (`mise_a_jour.py`) l'appellent : deux
écritures de ces trois règles divergeraient au premier cas limite.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlmodel import Session

from app.models.prestataires import Prestataire, TypeEquipement
from app.models.tickets import CategorieTicket
from app.utils.carnet_entretien import CATEGORIES_BATI
from app.utils.recuperer import ou_404
from app.utils.valeurs import valeur

#: Les unités de récurrence — celles de `ContratEntretien`, qui fixe le rythme
#: d'un prestataire. Même table côté écran : `FREQUENCES` de `$lib/prestataires`.
#: « mois » vaut « mensuelle » : sans nombre saisi, il vaut 1.
FREQUENCES: tuple[str, ...] = ("semaines", "mois", "fois_par_an", "ans")

CHAMPS: tuple[str, ...] = ("prestataire_id", "frequence_type", "frequence_valeur", "equipement")

#: Ce qu'une affaire peut désigner comme équipement : `TypeEquipement`, moins
#: ce qui classe un CONTRAT sans être un équipement. Même liste côté écran :
#: `EQUIPEMENTS_AFFAIRE` de `$lib/prestataires` (`test_types_equipement.py`).
HORS_EQUIPEMENT: frozenset[str] = frozenset(
    {TypeEquipement.assurance.value, TypeEquipement.syndic.value}
)
EQUIPEMENTS_AFFAIRE: tuple[str, ...] = tuple(
    e.value for e in TypeEquipement if e.value not in HORS_EQUIPEMENT
)


def _envoye(body: Any, champ: str) -> bool:
    """Le corps dit-il quelque chose de ce champ ? (présence, pas non-nullité)"""
    return champ in getattr(body, "model_fields_set", set())


def appliquer_intervenant(ticket: Any, body: Any, session: Session, *, est_cs: bool) -> list[str]:
    """Pose l'intervenant et la récurrence ; rend les lignes du journal de correction."""
    changes: list[str] = []
    if valeur(ticket.categorie) not in {valeur(c) for c in CATEGORIES_BATI}:
        if ticket.prestataire_id is not None:
            changes.append("Intervenant effacé")
        if ticket.equipement is not None:
            changes.append("Équipement effacé")
        ticket.prestataire_id = None
        ticket.equipement = None
    else:
        if (
            est_cs
            and _envoye(body, "prestataire_id")
            and body.prestataire_id != ticket.prestataire_id
        ):
            if body.prestataire_id is not None:
                ou_404(session, Prestataire, body.prestataire_id, "Prestataire")
            ticket.prestataire_id = body.prestataire_id
            changes.append("Intervenant")
        if (
            est_cs
            and _envoye(body, "equipement")
            and (body.equipement or None) != ticket.equipement
        ):
            if body.equipement and body.equipement not in EQUIPEMENTS_AFFAIRE:
                raise HTTPException(422, "Équipement inconnu")
            ticket.equipement = body.equipement or None
            changes.append("Équipement")

    if valeur(ticket.categorie) != CategorieTicket.entretien.value:
        #  Hors Entretien : rien ne se garde, quel que soit l'auteur du geste.
        if ticket.frequence_type or ticket.frequence_valeur:
            changes.append("Récurrence effacée")
        ticket.frequence_type = None
        ticket.frequence_valeur = None
        return changes

    if est_cs and (_envoye(body, "frequence_type") or _envoye(body, "frequence_valeur")):
        type_ = body.frequence_type or None
        nombre = 1 if type_ == "mois" and body.frequence_valeur is None else body.frequence_valeur
        if type_ is None or nombre is None:
            type_, nombre = None, None
        elif type_ not in FREQUENCES or nombre < 1:
            raise HTTPException(422, "Récurrence invalide : une unité connue et un nombre positif")
        if (type_, nombre) != (ticket.frequence_type, ticket.frequence_valeur):
            ticket.frequence_type, ticket.frequence_valeur = type_, nombre
            changes.append("Récurrence")
    return changes


__all__ = ["CHAMPS", "EQUIPEMENTS_AFFAIRE", "FREQUENCES", "appliquer_intervenant"]
