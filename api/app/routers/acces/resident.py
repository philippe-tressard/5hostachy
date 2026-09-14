"""Les badges vus par leur porteur — et la vue d'ensemble du conseil syndical.

Un résident déclare son badge, signale une perte, commande un accès. Le CS y
ajoute deux LECTURES : tous les vigiks, toutes les télécommandes, avec leur
porteur.

🔴 Trois routes d'ÉCRITURE ont été supprimées de ce module le 06/09/2026
(#805) : créer un vigik, créer une télécommande, changer un statut. Le
commentaire qui les remplace dit pourquoi — enregistrer un badge est déjà
couvert deux fois, et une troisième voie jamais exercée dérive.
"""
from datetime import datetime

from fastapi import (
    APIRouter, BackgroundTasks, Depends, HTTPException,
)
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import get_current_user
from app.database import get_session
from app.models.core import (
    CommandeAcces, Notification, StatutAcces, StatutImport,
    Utilisateur, UserLot, Lot,
)
from app.schemas import CommandeAccesCreate, CommandeAccesRead
from app.routers.acces.vues import AccesOut
from app.utils.types_acces import TELECOMMANDE, TYPES_ACCES, TypeAcces, VIGIK
from app.utils.destinataires import membres_cs_notifiables
from app.utils.noms import nom_affiche

router = APIRouter()


#  ── L'ACCÈS, écrit une fois ────────────────────────────────────────────────
#
#  🔴 Quatre paires de fonctions jumelles vivaient ici — lister, signaler perdu,
#  supprimer, déclarer — identiques à trois mots près. `utils/types_acces.py`
#  porte ces trois mots ; ce qui suit porte les gestes.
#
#  ⚠️ Les ROUTES restent distinctes (`/vigiks/…` et `/telecommandes/…`) : ce sont
#  les adresses que le front appelle déjà, et les fondre serait une rupture pour
#  un gain nul. Ce sont les CORPS qui étaient recopiés, pas les URL.


def _acces_du_porteur(session: Session, type_acces: TypeAcces, objet_id: int,
                      user: Utilisateur):
    """L'objet, s'il appartient bien à qui le demande — sinon 404.

    🔒 Ce contrôle de propriété était écrit QUATRE fois, à l'identique. Une règle
    d'autorisation recopiée est une règle qu'on durcira à trois endroits sur
    quatre : elle vit ici, et les gestes l'appellent.

    ⚠️ **404 et non 403**, comme les quatre copies le faisaient : répondre
    « interdit » confirmerait l'existence d'un badge qui ne vous appartient pas.
    """
    objet = session.get(type_acces.modele, objet_id)
    if not objet or objet.user_id != user.id:
        raise HTTPException(404, f"{type_acces.libelle} introuvable")
    return objet


def _mes_acces(session: Session, type_acces: TypeAcces,
               user: Utilisateur) -> list[AccesOut]:
    """Les accès d'un porteur : les siens, plus ceux qui lui sont attribués.

    ⚠️ Le dédoublonnage n'est pas décoratif : un copropriétaire peut être à la
    fois porteur direct et attributaire du même objet, et la liste l'affichait
    alors deux fois.

    🔴 **Une VUE, plus l'objet brut** (15/09/2026, demandé à l'écran : *« ajouter
    la colonne Accès »*). La liste rendait `session.exec(select(Vigik))` tel
    quel, donc `perimetre_cible` sous sa forme de stockage — la chaîne
    `'["bat:2"]'` là où l'écran attend une liste de codes. Parser côté écran
    aurait fait une seconde lecture du même champ ; `AccesOut` la fait une fois,
    et la vue du conseil syndical en dérive.
    """
    modele = type_acces.modele
    champ = getattr(type_acces.modele_attribution, type_acces.colonne_attribution)
    directs = session.exec(select(modele).where(modele.user_id == user.id)).all()
    attribues = session.exec(
        select(modele)
        .join(type_acces.modele_attribution, modele.id == champ)
        .where(type_acces.modele_attribution.user_id == user.id)
    ).all()
    vus, sortie = set(), []
    for objet in [*directs, *attribues]:
        if objet.id not in vus:
            vus.add(objet.id)
            sortie.append(objet)
    return AccesOut.depuis(session, type_acces, sortie)


