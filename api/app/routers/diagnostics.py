"""Router diagnostics réglementaires — types + rapports avec upload."""
import os
import re
import shutil
import uuid
from datetime import datetime, date as dateclass
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_cs_or_admin
from app.database import get_session
from app.models.core import DiagnosticRapport, DiagnosticType, Utilisateur

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])

UPLOADS_DIR = os.getenv("UPLOADS_DIR", "/app/uploads")


# ── Schémas ────────────────────────────────────────────────────────────────

class RapportRead(BaseModel):
    id: int
    diagnostic_type_id: int
    titre: str
    date_rapport: Optional[dateclass] = None
    fichier_nom: str
    taille_octets: Optional[int] = None
    mime_type: str
    synthese: Optional[str] = None
    publie_le: datetime

    class Config:
        from_attributes = True


class DiagnosticTypeRead(BaseModel):
    id: int
    code: str
    nom: str
    texte_legislatif: str
    frequence: Optional[str] = None
    ordre: int
    non_applicable: bool = False
    rapports: list[RapportRead] = []

    class Config:
        from_attributes = True


class DiagnosticTypeNonApplicableUpdate(BaseModel):
    non_applicable: bool


class RapportUpdate(BaseModel):
    titre: Optional[str] = None
    date_rapport: Optional[str] = None  # ISO date string ou null
    synthese: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("/types", response_model=list[DiagnosticTypeRead])
def list_types(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(get_current_user),
):
    types = session.exec(
        select(DiagnosticType)
        .where(DiagnosticType.actif == True)
        .order_by(DiagnosticType.ordre)
    ).all()
    result = []
    for t in types:
        rapports = session.exec(
            select(DiagnosticRapport)
            .where(DiagnosticRapport.diagnostic_type_id == t.id)
            .order_by(DiagnosticRapport.date_rapport.desc().nullslast(), DiagnosticRapport.publie_le.desc())
        ).all()
        result.append(DiagnosticTypeRead(
            id=t.id,
            code=t.code,
            nom=t.nom,
            texte_legislatif=t.texte_legislatif,
            frequence=t.frequence,
            ordre=t.ordre,
            non_applicable=t.non_applicable,
            rapports=[RapportRead.model_validate(r) for r in rapports],
        ))
    return result


@router.patch("/types/{type_id}/non-applicable", response_model=DiagnosticTypeRead)
def toggle_non_applicable(
    type_id: int,
    body: DiagnosticTypeNonApplicableUpdate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    diag_type = session.get(DiagnosticType, type_id)
    if not diag_type:
        raise HTTPException(404, "Type de diagnostic introuvable")
    diag_type.non_applicable = body.non_applicable
    session.add(diag_type)
    session.commit()
    session.refresh(diag_type)
    rapports = session.exec(
        select(DiagnosticRapport)
        .where(DiagnosticRapport.diagnostic_type_id == diag_type.id)
        .order_by(DiagnosticRapport.date_rapport.desc().nullslast(), DiagnosticRapport.publie_le.desc())
    ).all()
    return DiagnosticTypeRead(
        id=diag_type.id,
        code=diag_type.code,
        nom=diag_type.nom,
        texte_legislatif=diag_type.texte_legislatif,
        frequence=diag_type.frequence,
        ordre=diag_type.ordre,
        non_applicable=diag_type.non_applicable,
        rapports=[RapportRead.model_validate(r) for r in rapports],
    )


@router.post("/types/{type_id}/rapports", response_model=RapportRead, status_code=201)
async def upload_rapport(
    type_id: int,
    titre: str = Form(...),
    date_rapport: str | None = Form(None),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    diag_type = session.get(DiagnosticType, type_id)
    if not diag_type:
        raise HTTPException(404, "Type de diagnostic introuvable")

    os.makedirs(UPLOADS_DIR, exist_ok=True)
    raw_name = os.path.basename(file.filename or "rapport")
    safe_name = re.sub(r"[^\w.\-]", "_", raw_name)[:200] or "rapport"
    dest = os.path.join(UPLOADS_DIR, f"{uuid.uuid4().hex}_{safe_name}")
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    parsed_date = None
    if date_rapport:
        try:
            parsed_date = dateclass.fromisoformat(date_rapport)
        except ValueError:
            pass

    rapport = DiagnosticRapport(
        diagnostic_type_id=type_id,
        titre=titre,
        date_rapport=parsed_date,
        fichier_nom=file.filename or safe_name,
        fichier_chemin=dest,
        taille_octets=os.path.getsize(dest),
        mime_type=file.content_type or "application/octet-stream",
        publie_par_id=user.id,
        publie_le=datetime.utcnow(),
    )
    session.add(rapport)
    session.commit()
    session.refresh(rapport)
    return rapport


@router.patch("/rapports/{rapport_id}", response_model=RapportRead)
def update_rapport(
    rapport_id: int,
    body: RapportUpdate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    rapport = session.get(DiagnosticRapport, rapport_id)
    if not rapport:
        raise HTTPException(404, "Rapport introuvable")
    if body.titre is not None:
        rapport.titre = body.titre
    if body.date_rapport is not None:
        try:
            rapport.date_rapport = dateclass.fromisoformat(body.date_rapport) if body.date_rapport else None
        except ValueError:
            pass
    elif body.date_rapport == "":
        rapport.date_rapport = None
    if "synthese" in body.model_fields_set:
        rapport.synthese = body.synthese or None
    session.add(rapport)
    session.commit()
    session.refresh(rapport)
    return rapport


@router.delete("/rapports/{rapport_id}", status_code=204)
def delete_rapport(
    rapport_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    rapport = session.get(DiagnosticRapport, rapport_id)
    if not rapport:
        raise HTTPException(404, "Rapport introuvable")
    # Supprime le fichier physique
    if os.path.exists(rapport.fichier_chemin):
        os.remove(rapport.fichier_chemin)
    session.delete(rapport)
    session.commit()


@router.get("/rapports/{rapport_id}/télécharger")
def download_rapport(
    rapport_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(get_current_user),
):
    rapport = session.get(DiagnosticRapport, rapport_id)
    if not rapport:
        raise HTTPException(404, "Rapport introuvable")
    if not os.path.exists(rapport.fichier_chemin):
        raise HTTPException(404, "Fichier introuvable sur le serveur")
    return FileResponse(rapport.fichier_chemin, filename=rapport.fichier_nom, media_type=rapport.mime_type)
