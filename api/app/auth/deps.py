from fastapi import Depends, HTTPException, Cookie, Header, status
from datetime import date
from sqlmodel import Session, select, or_

from app.auth.jwt import decode_token
from app.database import get_session
from app.models.core import Delegation, StatutDelegation, Utilisateur, RoleUtilisateur


def _get_current_user(
    access_token: str | None = Cookie(default=None),
    session: Session = Depends(get_session),
) -> Utilisateur:
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Non authentifié")

    payload = decode_token(access_token)
    if payload is None or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide")

    user_id: int = payload.get("sub")
    user = session.get(Utilisateur, int(user_id))
    if not user or not user.actif:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilisateur introuvable ou inactif")
    return user


def get_current_user(user: Utilisateur = Depends(_get_current_user)) -> Utilisateur:
    return user


def get_acting_user(
    x_acting_as: int | None = Header(default=None, alias="X-Acting-As"),
    user: Utilisateur = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Utilisateur:
    """Retourne l'utilisateur effectif : le mandant si l'aidant agit en délégation,
    sinon l'utilisateur connecté lui-même."""
    if x_acting_as is None or x_acting_as == user.id:
        return user

    today = date.today()
    delegation = session.exec(
        select(Delegation).where(
            Delegation.aidant_id == user.id,
            Delegation.mandant_id == x_acting_as,
            Delegation.statut == StatutDelegation.active,
            Delegation.date_debut <= today,
            or_(Delegation.date_fin.is_(None), Delegation.date_fin >= today),  # type: ignore[arg-type]
        )
    ).first()

    if not delegation:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Aucune délégation active pour cet utilisateur",
        )

    mandant = session.get(Utilisateur, x_acting_as)
    if not mandant or not mandant.actif:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Mandant introuvable ou inactif")
    return mandant


def require_role(*roles: RoleUtilisateur):
    def checker(user: Utilisateur = Depends(get_current_user)):
        if not user.has_role(*roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Droits insuffisants")
        return user
    return checker


def require_proprietaire(user: Utilisateur = Depends(get_current_user)) -> Utilisateur:
    if not user.has_role(RoleUtilisateur.propriétaire, RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Réservé aux propriétaires")
    return user


def require_cs_or_admin(user: Utilisateur = Depends(get_current_user)) -> Utilisateur:
    if not user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Réservé au conseil syndical et à l'admin")
    return user


def require_admin(user: Utilisateur = Depends(get_current_user)) -> Utilisateur:
    if not user.has_role(RoleUtilisateur.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Réservé à l'admin")
    return user


def peut_commander(user: Utilisateur) -> bool:
    """Cet utilisateur peut-il fixer les champs « de commandement » ?

    Les champs de commandement sont ceux qui engagent autre chose que leur
    auteur : à qui la demande est adressée (syndic, conseil syndical), pour qui
    elle est saisie, et où elle en est dans son workflow. Un résident ne les
    fixe pas — sinon il peut adresser un ticket au syndic sans passer par le CS,
    ou déposer un signalement déjà « Résolu », donc hors du suivi, sans que
    personne l'ait regardé.

    POURQUOI ICI ET PAS DANS LE ROUTEUR (16/08/2026). Cette règle était écrite
    en ligne, une fois par champ — `destinataire_syndic if est_cs else False`,
    répété cinq fois — et j'allais en ajouter une sixième pour le workflow.
    Une règle d'autorisation recopiée à côté de chaque champ ne se durcit pas :
    on en corrige quatre sur six. Elle vit donc ici, avec les autres, où
    `test_autorisation.py` la voit (socle 03 §1, exigence 0c du pré-check).

    C'est un PRÉDICAT, pas une dépendance FastAPI : il ne refuse pas la requête,
    il dit si l'on retient la valeur demandée ou le défaut. Refuser serait faux —
    un résident a le droit de créer un ticket, simplement pas d'en fixer
    l'adressage ni l'étape.
    """
    return user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin)


#  ── Qui peut ÉDITER, qui peut COMMENTER ─────────────────────────────────────
#
#  🔴 Deux droits distincts, arbitrés par l'utilisateur le 18/08/2026 :
#
#    > « Seul l'auteur peut l'éditer ou le commenter, avec l'admin (en cas de
#    >   Pb), mais aussi le CS peut commenter, pas éditer (s'il est au courant de
#    >   certaines choses et influer sur le workflow ou émettre un commentaire) »
#
#  Le conseil syndical sait des choses et doit pouvoir peser sur le suivi ;
#  réécrire le ticket d'un résident n'est pas son rôle. C'était pourtant le cas :
#  `update_ticket` acceptait tout membre du CS sur n'importe quel ticket.
#
#  ⚠️ Ces fonctions vivent ICI et nulle part ailleurs. L'audit du 26/07/2026 a
#  trouvé trois dérives installées sans que rien ne les signale, dont un doublon
#  de `require_proprietaire` écrit dans un routeur et documenté comme officiel
#  dans les specs — la spec légitimait la dérive au lieu de la signaler.
#
#  Elles sont PURES (pas de `Depends`) : l'objet n'est connu qu'après lecture en
#  base, une dépendance FastAPI ne peut donc pas trancher. C'est aussi ce qui les
#  rend vérifiables sans monter d'application.


def est_auteur(objet, user: Utilisateur) -> bool:
    """L'objet est-il *celui de* cet utilisateur ?

    🔴 PUBLIQUE depuis le 29/08/2026. Elle s'appelait `_est_concerne` et n'était
    lue que par les deux fonctions ci-dessous — pendant que QUATORZE sites
    réécrivaient `objet.auteur_id != user.id` à la main, avec CINQ définitions
    différentes de « ou quelqu'un de plus haut ». Une règle d'accès privée n'est
    pas centralisée : elle est seulement inaccessible.

    ⚠️ « Saisi pour » compte comme auteur, et c'est la raison d'être du champ :
    un membre du CS qui dépose un ticket **au nom d'un résident** ne le dépossède
    pas de sa demande. Sans cela, le résident concerné serait le seul à ne pas
    pouvoir corriger ce qui parle de lui.
    """
    uid = user.id
    #  ⚠️ Sans identifiant, on ne compare rien : `None == None` rendrait VRAI sur
    #  tout objet dont l'auteur est nul, et ouvrirait l'édition à qui n'a pas
    #  d'identité. Un utilisateur authentifié en a toujours un — c'est donc une
    #  garde défensive, et son jumeau `$lib/droits.ts` la portait déjà. Les deux
    #  écritures d'une même règle doivent dire la même chose jusque dans leurs cas
    #  limites, sinon les comparer côte à côte ne prouve rien.
    if uid is None:
        return False
    return getattr(objet, "auteur_id", None) == uid or getattr(objet, "saisi_pour_user_id", None) == uid


def peut_editer(objet, user: Utilisateur) -> bool:
    """Corriger le CONTENU : titre, description, pièces, périmètre…

    L'auteur (ou le « saisi pour »), et l'admin en cas de problème. **Pas le
    conseil syndical** : il agit sur le suivi, il ne réécrit pas la demande.
    """
    return est_auteur(objet, user) or user.has_role(RoleUtilisateur.admin)


def peut_commenter(objet, user: Utilisateur) -> bool:
    """Ajouter une entrée d'Historique, et faire avancer le workflow.

    Les mêmes, **plus le conseil syndical** — c'est lui qui suit les dossiers.
    """
    return peut_editer(objet, user) or user.has_role(RoleUtilisateur.conseil_syndical)
