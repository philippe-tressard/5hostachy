"""Le suivi d'une actualité — optionnel, à trois états, posé par le conseil seul.

## La demande (10/10/2026)

> « Une affaire de type actualité possède un suivi (optionnel) à trois états
>   seulement, activable uniquement par le CS : Ouvert (par défaut), Résolu ou
>   Annulé. »

Arbitré le même jour, sur trois questions :

1. **Un repère, pas un circuit.** L'actualité suivie reste hors du kanban, des
   relances syndic, des compteurs « à traiter » et de la synthèse de clôture.
   D'où une colonne À PART (`Ticket.suivi_actualite`) : `statut` reste `publie`,
   et l'actualité sort de ces circuits PAR CONSTRUCTION, comme avant — aucun
   consommateur de `STATUTS_TICKET_ACTIFS` n'a une ligne à changer.
2. **L'archivage d'une affaire** : « Annulé » archive aussitôt, « Résolu » trente
   jours après ; « Ouvert » garde la règle de l'actualité (`utils/archivage`,
   règle `actualite_suivie`).
3. **Une case, puis la Suite.** La case « Activer le suivi » se coche à la
   création ou en correction (option `suivre_actualite`, réservée au conseil
   comme `suivi_kanban`) ; l'état se change ensuite par une Suite, qui en garde
   la trace au fil — une transition `etat`, comme celle d'une affaire.

⚠️ Ne pas confondre avec 🎯 « Transformer en affaire », qui en fait une AFFAIRE
suivie (changement de catégorie, `nature_affaire`) : ici, elle reste une
actualité, et le suivi n'est qu'un repère.

## Ce qui ne s'écrit qu'ici

| Question | Fonction |
|---|---|
| quels états ? | `ETATS_SUIVI_ACTUALITE` |
| l'état que la Suite fait avancer — celui du suivi, ou le statut | `etat_de_la_suite` |
| cocher ou décocher la case | `poser_suivi` |
| une affaire suivie n'a pas de suivi d'actualité | `normaliser_suivi` |
| l'état choisi au formulaire, à la création ou en correction | `poser_etat_saisi` |
| une Suite peut-elle porter cet état ? | `refuser_etat` |
| l'état change | `appliquer_etat` |
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import HTTPException

from app.models.tickets import STATUTS_TICKET_CLOS, STATUTS_TICKET_SANS_CYCLE, StatutTicket
from app.utils import horloge
from app.utils.nature_affaire import est_actualite
from app.utils.valeurs import valeur

#: Les trois états, et il n'y en a pas d'autre — des valeurs de `StatutTicket`,
#: jamais recopiées : l'écran les nomme et les colore par la même table.
ETATS_SUIVI_ACTUALITE: tuple[str, ...] = (
    StatutTicket.ouvert.value,
    StatutTicket.résolu.value,
    StatutTicket.annulé.value,
)

#: L'état d'un suivi qu'on active.
ETAT_SUIVI_DEFAUT = StatutTicket.ouvert.value


def est_suivie(ticket: Any) -> bool:
    """Cette actualité porte-t-elle un suivi ?"""
    return est_actualite(ticket) and bool(getattr(ticket, "suivi_actualite", None))


def etat_de_la_suite(ticket: Any) -> str:
    """L'état que le fil fait avancer : le suivi d'une actualité, le statut sinon.

    C'est lui que lisent `statuts_avant` et `suivi_corrige` (`utils/suivi_fil`) :
    les règles du fil sont les mêmes, seul change l'état qu'elles gouvernent.
    """
    if est_actualite(ticket):
        return valeur(getattr(ticket, "suivi_actualite", None)) or valeur(ticket.statut)
    return valeur(ticket.statut)


def _ouvrir(ticket: Any, etat: Optional[str]) -> None:
    ticket.suivi_actualite = etat
    ticket.ferme_le = None


def poser_suivi(ticket: Any, actif: bool) -> bool:
    """Coche ou décoche la case. Rend `True` si quelque chose a changé.

    Cocher une case déjà cochée ne rouvre rien : l'état en cours est gardé.
    Décocher efface l'état — et la date de clôture qu'il avait posée.
    """
    if actif and not ticket.suivi_actualite:
        _ouvrir(ticket, ETAT_SUIVI_DEFAUT)
        return True
    if not actif and ticket.suivi_actualite:
        _ouvrir(ticket, None)
        return True
    return False


def poser_etat_saisi(ticket: Any, etat: Optional[str], *, est_cs: bool) -> None:
    """L'état choisi au FORMULAIRE — à la création comme en correction (10/10/2026).

    Demandé à l'écran : *« la résolution est parfois rapide et l'ouverture se fait
    directement en l'état résolu »*. `None` ne dit rien ; un autre que le conseil
    est ignoré, comme la case qu'il ne voit pas (`OPTIONS_RESERVEES_AU_CS`) ; sans
    suivi activé, il n'y a pas d'état à poser. Un état hors des trois est refusé.
    """
    if etat is None or not est_cs or not est_suivie(ticket):
        return
    if etat not in ETATS_SUIVI_ACTUALITE:
        raise HTTPException(422, "Le suivi d'une actualité est Ouvert, Résolu ou Annulé")
    if etat != ticket.suivi_actualite:
        appliquer_etat(ticket, etat, horloge.maintenant())


def normaliser_suivi(ticket: Any) -> None:
    """Une affaire suivie n'a pas de suivi d'actualité — effacé si elle en venait."""
    if not est_actualite(ticket) and ticket.suivi_actualite:
        _ouvrir(ticket, None)


def refuser_etat(ticket: Any, etat: Any, *, est_cs: bool) -> None:
    """Une Suite peut-elle porter cet état ? Lève sinon.

    Une affaire suivie : tout état de son cycle, sauf `publie`. Une actualité :
    l'un des trois états de son suivi, s'il est activé, et par le conseil seul.
    """
    etat = valeur(etat)
    if not est_actualite(ticket):
        if etat in STATUTS_TICKET_SANS_CYCLE:
            raise HTTPException(422, "Une actualité n'a pas d'état de suivi")
        return
    if not ticket.suivi_actualite:
        raise HTTPException(
            422, "Cette actualité n'est pas suivie : le conseil syndical active son suivi"
        )
    if not est_cs:
        raise HTTPException(403, "Seul le conseil syndical fait avancer le suivi d'une actualité")
    if etat not in ETATS_SUIVI_ACTUALITE:
        raise HTTPException(422, "Le suivi d'une actualité est Ouvert, Résolu ou Annulé")


def appliquer_etat(ticket: Any, etat: str, ferme_le: datetime) -> None:
    """L'actualité prend cet état de suivi — daté s'il la clôt, comme une affaire."""
    ticket.suivi_actualite = etat
    ticket.ferme_le = ferme_le if etat in STATUTS_TICKET_CLOS else None
    ticket.mis_a_jour_le = horloge.maintenant()


__all__ = [
    "ETATS_SUIVI_ACTUALITE",
    "ETAT_SUIVI_DEFAUT",
    "appliquer_etat",
    "est_suivie",
    "etat_de_la_suite",
    "normaliser_suivi",
    "poser_etat_saisi",
    "poser_suivi",
    "refuser_etat",
]
