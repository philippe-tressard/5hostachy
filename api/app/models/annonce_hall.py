"""La table des annonces de hall — l'affiche PDF punaisée dans les halls.

Extraite de `models/core.py` le 15/08/2026, au fil de l'eau : ce fichier était à
1 433 lignes et le contrôle de modularité refuse qu'un fichier déjà au-dessus de
500 grossisse (rang 1 §4). Il fallait y ajouter le drapeau `confidentiel` des
actualités (#347) — et c'est justement l'affiche de hall que la confidentialité
interdit, les deux notions se touchent donc dans le même lot.

Même parti pris que `models/sauvegarde.py` : c'est un bloc qui se détache
proprement — une table sans aucune `Relationship` vers le reste du modèle, dont
les seuls liens sont deux clés étrangères déclarées par nom de table.

⚠️ `core.py` la **ré-exporte** : les fichiers qui écrivent
`from app.models.core import AnnonceHall` continuent de fonctionner, et c'est cet
import qui enregistre la table dans les métadonnées SQLModel.
"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class AnnonceHall(SQLModel, table=True):
    """Annonce imprimable affichée dans le hall des bâtiments (PDF A4 / A5).

    Le PDF est généré à la création puis figé sur disque : il fait foi (c'est
    lui qui a été envoyé au CS et affiché dans le hall). Une correction passe
    donc par une nouvelle annonce, jamais par une régénération silencieuse.
    """
    __tablename__ = "annonce_hall"
    id: Optional[int] = Field(default=None, primary_key=True)
    titre: str
    message: str                                    # HTML riche (RichEditor)
    perimetre_cible: str = '["résidence"]'          # JSON: résidence|bat:{id}|parking|cave|aful
    format_demande: str = "auto"                    # auto | a4 | a5
    format_effectif: str = "a4"                     # a4 | a5
    images_json: str = "[]"                         # JSON: photos facultatives (max 2)
    pdf_chemin: str = ""                            # chemin du PDF dans le volume uploads
    pdf_nom: str = ""                               # nom proposé au téléchargement
    taille_octets: Optional[int] = None
    destinataires: str = "[]"                       # JSON: emails notifiés
    envoye_le: Optional[datetime] = None
    archivee: bool = False
    # Publication d'origine si l'annonce a été générée depuis une actualité
    publication_id: Optional[int] = Field(default=None, foreign_key="publication.id")
    auteur_id: int = Field(foreign_key="utilisateur.id")
    cree_le: datetime = Field(default_factory=datetime.utcnow)
