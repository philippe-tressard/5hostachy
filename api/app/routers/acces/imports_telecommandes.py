"""L'import Excel des télécommandes de parking, et son appariement.

Le fichier du prestataire arrive en STAGING (`TelecommandeImport`), puis chaque
ligne est rapprochée d'un lot et d'un compte — automatiquement quand le nom
concorde, à la main sinon. La résolution crée la `Telecommande` réelle.

⚠️ Ce module ne porte plus **que** les chemins d'URL et ce qui lui est propre. Le
cycle lui-même — appariement, correction, résolution — vit dans `socle_imports`,
avec le récit de ce qu'il a coûté d'en avoir eu deux copies (#847).
"""
from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel
from sqlmodel import Session

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import (
    Telecommande,
    TelecommandeImport,
    Utilisateur,
)
from app.utils.auto_match_service import _create_user_telecommandes

from .commun import (
    _ignorer_import,
    _lister_imports,
    _remettre_en_attente_import,
    _stats_socle,
)
from . import socle_imports
from .socle_imports import PatchImportBody, TypeImportAcces

router = APIRouter()

#: La chaîne « télécommande », décrite par ses seules différences.
TELECOMMANDE = TypeImportAcces(
    libelle="télécommande",
    modele_import=TelecommandeImport,
    modele_objet=Telecommande,
    champ_reference="reference",
    champ_lien="telecommande_id",
    creer_liaisons=_create_user_telecommandes,
)

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
    return importer_depuis_bytes(contenu, session=session, remplacer=remplacer)


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
    """Apparie les imports en attente aux comptes inscrits.

    Aucune étape supplémentaire : le fichier des télécommandes ne porte ni
    bâtiment ni appartement, le lot ne peut donc venir que de `rattacher_lot_unique`.
    """
    return socle_imports.auto_match(TELECOMMANDE, session)


@router.patch("/admin/imports/{import_id}")
def patch_import(
    import_id: int,
    body: PatchImportBody,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Met à jour les liaisons d'un import (utilisateurs, lot, possession).
    Fonctionne même si l'import est déjà résolu (correction après coup)."""
    return socle_imports.patch(TELECOMMANDE, import_id, body, session)


@router.post("/admin/imports/{import_id}/resoudre")
def resoudre_import(
    import_id: int,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_cs_or_admin),
):
    """Résout un import : crée la Telecommande réelle et lie l'utilisateur.

    La télécommande est affectée au locataire si `chez_locataire`, sinon au
    propriétaire. Les copropriétaires du même lot sont associés via
    `UserTelecommande`.
    """
    return socle_imports.resoudre(TELECOMMANDE, import_id, session)


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
    """Le locataire a refusé la télécommande — elle reste/revient chez le propriétaire.

    ⚠️ Propre aux télécommandes : elles se remettent en main propre, et le refus
    est un geste du quotidien. L'asymétrie est déclarée dans
    `test_symetrie_imports_acces.py`.

    Il passe par `socle_imports.patch` et non par une écriture directe : sur un
    import DÉJÀ RÉSOLU, le refus doit redescendre sur la télécommande elle-même,
    sinon l'objet continue d'affirmer qu'elle est chez le locataire. La réponse,
    elle, garde sa forme d'origine — c'est un contrat, pas un détail.
    """
    socle_imports.patch(
        TELECOMMANDE, import_id, PatchImportBody(refuse_par_locataire=True), session
    )
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
