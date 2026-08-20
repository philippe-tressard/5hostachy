"""🔴 La DERNIÈRE migration est réellement EXÉCUTÉE, pas seulement lue.

## Pourquoi ce fichier existe (#553, 20/08/2026)

`test_migrations.py` vérifie le **graphe** des révisions : un seul head, une
seule base, pas de doublon. C'est nécessaire et cela ne dit rien de ce que la
migration FAIT. Son en-tête l'assume :

> *« on ne teste pas `upgrade head` depuis une base vierge car le schéma de base
> est créé par `SQLModel.create_all` puis ajusté par des migrations
> incrémentales »*

La conclusion était juste, et elle laissait un trou : **aucun contrôle ne faisait
tourner une migration**. Le 20/08/2026, la migration 0157 a échoué **deux fois**
à l'essai, sur deux erreurs différentes et toutes deux fatales :

    ValueError: Constraint must have a name
    NotImplementedError: No support for ALTER of constraints in SQLite dialect

⚠️ `start.sh` a `set -e` : l'une comme l'autre aurait **bloqué le conteneur au
démarrage**, donc mis le site à terre. La CI était verte — elle ne lisait que le
graphe.

## Ce que ce test fait, et ce qu'il ne fait pas

Il reconstitue le schéma comme le démarrage le fait (`SQLModel.create_all`),
**retire ce que la dernière migration doit poser**, l'applique, et vérifie
qu'elle passe — **puis qu'elle se rejoue** sans exploser, parce qu'une base
partiellement migrée existe dans ce projet.

Il ne rejoue pas toute la chaîne : cette dette-là est connue et documentée. Il
couvre **la migration du lot en cours**, celle qui va tourner ce soir en
production — c'est-à-dire la seule dont on ne sait encore rien.
"""
from __future__ import annotations

import os
import tempfile

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlmodel import SQLModel, create_engine

import app.models.core  # noqa: F401  — enregistre toutes les tables
from pathlib import Path

_API_DIR = Path(__file__).resolve().parents[1]

#: La révision éprouvée et celle qui la précède.
#:
#: ⚠️ Ces deux valeurs se mettent à jour à chaque nouvelle migration, et c'est
#: VOULU : le jour où on les oublie, le test éprouve encore la précédente et le
#: cas zéro plus bas le dit. Les déduire du graphe donnerait un test qui suit
#: toujours — donc qui ne pose jamais la question « et celle-ci, tu l'as
#: essayée ? ».
REVISION = "0157"
PRECEDENTE = "0156"

#: Les colonnes que `REVISION` doit poser. Retirées avant de l'appliquer.
COLONNES_POSEES = ("assurance_contrat_id", "syndic_contrat_id")


def _base_avant_migration(chemin: str):
    """Le schéma tel qu'il est AVANT la migration, sur une base jetable."""
    moteur = create_engine(f"sqlite:///{chemin}")
    SQLModel.metadata.create_all(moteur)
    with moteur.begin() as c:
        #  `DROP COLUMN` échoue quand une contrainte cite la colonne : on recrée
        #  la table sans elles, ce qui est aussi ce que la vraie base contient.
        cols = [r[1] for r in c.execute(text("PRAGMA table_info(copropriete)")).fetchall()]
        gardees = [x for x in cols if x not in COLONNES_POSEES]
        c.execute(text("PRAGMA foreign_keys=off"))
        c.execute(text(f"CREATE TABLE copro_tmp AS SELECT {', '.join(gardees)} FROM copropriete"))
        c.execute(text("DROP TABLE copropriete"))
        c.execute(text("ALTER TABLE copro_tmp RENAME TO copropriete"))

        c.execute(text(
            "INSERT INTO copropriete (id, nom, adresse, nb_parkings_communs) "
            "VALUES (1, 'Résidence du Parc', '5 boulevard', 0)"))
        c.execute(text(
            "INSERT INTO prestataire (id, nom, specialite, type_prestataire, actif, cree_le) "
            "VALUES (3, 'ASA Assurances', 'assurance', 'contrat_recurrent', 1, '2026-01-01')"))
        #  Deux contrats d'assurance : l'ancien et le courant. La reprise doit
        #  choisir le plus récent — c'est la règle qu'elle applique une dernière
        #  fois avant d'être remplacée par un choix explicite.
        for cid, debut in ((10, "2023-01-01"), (11, "2025-01-01")):
            c.execute(text(
                "INSERT INTO contrat_entretien "
                "(id, copropriete_id, prestataire_id, type_equipement, libelle, "
                " numero_contrat, date_debut, actif) "
                f"VALUES ({cid}, 1, 3, 'assurance', 'Multirisque', 'P-{cid}', '{debut}', 1)"))
    return moteur


