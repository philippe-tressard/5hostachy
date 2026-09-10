"""Router carnet d'entretien — la lecture de l'histoire du bâti.

Un routeur à lui seul, et non trois routes de plus dans `copropriete.py` : ce
fichier était à 478 lignes, et le plafond de modularité (rang 1) refuse qu'un
fichier déjà proche des 500 les franchisse pour une fonctionnalité neuve.

## Le droit : copropriétaires, conseil syndical, admin

Arbitré par Philippe le 10/09/2026. Le décret n° 2001-477 destine le carnet aux
**copropriétaires** — un acquéreur peut le réclamer via son vendeur —, et il porte
des références de contrats qui ne regardent pas un locataire.

🔴 **Aucune règle n'est écrite ici** : `require_proprietaire` disait déjà
exactement cela (propriétaire **ou** conseil syndical **ou** admin). Réécrire la
condition dans ce fichier en aurait fait une seconde version, libre de diverger au
premier durcissement — c'est `standards/03` §1, et c'est la dérive que
`_require_bailleur` avait produite sur dix-sept endpoints.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.auth.deps import require_proprietaire
from app.database import get_session
from app.models.core import Utilisateur
from app.utils.carnet_entretien import construire_carnet

router = APIRouter(prefix="/carnet-entretien", tags=["carnet d'entretien"])


@router.get("")
def lire_carnet(
    perimetre: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_proprietaire),
):
    """Le carnet, éventuellement restreint à un PÉRIMÈTRE.

    ⚠️ `perimetre` est un **code de l'arborescence** (`"bat:3"`, `"parking"`),
    pas un identifiant de bâtiment. C'est ce qui permet de filtrer sur des
    espaces qui n'ont pas de bâtiment — et de suivre un périmètre créé demain en
    administration, sans migration ni déploiement.

    Le filtre lui-même n'est pas écrit ici : `couvre()` (arbre des périmètres)
    répond à « cette ligne entre-t-elle dans ce que l'utilisateur regarde ? », et
    c'est la même question sur toutes les pages qui filtrent.
    """
    entrees = construire_carnet(session, perimetre=perimetre)
    return {
        "entrees": entrees,
        #  Le compte est rendu par le SERVEUR plutôt que déduit de la longueur du
        #  tableau : l'écran affiche « n interventions » à côté d'un filtre, et
        #  recompter côté client donnerait un chiffre juste tant que la pagination
        #  n'existe pas — c'est-à-dire jusqu'au jour où elle existera.
        "total": len(entrees),
    }
