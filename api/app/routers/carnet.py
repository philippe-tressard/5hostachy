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
from sqlmodel import Session, select

from app.auth.deps import require_proprietaire
from app.database import get_session
from app.models.core import Batiment, Utilisateur
from app.utils.batiments import libelle_batiment
from app.utils.carnet_entretien import construire_carnet

router = APIRouter(prefix="/carnet-entretien", tags=["carnet d'entretien"])


@router.get("")
def lire_carnet(
    batiment_id: Optional[int] = Query(default=None),
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_proprietaire),
):
    """Le carnet, éventuellement restreint à un bâtiment.

    Rend aussi la table des bâtiments : l'écran a besoin de leurs noms pour
    étiqueter chaque entrée, et les demander un par un ferait une requête par
    ligne. Le libellé vient de `libelle_batiment`, jamais d'un `f"Bât. {id}"` —
    deux formes de ce libellé ont déjà divergé dans ce dépôt.
    """
    batiments = {
        batiment.id: libelle_batiment(batiment)
        for batiment in session.exec(select(Batiment)).all()
    }
    entrees = construire_carnet(session, batiment_id=batiment_id)
    return {
        "entrees": entrees,
        "batiments": [
            {"id": identifiant, "nom": nom} for identifiant, nom in sorted(batiments.items())
        ],
        #  Le compte est rendu par le SERVEUR plutôt que déduit de la longueur du
        #  tableau : l'écran affiche « n interventions » à côté d'un filtre, et
        #  recompter côté client donnerait un chiffre juste tant que la pagination
        #  n'existe pas — c'est-à-dire jusqu'au jour où elle existera.
        "total": len(entrees),
    }
