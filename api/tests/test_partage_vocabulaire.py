"""Ce qui se transmet par courriel : la même liste des deux côtés (#1357).

L'écran déduit du lien d'un 🔗 ce qu'il désigne (`front/src/lib/partage.ts`,
`OBJETS_TRANSMISSIBLES`) ; le serveur n'envoie que ce que SA liste connaît
(`app/utils/liens.py`). Un type ajouté d'un seul côté proposerait un envoi que
le serveur refuse, ou priverait un 🔗 de l'envoi — sans que rien ne casse.
"""

from __future__ import annotations

import pathlib
import re

from app.utils.liens import OBJETS_TRANSMISSIBLES, lien_transmissible

FRONT = pathlib.Path(__file__).resolve().parents[2] / "front" / "src" / "lib" / "partage.ts"


def _liste_front() -> list[str]:
    source = FRONT.read_text(encoding="utf-8")
    bloc = re.search(r"OBJETS_TRANSMISSIBLES\s*=\s*\[([\s\S]*?)\]", source)
    assert bloc, "cas zéro : la liste de l'écran est introuvable"
    return re.findall(r"'(\w+)'", bloc.group(1))


def test_les_deux_listes_sont_les_memes():
    assert _liste_front() == list(OBJETS_TRANSMISSIBLES)


def test_chaque_type_a_un_lien():
    for objet in OBJETS_TRANSMISSIBLES:
        assert lien_transmissible(objet, 7).startswith("/")
