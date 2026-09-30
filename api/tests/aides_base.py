"""Une base de test et des comptes de test, écrits une fois (#1495).

## Pourquoi cette aide existe (30/09/2026)

- **La base en mémoire** (`create_engine("sqlite://")` + `create_all`) était
  recopiée dans trente-quatre fichiers ; la version « de référence » vivait dans
  `aides_badges.py`, un nom qui n'avait rien à voir, importé par des tests qui
  ne parlaient pas de badges. Elle est ici, et `conftest.py` en fait la fixture
  `session` que tout test reçoit sans l'importer.
- **La fabrique de compte** était recopiée dans quarante-huit fichiers — avec,
  dans chacun, un mot de passe passé sous un nom de champ qui **n'existe
  pas** dans `Utilisateur` (le vrai est `hashed_password`). SQLModel l'ignorait sans un mot ; la
  copie s'est propagée parce que personne ne pouvait la voir échouer.
"""

from __future__ import annotations

import uuid

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.models.core import Utilisateur


def moteur_memoire(*, partage: bool = False, schema: bool = True, cles_etrangeres: bool = False):
    """Un moteur SQLite en mémoire, schéma posé — sauf `schema=False`.

    `schema=False` rend une base VIDE : c'est ce qu'il faut pour rejouer une
    migration sur les tables qu'elle trouvait, écrites à la main par le test.

    `cles_etrangeres=True` branche la règle de l'APPLICATION
    (`app.database.activer_cles_etrangeres`) AVANT la première connexion : posé
    après, l'écouteur ne se déclencherait jamais — le piège que cette fonction
    décrit. Un test ne réécrit pas l'écouteur.

    `partage=True` garde UNE connexion pour tout le moteur (`StaticPool`) : c'est
    ce qu'il faut quand un `TestClient` lit la base depuis un autre fil que le
    test — sans elle, chaque connexion ouvre une base vide.
    """
    if partage:
        moteur = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    else:
        moteur = create_engine("sqlite://")
    if cles_etrangeres:
        from app.database import activer_cles_etrangeres

        activer_cles_etrangeres(moteur)
    if schema:
        SQLModel.metadata.create_all(moteur)
    return moteur


def compte(session: Session, *, prefixe: str = "compte", **champs) -> Utilisateur:
    """Un compte ACTIF, de courriel unique, écrit et relu.

    Tout champ d'`Utilisateur` se passe par nom (`roles_json=`, `statut=`,
    `role=`, `prenom=`…) et prime sur les défauts. Un nom qui n'est PAS un champ
    lève : c'est ce qui a manqué pendant que le faux champ se recopiait.
    """
    inconnus = set(champs) - set(Utilisateur.model_fields)
    assert not inconnus, f"champ(s) inconnu(s) d'Utilisateur : {sorted(inconnus)}"
    valeurs = {
        "email": f"{prefixe}-{uuid.uuid4().hex[:8]}@exemple.test",
        "hashed_password": "x",
        "prenom": "Prénom",
        "nom": "Nom",
        "actif": True,
    }
    valeurs.update(champs)
    u = Utilisateur(**valeurs)
    session.add(u)
    session.commit()
    session.refresh(u)
    return u
