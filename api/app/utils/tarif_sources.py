"""Les deux SOURCES du tarif d'un modèle : la grille du fournisseur et le taux BCE.

## Pourquoi le serveur lit lui-même (30/09/2026)

Demandé : *« l'appel à l'IA de ce use case recherche le prix sur l'opérateur
concerné du modèle du use case concerné, remplit les prix et enregistre »*.

Un modèle interrogé « de mémoire » rend le tarif de son apprentissage, et
aucun des trois fournisseurs n'offre la même recherche web par la même API.
Les deux grands publient en revanche leur grille en **Markdown** (OpenAI
~22 Ko, Anthropic ~48 Ko) : le serveur la lit à l'adresse que le code nomme
(`Fournisseur.page_tarifs`), et l'assistant n'a plus qu'à y trouver la ligne.

Les grilles sont en **dollars**. La conversion se fait ICI, au taux de
référence publié chaque jour ouvré par la Banque centrale européenne — pas
par le modèle, qui inventerait un taux.

## Ce qui ne part pas

Aucune donnée du site : deux GET vers des adresses fixes, sans cookie ni clé.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Optional

#: Le taux de référence euro, publié chaque jour ouvré vers 16 h (CET).
URL_TAUX_BCE = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
DELAI_S = 20
#: Une grille au-delà de cette taille n'est plus une grille : on la tronque
#: plutôt que de payer des dizaines de milliers de jetons pour la lire.
MAX_CARACTERES_GRILLE = 80_000


class SourceIndisponible(Exception):
    """Une source n'a pas pu être lue — l'appelant en fait une `ErreurLLM`."""


@dataclass(frozen=True)
class Taux:
    #: Combien de dollars vaut un euro, ce jour-là.
    usd_par_eur: Decimal
    #: La date de publication, telle que la BCE l'écrit (AAAA-MM-JJ).
    date: str


_RE_DATE = re.compile(r"time=['\"](\d{4}-\d{2}-\d{2})['\"]")
_RE_USD = re.compile(r"currency=['\"]USD['\"]\s+rate=['\"]([0-9.]+)['\"]")


def lire_taux_bce(xml: str) -> Taux:
    """PURE. Le taux USD du fichier quotidien de la BCE.

    ⚠️ Lu par motif, pas par un analyseur XML : le fichier fait vingt lignes,
    et un analyseur de la bibliothèque standard ouvert sur le réseau accepte
    les entités qu'on n'a pas demandées.
    """
    date, usd = _RE_DATE.search(xml or ""), _RE_USD.search(xml or "")
    if not date or not usd:
        raise SourceIndisponible("Le taux de la BCE est illisible.")
    try:
        taux = Decimal(usd.group(1))
    except InvalidOperation as exc:
        raise SourceIndisponible("Le taux de la BCE est illisible.") from exc
    if not Decimal("0.2") < taux < Decimal("5"):
        raise SourceIndisponible(f"Taux de la BCE invraisemblable : {taux}.")
    return Taux(usd_par_eur=taux, date=date.group(1))


def en_centimes_euro(montant: float, devise: str, taux: Optional[Taux]) -> int:
    """PURE. Un prix par million de jetons, rendu en CENTIMES d'euro entiers.

    En `Decimal` du début à la fin : 0,20 $ au taux 1,08 font 18,5 centimes,
    et c'est l'arrondi commercial qui tranche, pas la représentation binaire
    d'un flottant.
    """
    valeur = Decimal(str(montant))
    if devise == "USD":
        if taux is None:
            raise SourceIndisponible("Un prix en dollars demande le taux du jour.")
        valeur = valeur / taux.usd_par_eur
    elif devise != "EUR":
        raise SourceIndisponible(f"Devise non prise en charge : « {devise} ».")
    return int((valeur * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


async def _lire(url: str) -> str:
    import httpx

    try:
        async with httpx.AsyncClient(timeout=DELAI_S, follow_redirects=True) as client:
            #  ⚠️ En ASCII : un en-tête HTTP n'admet pas d'accent, et httpx lève
            #  avant même d'envoyer (constaté au premier essai réel).
            r = await client.get(url, headers={"User-Agent": "5Hostachy (tarif-modele)"})
    except httpx.HTTPError as exc:
        raise SourceIndisponible(f"« {url} » n'a pas pu être lue.") from exc
    if r.status_code != 200:
        raise SourceIndisponible(f"« {url} » a répondu {r.status_code}.")
    return r.text


async def lire_grille(url: str) -> str:
    """La grille tarifaire du fournisseur, bornée."""
    if not url:
        raise SourceIndisponible("Ce fournisseur ne publie pas de grille lisible.")
    return (await _lire(url))[:MAX_CARACTERES_GRILLE]


async def lire_taux() -> Taux:
    return lire_taux_bce(await _lire(URL_TAUX_BCE))


__all__ = [
    "SourceIndisponible",
    "Taux",
    "en_centimes_euro",
    "lire_grille",
    "lire_taux",
    "lire_taux_bce",
]
