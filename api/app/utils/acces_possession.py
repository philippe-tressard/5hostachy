"""Qui détient un accès, et où il se trouve physiquement — écrit une fois.

## Pourquoi ce module (18/09/2026, #779)

Ces deux règles vivaient dans `routers/acces/socle_imports.py`, qui les avait
déjà rassemblées pour les deux chaînes d'import (#847). Elles n'y étaient
pourtant pas à leur place : ce ne sont pas des règles de **routage**, ce sont
des règles du domaine — *qui a le badge en main*. La preuve est qu'un troisième
appelant en avait besoin et ne pouvait pas les prendre.

Cet appelant est `utils/auto_match_service.py`, qui résout les mêmes lignes
d'import à l'activation d'un compte. Il ne pouvait pas importer le socle — le
socle importe déjà `auto_match_service`, et le cycle aurait cassé le
démarrage — donc il les **réécrivait**. Et il les réécrivait à moitié :

| Règle | Résolution par un écran | Résolution automatique |
|---|---|---|
| détenteur (locataire ou propriétaire) | `possesseur()` | recopiée, identique |
| `chez_locataire` sur la télécommande | reporté | reporté |
| `chez_locataire` sur le **vigik** | reporté | 🔴 **perdu** |

🔴 C'est exactement le défaut que #847 a corrigé côté écran, et il survivait
côté automatique. Sa conséquence est la même : `routers/bailleur/acces.py` ne
propose au transfert que les accès `not chez_locataire`. Un vigik résolu au
bénéfice d'un locataire arrivait donc marqué « chez le propriétaire », et se
proposait au transfert vers le locataire suivant alors qu'il était déjà, dans la
vraie vie, dans la poche du locataire en place.

⚠️ La leçon n'est pas « il fallait mieux relire ». Une règle rangée dans le
module d'un appelant est une règle que le deuxième appelant ne peut pas prendre
même s'il le veut : le cycle d'import l'en empêche, et il recopie. Ce fichier
n'appartient à personne, et c'est ce qui le rend prenable.
"""
from __future__ import annotations

from typing import Optional


def possesseur(imp) -> Optional[int]:
    """Qui détient l'accès : le locataire s'il l'a en main, le propriétaire sinon.

    🔴 La règle centrale des deux chaînes. Elle était écrite **quatre** fois — deux
    fois par type, à la résolution et à la correction — et un seul de ces quatre
    endroits aurait suffi à faire diverger le détenteur affiché de celui
    enregistré. Deux de plus vivaient dans l'appariement automatique.
    """
    if imp.chez_locataire and imp.user_locataire_id:
        return imp.user_locataire_id
    return imp.user_proprietaire_id


def chez_le_locataire(imp) -> bool:
    """La possession physique, telle qu'elle doit être écrite sur l'objet.

    ⚠️ `and bool(user_locataire_id)` n'est pas une précaution : un import coché
    « chez le locataire » sans locataire lié produirait un objet marqué comme remis
    à quelqu'un qui n'existe pas, et `bailleur/acces.py` refuserait ensuite de le
    transférer sans pouvoir dire à qui il est.
    """
    return bool(imp.chez_locataire) and bool(imp.user_locataire_id)
