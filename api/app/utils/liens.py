"""Liens profonds vers le front — source de vérité unique.

Le fil d'activité, les notifications et les e-mails renvoient vers une page qui
contient souvent des centaines d'éléments répartis en onglets. Y arriver sans
précision oblige l'utilisateur à chercher ce sur quoi il vient de cliquer.

La convention du projet (cf. `front/src/lib/deepLink.ts`) tient en deux morceaux :

  - `?onglet=<id>`     → l'onglet à sélectionner
  - `#<prefixe>-<id>`  → l'élément à déplier et à révéler

Le problème n'est pas la convention, c'est qu'elle était **recopiée à la main** dans
une quinzaine de f-strings réparties sur `flux.py`, `annonces.py`, `idees.py` et
`calendrier.py`. Chaque nouvel appel devait redevenir savoir dans quel onglet vit
l'élément visé — et le 28/07/2026 une fiche prestataire est partie sans onglet :
`/prestataires#presta-23` déposait l'utilisateur sur « Prestations ponctuelles »,
où aucun élément ne porte cet id. La page était la bonne, la fiche invisible.

Ce module remplace ces f-strings par une table unique. Y ajouter une ligne est le
seul geste nécessaire pour exposer un nouveau type d'élément, et
`api/tests/test_liens_front.py` vérifie que chaque ligne pointe vers une page
réelle, un onglet réellement déclaré, et un onglet qui rend bien cette ancre.
"""
from __future__ import annotations

from typing import Optional

# préfixe d'ancre → (page front, onglet qui rend cette ancre ou None si la page n'a
# pas d'onglets / si l'élément vit dans l'onglet par défaut).
#
# L'onglet vaut pour l'onglet où l'élément porte réellement un `id="<prefixe>-…"`.
# `ev` cible explicitement `liste` : le Kanban du calendrier n'affiche qu'une colonne
# de statut et ne pose pas d'id par événement.
EMPLACEMENTS: dict[str, tuple[str, Optional[str]]] = {
    "pub": ("/actualites", None),
    "ev": ("/calendrier", "liste"),
    "dv": ("/prestataires", "prestations"),
    "presta": ("/prestataires", "prestataires"),
    "annonce": ("/sondages", "annonces"),
    "idee": ("/sondages", "idees"),
    "faq": ("/faq", None),
    "diag": ("/residence", None),
    "doc": ("/residence", None),
}


def lien_element(prefixe: str, identifiant: int) -> str:
    """URL qui ouvre la page, sélectionne le bon onglet et révèle l'élément.

    >>> lien_element("presta", 23)
    '/prestataires?onglet=prestataires#presta-23'
    >>> lien_element("pub", 7)
    '/actualites#pub-7'
    """
    try:
        page, onglet = EMPLACEMENTS[prefixe]
    except KeyError:
        raise KeyError(
            f"préfixe d'ancre inconnu : {prefixe!r}. Ajoutez-le à "
            f"EMPLACEMENTS (app/utils/liens.py) plutôt que de fabriquer "
            f"l'URL à la main — sinon l'onglet cible redevient une devinette."
        ) from None
    onglet_qs = f"?onglet={onglet}" if onglet else ""
    return f"{page}{onglet_qs}#{prefixe}-{identifiant}"


def page_element(prefixe: str) -> str:
    """Page seule (sans onglet ni ancre) — pour un repli quand l'id est inconnu."""
    return EMPLACEMENTS[prefixe][0]

def lien_ticket(ticket_id: int, message_id: int | None = None) -> str:
    """URL d'un ticket, éventuellement ancrée sur un message précis.

    Les six URLs `/tickets/{id}` de tickets.py étaient fabriquées à la main,
    alors que ce module existe précisément pour que personne n'ait à le faire.
    Conséquence : une notification « nouvelle réponse » déposait le lecteur en
    haut de la page, à lui de retrouver ce qui avait déclenché l'alerte.
    Avec `message_id`, il arrive dessus.

    >>> lien_ticket(23)
    '/tickets/23'
    >>> lien_ticket(23, 45)
    '/tickets/23#msg-45'
    """
    base = f"/tickets/{ticket_id}"
    return f"{base}#msg-{message_id}" if message_id else base
