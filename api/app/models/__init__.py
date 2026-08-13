"""Modèles SQLModel.

`Perimetre`, et depuis le 13/08/2026 `Copropriete`/`Batiment`/`Lot`,
vivent dans leur propre module — `core.py` dépasse 1 500 lignes et la
règle de modularité (rang 1) refuse qu'un fichier au-delà de 500 lignes grossisse
pour une nouvelle fonctionnalité. Le pré-check MEP l'a refusé, à juste titre.

L'import ci-dessous n'est pas décoratif : c'est lui qui enregistre la table
auprès de SQLModel avant `create_all`. Un modèle défini dans un module que
personne n'a importé n'existe pas pour `metadata.create_all`, et la table
manquerait sans le moindre message.
"""
from app.models.copropriete import (  # patrimoine PHYSIQUE, extrait le 13/08/2026
    Batiment as Batiment,
    Copropriete as Copropriete,
    Lot as Lot,
)
from app.models.perimetre import Perimetre as Perimetre
