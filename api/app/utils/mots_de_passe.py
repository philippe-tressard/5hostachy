"""La règle de robustesse d'un mot de passe — écrite une fois.

Extraite de `routers/auth.py` le 14/08/2026 avec le bloc « mot de passe » : trois
routes l'appellent, et deux d'entre elles vivent désormais dans un autre fichier.
La laisser dans `auth.py` aurait obligé le second module à importer un nom privé
d'un router, ou — bien pire — à recopier les quatre critères.

Un critère recopié diverge : c'est exactement ce qui produirait un mot de passe
accepté à l'inscription et refusé au changement, sans que rien ne le signale.
"""

import re

from fastapi import HTTPException


def verifier_robustesse(password: str) -> None:
    """Vérifie la complexité du mot de passe. Lève HTTPException 400 si les critères ne sont pas satisfaits."""
    errors = []
    if len(password) < 8:
        errors.append("au moins 8 caractères")
    if not re.search(r"[A-Z]", password):
        errors.append("une lettre majuscule")
    if not re.search(r"\d", password):
        errors.append("un chiffre")
    if not re.search(r"[@$!%*?&#._\-+]", password):
        errors.append("un caractère spécial (@$!%*?&#._-+)")
    if errors:
        raise HTTPException(400, "Le mot de passe doit contenir : " + ", ".join(errors) + ".")


def poser_mot_de_passe(
    session,
    utilisateur,
    nouveau: str,
    *,
    jeton_courant: str | None = None,
) -> int:
    """Pose un nouveau mot de passe **et** ferme les sessions qu'il ouvrait.

    🔴 Les deux portes divergeaient jusqu'au 19/09/2026 (#1027). « Mot de passe
    oublié » révoquait toutes les sessions actives ; « changer mon mot de passe »
    ne révoquait rien. Un attaquant qui détenait une session ouverte la
    conservait **sept jours** après que la victime avait changé son mot de passe
    — et la victime croyait avoir refermé la porte.

    Les deux gestes sont le même : *poser un mot de passe*. Ils s'écrivent donc
    ici une fois. C'est l'écriture la plus **stricte** qui l'emporte, et non la
    plus répandue : en sécurité, la minorité prudente gagne
    (`standards/02` §4 bis).

    :param jeton_courant: le jeton de rafraîchissement porté par la requête, s'il
        y en a un. La session qui le présente **survit** ; toutes les autres
        tombent. Sans lui — cas de la réinitialisation, où l'appelant n'est pas
        authentifié — **tout** tombe, ce qui est le comportement voulu : on
        réinitialise parce qu'on craint que quelqu'un d'autre soit entré.
    :return: le nombre de sessions révoquées.

    ⚠️ **Ce que cette fonction ne peut pas faire.** Le jeton d'accès est un JWT
    autoporteur, valable 120 minutes, que rien ne révoque côté serveur. La
    fenêtre d'un attaquant passe donc de 7 jours à **2 heures au plus**, pas à
    zéro. La fermer entièrement demanderait une liste de révocation par `jti` —
    un autre chantier, et il est nommé dans #1063 plutôt que laissé à deviner.
    """
    from sqlmodel import select

    from app.auth.jwt import hash_password
    from app.models.core import RefreshToken

    verifier_robustesse(nouveau)
    utilisateur.hashed_password = hash_password(nouveau)

    a_revoquer = session.exec(
        select(RefreshToken).where(
            RefreshToken.user_id == utilisateur.id,
            RefreshToken.revoked == False,  # noqa: E712
        )
    ).all()

    revoquees = 0
    for jeton in a_revoquer:
        if jeton_courant is not None and jeton.token == jeton_courant:
            continue
        jeton.revoked = True
        session.add(jeton)
        revoquees += 1

    session.add(utilisateur)
    return revoquees