def _signaler_perdu(session: Session, type_acces: TypeAcces, objet_id: int,
                    user: Utilisateur) -> dict:
    objet = _acces_du_porteur(session, type_acces, objet_id, user)
    objet.statut = StatutAcces.perdu
    session.add(objet)
    session.commit()
    return {"statut": objet.statut}


#  🔴 `_supprimer_acces` A ÉTÉ RETIRÉ LE 15/09/2026, avec ses deux routes —
#  demandé à l'écran :
#
#      « sur la page Mes lots & accès : enlève la poubelle. Un résident ne peut
#        pas supprimer un accès, il peut juste signaler qu'il a perdu. »
#
#  Et c'est une correction de FOND, pas de présentation. Le geste détruisait la
#  ligne : l'attribution partait, l'import se déliait, l'objet disparaissait.
#  Or **le badge, lui, existe toujours** — il est dans une poche, dans un tiroir,
#  ou perdu. Le parc cessait de pouvoir dire qu'il circule, et l'import le
#  reproposait à la résolution suivante comme s'il n'avait jamais été remis.
#
#  C'est la règle déjà déployée partout : archiver sur la vue principale,
#  supprimer réservé à l'admin (`ux-patterns` §8). Elle vaut ici aussi — et la
#  suppression définitive existe, chez l'administrateur, sur l'écran du parc.
#
#  ⚠️ Retirer le bouton **sans retirer la route** aurait laissé le geste
#  accessible à qui appelle l'API directement : un écran n'est pas un contrôle
#  d'accès. Le détachement, lui, reste employé par le parc — il vit dans
#  `utils/acces_detachement`, et c'est pour cela qu'il n'était pas écrit ici.


def _declarer_acces(session: Session, type_acces: TypeAcces, code: str,
                    user: Utilisateur) -> dict:
    """Un porteur déclare un accès qu'il détient déjà.

    Si le code correspond à une ligne d'import non résolue, celle-ci est marquée
    résolue et **son lot est repris sur l'objet créé**.

    🔴 C'est la correction que la factorisation apporte (14/09/2026) : la branche
    vigik reprenait le `lot_id` de l'import, la branche télécommande ne le
    faisait pas. Une télécommande déclarée par son porteur restait donc sans lot
    dans la vue du conseil syndical, alors que l'import le connaissait. Les deux
    branches se ressemblaient assez pour qu'on ne relise jamais les deux.
    """
    objet = session.exec(
        select(type_acces.modele).where(
            type_acces.modele.code == code,
            type_acces.modele.user_id == user.id,
        )
    ).first()
    if objet:
        raise HTTPException(400, f"{type_acces.libelle} déjà enregistré sur votre compte")

    objet = type_acces.modele(code=code, user_id=user.id, statut=StatutAcces.actif)
    session.add(objet)
    session.flush()

    ligne = session.exec(
        select(type_acces.modele_import).where(
            type_acces.champ_code_import == code,
            type_acces.modele_import.statut != StatutImport.resolu,
        )
    ).first()
    if ligne:
        ligne.statut = StatutImport.resolu
        setattr(ligne, type_acces.colonne_import, objet.id)
        ligne.resolu_le = datetime.utcnow()
        if not ligne.user_proprietaire_id:
            ligne.user_proprietaire_id = user.id
        if ligne.lot_id:
            objet.lot_id = ligne.lot_id
        session.add(ligne)

    session.commit()
    session.refresh(objet)
    return {"type": type_acces.cle, "id": objet.id, "code": code,
            "import_resolu": ligne is not None}


# ── Vue résident ────────────────────────────────────────────────────────────

