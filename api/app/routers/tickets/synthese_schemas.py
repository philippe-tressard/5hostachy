"""Les corps et la réponse propres au routeur de la synthèse (#1643).

À côté de lui, et non dans `schemas_synthese.py` : un seul module s'en sert
(`test_schemas_morts.py`). `SyntheseLue`, partagée avec le carnet, reste là-bas.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.schemas_synthese import SyntheseLue


class SyntheseEtat(BaseModel):
    """Ce que la fiche demande : la synthèse lisible, et si l'on peut en produire une."""

    synthese: Optional[SyntheseLue] = None
    #: Vrai pour le conseil sur une affaire du carnet close sans synthèse (affaires
    #: d'avant la mise en service) — c'est le bouton « Produire la synthèse ».
    produisible: bool = False
    #: Une demande attend son délai de grâce : la synthèse arrive.
    en_attente: bool = False


class SyntheseModification(BaseModel):
    """« Modifier » : les trois textes, tout facultatif (PATCH partiel)."""

    synthese: Optional[str] = Field(default=None, max_length=20_000)
    difficultes: Optional[str] = Field(default=None, max_length=20_000)
    amelioration: Optional[str] = Field(default=None, max_length=20_000)


class SyntheseRelance(BaseModel):
    """« Relancer » : un complément ajouté au prompt de l'usage."""

    prompt_complement: str = Field(min_length=1, max_length=1_000)
