"""Périmètres — l'arborescence qui dit OÙ se situe une demande.

Module à part, et non une classe de plus dans `core.py` : ce fichier passait
1 506 lignes avant ce lot, et la règle de modularité — rang 1, sans exception —
refuse qu'un fichier au-delà de 500 lignes grossisse pour une nouvelle
fonctionnalité. Le pré-check l'a refusé, à juste titre.

`Perimetre` est réexporté par `app.models.core`, si bien que les imports
existants (`from app.models.core import Perimetre`) continuent de fonctionner —
et surtout que la table reste enregistrée auprès de SQLModel au moment du
`create_all`, ce qu'un module jamais importé ne garantirait pas.
"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Perimetre(SQLModel, table=True):
    """Arborescence des périmètres — **où** se situe une demande.

    Remplace la table de libellés qui était écrite en dur à deux endroits, avec
    deux contenus différents : `utils/perimetres.py` couvrait `bat:1` à `bat:9`,
    `front/src/lib/utils.ts` s'arrêtait à `bat:4`. Un cinquième bâtiment
    s'affichait donc « Bât. 5 » côté API et `bat:5` brut à l'écran.

    **Aucun code de périmètre n'existe plus dans le code.** Le produit doit servir
    une autre copropriété, qui n'a ni AFUL, ni quatre bâtiments, ni forcément de
    caves : cet arbre est intégralement reconstructible depuis l'administration, et
    le vider ne doit rien casser (un périmètre vide vaut « concerne tout le monde »,
    comme aujourd'hui).

    À ne pas confondre avec `Document.perimetre` / `CategorieDocument.perimetre_defaut`
    (`résidence` / `bâtiment` / `lot`), qui portent le même nom mais répondent à une
    autre question : non pas *où* se passe une demande, mais *qui a le droit de lire*
    un fichier. Les deux axes restent distincts — le glossaire nomme le second
    « granularité documentaire ».
    """
    __tablename__ = "perimetre"
    id: Optional[int] = Field(default=None, primary_key=True)

    #: Ce qui est stocké dans les contenus (`ticket.perimetre_cible`,
    #: `evenement.perimetre`…). **Immuable après création** : le changer
    #: orphelinerait les tickets déjà publiés.
    code: str = Field(unique=True, index=True)
    parent_id: Optional[int] = Field(default=None, foreign_key="perimetre.id")

    libelle: str
    libelle_court: Optional[str] = None
    description: str = ""
    icone: Optional[str] = None  # nom d'icône Lucide, rendu par Icon.svelte

    #: Rattachement réel au bâtiment, en clé étrangère — remplace le préfixe
    #: textuel `bat:` qui était analysé à sept endroits du dépôt. Les descendants
    #: d'un nœud de bâtiment en héritent par remontée d'arbre.
    batiment_id: Optional[int] = Field(default=None, foreign_key="batiment.id")

    #: ⚠️ Décision de sécurité. Remplace la liste `SCOPES_RESIDENCE`, qui existait
    #: en trois exemplaires. Un nœud à portée globale, ou dont un ancêtre l'est,
    #: est visible de tous les résidents et notifie l'ensemble du conseil syndical.
    portee_globale: bool = Field(default=False)

    #: Un nœud de regroupement (« Bâtiments ») ne se cible pas. Sert aussi à
    #: retirer un périmètre de la saisie sans casser l'historique : `cave` reste
    #: affiché sur les contenus déjà publiés, sans être proposé aux nouveaux.
    selectionnable: bool = Field(default=True)

    ordre: int = Field(default=0)
    actif: bool = Field(default=True)

    cree_le: datetime = Field(default_factory=datetime.utcnow)
    modifie_le: Optional[datetime] = None
    modifie_par_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
