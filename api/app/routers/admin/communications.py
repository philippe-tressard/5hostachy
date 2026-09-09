"""Admin — Historique des e-mails, modèles, notifications et télémétrie.

Extrait de `admin.py` (2057 lignes) le 06/08/2026, sans modification de logique.
Voir `__init__.py` pour la règle de découpage.
"""

import json
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

from app.utils.noeud import noeud_courant


def _variables_du_modele(modele: ModeleEmail) -> str:
    """Les variables que ce modèle emploie RÉELLEMENT, en JSON, pour l'écran.

    ## 🔴 Pourquoi ce n'est plus la colonne `variables_disponibles`

    Cette colonne était une **copie**, posée à la main par la migration qui créait
    le modèle et jamais reprise ensuite. Signalé par Philippe le 08/09/2026, en
    capture d'écran : `nouvel_arrivant_bal` venait de gagner trois variables
    (`role_destinataire`, `lien_consignes`, `destinataire`) et l'écran annonçait
    toujours les trois de la migration 0066 — celles de mars.

    Une liste recopiée diverge au premier enrichissement. Celle-ci avait six mois
    de retard, et **rien ne pouvait le dire** : le modèle et sa liste vivent dans
    la même ligne, personne ne les compare, et le contrat de variables du dépôt
    (`tests/test_email_templates.py`) ne lit que le code — pas la base.

    La conséquence n'était pas cosmétique : cet encart est ce qu'un membre du
    conseil lit **avant de modifier un modèle**. Il y voyait trois variables sur
    six, et aurait écrit un message amputé en croyant employer tout ce qui
    existe.

    ## Ce que ça retire

    Les variables du gabarit commun (`residence`, `app`, `annee`…) : elles sont
    injectées d'office par `email._contexte_rendu` et valent pour tous les
    modèles. Les annoncer ici les ferait passer pour propres à celui-ci.

    ⚠️ La liste est calculée sur le texte **en base**, pas sur celui du dépôt :
    c'est ce que la personne édite qui doit être décrit. Un modèle retouché
    depuis cet écran annonce donc ses propres variables, ce qui est exact.
    """
    #  🔴 La lecture elle-même vit dans `utils/email/variables.py` (#852) : elle
    #  était écrite ici, dans le contrôle quotidien et dans les tests, avec trois
    #  fois sa propre liste de variables du gabarit — celle d'ici en était une
    #  quatrième copie, locale à la fonction.
    from app.utils.email.variables import ModeleIllisible, variables_de

    try:
        return json.dumps(sorted(variables_de(modele.sujet, modele.corps_html)))
    except ModeleIllisible:
        #  Un modèle au Jinja invalide ne peut pas être analysé. Rendre la
        #  colonne stockée plutôt que rien : elle est peut-être périmée, mais
        #  l'écran doit continuer d'aider — et le modèle, lui, échouera à
        #  l'envoi, ce qui est le vrai signal.
        return modele.variables_disponibles or "[]"


