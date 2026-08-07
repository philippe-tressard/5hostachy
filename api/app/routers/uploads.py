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
from app.models.core import Copropriete, Publication, Utilisateur
from app.utils.fichiers import nom_stocke
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
    #  Le nom passe par `nom_stocke`, comme toute autre pièce jointe. Il était
    #  fabriqué ici à la main — `f"{uuid4().hex}.jpg"`, sans radical — alors que
    #  `app/utils/fichiers.py` annonce en tête « écrit une seule fois ». Il l'était
    #  deux fois, et la seconde perdait le nom d'origine : une photo arrivait dans
    #  l'e-mail sous « fb6cb1df94734926bfcd9b7f07e99ded.jpg », là où un PDF joint au
    #  même message s'affichait « Devis-toiture.pdf ». Signalé sur un e-mail réel le
    #  07/08/2026. L'image est réencodée en JPEG, d'où l'extension forcée — mais le
    #  radical du fichier d'origine, lui, n'a aucune raison d'être jeté.
    filename = nom_stocke(file.filename, ".jpg")
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


# Les endpoints `/ticket/{id}` et `/evenement/{id}` ont été supprimés le
# 03/08/2026 avec les pièces jointes documentaires : les formulaires de création
# téléversent désormais photos ET documents par `/fichier`, avant que l'élément
# existe, et passent les URLs dans le payload de création. C'est ce qui permet à
# l'e-mail syndic/CS de partir avec ses pièces jointes — l'ancien flux
# « créer puis téléverser » construisait l'e-mail avant les photos.


@router.post("/fichier", summary="Upload une pièce jointe (photo ou document)")
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
        ftype = "image"
    else:
        data = file.file.read()
        if len(data) > MAX_DOC_SIZE_MB * 1024 * 1024:
            raise HTTPException(413, f"Fichier trop volumineux (max {MAX_DOC_SIZE_MB} Mo).")
        # L'extension vient de la liste blanche de types MIME, JAMAIS du nom
        # fourni : `/app/uploads` est servi en statique et Caddy pose le
        # `Content-Type` d'après l'extension du fichier sur disque. Un `.html`
        # téléversé sous un type MIME autorisé s'exécuterait sur notre origine.
        ext_map = DOC_EXTENSIONS.get(file.content_type, ".bin")
        dest_dir = UPLOADS_ROOT / "fichiers"
        dest_dir.mkdir(parents=True, exist_ok=True)
        filename = nom_stocke(original_name, ext_map)
        (dest_dir / filename).write_bytes(data)
        url = f"/uploads/fichiers/{filename}"
        ftype = "document"

    return {"url": url, "nom": original_name, "type": ftype}
