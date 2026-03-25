"""
Router uploads — gestion des photos (avatar, résidence, publications).
Les fichiers sont enregistrés dans /app/uploads/{type}/{uuid}.ext
et servis en statique via /uploads/*.
"""
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from PIL import Image
import io

from app.auth.deps import get_current_user, require_cs_or_admin
from app.database import get_session
from app.models.core import Copropriete, Publication, Utilisateur
from sqlmodel import Session, select

router = APIRouter(prefix="/uploads", tags=["uploads"])

UPLOADS_ROOT = Path("/app/uploads")
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_SIZE_MB = 5

# ── helpers ────────────────────────────────────────────────────────────────

def _save_image(file: UploadFile, subfolder: str, max_dim: int = 1600) -> str:
    """Valide, redimensionne si besoin et sauvegarde le fichier. Retourne l'URL relative."""
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(400, f"Format non supporté : {file.content_type}. Utilisez JPEG, PNG ou WebP.")

    data = file.file.read()
    if len(data) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(413, f"Fichier trop volumineux (max {MAX_SIZE_MB} Mo).")

    # Redimensionnement via Pillow si nécessaire
    try:
        img = Image.open(io.BytesIO(data))
        img = img.convert("RGB")
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim), Image.LANCZOS)
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=85, optimize=True)
        data = output.getvalue()
    except Exception:
        raise HTTPException(400, "Impossible de lire l'image.")

    dest_dir = UPLOADS_ROOT / subfolder
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.jpg"
    (dest_dir / filename).write_bytes(data)
    return f"/uploads/{subfolder}/{filename}"


# ── endpoints ──────────────────────────────────────────────────────────────

@router.post("/avatar", summary="Mettre à jour la photo de profil")
def upload_avatar(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Upload et sauvegarde la photo de profil de l'utilisateur connecté."""
    url = _save_image(file, "avatars", max_dim=400)
    user.photo_url = url
    session.add(user)
    session.commit()
    return {"url": url}


@router.post("/residence", summary="Ajouter une photo de la résidence (CS/Admin)")
def upload_residence(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Upload une photo de la résidence. Retourne l'URL publique."""
    url = _save_image(file, "residence", max_dim=1600)
    # Enregistre la dernière photo dans la table copropriete
    copro = session.exec(select(Copropriete)).first()
    if copro:
        copro.photo_url = url  # type: ignore[attr-defined]
        session.add(copro)
        session.commit()
    return {"url": url}


@router.post("/publication/{pub_id}", summary="Ajouter une image à une publication (CS/Admin)")
def upload_publication_image(
    pub_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Attache une image à une publication existante."""
    pub = session.get(Publication, pub_id)
    if not pub:
        raise HTTPException(404, "Publication introuvable")
    url = _save_image(file, "publications", max_dim=1200)
    pub.image_url = url  # type: ignore[attr-defined]
    session.add(pub)
    session.commit()
    return {"url": url}
