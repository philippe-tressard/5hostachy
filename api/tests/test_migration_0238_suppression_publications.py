"""La 0238 supprime `publication` et `publication_evolution` — et le défait (#1177).

Exécutée pour de vrai, par le contexte d'Alembic, sur le schéma des modèles
ACTUELS : la descente recrée d'abord les deux tables et les deux colonnes
`publication_id` (la forme qu'avait la production), la montée les retire.

Elle a été rejouée le 30/09/2026 sur une copie de la sauvegarde du 29/09 (0234
→ 0238 → 0237 → 0238, `integrity_check` ok, aucune violation de clé). Ce test
garde ce qui ne dépend pas d'une copie : l'ordre des retraits, l'idempotence
qu'exige `start.sh` (`set -e`), et ce que la redirection des anciens liens lit
encore — `ticket.promu_depuis_publication_id`.

Il remplace `test_migration_0210_actualites.py`, qui reconstruisait les tables
à partir des modèles `Publication` supprimés par ce même lot.
"""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlmodel import Session, SQLModel, create_engine

from app.models.core import Ticket, Utilisateur

_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "0238_suppression_tables_publication.py"
)


def _jouer(moteur, sens: str) -> None:
    spec = importlib.util.spec_from_file_location("mig0238", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with moteur.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(module, sens)()


def _etat(moteur) -> dict:
    inspecteur = sa.inspect(moteur)
    colonnes = lambda t: {c["name"] for c in inspecteur.get_columns(t)}  # noqa: E731
    return {
        "tables": {t for t in inspecteur.get_table_names() if t.startswith("publication")},
        "document": "publication_id" in colonnes("document"),
        "annonce_hall": "publication_id" in colonnes("annonce_hall"),
    }


@pytest.fixture()
def moteur():
    m = create_engine("sqlite://")
    SQLModel.metadata.create_all(m)
    with Session(m) as s:
        auteur = Utilisateur(
            email=f"a-{uuid.uuid4().hex[:6]}@x.fr", mot_de_passe_hash="x", prenom="A", nom="B"
        )
        s.add(auteur)
        s.commit()
        s.refresh(auteur)
        s.add(
            Ticket(
                numero="TK-A00024",
                titre="Coupure d'eau",
                description="x",
                categorie="actualite",
                statut="publie",
                auteur_id=auteur.id,
                promu_depuis_publication_id=24,
            )
        )
        s.commit()
    #  La forme de la production AVANT la 0238 : la descente la recrée.
    _jouer(m, "downgrade")
    return m


def test_la_descente_rend_au_schema_la_forme_de_la_production(moteur):
    assert _etat(moteur) == {
        "tables": {"publication", "publication_evolution"},
        "document": True,
        "annonce_hall": True,
    }


def test_la_montee_retire_les_deux_tables_et_les_deux_colonnes(moteur):
    _jouer(moteur, "upgrade")
    assert _etat(moteur) == {"tables": set(), "document": False, "annonce_hall": False}


def test_la_montee_est_rejouable(moteur):
    """`start.sh` est en `set -e` : une montée qui échouerait au second passage
    arrêterait le conteneur."""
    _jouer(moteur, "upgrade")
    _jouer(moteur, "upgrade")
    assert _etat(moteur)["tables"] == set()


def test_l_ancien_numero_survit_sur_l_affaire(moteur):
    """C'est la seule chose que la redirection `/publications/{n}` lit."""
    _jouer(moteur, "upgrade")
    with Session(moteur) as s:
        affaire = s.exec(
            sa.select(Ticket).where(Ticket.promu_depuis_publication_id == 24)
        ).scalar_one()
    assert affaire.numero == "TK-A00024"
