"""QUI porte un badge — déduit de son lot, écrit une fois (#1194, 23/09/2026).

## La règle arbitrée

Un badge (Vigik, télécommande) **appartient au lot**. Ses porteurs ne sont pas
enregistrés, ils se **lisent** :

| Le badge | Ses porteurs |
|---|---|
| posé sur un lot | les copropriétaires du lot — le conjoint **exactement comme l'autre** |
| … et remis au locataire | les mêmes, **plus** le locataire du lot — lien `user_lot` ou bail en cours (arbitrage 2 : les copropriétaires le voient toujours) |
| sans lot connu (donnée ancienne) | celui qui le détient, et ceux qui partagent un lot avec lui |

S'y ajoute toujours celui qui le détient en main (`user_id`), quand il est connu.

## 🔴 Ce que la règle remplace

Les tables `user_vigik` / `user_telecommande` ÉCRIVAIENT cette réponse, par sept
chemins — l'import, la résolution, l'activation d'un compte, et un chemin
spécial pour le conjoint inscrit après coup (`_propagate_acces_pour_utilisateur`),
qui ne se déclenchait que dans certains cas. Une réponse écrite se périme : un
conjoint rattaché au lot par l'administration, et non par l'activation de son
compte, ne voyait pas les badges du ménage. Une réponse LUE ne se périme pas.

Et « a un badge » avait **quatre** définitions — dont une qui comptait les badges
perdus. Il n'en reste qu'une : `ids_detenteurs`.

⚠️ Ce module ne connaît ni route ni écran. Il dit qui porte, pas qui peut
regarder le parc : le conseil syndical voit tout, par ses propres routes.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from sqlmodel import Session, select

from app.models.core import StatutAcces, UserLot
from app.utils.resolution_lots import TYPES_COPROPRIETAIRES
from app.utils.valeurs import valeur


class _Liens:
    """Les liens actifs lot ⇄ personne, lus UNE fois pour tout un calcul.

    Le parc compte une centaine d'objets : les relire lien par lien ferait une
    requête par badge, et le tableau de l'administration en affiche des
    dizaines à la fois.
    """

    def __init__(self, session: Session):
        self.copros_du_lot: dict[int, set[int]] = defaultdict(set)
        self.locataires_du_lot: dict[int, set[int]] = defaultdict(set)
        self.lots_copro_de: dict[int, set[int]] = defaultdict(set)
        for ul in session.exec(select(UserLot).where(UserLot.actif == True)).all():  # noqa: E712
            if valeur(ul.type_lien) in TYPES_COPROPRIETAIRES:
                self.copros_du_lot[ul.lot_id].add(ul.user_id)
                self.lots_copro_de[ul.user_id].add(ul.lot_id)
            elif valeur(ul.type_lien) == "locataire":
                self.locataires_du_lot[ul.lot_id].add(ul.user_id)
        #  Le locataire d'un BAIL en cours l'est aussi (V3 de #1194) : c'est par
        #  le bail que le bailleur remet un badge, et le locataire n'a pas
        #  toujours de lien `user_lot` — « chez le locataire » n'a qu'un sens.
        from app.models.core import LocationBail, StatutBail

        for bail in session.exec(select(LocationBail).where(
            LocationBail.statut != StatutBail.termine, LocationBail.locataire_id != None,  # noqa: E711
        )).all():
            self.locataires_du_lot[bail.lot_id].add(bail.locataire_id)

    def partages(self, user_id: int) -> set[int]:
        """Ceux qui partagent au moins un lot, comme copropriétaires, avec lui."""
        ensemble: set[int] = set()
        for lot_id in self.lots_copro_de.get(user_id, ()):
            ensemble |= self.copros_du_lot[lot_id]
        return ensemble

    def porteurs(self, objet) -> set[int]:
        ids: set[int] = {objet.user_id} if objet.user_id else set()
        if objet.lot_id:
            ids |= self.copros_du_lot.get(objet.lot_id, set())
            if objet.chez_locataire:
                ids |= self.locataires_du_lot.get(objet.lot_id, set())
        elif objet.user_id:
            ids |= self.partages(objet.user_id)
        return ids


def copros_par_lot(session: Session) -> dict[int, set[int]]:
    """`{lot: ses copropriétaires}` — ceux qui porteront un badge posé sur ce lot."""
    return _Liens(session).copros_du_lot


def porteurs_par_acces(session: Session, objets: Iterable) -> dict[int, set[int]]:
    """`{id de l'objet: identifiants de ses porteurs}` — la règle, en lot."""
    liens = _Liens(session)
    return {o.id: liens.porteurs(o) for o in objets}


def porteurs(session: Session, objet) -> set[int]:
    """Les porteurs d'UN badge."""
    return porteurs_par_acces(session, [objet])[objet.id]


