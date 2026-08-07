"""Admin — Accueil d'un arrivant, baux locatifs et fiche d'arrivée.

Extrait de `admin.py` (2057 lignes) le 06/08/2026, sans modification de logique.
Voir `__init__.py` pour la règle de découpage.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from app.auth.deps import get_current_user, require_cs_or_admin
from app.database import get_session
from app.models.core import (
    AgCsInfo,
    Batiment,
    ConfigSite,
    LocationBail,
    MembreCS,
    MembreSyndic,
    Notification,
    StatutBail,
    StatutUtilisateur,
    SyndicInfo,
    Utilisateur,
)
#  Importé sous un autre nom : plusieurs de ces fonctions affectent une variable
#  LOCALE `site_manager_user_id`, et l'import serait alors masqué. C'est la raison
#  d'être de l'ancien alias `_get_site_manager_user_id`, supprimé au découpage.
from app.utils.destinataires import site_manager_user_id as _site_manager_user_id
from datetime import datetime
from html import escape
from typing import Optional

router = APIRouter()


class AccueilArrivantBody(BaseModel):
    batiment: Optional[str] = None
    ancien_resident: Optional[str] = None
    ancien_resident_inconnu: bool = False


def _declencher_accueil_arrivant(
    user: Utilisateur,
    body: AccueilArrivantBody,
    background_tasks: BackgroundTasks,
    session: Session,
    allow_repeat: bool = False,
):
    """Déclenche les actions d'accueil pour un nouvel arrivant résidentiel."""
    if not user.actif:
        raise HTTPException(400, "Le compte doit être actif pour déclarer un nouvel arrivant")

    statuts_residentiels = {
        StatutUtilisateur.copropriétaire_résident,
        StatutUtilisateur.copropriétaire_bailleur,
        StatutUtilisateur.locataire,
    }
    if user.statut not in statuts_residentiels:
        raise HTTPException(400, "Cette démarche est réservée aux profils résidentiels")

    if not allow_repeat:
        deja_declenche = session.exec(
            select(Notification).where(
                Notification.destinataire_id == user.id,
                Notification.titre == "Bienvenue dans la résidence !",
            )
        ).first()
        if deja_declenche:
            raise HTTPException(409, "La démarche Nouvel Arrivant a déjà été déclarée pour ce compte")

    nom_complet = f"{user.prenom} {user.nom}"
    bat = body.batiment or ""
    ancien = body.ancien_resident or ""
    bat_str = f", {bat}" if bat else ""
    ancien_str = f" (ancien résident : {ancien})" if ancien else ""
    nb_notifs = 0

    # ── A. Notification unique regroupée → arrivant ───────────────────────────
    demarches: list[str] = []

    # Syndic principal (pour l'email BAL)
    syndic_principal: MembreSyndic | None = session.exec(
        select(MembreSyndic).where(
            MembreSyndic.est_principal == True  # noqa: E712
        )
    ).first()
    if syndic_principal:
        demarches.append(
            f"• Demande d'étiquette boîte aux lettres transmise au syndic{bat_str}{ancien_str}."
        )

    # CS du bâtiment + gestionnaire du site (pour les notifs interphone)
    cs_query = select(MembreCS).where(MembreCS.user_id != None)  # noqa: E711
    site_manager_user_id = _site_manager_user_id(session)
    if user.batiment_id:
        cs_filters = (MembreCS.batiment_id == user.batiment_id)
        if site_manager_user_id is not None:
            cs_filters = cs_filters | (MembreCS.user_id == site_manager_user_id)
        cs_members = session.exec(cs_query.where(cs_filters)).all()
    else:
        if site_manager_user_id is not None:
            cs_members = session.exec(cs_query.where(MembreCS.user_id == site_manager_user_id)).all()
        else:
            cs_members = []
    # Dédoublonner par user_id
    cs_seen: set[int] = set()
    cs_unique: list[MembreCS] = []
    for mc in cs_members:
        if mc.user_id not in cs_seen:
            cs_seen.add(mc.user_id)
            cs_unique.append(mc)

    if cs_unique:
        demarches.append(
            f"• Demande d'ajout sur l'interphone transmise au Conseil Syndical{bat_str}{ancien_str}."
        )

    # Corps en HTML : `safeRichContent()` côté front bascule en mode HTML dès qu'une
    # balise est détectée et ne convertit alors plus les `\n` en `<br>`. Tout le
    # corps doit donc être structuré, sinon l'ajout du lien écraserait la mise en
    # forme. Bénéfice au passage : les `**gras**` de l'ancienne version, qui
    # s'affichaient avec leurs astérisques (aucun rendu markdown côté front),
    # deviennent de vrais `<strong>`.
    demarches_html = ""
    if demarches:
        # Les puces arrivent préfixées « • » (format texte) — on les retire au
        # profit d'un vrai <ul>.
        items = "".join(f"<li>{escape(d.lstrip('• ').strip())}</li>" for d in demarches)
        demarches_html = (
            "<p><strong>Démarches initiées en votre nom</strong></p>"
            f"<ul>{items}</ul>"
        )

    # La fiche d'accueil n'était référencée NULLE PART dans le parcours : cette
    # notification affirmait que « l'ensemble des consignes est disponible dans
    # l'application » sans le moindre lien, et son champ `lien` pointait sur `/`.
    # L'arrivant devait donc tomber par hasard sur la carte du tableau de bord.
    # Même chemin que celle-ci (`tableau-de-bord/+page.svelte`).
    FICHE_URL = "/api/admin/fiche-arrivant"

    session.add(Notification(
        destinataire_id=user.id,
        type="system",
        titre="Bienvenue dans la résidence !",
        corps=(
            f"<p>Bienvenue {escape(user.prenom)} ! Nous sommes heureux de vous "
            "accueillir dans notre résidence. Vous trouverez dans cette application "
            "toutes les informations pratiques : actualités, documents, contacts "
            "et services.</p>"
            "<p><strong>Consignes de la copropriété</strong><br>"
            "Règlement intérieur, consignes de tri, modalités d'accès, "
            "stationnement et contacts utiles sont réunis dans votre fiche "
            f'd\'accueil : <a href="{FICHE_URL}" target="_blank" rel="noopener">'
            "consulter les consignes de la copropriété</a>.</p>"
            + demarches_html
        ),
        lien=FICHE_URL,
    ))
    nb_notifs += 1

    # ── B. Notification interphone → CS du bâtiment + gestionnaire du site ─────
    for mc in cs_unique:
        session.add(Notification(
            destinataire_id=mc.user_id,
            type="system",
            titre="Accueil — Demande d'ajout sur l'interphone",
            corps=(
                f"Merci d'ajouter le nom **{nom_complet}**{bat_str}{ancien_str} "
                "sur l'interphone du bâtiment concerné."
            ),
        ))
        nb_notifs += 1

    # ── C. E-mail BAL → syndic principal (CC arrivant) ────────────────────────
    if syndic_principal and syndic_principal.email:
        from app.utils.email import send_email

        # Lire reference_copro pour le sujet
        ref_copro_row = session.get(ConfigSite, "reference_copro")
        ref_copro = (ref_copro_row.valeur if ref_copro_row else "").strip()

        ctx = {
            "nom_complet": nom_complet,
            "batiment": bat,
            "ancien_resident": ancien,
            "reference_copro": ref_copro,
        }
        # Email individuel au syndic
        background_tasks.add_task(
            send_email,
            code="nouvel_arrivant_bal",
            to=syndic_principal.email,
            context=ctx,
            session=session,
            destinataire_id=syndic_principal.user_id,
        )
        # Copie à l'arrivant
        if user.email:
            background_tasks.add_task(
                send_email,
                code="nouvel_arrivant_bal",
                to=user.email,
                context=ctx,
                session=session,
                destinataire_id=user.id,
            )

    # ── Persister le choix en base ───────────────────────────────────────────
    user.demarche_arrivant = "nouvel_arrivant"

    session.commit()
    return {
        "ok": True,
        "notifications_envoyees": nb_notifs,
        "email_syndic": bool(syndic_principal and syndic_principal.email),
    }

