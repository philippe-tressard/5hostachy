"""Modèles SQLModel.

`Perimetre` vit dans son propre module — `core.py` dépasse 1 500 lignes et la
règle de modularité (rang 1) refuse qu'un fichier au-delà de 500 lignes grossisse
pour une nouvelle fonctionnalité. Le pré-check MEP l'a refusé, à juste titre.

L'import ci-dessous n'est pas décoratif : c'est lui qui enregistre la table
auprès de SQLModel avant `create_all`. Un modèle défini dans un module que
personne n'a importé n'existe pas pour `metadata.create_all`, et la table
manquerait sans le moindre message.
"""
from app.models.perimetre import Perimetre as Perimetre
