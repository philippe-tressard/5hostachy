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
from app.models.core import AnnonceHall, ConfigSite, Document, Publication, Utilisateur
from app.utils.annonce_hall import (
    APERCU_MAX,
    FORMATS,
    MAX_PHOTOS,
    choisir_format,
    construire_html,
    format_libelle,
    generer_pdf,
    nom_fichier,
    texte_brut,
)
from app.routers.annonces_hall_courriels import (
    _envoyer_email_annonce,
    _partager_sur_le_groupe,
)
from app.utils.perimetres import parse_json_perimetres, perimetre_label_liste
from app.utils.photos import parse_photos
from app.utils.noms import nom_affiche

router = APIRouter(prefix="/annonces-hall", tags=["annonces-hall"])

#  L'aperçu avant envoi vit dans son propre module — même découpage que les
#  actualités (`publications/apercu.py`) : il ne partage avec la création que les
#  fonctions de composition, et surtout pas son routeur (#480/#498).
from app.routers.annonces_hall_apercu import router as _router_apercu  # noqa: E402

router.include_router(_router_apercu)

PDF_DIR = Path("/app/uploads/annonces-hall")
UPLOADS_ROOT = os.path.realpath("/app/uploads")


# ── Schémas ──────────────────────────────────────────────────────────────────

class AnnonceHallBase(BaseModel):
    titre: str
    message: str
    perimetre_cible: list[str] = ["résidence"]
    format_demande: str = "auto"
    images: list[str] = []


class AnnonceHallCreate(AnnonceHallBase):
    #  🔴 La DIFFUSION est un ACTE, et elle se coche (section 9 du cadre #430).
    #
    #  L'envoi au CS était AUTOMATIQUE jusqu'au 18/08, puis supprimé le même jour
    #  parce qu'il partait au moindre essai de mise en page. Il revient ici sous sa
    #  forme juste : un choix, décoché par défaut.
    #
    #  ⚠️ Décoché par défaut, et c'est le point : la valeur par défaut d'un envoi
    #  est « ne pas envoyer ». Un défaut à `True` reproduirait l'automatisme qu'on
    #  vient de retirer, en donnant l'illusion du choix.
    envoyer_cs: bool = False
    #  Les deux autres canaux de la Diffusion (#480). Mêmes règles : décochés par
    #  défaut, et CONSOMMÉS — un champ ouvert dans l'interface que le serveur
    #  ignorerait est ce que le cadre interdit.
    envoyer_syndic: bool = False
    partager_whatsapp: bool = False
    #  La 4e case : « Envoyer une copie à … ». Le destinataire est l'auteur de
    #  l'AFFICHE — voir `app/utils/copie_auteur.py`.
    envoyer_auteur: bool = False


class AnnonceHallArchive(BaseModel):
    archivee: bool


# ── Helpers ──────────────────────────────────────────────────────────────────

def _config_site(session: Session) -> dict[str, str]:
    rows = session.exec(
        select(ConfigSite).where(ConfigSite.cle.in_(("site_nom", "site_url")))
    ).all()
    return {r.cle: (r.valeur or "") for r in rows}


#  ⚠️ `_batiments()` a disparu avec `perimetre_libelle` (27/08/2026) : il ne
#  servait qu'à fabriquer « Bât. {numero} » en dehors de l'arbre. Le libellé d'un
#  bâtiment vient désormais de la table `perimetre`, donc de l'administration —
#  un renommage l'atteint, ce que cette table-là ne permettait pas.


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
        "perimetre_label": perimetre_label_liste(body.perimetre_cible),
        "format_effectif": format_effectif,
        "site_nom": cfg.get("site_nom") or "5Hostachy",
        "site_url": cfg.get("site_url") or "https://5hostachy.fr",
        "images": body.images,
        "date_affichage": date_affichage,
    }


def _to_read(annonce: AnnonceHall, session: Session) -> dict:
    auteur = session.get(Utilisateur, annonce.auteur_id)
    perimetres = parse_json_perimetres(annonce.perimetre_cible)
    return {
        "id": annonce.id,
        "titre": annonce.titre,
        "message": annonce.message,
        "apercu": texte_brut(annonce.message)[:APERCU_MAX],
        "perimetre_cible": perimetres,
        "perimetre_label": perimetre_label_liste(perimetres),
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
        "auteur_nom": nom_affiche(auteur.prenom, auteur.nom) if auteur else "",
    }


