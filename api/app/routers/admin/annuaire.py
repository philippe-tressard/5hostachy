"""Admin — Annuaire public, composition du conseil syndical et du syndic.

Extrait de `admin.py` (2057 lignes) le 06/08/2026, sans modification de logique.
Voir `__init__.py` pour la règle de découpage.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from app.auth.deps import get_current_user, require_cs_or_admin
from app.database import get_session
from app.models.core import (
    AgCsInfo,
    Batiment,
    ConfigSite,
    MembreCS,
    MembreSyndic,
    SyndicInfo,
    Utilisateur,
)
#  Importé sous un autre nom : plusieurs de ces fonctions affectent une variable
#  LOCALE `site_manager_user_id`, et l'import serait alors masqué. C'est la raison
#  d'être de l'ancien alias `_get_site_manager_user_id`, supprimé au découpage.
from app.utils.destinataires import site_manager_user_id as _site_manager_user_id
from app.utils.syndic import nom_du_syndic, source_du_nom
from typing import Optional

router = APIRouter()


# ── Annuaire public ──────────────────────────────────────────────────────────

@router.get("/annuaire")
def annuaire(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(get_current_user),
):
    """Équipe accessible à tous les résidents : membres CS + syndic depuis les tables dédiées."""
    # ── CS ──
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

    cs_out = [
        {
            "id": m.id,
            "genre": m.genre,
            "prenom": m.prenom,
            "nom": m.nom,
            "batiment_nom": _bat_nom(m.batiment_id),
            "etage": m.etage,
            "est_gestionnaire_site": bool(
                m.est_gestionnaire_site or (site_manager_user_id is not None and m.user_id == site_manager_user_id)
            ),
            "est_president": m.est_president,
            "photo_url": _user_photo(m.user_id),
        }
        for m in membres_cs_sorted
    ]

    # ── Syndic ──
    syndic_info = session.exec(select(SyndicInfo)).first()
    membres_syndic_raw = session.exec(select(MembreSyndic)).all()
    membres_syndic_sorted = sorted(
        membres_syndic_raw,
        key=lambda m: m.ordre,
    )
    syndic_membres_out = [
        {
            "id": m.id,
            "genre": m.genre,
            "prenom": m.prenom,
            "nom": m.nom,
            "fonction": m.fonction,
            "email": m.email,
            "telephone": m.telephone,
            "est_principal": m.est_principal,
            "photo_url": _user_photo(m.user_id),
        }
        for m in membres_syndic_sorted
    ]

    return {
        "cs": {
            "ag_annee": ag.ag_annee if ag else None,
            "ag_date": ag.ag_date.isoformat() if (ag and ag.ag_date) else None,
            "membres": cs_out,
        },
        "syndic": {
            #  🔴 Le CONTRAT fait foi (#535) : le nom vivait ici en texte libre
            #  ET dans `syndic_contrat_id → ContratEntretien → Prestataire.nom`.
            #  Changer de syndic dans Prestataires ne mettait à jour ni cet
            #  écran ni la fiche arrivant. Une seule source désormais.
            "nom_syndic": nom_du_syndic(session),
            #  L'écran doit savoir si la saisie sert encore : un champ sans
            #  effet qui ne le dit pas fait corriger un texte que personne ne lit.
            "nom_syndic_source": source_du_nom(session),
            "adresse": syndic_info.adresse if syndic_info else "",
            "site_web": syndic_info.site_web if syndic_info else None,
            "membres": syndic_membres_out,
        },
        "whatsapp_url": (
            session.exec(select(ConfigSite).where(ConfigSite.cle == "whatsapp_community_url")).first()
            or ConfigSite(cle="", valeur="")
        ).valeur or None,
    }


# ── Annuaire CS — gestion (CS + admin) ──────────────────────────────────────

class MembreCSIn(BaseModel):
    genre: str
    prenom: str
    nom: str
    batiment_id: Optional[int] = None
    etage: Optional[int] = None
    est_president: bool = False
    user_id: Optional[int] = None

class CompositionCSIn(BaseModel):
    ag_annee: Optional[int] = None
    ag_date: Optional[str] = None   # ISO "YYYY-MM-DD" ou None
    whatsapp_url: Optional[str] = None
    membres: list[MembreCSIn] = []

@router.get("/annuaire/cs")
def get_composition_cs(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    ag = session.exec(select(AgCsInfo)).first()
    membres = session.exec(select(MembreCS).order_by(MembreCS.ordre)).all()
    site_manager_user_id = _site_manager_user_id(session)
    _bat_cache: dict[int, str] = {}
    def _bat_nom_cs(bid: Optional[int]) -> Optional[str]:
        if bid is None:
            return None
        if bid not in _bat_cache:
            bat = session.get(Batiment, bid)
            _bat_cache[bid] = bat.numero if bat else str(bid)
        return _bat_cache[bid]
    return {
        "ag_annee": ag.ag_annee if ag else None,
        "ag_date": ag.ag_date.isoformat() if (ag and ag.ag_date) else None,
        "whatsapp_url": (
            session.exec(select(ConfigSite).where(ConfigSite.cle == "whatsapp_community_url")).first()
            or ConfigSite(cle="", valeur="")
        ).valeur or "",
        "membres": [
            {
                "id": m.id,
                "genre": m.genre,
                "prenom": m.prenom,
                "nom": m.nom,
                "batiment_id": m.batiment_id,
                "batiment_nom": _bat_nom_cs(m.batiment_id),
                "etage": m.etage,
                "est_gestionnaire_site": bool(
                    m.est_gestionnaire_site or (site_manager_user_id is not None and m.user_id == site_manager_user_id)
                ),
                "est_president": m.est_president,
                "ordre": m.ordre,
                "user_id": m.user_id,
            }
            for m in membres
        ],
    }

@router.put("/annuaire/cs")
def put_composition_cs(
    body: CompositionCSIn,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    # Valider qu'il y a au maximum 1 président
    presidents_count = sum(1 for mb in body.membres if mb.est_president)
    if presidents_count > 1:
        raise HTTPException(status_code=400, detail="Il ne peut y avoir qu'un seul président du Conseil Syndical.")

    # Upsert AgCsInfo
    from datetime import date as date_type
    ag = session.exec(select(AgCsInfo)).first()
    if ag is None:
        ag = AgCsInfo()
        session.add(ag)
    ag.ag_annee = body.ag_annee
    ag.ag_date = date_type.fromisoformat(body.ag_date) if body.ag_date else None

    # WhatsApp URL
    wa_cfg = session.exec(select(ConfigSite).where(ConfigSite.cle == "whatsapp_community_url")).first()
    if wa_cfg is None:
        wa_cfg = ConfigSite(cle="whatsapp_community_url", valeur="")
        session.add(wa_cfg)
    wa_cfg.valeur = body.whatsapp_url or ""

    # Remplacer tous les membres CS
    old = session.exec(select(MembreCS)).all()
    for m in old:
        session.delete(m)
    session.flush()

    for i, mb in enumerate(body.membres):
        session.add(MembreCS(
            genre=mb.genre,
            prenom=mb.prenom,
            nom=mb.nom,
            batiment_id=mb.batiment_id,
            etage=mb.etage,
            est_gestionnaire_site=False,
            est_president=mb.est_president,
            ordre=i,
            user_id=mb.user_id,
        ))

    session.commit()
    return {"ok": True}


# ── Annuaire Syndic — gestion (CS + admin) ──────────────────────────────────

class MembreSyndicIn(BaseModel):
    genre: str
    prenom: str
    nom: str
    fonction: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    est_principal: bool = False
    user_id: Optional[int] = None

class SyndicIn(BaseModel):
    nom_syndic: str = ""
    adresse: str = ""
    site_web: Optional[str] = None
    membres: list[MembreSyndicIn] = []

@router.get("/annuaire/syndic")
def get_syndic_info(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    syndic = session.exec(select(SyndicInfo)).first()
    membres = session.exec(select(MembreSyndic).order_by(MembreSyndic.ordre)).all()
    return {
        "nom_syndic": nom_du_syndic(session),
        "nom_syndic_source": source_du_nom(session),
        "adresse": syndic.adresse if syndic else "",
        "site_web": syndic.site_web if syndic else None,
        "membres": [
            {
                "id": m.id,
                "genre": m.genre,
                "prenom": m.prenom,
                "nom": m.nom,
                "fonction": m.fonction,
                "email": m.email,
                "telephone": m.telephone,
                "est_principal": m.est_principal,
                "ordre": m.ordre,
                "user_id": m.user_id,
            }
            for m in membres
        ],
    }

@router.put("/annuaire/syndic")
def put_syndic_info(
    body: SyndicIn,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    # Upsert SyndicInfo
    syndic = session.exec(select(SyndicInfo)).first()
    if syndic is None:
        syndic = SyndicInfo()
        session.add(syndic)
    #  🔴 La saisie n'écrase PAS le repli quand le contrat fait foi (#535).
    #
    #  L'écran désactive le champ dans ce cas, et renvoie donc la valeur qu'il a
    #  reçue — celle du CONTRAT. L'enregistrer ici remplacerait la saisie
    #  d'origine par le nom du contrat : le repli cesserait d'être un repli, et
    #  retirer le contrat plus tard ferait réapparaître une valeur qui n'a jamais
    #  été saisie.
    #
    #  ⚠️ La règle vit ICI et pas dans l'écran : un second écran, ou un appel
    #  direct, contournerait un garde posé côté front. C'est le serveur qui
    #  décide de ce qu'il écrit.
    if source_du_nom(session) != "contrat":
        syndic.nom_syndic = body.nom_syndic
    syndic.adresse = body.adresse
    syndic.site_web = body.site_web

    # Remplacer tous les membres syndic
    old = session.exec(select(MembreSyndic)).all()
    for m in old:
        session.delete(m)
    session.flush()

    for i, mb in enumerate(body.membres):
        session.add(MembreSyndic(
            genre=mb.genre,
            prenom=mb.prenom,
            nom=mb.nom,
            fonction=mb.fonction,
            email=mb.email,
            telephone=mb.telephone,
            est_principal=mb.est_principal,
            ordre=i,
            user_id=mb.user_id,
        ))

    session.commit()
    return {"ok": True}
