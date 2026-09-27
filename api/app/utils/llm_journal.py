"""Ce que coûte l'assistant IA — le journal, le plafond, la consommation.

## Pourquoi (#1383, 27/09/2026)

Trois usages appellent un modèle facturé au jeton, dont un **automatique** : la
mise en forme des réponses du syndic reçues par courriel (#1322), déclenchée par
la relève toutes les dix minutes. Rien n'était compté. Une boucle — un courriel
qui en déclenche un autre — aurait facturé en silence jusqu'à la facture.

## Ce que ce module porte, et ce qu'il ne porte pas

- **le journal** : une ligne par appel parti chez le fournisseur (ou refusé par
  le plafond), écrite par `llm.demander` et par lui seul ;
- **le plafond mensuel** de chaque usage, en jetons : atteint, l'appel est
  refusé AVANT l'envoi — l'usage automatique s'arrête, l'usage manuel reçoit un
  refus qui le dit ;
- **la consommation** par mois, usage et modèle, et son coût estimé au tarif
  que l'administrateur a saisi.

🔴 **Aucun tarif n'est écrit ici.** Les prix changent, et le modèle de chaque
usage se choisit dans l'administration : une grille codée en dur se périmerait
comme la liste de modèles retirée le 11/09. Sans tarif saisi, le coût est
`None` — jamais 0, qui se lirait « gratuit ».

⚠️ Des COMPTEURS, jamais du contenu (`app/models/ia.py`).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.core import ConfigSite
from app.models.ia import AppelIA
from app.utils import horloge
from app.utils.llm_usages import USAGES
from app.utils.montants import montant_fr

logger = logging.getLogger("hostachy.llm")

STATUT_SUCCES = "succes"
STATUT_ERREUR = "erreur"
#: Refusé avant l'envoi : le plafond mensuel de l'usage est atteint.
STATUT_PLAFOND = "plafond"

#: Le détail se garde treize mois : un an complet, plus le mois en cours, pour
#: comparer un mois à celui de l'an dernier. Purgé par la maintenance.
CONSERVATION_MOIS = 13


def jetons_de(charge: Any) -> tuple[Optional[int], Optional[int]]:
    """PURE. Les jetons (entrée, sortie) d'une réponse de fournisseur.

    Deux vocabulaires existent, et les trois fournisseurs les emploient tous
    deux selon l'API : `input_tokens`/`output_tokens` (Anthropic, OpenAI
    Responses) et `prompt_tokens`/`completion_tokens` (OpenAI et Azure Chat).
    Une réponse sans compteur rend `None` — l'écran dira « non communiqué ».
    """
    usage = charge.get("usage") if isinstance(charge, dict) else None
    if not isinstance(usage, dict):
        return None, None

    def entier(*cles: str) -> Optional[int]:
        for cle in cles:
            v = usage.get(cle)
            if isinstance(v, int) and not isinstance(v, bool):
                return v
        return None

    return entier("input_tokens", "prompt_tokens"), entier("output_tokens", "completion_tokens")


def debut_du_mois(maintenant: datetime) -> datetime:
    return maintenant.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _reglage(session: Session, cle: str) -> int:
    """Un réglage entier de l'administration ; 0 s'il est absent ou illisible."""
    ligne = session.exec(select(ConfigSite).where(ConfigSite.cle == cle)).first()
    try:
        return max(0, int((ligne.valeur if ligne else "") or 0))
    except (TypeError, ValueError):
        return 0


def plafond_mensuel(session: Session, usage: str) -> int:
    """Le plafond de jetons du mois pour cet usage ; 0 = aucun plafond."""
    return _reglage(session, USAGES[usage].cle("plafond_mois"))


def consommes_du_mois(session: Session, usage: str, maintenant: datetime) -> int:
    """Les jetons (entrée + sortie) consommés par cet usage depuis le 1er du mois."""
    total = session.exec(
        select(
            func.coalesce(func.sum(AppelIA.jetons_entree), 0)
            + func.coalesce(func.sum(AppelIA.jetons_sortie), 0)
        ).where(
            AppelIA.usage == usage,
            AppelIA.statut == STATUT_SUCCES,
            AppelIA.cree_le >= debut_du_mois(maintenant),
        )
    ).one()
    return int(total or 0)


def plafond_atteint(session: Session, usage: str) -> Optional[str]:
    """Le message de refus si le plafond mensuel est atteint, sinon `None`."""
    plafond = plafond_mensuel(session, usage)
    if not plafond:
        return None
    consommes = consommes_du_mois(session, usage, horloge.maintenant())
    if consommes < plafond:
        return None
    return (
        f"Plafond mensuel atteint pour « {USAGES[usage].libelle} » "
        f"({montant_fr(consommes, devise='')} jetons sur {montant_fr(plafond, devise='')}). "
        "À relever dans Administration › Assistant IA, ou attendre le mois prochain."
    )


def journaliser(
    session: Session,
    *,
    usage: str,
    fournisseur: str,
    modele: str,
    statut: str,
    duree_ms: int = 0,
    jetons_entree: Optional[int] = None,
    jetons_sortie: Optional[int] = None,
) -> None:
    """Écrit une ligne du journal, dans SA propre transaction.

    ⚠️ Jamais dans la session de l'appelant : la valider emporterait ce qu'il
    avait en cours, au moment qu'il n'a pas choisi. Et une écriture de journal
    qui échoue ne fait JAMAIS échouer l'appel — elle se journalise.
    """
    try:
        with Session(session.get_bind()) as s:
            s.add(
                AppelIA(
                    usage=usage,
                    fournisseur=fournisseur,
                    modele=modele,
                    statut=statut,
                    duree_ms=max(0, int(duree_ms)),
                    jetons_entree=jetons_entree,
                    jetons_sortie=jetons_sortie,
                )
            )
            s.commit()
    except Exception as exc:  # pragma: no cover - le journal ne casse jamais l'appel
        logger.warning("Journal IA non écrit (%s) : %s", usage, exc)


def _cout_centimes(entree: int, sortie: int, prix_entree: int, prix_sortie: int) -> Optional[int]:
    """PURE. Le coût en centimes, au tarif saisi (centimes par million de jetons).

    Calculé sur le TOTAL du mois, arrondi une fois : arrondir chaque appel perdait
    tout, un appel de 3 000 jetons coûtant moins d'un centime.
    """
    if not prix_entree and not prix_sortie:
        return None
    return round((entree * prix_entree + sortie * prix_sortie) / 1_000_000)


def consommation(session: Session, maintenant: Optional[datetime] = None) -> dict:
    """Ce que l'écran de maintenance montre : par mois, par usage et modèle."""
    maintenant = maintenant or horloge.maintenant()
    mois = func.strftime("%Y-%m", AppelIA.cree_le)  # clé machine, pas un affichage
    lignes = session.exec(
        select(
            mois,
            AppelIA.usage,
            AppelIA.modele,
            func.count(),
            func.sum(AppelIA.statut == STATUT_ERREUR),
            func.sum(AppelIA.statut == STATUT_PLAFOND),
            func.coalesce(func.sum(AppelIA.jetons_entree), 0),
            func.coalesce(func.sum(AppelIA.jetons_sortie), 0),
        )
        .group_by(mois, AppelIA.usage, AppelIA.modele)
        .order_by(mois.desc(), AppelIA.usage)
    ).all()
    tarifs = {
        code: (_reglage(session, u.cle("prix_entree")), _reglage(session, u.cle("prix_sortie")))
        for code, u in USAGES.items()
    }
    resultat: dict[str, list[dict]] = {}
    for m, usage, modele, appels, erreurs, refus, entree, sortie in lignes:
        prix = tarifs.get(usage, (0, 0))
        resultat.setdefault(m, []).append(
            {
                "usage": usage,
                "libelle": USAGES[usage].libelle if usage in USAGES else usage,
                "modele": modele,
                "appels": int(appels),
                "erreurs": int(erreurs or 0),
                "refus": int(refus or 0),
                "jetons_entree": int(entree),
                "jetons_sortie": int(sortie),
                "cout_centimes": _cout_centimes(int(entree), int(sortie), *prix),
            }
        )
    mois_courant = maintenant.strftime("%Y-%m")
    return {
        "mois": [{"mois": m, "usages": u} for m, u in resultat.items()],
        "plafonds": [
            {
                "usage": code,
                "libelle": u.libelle,
                "plafond": plafond_mensuel(session, code),
                "consommes": consommes_du_mois(session, code, maintenant),
            }
            for code, u in USAGES.items()
        ],
        "mois_courant": mois_courant,
    }


