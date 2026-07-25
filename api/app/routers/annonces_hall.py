"""Router annonces hall — affiches PDF (A4/A5) du Conseil Syndical.

Deux usages :
  1. création d'une annonce → PDF généré à la charte + envoi par e-mail aux
     membres du CS du périmètre, le PDF en pièce jointe ;
  2. historique consultable, archivable (CS) et supprimable (admin).
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import require_admin, require_cs_or_admin
from app.database import get_session
from app.models.core import AnnonceHall, Batiment, ConfigSite, Document, Publication, Utilisateur
from app.utils.annonce_hall import (
    FORMATS,
    MAX_PHOTOS,
    choisir_format,
    construire_html,
    date_longue,
    format_libelle,
    generer_pdf,
    nom_fichier,
    perimetre_libelle,
    texte_brut,
)
from app.utils.destinataires import batiments_du_perimetre, membres_cs_notifiables
from app.utils.email import send_email_group

router = APIRouter(prefix="/annonces-hall", tags=["annonces-hall"])

PDF_DIR = Path("/app/uploads/annonces-hall")
UPLOADS_ROOT = os.path.realpath("/app/uploads")
APERCU_MAX = 180


# ── Schémas ──────────────────────────────────────────────────────────────────

class AnnonceHallBase(BaseModel):
    titre: str
    message: str
    perimetre_cible: list[str] = ["résidence"]
    format_demande: str = "auto"
    images: list[str] = []


class AnnonceHallCreate(AnnonceHallBase):
    pass


class AnnonceHallArchive(BaseModel):
    archivee: bool


# ── Helpers ──────────────────────────────────────────────────────────────────

def _config_site(session: Session) -> dict[str, str]:
    rows = session.exec(
        select(ConfigSite).where(ConfigSite.cle.in_(("site_nom", "site_url")))
    ).all()
    return {r.cle: (r.valeur or "") for r in rows}


def _batiments(session: Session) -> dict[int, str]:
    """`{id: numero}` — pour libeller `bat:1` en `Bât. A`."""
    return {b.id: b.numero for b in session.exec(select(Batiment)).all() if b.id is not None}


def _valider(body: AnnonceHallBase) -> None:
    if not body.titre.strip():
        raise HTTPException(422, "Le titre est obligatoire")
    if not texte_brut(body.message):
        raise HTTPException(422, "Le message est obligatoire")
    if (body.format_demande or "auto").lower() not in ("auto", *FORMATS):
        raise HTTPException(422, "Format invalide (auto, a4 ou a5)")
    if len(body.images) > MAX_PHOTOS:
        raise HTTPException(422, f"{MAX_PHOTOS} photos au maximum")
    if any(not u.startswith("/uploads/") for u in body.images):
        raise HTTPException(422, "Photo invalide")


def _html_params(body: AnnonceHallBase, session: Session, *, format_effectif: str,
                 date_affichage: datetime) -> dict:
    cfg = _config_site(session)
    return {
        "titre": body.titre.strip(),
        "message_html": body.message,
        "perimetre_label": perimetre_libelle(body.perimetre_cible, _batiments(session)),
        "format_effectif": format_effectif,
        "site_nom": cfg.get("site_nom") or "5Hostachy",
        "site_url": cfg.get("site_url") or "https://5hostachy.fr",
        "images": body.images,
        "date_affichage": date_affichage,
    }


def _to_read(annonce: AnnonceHall, session: Session, batiments: dict[int, str]) -> dict:
    auteur = session.get(Utilisateur, annonce.auteur_id)
    perimetres = json.loads(annonce.perimetre_cible or '["résidence"]')
    return {
        "id": annonce.id,
        "titre": annonce.titre,
        "message": annonce.message,
        "apercu": texte_brut(annonce.message)[:APERCU_MAX],
        "perimetre_cible": perimetres,
        "perimetre_label": perimetre_libelle(perimetres, batiments),
        "format_demande": annonce.format_demande,
        "format_effectif": annonce.format_effectif,
        "format_label": format_libelle(annonce.format_effectif),
        "images": json.loads(annonce.images_json or "[]"),
        "pdf_nom": annonce.pdf_nom,
        "taille_octets": annonce.taille_octets,
        "destinataires": json.loads(annonce.destinataires or "[]"),
        "envoye_le": annonce.envoye_le.isoformat() if annonce.envoye_le else None,
        "archivee": annonce.archivee,
        "publication_id": annonce.publication_id,
        "cree_le": annonce.cree_le.isoformat(),
        "auteur_nom": f"{auteur.prenom} {auteur.nom}" if auteur else "",
    }


def _envoyer_email_cs(
    annonce: AnnonceHall, user: Utilisateur, background_tasks: BackgroundTasks,
    session: Session, batiments: dict[int, str],
) -> list[str]:
    """Programme l'envoi de l'annonce au CS du périmètre. Retourne les e-mails visés."""
    perimetres = json.loads(annonce.perimetre_cible or '["résidence"]')
    destinataires = membres_cs_notifiables(session, batiments_du_perimetre(perimetres))
    if not destinataires:
        return []

    ctx = {
        "annonce": {
            "id": annonce.id,
            "titre": annonce.titre,
            "perimetre": perimetre_libelle(perimetres, batiments),
            "format": format_libelle(annonce.format_effectif),
            "date": date_longue(annonce.cree_le),
            "apercu": texte_brut(annonce.message)[:APERCU_MAX],
            "fichier": annonce.pdf_nom,
        },
        "auteur": {"prenom": user.prenom, "nom": user.nom},
    }

    emails = [email for _, email in destinataires]
    # Auteur en copie cachée : confirmation visuelle que l'envoi a bien eu lieu.
    auteur_bcc = (
        [user.email] if user.email and user.email.lower() not in {e.lower() for e in emails} else None
    )
    background_tasks.add_task(
        send_email_group,
        code="annonce_hall",
        to_recipients=destinataires,
        context=ctx,
        session=session,
        bcc=auteur_bcc,
        attachments=[annonce.pdf_chemin] if os.path.isfile(annonce.pdf_chemin) else None,
    )
    return emails


def images_de_publication(pub: Publication, session: Session) -> list[str]:
    """Photos exploitables d'une actualité, limitées à `MAX_PHOTOS`.

    L'image de la publication vient en premier, puis ses pièces jointes de type
    image (des `Document`, dont le `fichier_chemin` est converti en URL
    `/uploads/...` — les documents sont écrits à la racine du volume uploads,
    cf. `documents.py`).
    """
    urls: list[str] = []
    if pub.image_url and pub.image_url.startswith("/uploads/"):
        urls.append(pub.image_url)

    docs = session.exec(
        select(Document)
        .where(Document.publication_id == pub.id)
        .order_by(Document.publie_le)  # type: ignore[arg-type]
    ).all()

    for doc in docs:
        if not (doc.mime_type or "").startswith("image/"):
            continue
        reel = os.path.realpath(doc.fichier_chemin or "")
        if not reel.startswith(UPLOADS_ROOT + os.sep) or not os.path.isfile(reel):
            continue
        url = "/uploads/" + os.path.relpath(reel, UPLOADS_ROOT).replace(os.sep, "/")
        if url not in urls:
            urls.append(url)
    return urls[:MAX_PHOTOS]


def _supprimer_fichier(chemin: str | None) -> None:
    """Supprime un fichier du volume uploads (jamais hors de ce volume)."""
    if not chemin:
        return
    reel = os.path.realpath(chemin)
    if not reel.startswith(UPLOADS_ROOT + os.sep):
        return
    try:
        os.unlink(reel)
    except OSError:
        pass


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("", summary="Historique des annonces de hall (CS/Admin)")
def list_annonces_hall(
    archivees: bool = False,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    annonces = session.exec(
        select(AnnonceHall)
        .where(AnnonceHall.archivee == archivees)
        .order_by(AnnonceHall.cree_le.desc())  # type: ignore[arg-type]
    ).all()
    batiments = _batiments(session)
    return [_to_read(a, session, batiments) for a in annonces]


@router.get("/depuis-publication/{pub_id}",
            summary="Pré-remplissage d'une annonce depuis une actualité (CS/Admin)")
def prefill_depuis_publication(
    pub_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Retourne les champs d'une actualité, prêts à alimenter le formulaire.

    Aucune écriture : le CS ajuste ensuite librement avant de valider.
    """
    pub = session.get(Publication, pub_id)
    if not pub:
        raise HTTPException(404, "Actualité introuvable")
    return {
        "titre": pub.titre,
        "message": pub.contenu,
        "perimetre_cible": json.loads(pub.perimetre_cible or '["résidence"]'),
        "images": images_de_publication(pub, session),
    }


