"""**Qui est qui** — les rôles, les statuts, et la hiérarchie qui les départage.

Extrait de `core.py` le 15/09/2026 (modularité, rang 1) : le fichier était à 924
lignes et ne pouvait plus grossir pour recevoir la règle ci-dessous. Même geste
que `tickets.py` (17/08) et `whatsapp.py` (05/09), même conséquence : tout est
**ré-exporté par `core.py`**, donc aucun des appelants ne change et SQLModel
continue de connaître les énumérations.

## Rôle ≠ statut

Le **rôle** dit ce qu'un compte a le droit de faire ; le **statut** dit ce qu'une
personne est dans la copropriété. Un copropriétaire bailleur peut siéger au
conseil syndical : deux axes, jamais un. La contrepartie front est
`front/src/lib/roles.ts`, et `api/tests/test_roles_libelles.py` échoue si les
deux divergent.
"""

from __future__ import annotations

from enum import Enum


class StatutUtilisateur(str, Enum):
    copropriétaire_résident = "copropriétaire_résident"
    copropriétaire_bailleur = "copropriétaire_bailleur"
    locataire = "locataire"
    syndic = "syndic"
    mandataire = "mandataire"
    aidant = "aidant"  # proche aidant (famille) — accès délégué, pas de vote AG
    admin_technique = "admin_technique"  # compte technique sans lot ni statut résidentiel


class RoleUtilisateur(str, Enum):
    propriétaire = "propriétaire"
    résident = "résident"
    externe = "externe"
    conseil_syndical = "conseil_syndical"
    admin = "admin"


#  🔴 LA HIÉRARCHIE DES RÔLES — écrite UNE fois (15/09/2026).
#
#  Elle l'était **deux fois**, avec sa fonction de classement, dans
#  `Utilisateur.ajouter_role` et `Utilisateur.retirer_role` — vingt-cinq lignes
#  d'écart, dans le même fichier. Deux copies dans un même fichier ne se voient
#  pas : relire l'une ne montre jamais l'autre (`standards/02` §1 ter).
#
#  ⚠️ C'est la table la plus sensible du modèle : elle décide quel rôle s'affiche
#  et lequel fait autorité quand un compte en porte plusieurs. Un sixième rôle
#  ajouté à une seule des deux copies aurait valu **0** dans l'autre — donc perdu
#  contre n'importe quel rôle existant, en silence.
#
#  `résident` et `externe` partagent le rang 1 : ni l'un ni l'autre ne donne de
#  droit particulier, et les départager ferait croire à une préséance qui
#  n'existe pas.
#
#  📖 Elle ne décide **aucun droit** : l'autorisation est centralisée dans
#  `app/auth/deps.py` et se demande toujours par `has_role(...)`, qui interroge
#  la LISTE des rôles portés. Cette table ne sert qu'à choisir lequel **montrer**.
PRIORITE_ROLE: dict[RoleUtilisateur, int] = {
    RoleUtilisateur.admin: 4,
    RoleUtilisateur.conseil_syndical: 3,
    RoleUtilisateur.propriétaire: 2,
    RoleUtilisateur.résident: 1,
    RoleUtilisateur.externe: 1,
}


def rang_role(role: str) -> int:
    """Le rang d'un rôle. **0 pour un inconnu** — jamais une erreur.

    Un rôle que l'énumération ne connaît plus vient d'une base plus vieille que
    le code. Lever ici empêcherait de lire le compte ; le classer dernier le
    laisse lisible et le fait perdre contre tout rôle vivant.
    """
    try:
        return PRIORITE_ROLE.get(RoleUtilisateur(role), 0)
    except ValueError:
        return 0


def role_principal(roles: list[str], *, defaut: str) -> RoleUtilisateur | None:
    """Le plus élevé des rôles portés, ou `None` s'il n'est pas lisible.

    `None` plutôt qu'une exception : l'appelant garde alors le rôle qu'il avait,
    ce qui est toujours une valeur valide — là où lever laisserait l'objet à
    moitié modifié, avec sa liste de rôles à jour et son rôle principal périmé.
    """
    try:
        return RoleUtilisateur(max(roles, key=rang_role, default=defaut))
    except ValueError:
        return None
