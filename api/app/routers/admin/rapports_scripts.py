"""Admin — canal machine-à-machine des scripts d'exploitation.

Les scripts cron des nœuds (`maintenance.sh`, `bascule.sh`, `export-hors-site.sh`,
`check-reliability.sh`) déposent leurs rapports et lisent leurs dates ici. C'est le
SEUL endroit de l'API authentifié par un **secret partagé** et non par une session :
ces appels n'ont pas d'utilisateur.

Extrait de `exploitation.py` le 11/08/2026, au fil de l'eau — le fichier atteignait
542 lignes et le garde-fou de modularité a refusé le push, à raison. La frontière
n'est pas arbitraire : ces deux routes ont une raison de changer qui leur est
propre (le protocole des scripts), et un régime d'authentification qui n'est celui
d'aucune autre route du projet. Les isoler rend ce régime visible plutôt que noyé
au milieu d'endpoints protégés par `require_admin`.
"""
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.config import get_settings
from app.database import get_session
from app.models.core import HistoriqueMaintenance

from .exploitation import _purger_anciens_rapports

router = APIRouter()


class RapportMaintenance(BaseModel):
    statut: str = "succes"
    tokens_supprimes: int = 0
    taille_db_octets: Optional[int] = None
    duree_secondes: Optional[int] = None
    erreur: Optional[str] = None
    declenchee_par: str = "cron"
    cree_le: Optional[datetime] = None
    terminee_le: Optional[datetime] = None
    # Ajoutés en v2.32 — un rapport sans ces champs reste valide (défauts
    # identiques au comportement d'avant), donc un nœud dont le script n'a pas
    # encore été redéployé continue d'être accepté.
    tache: str = "maintenance"
    noeud: Optional[str] = None                # rpi1 | rpi2
    portee: str = "applicative"                # applicative | hygiene_locale
    details: Optional[dict] = None             # chiffres propres à la tâche


def _exiger_cle_maintenance(cle_recue: Optional[str]) -> None:
    """Vérifie la clé partagée des scripts d'exploitation.

    Extrait de `maintenance_rapport` le 11/08/2026, quand un second endpoint a eu
    besoin du même contrôle : recopier trois lignes d'authentification est la
    façon la plus courante de laisser l'une des deux copies s'assouplir.

    Ce canal n'est PAS une session : il n'autorise que les scripts cron des nœuds,
    qui lisent la clé dans `/opt/5hostachy/.env`. Il ne donne accès à aucune
    donnée de copropriétaire — uniquement aux dates d'exécution des tâches.
    """
    settings = get_settings()
    if not settings.maintenance_key:
        raise HTTPException(status_code=503, detail="Maintenance reporting non configuré (MAINTENANCE_KEY vide)")
    if cle_recue != settings.maintenance_key:
        raise HTTPException(status_code=403, detail="Clé maintenance invalide")


@router.get("/maintenance/dernier-rapport")
def maintenance_dernier_rapport(
    tache: str = "maintenance",
    x_maintenance_key: Optional[str] = Header(default=None, alias="x-maintenance-key"),
    session: Session = Depends(get_session),
):
    """Date du dernier rapport reçu, par nœud, pour UNE tâche.

    **Pourquoi cette route existe** (11/08/2026). Deux sondes indépendantes
    mesurent la maintenance hebdomadaire et se contredisaient sans que personne
    ne les confronte :

      - le **journal du nœud** — `check-reliability.sh` C17 y lit la ligne
        « Garde-fou » horodatée, et savait que la maintenance avait tourné ;
      - la **base** — l'écran d'administration n'y trouvait aucun rapport et
        affichait « Aucun rapport reçu », en rouge, depuis des jours.

    Les deux disaient vrai : le script tournait, et son rapport n'arrivait pas
    (la rotation des journaux déliait son propre inode et tuait le script avant
    l'envoi — corrigé en v2.46.8). Mais aucun contrôle ne comparait les deux, si
    bien que le seul symptôme était un badge rouge illisible, qu'on pouvait aussi
    bien attribuer à une tâche qui n'avait pas tourné.

    `check-reliability.sh` C19 interroge donc cette route pour dire la différence
    (`standards/04-fiabilite-des-controles.md` : deux sondes indépendantes, et
    c'est leur DÉSACCORD qui porte l'information).

    Authentifiée par la clé des scripts, pas par une session : le contrôle tourne
    en cron sur les nœuds, sans utilisateur. Elle ne rend que des dates
    d'exécution — aucune donnée personnelle.
    """
    _exiger_cle_maintenance(x_maintenance_key)
    lignes = session.exec(
        select(HistoriqueMaintenance)
        .where(HistoriqueMaintenance.tache == tache)
        .order_by(HistoriqueMaintenance.cree_le.desc())
        .limit(50)
    ).all()
    par_noeud: dict = {}
    for ligne in lignes:
        cle = ligne.noeud or "inconnu"
        if cle not in par_noeud:      # la première vue est la plus récente
            par_noeud[cle] = ligne.cree_le
    return {"tache": tache, "noeuds": par_noeud, "genere_le": datetime.utcnow()}


@router.post("/maintenance/rapport", status_code=201)
def maintenance_rapport(
    body: RapportMaintenance,
    x_maintenance_key: Optional[str] = Header(default=None, alias="x-maintenance-key"),
    session: Session = Depends(get_session),
):
    _exiger_cle_maintenance(x_maintenance_key)
    entry = HistoriqueMaintenance(
        tache=body.tache,
        noeud=body.noeud,
        portee=body.portee,
        declenchee_par=body.declenchee_par,
        statut=body.statut,
        tokens_supprimes=body.tokens_supprimes,
        taille_db_octets=body.taille_db_octets,
        duree_secondes=body.duree_secondes,
        details=json.dumps(body.details, ensure_ascii=False) if body.details else None,
        erreur=body.erreur,
        cree_le=body.cree_le or datetime.utcnow(),
        terminee_le=body.terminee_le,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    _purger_anciens_rapports(session)
    return entry
