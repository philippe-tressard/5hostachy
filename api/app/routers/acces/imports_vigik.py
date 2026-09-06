"""L'import Excel des badges Vigik, et son appariement.

Jumeau de `imports_telecommandes` — voir la note qui s'y trouve sur ce qui est
partagé et ce qui ne l'est pas.
"""
from datetime import datetime

from fastapi import (
    APIRouter, Depends, File, HTTPException, Query, UploadFile,
)
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import (
    StatutAcces, StatutImport,
    Utilisateur, Vigik, VigikImport,
)
from app.utils.auto_match_service import (
    _user_keys, _matches_user, _create_user_vigiks, rattacher_lot_unique,
)

from .commun import (
    _ignorer_import, _lister_imports, _remettre_en_attente_import, _stats_socle,
)

router = APIRouter()




router = APIRouter()

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
    lignes, stats = _stats_socle(VigikImport, session)
    stats["avec_code"] = sum(1 for i in lignes if i.code)
    stats["avec_lot"] = sum(1 for i in lignes if i.lot_id)
    return stats


@router.get("/admin/imports-vigik")
def list_imports_vigik(
    statut: str = Query(None),
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Liste les imports vigik, optionnellement filtrés par statut."""
    return _lister_imports(VigikImport, statut, session)


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

        #  La règle du lot unique vit dans `rattacher_lot_unique` — elle était
        #  écrite quatre fois, avec deux comportements différents.
        if rattacher_lot_unique(imp, session):
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


@router.post("/admin/imports-vigik/{import_id}/remettre-en-attente")
def remettre_en_attente_import_vigik(
    import_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Remet un import vigik ignoré en 'en attente' — absent jusqu'à #576."""
    return _remettre_en_attente_import(VigikImport, import_id, session)


@router.post("/admin/imports-vigik/{import_id}/ignorer")
def ignorer_import_vigik(
    import_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Marque un import vigik comme ignoré."""
    return _ignorer_import(VigikImport, import_id, session)
