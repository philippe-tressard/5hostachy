"""Router accès — vigiks, télécommandes, commandes d'accès."""
import unicodedata
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_cs_or_admin
from app.database import get_session
from app.models.core import (
    CommandeAcces, Notification, StatutAcces, StatutCommande, StatutImport,
    Telecommande, TelecommandeImport, Utilisateur, UserLot, Vigik, VigikImport,
    UserVigik, UserTelecommande,
    Batiment, Lot,
)
from app.schemas import CommandeAccesCreate, CommandeAccesRead
from app.utils.auto_match_service import (
    _user_keys, _matches_user, _split_name_candidates,
    _create_user_vigiks, _create_user_telecommandes, _lot_coproprio_ids,
)

router = APIRouter(prefix="/acces", tags=["accès"])


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
            corps=f"{user.prenom} {user.nom} — lot #{body.lot_id}",
            lien="/espace-cs",
        ))
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
    # Dé-lier l'import correspondant s'il existe
    imp = session.exec(
        select(TelecommandeImport).where(TelecommandeImport.telecommande_id == tc_id)
    ).first()
    if imp:
        imp.telecommande_id = None
        imp.statut = StatutImport.proprietaire_lie if imp.user_proprietaire_id else StatutImport.en_attente
        session.add(imp)
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

