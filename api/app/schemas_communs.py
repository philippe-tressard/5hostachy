"""Le socle des schémas — ce dont tous les autres ont besoin, et qui ne dépend de rien.

Extrait de `schemas.py` le 19/08/2026 : le fichier venait de franchir les 500
lignes et le garde-fou de modularité (rang 1, `standards/02` §6) a refusé qu'il
grossisse pour recevoir le périmètre d'une évolution (#497).

⚠️ **Ce module n'importe RIEN du projet, et c'est sa raison d'être.** C'est ce
qui permet à `schemas_tickets.py` de s'en servir sans dépendre de `schemas.py`,
qui l'importe lui-même — un cycle rendrait l'ordre de chargement décisif pour le
démarrage de l'application.
"""
import json
from datetime import datetime
from typing import Annotated, List, Optional

from pydantic import BaseModel, BeforeValidator



def liste_depuis_json(v):
    """Colonne texte contenant un tableau JSON → liste d'URLs.

    Quatre schémas portaient ce même validateur recopié (`photos_urls`,
    `fichiers_urls` × 3). C'est la contrepartie côté pydantic de
    `app/utils/photos.parse_photos`, que les routeurs utilisent pour lire les
    mêmes colonnes : deux points d'entrée, une seule règle.

    Ne lève jamais : une valeur illisible en base ne doit pas faire échouer la
    lecture de l'élément qui la porte. Le pire cas est une liste vide.

    Publique (et non `_privée`) depuis le 16/08/2026 : le détail d'un sondage
    construit sa réponse à la main, sans `response_model`, et devait donc appeler
    la règle plutôt que la réécrire.
    """
    if v is None:
        return []
    if isinstance(v, str):
        try:
            charge = json.loads(v)
        except Exception:
            return []
        return [str(u) for u in charge] if isinstance(charge, list) else []
    return v


#: Champ exposé en liste, stocké en colonne texte. `Optional[ListeJson]` reste
#: possible là où l'absence et la liste vide doivent se distinguer.
#:
#: ⚠️ Ce type s'appelait `ListeJson` — un nom qui décrivait ses trois premiers
#: usages (photos, fichiers) et non ce qu'il fait. Le ciblage des sondages avait
#: exactement le même besoin pour des CODES de périmètre : soit on importait un
#: type nommé « URLs » pour des périmètres, soit on en écrivait un second,
#: identique. Renommé pour ce qu'il est — une liste sérialisée en JSON.
ListeJson = Annotated[List[str], BeforeValidator(liste_depuis_json)]

class ChampsIntervenant(BaseModel):
    """Intervenant, récurrence et équipement d'une affaire — conseil seul.

    Les trois formes du ticket (création, lecture, correction) portaient chacune
    les trois premiers champs, recopiés ; l'équipement (#1097) aurait fait la
    quatrième ligne de chaque copie. Les règles vivent dans `utils/intervenant`.
    """

    prestataire_id: Optional[int] = None
    frequence_type: Optional[str] = None
    frequence_valeur: Optional[int] = None
    equipement: Optional[str] = None


class EvolutionLue(BaseModel):
    """**Une entrée de fil, telle qu'un écran la reçoit** — les neuf champs
    communs aux trois historiques (ticket, actualité, événement).

    ## 🔴 Pourquoi ici (15/09/2026)

    Les trois schémas les déclaraient à l'identique… à un détail près, et ce
    détail est un défaut :

    | schéma | `fichiers_urls` |
    |---|---|
    | `TicketEvolutionRead` | `ListeJson` |
    | `PublicationEvolutionRead` | `ListeJson` |
    | `EvolutionEvenementRead` | `list[str]` — et un `parse_photos` **à la main** |

    La colonne stocke un tableau JSON. `ListeJson` le désérialise ; `list[str]`
    ne le fait pas, et le calendrier compensait en convertissant avant de
    valider. Les deux marchent — tant que personne n'ajoute un second chemin de
    lecture sans se rappeler de la conversion. Alors Pydantic reçoit une chaîne
    là où il attend une liste, et rejette l'entrée entière.

    ⚠️ C'est le motif que le dépôt connaît : deux copies qui divergent sur le
    cas limite, et celle qui compense est la plus fragile — elle marche par
    l'attention de qui la lit, pas par construction.

    ## Ce qu'il ne porte pas

    La clé du porteur (`ticket_id`, `publication_id`, `evenement_id`) et les
    champs propres à une entité (`perimetre_cible`, sur les tickets seuls).
    C'est exactement ce qui les distingue.
    """

    id: int
    #: `commentaire` ou `etat` — jamais un troisième. Une correction est un
    #: commentaire préfixé (`utils/corrections`).
    type: str
    contenu: Optional[str] = None
    ancien_statut: Optional[str] = None
    nouveau_statut: Optional[str] = None
    auteur_id: int
    #: Composé par le serveur : l'écran ne rapproche pas un identifiant d'un nom.
    auteur_nom: Optional[str] = None
    cree_le: datetime
    fichiers_urls: ListeJson = []
    #: « Rédigé avec l'assistant IA » (#985). Déclaré ici et non par le mixin
    #: `AssisteIASortie` : ce module n'importe RIEN du projet, c'est sa raison
    #: d'être (voir l'en-tête).
    assiste_ia: bool = False

    class Config:
        from_attributes = True
