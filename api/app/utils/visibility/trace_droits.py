"""La trace, dans le fil, d'une Suite qui change QUI LIT l'affaire (29/09/2026).

## L'arbitrage

Signalé sur TK-124285 : des copropriétaires lisaient l'affaire sans en lire les
suites. Arbitré à l'écran le 29/09/2026 :

> *« si une suite change les droits, elle s'applique à la totalité du fil et
>   du document maître »*

Les droits de lecture appartiennent à l'AFFAIRE, jamais à un message : le fil
se lit par qui lit l'affaire (`ticket_visible`). Une Suite qui change les
Destinataires ou l'Accès les change donc pour tout le fil — messages antérieurs
compris. ⚠️ Un ÉLARGISSEMENT est rétroactif : ouvrir aux locataires leur fait
lire aussi ce qui a été écrit avant.

C'est pourquoi la Suite le DIT, dans son texte : l'intervenant et la date s'y
écrivaient déjà (`evolutions.py`, `planifie`) ; les droits, qui comptent plus,
passaient en silence.

Pure : aucune base, aucune requête. Dans ce paquet parce qu'elle dit QUI LIT,
et qu'elle lit les Destinataires comme la règle les lit (`_parse_json_list`) ;
les libellés viennent de `LIBELLES_PUBLIC_CIBLE`, tenus d'accord avec l'écran
par `test_destinataires_vocabulaire.py`.
"""

from __future__ import annotations

from html import escape
from typing import Optional

from app.models.core import Ticket

from .defauts_affaire import destinataires_par_defaut
from .socle import LIBELLES_PUBLIC_CIBLE, _parse_json_list

#: Les codes que la règle LIT sans que le sélecteur les propose : `résidents`
#: (l'absence de restriction) et l'ancien `copropriétaires` (#1301).
_CODES_LUS = {"résidents": "Tous", "copropriétaires": "Copropriétaires"}


def _libelle(codes: list[str], vide: str) -> str:
    if not codes:
        return vide
    return ", ".join(LIBELLES_PUBLIC_CIBLE.get(c) or _CODES_LUS.get(c) or c for c in codes)


def trace_droits(
    avant: Optional[str],
    apres: Optional[str],
    reserve_avant: bool,
    reserve_apres: bool,
    *,
    vide: str,
) -> list[str]:
    """Les lignes à écrire dans la Suite — aucune si les droits n'ont pas bougé.

    `avant` / `apres` : `ticket.public_cible` tel que stocké (JSON, ou `None`).

    `vide` : ce que veut dire une liste vide pour CET objet — le défaut de la
    catégorie pour une affaire, « Tous » pour une actualité. L'ordre des codes
    ne compte pas : le formulaire les rend dans l'ordre de ses pastilles.
    """
    codes_avant, codes_apres = _parse_json_list(avant, []), _parse_json_list(apres, [])
    lignes = []
    if set(codes_avant) != set(codes_apres):
        lignes.append(
            f"🔒 Destinataires : {_libelle(codes_avant, vide)} → {_libelle(codes_apres, vide)}"
        )
    if reserve_avant != reserve_apres:
        lignes.append(
            "🔒 Accès : réservé au périmètre"
            if reserve_apres
            else "🔓 Accès : ouvert à toute la copropriété"
        )
    #  Un code inconnu vient du client : il ne rejoint pas le HTML tel quel.
    return [escape(ligne, quote=False) for ligne in lignes]


def trace_lecture_par_defaut(ticket: Ticket, avant: list[str]) -> list[str]:
    """La ligne d'une Suite dont l'ÉTAT change qui lit l'affaire — ou aucune.

    Standard du 30/09/2026 : une Étude & travaux sans choix du conseil passe
    du conseil seul aux copropriétaires en AG, chez le prestataire, résolue ou
    annulée (`defauts_affaire.STATUTS_ETUDE_OUVERTE`). Aucun Destinataire n'a
    bougé, et pourtant tout le fil s'ouvre : la Suite le dit, comme elle dit un
    changement de Destinataires.

    `avant` : `destinataires_par_defaut(ticket)` lu AVANT le changement d'état.
    Rien si le conseil a choisi (ses Destinataires décident, pas l'état) ou si
    l'affaire est confidentielle.
    """
    if ticket.confidentiel or _parse_json_list(ticket.public_cible, []):
        return []
    apres = destinataires_par_defaut(ticket)
    if set(avant) == set(apres):
        return []
    ligne = (
        f"🔒 Lue par défaut : {_libelle(avant, '—')} → {_libelle(apres, '—')}"
        " — toute l'affaire et tout son fil"
    )
    return [escape(ligne, quote=False)]
