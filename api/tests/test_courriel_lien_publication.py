"""Le bouton de `publication_syndic` mène à CE qu'il annonce (23/09/2026).

Le gabarit écrivait en dur `{{ app.url }}/actualites#pub-{{ publication.id }}`.
Or les SONDAGES le réemploient, avec `publication.id` = l'identifiant du
sondage : leur courriel au syndic ou au CS portait un bouton « Voir la
publication » vers une AUTRE actualité, ou vers rien. Et l'actualité devient
une affaire (#1091) : `/actualites#pub-` n'aura bientôt plus rien à révéler.

Le lien est désormais fourni par l'appelant (`publication.lien`, relatif) — le
motif des autres gabarits (`document.lien`, `annonce.lien`).
"""
from __future__ import annotations

import pathlib
import re

from jinja2 import ChainableUndefined, Environment

from app.seed.emails import EMAIL_TEMPLATES
from app.utils.liens import lien_sondage


def _corps(code: str) -> str:
    return next(corps for c, _l, _s, corps, *_ in EMAIL_TEMPLATES if c == code)


def test_le_bouton_suit_le_lien_fourni():
    html = Environment(undefined=ChainableUndefined).from_string(_corps("publication_syndic")).render(
        publication={"id": 7, "titre": "T", "contenu": "C", "lien": lien_sondage(7)},
        app={"url": "https://5hostachy.fr"},
    )
    assert "https://5hostachy.fr/sondages/7" in html
    assert "actualites#pub" not in html, "le gabarit fabrique encore son propre lien"


def test_le_lien_d_un_sondage_est_celui_de_sa_fiche():
    assert lien_sondage(12) == "/sondages/12"


# ── Aucune URL fabriquée à la main quand sa fabrique existe ──────────────────
#
#  `lien_sondage` et `lien_ticket` existaient ; six URL les ignoraient
#  (`f"/sondages/{…}"` cinq fois, `f"/tickets/{…}"` une fois). C'est la
#  neuvième occurrence de « le composant existait déjà ».

_APP = pathlib.Path(__file__).resolve().parents[1] / "app"
_A_LA_MAIN = re.compile(r"""f["']/(sondages|tickets)/\{""")


def test_aucune_url_de_sondage_ou_d_affaire_a_la_main():
    fautes = [
        f"{p.relative_to(_APP).as_posix()}:{n}"
        for p in _APP.rglob("*.py") if "__pycache__" not in p.parts and p.name != "liens.py"
        for n, ligne in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if _A_LA_MAIN.search(ligne) and not ligne.lstrip().startswith("#")
    ]
    assert not fautes, f"URL fabriquée à la main — employer `lien_sondage` / `lien_ticket` : {fautes}"
