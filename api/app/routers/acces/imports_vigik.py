"""L'import Excel des badges Vigik, et son appariement.

Jumeau de `imports_telecommandes`. Le CYCLE des deux est écrit une seule fois
dans `socle_imports` — voir son en-tête, et le défaut de possession qui a prouvé
que ce n'étaient pas deux ressemblances de hasard (#847).

Ce qui reste ici et **nulle part ailleurs** : la résolution du lot par
`batiment_raw` + `appartement_raw`. Le fichier Vigik porte ces deux colonnes, le
fichier des télécommandes ne les a pas.
"""
from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlmodel import Session

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import Utilisateur, Vigik, VigikImport
from app.utils.auto_match_service import _create_user_vigiks

from .commun import (
    _ignorer_import,
    _lister_imports,
    _remettre_en_attente_import,
    _stats_socle,
)
from . import socle_imports
from .socle_imports import PatchImportBody, TypeImportAcces

router = APIRouter()

#: La chaîne « badge Vigik », décrite par ses seules différences.
VIGIK = TypeImportAcces(
    libelle="badge Vigik",
    modele_import=VigikImport,
    modele_objet=Vigik,
    champ_reference="code",
    champ_lien="vigik_id",
    creer_liaisons=_create_user_vigiks,
)

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
    return importer_depuis_bytes(contenu, session=session, remplacer=remplacer)


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


def _etape_lot_par_adresse(session: Session):
    """Le lot déduit du bâtiment et de l'appartement écrits dans l'Excel.

    🔴 **La seule chose que le Vigik fait et que la télécommande ne peut pas
    faire.** C'est ce qui justifie le crochet `etape_supplementaire` du socle
    plutôt qu'un `if type == "vigik"` en son sein : une différence réelle
    s'exprime là où elle est vraie.

    ⚠️ L'index est construit **une fois**, en dehors de la boucle, et c'est
    pourquoi cette fonction rend une fermeture plutôt que d'être l'étape
    elle-même : `_build_lot_index` lit TOUS les bâtiments et TOUS les lots. Le
    rappeler par ligne d'import rendrait l'appariement quadratique — le code
    d'origine le construisait déjà une fois, et une mise en commun n'a pas le
    droit de coûter plus cher que ce qu'elle remplace.
    """
    from app.utils.import_vigiks import _build_lot_index, normaliser

    index = _build_lot_index(session)

    def etape(imp, _session: Session) -> bool:
        if imp.lot_id or not imp.batiment_raw or not imp.appartement_raw:
            return False
        lot_id = index.get((normaliser(imp.batiment_raw), normaliser(imp.appartement_raw)))
        if not lot_id:
            return False
        imp.lot_id = lot_id
        return True

    return etape


@router.post("/admin/imports-vigik/auto-match")
def auto_match_imports_vigik(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Apparie les imports vigik en attente aux comptes inscrits."""
    return socle_imports.auto_match(
        VIGIK, session, etape_supplementaire=_etape_lot_par_adresse(session)
    )


@router.patch("/admin/imports-vigik/{import_id}")
def patch_import_vigik(
    import_id: int,
    body: PatchImportBody,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Met à jour les liaisons d'un import vigik.
    Fonctionne même si l'import est déjà résolu (correction après coup)."""
    return socle_imports.patch(VIGIK, import_id, body, session)


@router.post("/admin/imports-vigik/{import_id}/resoudre")
def resoudre_import_vigik(
    import_id: int,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_cs_or_admin),
):
    """Résout un import vigik : crée le Vigik réel et lie l'utilisateur.
    Les copropriétaires du même lot sont automatiquement associés via UserVigik."""
    return socle_imports.resoudre(VIGIK, import_id, session)


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
