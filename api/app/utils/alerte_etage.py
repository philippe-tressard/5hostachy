"""Prévenir l'administrateur du site quand un résident et son lot se contredisent.

Demandé par Philippe le 09/09/2026 : *« notifier s'il y a une différence entre le
lot et la saisie du résident ; préférer celle du Lot et envoyer un mail à
l'administrateur du site qu'il vérifie et corrige l'info si nécessaire »*.

## Pourquoi un module, et pas dix lignes dans `auth.py`

`routers/auth.py` passe déjà le plafond de modularité, et cette alerte n'est pas
une règle d'authentification : elle lit le patrimoine, compose un courriel et
connaît le gestionnaire du site. La décision — *y a-t-il divergence ?* — reste
dans `utils/etages.py`, pure et testable sans base ni SMTP.

## Ce qui n'est PAS ici, volontairement

La déduplication. Elle vit dans l'appelant, sous la forme d'une condition sur le
**changement** (`body.etage != user.etage`) : c'est la seule qui n'exige aucun
stockage, et elle dit exactement ce qu'on veut dire — une alerte par valeur neuve.
"""
from __future__ import annotations

from fastapi import BackgroundTasks
from sqlmodel import Session, select

from app.models.core import Lot, UserLot, Utilisateur
from app.utils.etages import divergence_etage, etage_label


def lots_de(session: Session, user: Utilisateur) -> list[Lot]:
    """Les lots ACTIVEMENT rattachés à ce compte.

    ⚠️ Pas de repli « tous les lots » pour un compte d'administration, à la
    différence de `GET /lots/mes-lots` : ce repli sert à *consulter* le patrimoine,
    et l'appliquer ici comparerait l'étage d'un administrateur à un lot qui n'est
    pas le sien.
    """
    rattachements = session.exec(
        select(UserLot).where(UserLot.user_id == user.id, UserLot.actif == True)  # noqa: E712
    ).all()
    ids = [ul.lot_id for ul in rattachements]
    if not ids:
        return []
    return list(session.exec(select(Lot).where(Lot.id.in_(ids))).all())


def alerter_divergence_etage(
    session: Session,
    background_tasks: BackgroundTasks,
    user: Utilisateur,
    etage_saisi: int | None,
) -> None:
    """Envoie l'alerte si la saisie contredit le lot — silencieux sinon.

    Silencieux aussi quand le site n'a pas d'adresse de gestionnaire : un envoi
    sans destinataire n'est pas une alerte, c'est une ligne d'erreur dans un
    journal que personne ne lit (`standards/04` §7).
    """
    ecart = divergence_etage(etage_saisi, lots_de(session, user))
    if ecart is None:
        return

    from app.utils.email import get_site_manager_notification_email, send_email

    destinataire, cfg = get_site_manager_notification_email(session)
    if not destinataire:
        return

    saisi, lot = ecart
    background_tasks.add_task(
        send_email,
        code="etage_divergent",
        to=destinataire,
        context={
            "utilisateur": {
                "nom": user.nom,
                "prenom": user.prenom,
                "email": user.email,
            },
            "etage": {
                #  Les libellés sont calculés ICI : un modèle Jinja n'a pas à
                #  porter « RDC » ni « SS 1 », et le faire en gabarit rouvrirait
                #  la septième écriture de `etage_label`.
                "saisi": etage_label(saisi),
                "lot": etage_label(lot),
            },
            "residence": {"nom": cfg.get("site_nom") or "5Hostachy"},
            "app": {"url": (cfg.get("site_url") or "https://localhost").rstrip("/")},
        },
    )
