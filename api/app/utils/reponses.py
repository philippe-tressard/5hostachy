"""Helpers partagés pour les réponses de la Communauté (idées, annonces, sondages).

Source unique de vérité pour :
  - l'enrichissement de l'auteur d'une réponse (nom + bâtiment + rôle) ;
  - la mise en avant des réponses CS/admin (est_cs → tri prioritaire côté front) ;
  - la notification du créateur du contenu (in-app + email, dans le respect des
    préférences utilisateur).

Utilisé par idees.py, annonces.py et sondages.py pour une UX cohérente et éviter
toute divergence de code entre les sous-rubriques.
"""
from __future__ import annotations

from typing import Optional

from fastapi import BackgroundTasks
from sqlmodel import Session

from app.models.core import (
    Batiment,
    ConfigSite,
    Notification,
    RoleUtilisateur,
    Utilisateur,
)

# Code du template email (voir seed.EMAIL_TEMPLATES + _EMAIL_PREF_MAP).
REPONSE_EMAIL_CODE = "reponse_communaute"

# Libellés de rôle affichés à côté d'une réponse.
_STATUT_ROLE_LABELS = {
    "copropriétaire_résident": "Copropriétaire",
    "copropriétaire_bailleur": "Copropriétaire",
    "locataire": "Locataire",
    "syndic": "Syndic",
    "mandataire": "Mandataire",
    "aidant": "Aidant",
    "admin_technique": "Admin technique",
}


def auteur_meta(auteur: Optional[Utilisateur], session: Session) -> dict:
    """Nom + bâtiment + rôle d'un auteur de réponse.

    est_cs=True pour CS/admin : leur réponse a plus de poids (tri prioritaire +
    mise en avant côté front).
    """
    if auteur is None:
        return {"auteur_nom": "Utilisateur supprimé", "auteur_batiment": None,
                "auteur_role": None, "est_cs": False}
    est_cs = auteur.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin)
    if auteur.has_role(RoleUtilisateur.conseil_syndical):
        role = "Conseil syndical"
    elif auteur.has_role(RoleUtilisateur.admin):
        role = "Administrateur"
    else:
        statut = auteur.statut.value if auteur.statut is not None else ""
        role = _STATUT_ROLE_LABELS.get(statut, statut or None)
    batiment = None
    if auteur.batiment_id is not None:
        bat = session.get(Batiment, auteur.batiment_id)
        if bat:
            batiment = f"Bât. {bat.numero}"
    return {
        "auteur_nom": f"{auteur.prenom} {auteur.nom}",
        "auteur_batiment": batiment,
        "auteur_role": role,
        "est_cs": est_cs,
    }


def enrich_reponse(rep, session: Session) -> dict:
    """Sérialise une réponse (ReponseCommunaute ou CommentaireSondage) + auteur."""
    auteur = session.get(Utilisateur, rep.auteur_id)
    return {
        "id": rep.id,
        "auteur_id": rep.auteur_id,
        "contenu": rep.contenu,
        "cree_le": rep.cree_le,
        **auteur_meta(auteur, session),
    }


def tri_reponses(reponses: list[dict]) -> list[dict]:
    """CS/admin d'abord (plus de poids), puis du plus ancien au plus récent."""
    return sorted(reponses, key=lambda x: (not x["est_cs"], x["cree_le"]))


#  `_pref` a disparu le 14/08/2026 (#339). Il lisait `communaute_app`, l'un des
#  quatre réglages de notification DANS L'APPLICATION — supprimés avec la matrice.
#  Ces notifications restent actives, ce qui était déjà leur valeur par défaut :
#  la condition est donc devenue toujours vraie, et on la retire plutôt que de la
#  laisser mentir. Seul l'e-mail se règle désormais, par bâtiment
#  (`utils/preferences_mail.py`).

def _site_url(session: Session) -> str:
    row = session.get(ConfigSite, "site_url")
    return (row.valeur if row else "https://localhost").rstrip("/")


def notifier_nouvelle_reponse(
    session: Session,
    background_tasks: BackgroundTasks,
    *,
    createur_id: Optional[int],
    auteur: Utilisateur,
    rubrique_label: str,
    sujet: str,
    extrait: str,
    lien_path: str,
) -> None:
    """Notifie le créateur d'un contenu (idée/annonce/sondage) d'une nouvelle réponse.

    - In-app : Notification (respecte la préférence communaute_app).
    - Email  : send_email(code=reponse_communaute) (respecte communaute_mail via
      destinataire_id — l'utilisateur qui s'y est opposé ne reçoit rien).
    On ne notifie jamais l'auteur de sa propre réponse.
    """
    if not createur_id or createur_id == auteur.id:
        return
    createur = session.get(Utilisateur, createur_id)
    if not createur:
        return

    extrait = (extrait or "").strip()
    session.add(Notification(
        destinataire_id=createur_id,
        type="communaute_reponse",
        titre=f"Nouvelle réponse sur {rubrique_label}",
        corps=extrait[:200],
        lien=lien_path,
    ))

    if createur.email:
        # send_email importé paresseusement (comme tickets.py) — évite un import
        # lourd au chargement du module et les cycles.
        from app.utils.email import send_email
        ctx = {
            "reponse": {
                "auteur": f"{auteur.prenom} {auteur.nom}",
                "rubrique_label": rubrique_label,
                "sujet": sujet,
                "extrait": extrait[:300],
                "lien": f"{_site_url(session)}{lien_path}",
            }
        }
        background_tasks.add_task(
            send_email,
            code=REPONSE_EMAIL_CODE,
            to=createur.email,
            context=ctx,
            destinataire_id=createur_id,
        )


# Code du template email pour un changement de statut d'idée.
IDEE_STATUT_EMAIL_CODE = "idee_statut"


def notifier_votants_idee(
    session: Session,
    background_tasks: BackgroundTasks,
    *,
    votant_ids: list[int],
    idee_titre: str,
    statut_label: str,
    lien_path: str = "/sondages",
    exclure_id: Optional[int] = None,
) -> None:
    """Notifie les votants d'une idée qu'elle a changé de statut (retenue/réalisée).

    In-app (préférence communaute_app) + email (préférence communaute_mail). On
    ne notifie qu'une fois chaque votant et jamais l'auteur de l'action.
    """
    site_url = _site_url(session)
    for uid in {u for u in votant_ids if u and u != exclure_id}:
        dest = session.get(Utilisateur, uid)
        if not dest:
            continue
        session.add(Notification(
            destinataire_id=uid,
            type="communaute_idee",
            titre=f"Une idée que vous avez soutenue est {statut_label.lower()}",
            corps=idee_titre[:200],
            lien=lien_path,
        ))
        if dest.email:
            from app.utils.email import send_email
            ctx = {"idee": {
                "titre": idee_titre,
                "statut_label": statut_label,
                "lien": f"{site_url}{lien_path}",
            }}
            background_tasks.add_task(
                send_email,
                code=IDEE_STATUT_EMAIL_CODE,
                to=dest.email,
                context=ctx,
                destinataire_id=uid,
            )
