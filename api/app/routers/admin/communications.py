"""Admin — Historique des e-mails, modèles, notifications et télémétrie.

Extrait de `admin.py` (2057 lignes) le 06/08/2026, sans modification de logique.
Voir `__init__.py` pour la règle de découpage.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session, select
from app.auth.deps import get_current_user, require_admin
from app.database import get_session
from app.models.core import (
    HistoriqueEmail,
    HistoriqueTelemetrie,
    ModeleEmail,
    Notification,
    Utilisateur,
)
from datetime import datetime

router = APIRouter()


# ── Historique emails ─────────────────────────────────────────────────────────

@router.get("/emails/historique")
def emails_historique(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    return session.exec(
        select(HistoriqueEmail).order_by(HistoriqueEmail.cree_le.desc()).limit(10)
    ).all()


# ── Télémétrie — agrégation manuelle ──────────────────────────────────────────

@router.post("/telemetry/agreger", status_code=202)
def telemetry_agreger(
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Lance l'agrégation de la télémétrie en arrière-plan."""
    from app.utils.telemetry_aggregation import run_telemetry_aggregation
    entry = HistoriqueTelemetrie(declenchee_par="manuelle", noeud=noeud_courant())
    session.add(entry)
    session.commit()
    session.refresh(entry)
    background_tasks.add_task(run_telemetry_aggregation, entry.id)
    return {"message": "Agrégation lancée en arrière-plan", "id": entry.id}


@router.get("/telemetry/historique")
def telemetry_history(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    return session.exec(
        select(HistoriqueTelemetrie).order_by(HistoriqueTelemetrie.cree_le.desc()).limit(10)
    ).all()
# ── Modèles e-mail ────────────────────────────────────────────────────────────────────────

from app.models.core import ModeleEmail
from app.utils.noeud import noeud_courant


@router.get("/modeles-email")
def list_modeles_email(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    return session.exec(select(ModeleEmail).order_by(ModeleEmail.code)).all()


@router.patch("/modeles-email/{modele_id}")
def update_modele_email(
    modele_id: int,
    payload: dict,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    modele = session.get(ModeleEmail, modele_id)
    if not modele:
        raise HTTPException(404, "Modèle introuvable")
    allowed = {"sujet", "corps_html", "corps_texte", "actif", "intention"}
    for key, value in payload.items():
        if key not in allowed:
            continue
        # L'intention est rendue telle quelle dans le gabarit : liste blanche,
        # jamais la valeur reçue. `""` reste permis — c'est « aucun bandeau ».
        if key == "intention":
            from app.utils.email import INTENTIONS

            value = (value or "").strip()
            if value and value not in INTENTIONS:
                raise HTTPException(
                    422,
                    f"Intention inconnue : {value!r}. Valeurs admises : "
                    + ", ".join(sorted(INTENTIONS)),
                )
        setattr(modele, key, value)
    from datetime import datetime
    modele.modifie_le = datetime.utcnow()
    modele.modifie_par_id = _.id
    session.add(modele)
    session.commit()
    session.refresh(modele)
    return modele


@router.post("/modeles-email/reinitialiser")
def reinitialiser_modeles_email(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Remet tous les modèles e-mail aux valeurs par défaut (seed)."""
    from app.seed import EMAIL_TEMPLATES, INTENTIONS_PAR_MODELE
    updated = 0
    for code, libelle, sujet, corps_html, desactivable in EMAIL_TEMPLATES:
        modele = session.exec(
            select(ModeleEmail).where(ModeleEmail.code == code)
        ).first()
        if modele:
            modele.sujet = sujet
            modele.corps_html = corps_html
            # « Réinitialiser » doit tout remettre par défaut : l'intention
            # aussi, sans quoi un modèle réinitialisé garderait un bandeau
            # modifié au-dessus d'un corps redevenu celui d'origine.
            modele.intention = INTENTIONS_PAR_MODELE.get(code, "")
            modele.modifie_le = datetime.utcnow()
            modele.modifie_par_id = _.id
            session.add(modele)
            updated += 1
    session.commit()
    return {"message": f"{updated} modèles réinitialisés"}


# ── Notifications utilisateur ────────────────────────────────────────────────

@router.get("/notifications")
def mes_notifications(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    return session.exec(
        select(Notification)
        .where(Notification.destinataire_id == user.id)
        .order_by(Notification.cree_le.desc())
        .limit(50)
    ).all()


@router.post("/notifications/{notif_id}/lue")
def mark_lue(
    notif_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    notif = session.get(Notification, notif_id)
    if not notif or notif.destinataire_id != user.id:
        raise HTTPException(404, "Notification introuvable")
    notif.lue = True
    session.add(notif)
    session.commit()
    return {"ok": True}