@router.post("/utilisateurs/{user_id}/accueil-arrivant")
def accueil_arrivant(
    user_id: int,
    body: AccueilArrivantBody,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_cs_or_admin),
):
    """Déclenche les actions d'accueil pour un nouvel arrivant résidentiel (CS/Admin)."""
    user = session.get(Utilisateur, user_id)
    if not user:
        raise HTTPException(404, "Utilisateur introuvable")
    return _declencher_accueil_arrivant(user, body, background_tasks, session, allow_repeat=True)


@router.post("/me/accueil-arrivant")
def accueil_arrivant_me(
    body: AccueilArrivantBody,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Self-service : l'utilisateur déclare lui-même son arrivée dans la résidence."""
    ancien = (body.ancien_resident or "").strip()
    if not ancien and not body.ancien_resident_inconnu:
        raise HTTPException(422, "Le nom de l'ancien résident est requis (ou cochez 'Je ne sais pas').")
    if body.ancien_resident_inconnu:
        body.ancien_resident = "Ne sait pas"
    return _declencher_accueil_arrivant(user, body, background_tasks, session, allow_repeat=False)
# ── Gestion manuelle des baux locatifs ────────────────────────────────────────

@router.post("/baux/{bail_id}/lier-locataire/{user_id}", response_model=dict)
def lier_locataire_bail(
    bail_id: int,
    user_id: int,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_cs_or_admin),
):
    """Admin : lier manuellement un locataire inscrit à un bail actif."""
    bail = session.get(LocationBail, bail_id)
    if not bail:
        raise HTTPException(404, "Bail introuvable")
    if bail.statut == StatutBail.termine:
        raise HTTPException(400, "Impossible de lier un locataire à un bail terminé")
    locataire = session.get(Utilisateur, user_id)
    if not locataire:
        raise HTTPException(404, "Utilisateur introuvable")
    bail.locataire_id = user_id
    session.add(bail)
    session.commit()
    return {"bail_id": bail.id, "locataire_id": user_id, "ok": True}


