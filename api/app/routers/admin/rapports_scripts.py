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
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.config import get_settings
from app.database import get_session
from app.models.core import HistoriqueEmail, HistoriqueMaintenance

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


@router.get("/emails/echecs-recents")
def emails_echecs_recents(
    jours: int = 7,
    x_maintenance_key: Optional[str] = Header(default=None, alias="x-maintenance-key"),
    session: Session = Depends(get_session),
):
    """Combien d'e-mails ont échoué ces derniers jours, et de quels modèles.

    **Pourquoi cette route existe.** Le point 9 du pré-check MEP — « e-mails sans
    échec récent » — sortait `INCONNU` à *chaque* exécution : l'historique
    s'interroge in-process et exigeait une session admin, donc il fallait ouvrir
    l'écran à la main. Personne ne le faisait. Un contrôle qu'on ne fait jamais ne
    protège rien, et celui-là garde la seule trace d'une classe de défaut qui s'est
    reproduite **trois fois** : un e-mail dont le gabarit Jinja ne se rend pas part
    en échec **sans que rien ne remonte à l'expéditeur** — l'envoi est une
    `BackgroundTask`. Le 28/07/2026, six membres du conseil syndical n'ont rien
    reçu et cela ne se voyait nulle part ailleurs.

    **Ce qu'elle rend, et ce qu'elle ne rend pas.** Des comptes et des codes de
    modèles. **Jamais d'adresse ni de sujet** : ce canal est authentifié par un
    secret partagé, pas par une session, et il n'a aucune raison de laisser sortir
    une donnée personnelle pour répondre à « combien ». C'est la même discipline
    que `dernier-rapport`, qui ne rend que des dates.

    `total = 0` est la réponse attendue ; toute autre valeur fait échouer le point 9.
    """
    _exiger_cle_maintenance(x_maintenance_key)
    #  Borné : une valeur aberrante passée par un script ne doit pas balayer toute
    #  la table, que la purge garde à 90 jours.
    jours = max(1, min(int(jours), 90))
    depuis = datetime.utcnow() - timedelta(days=jours)

    lignes = session.exec(
        select(HistoriqueEmail)
        .where(HistoriqueEmail.statut == "erreur", HistoriqueEmail.cree_le >= depuis)
    ).all()

    par_code: dict[str, int] = {}
    for ligne in lignes:
        par_code[ligne.code] = par_code.get(ligne.code, 0) + 1

    return {
        "jours": jours,
        "total": len(lignes),
        "par_code": par_code,
        "dernier": max((l.cree_le for l in lignes), default=None),
        "genere_le": datetime.utcnow(),
    }


@router.get("/maintenance/cles-etrangeres")
def maintenance_cles_etrangeres(
    x_maintenance_key: Optional[str] = Header(default=None, alias="x-maintenance-key"),
):
    """Les lignes orphelines de la base — porte des SCRIPTS d'exploitation (#546).

    Même mesure que `GET /admin/db/cles-etrangeres`, autre authentification :
    la clé partagée que les crons lisent dans `/opt/5hostachy/.env`.

    ⚠️ **Elle reste dans la borne de ce canal** — « aucune donnée de
    copropriétaire » : noms de tables, noms de colonnes, comptes. Le `rowid`
    que rend `PRAGMA foreign_key_check` désignerait une ligne précise ; il
    n'est pas exposé (cf. `utils/diagnostic_cles.py`).

    🔴 Pourquoi cette seconde porte plutôt qu'un « admin OU clé » sur une seule
    route : une dépendance optionnelle et une auth conditionnelle sont la forme
    exacte dans laquelle un contournement se glisse sans se voir. Deux portes
    explicites, chacune avec sa serrure, et **une seule** mesure derrière.

    Elle existe pour que la surveillance soit CONTINUE : des orphelins peuvent
    réapparaître tant que les 21 endpoints DELETE non testés n'ont pas été
    éprouvés. Ce qui est critique en continu ne se vérifie pas qu'en MEP.
    """
    _exiger_cle_maintenance(x_maintenance_key)

    from app.database import engine
    from app.utils.diagnostic_cles import compter_orphelins

    return compter_orphelins(engine)