def problemes_ia(session: Session) -> list[str]:
    """Pour le contrôle de 06:00 : les usages REFUSÉS par leur plafond depuis 24 h.

    Le fait du jour, pas l'état du mois : un plafond atteint le 3 ne doit pas
    écrire tous les matins jusqu'au 30. Ce qui alerte, c'est qu'un appel a été
    refusé — l'usage automatique s'est arrêté, ou quelqu'un a buté dessus.
    """
    depuis = horloge.maintenant() - timedelta(hours=24)
    refus = session.exec(
        select(AppelIA.usage, func.count())
        .where(AppelIA.statut == STATUT_PLAFOND, AppelIA.cree_le >= depuis)
        .group_by(AppelIA.usage)
    ).all()
    return [
        f"Assistant IA : « {USAGES[u].libelle if u in USAGES else u} » refusé {n} fois "
        "depuis 24 h — plafond mensuel atteint (Administration › Assistant IA)"
        for u, n in refus
    ]


def limite_conservation(maintenant: datetime) -> datetime:
    """Le 1er du mois le plus ancien conservé : le mois courant et les douze
    précédents. `utils/maintenance.purger` efface ce qui est avant."""
    limite = debut_du_mois(maintenant)
    for _ in range(CONSERVATION_MOIS - 1):
        limite = debut_du_mois(limite - timedelta(days=1))
    return limite
