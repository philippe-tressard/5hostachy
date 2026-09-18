"""À QUI un accès appartient, au-delà de celui qui le porte — écrit une fois.

## Pourquoi ce module (18/09/2026, #779)

Un badge posé sur un lot n'appartient pas qu'à la personne qui l'a en main : il
appartient aussi aux **copropriétaires de ce lot**, et à ceux qui partagent un
lot avec son porteur. C'est ce qui permet au conjoint de voir le badge du
ménage, et au bailleur de retrouver celui qu'il a confié.

Cette règle vivait dans `utils/auto_match_service.py`, module de service
d'appariement — c'est-à-dire chez l'un de ses appelants. Le second, le socle des
imports (`routers/acces/socle_imports.py`), y accédait par un `creer_liaisons`
passé en paramètre à travers un objet descripteur : un détour qui n'existait que
parce que la règle n'avait pas de maison.

⚠️ C'est le même motif que `utils/acces_possession` le même jour : une règle
rangée chez un appelant oblige le suivant à la recevoir par un canal détourné,
ou à la recopier. Ce fichier n'appartient à personne, et c'est ce qui le rend
prenable.

## Ce qu'il ne fait pas

Il ne décide pas de la VISIBILITÉ d'un accès à l'écran — cela reste
`utils/visibility`. Il décide de l'attribution enregistrée en base, celle qui
survit à un changement de périmètre.
"""
from __future__ import annotations

from sqlmodel import Session, select

#: Les types de lien qui font d'un utilisateur un « copropriétaire » du lot au
#: sens de cette règle. Le locataire n'y est pas : il détient l'accès qu'on lui
#: a remis, il n'hérite pas de ceux des autres.
TYPES_COPROPRIETAIRES = {"propriétaire", "bailleur", "mandataire"}


def _lien(user_lot) -> str:
    """Le type de lien, qu'il soit une énumération ou déjà une chaîne."""
    valeur = user_lot.type_lien
    return valeur.value if hasattr(valeur, "value") else str(valeur)


def coproprietaires_du_lot(lot_id: int | None, session: Session) -> set[int]:
    """Les identifiants des copropriétaires de CE lot."""
    if not lot_id:
        return set()
    from app.models.core import UserLot

    liens = session.exec(
        select(UserLot).where(UserLot.lot_id == lot_id, UserLot.actif == True)  # noqa: E712
    ).all()
    return {ul.user_id for ul in liens if _lien(ul) in TYPES_COPROPRIETAIRES}


def coproprietaires_partages(user_id: int, session: Session) -> set[int]:
    """Tous ceux qui partagent au moins un lot avec cet utilisateur."""
    from app.models.core import UserLot

    miens = session.exec(
        select(UserLot).where(UserLot.user_id == user_id, UserLot.actif == True)  # noqa: E712
    ).all()
    lot_ids = {ul.lot_id for ul in miens if _lien(ul) in TYPES_COPROPRIETAIRES}
    if not lot_ids:
        return set()

    ensemble = session.exec(
        select(UserLot).where(
            UserLot.lot_id.in_(list(lot_ids)),  # type: ignore[attr-defined]
            UserLot.actif == True,  # noqa: E712
        )
    ).all()
    return {ul.user_id for ul in ensemble if _lien(ul) in TYPES_COPROPRIETAIRES}


def attribuer_aux_coproprietaires(acces, type_acces, session: Session) -> None:
    """Attribue cet accès à son porteur ET aux copropriétaires concernés.

    🔴 Le geste était écrit DEUX fois, une par type d'accès
    (`_create_user_telecommandes`, `_create_user_vigiks`), alors que la seule
    chose qui changeait — la table d'attribution et le nom de sa colonne — est
    décrite par `TypeAcces` depuis le 14/09/2026.

    Les trois ensembles se cumulent sans ordre : le porteur, les copropriétaires
    du lot de l'accès, et ceux de tous les lots du porteur. Un accès déjà
    attribué n'est pas recréé — `TypeAcces.attribuer` rend `False`.
    """
    beneficiaires = {acces.user_id}
    beneficiaires |= coproprietaires_du_lot(acces.lot_id, session)
    beneficiaires |= coproprietaires_partages(acces.user_id, session)
    for user_id in beneficiaires:
        type_acces.attribuer(session, user_id=user_id, acces_id=acces.id)