@router.get("/baux", response_model=list)
def list_baux(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Admin : liste de tous les baux actifs (pour validation manuelle)."""
    baux = session.exec(
        select(LocationBail).where(LocationBail.statut != StatutBail.termine)
    ).all()
    result = []
    for b in baux:
        locataire = session.get(Utilisateur, b.locataire_id) if b.locataire_id else None
        bailleur = session.get(Utilisateur, b.bailleur_id)
        result.append({
            "id": b.id,
            "lot_id": b.lot_id,
            "statut": b.statut,
            "locataire_email": b.locataire_email,
            "locataire_id": b.locataire_id,
            "locataire_nom": f"{locataire.prenom} {locataire.nom}" if locataire else None,
            "bailleur_id": b.bailleur_id,
            "bailleur_nom": f"{bailleur.prenom} {bailleur.nom}" if bailleur else "?",
            "date_entree": b.date_entree,
            "liaison_manquante": bool(b.locataire_email and not b.locataire_id),
        })
    return result


# ── Fiche arrivant (génération dynamique) ────────────────────────────────────

@router.get("/fiche-arrivant")
def get_fiche_arrivant(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(get_current_user),
):
    """Génère la fiche arrivant HTML à partir des données annuaire actuelles."""
    from datetime import date
    from fastapi.responses import HTMLResponse
    from app.utils.fiche_arrivant import generer_fiche_arrivant

    # Récupérer les données annuaire (même logique que GET /admin/annuaire)
    ag = session.exec(select(AgCsInfo)).first()
    membres_cs_raw = session.exec(select(MembreCS)).all()

    def _genre_order(g: str) -> int:
        return 0 if g in ("Mme", "Mlle") else 1

    membres_cs_sorted = sorted(
        membres_cs_raw,
        key=lambda m: (m.batiment_id or 9999, _genre_order(m.genre), m.nom.lower()),
    )

    batiments_cache: dict[int, str] = {}
    def _bat_nom(bid: Optional[int]) -> Optional[str]:
        if bid is None:
            return None
        if bid not in batiments_cache:
            bat = session.get(Batiment, bid)
            batiments_cache[bid] = bat.numero if bat else str(bid)
        return batiments_cache[bid]

    user_photo_cache: dict[int, Optional[str]] = {}
    def _user_photo(uid: Optional[int]) -> Optional[str]:
        if uid is None:
            return None
        if uid not in user_photo_cache:
            u = session.get(Utilisateur, uid)
            user_photo_cache[uid] = u.photo_url if u else None
        return user_photo_cache[uid]

    site_manager_user_id = _site_manager_user_id(session)

    cs_membres = [
        {
            "genre": m.genre,
            "prenom": m.prenom,
            "nom": m.nom,
            "batiment_nom": _bat_nom(m.batiment_id),
            "etage": m.etage,
            "est_gestionnaire_site": bool(
                m.est_gestionnaire_site or (site_manager_user_id and m.user_id == site_manager_user_id)
            ),
            "est_president": m.est_president,
            "photo_url": _user_photo(m.user_id),
        }
        for m in membres_cs_sorted
    ]

    syndic_info = session.exec(select(SyndicInfo)).first()
    membres_syndic_raw = session.exec(select(MembreSyndic)).all()
    syndic_membres = [
        {
            "genre": m.genre,
            "prenom": m.prenom,
            "nom": m.nom,
            "fonction": m.fonction,
            "email": m.email,
            "telephone": m.telephone,
            "est_principal": m.est_principal,
            "photo_url": _user_photo(m.user_id),
        }
        for m in sorted(membres_syndic_raw, key=lambda m: m.ordre)
    ]

    whatsapp_url = (
        session.exec(select(ConfigSite).where(ConfigSite.cle == "whatsapp_community_url")).first()
        or ConfigSite(cle="", valeur="")
    ).valeur or None

    html = generer_fiche_arrivant(
        cs_data={
            "ag_annee": ag.ag_annee if ag else None,
            "ag_date": ag.ag_date.isoformat() if (ag and ag.ag_date) else None,
            "membres": cs_membres,
        },
        syndic_data={
            "nom_syndic": syndic_info.nom_syndic if syndic_info else "",
            "adresse": syndic_info.adresse if syndic_info else "",
            "site_web": syndic_info.site_web if syndic_info else None,
            "membres": syndic_membres,
        },
        whatsapp_url=whatsapp_url,
        annee=date.today().year,
    )
    # Jamais de cache : la fiche est régénérée à chaque appel depuis l'annuaire
    # (membres du CS, syndic, date d'AG). Sans ces en-têtes, un navigateur pouvait
    # garder une copie et afficher une fiche périmée après une modification de
    # l'annuaire — ou après un correctif, ce qui a semé la confusion le 26/07/2026.
    # Le document contient en outre des données personnelles : on évite qu'il
    # traîne dans un cache partagé.
    return HTMLResponse(
        content=html,
        headers={"Cache-Control": "no-store, must-revalidate", "Pragma": "no-cache"},
    )
