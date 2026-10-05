"""Les métriques d'une affaire close — **calculées par le code**, figées en JSON (#1643).

Le modèle les reçoit, il ne les devine pas : un délai que l'assistant aurait
« estimé » en lisant le fil ne se vérifie pas, et la synthèse est opposable au
syndic en assemblée générale.

## Le vocabulaire

- un **fait** est une entrée du fil réduite à ce qui se mesure : sa date, son
  type, l'état qu'elle quitte et celui qu'elle pose, et si elle vient du syndic ;
- une **Suite** est un fait `commentaire`, `etat` ou `reponse` — la relance et la
  synthèse elle-même ne sont pas des Suites ;
- toutes les durées sont en **jours ouvrés** (`utils/jours_ouvres`), au demi-jour.

## Ce qui est arbitré (03/10/2026)

- la durée totale va de l'ouverture à la clôture, **AG comprise** ; l'étape
  « À l'AG » n'apparaît que si l'affaire y est passée, et l'état de sortie
  (résolu, annulé) termine la frise ;
- une affaire **rouverte** est mesurée sur toute sa vie : le temps passé close
  avant la réouverture est une étape à part (`close_avant_reouverture`), jamais
  la « plus longue » ;
- la comparaison est la **moyenne** des autres affaires closes de même catégorie
  sur l'**exercice comptable** qui contient la clôture — masquée sous trois.

Ce module ne lit pas la base : `production.py` lui donne les faits. Seule
l'horloge y entre, pour passer de l'UTC de la base aux heures murales de Paris.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from app.models.tickets import STATUTS_TICKET_CLOS, StatutTicket
from app.utils import horloge
from app.utils.jours_ouvres import au_demi_jour, heures_ouvrees, jours_ouvres

VERSION = 1
#: Les quatre colonnes du kanban, dans l'ordre de la frise.
ETAPES_KANBAN = (
    StatutTicket.ouvert.value,
    StatutTicket.en_ag.value,
    StatutTicket.en_cours.value,
    StatutTicket.chez_prestataire.value,
)
#: Le temps passé close avant une réouverture — une étape à part.
CLOSE_AVANT_REOUVERTURE = "close_avant_reouverture"
TYPES_SUITE = ("commentaire", "etat", "reponse")
#: Sous ce nombre d'affaires comparables, la moyenne ne dit rien : masquée.
MINIMUM_COMPARABLES = 3


@dataclass(frozen=True)
class Fait:
    """Une entrée du fil, réduite à ce qui se mesure."""

    quand: datetime  # UTC naïf, comme en base
    type: str
    ancien_statut: Optional[str] = None
    nouveau_statut: Optional[str] = None
    syndic: bool = False


def _mur(instant: datetime) -> datetime:
    """L'heure murale de Paris, naïve — ce que `jours_ouvres` attend."""
    return horloge.a_paris(instant).replace(tzinfo=None)


def _jours(debut: datetime, fin: datetime) -> float:
    return jours_ouvres(_mur(debut), _mur(fin))


def _etats(faits: list[Fait], cloture_le: datetime) -> list[Fait]:
    return [f for f in faits if f.type == "etat" and f.nouveau_statut and f.quand <= cloture_le]


def etat_initial(faits: list[Fait], cloture_le: datetime) -> str:
    """L'état de l'affaire à son ouverture — celui que quitte sa première étape tracée.

    🔴 UNE source pour la frise ET la chronologie (03/10/2026, relevé à l'écran :
    la frise disait « Chez le syndic 6 j » quand la chronologie partait de
    « Ouvert »). Une étape qui n'a laissé aucune trace — un état corrigé à la
    main avant `rassemblement` qui sait les lire — ne doit pas faire raconter
    deux histoires aux deux graphiques.
    """
    etats = _etats(faits, cloture_le)
    return (etats[0].ancien_statut if etats else None) or StatutTicket.ouvert.value


