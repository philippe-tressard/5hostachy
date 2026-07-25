"""Résolution des destinataires CS — source unique.

Factorise la logique « membres du CS concernés par un périmètre » utilisée par
la démarche nouvel arrivant (`admin.py`) et par les annonces de hall
(`annonces_hall.py`). Ne pas dupliquer ces règles dans les routers.

Règles :
  - Seuls les membres du CS **liés à un compte utilisateur actif avec e-mail**
    sont notifiables (`MembreCS.user_id` renseigné).
  - Le **gestionnaire du site** est toujours ajouté, quel que soit le périmètre.
  - Périmètre transverse (résidence / parking / cave / AFUL) → tout le CS.
"""
from __future__ import annotations

from typing import Optional

from sqlmodel import Session, select

from app.models.core import ConfigSite, MembreCS, Utilisateur
from app.utils.visibility import SCOPES_RESIDENCE


def site_manager_user_id(session: Session) -> Optional[int]:
    """Id utilisateur du gestionnaire du site (ConfigSite), ou None."""
    cfg = session.get(ConfigSite, "site_manager_user_id")
    if not cfg:
        return None
    valeur = (cfg.valeur or "").strip()
    return int(valeur) if valeur.isdigit() else None


def batiments_du_perimetre(perimetres: list[str]) -> Optional[set[int]]:
    """`['bat:1','bat:3']` → `{1, 3}` ; None si le périmètre couvre la résidence.

    Les périmètres transverses (parking, cave, AFUL) concernent l'ensemble des
    résidents : ils sont traités comme « résidence entière ».
    """
    if not perimetres:
        return None
    ids: set[int] = set()
    for p in perimetres:
        p = p.lower()
        if p in SCOPES_RESIDENCE:
            return None
        if p.startswith("bat:"):
            ident = p.split(":", 1)[1]
            if ident.isdigit():
                ids.add(int(ident))
    return ids or None


def membres_cs_notifiables(
    session: Session, batiment_ids: Optional[set[int]] = None
) -> list[tuple[int, str]]:
    """Destinataires CS `[(user_id, email)]`, dédoublonnés.

    `batiment_ids` à None → tous les membres du CS. Sinon, membres rattachés à
    l'un des bâtiments, plus le gestionnaire du site.
    """
    manager_id = site_manager_user_id(session)

    stmt = select(MembreCS).where(MembreCS.user_id != None)  # noqa: E711
    if batiment_ids:
        filtres = MembreCS.batiment_id.in_(batiment_ids)  # type: ignore[union-attr]
        if manager_id is not None:
            filtres = filtres | (MembreCS.user_id == manager_id)
        stmt = stmt.where(filtres)
    membres = session.exec(stmt).all()

    destinataires: list[tuple[int, str]] = []
    vus: set[str] = set()
    for membre in membres:
        user = session.get(Utilisateur, membre.user_id)
        if not user or not user.actif or not user.email:
            continue
        email = user.email.strip()
        if not email or email.lower() in vus:
            continue
        vus.add(email.lower())
        destinataires.append((user.id, email))
    return destinataires
