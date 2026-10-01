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

import re
from types import SimpleNamespace as Faux

from jinja2 import ChainableUndefined, Environment

from app.seed.emails import EMAIL_TEMPLATES
from app.utils.liens import lien_sondage
from tests.aides_sources import modules_app


def _corps(code: str) -> str:
    return next(corps for c, _l, _s, corps, *_ in EMAIL_TEMPLATES if c == code)


def test_le_bouton_suit_le_lien_fourni():
    html = (
        Environment(undefined=ChainableUndefined)
        .from_string(_corps("publication_syndic"))
        .render(
            publication={"id": 7, "titre": "T", "contenu": "C", "lien": lien_sondage(7)},
            app={"url": "https://5hostachy.fr"},
        )
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

_A_LA_MAIN = re.compile(r"""f["']/(sondages|tickets)/\{""")


#: La fabrique — le seul module où ces URL s'écrivent à la main.
_FABRIQUE = "utils/liens.py"


def _a_la_main(modules) -> list[str]:
    return [
        f"{m.rel}:{n}"
        for m in modules
        for n, ligne in enumerate(m.lignes, 1)
        if _A_LA_MAIN.search(ligne) and not ligne.lstrip().startswith("#")
    ]


def test_aucune_url_de_sondage_ou_d_affaire_a_la_main():
    fautes = _a_la_main(m for m in modules_app() if m.rel != _FABRIQUE)
    assert not fautes, (
        f"URL fabriquée à la main — employer `lien_sondage` / `lien_ticket` : {fautes}"
    )


def test_le_controle_VOIT_les_url_de_la_fabrique():
    """Cas zéro (#1496) : la fabrique écrit les deux URL à la main, et c'est son
    rôle — le motif doit l'y voir, sinon il ne verrait pas non plus la copie.
    Et une copie forgée, en commentaire puis en code, n'est refusée qu'en code."""
    fabrique = _a_la_main(m for m in modules_app() if m.rel == _FABRIQUE)
    assert len(fabrique) >= 2, f"le motif ne voit plus les URL de {_FABRIQUE} : {fabrique}"
    forge = Faux(rel="forge.py", lignes=['# f"/tickets/{t.id}"', 'url = f"/sondages/{s.id}"'])
    assert _a_la_main([forge]) == ["forge.py:2"]
