"""Les publications — la copie GELÉE des actualités d'avant la bascule en affaires.

Extrait de `core.py` le 28/09/2026, au fil de l'eau (#779, modularité).

Depuis la migration 0210 (#1091), chaque publication est recopiée en affaire de
catégorie « Actualité » : ces deux tables ne sont plus lues que par la
redirection des anciens liens (`routers/publications`), qui cherche l'affaire
d'abord. Elles sont gardées le temps de pouvoir redescendre la 0210 sans
restauration ; leur suppression est #1177 — un module à retirer, désormais, et
non plus des lignes à démêler au milieu de `core.py`.

Ré-exportées par `core.py` : les imports existants ne bougent pas, et c'est cet
import qui enregistre les tables auprès de SQLModel.
"""

from typing import TYPE_CHECKING, List, Optional

from pydantic import NaiveDatetime
from sqlmodel import Field, Relationship

from app.models.evolution import EvolutionMixin
from app.utils import horloge
from app.utils.assiste_ia import AssisteIAMixin
from app.utils.saisi_pour import SaisiPourMixin

#  Références différées vers `core.py`, comme dans `copropriete.py` : `core`
#  importe CE module, un import réciproque réel formerait un cycle. SQLAlchemy
#  résout les chaînes par son registre de classes.
if TYPE_CHECKING:  # pragma: no cover
    from app.models.core import Utilisateur


class Publication(SaisiPourMixin, AssisteIAMixin, table=True):
    __tablename__ = "publication"
    id: Optional[int] = Field(default=None, primary_key=True)
    titre: str
    contenu: str
    perimetre: str = "résidence"  # résidence | bâtiment
    batiment_id: Optional[int] = Field(default=None, foreign_key="batiment.id")
    epingle: bool = False
    urgente: bool = False
    auteur_id: int = Field(foreign_key="utilisateur.id")
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    publiee_le: Optional[NaiveDatetime] = None
    #  -- Section « Quand » (#1092) ----------------------------------
    #  Une actualité datée — « Coupure d'eau jeudi 9h-12h » — paraît au
    #  calendrier sans qu'il faille en faire un troisième objet. Pas
    #  d'échéance ici : une actualité ne se suit pas, et une colonne que rien
    #  ne consomme ouvrirait un champ d'écran sans effet (cadre #430).
    debut: Optional[NaiveDatetime] = None
    fin: Optional[NaiveDatetime] = None
    mis_a_jour_le: Optional[NaiveDatetime] = None
    photos_urls: Optional[str] = None  # JSON array — même convention que Ticket/Evenement
    perimetre_cible: Optional[str] = Field(
        default='["résidence"]'
    )  # JSON: résidence|bat:{id}|parking|cave|résidents
    public_cible: Optional[str] = Field(
        default='["résidents"]'
    )  # JSON: résidents|locataires|copropriétaires
    # statut : publie (défaut, hors workflow) | en_cours | resolu | annule
    statut: Optional[str] = "publie"
    statut_change_le: Optional[NaiveDatetime] = None
    brouillon: bool = False
    archivee: bool = False
    partager_whatsapp: bool = False
    envoyer_syndic: bool = False
    envoyer_cs: bool = False
    annonce_hall: bool = False  # génère une affiche de hall à la publication
    #  Confidentiel : le périmètre redevient RESTRICTIF pour cette publication-là.
    #  Depuis #339, une actualité ciblée sur un bâtiment reste lisible de toute la
    #  copropriété ; ce drapeau rend la lecture au seul périmètre visé. Il ne fait
    #  que restreindre — il se combine en ET avec `public_cible` (cf. #347).
    confidentiel: bool = False

    auteur: Optional["Utilisateur"] = Relationship(back_populates="publications")
    evolutions: List["PublicationEvolution"] = Relationship(back_populates="publication")


class PublicationEvolution(EvolutionMixin, table=True):
    __tablename__ = "publication_evolution"
    id: Optional[int] = Field(default=None, primary_key=True)
    publication_id: int = Field(foreign_key="publication.id")
    # type : commentaire | etat — une correction est un `commentaire` préfixé « Correction : » (#433)
    #  Les sept champs communs — `type`, `contenu`, les deux statuts,
    #  l'auteur, la date et les pièces jointes — viennent d'`EvolutionMixin`.

    publication: Optional[Publication] = Relationship(back_populates="evolutions")
    auteur: Optional["Utilisateur"] = Relationship()