@router.post("/previsualiser", summary="Aperçu HTML de l'annonce avant envoi (CS/Admin)")
def previsualiser_annonce(
    body: AnnonceHallCreate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Rend l'annonce en HTML sans rien enregistrer ni envoyer."""
    _valider(body)
    fmt = choisir_format(
        body.message, body.format_demande,
        titre=body.titre, avec_photos=bool(body.images),
    )
    params = _html_params(body, session, format_effectif=fmt, date_affichage=datetime.utcnow())
    return {
        "format_effectif": fmt,
        "format_label": format_libelle(fmt),
        "perimetre_label": params["perimetre_label"],
        "html": construire_html(**params),
    }


def creer_annonce_hall(
    *,
    session: Session,
    user: Utilisateur,
    background_tasks: BackgroundTasks,
    titre: str,
    message: str,
    perimetre_cible: list[str],
    format_demande: str = "auto",
    images: Optional[list[str]] = None,
    publication_id: Optional[int] = None,
) -> AnnonceHall:
    """Génère le PDF, l'enregistre dans l'historique et l'envoie au CS du périmètre.

    Point d'entrée unique : utilisé par l'onglet Annonces Hall **et** par l'option
    « Annonce Hall » d'une actualité (`publications.py`).
    """
    body = AnnonceHallCreate(
        titre=titre,
        message=message,
        perimetre_cible=perimetre_cible or ["résidence"],
        format_demande=format_demande,
        images=(images or [])[:MAX_PHOTOS],
    )
    _valider(body)
    maintenant = datetime.utcnow()
    fmt = choisir_format(
        body.message, body.format_demande,
        titre=body.titre, avec_photos=bool(body.images),
    )
    params = _html_params(body, session, format_effectif=fmt, date_affichage=maintenant)

    try:
        pdf = generer_pdf(**params)
    except Exception as exc:  # pragma: no cover - dépend de l'environnement de rendu
        raise HTTPException(500, f"Génération du PDF impossible : {exc}") from exc

    PDF_DIR.mkdir(parents=True, exist_ok=True)
    chemin = PDF_DIR / f"{uuid.uuid4().hex}.pdf"
    chemin.write_bytes(pdf)

    annonce = AnnonceHall(
        titre=body.titre.strip(),
        message=body.message,
        perimetre_cible=json.dumps(body.perimetre_cible, ensure_ascii=False),
        format_demande=(body.format_demande or "auto").lower(),
        format_effectif=fmt,
        images_json=json.dumps(body.images, ensure_ascii=False),
        pdf_chemin=str(chemin),
        pdf_nom=nom_fichier(body.titre, maintenant),
        taille_octets=len(pdf),
        publication_id=publication_id,
        auteur_id=user.id,
        cree_le=maintenant,
    )
    session.add(annonce)
    session.commit()
    session.refresh(annonce)

    emails = _envoyer_email_cs(annonce, user, background_tasks, session, _batiments(session))
    if emails:
        annonce.destinataires = json.dumps(emails, ensure_ascii=False)
        annonce.envoye_le = datetime.utcnow()
        session.add(annonce)
        session.commit()
        session.refresh(annonce)

    return annonce


@router.post("", status_code=201, summary="Créer une annonce de hall (CS/Admin)")
def create_annonce_hall(
    body: AnnonceHallCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Génère le PDF, l'archive dans l'historique et l'envoie au CS du périmètre."""
    annonce = creer_annonce_hall(
        session=session,
        user=user,
        background_tasks=background_tasks,
        titre=body.titre,
        message=body.message,
        perimetre_cible=body.perimetre_cible,
        format_demande=body.format_demande,
        images=body.images,
    )
    return _to_read(annonce, session, _batiments(session))


@router.get("/{annonce_id}/pdf", summary="Télécharger le PDF d'une annonce (CS/Admin)")
def download_pdf(
    annonce_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    annonce = session.get(AnnonceHall, annonce_id)
    if not annonce:
        raise HTTPException(404, "Annonce introuvable")
    if not annonce.pdf_chemin or not os.path.isfile(annonce.pdf_chemin):
        raise HTTPException(404, "PDF introuvable sur le serveur")
    return FileResponse(
        annonce.pdf_chemin,
        media_type="application/pdf",
        filename=annonce.pdf_nom or f"annonce-{annonce_id}.pdf",
    )


@router.post("/{annonce_id}/renvoyer-email", status_code=204,
             summary="Renvoyer l'annonce au CS du périmètre (CS/Admin)")
def renvoyer_email(
    annonce_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    annonce = session.get(AnnonceHall, annonce_id)
    if not annonce:
        raise HTTPException(404, "Annonce introuvable")
    emails = _envoyer_email_cs(annonce, user, background_tasks, session, _batiments(session))
    if not emails:
        raise HTTPException(
            422,
            "Aucun membre du CS rattaché à ce périmètre ne dispose d'un compte avec e-mail",
        )
    annonce.destinataires = json.dumps(emails, ensure_ascii=False)
    annonce.envoye_le = datetime.utcnow()
    session.add(annonce)
    session.commit()


@router.patch("/{annonce_id}", summary="Archiver / désarchiver une annonce (CS/Admin)")
def archiver_annonce(
    annonce_id: int,
    body: AnnonceHallArchive,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    annonce = session.get(AnnonceHall, annonce_id)
    if not annonce:
        raise HTTPException(404, "Annonce introuvable")
    annonce.archivee = body.archivee
    session.add(annonce)
    session.commit()
    session.refresh(annonce)
    return _to_read(annonce, session, _batiments(session))


@router.delete("/{annonce_id}", status_code=204,
               summary="Supprimer définitivement une annonce (Admin)")
def delete_annonce_hall(
    annonce_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Suppression définitive : la ligne, le PDF et l'illustration partent."""
    annonce = session.get(AnnonceHall, annonce_id)
    if not annonce:
        raise HTTPException(404, "Annonce introuvable")
    _supprimer_fichier(annonce.pdf_chemin)
    for url in json.loads(annonce.images_json or "[]"):
        if url:
            _supprimer_fichier(os.path.join("/app", url.lstrip("/")))
    session.delete(annonce)
    session.commit()