def acces_de(session: Session, type_acces, user_id: int) -> list:
    """Les badges de ce type dont cette personne est porteuse, perdus compris.

    Un badge perdu reste dans la liste de son porteur : c'est là qu'il l'a
    signalé, et c'est là qu'il le retrouve.
    """
    objets = session.exec(select(type_acces.modele)).all()
    par_objet = porteurs_par_acces(session, objets)
    return [o for o in objets if user_id in par_objet[o.id]]


def noms_des_porteurs(session: Session, objets: Iterable) -> dict[int, str]:
    """`{id de l'objet: ce que la colonne « Porteurs » affiche}`.

    Les comptes porteurs d'abord. Sans compte, le copropriétaire tel que le
    FICHIER des lots le nomme, « (sans compte) » — c'était un tiret, sur la
    plupart des badges importés (signalé le 23/09/2026). Sans lot ni
    porteur : « En stock ».
    """
    from app.models.core import LotImport, Utilisateur
    from app.utils.noms import nom_affiche

    objets = list(objets)
    par_objet = porteurs_par_acces(session, objets)
    fichier: dict[int, str] = {}
    for li in session.exec(select(LotImport).where(LotImport.lot_id != None)).all():  # noqa: E711
        if li.nom_coproprietaire:
            fichier.setdefault(li.lot_id, li.nom_coproprietaire)
    noms: dict[int, str] = {}
    for o in objets:
        comptes = [session.get(Utilisateur, uid) for uid in sorted(par_objet[o.id])]
        affiches = [nom_affiche(u.prenom, u.nom) for u in comptes if u]
        if affiches:
            noms[o.id] = ", ".join(affiches)
        elif o.lot_id and o.lot_id in fichier:
            noms[o.id] = f"{fichier[o.lot_id]} (sans compte)"
        else:
            noms[o.id] = "—" if o.lot_id else "En stock"
    return noms


def lot_unique_de_nature(session: Session, type_acces, user_id: int) -> int | None:
    """Le lot de cette personne où va ce badge, s'il n'y en a qu'UN de sa nature.

    Un appartement pour un Vigik, un parking pour une télécommande. Deux
    parkings, et on ne choisit pas à sa place : le lot reste à préciser.
    """
    from app.models.copropriete import Lot

    lots = session.exec(
        select(Lot.id).join(UserLot, UserLot.lot_id == Lot.id).where(
            UserLot.user_id == user_id,
            UserLot.actif == True,  # noqa: E712
            Lot.type.in_(list(type_acces.types_lot)),  # type: ignore[attr-defined]
        )
    ).all()
    return lots[0] if len(set(lots)) == 1 else None


def ids_detenteurs(session: Session, type_acces) -> set[int]:
    """« A un badge » — la seule définition : porteur d'au moins un badge NON perdu."""
    objets = session.exec(
        select(type_acces.modele).where(type_acces.modele.statut != StatutAcces.perdu)
    ).all()
    ids: set[int] = set()
    for porteurs_objet in porteurs_par_acces(session, objets).values():
        ids |= porteurs_objet
    return ids


__all__ = ["acces_de", "copros_par_lot", "noms_des_porteurs", "ids_detenteurs", "lot_unique_de_nature", "porteurs", "porteurs_par_acces"]
