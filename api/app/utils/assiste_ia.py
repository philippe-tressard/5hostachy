"""**« Rédigé avec l'assistant IA »** — la marque qu'un texte a été retravaillé.

## La notion (#985, 17/09/2026)

Quand l'auteur applique une proposition de l'assistant (`utils/assistant_description`)
puis enregistre, l'objet porte `assiste_ia = True`. L'écran le rend par un petit
✨ discret à côté de l'auteur — *« l'auteur reste, l'icône dit que l'IA a modifié
la réponse manuelle »* (arbitrage du 17/09/2026).

⚠️ Ce n'est PAS un encart dans le texte : une description n'est pas un document
réglementaire comme la synthèse d'un contrat, et un marqueur caché dans le HTML
ne survivrait pas à l'assainisseur. C'est une colonne, sur chaque entité qui
porte une section Description.

## Pourquoi un mixin

Neuf tables reçoivent la notion — ticket, publication, événement, leurs trois
fils, sondage, idée, annonce. Neuf déclarations de la même colonne, avec la
même valeur par défaut, seraient neuf occasions de diverger : c'est exactement
ce qui est arrivé à `fichiers_urls` (`models/evolution.py`). Le mixin décrit le
socle ; l'entité l'hérite.

## Ce que la marque VEUT dire, et ce qu'elle ne dit pas

Elle dit que l'assistant a contribué au texte enregistré. Elle ne dit pas que
le texte est celui du modèle : l'auteur a pu le retoucher après. C'est pourquoi
elle ne se RETIRE pas à la correction suivante — le client ne l'envoie qu'à
`True`, quand une proposition a été appliquée dans le formulaire, et ne l'envoie
pas sinon (`AssisteIACorrection`).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel
from sqlmodel import Field, SQLModel

CHAMP = "assiste_ia"


class AssisteIAMixin(SQLModel):
    """La colonne, héritée plutôt que recopiée neuf fois."""

    #  `server_default` : une base NEUVE (`create_all`) porte le même défaut que
    #  les bases migrées (0194, 0220, 0225 posent toutes `server_default="0"`).
    #  Sans lui, un INSERT qui ne nomme pas la colonne passait en production et
    #  échouait sur une base neuve (#1327).
    assiste_ia: bool = Field(default=False, sa_column_kwargs={"server_default": "0"})


class AssisteIAEntree(BaseModel):
    """Ce qu'un formulaire de CRÉATION envoie — vrai si une proposition a été
    appliquée avant d'enregistrer."""

    assiste_ia: bool = False


class AssisteIACorrection(BaseModel):
    """Ce qu'un formulaire de CORRECTION envoie.

    `None` = « je n'en dis rien », et l'objet garde sa marque : une correction
    sans l'assistant n'efface pas la contribution passée. Seul `True` s'écrit.
    """

    assiste_ia: Optional[bool] = None


class AssisteIASortie(BaseModel):
    """Ce qu'un écran REÇOIT."""

    assiste_ia: bool = False


def marquer(objet, body) -> None:
    """Pose la marque depuis une correction — dans UN sens seulement.

    Un `False` ne s'écrit pas : la marque dit qu'une contribution a eu lieu,
    et cela reste vrai après une retouche à la main.
    """
    if getattr(body, CHAMP, None) is True:
        setattr(objet, CHAMP, True)


__all__ = [
    "CHAMP",
    "AssisteIACorrection",
    "AssisteIAEntree",
    "AssisteIAMixin",
    "AssisteIASortie",
    "marquer",
]
