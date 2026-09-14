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
from app.utils.batiments import libelle_lot
from app.database import get_session
from app.models.core import (
    CommandeAcces, Notification, StatutAcces, StatutImport,
    Telecommande, Utilisateur, UserLot, Vigik,
    Lot,
)
from app.schemas import CommandeAccesCreate, CommandeAccesRead
from app.utils.acces_detachement import detacher_acces
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


def _mes_acces(session: Session, type_acces: TypeAcces, user: Utilisateur) -> list:
    """Les accès d'un porteur : les siens, plus ceux qui lui sont attribués.

    ⚠️ Le dédoublonnage n'est pas décoratif : un copropriétaire peut être à la
    fois porteur direct et attributaire du même objet, et la liste l'affichait
    alors deux fois.
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
    return sortie


def _signaler_perdu(session: Session, type_acces: TypeAcces, objet_id: int,
                    user: Utilisateur) -> dict:
    objet = _acces_du_porteur(session, type_acces, objet_id, user)
    objet.statut = StatutAcces.perdu
    session.add(objet)
    session.commit()
    return {"statut": objet.statut}


def _supprimer_acces(session: Session, type_acces: TypeAcces, objet_id: int,
                     user: Utilisateur) -> None:
    """L'attribution part, la ligne d'import se délie, l'objet disparaît.

    Le pourquoi du détachement est dans `utils/acces_detachement.py`.
    """
    _acces_du_porteur(session, type_acces, objet_id, user)
    detacher_acces(
        session, objet_id,
        type_acces.modele_attribution, type_acces.colonne_attribution,
        type_acces.modele_import, type_acces.colonne_import,
    )
    session.delete(session.get(type_acces.modele, objet_id))
    session.commit()


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
    return _signaler_perdu(session, VIGIK, vigik_id, user)


@router.patch("/telecommandes/{tc_id}/perdu")
def signaler_tc_perdu(
    tc_id: int,
    body: SignalerPerduBody,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    return _signaler_perdu(session, TELECOMMANDE, tc_id, user)


@router.delete("/vigiks/{vigik_id}", status_code=204)
def supprimer_vigik(
    vigik_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    _supprimer_acces(session, VIGIK, vigik_id, user)


@router.delete("/telecommandes/{tc_id}", status_code=204)
def supprimer_telecommande(
    tc_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    _supprimer_acces(session, TELECOMMANDE, tc_id, user)


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
                #  🔴 `f"{lot.type}"` rendait « TypeLot.appartement 314 » — la
                #  représentation Python de l'enum, jusque sur l'écran du CS
                #  (12/09/2026, signalé à l'écran). Le libellé est écrit UNE
                #  fois, dans `utils/batiments`, et trois autres endroits le
                #  composaient déjà correctement à la main.
                lot_libelle=libelle_lot(lot),
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
