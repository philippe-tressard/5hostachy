"""Router lots — consultation et import (staging) des lots."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_cs_or_admin
from app.database import get_session
from app.models.core import (
    Batiment,
    Lot,
    LotImport,
    StatutLotImport,
    TypeLien,
    UserLot,
    Utilisateur,
    RoleUtilisateur,
    CommandeAcces,
)
from app.utils.import_xlsx import etage_de_lot, type_de_lot
from app.utils.resolution_lots import rapprocher_imports, resoudre_imports


# ── Helpers JSON utilisateurs ─────────────────────────────────────────────────

def _parse_users(utilisateurs_json: str) -> list[dict]:
    """Retourne la liste [{user_id, type_lien}] ou [] en cas d'erreur."""
    try:
        val = json.loads(utilisateurs_json or "[]")
        return val if isinstance(val, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _type_lien_from_str(s: str) -> TypeLien:
    try:
        return TypeLien(s)
    except ValueError:
        return TypeLien.propriétaire

router = APIRouter(prefix="/lots", tags=["lots"])


#  Helpers 

#  🔴 Le vocabulaire de la colonne TYPE (tables, `_norm`, `_type_from_raw`,
#  `_etage_from_raw`) vit dans `utils/import_xlsx` depuis #829 : il décrit ce
#  qu'un CLASSEUR contient, pas ce qu'un routeur fait. Il était écrit ici ET
#  dans `auto_match_service`, où la copie s'était logée dans un corps de
#  fonction pour contourner un homonyme.


#  Schémas 

class LotRead(BaseModel):
    id: int
    numero: str
    type: str
    type_appartement: Optional[str] = None
    etage: Optional[int] = None
    superficie: Optional[float] = None
    batiment_id: Optional[int] = None
    batiment_nom: Optional[str] = None


def _lot_read(lot: Lot) -> LotRead:
    return LotRead(
        id=lot.id,
        numero=lot.numero,
        type=lot.type.value if hasattr(lot.type, "value") else str(lot.type),
        type_appartement=lot.type_appartement,
        etage=lot.etage,
        superficie=lot.superficie,
        batiment_id=lot.batiment_id,
        batiment_nom=f"Bât. {lot.batiment.numero}" if lot.batiment else None,
    )


#  Endpoints publics 

@router.get("/mes-lots")
def mes_lots(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    # Toujours privilégier les associations explicites UserLot.
    # Évite qu'un profil CS/admin voie "tous les lots" alors qu'il attend ses lots personnels.
    user_lots = session.exec(
        select(UserLot).where(UserLot.user_id == user.id, UserLot.actif == True)
    ).all()
    user_lot_ids = [ul.lot_id for ul in user_lots]

    if user_lot_ids:
        lots = session.exec(select(Lot).where(Lot.id.in_(user_lot_ids))).all()
    elif user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical):
        # Fallback pour comptes d'administration sans association propre.
        lots = session.exec(select(Lot)).all()
    else:
        return []
    return [_lot_read(l) for l in lots]


@router.get("/admin/tous")
def tous_les_lots(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Liste complète de tous les lots (admin/CS)."""
    return [_lot_read(lot) for lot in session.exec(select(Lot)).all()]


@router.get("/{lot_id}")
def get_lot(
    lot_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    lot = session.get(Lot, lot_id)
    if not lot:
        raise HTTPException(404, "Lot introuvable")
    if not user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical):
        user_lot_ids = [ul.lot_id for ul in user.user_lots if ul.actif]
        if lot_id not in user_lot_ids:
            raise HTTPException(403, "Accès refusé")
    return _lot_read(lot)


@router.get("/commandes-acces/mes-commandes")
def mes_commandes(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    stmt = select(CommandeAcces).where(CommandeAcces.user_id == user.id)
    return session.exec(stmt.order_by(CommandeAcces.cree_le.desc())).all()


class CommandeAccesCreate(BaseModel):
    lot_id: int
    type_acces: str
    quantite: int = 1
    motif: str | None = None


@router.post("/commandes-acces", status_code=201)
def creer_commande_acces(
    body: CommandeAccesCreate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    if not user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical):
        user_lot_ids = [ul.lot_id for ul in user.user_lots if ul.actif]
        if body.lot_id not in user_lot_ids:
            raise HTTPException(403, "Vous n'êtes pas associé à ce lot.")
    if body.quantite < 1 or body.quantite > 10:
        raise HTTPException(400, "Quantité invalide (1-10).")
    cmd = CommandeAcces(
        user_id=user.id,
        lot_id=body.lot_id,
        type=body.type_acces,
        quantite=body.quantite,
        motif=body.motif,
    )
    session.add(cmd)
    session.commit()
    session.refresh(cmd)
    return cmd


#  Import staging  endpoints 

@router.post("/admin/imports/upload", status_code=201)
async def upload_import_lots(
    file: UploadFile = File(...),
    remplacer: bool = Query(False),
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Upload un Excel, auto-matche et résout automatiquement les copropriétaires."""
    from app.utils.import_lots import importer_depuis_bytes
    contenu = await file.read()
    stats_import = importer_depuis_bytes(contenu, session=session, remplacer=remplacer)
    #  Rapprocher PUIS résoudre — deux étapes, une écriture chacune (#829).
    #  Ce bloc était recopié dans `auto_match_imports` juste en dessous, et les
    #  deux copies avaient déjà dérivé sur l'affectation du statut.
    rapprocher_imports(session)
    session.flush()
    # Auto-résolution copropriétaires
    stats_resolve = resoudre_imports(session)
    session.commit()
    return {**stats_import, **{"auto_" + k: v for k, v in stats_resolve.items()}}


def _imp_row(imp: LotImport, session: Session) -> dict:
    lot = session.get(Lot, imp.lot_id) if imp.lot_id else None
    bat = session.get(Batiment, imp.batiment_id) if imp.batiment_id else None

    # Libellé bâtiment
    if bat:
        bat_nom = f"Bât. {bat.numero}"
    elif imp.batiment_id:
        bat_nom = str(imp.batiment_id)
    else:
        bat_nom = "P"  # parking sans bâtiment

    # Résoudre chaque utilisateur depuis DB
    utilisateurs_out = []
    for entry in _parse_users(imp.utilisateurs_json):
        uid = entry.get("user_id")
        tl  = entry.get("type_lien", "propriétaire")
        u = session.get(Utilisateur, uid) if uid else None
        utilisateurs_out.append({
            "user_id": uid,
            "type_lien": tl,
            "utilisateur": {"id": u.id, "prenom": u.prenom, "nom": u.nom} if u else None,
        })

    return {
        "id": imp.id,
        "batiment_id": imp.batiment_id,
        "batiment_nom": bat_nom,
        "numero": imp.numero,
        "type_raw": imp.type_raw,
        "etage_raw": imp.etage_raw,
        "no_coproprietaire": imp.no_coproprietaire,
        "nom_coproprietaire": imp.nom_coproprietaire,
        "statut": imp.statut.value if hasattr(imp.statut, "value") else imp.statut,
        "lot_id": imp.lot_id,
        "lot_label": (
            f"Bât. {lot.batiment.numero} — {lot.numero} ({lot.type.value})"
            if lot and lot.batiment else (f"#{imp.lot_id}" if imp.lot_id else None)
        ),
        "utilisateurs": utilisateurs_out,
        "notes_admin": imp.notes_admin,
        "importe_le": imp.importe_le.isoformat() if imp.importe_le else None,
        "resolu_le": imp.resolu_le.isoformat() if imp.resolu_le else None,
    }


@router.get("/admin/imports")
def list_imports(
    statut: Optional[str] = Query(None),
    tri: Optional[str] = Query("copro", description="copro | batiment | numero"),
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    stmt = select(LotImport)
    if statut:
        stmt = stmt.where(LotImport.statut == statut)
    if tri == "batiment":
        stmt = stmt.order_by(LotImport.batiment_id, LotImport.numero)
    elif tri == "numero":
        stmt = stmt.order_by(LotImport.numero)
    else:  # copro (défaut)
        stmt = stmt.order_by(LotImport.nom_coproprietaire, LotImport.no_coproprietaire, LotImport.batiment_id, LotImport.numero)
    imports = session.exec(stmt).all()
    return [_imp_row(imp, session) for imp in imports]


@router.get("/admin/imports/stats")
def stats_imports(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    all_imps = session.exec(select(LotImport)).all()
    return {
        "total":           len(all_imps),
        "en_attente":      sum(1 for x in all_imps if x.statut == StatutLotImport.en_attente),
        "utilisateur_lie": sum(1 for x in all_imps if x.statut == StatutLotImport.utilisateur_lie),
        "lot_lie":         sum(1 for x in all_imps if x.statut == StatutLotImport.lot_lie),
        "resolu":          sum(1 for x in all_imps if x.statut == StatutLotImport.resolu),
        "ignore":          sum(1 for x in all_imps if x.statut == StatutLotImport.ignore),
        "avec_user":       sum(1 for x in all_imps if _parse_users(x.utilisateurs_json)),
    }


class UserLienItem(BaseModel):
    user_id: int
    type_lien: str = "propriétaire"  # propriétaire | locataire


class PatchImport(BaseModel):
    lot_id: Optional[int] = None
    utilisateurs: Optional[list[UserLienItem]] = None   # remplace l'ancien user_id unique
    notes_admin: Optional[str] = None


@router.patch("/admin/imports/{imp_id}")
def patch_import(
    imp_id: int,
    body: PatchImport,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    imp = session.get(LotImport, imp_id)
    if not imp:
        raise HTTPException(404, "Import introuvable")
    if body.lot_id is not None:
        imp.lot_id = body.lot_id or None
    # Capturer les anciens user_ids AVANT mise à jour (pour diff UserLot si résolu)
    old_user_ids: set[int] = {e["user_id"] for e in _parse_users(imp.utilisateurs_json) if e.get("user_id")}
    if body.utilisateurs is not None:
        imp.utilisateurs_json = json.dumps(
            [{"user_id": u.user_id, "type_lien": u.type_lien} for u in body.utilisateurs],
            ensure_ascii=False,
        )
    if body.notes_admin is not None:
        imp.notes_admin = body.notes_admin or None
    # Recalculer le statut
    if imp.statut not in (StatutLotImport.resolu, StatutLotImport.ignore):
        imp.statut = StatutLotImport.lot_lie if imp.lot_id else StatutLotImport.en_attente
    # Si l'import est déjà résolu et qu'un lot est connu, synchroniser les UserLot :
    # - créer les nouveaux liens
    # - supprimer les liens retirés par l'admin
    if imp.statut == StatutLotImport.resolu and imp.lot_id and body.utilisateurs is not None:
        new_entries = _parse_users(imp.utilisateurs_json)
        new_user_ids: set[int] = {e["user_id"] for e in new_entries if e.get("user_id")}
        # Supprimer les UserLot retirés
        for uid_removed in old_user_ids - new_user_ids:
            ul = session.exec(
                select(UserLot).where(UserLot.user_id == uid_removed, UserLot.lot_id == imp.lot_id)
            ).first()
            if ul:
                session.delete(ul)
        # Créer les nouveaux UserLot
        for entry in new_entries:
            uid = entry.get("user_id")
            tl  = _type_lien_from_str(entry.get("type_lien", "propriétaire"))
            if not uid:
                continue
            existing_ul = session.exec(
                select(UserLot).where(UserLot.user_id == uid, UserLot.lot_id == imp.lot_id)
            ).first()
            if not existing_ul:
                session.add(UserLot(user_id=uid, lot_id=imp.lot_id, type_lien=tl, actif=True))
    session.add(imp)
    session.commit()
    session.refresh(imp)
    return _imp_row(imp, session)


@router.post("/admin/imports/{imp_id}/resoudre", status_code=200)
def resoudre_import(
    imp_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    imp = session.get(LotImport, imp_id)
    if not imp:
        raise HTTPException(404, "Import introuvable")
    if imp.statut == StatutLotImport.resolu:
        raise HTTPException(400, "Déjà résolu")

    # 1. Trouver ou créer le Lot
    lot = session.get(Lot, imp.lot_id) if imp.lot_id else None
    if not lot:
        if imp.batiment_id:
            # Lot résidentiel/cave : chercher par batiment_id + numero
            lot = session.exec(
                select(Lot).where(Lot.batiment_id == imp.batiment_id, Lot.numero == imp.numero)
            ).first()
        else:
            # Parking (batiment_id=None) : chercher par numero parmi les lots de type parking
            lot = session.exec(
                select(Lot).where(Lot.batiment_id.is_(None), Lot.numero == imp.numero)  # type: ignore
            ).first()
    if not lot:
        # Créer le Lot (parking autorisé avec batiment_id=None)
        lot_type, type_app = type_de_lot(imp.type_raw)
        lot = Lot(
            batiment_id=imp.batiment_id,  # None pour parking
            numero=imp.numero,
            type=lot_type,
            type_appartement=type_app,
            etage=etage_de_lot(imp.etage_raw),
        )
        session.add(lot)
        session.flush()
    imp.lot_id = lot.id

    # 2. Créer les UserLot pour chaque utilisateur lié
    for entry in _parse_users(imp.utilisateurs_json):
        uid = entry.get("user_id")
        tl  = _type_lien_from_str(entry.get("type_lien", "propriétaire"))
        if not uid:
            continue
        existing_ul = session.exec(
            select(UserLot).where(
                UserLot.user_id == uid,
                UserLot.lot_id == lot.id,
            )
        ).first()
        if not existing_ul:
            session.add(UserLot(
                user_id=uid,
                lot_id=lot.id,
                type_lien=tl,
                actif=True,
            ))
    session.flush()

    imp.statut = StatutLotImport.resolu
    imp.resolu_le = datetime.utcnow()
    session.add(imp)
    session.commit()
    return {"ok": True, "lot_id": lot.id, "nb_liens": len(_parse_users(imp.utilisateurs_json))}


@router.post("/admin/imports/{imp_id}/ignorer", status_code=200)
def ignorer_import(
    imp_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    imp = session.get(LotImport, imp_id)
    if not imp:
        raise HTTPException(404, "Import introuvable")
    imp.statut = StatutLotImport.ignore
    session.add(imp)
    session.commit()
    return {"ok": True}


#  🔴 `_auto_resoudre_proprietaires_batch` vit dans `utils/resolution_lots`
#  depuis #829. Cette copie-ci sautait tout import dont un occupant était
#  locataire, et posait les `UserLot` SANS revalider le nom — l'autre voie
#  faisait l'inverse des deux. Le résultat dépendait du bouton employé.


@router.post("/admin/imports/auto-resoudre", status_code=200)
def auto_resoudre_imports(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Résout automatiquement tous les imports copropriétaires matchés (lot + user liés)."""
    stats = resoudre_imports(session)
    #  Le module ne committe pas : c'est l'appelant qui décide de la portée
    #  de sa transaction, et ici l'endpoint se termine.
    session.commit()
    return stats


@router.post("/admin/imports/auto-match", status_code=200)
def auto_match_imports(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Tente de lier automatiquement les LotImport aux Lot et Utilisateur existants.
    Utilise l'algorithme robuste de matching (accents, tirets, noms composés, bigrammes)."""
    matches = rapprocher_imports(session)
    session.commit()
    return {"matches": matches}
