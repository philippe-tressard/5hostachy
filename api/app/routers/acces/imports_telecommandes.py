"""L'import Excel des télécommandes de parking, et son appariement.

Le fichier du prestataire arrive en STAGING (`TelecommandeImport`), puis chaque
ligne est rapprochée d'un lot et d'un compte — automatiquement quand le nom
concorde, à la main sinon. La résolution crée la `Telecommande` réelle.

⚠️ Ce module et son jumeau `imports_vigik` se ressemblent beaucoup et ne sont
PAS fusionnés : les deux fichiers sources n'ont ni les mêmes colonnes ni les
mêmes règles d'appariement (le vigik porte un code, la télécommande un numéro de
série et un badge chez le locataire). Ce qu'ils partagent vraiment — la
normalisation des noms — est dans `commun`.
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
    Telecommande, TelecommandeImport, Utilisateur,
)
from app.utils.auto_match_service import (
    _user_keys, _matches_user, _create_user_telecommandes,
    rattacher_lot_unique,
)

from .commun import (
    _ignorer_import, _lister_imports, _remettre_en_attente_import, _stats_socle,
)

router = APIRouter()




router = APIRouter()

# ── Import Excel télécommandes ──────────────────────────────────────────────



@router.post("/admin/imports/upload", status_code=201)
async def upload_import_excel(
    file: UploadFile = File(...),
    remplacer: bool = Query(False, description="Supprimer les imports en_attente avant ré-import"),
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Upload un fichier Excel et importe les télécommandes dans la table de staging."""
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
    return _lister_imports(TelecommandeImport, statut, session)


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


#  Lister les imports d'un type, avec leurs liaisons résolues. Les deux corps
#  étaient IDENTIQUES au modèle près — vérifié ligne à ligne avant extraction,
#  jamais supposé (#576).

#  ── Les gestes de STATUT d'un import, écrits UNE fois (#576) ────────────────
#  Deux tables, un seul CYCLE. Écrits deux fois, ils ont produit le défaut de
#  #576 : `remettre-en-attente` n'existait que côté télécommandes, et un import
#  Vigik ignoré par erreur était définitivement perdu. Écrits une fois, la
#  symétrie est STRUCTURELLE ; `test_symetrie_imports_acces.py` garde le reste.

@router.post("/admin/imports/{import_id}/ignorer")
def ignorer_import(
    import_id: int,
    body: BaseModel = None,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Marque un import comme ignoré (accès non-résidentiel, doublon, etc.)."""
    return _ignorer_import(TelecommandeImport, import_id, session)


@router.post("/admin/imports/{import_id}/remettre-en-attente")
def remettre_en_attente_import(
    import_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Remet un import ignoré en statut 'en attente' pour traitement ultérieur."""
    return _remettre_en_attente_import(TelecommandeImport, import_id, session)


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
    lignes, stats = _stats_socle(TelecommandeImport, session)
    stats["avec_reference"] = sum(1 for i in lignes if i.reference)
    return stats