def images_de_publication(pub: Publication, session: Session) -> list[str]:
    """Photos exploitables d'une actualité, limitées à `MAX_PHOTOS`.

    L'image de la publication vient en premier, puis ses pièces jointes de type
    image (des `Document`, dont le `fichier_chemin` est converti en URL
    `/uploads/...` — les documents sont écrits à la racine du volume uploads,
    cf. `documents.py`).
    """
    urls: list[str] = [
        u for u in parse_photos(pub.photos_urls) if u.startswith("/uploads/")
    ]

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
    return [_to_read(a, session) for a in annonces]


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
    #  Décoché par défaut : la valeur par défaut d'un envoi est « ne pas envoyer ».
    #  Les autres appelants (pré-remplissage depuis une actualité) n'envoient donc
    #  rien sans le demander.
    envoyer_cs: bool = False,
    #  🔴 Les DEUX autres canaux de la Diffusion (#480, 01/09/2026). Ils
    #  s'affichaient dans `CanauxNotification` partout ailleurs et n'existaient pas
    #  ici : l'écran portait une case unique, et le cadre interdit d'ouvrir un
    #  champ que le serveur ne consomme pas. Les voici consommés.
    envoyer_syndic: bool = False,
    partager_whatsapp: bool = False,
    envoyer_auteur: bool = False,
) -> AnnonceHall:
    """Génère le PDF et l'enregistre dans l'historique.

    ⚠️ Plus aucun envoi depuis le 18/08/2026 : cet écran fabrique un document à
    imprimer, et sa diffusion appartient à celui qui le génère.

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

    #  🔴 L'ENVOI EST UN CHOIX, jamais un automatisme (18/08/2026).
    #
    #  Il était automatique le matin — « ce menu ne doit pas envoyer de mail au CS,
    #  juste générer un PDF » —, supprimé dans la foulée, puis rendu au CADRE : la
    #  Diffusion est la section 9, elle se coche, et elle n'agit que cochée.
    #
    #  Cet écran FABRIQUE un document à imprimer. Qui l'imprime, quand, et à qui il
    #  l'envoie sont des décisions qui appartiennent à celui qui le génère — les
    #  prendre à sa place expédiait un courriel à tout le conseil syndical au moindre
    #  essai de mise en page, pièce jointe comprise.
    #
    #  ⚠️ Le bouton dit « Générer une affiche », et c'est vrai dans les deux cas :
    #  l'affiche est produite, l'envoi est une option qu'on ajoute. C'est ce qui
    #  distingue cette section 9 d'un bouton « Envoyer » — le geste principal reste
    #  la génération.
    #
    #  Sans la case, `destinataires` et `envoye_le` restent vides : l'historique dit
    #  qu'une affiche a été générée, et rien de plus — ce qui est exactement le fait.
    diffuse = False
    if envoyer_cs or envoyer_syndic:
        emails = _envoyer_email_annonce(
            annonce, user, background_tasks, session,
            syndic=envoyer_syndic, cs=envoyer_cs, auteur=envoyer_auteur,
        )
        if emails:
            annonce.destinataires = json.dumps(emails, ensure_ascii=False)
            diffuse = True
    if partager_whatsapp and _partager_sur_le_groupe(annonce, background_tasks, session):
        diffuse = True

    #  ⚠️ `envoye_le` est posé si UN canal a réellement été programmé — pas si une
    #  case était cochée. Un WhatsApp éteint ou un périmètre sans conseiller ne
    #  doivent pas inscrire dans l'historique une diffusion qui n'a pas eu lieu.
    if diffuse:
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
    """Génère le PDF et l'archive dans l'historique — sans aucun envoi (18/08/2026)."""
    annonce = creer_annonce_hall(
        session=session,
        user=user,
        background_tasks=background_tasks,
        titre=body.titre,
        message=body.message,
        perimetre_cible=body.perimetre_cible,
        format_demande=body.format_demande,
        images=body.images,
        envoyer_cs=body.envoyer_cs,
        envoyer_syndic=body.envoyer_syndic,
        partager_whatsapp=body.partager_whatsapp,
        envoyer_auteur=body.envoyer_auteur,
    )
    return _to_read(annonce, session)


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
    #  Le renvoi manuel vise le CS du périmètre, comme avant : c'est un geste de
    #  rattrapage sur un envoi qui a déjà eu lieu, pas une nouvelle diffusion.
    emails = _envoyer_email_annonce(annonce, user, background_tasks, session)
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
    return _to_read(annonce, session)


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
