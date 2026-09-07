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
from typing import Optional

from fastapi import (
    APIRouter, BackgroundTasks, Depends, HTTPException,
)
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_cs_or_admin
from app.database import get_session
from app.models.core import (
    CommandeAcces, Notification, StatutAcces, StatutImport,
    Telecommande, TelecommandeImport, Utilisateur, UserLot, Vigik, VigikImport,
    UserVigik, UserTelecommande,
    Lot,
)
from app.schemas import CommandeAccesCreate, CommandeAccesRead
from app.utils.acces_detachement import detacher_acces
from app.utils.destinataires import membres_cs_notifiables
from app.utils.noms import nom_affiche

router = APIRouter()



router = APIRouter()

# ── Vue résident ────────────────────────────────────────────────────────────

@router.get("/mes-vigiks")
def mes_vigiks(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    # Vigiks possédés directement + associés via UserVigik (copropriétaire)
    directs = session.exec(
        select(Vigik).where(Vigik.user_id == user.id)
    ).all()
    via_assoc = session.exec(
        select(Vigik).join(UserVigik, Vigik.id == UserVigik.vigik_id).where(
            UserVigik.user_id == user.id
        )
    ).all()
    seen = set()
    result = []
    for v in [*directs, *via_assoc]:
        if v.id not in seen:
            seen.add(v.id)
            result.append(v)
    return result


@router.get("/mes-telecommandes")
def mes_telecommandes(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    # TC possédées directement + associées via UserTelecommande (copropriétaire)
    directs = session.exec(
        select(Telecommande).where(Telecommande.user_id == user.id)
    ).all()
    via_assoc = session.exec(
        select(Telecommande).join(
            UserTelecommande, Telecommande.id == UserTelecommande.telecommande_id
        ).where(UserTelecommande.user_id == user.id)
    ).all()
    seen = set()
    result = []
    for t in [*directs, *via_assoc]:
        if t.id not in seen:
            seen.add(t.id)
            result.append(t)
    return result


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
            corps=f"{user.prenom} {user.nom} — lot {lot_numero}",
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
    vigik = session.get(Vigik, vigik_id)
    if not vigik or vigik.user_id != user.id:
        raise HTTPException(404, "Vigik introuvable")
    vigik.statut = StatutAcces.perdu
    session.add(vigik)
    session.commit()
    return {"statut": vigik.statut}


@router.patch("/telecommandes/{tc_id}/perdu")
def signaler_tc_perdu(
    tc_id: int,
    body: SignalerPerduBody,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    tc = session.get(Telecommande, tc_id)
    if not tc or tc.user_id != user.id:
        raise HTTPException(404, "Télécommande introuvable")
    tc.statut = StatutAcces.perdu
    session.add(tc)
    session.commit()
    return {"statut": tc.statut}


@router.delete("/vigiks/{vigik_id}", status_code=204)
def supprimer_vigik(
    vigik_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    vigik = session.get(Vigik, vigik_id)
    if not vigik or vigik.user_id != user.id:
        raise HTTPException(404, "Badge introuvable")
    #  L'attribution part, la ligne d'import se délie — pourquoi, et pourquoi
    #  c'est le même geste que la télécommande : `utils/acces_detachement.py`.
    detacher_acces(session, vigik_id, UserVigik, "vigik_id", VigikImport, "vigik_id")
    session.delete(vigik)
    session.commit()


@router.delete("/telecommandes/{tc_id}", status_code=204)
def supprimer_telecommande(
    tc_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    tc = session.get(Telecommande, tc_id)
    if not tc or tc.user_id != user.id:
        raise HTTPException(404, "Télécommande introuvable")
    #  Même geste que le vigik, et désormais le même code (#546).
    detacher_acces(
        session, tc_id, UserTelecommande, "telecommande_id", TelecommandeImport, "telecommande_id"
    )
    session.delete(tc)
    session.commit()


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
    Si le code correspond à un import non résolu, celui-ci est marqué résolu."""
    code = body.code.strip()
    if not code:
        raise HTTPException(422, "Code vide")

    if body.type == "vigik":
        # Vérifier doublon
        existing = session.exec(select(Vigik).where(Vigik.code == code, Vigik.user_id == user.id)).first()
        if existing:
            raise HTTPException(400, "Ce badge est déjà enregistré sur votre compte")
        acces_obj = Vigik(code=code, user_id=user.id, statut=StatutAcces.actif)
        session.add(acces_obj)
        session.flush()
        # Tenter de résoudre un import correspondant
        imp_vigik = session.exec(
            select(VigikImport).where(
                VigikImport.code == code,
                VigikImport.statut != StatutImport.resolu,
            )
        ).first()
        if imp_vigik:
            imp_vigik.statut = StatutImport.resolu
            imp_vigik.vigik_id = acces_obj.id
            imp_vigik.resolu_le = datetime.utcnow()
            if not imp_vigik.user_proprietaire_id:
                imp_vigik.user_proprietaire_id = user.id
            if imp_vigik.lot_id:
                acces_obj.lot_id = imp_vigik.lot_id
            session.add(imp_vigik)
        session.commit()
        session.refresh(acces_obj)
        return {"type": "vigik", "id": acces_obj.id, "code": code, "import_resolu": imp_vigik is not None}

    elif body.type == "telecommande":
        existing = session.exec(select(Telecommande).where(Telecommande.code == code, Telecommande.user_id == user.id)).first()
        if existing:
            raise HTTPException(400, "Cette télécommande est déjà enregistrée sur votre compte")
        tc = Telecommande(code=code, user_id=user.id, statut=StatutAcces.actif)
        session.add(tc)
        session.flush()
        # Tenter de résoudre un import correspondant
        imp = session.exec(
            select(TelecommandeImport).where(
                TelecommandeImport.reference == code,
                TelecommandeImport.statut != StatutImport.resolu,
            )
        ).first()
        if imp:
            imp.statut = StatutImport.resolu
            imp.telecommande_id = tc.id
            imp.resolu_le = datetime.utcnow()
            if not imp.user_proprietaire_id:
                imp.user_proprietaire_id = user.id
            session.add(imp)
        session.commit()
        session.refresh(tc)
        return {"type": "telecommande", "id": tc.id, "code": code, "import_resolu": imp is not None}

    else:
        raise HTTPException(422, "Type invalide : vigik ou telecommande")

class AccesAdminOut(BaseModel):
    """Un badge tel que le conseil syndical a besoin de le VOIR.

    🔴 Les deux listes rendaient l'objet BRUT (`select(Vigik)`), donc `user_id`
    et `lot_id` — deux nombres. Un écran bâti dessus aurait affiché « badge 4521
    → utilisateur 37 », c'est-à-dire rien : la question qu'on pose à cette liste
    est *« qui a ce badge ? »*, et elle n'y répondait pas.

    C'est pourquoi enrichir la lecture faisait partie du lot qui l'expose : une
    route sans appelant n'est jamais mise à l'épreuve de la question à laquelle
    elle est censée répondre (#805).
    """
    id: int
    code: str
    statut: StatutAcces
    chez_locataire: bool
    porteur_nom: str
    porteur_id: int
    lot_libelle: Optional[str] = None
    cree_le: datetime


def _acces_admin_out(objets, session: Session) -> list[AccesAdminOut]:
    """Sérialise une liste de Vigik OU de Telecommande — les deux ont les mêmes
    champs utiles, et deux fonctions jumelles auraient divergé au premier ajout."""
    sortie = []
    for o in objets:
        porteur = session.get(Utilisateur, o.user_id)
        lot = session.get(Lot, o.lot_id) if o.lot_id else None
        sortie.append(
            AccesAdminOut(
                id=o.id,
                code=o.code,
                statut=o.statut,
                chez_locataire=o.chez_locataire,
                #  Le nom passe par `nom_affiche` : « Prénom NOM », comme partout
                #  ailleurs. Un `f"{prenom} {nom}"` local serait la 35e écriture
                #  de cette règle.
                porteur_nom=nom_affiche(porteur.prenom, porteur.nom) if porteur else "—",
                porteur_id=o.user_id,
                lot_libelle=f"{lot.type} {lot.numero}" if lot else None,
                cree_le=o.cree_le,
            )
        )
    #  Par code : c'est ce qu'on a sous les yeux quand on cherche « à qui est ce
    #  badge ? », un numéro gravé sur un objet physique.
    return sorted(sortie, key=lambda a: a.code)


@router.get("/admin/vigiks", response_model=list[AccesAdminOut])
def list_vigiks(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Tous les badges Vigik de la copropriété, avec leur porteur."""
    return _acces_admin_out(session.exec(select(Vigik)).all(), session)


@router.get("/admin/telecommandes", response_model=list[AccesAdminOut])
def list_telecommandes(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Toutes les télécommandes de parking, avec leur porteur."""
    return _acces_admin_out(session.exec(select(Telecommande)).all(), session)


#  🔴 TROIS ROUTES D'ÉCRITURE SUPPRIMÉES ICI le 06/09/2026 (#805), sur arbitrage :
#
#      PATCH  /acces/admin/vigiks/{id}      (changer le statut)
#      POST   /acces/admin/vigiks           (créer un badge)
#      POST   /acces/admin/telecommandes    (créer une télécommande)
#
#  Aucune n'avait d'appelant, et surtout : le besoin qu'elles servaient est déjà
#  couvert DEUX fois.
#
#  | Enregistrer des badges | par où |
#  |---|---|
#  | en masse | l'import Excel + `resoudre_import_*` |
#  | à l'unité | `POST /acces/declarer-badge`, par le résident lui-même |
#
#  Une troisième voie de création, jamais exercée, est du code qui dérive sans
#  qu'on le voie : `changer-role` était dans cet état et avait accumulé un
#  passe-droit que les gestes vivants n'ont pas (#801, même journée).
#
#  ⚠️ Elles n'étaient PAS défectueuses — vérifié : `create_vigik` appelait bien
#  `_create_user_vigiks`, comme la résolution d'import. C'est leur redondance qui
#  les condamne, pas un défaut. Les retirer sur un défaut supposé aurait été un
#  mauvais motif pour une bonne décision.
#
#  Ce qui RESTE, et pourquoi : les deux LECTURES ci-dessus répondent à une
#  question qu'aucun autre écran ne sait poser — « quels badges circulent, et
#  chez qui ? ». C'est le seul trou réel qu'avait ce domaine.
