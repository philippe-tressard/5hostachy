"""Un **accès** — vigik ou télécommande — décrit une fois, par un objet.

## 🔴 Pourquoi (14/09/2026, #779)

`routers/acces/resident.py` portait **quatre paires de fonctions jumelles** :
lister les miens, signaler une perte, supprimer, déclarer. Chaque paire disait
la même chose deux fois, à trois mots près — le modèle, sa table de liaison, et
le nom du champ qui porte la référence (``code`` pour le vigik, ``reference``
pour la télécommande).

Le dépôt savait déjà que c'était un défaut : ``_acces_admin_out`` porte, écrit à
la main, *« les deux ont les mêmes champs utiles, et deux fonctions jumelles
auraient divergé au premier ajout »*. Et ``detacher_acces`` avait été factorisé
pour la même raison (#546) — au prix de **six paramètres** que chaque appelant
devait rappeler dans le bon ordre.

🔴 **Elles avaient bel et bien divergé**, et personne ne l'avait vu : à la
déclaration d'un badge, la branche vigik recopiait le ``lot_id`` de la ligne
d'import sur l'objet créé, la branche télécommande non. Une télécommande
déclarée par son porteur restait donc **sans lot** dans la vue du conseil
syndical, alors que l'import connaissait le lot. La factorisation corrige ce
défaut en passant — c'est ce qu'elle a de mieux à offrir.

## Ce que cet objet est, et ce qu'il n'est pas

Il ne remplace pas les deux modèles : ``Vigik`` et ``Telecommande`` restent deux
tables, parce que ce sont deux objets physiques distincts que l'on compte
séparément. Il décrit **ce qui, dans le code, change de l'un à l'autre** — et
rien d'autre. Tout ce qui n'est pas ici est commun, donc s'écrit une fois.

⚠️ Un troisième accès (une clé, un bip de portail) s'ajoute en déclarant une
entrée ici. S'il fallait en plus recopier quatre fonctions, il serait ajouté à
moitié — c'est précisément ce qui est arrivé au ``lot_id``.
"""
from dataclasses import dataclass

from app.models.core import (
    Telecommande,
    TelecommandeImport,
    UserTelecommande,
    UserVigik,
    Vigik,
    VigikImport,
)


@dataclass(frozen=True)
class TypeAcces:
    """Ce qui distingue un vigik d'une télécommande — la liste complète."""

    #: La valeur employée dans les URL et les corps de requête : `vigik`…
    cle: str
    #: Ce qu'un humain lit dans un message d'erreur.
    libelle: str
    #: La table de l'objet remis au porteur.
    modele: type
    #: La table d'attribution à plusieurs copropriétaires.
    modele_attribution: type
    #: La colonne de cette table qui pointe l'objet.
    colonne_attribution: str
    #: La table de staging de l'import Excel.
    modele_import: type
    #: La colonne de l'import qui pointe l'objet une fois résolu.
    colonne_import: str
    #: 🔴 La SEULE divergence de vocabulaire : le classeur des vigiks nomme sa
    #: référence `code`, celui des télécommandes `reference`. C'est cette
    #: différence-là qui rendait les deux branches « pas tout à fait pareilles »,
    #: et donc impossibles à relire ensemble.
    colonne_code_import: str

    @property
    def champ_code_import(self):
        """La colonne de l'import, prête pour un `where`."""
        return getattr(self.modele_import, self.colonne_code_import)


VIGIK = TypeAcces(
    cle="vigik",
    libelle="Vigik",
    modele=Vigik,
    modele_attribution=UserVigik,
    colonne_attribution="vigik_id",
    modele_import=VigikImport,
    colonne_import="vigik_id",
    colonne_code_import="code",
)

TELECOMMANDE = TypeAcces(
    cle="telecommande",
    libelle="Télécommande",
    modele=Telecommande,
    modele_attribution=UserTelecommande,
    colonne_attribution="telecommande_id",
    modele_import=TelecommandeImport,
    colonne_import="telecommande_id",
    colonne_code_import="reference",
)

#: Les accès connus, par leur clé d'URL — la source unique de « quels types
#: existent ». Un écran ou un routeur qui énumérerait « vigik ou telecommande »
#: à la main serait une seconde liste, libre de diverger.
TYPES_ACCES = {t.cle: t for t in (VIGIK, TELECOMMANDE)}