def _segments(cree_le: datetime, cloture_le: datetime, faits: list[Fait]) -> list[tuple]:
    """(état, début, fin) de l'ouverture à la clôture, dans l'ordre."""
    etats = _etats(faits, cloture_le)
    courant = etat_initial(faits, cloture_le)
    depuis = cree_le
    segments = []
    for e in etats:
        segments.append((courant, depuis, max(depuis, e.quand)))
        courant, depuis = e.nouveau_statut, max(depuis, e.quand)
    segments.append((courant, depuis, max(depuis, cloture_le)))
    return segments


def _etapes(segments: list[tuple]) -> tuple[list[dict], Optional[str]]:
    """Le temps par étape (kanban, puis l'éventuel temps close), et la plus longue."""
    heures: dict[str, float] = {}
    for i, (statut, debut, fin) in enumerate(segments):
        cle = statut
        if statut in STATUTS_TICKET_CLOS:
            if i == len(segments) - 1:
                continue  # l'état de sortie termine la frise, il n'a pas de durée
            cle = CLOSE_AVANT_REOUVERTURE
        heures[cle] = heures.get(cle, 0.0) + heures_ouvrees(_mur(debut), _mur(fin))
    ordre = [*ETAPES_KANBAN, CLOSE_AVANT_REOUVERTURE]
    etapes = [
        {"statut": s, "jours": au_demi_jour(heures[s] / 8)}
        for s in sorted(heures, key=lambda s: ordre.index(s) if s in ordre else len(ordre))
    ]
    candidates = [e for e in etapes if e["statut"] in ETAPES_KANBAN and e["jours"] > 0]
    plus_longue = max(candidates, key=lambda e: e["jours"])["statut"] if candidates else None
    return etapes, plus_longue


def _chronologie(cree_le: datetime, cloture_le: datetime, issue: str, faits: list[Fait]):
    """Les jalons datés : ouverture, états, relances, réouvertures, clôture."""
    jalons = [{"quand": cree_le, "type": "creation", "statut": etat_initial(faits, cloture_le)}]
    for f in faits:
        if f.quand > cloture_le:
            continue
        if f.type == "relance":
            jalons.append({"quand": f.quand, "type": "relance", "statut": None})
        elif f.type == "etat" and f.nouveau_statut:
            rouvre = f.ancien_statut in STATUTS_TICKET_CLOS and f.nouveau_statut not in (
                STATUTS_TICKET_CLOS
            )
            jalons.append(
                {
                    "quand": f.quand,
                    "type": "reouverture" if rouvre else "etat",
                    "statut": f.nouveau_statut,
                }
            )
    if not (jalons[-1]["type"] == "etat" and jalons[-1]["statut"] == issue):
        jalons.append({"quand": cloture_le, "type": "etat", "statut": issue})
    precedent = None
    for j in jalons:
        j["ecart"] = None if precedent is None else _jours(precedent, j["quand"])
        precedent = j["quand"]
        j["quand"] = j["quand"].isoformat()
    return jalons


