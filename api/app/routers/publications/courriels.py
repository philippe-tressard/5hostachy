"""Publications — les courriels que produit une publication.

Extrait de `publications.py` le 11/08/2026, comme `tickets/courriels.py` l'avait
été le 08/08 : ce qui **compose et envoie** un message vit à part, pour que les
routes ne portent plus que la décision de l'envoyer.
"""
import os
from datetime import datetime

from fastapi import BackgroundTasks
from sqlmodel import Session, select

from app.models.core import (
    ConfigSite, Document, MembreSyndic, Publication, PublicationEvolution,
    Utilisateur,
)
from app.utils.dates_fr import datetime_longue_paris as _fmt_paris
from app.utils.fichiers import chemins_locaux
from app.utils.perimetres import batiments_cibles, parse_json_perimetres
from app.utils.photos import parse_photos


def _batiments_de(pub) -> set[int]:
    """Les bâtiments visés par une publication, pour la préférence d'e-mail.

    Sans cela, la case « des autres bâtiments » du profil ne déciderait rien : le
    moteur d'envoi ne saurait pas d'où vient le contenu et retomberait sur
    « mon bâtiment » — c'est-à-dire enverrait toujours (#339).

    Un ensemble VIDE signifie « portée globale ou périmètre inconnu », et
    `preferences_mail.mail_autorise` le traite comme « me concerne » : une
    actualité qui vise tout le monde me vise aussi.
    """
    return batiments_cibles(parse_json_perimetres(getattr(pub, "perimetre_cible", None)))


def _envoyer_email_syndic_publication(
    pub: Publication, user: Utilisateur, background_tasks: BackgroundTasks, session: Session,
    *, syndic: bool = True, cs: bool = False,
    commentaire: str | None = None, fichiers_urls: list[str] | None = None,
):
    """Envoie un email au syndic et/ou CS avec la publication en corps."""
    from app.utils.email import send_email_group

    destinataires: list[tuple[int | None, str]] = []
    seen_emails: set[str] = set()

    if syndic:
        syndic_principal = session.exec(
            select(MembreSyndic).where(MembreSyndic.est_principal == True)
        ).first()
        if syndic_principal and syndic_principal.email:
            destinataires.append((syndic_principal.user_id, syndic_principal.email))
            seen_emails.add(syndic_principal.email.lower())

    if cs:
        cs_users = session.exec(
            select(Utilisateur.id, Utilisateur.email)
            .where(
                Utilisateur.actif == True,
                Utilisateur.email.isnot(None),
                Utilisateur.roles_json.contains("conseil_syndical"),
            )
        ).all()
        for uid, email in cs_users:
            if email and email.lower() not in seen_emails:
                destinataires.append((uid, email))
                seen_emails.add(email.lower())

    if not destinataires:
        return

    cfg_rows = session.exec(
        select(ConfigSite).where(ConfigSite.cle.in_(("site_nom", "site_url")))
    ).all()
    cfg = {r.cle: r.valeur for r in cfg_rows}

    # Historique des évolutions (pour les commentaires)
    evols_ctx = []
    is_commentaire = commentaire is not None
    if is_commentaire:
        evols = session.exec(
            select(PublicationEvolution)
            .where(PublicationEvolution.publication_id == pub.id)
            .order_by(PublicationEvolution.cree_le)
        ).all()
        for e in evols[:-1]:  # Exclure le dernier (= le commentaire en cours)
            if not e.contenu:
                continue
            auteur_e = session.get(Utilisateur, e.auteur_id)
            evols_ctx.append({
                "auteur_nom": f"{auteur_e.prenom} {auteur_e.nom}" if auteur_e else "?",
                "date": _fmt_paris(e.cree_le),
                "contenu": e.contenu,
            })

    # La galerie ENTIÈRE, résolue par `chemins_locaux` et JAMAIS par un dossier
    # écrit en dur : les photos vivent dans `/uploads/fichiers/` depuis
    # l'unification, et un chemin figé rendait un courriel SANS ses photos, sans
    # la moindre erreur (10/08/2026).
    all_attachments: list[str] = chemins_locaux(parse_photos(pub.photos_urls))

    # Fichiers joints (documents liés à la publication)
    docs = session.exec(select(Document).where(Document.publication_id == pub.id)).all()
    for doc in docs:
        if doc.fichier_chemin and os.path.isfile(doc.fichier_chemin):
            all_attachments.append(doc.fichier_chemin)

    # Fichiers joints au commentaire
    if fichiers_urls:
        all_attachments.extend(chemins_locaux(fichiers_urls))

    ctx = {
        "publication": {"id": pub.id, "titre": pub.titre, "contenu": pub.contenu or ""},
        "auteur": {"prenom": user.prenom, "nom": user.nom},
        "residence": {"nom": cfg.get("site_nom", "5Hostachy")},
        "app": {"url": (cfg.get("site_url") or "https://localhost").rstrip("/")},
        "is_commentaire": is_commentaire,
        "commentaire": commentaire or "",
        "date_commentaire": _fmt_paris(datetime.utcnow()),
        "date_publication": _fmt_paris(pub.cree_le),
        "evolutions": evols_ctx,
        # Ce que le lecteur voit annoncé doit être ce qui est réellement attaché :
        # le drapeau se calcule donc APRÈS la liste, et sur elle. Il ne portait que
        # sur les fichiers du commentaire — une actualité publiée avec ses pièces
        # jointes les envoyait sans jamais les annoncer.
        "fichiers": bool(all_attachments),
    }

    if destinataires:
        # Auteur en copie cachée : confirmation visuelle que l'envoi a bien eu lieu.
        # Pas de doublon si l'auteur est déjà destinataire principal (syndic/CS).
        auteur_bcc = [user.email] if user.email.lower() not in seen_emails else None
        background_tasks.add_task(
            send_email_group,
            code="publication_syndic",
            to_recipients=destinataires,
            context=ctx,
            session=session,
            bcc=auteur_bcc,
            attachments=all_attachments or None,
            batiments_concernes=_batiments_de(pub),
        )


