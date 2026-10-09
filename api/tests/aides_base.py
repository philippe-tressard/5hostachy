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
import weakref

from sqlalchemy import event, text
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
    #  🐘 Sur PostgreSQL quand `TESTS_BASE_URL` le demande (#1747) : le workflow
    #  « PostgreSQL » rejoue ainsi toute la suite sur le moteur cible (D4), sans
    #  qu'un seul test change. Ailleurs, rien ne change.
    url = os.environ.get("TESTS_BASE_URL")
    if url:
        return _moteur_postgresql(url, schema=schema)
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


def _moteur_postgresql(url: str, *, schema: bool):
    """Une base PostgreSQL propre à l'appelant : un SCHÉMA neuf, retiré à sa libération.

    Un schéma par moteur rend à chaque test la base vide qu'il reçoit de SQLite en
    mémoire. `search_path` le fait seul visible ; il est supprimé quand le moteur
    est libéré (fin du test), sans quoi des milliers de schémas s'accumuleraient
    dans le catalogue au fil de la suite. `partage` et `cles_etrangeres` n'ont pas
    d'objet : PostgreSQL sert plusieurs fils, et vérifie toujours ses clés.
    """
    nom = f"t_{uuid.uuid4().hex[:16]}"
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'CREATE SCHEMA "{nom}"'))  # noqa: S608 — identifiant généré ici
    moteur = create_engine(url)

    #  Posé à CHAQUE connexion, par SQL : le pilote (pg8000) n'accepte pas
    #  l'option de démarrage `options` qu'emploie psycopg.
    @event.listens_for(moteur, "connect")
    def _schema(dbapi_connection, _record):
        curseur = dbapi_connection.cursor()
        curseur.execute(f'SET search_path TO "{nom}"')
        curseur.close()

    if schema:
        SQLModel.metadata.create_all(moteur)

    def _retirer(admin=admin, nom=nom):
        try:
            with admin.connect() as c:
                c.execute(text(f'DROP SCHEMA IF EXISTS "{nom}" CASCADE'))  # noqa: S608
        finally:
            admin.dispose()

    weakref.finalize(moteur, _retirer)
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
