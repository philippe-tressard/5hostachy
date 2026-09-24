"""Rattacher automatiquement un LOCATAIRE à son bailleur, par le nom (#1136).

## Pourquoi (arbitré le 24/09/2026)

Signalé à l'écran le 22/09 : « un nouvel utilisateur (ici un locataire) n'a pas
été automatiquement rapproché avec son bailleur ». Le locataire déclare à
l'inscription le nom de son propriétaire (`nom_proprietaire`) ; rien ne s'en
servait, sauf la liste « locataires suggérés » du bailleur. Arbitré :
« rattacher automatiquement un locataire à son bailleur à partir du seul nom ».

## 🔴 Le risque accepté, et ce qui le borne

Un rattachement ouvre au locataire les badges du lot (porteurs dérivés,
`utils/porteurs_acces`). Deux foyers homonymes sont indiscernables par le nom —
c'est le risque que l'arbitrage accepte. Ce module le borne sans le refuser :

- **un seul** bailleur doit porter ce nom — deux homonymes, et rien n'est fait ;
- ce bailleur n'a qu'**un** bail sans locataire, ou à défaut qu'**un** logement ;
- le locataire n'est lié à aucun lot ni aucun bail — on ne corrige pas un lien
  posé à la main ;
- chaque rattachement est **journalisé** (`journal_securite`) et **signalé** au
  gestionnaire du site, qui défait d'un geste ce qui serait faux.

Réutilise la comparaison des noms d'`auto_match_service` (`_user_keys`,
`_matches_user`), la même que pour les imports du syndic : deux règles pour
« ce nom est-il le sien ? » divergeraient au premier cas limite.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.copropriete import TypeLot
from app.models.core import (
    LocationBail,
    Lot,
    StatutBail,
    StatutUtilisateur,
    TypeLien,
    UserLot,
    Utilisateur,
)
from app.utils.auto_match_service import _matches_user, _user_keys
from app.utils.cloche import sonner_systeme
from app.utils.destinataires import site_manager_user_id
from app.utils.journal_securite import journaliser_securite
from app.utils.noms import nom_affiche
from app.utils.valeurs import valeur

#: Qui peut louer un lot : un copropriétaire, résident ou non.
STATUTS_BAILLEUR = frozenset(
    {
        StatutUtilisateur.copropriétaire_bailleur.value,
        StatutUtilisateur.copropriétaire_résident.value,
    }
)


def _deja_rattache(user: Utilisateur, session: Session) -> bool:
    lien = session.exec(
        select(UserLot).where(UserLot.user_id == user.id, UserLot.actif == True)  # noqa: E712
    ).first()
    bail = session.exec(select(LocationBail).where(LocationBail.locataire_id == user.id)).first()
    return lien is not None or bail is not None


def bailleur_designe(user: Utilisateur, session: Session) -> Utilisateur | None:
    """Le SEUL bailleur actif dont le nom répond à `nom_proprietaire`, ou `None`."""
    if not user.nom_proprietaire:
        return None
    candidats = [
        b
        for b in session.exec(select(Utilisateur).where(Utilisateur.actif == True)).all()  # noqa: E712
        if b.id != user.id
        and valeur(b.statut) in STATUTS_BAILLEUR
        and _matches_user(user.nom_proprietaire, _user_keys(b.nom or "", b.prenom or ""))
    ]
    return candidats[0] if len(candidats) == 1 else None


def rattacher_au_bailleur(user: Utilisateur, session: Session) -> int:
    """Rattache le locataire au bail, sinon au logement, de son bailleur ; rend 0 ou 1.

    Ne committe pas — l'appelant (`auto_match_pour_utilisateur`) le fait.
    """
    if valeur(user.statut) != StatutUtilisateur.locataire.value or _deja_rattache(user, session):
        return 0
    bailleur = bailleur_designe(user, session)
    if bailleur is None:
        return 0

    baux = session.exec(
        select(LocationBail).where(
            LocationBail.bailleur_id == bailleur.id,
            LocationBail.locataire_id.is_(None),  # type: ignore[union-attr]
            LocationBail.statut != StatutBail.termine,
        )
    ).all()
    if len(baux) == 1:
        baux[0].locataire_id = user.id
        session.add(baux[0])
        quoi = f"bail {baux[0].id}"
    else:
        logements = [
            ul.lot_id
            for ul in session.exec(
                select(UserLot).where(
                    UserLot.user_id == bailleur.id,
                    UserLot.actif == True,  # noqa: E712
                )
            ).all()
            if (lot := session.get(Lot, ul.lot_id)) is not None
            and valeur(lot.type) == TypeLot.appartement.value
        ]
        if len(set(logements)) != 1:
            return 0
        session.add(
            UserLot(user_id=user.id, lot_id=logements[0], type_lien=TypeLien.locataire, actif=True)
        )
        quoi = f"lot {logements[0]}"

    #  Des IDENTIFIANTS, jamais un nom : le journal ne porte aucune donnée
    #  personnelle (`test_journal_securite.py`).
    journaliser_securite(
        "rattachement_auto", cible_id=user.id, detail=f"bailleur {bailleur.id} · {quoi}"
    )
    gestionnaire = site_manager_user_id(session)
    if gestionnaire is not None:
        sonner_systeme(
            session,
            "rattachement",
            destinataire_id=gestionnaire,
            type="system",
            titre="Locataire rattaché automatiquement",
            corps=f"{nom_affiche(user.prenom, user.nom)} a été rattaché au {quoi} de "
            f"{nom_affiche(bailleur.prenom, bailleur.nom)}, "
            "d'après le nom de propriétaire déclaré. À défaire s'il s'agit d'un homonyme.",
            lien="/admin?onglet=comptes",
        )
    return 1


__all__ = ["bailleur_designe", "rattacher_au_bailleur"]