def _envoyer_email_externe_publication(
    pub: Publication,
    user: Utilisateur,
    email_externe: str,
    background_tasks: BackgroundTasks,
    session: Session,
    *,
    is_commentaire: bool = True,
    commentaire: str | None = None,
    fichiers_urls: list[str] | None = None,
):
    """Envoie un email vers une adresse externe (non-utilisateur) avec l'historique de la publication."""
    from app.utils.email import send_email

    cfg_rows = session.exec(
        select(ConfigSite).where(ConfigSite.cle.in_(("site_nom", "site_url")))
    ).all()
    cfg = {r.cle: r.valeur for r in cfg_rows}

    # Historique des évolutions (du plus ancien au plus récent, sauf la dernière si commentaire)
    evols = session.exec(
        select(PublicationEvolution)
        .where(PublicationEvolution.publication_id == pub.id)
        .order_by(PublicationEvolution.cree_le)
    ).all()
    evols_for_history = evols[:-1] if (is_commentaire and evols) else evols
    evol_ctx = []
    for e in evols_for_history:
        if not e.contenu:
            continue
        auteur_e = session.get(Utilisateur, e.auteur_id)
        evol_ctx.append({
            "auteur_nom": f"{auteur_e.prenom} {auteur_e.nom}" if auteur_e else "?",
            "date": _fmt_paris(e.cree_le),
            "contenu": e.contenu,
        })

    attachments = chemins_locaux(fichiers_urls or [])

    ctx = {
        "publication": {"id": pub.id, "titre": pub.titre, "contenu": pub.contenu or ""},
        "auteur": {"prenom": user.prenom, "nom": user.nom},
        "date_publication": _fmt_paris(pub.cree_le),
        "date_commentaire": _fmt_paris(datetime.utcnow()),
        "residence": {"nom": cfg.get("site_nom", "5Hostachy")},
        "app": {"url": (cfg.get("site_url") or "https://localhost").rstrip("/")},
        "is_commentaire": is_commentaire,
        "commentaire": commentaire or "",
        "evolutions": evol_ctx,
        "fichiers": bool(attachments),
    }

    # Auteur en copie cachée : confirmation visuelle que l'envoi a bien eu lieu.
    auteur_bcc = [user.email] if user.email.lower() != email_externe.lower() else None
    background_tasks.add_task(
        send_email,
        code="publication_externe",
        to=email_externe,
        context=ctx,
        bcc=auteur_bcc,
        attachments=attachments or None,
    )