def _semaines(cree_le: datetime, cloture_le: datetime, suites: list[Fait]) -> list[int]:
    """Le nombre de Suites par semaine glissante depuis l'ouverture."""
    nb = max(1, math.ceil((cloture_le - cree_le).total_seconds() / (7 * 86_400)))
    comptes = [0] * nb
    for s in suites:
        rang = int((s.quand - cree_le).total_seconds() // (7 * 86_400))
        comptes[min(max(rang, 0), nb - 1)] += 1
    return comptes


def mesures_de_base(cree_le: datetime, cloture_le: datetime, faits: list[Fait]) -> dict:
    """Les quatre mesures que la comparaison reprend — durée, 1ʳᵉ réponse, relances, Suites."""
    faits = sorted(faits, key=lambda f: f.quand)
    suites = [f for f in faits if f.type in TYPES_SUITE and f.quand <= cloture_le]
    syndic = next((f for f in suites if f.syndic), None)
    return {
        "duree_totale": _jours(cree_le, cloture_le),
        "premiere_reponse_syndic": _jours(cree_le, syndic.quand) if syndic else None,
        "relances": sum(1 for f in faits if f.type == "relance" and f.quand <= cloture_le),
        "suites": len(suites),
    }


def calculer(
    *,
    cree_le: datetime,
    cloture_le: datetime,
    issue: str,
    faits: list[Fait],
    comparaison: Optional[dict] = None,
) -> dict:
    """PURE (hors horloge). Les métriques d'une affaire close, prêtes à figer en JSON."""
    faits = sorted(faits, key=lambda f: f.quand)
    base = mesures_de_base(cree_le, cloture_le, faits)
    suites = [f for f in faits if f.type in TYPES_SUITE and f.quand <= cloture_le]
    relances = [f for f in faits if f.type == "relance" and f.quand <= cloture_le]
    reaction = None
    if relances:
        apres = next((s for s in suites if s.syndic and s.quand > relances[-1].quand), None)
        reaction = _jours(relances[-1].quand, apres.quand) if apres else None
    etapes, plus_longue = _etapes(_segments(cree_le, cloture_le, faits))
    semaines = _semaines(cree_le, cloture_le, suites)
    chronologie = _chronologie(cree_le, cloture_le, issue, faits)
    return {
        "version": VERSION,
        "issue": issue,
        "ouverte_le": cree_le.isoformat(),
        "close_le": cloture_le.isoformat(),
        **base,
        "etapes": etapes,
        "etape_plus_longue": plus_longue,
        "reaction_relance": reaction,
        "semaines": semaines,
        "semaines_muettes": sum(1 for n in semaines if n == 0),
        "chronologie": chronologie,
        "reouvertures": sum(1 for j in chronologie if j["type"] == "reouverture"),
        "comparaison": comparaison,
    }


def bornes_exercice(jour: date, mois_debut: Optional[int]) -> tuple[date, date, str]:
    """L'exercice comptable qui contient `jour` : (début inclus, fin exclue, libellé).

    Sans mois de début renseigné, l'exercice est l'année civile. Un exercice qui
    commence en juillet se nomme « 2025-2026 », un exercice civil « 2026 ».
    """
    m = mois_debut if mois_debut and 1 <= mois_debut <= 12 else 1
    annee = jour.year if jour.month >= m else jour.year - 1
    debut = date(annee, m, 1)
    fin = date(annee + 1, m, 1)
    libelle = str(annee) if m == 1 else f"{annee}-{annee + 1}"
    return debut, fin, libelle


def moyenne_de(valeurs) -> Optional[float]:
    """La moyenne des valeurs CONNUES — `None` quand il n'y en a aucune, jamais 0.

    Une mesure absente (pas de réponse du syndic, pas de relance) ne compte pas
    pour zéro : elle tirerait la moyenne vers un délai que personne n'a vécu.
    Une règle, deux lecteurs : la comparaison d'une synthèse (ci-dessous) et les
    moyennes d'un ensemble d'affaires (`agregats`, #1645 #1646).
    """
    connues = [v for v in valeurs if v is not None]
    return sum(connues) / len(connues) if connues else None


def moyenne(mesures: list[dict], categorie: str, exercice: str) -> Optional[dict]:
    """La moyenne des mesures de base des affaires comparables — `None` sous trois."""
    if len(mesures) < MINIMUM_COMPARABLES:
        return None

    def moy(cle: str) -> Optional[float]:
        return moyenne_de(m.get(cle) for m in mesures)

    duree, reponse = moy("duree_totale"), moy("premiere_reponse_syndic")
    return {
        "nombre": len(mesures),
        "categorie": categorie,
        "exercice": exercice,
        "duree_totale": au_demi_jour(duree) if duree is not None else None,
        "premiere_reponse_syndic": au_demi_jour(reponse) if reponse is not None else None,
        "relances": round(moy("relances") or 0, 1),
        "suites": round(moy("suites") or 0, 1),
    }


def debut_utc(jour: date) -> datetime:
    """Minuit de Paris du jour, en UTC naïf — la borne d'une requête sur `ferme_le`."""
    return horloge.debut_du_jour_utc(jour)


__all__ = [
    "CLOSE_AVANT_REOUVERTURE",
    "ETAPES_KANBAN",
    "Fait",
    "MINIMUM_COMPARABLES",
    "bornes_exercice",
    "calculer",
    "etat_initial",
    "debut_utc",
    "mesures_de_base",
    "moyenne",
    "moyenne_de",
]
