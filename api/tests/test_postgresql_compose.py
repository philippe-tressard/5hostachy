"""Le service PostgreSQL du compose : éteint par défaut, fermé, sans secret connu (#1759, DI-7).

Tant que la bascule des données (DI-7c) n'est pas faite, la production reste sous
SQLite : le service n'existe que si `.env` allume son profil. Ces contrôles
tiennent ce qui ferait du mal le jour où il s'allume — un port ouvert, un mot de
passe par défaut, des réglages qui useraient la carte SD ou céderaient la
durabilité.
"""

from __future__ import annotations

from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[2]
COMPOSE = yaml.safe_load((RACINE / "docker-compose.yml").read_text(encoding="utf-8"))
PG = COMPOSE["services"]["postgres"]


def _reglages() -> dict[str, str]:
    commande = PG["command"]
    return dict(commande[i + 1].split("=", 1) for i, m in enumerate(commande) if m == "-c")


def test_le_service_est_eteint_par_defaut():
    assert PG.get("profiles") == ["postgresql"], (
        "sans profil, `docker compose up -d` démarrerait PostgreSQL sur la production "
        "avant la bascule des données"
    )


def test_aucun_port_n_est_publie():
    assert "ports" not in PG, "seule l'API l'atteint, par le réseau `hostachy`"
    assert PG["networks"] == ["hostachy"]


def test_aucun_mot_de_passe_par_defaut():
    environnement = dict(e.split("=", 1) for e in PG["environment"])
    assert environnement["POSTGRES_PASSWORD"] == "${POSTGRES_PASSWORD:-}", (
        "vide sans `.env` : l'image refuse alors d'initialiser la base — jamais un secret écrit ici"
    )


def test_l_image_porte_une_mineure_explicite():
    nom, _, etiquette = PG["image"].partition(":")
    assert nom == "postgres" and etiquette.count(".") == 1, (
        "majeure.mineure, comme Caddy (#1602) : Dependabot propose les montées"
    )


def test_les_donnees_vivent_dans_un_volume_nomme():
    assert "pg_data:/var/lib/postgresql/data" in PG["volumes"]
    assert "pg_data" in COMPOSE["volumes"]


def test_les_reglages_menagent_la_carte_sans_ceder_la_durabilite():
    reglages = _reglages()
    #  Moins d'écritures : points de contrôle espacés, WAL compressé.
    assert reglages["checkpoint_timeout"] == "15min"
    assert reglages["wal_compression"] == "on"
    #  La réplication en continu vers le standby (DI-7b) en a besoin.
    assert reglages["wal_level"] == "replica"
    #  🔴 Jamais au prix d'un commit perdu : ces deux-là restent à leur défaut, actifs.
    for interdit in ("fsync", "synchronous_commit", "full_page_writes"):
        assert interdit not in reglages, f"`{interdit}` ne se règle pas ici : la durabilité prime"


def test_la_base_dit_quand_elle_est_prete():
    assert "pg_isready" in " ".join(PG["healthcheck"]["test"])
