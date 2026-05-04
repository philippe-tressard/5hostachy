"""
Router uploads — gestion des photos (avatar, résidence, publications).
Les fichiers sont enregistrés dans /app/uploads/{type}/{uuid}.ext
et servis en statique via /uploads/*.
"""
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from PIL import Image, ImageOps
import io

from app.auth.deps import get_current_user, require_cs_or_admin
from app.database import get_session
from app.models.core import Copropriete, Publication, Ticket, Utilisateur
from sqlmodel import Session, select

router = APIRouter(prefix="/uploads", tags=["uploads"])

UPLOADS_ROOT = Path("/app/uploads")
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_SIZE_MB = 5

ALLOWED_DOC_MIME = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
DOC_EXTENSIONS = {
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
}
MAX_DOC_SIZE_MB = 15

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
        img = ImageOps.exif_transpose(img) or img  # Corriger l'orientation AVANT convert
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


@router.post("/ticket/{ticket_id}", summary="Ajouter une photo à un ticket")
def upload_ticket_photo(
    ticket_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Ajoute une photo à un ticket existant (max 5)."""
    import json

    ticket = session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket introuvable")

    # Parse existing photos
    photos: list[str] = []
    if ticket.photos_urls:
        try:
            photos = json.loads(ticket.photos_urls)
        except Exception:
            photos = []

    if len(photos) >= 5:
        raise HTTPException(400, "Maximum 5 photos par ticket.")

    url = _save_image(file, "tickets", max_dim=1200)
    photos.append(url)
    ticket.photos_urls = json.dumps(photos)
    session.add(ticket)
    session.commit()
    return {"url": url, "photos_urls": photos}


@router.post("/fichier", summary="Upload un fichier (photo ou document) pour commentaire")
def upload_fichier(
    file: UploadFile = File(...),
    user: Utilisateur = Depends(get_current_user),
):
    """
    Upload une photo ou un document (PDF, Word, Excel) destiné à être joint
    à un commentaire d'actualité ou de ticket.
    - Images : redimensionnées à 1200px max, converties en JPEG
    - Documents : stockés tels quels, max 15 Mo
    Retourne { url, nom, type }
    """
    is_image = file.content_type in ALLOWED_MIME
    is_doc = file.content_type in ALLOWED_DOC_MIME

    if not is_image and not is_doc:
        raise HTTPException(
            400,
            f"Format non supporté : {file.content_type}. "
            "Utilisez JPEG, PNG, WebP pour les photos ou PDF, Word, Excel pour les documents."
        )

    original_name = file.filename or "fichier"

    if is_image:
        url = _save_image(file, "fichiers", max_dim=1200)
        ext = "jpg"
        ftype = "image"
    else:
        data = file.file.read()
        if len(data) > MAX_DOC_SIZE_MB * 1024 * 1024:
            raise HTTPException(413, f"Fichier trop volumineux (max {MAX_DOC_SIZE_MB} Mo).")
        ext_map = DOC_EXTENSIONS.get(file.content_type, ".bin")
        dest_dir = UPLOADS_ROOT / "fichiers"
        dest_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid.uuid4().hex}{ext_map}"
        (dest_dir / filename).write_bytes(data)
        url = f"/uploads/fichiers/{filename}"
        ext = ext_map.lstrip(".")
        ftype = "document"

    return {"url": url, "nom": original_name, "type": ftype}
