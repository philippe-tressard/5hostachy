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

import os
import uuid
import warnings

from sqlalchemy import event, text
from sqlalchemy.pool import NullPool, StaticPool
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
    #  🐘 Sur PostgreSQL quand `TESTS_BASE_URL` le demande (#1747) : le workflow
    #  « PostgreSQL » rejoue ainsi toute la suite sur le moteur cible (D4), sans
    #  qu'un seul test change. Ailleurs, rien ne change.
    url = os.environ.get("TESTS_BASE_URL")
    if url:
        return _moteur_postgresql(url, schema=schema, cles_etrangeres=cles_etrangeres)
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


#: Les schémas PostgreSQL posés pendant le test en cours — retirés par la fixture
#: `_retirer_schemas_postgresql` de `conftest.py` à la fin du test.
_SCHEMAS_DU_TEST: list[tuple[object, str]] = []


def _moteur_postgresql(url: str, *, schema: bool, cles_etrangeres: bool):
    """Une base PostgreSQL propre à l'appelant : un SCHÉMA neuf, retiré à la fin du test.

    Un schéma par moteur rend à chaque test la base vide qu'il reçoit de SQLite en
    mémoire ; `search_path` le fait seul visible.

    🔴 **Retiré à la fin du TEST, pas à la libération du moteur** : un moteur gardé
    en vie par une référence de module (un `engine` remplacé, une fermeture) ne
    l'était qu'à la sortie du processus. Deux mesures complètes ont rempli ainsi
    le disque de la base d'essai, en plein passage (09/10/2026).

    **Le régime des clés est celui de SQLite** : désactivées sauf
    `cles_etrangeres=True`, comme `moteur_memoire` le fait en mémoire. PostgreSQL
    les vérifie toujours ; `session_replication_role = replica` suspend leurs
    déclencheurs pour la connexion — sans quoi chaque fixture qui écrit un enfant
    sans son parent, permise sous SQLite, échouait ici.
    """
    nom = f"t_{uuid.uuid4().hex[:16]}"
    #  🔴 NullPool : une connexion se FERME dès qu'elle est rendue. Avec un pool,
    #  chaque base de test gardait les siennes jusqu'au ramasse-miettes, et la
    #  suite dépassait `max_connections` (« too many clients », 09/10/2026).
    admin = create_engine(url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    with admin.connect() as c:
        c.execute(text(f'CREATE SCHEMA "{nom}"'))  # noqa: S608 — identifiant généré ici
    _SCHEMAS_DU_TEST.append((admin, nom))
    reglages = f'SET search_path TO "{nom}"'
    if not cles_etrangeres:
        reglages += "; SET session_replication_role = replica"
    moteur = create_engine(url, poolclass=NullPool)

    @event.listens_for(moteur, "connect")
    def _regler(dbapi_connection, _record):
        curseur = dbapi_connection.cursor()
        curseur.execute(reglages)
        curseur.close()
        dbapi_connection.commit()

    if schema:
        SQLModel.metadata.create_all(moteur)
    return moteur


def retirer_schemas_postgresql() -> None:
    """Retire les schémas posés par le test qui s'achève — appelé par `conftest.py`."""
    while _SCHEMAS_DU_TEST:
        admin, nom = _SCHEMAS_DU_TEST.pop()
        try:
            with admin.connect() as c:
                #  Une connexion restée ouverte (un client HTTP de test) bloquerait
                #  le retrait : on attend 10 s, puis on laisse le schéma au
                #  conteneur jetable plutôt que de figer la suite.
                c.execute(text("SET lock_timeout = '10s'"))
                c.execute(text(f'DROP SCHEMA IF EXISTS "{nom}" CASCADE'))  # noqa: S608
        except Exception as exc:  # noqa: BLE001 — un retrait manqué ne fait pas échouer le test
            warnings.warn(f"schéma de test {nom} non retiré : {exc}", stacklevel=1)
        finally:
            admin.dispose()


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
