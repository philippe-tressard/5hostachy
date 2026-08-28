"""Flux — contexte de collecte et notions partagées par toutes les rubriques.

Extrait de `flux.py` (1044 lignes) le 08/08/2026. Voir `__init__.py` pour la
règle de découpage.

Ce module porte ce qu'une rubrique ne peut **pas** redéfinir sans faire diverger
le fil : le libellé d'un périmètre, le résumé d'un texte riche, les marqueurs
« Épinglé » / « Urgent ». Une rubrique qui en réécrirait un afficherait la même
notion sous deux formes selon la ligne — c'est précisément ce que le découpage
doit empêcher, pas provoquer.
"""
import html as _html
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlmodel import Session

from app.models.core import Utilisateur

#  Les périmètres vivent dans `app/utils/perimetres.py` : la table et l'analyse
#  étaient écrites ici ET dans la relance syndic des tickets, avec deux résultats
#  différents pour AFUL. Importés sous leur vrai nom et non ré-exportés : un
#  alias qui délègue au helper partagé masque son origine (socle 02 §6).
from app.utils.perimetres import parse_json_perimetres, parse_perimetres


@dataclass(frozen=True)
class ContexteFlux:
    """Ce que chaque rubrique reçoit pour collecter ses lignes.

    `now` et `since` sont calculés **une fois** par requête et transportés :
    douze rubriques qui appelleraient `utcnow()` chacune travailleraient sur
    douze instants différents, et la fenêtre glissante ne serait plus la même
    d'une ligne à l'autre.
    """

    session: Session
    user: Utilisateur
    now: datetime
    since: datetime


# ── Périmètres ───────────────────────────────────────────────────────────────

def perimetres_de(obj) -> list[str]:
    """Périmètre d'un élément qui porte `perimetre_cible` — ticket ou publication.

    Précision décroissante : la cible JSON explicite, sinon le bâtiment de
    rattachement, sinon le champ texte `perimetre`. Un `Ticket` n'a pas ce
    dernier champ, il retombe donc sur « résidence » — exactement le
    comportement d'avant le découpage, où les quatre blocs de ticket écrivaient
    cette cascade à la main, à l'identique.

    ⚠️ **Ne pas étendre aux événements.** Ceux-là n'ont pas de `perimetre_cible`
    et leur règle ignore volontairement `batiment_id` : les faire passer ici
    changerait le périmètre affiché dès qu'un bâtiment est renseigné. Deux règles
    qui se ressemblent ne sont pas la même règle
    (`standards/02-factorisation.md` §4) — d'où l'appel direct à
    `parse_perimetres` conservé dans `evenements.py`. Le devis relevait de la même
    exception jusqu'à son retrait ; `prestataires.py` ne lit plus aucun périmètre.
    """
    cible = getattr(obj, "perimetre_cible", None)
    if cible:
        return parse_json_perimetres(cible)
    batiment_id = getattr(obj, "batiment_id", None)
    if batiment_id:
        return [f"bat:{batiment_id}"]
    return parse_perimetres(getattr(obj, "perimetre", None))


# ── Résumés, auteurs, marqueurs ──────────────────────────────────────────────

def auteur_nom(session: Session, uid: Optional[int]) -> Optional[str]:
    if not uid:
        return None
    u = session.get(Utilisateur, uid)
    return f"{u.prenom} {u.nom}" if u else None


def strip_html(text: Optional[str], max_len: int = 120) -> Optional[str]:
    """Retire les balises HTML et tronque pour un résumé texte."""
    if not text:
        return None
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = _html.unescape(clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    if len(clean) > max_len:
        clean = clean[:max_len].rsplit(" ", 1)[0] + "…"
    return clean


def badges_marqueurs(obj) -> list[str]:
    """Marqueurs « Épinglé » / « Urgent », identiques quelle que soit la rubrique.

    Ils étaient construits à la main pour les publications ; les événements ont
    désormais le même épinglage, et rien ne justifie deux écritures du même badge.
    `getattr` avec défaut : toutes les rubriques ne portent pas les deux notions.
    """
    marqueurs = []
    if getattr(obj, "epingle", False):
        marqueurs.append("📌 Épinglé")
    if getattr(obj, "urgente", False):
        marqueurs.append("🔴 Urgent")
    #  Confidentiel (#347) : celui qui voit la carte fait partie du périmètre —
    #  le badge lui dit que les autres bâtiments, eux, ne la voient pas. Sans
    #  lui, rien ne distingue à l'écran une actualité restreinte d'une autre, et
    #  le périmètre seul ne le dit pas (il ne décrit que le sujet depuis #339).
    if getattr(obj, "confidentiel", False):
        marqueurs.append("🔒 Confidentiel")
    return marqueurs
