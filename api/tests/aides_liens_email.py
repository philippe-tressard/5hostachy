"""Les liens des modèles d'e-mail, extraits UNE fois (#1496).

## Pourquoi cette aide existe (30/09/2026)

Trois contrôles lisaient les liens des modèles d'e-mail, chacun à sa façon :

| Contrôle | Ce qu'il lisait | Ce qu'il voyait (30/09/2026) |
|---|---|---|
| `test_liens_front` | les modèles COMPOSÉS, `href="{{ app.url }}/…"` sans variable | 4 chemins |
| `test_liens_modeles_email` | les SOURCES, `href="…"` + `bouton("…")` | 16 adresses |
| `test_liens_email_audience` | les SOURCES, `href=` seulement | 4 chemins, tous `/admin` |

Le dernier était **aveugle aux boutons** depuis la factorisation #959 : un
bouton s'écrit `bouton("{{ app.url }}/calendrier", …)`, et aucun `href=` ne
paraît plus dans la source. Ni `/calendrier`, ni un seul lien de `tickets.py` ou
de `vie_collective.py` n'était soumis à la question « le destinataire peut-il
ouvrir cette page ? ». Le deuxième avait appris la forme `bouton(…)` ; le
troisième non : **une extraction recopiée diverge** (`standards/05` §9).

## Ce qu'elle garantit

- **Les modèles tels qu'ils partent** : on lit `EMAIL_TEMPLATES`, donc le HTML
  COMPOSÉ — un bouton y est une ancre comme une autre, quelle que soit la
  fonction qui l'a fabriquée. Une prochaine factorisation de la mise en forme
  ne rendra pas le contrôle aveugle : ce n'est plus la source qu'on lit.
- **Toutes les adresses**, variables Jinja comprises (`{{ reponse.lien }}`,
  `{{ app.url }}/tickets/{{ ticket.id }}`, `mailto:…`) : chaque contrôle choisit
  ce qu'il vérifie, aucun ne choisit ce qu'il voit.
- **Un cas zéro intégré** : moins de `PLANCHER_LIENS` liens, et l'extraction
  lève au lieu de rendre des contrôles verts sur rien (`standards/04` §2).
"""

from __future__ import annotations

import functools
import re
from collections.abc import Iterable
from dataclasses import dataclass

#: Le préfixe qui rend une URL absolue dans un modèle.
BASE = "{{ app.url }}"

_BASE = re.compile(r"\{\{\s*app\.url\s*\}\}")

#: Les deux guillemets : un modèle peut écrire `href='…'` aussi bien que `href="…"`.
_HREF = re.compile(r"""\bhref\s*=\s*(["'])(.*?)\1""", re.DOTALL)

#: Il y en a 24 le 30/09/2026 : sous ce seuil, l'extraction ne lit plus les
#: modèles comme ils sont écrits, et les contrôles qui l'emploient ne mesurent rien.
PLANCHER_LIENS = 15


@dataclass(frozen=True)
class LienModele:
    """Une adresse d'un modèle d'e-mail, telle qu'elle est écrite dans le modèle composé."""

    modele: str  #: le code du modèle — `ticket_nouveau_cs`
    adresse: str  #: `{{ app.url }}/tickets/{{ ticket.id }}`, `{{ reponse.lien }}`, `mailto:…`

    @property
    def chemin(self) -> str | None:
        """Le chemin du front visé — `/tickets/{{ ticket.id }}` —, ou None.

        None quand l'adresse ne désigne pas une page lisible ici : un `mailto:`,
        la racine du site, ou un chemin fourni ENTIER par une variable
        (`{{ app.url }}{{ document.lien }}`), qui vient d'`EMPLACEMENTS` et y est
        vérifié ligne par ligne. Un segment variable (`{{ ticket.id }}`) reste
        tel quel : `aides_routes_front` le lit comme un segment dynamique `[id]`.
        """
        m = _BASE.match(self.adresse)
        if not m:
            return None
        reste = self.adresse[m.end() :]
        return reste if reste.startswith("/") else None


def extraire_liens(modeles: Iterable[tuple[str, str | None, str | None]]) -> tuple[LienModele, ...]:
    """Les adresses de `(code, sujet, corps)` — séparée de la lecture du seed pour
    qu'un contrôle prouve qu'il REFUSE, sur un modèle forgé."""
    return tuple(
        LienModele(code, adresse.strip())
        for code, sujet, corps in modeles
        for _guillemet, adresse in _HREF.findall(f"{sujet or ''} {corps or ''}")
    )


@functools.lru_cache(maxsize=None)
def liens_des_modeles_email() -> tuple[LienModele, ...]:
    """Toutes les adresses de tous les modèles d'e-mail, dans l'ordre du seed."""
    from app.seed import EMAIL_TEMPLATES

    liens = extraire_liens((code, sujet, corps) for code, _lib, sujet, corps, _d in EMAIL_TEMPLATES)
    assert len(liens) >= PLANCHER_LIENS, (
        f"seulement {len(liens)} lien(s) extraits des modèles d'e-mail (plancher "
        f"{PLANCHER_LIENS}) : l'extraction ne reconnaît plus la façon dont ils sont "
        "écrits, et les contrôles qui l'emploient ne mesurent plus rien."
    )
    return liens