@router.get("/modeles-email")
def list_modeles_email(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Les modèles, avec leurs variables **calculées** et non recopiées.

    La colonne `variables_disponibles` reste en base — quatre migrations figées
    l'écrivent — mais ce qui est SERVI est calculé. Une colonne qu'on n'affiche
    plus cesse de mentir sans qu'il faille la supprimer partout.
    """
    modeles = session.exec(select(ModeleEmail).order_by(ModeleEmail.code)).all()
    return [
        {**m.model_dump(), "variables_disponibles": _variables_du_modele(m)}
        for m in modeles
    ]


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
    #  🔴 `corps_texte` a QUITTÉ cette liste blanche le 08/09/2026, avec le champ
    #  de l'écran. Il était stocké, affiché, modifiable — et envoyé nulle part :
    #  aucun code ne le lisait, le gabarit produit toujours du HTML. Le laisser
    #  ici permettrait à un appelant direct de continuer d'écrire un texte que
    #  personne ne reçoit, et de croire l'avoir envoyé.
    #
    #  La colonne reste en base : quatre migrations figées l'écrivent, et la
    #  retirer casserait `alembic upgrade` sur une base neuve.
    allowed = {"sujet", "corps_html", "actif", "intention"}

    #  🔴 Un modèle illisible ne s'enregistre PAS (#852).
    #
    #  Ce champ est un `<textarea>` où l'on saisit du Jinja à la main : un
    #  `{% endif %}` de trop, un `{%` non refermé, et le modèle ne se rend plus.
    #  Rien ne le disait — ni ici, ni à l'envoi : `send_email` capture toute
    #  exception et n'en garde trace que dans `historique_email`. Le message
    #  cessait simplement de partir, et le contrôle quotidien lui-même lisait
    #  l'échec comme un écart de variables.
    #
    #  Le refus est le bon geste plutôt qu'une alerte a posteriori : la personne
    #  est DEVANT le texte, elle vient de l'écrire, et Jinja dit à quel caractère.
    #  Découvrir la même erreur le lendemain matin par un e-mail d'alerte n'a
    #  aucune commune mesure — c'est le contrôle qui remplace la prévention.
    from app.utils.email.variables import ModeleIllisible, variables_de

    #  Seuls les champs que la requête ÉCRIT sont relus. Reprendre ceux déjà en
    #  base fermerait la seule voie de réparation : une ligne dont le corps est
    #  cassé ne pourrait plus être touchée du tout, pas même pour la remettre
    #  d'aplomb — l'écran servirait à réparer et refuserait d'agir.
    try:
        variables_de(
            payload.get("sujet") if "sujet" in payload else None,
            payload.get("corps_html") if "corps_html" in payload else None,
        )
    except ModeleIllisible as illisible:
        raise HTTPException(
            422,
            f"Le champ « {illisible.champ} » contient du Jinja invalide : "
            f"{illisible.cause}. Le modèle n'est pas enregistré — il ne pourrait "
            "plus être envoyé, et l'échec ne se verrait que dans l'historique.",
        )

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


def _remettre_par_defaut(session: Session, modele: ModeleEmail, par_id: int) -> bool:
    """Remet UN modèle au texte du seed. Rend False si le code n'y est plus.

    Écrit une fois et appelée par les deux routes de réinitialisation — celle
    d'un modèle et celle de tous. Deux boucles jumelles auraient divergé sur
    l'intention exactement comme elles avaient divergé ailleurs : « remettre par
    défaut » doit remettre le bandeau aussi, sans quoi un modèle réinitialisé
    garderait une intention modifiée au-dessus d'un corps redevenu d'origine.
    """
    from app.seed import EMAIL_TEMPLATES, INTENTIONS_PAR_MODELE

    defaut = next((t for t in EMAIL_TEMPLATES if t[0] == modele.code), None)
    if not defaut:
        #  Un modèle que le code ne connaît plus n'a pas de version par défaut.
        return False
    _code, _libelle, sujet, corps_html, _desactivable = defaut
    modele.sujet = sujet
    modele.corps_html = corps_html
    modele.intention = INTENTIONS_PAR_MODELE.get(modele.code, "")
    modele.modifie_le = datetime.utcnow()
    modele.modifie_par_id = par_id
    session.add(modele)
    return True


@router.post("/modeles-email/{modele_id}/reinitialiser")
def reinitialiser_un_modele_email(
    modele_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Remet UN modèle au texte du code, sans toucher aux vingt-trois autres.

    🔴 Il n'existait que la remise à zéro **globale** (#852). Réparer un seul
    modèle — celui dont le Jinja a été cassé d'un caractère, celui qui a manqué
    un enrichissement — imposait donc de détruire les textes choisis pour tous
    les autres. C'est le genre de remède qu'on n'applique pas, et le défaut reste
    alors en place : le contrôle quotidien signale, et personne ne peut agir.
    """
    modele = session.get(ModeleEmail, modele_id)
    if not modele:
        raise HTTPException(404, "Modèle introuvable")
    if not _remettre_par_defaut(session, modele, _.id):
        raise HTTPException(
            422,
            f"Le code ne porte plus de version par défaut pour « {modele.code} » : "
            "ce modèle n'existe qu'en base, il n'y a rien à quoi le ramener.",
        )
    session.commit()
    session.refresh(modele)
    return modele


@router.post("/modeles-email/reinitialiser")
def reinitialiser_modeles_email(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Remet tous les modèles e-mail aux valeurs par défaut (seed)."""
    modeles = session.exec(select(ModeleEmail)).all()
    updated = sum(_remettre_par_defaut(session, m, _.id) for m in modeles)
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
