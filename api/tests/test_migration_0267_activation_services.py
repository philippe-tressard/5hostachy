"""La 0267 ramène à `"1"` les activations IMAP que seule l'ancienne règle lisait (#1718).

Exécutée pour de vrai par le contexte d'Alembic, sur une base en mémoire. Aucun
service ne doit changer d'état : ce qui était lu « activé » le reste, ce qui ne
l'était pas ne s'allume pas.
"""

from __future__ import annotations

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

from tests.aides_base import moteur_memoire
from tests.aides_migrations import charger_migration


def _apres(valeurs: dict[str, str]) -> dict[str, str]:
    m = moteur_memoire(schema=False)
    with m.begin() as conn:
        conn.execute(text("CREATE TABLE config_site (cle VARCHAR PRIMARY KEY, valeur VARCHAR)"))
        for cle, valeur in valeurs.items():
            conn.execute(text("INSERT INTO config_site VALUES (:c, :v)"), {"c": cle, "v": valeur})
    with m.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            charger_migration("0267_activation_services_normalisee").upgrade()
    with m.connect() as conn:
        return dict(conn.execute(text("SELECT cle, valeur FROM config_site")).all())


@pytest.mark.parametrize(
    "avant, apres",
    [("true", "1"), ("TRUE", "1"), ("Oui", "1"), ("1", "1"), ("0", "0"), ("non", "non")],
)
def test_la_releve_garde_son_etat(avant, apres):
    assert _apres({"imap_enabled": avant})["imap_enabled"] == apres


def test_les_autres_services_ne_s_allument_pas():
    """`"true"` valait « éteint » pour l'IA et WhatsApp : le ramener à `"1"` les allumerait."""
    lu = _apres({"llm_actif": "true", "whatsapp_enabled": "oui"})
    assert lu == {"llm_actif": "true", "whatsapp_enabled": "oui"}
