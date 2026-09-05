"""Liens profonds vers le front — source de vérité unique.

Le fil d'activité, les notifications et les e-mails renvoient vers une page qui
contient souvent des centaines d'éléments répartis en onglets. Y arriver sans
précision oblige l'utilisateur à chercher ce sur quoi il vient de cliquer.

La convention du projet (cf. `front/src/lib/deepLink.ts`) tient en deux morceaux :

  - une **route dédiée** par onglet (`/annonces`, `/calendrier/kanban`)
  - `#<prefixe>-<id>`  → l'élément à déplier et à révéler

⚠️ Le premier morceau était `?onglet=<id>` jusqu'au 05/09/2026. Les anciennes URL
restent servies — le front les redirige en 308 — mais aucune ne s'écrit plus ici :
une adresse qu'on fabrique doit être celle qu'on veut voir dans la barre du
navigateur, sinon on envoie un lien qui rebondit.

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

# préfixe d'ancre → route du front qui rend réellement `id="<prefixe>-…"`.
#
# La route est celle de l'ONGLET, pas seulement de la page : `/calendrier` est la vue
# liste (le Kanban ne pose pas d'id par événement), `/annonces` et `/idees` sont deux
# rubriques d'un même écran. C'est ce que `test_liens_front.py` vérifie ligne à ligne,
# en relisant la table des onglets du front.
EMPLACEMENTS: dict[str, str] = {
    "pub": "/actualites",
    "ev": "/calendrier",
    "presta": "/prestataires",
    "annonce": "/annonces",
    "idee": "/idees",
    "faq": "/faq",
    "diag": "/residence",
    "doc": "/residence",
}


def lien_element(prefixe: str, identifiant: int) -> str:
    """URL qui ouvre la page, sélectionne le bon onglet et révèle l'élément.

    >>> lien_element("presta", 23)
    '/prestataires#presta-23'
    >>> lien_element("annonce", 12)
    '/annonces#annonce-12'
    """
    try:
        route = EMPLACEMENTS[prefixe]
    except KeyError:
        raise KeyError(
            f"préfixe d'ancre inconnu : {prefixe!r}. Ajoutez-le à "
            f"EMPLACEMENTS (app/utils/liens.py) plutôt que de fabriquer "
            f"l'URL à la main — sinon la rubrique cible redevient une devinette."
        ) from None
    return f"{route}#{prefixe}-{identifiant}"


def page_element(prefixe: str) -> str:
    """Route seule (sans ancre) — pour un repli quand l'identifiant est inconnu."""
    return EMPLACEMENTS[prefixe]

def lien_sondage(sondage_id: int | None = None) -> str:
    """Fiche d'un sondage, ou la rubrique elle-même quand l'identifiant est inconnu.

    Un sondage a sa propre page (`/sondages/12`) : il n'a donc pas d'ancre, et rien
    à faire dans `EMPLACEMENTS`. Il a quand même sa place ICI — c'est la règle du
    module, et `signalements.py` écrivait ces deux formes à la main juste à côté de
    deux liens d'ancre qu'il fabriquait aussi lui-même.

    >>> lien_sondage(12)
    '/sondages/12'
    >>> lien_sondage()
    '/sondages'
    """
    return f"/sondages/{sondage_id}" if sondage_id else "/sondages"


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
