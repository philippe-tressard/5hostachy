"""Router documents — bibliothèque documentaire avec contrôle d'accès 3 couches."""
import json
import os
import shutil
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_cs_or_admin
from app.database import get_session
from app.models.core import (
    CategorieDocument, ConfigSite, Document, Notification,
    ProfilAccesDocument, Utilisateur, RoleUtilisateur
)
from app.schemas import DocumentRead
from app.utils.fichiers import REPERTOIRE_PRIVE, extension_assainie, nom_stocke
# Toute règle de visibilité — documents compris — vient du module central.
from app.utils.visibility import document_visible

router = APIRouter(prefix="/documents", tags=["documents"])

UPLOADS_DIR = os.getenv("UPLOADS_DIR", "/app/uploads")


# La règle d'accès aux documents est `document_visible` (app/utils/visibility.py),
# avec toutes les autres règles de visibilité. Ce router l'appelle, il ne la redéfinit
# pas et ne l'aliase pas : un seul nom, un seul endroit.


def _notifier_document_publie(
    doc: Document, auteur: Utilisateur, background_tasks: BackgroundTasks, session: Session,
) -> None:
    """Prévient les résidents qui ont le droit de voir ce document.

    Le modèle `document_publie` existait depuis l'origine sans qu'aucune ligne
    ne l'envoie. Ce n'était pas un modèle mort : le manuel recommande
    « documents = e-mail » et le profil affiche la ligne « Nouveaux documents
    ajoutés » avec ses deux cases. Les deux canaux étaient promis, aucun n'était
    branché — la préférence se réglait dans le vide.

    **Le périmètre de diffusion est celui de la lecture, pas un autre.** La
    liste des destinataires est filtrée par `document_visible`, la même
    fonction que l'endpoint de téléchargement : une notification qui annonce un
    document qu'on ne peut pas ouvrir est au mieux une frustration, au pire la
    divulgation d'un titre confidentiel. Réutiliser la règle plutôt que de la
    réécrire garantit qu'un durcissement ultérieur profite aux deux.

    Envois **individuels** et non groupés : `send_email_group` place tous les
    destinataires en TO, où ils se voient les uns les autres. Le dépôt ne s'en
    sert que pour des groupes internes de quelques personnes (syndic, conseil
    syndical) ; diffuser ainsi à toute la résidence exposerait le carnet
    d'adresses des copropriétaires à chacun d'eux.
    """
    from app.utils.email import send_email
    from app.utils.liens import lien_element

    # Une pièce jointe d'actualité et un document de contrat ne sont pas des
    # publications documentaires : la première est annoncée par l'e-mail de sa
    # publication, le second ne concerne que le CS, déjà à la manœuvre.
    if not doc.categorie_id:
        return

    cfg = {
        row.cle: row.valeur
        for row in session.exec(
            select(ConfigSite).where(ConfigSite.cle.in_(("site_nom", "site_url")))
        ).all()
    }
    site_nom = cfg.get("site_nom") or "5Hostachy"
    site_url = (cfg.get("site_url") or "https://localhost").rstrip("/")

    destinataires = session.exec(
        select(Utilisateur).where(Utilisateur.actif == True)  # noqa: E712
    ).all()

    # Ni ici ni dans le modèle l'URL n'est écrite à la main : `/documents`
    # n'existe pas côté front, et c'est exactement la faute qui a produit un 404
    # en pleine page le 26/07/2026. La table `EMPLACEMENTS` sait où vit un
    # document, et `test_liens_front.py` vérifie qu'elle dit vrai.
    lien_doc = lien_element("doc", doc.id)

    for u in destinataires:
        if u.id == auteur.id or not document_visible(u, doc, session):
            continue
        session.add(Notification(
            destinataire_id=u.id,
            type="document",
            titre=f"Nouveau document : {doc.titre}",
            corps=doc.titre,
            lien=lien_doc,
        ))
        if not u.email:
            continue
        background_tasks.add_task(
            send_email,
            code="document_publie",
            to=u.email,
            context={
                "document": {"titre": doc.titre, "lien": lien_doc},
                "residence": {"nom": site_nom},
                "app": {"url": site_url},
            },
            session=session,
            # Sans cet identifiant, la préférence `doc_mail` du profil ne serait
            # toujours pas consultée : la case resterait décorative.
            destinataire_id=u.id,
        )
    session.commit()


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
    ticket_id: int | None = None,
    evenement_id: int | None = None,
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
    if ticket_id:
        stmt = stmt.where(Document.ticket_id == ticket_id)
    if evenement_id:
        stmt = stmt.where(Document.evenement_id == evenement_id)

    #  🔴 UNE PIÈCE JOINTE N'EST PAS UN DOCUMENT DE LA BIBLIOTHÈQUE (#390).
    #
    #  Cet endpoint SANS filtre rend toutes les lignes, et c'est ce que l'écran
    #  Résidence appelle pour son dépôt de plans et de règlements. Sans cette
    #  exclusion, chaque photo jointe à un ticket s'y afficherait dès le premier
    #  écran basculé — la faille exacte que #390 existe pour fermer, retournée.
    #
    #  ⚠️ On exclut au niveau de la REQUÊTE et non du filtrage par visibilité :
    #  `document_visible` répondrait « oui » pour l'auteur du ticket, ce qui est
    #  juste — la pièce jointe lui est bien lisible — mais elle n'a rien à faire
    #  dans la bibliothèque pour autant. Ce sont deux questions différentes.
    if not ticket_id and not evenement_id:
        stmt = stmt.where(Document.ticket_id.is_(None), Document.evenement_id.is_(None))

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
    ticket_id: int | None = Form(None),
    evenement_id: int | None = Form(None),
    perimetre: str = Form("résidence"),
    batiment_id: int | None = Form(None),
    lot_id: int | None = Form(None),
    annee: int | None = Form(None),
    date_ag: str | None = Form(None),
    batiments_ids_json: str | None = Form(None),
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    #  🔴 L'INVARIANT : une ligne `document` porte TOUJOURS un rattachement.
    #  C'est lui qui garantit qu'aucune ligne orpheline n'existe, et donc que
    #  `document_visible` a toujours une source de protection à consulter. Il
    #  S'ÉTEND aux pièces jointes de ticket et d'événement (#390) plutôt que de se
    #  relâcher : le découpage d'origine proposait de créer la ligne « sans
    #  rattachement, rattachée ensuite », ce qui l'aurait violé le temps d'un
    #  formulaire abandonné — c'est-à-dire pour toujours.
    if not categorie_id and not contrat_id and not publication_id             and not ticket_id and not evenement_id:
        raise HTTPException(
            400,
            "categorie_id, contrat_id, publication_id, ticket_id ou evenement_id obligatoire",
        )

    if categorie_id:
        categorie = session.get(CategorieDocument, categorie_id)
        if not categorie or not categorie.actif:
            raise HTTPException(400, "Catégorie invalide")

    # REPERTOIRE_PRIVE et non la racine du volume : `/uploads/*` est servi en
    # statique sans authentification, et le contrôle d'accès à trois couches de
    # `document_visible` serait contourné par la simple URL du fichier.
    os.makedirs(REPERTOIRE_PRIVE, exist_ok=True)
    # Assainissement et préfixe UUID : app/utils/fichiers.py, seul endroit où
    # cette règle est écrite. Le téléchargement passe par un endpoint
    # authentifié qui impose lui-même le `media_type`, l'extension d'origine
    # peut donc être conservée telle quelle.
    raw_name = file.filename or "document"
    dest = os.path.join(REPERTOIRE_PRIVE, nom_stocke(raw_name, extension_assainie(raw_name)))
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
        ticket_id=ticket_id,
        evenement_id=evenement_id,
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

    # `background_tasks` est optionnel : un appel qui ne le fournit pas publie
    # le document sans notifier, plutôt que d'échouer en cours de route.
    if background_tasks is not None:
        _notifier_document_publie(doc, user, background_tasks, session)

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