def _appliquer(chemin: str):
    cfg = Config(str(_API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_API_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{chemin}")
    command.stamp(cfg, PRECEDENTE)
    command.upgrade(cfg, REVISION)
    return cfg


@pytest.fixture
def base():
    chemin = os.path.join(tempfile.mkdtemp(), "essai.db")
    yield chemin, _base_avant_migration(chemin)


def test_le_cas_zero_est_bien_pose(base):
    """⚠️ Sans colonnes à poser, ce fichier ne mesurerait plus rien.

    Le jour où `COLONNES_POSEES` ne correspond plus à `REVISION` — parce qu'on a
    ajouté une migration sans mettre ces constantes à jour —, le schéma d'avant
    serait identique au schéma d'après, et la migration passerait sans rien
    faire. Le test dirait vert sur une migration jamais éprouvée.
    """
    chemin, moteur = base
    with moteur.begin() as c:
        cols = {r[1] for r in c.execute(text("PRAGMA table_info(copropriete)")).fetchall()}
    absentes = set(COLONNES_POSEES) - cols
    assert absentes == set(COLONNES_POSEES), (
        f"le schéma d'avant contient déjà {sorted(cols & set(COLONNES_POSEES))} : "
        f"`COLONNES_POSEES` décrit-il encore ce que {REVISION} apporte ?"
    )


def test_la_migration_S_EXECUTE(base):
    """🔴 Le contrôle qui manquait : elle tourne, pour de vrai.

    Deux échecs fatals ont été trouvés ici avant la production, sur une
    migration dont la CI disait pourtant du bien.
    """
    chemin, moteur = base
    _appliquer(chemin)
    with moteur.begin() as c:
        cols = {r[1] for r in c.execute(text("PRAGMA table_info(copropriete)")).fetchall()}
    assert set(COLONNES_POSEES) <= cols, f"colonnes manquantes après {REVISION} : {sorted(set(COLONNES_POSEES) - cols)}"


def test_la_reprise_choisit_le_contrat_le_plus_recent(base):
    """Sans reprise, la fiche perdrait son assurance le jour du déploiement.

    Et le défaut ressemblerait à « il n'y a plus de contrat » alors que le
    contrat est là — le pire des messages, puisqu'il envoie en chercher un autre.
    """
    chemin, moteur = base
    _appliquer(chemin)
    with moteur.begin() as c:
        assurance, syndic = c.execute(text(
            "SELECT assurance_contrat_id, syndic_contrat_id FROM copropriete WHERE id = 1")).one()
    assert assurance == 11, f"la reprise n'a pas choisi le contrat le plus récent : {assurance}"
    assert syndic is None, "le syndic ne doit rien inventer : aucun contrat de ce type n'existe"


def test_la_migration_se_REJOUE_sans_exploser(base):
    """⚠️ Une base partiellement migrée existe dans ce projet.

    Une migration qui suppose un état neuf plante sur une base rejouée — et
    `set -e` transforme ce plantage en conteneur bloqué.
    """
    chemin, _moteur = base
    cfg = _appliquer(chemin)
    command.stamp(cfg, PRECEDENTE)
    command.upgrade(cfg, REVISION)  # ne doit pas lever
