"""Router documents — bibliothèque documentaire avec contrôle d'accès 3 couches."""
import json
import os
import re
import shutil
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_cs_or_admin
from app.database import get_session
from app.models.core import (
    Batiment, CategorieDocument, Document, ProfilAccesDocument,
    Utilisateur, UserLot, RoleUtilisateur, StatutUtilisateur
)
from app.schemas import DocumentRead

router = APIRouter(prefix="/documents", tags=["documents"])

UPLOADS_DIR = os.getenv("UPLOADS_DIR", "/app/uploads")


def _user_can_read(user: Utilisateur, doc: Document, session: Session) -> bool:
    """
    Algorithme d'accès en 5 étapes (specs modele-donnees.md).
    Retourne True si l'utilisateur a le droit de lire ce document.
    """
    # Admin et CS voient tout
    if user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical):
        return True

    # Documents liés à un contrat (sans catégorie) : CS/admin uniquement
    if doc.contrat_id and not doc.categorie_id:
        return False

    profil_id = doc.profil_acces_override_id or doc.categorie.profil_acces_id
    profil: ProfilAccesDocument = session.get(ProfilAccesDocument, profil_id)
    if not profil:
        return False

    # Vérifier le rôle (supporte valeurs de rôles ET de statuts pour compatibilité)
    roles_autorises = json.loads(profil.roles_autorises)
    user_idents = set(user.roles) | {user.statut.value}
    if not any(r in roles_autorises for r in user_idents):
        return False

    # Vérifier le périmètre
    if doc.perimetre == "bâtiment" and doc.batiment_id:
        user_batiments = {
            ul.lot.batiment_id for ul in user.user_lots if ul.actif and ul.lot
        }
        if doc.batiment_id not in user_batiments:
            return False

    if doc.perimetre == "lot" and doc.lot_id:
        user_lots = {ul.lot_id for ul in user.user_lots if ul.actif}
        if doc.lot_id not in user_lots:
            return False

    return True


@router.get("/categories")
def list_categories(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Retourne les catégories de documents actives accessibles à l'utilisateur."""
    cats = session.exec(select(CategorieDocument).where(CategorieDocument.actif == True).order_by(CategorieDocument.libelle)).all()
    # CS et admin voient toutes les catégories
    if user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical):
        return [{"id": c.id, "code": c.code, "libelle": c.libelle} for c in cats]
    # Pour les autres : ne retourner que les catégories dont le profil d'accès autorise le rôle
    user_idents = set(user.roles) | {user.statut.value}
    result = []
    for c in cats:
        profil = session.get(ProfilAccesDocument, c.profil_acces_id)
        if profil:
            roles_autorises = json.loads(profil.roles_autorises)
            if any(r in roles_autorises for r in user_idents):
                result.append({"id": c.id, "code": c.code, "libelle": c.libelle})
    return result


@router.get("", response_model=list[DocumentRead])
def list_documents(
    categorie_id: int | None = None,
    contrat_id: int | None = None,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    stmt = select(Document)
    if categorie_id:
        stmt = stmt.where(Document.categorie_id == categorie_id)
    if contrat_id:
        stmt = stmt.where(Document.contrat_id == contrat_id)

    docs = session.exec(stmt.order_by(Document.publie_le.desc())).all()

    # Filtrage côté serveur selon profil d'accès
    if not user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical):
        docs = [d for d in docs if _user_can_read(user, d, session)]

    return docs


@router.get("/{doc_id}/télécharger")
def download_document(
    doc_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document introuvable")
    if not _user_can_read(user, doc, session):
        raise HTTPException(403, "Accès refusé")
    if not os.path.exists(doc.fichier_chemin):
        raise HTTPException(404, "Fichier introuvable sur le serveur")
    return FileResponse(doc.fichier_chemin, filename=doc.fichier_nom, media_type=doc.mime_type)


class DocumentUpdate(BaseModel):
    titre: Optional[str] = None
    annee: Optional[int] = None
    date_ag: Optional[str] = None  # ISO date string


@router.patch("/{doc_id}", response_model=DocumentRead)
def update_document(
    doc_id: int,
    body: DocumentUpdate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document introuvable")
    if body.titre is not None:
        doc.titre = body.titre
    if body.annee is not None:
        doc.annee = body.annee
    if body.date_ag is not None:
        from datetime import date as dateclass
        doc.date_ag = dateclass.fromisoformat(body.date_ag) if body.date_ag else None
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


@router.post("", response_model=DocumentRead, status_code=201)
async def upload_document(
    titre: str = Form(...),
    categorie_id: int | None = Form(None),
    contrat_id: int | None = Form(None),
    perimetre: str = Form("résidence"),
    batiment_id: int | None = Form(None),
    lot_id: int | None = Form(None),
    annee: int | None = Form(None),
    date_ag: str | None = Form(None),
    batiments_ids_json: str | None = Form(None),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    if not categorie_id and not contrat_id:
        raise HTTPException(400, "categorie_id ou contrat_id obligatoire")

    if categorie_id:
        categorie = session.get(CategorieDocument, categorie_id)
        if not categorie or not categorie.actif:
            raise HTTPException(400, "Catégorie invalide")

    os.makedirs(UPLOADS_DIR, exist_ok=True)
    # Sanitize filename to prevent path traversal attacks
    raw_name = os.path.basename(file.filename or "document")
    safe_name = re.sub(r"[^\w.\-]", "_", raw_name)[:200] or "document"
    dest = os.path.join(UPLOADS_DIR, f"{uuid.uuid4().hex}_{safe_name}")
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    size = os.path.getsize(dest)

    parsed_date_ag = None
    if date_ag:
        from datetime import date as dateclass
        try:
            parsed_date_ag = dateclass.fromisoformat(date_ag)
        except ValueError:
            pass

    doc = Document(
        titre=titre,
        fichier_nom=file.filename,
        fichier_chemin=dest,
        taille_octets=size,
        mime_type=file.content_type or "application/octet-stream",
        categorie_id=categorie_id,
        contrat_id=contrat_id,
        perimetre=perimetre,
        batiment_id=batiment_id,
        lot_id=lot_id,
        publie_par_id=user.id,
        annee=annee,
        date_ag=parsed_date_ag,
        batiments_ids_json=batiments_ids_json,
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


@router.delete("/{doc_id}", status_code=204)
def delete_document(
    doc_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document introuvable")
    if os.path.exists(doc.fichier_chemin):
        os.remove(doc.fichier_chemin)
    session.delete(doc)
    session.commit()
