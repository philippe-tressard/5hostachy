"""Router documents — bibliothèque documentaire avec contrôle d'accès 3 couches."""
import json
import os
import shutil
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
    Utilisateur, RoleUtilisateur
)
from app.schemas import DocumentRead
from app.utils.fichiers import extension_assainie, nom_stocke
# Toute règle de visibilité — documents compris — vient du module central.
from app.utils.visibility import document_visible

router = APIRouter(prefix="/documents", tags=["documents"])

UPLOADS_DIR = os.getenv("UPLOADS_DIR", "/app/uploads")


# La règle d'accès aux documents est `document_visible` (app/utils/visibility.py),
# avec toutes les autres règles de visibilité. Ce router l'appelle, il ne la redéfinit
# pas et ne l'aliase pas : un seul nom, un seul endroit.


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
    publication_id: int | None = None,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    stmt = select(Document)
    if categorie_id:
        stmt = stmt.where(Document.categorie_id == categorie_id)
    if contrat_id:
        stmt = stmt.where(Document.contrat_id == contrat_id)
    if publication_id:
        stmt = stmt.where(Document.publication_id == publication_id)

    docs = session.exec(stmt.order_by(Document.publie_le.desc())).all()

    # Filtrage côté serveur selon profil d'accès
    if not user.has_role(RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical):
        docs = [d for d in docs if document_visible(user, d, session)]

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
    if not document_visible(user, doc, session):
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
    publication_id: int | None = Form(None),
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
    if not categorie_id and not contrat_id and not publication_id:
        raise HTTPException(400, "categorie_id, contrat_id ou publication_id obligatoire")

    if categorie_id:
        categorie = session.get(CategorieDocument, categorie_id)
        if not categorie or not categorie.actif:
            raise HTTPException(400, "Catégorie invalide")

    os.makedirs(UPLOADS_DIR, exist_ok=True)
    # Assainissement et préfixe UUID : app/utils/fichiers.py, seul endroit où
    # cette règle est écrite. Le téléchargement passe par un endpoint
    # authentifié qui impose lui-même le `media_type`, l'extension d'origine
    # peut donc être conservée telle quelle.
    raw_name = file.filename or "document"
    dest = os.path.join(UPLOADS_DIR, nom_stocke(raw_name, extension_assainie(raw_name)))
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
        publication_id=publication_id,
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