@router.get("/admin/vigiks")
def list_vigiks(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    return session.exec(select(Vigik)).all()


@router.get("/admin/telecommandes")
def list_telecommandes(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    return session.exec(select(Telecommande)).all()


class AccesBody(BaseModel):
    statut: StatutAcces


@router.patch("/admin/vigiks/{vigik_id}")
def update_vigik(
    vigik_id: int,
    body: AccesBody,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    vigik = session.get(Vigik, vigik_id)
    if not vigik:
        raise HTTPException(404, "Vigik introuvable")
    vigik.statut = body.statut
    session.add(vigik)
    session.commit()
    return vigik


class CreateVigikBody(BaseModel):
    code: str
    lot_id: int
    user_id: int


@router.post("/admin/vigiks", status_code=201)
def create_vigik(
    body: CreateVigikBody,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    vigik = Vigik(code=body.code, lot_id=body.lot_id, user_id=body.user_id)
    session.add(vigik)
    session.flush()
    _create_user_vigiks(vigik, session)
    session.commit()
    session.refresh(vigik)
    return vigik


class CreateTcBody(BaseModel):
    code: str
    lot_id: int | None = None
    user_id: int


@router.post("/admin/telecommandes", status_code=201)
def create_telecommande(
    body: CreateTcBody,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    tc = Telecommande(code=body.code, lot_id=body.lot_id, user_id=body.user_id)
    session.add(tc)
    session.flush()
    _create_user_telecommandes(tc, session)
    session.commit()
    session.refresh(tc)
    return tc


# ── Import Excel télécommandes ──────────────────────────────────────────────

def _normaliser(s: str) -> str:
    """Normalise un nom : majuscules, sans accents, espaces normalisés."""
    if not s:
        return ""
    s = s.strip().upper()
    s = "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(s.split())


@router.post("/admin/imports/upload", status_code=201)
async def upload_import_excel(
    file: UploadFile = File(...),
    remplacer: bool = Query(False, description="Supprimer les imports en_attente avant ré-import"),
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Upload un fichier Excel et importe les télécommandes dans la table de staging."""
    import io
    from app.utils.import_telecommandes import importer_depuis_bytes
    contenu = await file.read()
    stats = importer_depuis_bytes(contenu, session=session, remplacer=remplacer)
    return stats


@router.get("/admin/imports")
def list_imports(
    statut: str = Query(None),
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Liste les imports, optionnellement filtrés par statut."""
    q = select(TelecommandeImport)
    if statut:
        q = q.where(TelecommandeImport.statut == statut)
    q = q.order_by(TelecommandeImport.nom_proprietaire)
    items = session.exec(q).all()
    # Enrichir avec les utilisateurs liés
    result = []
    for item in items:
        d = item.model_dump()
        if item.user_proprietaire_id:
            u = session.get(Utilisateur, item.user_proprietaire_id)
            d["proprietaire"] = {"id": u.id, "nom": u.nom, "prenom": u.prenom} if u else None
        else:
            d["proprietaire"] = None
        if item.user_locataire_id:
            u = session.get(Utilisateur, item.user_locataire_id)
            d["locataire"] = {"id": u.id, "nom": u.nom, "prenom": u.prenom} if u else None
        else:
            d["locataire"] = None
        if item.lot_id:
            lot = session.get(Lot, item.lot_id)
            if lot:
                bat = session.get(Batiment, lot.batiment_id)
                d["lot_label"] = f"Bât.{bat.numero} — {lot.numero}" if bat else lot.numero
            else:
                d["lot_label"] = None
        else:
            d["lot_label"] = None
        result.append(d)
    return result


@router.post("/admin/imports/auto-match")
def auto_match_imports(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Tente de matcher automatiquement les imports en_attente avec les utilisateurs
    inscrits, en utilisant l'algorithme robuste (accents, tirets, noms composés,
    bigrammes). Quand un nom Excel matche plusieurs users (couple), le premier est
    affecté comme propriétaire — les co-propriétaires seront ajoutés à la résolution."""
    imports = session.exec(
        select(TelecommandeImport).where(
            TelecommandeImport.statut.in_([
                StatutImport.en_attente,
                StatutImport.proprietaire_lie,
            ])
        )
    ).all()
    utilisateurs = session.exec(select(Utilisateur)).all()

    # Pré-calculer les clés de matching pour chaque user
    user_keys_map: dict[int, set[str]] = {}
    for u in utilisateurs:
        user_keys_map[u.id] = _user_keys(u.nom, u.prenom)

    matched = 0
    for imp in imports:
        changed = False

        # Match propriétaire
        if not imp.user_proprietaire_id and imp.nom_proprietaire:
            candidats = [
                u for u in utilisateurs
                if _matches_user(imp.nom_proprietaire, user_keys_map[u.id])
            ]
            if candidats:
                imp.user_proprietaire_id = candidats[0].id
                changed = True

        # Match locataire
        if imp.nom_locataire and not imp.user_locataire_id:
            candidats = [
                u for u in utilisateurs
                if _matches_user(imp.nom_locataire, user_keys_map[u.id])
            ]
            if candidats:
                imp.user_locataire_id = candidats[0].id
                changed = True

        # Auto-link lot via UserLot si pas encore lié
        if imp.user_proprietaire_id and not imp.lot_id:
            user_lots = session.exec(
                select(UserLot).where(
                    UserLot.user_id == imp.user_proprietaire_id,
                    UserLot.actif == True,
                )
            ).all()
            if len(user_lots) == 1:
                imp.lot_id = user_lots[0].lot_id
                changed = True

        if changed:
            if imp.user_proprietaire_id:
                imp.statut = StatutImport.proprietaire_lie
            session.add(imp)
            matched += 1

    session.commit()
    return {"matches": matched, "total": len(imports)}


class PatchImportBody(BaseModel):
    user_proprietaire_id: int | None = None
    user_locataire_id: int | None = None
    lot_id: int | None = None
    chez_locataire: bool | None = None
    refuse_par_locataire: bool | None = None
    notes_admin: str | None = None


@router.patch("/admin/imports/{import_id}")
def patch_import(
    import_id: int,
    body: PatchImportBody,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Met à jour les liaisons d'un import (utilisateurs, lot, possession).
    Fonctionne même si l'import est déjà résolu (correction après coup)."""
    imp = session.get(TelecommandeImport, import_id)
    if not imp:
        raise HTTPException(404, "Import introuvable")

    if body.user_proprietaire_id is not None:
        imp.user_proprietaire_id = body.user_proprietaire_id or None
    if body.user_locataire_id is not None:
        imp.user_locataire_id = body.user_locataire_id or None
    if body.lot_id is not None:
        imp.lot_id = body.lot_id or None
    if body.chez_locataire is not None:
        imp.chez_locataire = body.chez_locataire
    if body.refuse_par_locataire is not None:
        imp.refuse_par_locataire = body.refuse_par_locataire
        if body.refuse_par_locataire:
            imp.chez_locataire = False  # refus → retour chez proprio
    if body.notes_admin is not None:
        imp.notes_admin = body.notes_admin

    # Si déjà résolu, mettre à jour la Telecommande liée directement
    if imp.statut == StatutImport.resolu and imp.telecommande_id:
        tc = session.get(Telecommande, imp.telecommande_id)
        if tc:
            new_user_id = (
                imp.user_locataire_id
                if (imp.chez_locataire and imp.user_locataire_id)
                else imp.user_proprietaire_id
            )
            if new_user_id:
                tc.user_id = new_user_id
                tc.lot_id = imp.lot_id or tc.lot_id
                session.add(tc)
    else:
        # Recalculer le statut pour les imports non résolus
        if imp.user_proprietaire_id:
            imp.statut = StatutImport.proprietaire_lie
        else:
            imp.statut = StatutImport.en_attente

    session.add(imp)
    session.commit()
    session.refresh(imp)
    return imp


@router.post("/admin/imports/{import_id}/resoudre")
def resoudre_import(
    import_id: int,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_cs_or_admin),
):
    """Résout un import : crée la Telecommande réelle et lie l'utilisateur.
    
    La télécommande est affectée au locataire si chez_locataire=True,
    sinon au propriétaire. Les copropriétaires du même lot sont automatiquement
    associés via UserTelecommande.
    """
    imp = session.get(TelecommandeImport, import_id)
    if not imp:
        raise HTTPException(404, "Import introuvable")
    if imp.statut == StatutImport.resolu:
        raise HTTPException(400, "Import déjà résolu")
    if imp.statut == StatutImport.ignore:
        raise HTTPException(400, "Cet import est ignoré")
    if not imp.user_proprietaire_id:
        raise HTTPException(422, "Le propriétaire doit être lié avant de résoudre")
    if not imp.reference:
        raise HTTPException(422, "Cet import n'a pas de référence de télécommande")

    # Déterminer le possesseur
    user_id = (
        imp.user_locataire_id
        if (imp.chez_locataire and imp.user_locataire_id)
        else imp.user_proprietaire_id
    )

    # Créer la Telecommande
    tc = Telecommande(
        code=imp.reference,
        lot_id=imp.lot_id or None,
        user_id=user_id,
        chez_locataire=imp.chez_locataire and bool(imp.user_locataire_id),
        statut=StatutAcces.actif,
    )
    session.add(tc)
    session.flush()

    # Associer tous les copropriétaires du lot via UserTelecommande
    _create_user_telecommandes(tc, session)

    # Marquer l'import comme résolu
    imp.statut = StatutImport.resolu
    imp.telecommande_id = tc.id
    imp.resolu_le = datetime.utcnow()
    session.add(imp)
    session.commit()
    session.refresh(tc)
    return {"telecommande": tc, "import_id": imp.id}


@router.post("/admin/imports/{import_id}/ignorer")
def ignorer_import(
    import_id: int,
    body: BaseModel = None,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Marque un import comme ignoré (accès non-résidentiel, doublon, etc.)."""
    imp = session.get(TelecommandeImport, import_id)
    if not imp:
        raise HTTPException(404, "Import introuvable")
    if imp.statut == StatutImport.resolu:
        raise HTTPException(400, "Import déjà résolu — ne peut être ignoré")
    imp.statut = StatutImport.ignore
    session.add(imp)
    session.commit()
    return {"statut": imp.statut}


@router.post("/admin/imports/{import_id}/remettre-en-attente")
def remettre_en_attente_import(
    import_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Remet un import ignoré en statut 'en attente' pour traitement ultérieur."""
    imp = session.get(TelecommandeImport, import_id)
    if not imp:
        raise HTTPException(404, "Import introuvable")
    if imp.statut != StatutImport.ignore:
        raise HTTPException(400, "Seuls les imports ignorés peuvent être remis en attente")
    imp.statut = StatutImport.en_attente
    session.add(imp)
    session.commit()
    return {"statut": imp.statut}


@router.post("/admin/imports/{import_id}/refuser-locataire")
def refuser_telecommande_locataire(
    import_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Le locataire a refusé la télécommande — elle reste/revient chez le propriétaire."""
    imp = session.get(TelecommandeImport, import_id)
    if not imp:
        raise HTTPException(404, "Import introuvable")
    imp.refuse_par_locataire = True
    imp.chez_locataire = False
    session.add(imp)
    session.commit()
    return {"refuse_par_locataire": True, "chez_locataire": False}


@router.get("/admin/imports/stats")
def stats_imports(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Statistiques synthétiques sur les imports."""
    all_imports = session.exec(select(TelecommandeImport)).all()
    total = len(all_imports)
    par_statut = {}
    for s in StatutImport:
        par_statut[s.value] = sum(1 for i in all_imports if i.statut == s)
    avec_reference = sum(1 for i in all_imports if i.reference)
    avec_locataire = sum(1 for i in all_imports if i.nom_locataire)
    return {
        "total": total,
        "en_attente": par_statut.get("en_attente", 0),
        "proprietaire_lie": par_statut.get("proprietaire_lie", 0),
        "resolu": par_statut.get("resolu", 0),
        "ignore": par_statut.get("ignore", 0),
        "avec_reference": avec_reference,
        "avec_locataire": avec_locataire,
    }


# ── Import Excel vigiks ────────────────────────────────────────────────────

@router.post("/admin/imports-vigik/upload", status_code=201)
async def upload_import_vigik_excel(
    file: UploadFile = File(...),
    remplacer: bool = Query(False, description="Supprimer les imports en_attente avant ré-import"),
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Upload un fichier Excel et importe les vigiks dans la table de staging."""
    from app.utils.import_vigiks import importer_depuis_bytes
    contenu = await file.read()
    stats = importer_depuis_bytes(contenu, session=session, remplacer=remplacer)
    return stats


@router.get("/admin/imports-vigik/stats")
def stats_imports_vigik(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Statistiques synthétiques sur les imports vigik."""
    all_imports = session.exec(select(VigikImport)).all()
    total = len(all_imports)
    par_statut = {}
    for s in StatutImport:
        par_statut[s.value] = sum(1 for i in all_imports if i.statut == s)
    avec_code = sum(1 for i in all_imports if i.code)
    avec_locataire = sum(1 for i in all_imports if i.nom_locataire)
    avec_lot = sum(1 for i in all_imports if i.lot_id)
    return {
        "total": total,
        "en_attente": par_statut.get("en_attente", 0),
        "proprietaire_lie": par_statut.get("proprietaire_lie", 0),
        "resolu": par_statut.get("resolu", 0),
        "ignore": par_statut.get("ignore", 0),
        "avec_code": avec_code,
        "avec_locataire": avec_locataire,
        "avec_lot": avec_lot,
    }


@router.get("/admin/imports-vigik")
def list_imports_vigik(
    statut: str = Query(None),
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Liste les imports vigik, optionnellement filtrés par statut."""
    q = select(VigikImport)
    if statut:
        q = q.where(VigikImport.statut == statut)
    q = q.order_by(VigikImport.nom_proprietaire)
    items = session.exec(q).all()
    result = []
    for item in items:
        d = item.model_dump()
        if item.user_proprietaire_id:
            u = session.get(Utilisateur, item.user_proprietaire_id)
            d["proprietaire"] = {"id": u.id, "nom": u.nom, "prenom": u.prenom} if u else None
        else:
            d["proprietaire"] = None
        if item.user_locataire_id:
            u = session.get(Utilisateur, item.user_locataire_id)
            d["locataire"] = {"id": u.id, "nom": u.nom, "prenom": u.prenom} if u else None
        else:
            d["locataire"] = None
        if item.lot_id:
            lot = session.get(Lot, item.lot_id)
            if lot:
                bat = session.get(Batiment, lot.batiment_id)
                d["lot_label"] = f"Bât.{bat.numero} — {lot.numero}" if bat else lot.numero
            else:
                d["lot_label"] = None
        else:
            d["lot_label"] = None
        result.append(d)
    return result


@router.post("/admin/imports-vigik/auto-match")
def auto_match_imports_vigik(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Tente de matcher automatiquement les imports vigik avec les utilisateurs
    inscrits, en utilisant l'algorithme robuste (accents, tirets, noms composés,
    bigrammes)."""
    from app.utils.import_vigiks import _build_lot_index
    imports = session.exec(
        select(VigikImport).where(
            VigikImport.statut.in_([
                StatutImport.en_attente,
                StatutImport.proprietaire_lie,
            ])
        )
    ).all()
    utilisateurs = session.exec(select(Utilisateur)).all()

    # Pré-calculer les clés de matching pour chaque user
    user_keys_map: dict[int, set[str]] = {}
    for u in utilisateurs:
        user_keys_map[u.id] = _user_keys(u.nom, u.prenom)

    lot_index = _build_lot_index(session)

    matched = 0
    for imp in imports:
        changed = False

        # Match propriétaire
        if not imp.user_proprietaire_id and imp.nom_proprietaire:
            candidats = [
                u for u in utilisateurs
                if _matches_user(imp.nom_proprietaire, user_keys_map[u.id])
            ]
            if candidats:
                imp.user_proprietaire_id = candidats[0].id
                changed = True

        # Match locataire
        if imp.nom_locataire and not imp.user_locataire_id:
            candidats = [
                u for u in utilisateurs
                if _matches_user(imp.nom_locataire, user_keys_map[u.id])
            ]
            if candidats:
                imp.user_locataire_id = candidats[0].id
                changed = True

        # Résolution lot via batiment_raw + appartement_raw
        if not imp.lot_id and imp.batiment_raw and imp.appartement_raw:
            from app.utils.import_vigiks import normaliser as _norm_vigik
            key = (_norm_vigik(imp.batiment_raw), _norm_vigik(imp.appartement_raw))
            lot_id = lot_index.get(key)
            if lot_id:
                imp.lot_id = lot_id
                changed = True

        # Auto-link lot via UserLot si encore pas résolu
        if imp.user_proprietaire_id and not imp.lot_id:
            user_lots = session.exec(
                select(UserLot).where(
                    UserLot.user_id == imp.user_proprietaire_id,
                    UserLot.actif == True,
                )
            ).all()
            if len(user_lots) == 1:
                imp.lot_id = user_lots[0].lot_id
                changed = True

        if changed:
            if imp.user_proprietaire_id:
                imp.statut = StatutImport.proprietaire_lie
            session.add(imp)
            matched += 1

    session.commit()
    return {"matches": matched, "total": len(imports)}


class PatchImportVigikBody(BaseModel):
    user_proprietaire_id: int | None = None
    user_locataire_id: int | None = None
    lot_id: int | None = None
    chez_locataire: bool | None = None
    refuse_par_locataire: bool | None = None
    notes_admin: str | None = None


@router.patch("/admin/imports-vigik/{import_id}")
def patch_import_vigik(
    import_id: int,
    body: PatchImportVigikBody,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Met à jour les liaisons d'un import vigik.
    Fonctionne même si l'import est déjà résolu (correction après coup)."""
    imp = session.get(VigikImport, import_id)
    if not imp:
        raise HTTPException(404, "Import introuvable")

    if body.user_proprietaire_id is not None:
        imp.user_proprietaire_id = body.user_proprietaire_id or None
    if body.user_locataire_id is not None:
        imp.user_locataire_id = body.user_locataire_id or None
    if body.lot_id is not None:
        imp.lot_id = body.lot_id or None
    if body.chez_locataire is not None:
        imp.chez_locataire = body.chez_locataire
    if body.refuse_par_locataire is not None:
        imp.refuse_par_locataire = body.refuse_par_locataire
        if body.refuse_par_locataire:
            imp.chez_locataire = False
    if body.notes_admin is not None:
        imp.notes_admin = body.notes_admin

    # Si déjà résolu, mettre à jour le Vigik lié directement
    if imp.statut == StatutImport.resolu and imp.vigik_id:
        vigik = session.get(Vigik, imp.vigik_id)
        if vigik:
            new_user_id = (
                imp.user_locataire_id
                if (imp.chez_locataire and imp.user_locataire_id)
                else imp.user_proprietaire_id
            )
            if new_user_id:
                vigik.user_id = new_user_id
                vigik.lot_id = imp.lot_id or vigik.lot_id
                session.add(vigik)
    else:
        imp.statut = StatutImport.proprietaire_lie if imp.user_proprietaire_id else StatutImport.en_attente

    session.add(imp)
    session.commit()
    session.refresh(imp)
    return imp


@router.post("/admin/imports-vigik/{import_id}/resoudre")
def resoudre_import_vigik(
    import_id: int,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_cs_or_admin),
):
    """Résout un import vigik : crée le Vigik réel et lie l'utilisateur.
    Les copropriétaires du même lot sont automatiquement associés via UserVigik."""
    imp = session.get(VigikImport, import_id)
    if not imp:
        raise HTTPException(404, "Import introuvable")
    if imp.statut == StatutImport.resolu:
        raise HTTPException(400, "Import déjà résolu")
    if imp.statut == StatutImport.ignore:
        raise HTTPException(400, "Cet import est ignoré")
    if not imp.user_proprietaire_id:
        raise HTTPException(422, "Le propriétaire doit être lié avant de résoudre")
    if not imp.code:
        raise HTTPException(422, "Cet import n'a pas de code vigik")

    user_id = (
        imp.user_locataire_id
        if (imp.chez_locataire and imp.user_locataire_id)
        else imp.user_proprietaire_id
    )

    vigik = Vigik(
        code=imp.code,
        lot_id=imp.lot_id or None,
        user_id=user_id,
        statut=StatutAcces.actif,
    )
    session.add(vigik)
    session.flush()

    # Associer tous les copropriétaires du lot via UserVigik
    _create_user_vigiks(vigik, session)

    imp.statut = StatutImport.resolu
    imp.vigik_id = vigik.id
    imp.resolu_le = datetime.utcnow()
    session.add(imp)
    session.commit()
    session.refresh(vigik)
    return {"vigik": vigik, "import_id": imp.id}


@router.post("/admin/imports-vigik/{import_id}/ignorer")
def ignorer_import_vigik(
    import_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Marque un import vigik comme ignoré."""
    imp = session.get(VigikImport, import_id)
    if not imp:
        raise HTTPException(404, "Import introuvable")
    if imp.statut == StatutImport.resolu:
        raise HTTPException(400, "Import déjà résolu — ne peut être ignoré")
    imp.statut = StatutImport.ignore
    session.add(imp)
    session.commit()
    return {"statut": imp.statut}
