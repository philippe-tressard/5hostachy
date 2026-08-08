"""Périmètres — libellés et analyse, écriture unique.

Un périmètre (« résidence », « bat:3 », « parking ») se lit et s'affiche au même
endroit partout. Il était écrit **trois fois** dans le dépôt le 08/08/2026 :

- `app/routers/flux/commun.py` — table complète, bâtiments 1 à 9, AFUL ;
- `app/routers/tickets.py` (relance syndic) — table partielle : ni AFUL, ni
  bâtiment au-delà de ce que le préfixe `bat:` produisait, et un rendu vide
  quand le champ est absent ;
- `front/src/lib/utils.ts` (`perimetreLabel`) — côté interface.

Les deux tables Python ne donnaient donc pas le même libellé pour un même
périmètre : un ticket ciblé AFUL sortait « aful » dans l'e-mail de relance et
« AFUL » dans le fil. C'est la divergence typique décrite par
`standards/02-factorisation.md` §2.
"""
import json
from typing import Optional

#: Nombre de bâtiments couverts par la table. Au-delà, `bat:N` retombe sur un
#: libellé calculé — aucun périmètre ne reste jamais affiché en brut.
_BATIMENTS = 9

LABELS: dict[str, str] = {
    "résidence": "Copropriété entière",
    "parking": "Parking",
    "cave": "Cave",
    "aful": "AFUL",
    **{f"bat:{i}": f"Bât. {i}" for i in range(1, _BATIMENTS + 1)},
}


def libelle_un(perim: str) -> str:
    """Libellé d'un périmètre isolé, y compris un bâtiment hors table."""
    if perim in LABELS:
        return LABELS[perim]
    if perim.startswith("bat:"):
        return f"Bât. {perim[4:]}"
    return perim


def libelle(perims: list[str]) -> str:
    """« Bât. 1 · Parking » — le rendu commun à toutes les rubriques."""
    return " · ".join(libelle_un(p) for p in perims)


def depuis_texte(perimetre: Optional[str]) -> list[str]:
    """Champ `perimetre` en texte (« résidence », « parking,cave »)."""
    if not perimetre:
        return ["résidence"]
    return [s.strip() for s in perimetre.split(",") if s.strip()]


def depuis_json(perimetre_cible: Optional[str]) -> list[str]:
    """Champ `perimetre_cible` en JSON (ex. '["bat:1","bat:3"]').

    Un contenu illisible retombe sur « résidence » plutôt que de lever : ce champ
    alimente un affichage, il ne doit jamais faire échouer une requête.
    """
    if not perimetre_cible:
        return ["résidence"]
    try:
        val = json.loads(perimetre_cible) if isinstance(perimetre_cible, str) else perimetre_cible
        return list(val) if isinstance(val, (list, tuple)) else ["résidence"]
    except Exception:
        return ["résidence"]


def libelle_json(perimetre_cible: Optional[str], *, vide: str = "") -> str:
    """Libellé direct depuis un champ JSON.

    `vide` est rendu quand le champ est absent — l'e-mail de relance syndic
    n'affiche alors aucune ligne « périmètre », là où le fil affiche
    « Copropriété entière ». Deux besoins légitimes, un seul paramètre, plutôt
    que deux tables.
    """
    if not perimetre_cible:
        return vide
    return libelle(depuis_json(perimetre_cible))