@router.get("/mes-vigiks")
def mes_vigiks(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    return _mes_acces(session, VIGIK, user)


@router.get("/mes-telecommandes")
def mes_telecommandes(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    return _mes_acces(session, TELECOMMANDE, user)


@router.get("/mes-commandes", response_model=list[CommandeAccesRead])
def mes_commandes(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    return session.exec(
        select(CommandeAcces)
        .where(CommandeAcces.user_id == user.id)
        .order_by(CommandeAcces.cree_le.desc())
    ).all()


@router.post("/commandes", response_model=CommandeAccesRead, status_code=201)
def creer_commande(
    body: CommandeAccesCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    # Vérifie que l'utilisateur est bien lié au lot
    lien = session.exec(
        select(UserLot).where(UserLot.user_id == user.id, UserLot.lot_id == body.lot_id)
    ).first()
    if not lien:
        raise HTTPException(403, "Vous n'êtes pas associé à ce lot")

    cmd = CommandeAcces(
        user_id=user.id,
        lot_id=body.lot_id,
        type=body.type,
        quantite=body.quantite,
        motif=body.motif,
    )
    session.add(cmd)
    session.flush()

    # Numéro affichable du lot — `lot_id` est un identifiant interne, illisible
    # pour un membre du CS qui reçoit la demande.
    lot = session.get(Lot, body.lot_id)
    lot_numero = lot.numero if lot else str(body.lot_id)

    # Notifier CS
    cs = session.exec(
        select(Utilisateur).where(
            Utilisateur.role.in_(["conseil_syndical", "admin"])
        )
    ).all()
    for membre in cs:
        session.add(Notification(
            destinataire_id=membre.id,
            type="vigik",
            titre=f"Nouvelle demande de {body.type}",
            corps=f"{nom_affiche(user.prenom, user.nom)} — lot {lot_numero}",
            lien="/espace-cs",
        ))

    # ── Email au CS ───────────────────────────────────────────────────────
    # `vigik_commande_recue` n'était envoyé par personne : le CS ne découvrait
    # la demande qu'en ouvrant l'application. Une commande de badge attend une
    # décision humaine — elle doit atteindre son destinataire (01/08/2026).
    # Passe par `membres_cs_notifiables`, source unique des destinataires CS.
    destinataires_cs = membres_cs_notifiables(session)
    if destinataires_cs:
        from app.utils.email import send_email_group
        background_tasks.add_task(
            send_email_group,
            code="vigik_commande_recue",
            to_recipients=destinataires_cs,
            context={
                "type": body.type,
                "lot": {"numero": lot_numero},
                "demandeur": {"prenom": user.prenom, "nom": user.nom},
            },
        )

    session.commit()
    session.refresh(cmd)
    return cmd


class SignalerPerduBody(BaseModel):
    raison: str = ""


@router.patch("/vigiks/{vigik_id}/perdu")
def signaler_vigik_perdu(
    vigik_id: int,
    body: SignalerPerduBody,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    return _signaler_perdu(session, VIGIK, vigik_id, user)


@router.patch("/telecommandes/{tc_id}/perdu")
def signaler_tc_perdu(
    tc_id: int,
    body: SignalerPerduBody,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    return _signaler_perdu(session, TELECOMMANDE, tc_id, user)


class DeclarerBadgeBody(BaseModel):
    type: str  # 'vigik' | 'telecommande'
    code: str


@router.post("/declarer-badge", status_code=201)
def declarer_badge(
    body: DeclarerBadgeBody,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Un résident déclare un badge / TC qu'il possède déjà.

    ⚠️ Le type est cherché dans `TYPES_ACCES`, jamais comparé à des chaînes
    écrites ici : une seconde liste des types connus diverge au troisième accès.
    """
    code = body.code.strip()
    if not code:
        raise HTTPException(422, "Code vide")
    type_acces = TYPES_ACCES.get(body.type)
    if type_acces is None:
        raise HTTPException(422, "Type invalide : " + " ou ".join(TYPES_ACCES))
    return _declarer_acces(session, type_acces, code, user)
