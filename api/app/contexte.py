"""Le contexte de copropriété — le SEUL accès aux ressources d'une copropriété (#1744).

Chantier multi-copropriétés, spec `specs/architecture/multi-coproprietes.md` §4.1,
règle 3 : *aucune ressource ne se construit depuis la configuration globale*. La
base, la racine des fichiers, le secret de signature et l'expéditeur des courriels
appartiennent à UNE copropriété ; ils se demandent ici, et nulle part ailleurs.

Tant qu'il n'y a qu'une copropriété (phase 2, §8 bis), le contexte les lit dans
`settings` : le comportement est inchangé. Le jour où une requête se résoudra par
son nom d'hôte (P2-9, #1751), seul ce module changera — et les appelants, qui ne
nomment plus `settings.database_url` ni `engine`, suivront sans un mot.

🔒 `tests/test_contexte_source_unique.py` refuse, dans `app/`, toute lecture
directe de ces ressources hors de ce module (et de `database.py`, qui construit
le moteur).

Il relit la configuration à chaque appel (`get_settings` est mis en cache une
fois pour le processus). Son seul état est le registre des états de processus
(`etat`), indexé par l'identifiant de la copropriété ; un registre des moteurs,
quand il viendra, le sera de même — `test_etat_module_par_copropriete.py` y veille.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from sqlmodel import Session

from app.config import get_settings

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

#: L'identifiant de l'unique copropriété d'une installation de phase 2. Il indexe
#: déjà les états de processus (`etat`) : la seconde copropriété n'aura qu'à en
#: apporter un autre.
IDENTIFIANT_UNIQUE = "principale"


@dataclass(frozen=True)
class Copropriete:
    """Ce qu'il faut pour servir UNE copropriété — rien de commun à la plateforme."""

    identifiant: str
    url_base: str
    racine_fichiers: Path
    secret: str
    expediteur: str
    nom_expediteur: str


def courante() -> Copropriete:
    """La copropriété servie. Une seule en phase 2 : celle de la configuration."""
    s = get_settings()
    return Copropriete(
        identifiant=IDENTIFIANT_UNIQUE,
        url_base=s.database_url,
        racine_fichiers=Path(s.uploads_dir),
        secret=s.secret_key,
        expediteur=s.mail_from,
        nom_expediteur=s.mail_from_name,
    )


def moteur() -> Engine:
    """Le moteur de la base de la copropriété servie.

    Lu à l'APPEL dans `app.database` : un test qui remplace `app.database.engine`
    obtient sa base partout, sans remplacer un attribut par module appelant.
    """
    from app import database

    return database.engine


def nouvelle_session() -> Session:
    """Une session hors requête HTTP (tâche planifiée, envoi différé, cache).

    Dans une route, la session vient de la dépendance `get_session`.
    """
    return Session(moteur())


#: Les états de processus (caches, quotas), un dictionnaire par (copropriété, nom).
#: Le SEUL état mutable qu'un module de l'application puisse tenir pour une
#: copropriété — `test_etat_module_par_copropriete.py` refuse tout autre (§4.5).
_etats: dict[tuple[str, str], dict] = {}


def etat(nom: str) -> dict:
    """Le dictionnaire d'état `nom` de la copropriété servie, créé vide au besoin.

    L'utilisateur n° 12 d'une copropriété n'est pas celui d'une autre : un cache
    indexé par le seul `user_id` les confondrait. Un module ne garde donc pas son
    cache dans une variable à lui ; il le demande ici à chaque usage, et reçoit
    celui de la copropriété servie. `setdefault` est atomique sous le GIL : deux
    fils qui demandent le même état reçoivent le même dictionnaire.
    """
    return _etats.setdefault((courante().identifiant, nom), {})
