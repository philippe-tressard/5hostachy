"""Le manuel utilisateur en PDF (#651).

Une seule route, et un choix à expliquer : **elle est publique**, comme
`/manuel-utilisateur.html` que le front sert déjà sans authentification. Un
manuel qui explique comment se servir du site doit pouvoir être lu avant de
savoir s'en servir — et il ne contient aucune donnée : ni nom, ni adresse, ni
contenu de la copropriété, seulement la description des écrans.

⚠️ Le PDF ne réécrit rien : il met en page le manuel **tel qu'il est servi**.
Voir `utils/manuel_pdf` pour le pourquoi.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session

from app.database import get_session
from app.utils.manuel_pdf import ManuelIndisponible, generer_manuel_pdf

router = APIRouter(prefix="/manuel", tags=["manuel"])


@router.get("/pdf")
def manuel_pdf(session: Session = Depends(get_session)):
    """Le manuel complet, avec page de garde, sommaire et mentions."""
    from app.routers.tickets.commun import config_site

    cfg = config_site(session)
    site_nom = cfg.get("site_nom") or "5Hostachy"
    site_url = (cfg.get("site_url") or "https://5hostachy.fr").rstrip("/")

    try:
        pdf = generer_manuel_pdf(site_nom, site_url)
    except ManuelIndisponible as exc:
        #  🔴 502 et non 500 : la panne est CHEZ LE VOISIN, pas ici. Le message
        #  le dit, parce qu'un « erreur interne » enverrait chercher le défaut
        #  au mauvais endroit — la leçon du 26/07/2026 sur la panne de chemin
        #  confondue avec la panne d'un nœud.
        raise HTTPException(502, f"Manuel indisponible : {exc}") from exc

    nom = f"manuel-utilisateur-{site_nom.lower().replace(' ', '-')}-{date.today():%Y-%m-%d}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{nom}"'},
    )
