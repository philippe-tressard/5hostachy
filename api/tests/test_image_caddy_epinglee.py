"""L'image de base de Caddy porte une version MINEURE explicite (#1602, 04/10/2026).

POURQUOI — `FROM caddy:2` n'a qu'une majeure : Dependabot (`docker`) ne propose
jamais de 2.x → 2.y, et `maintenance.sh` (#1379) re-tire l'image chaque dimanche,
donc le Caddy de production change sans qu'aucun commit ne le dise. Avec
`caddy:2.11`, la mineure servie est écrite dans le dépôt : un correctif de la
même mineure se tire toujours, et un changement de mineure arrive par une PR.

CE QUE CE TEST REFUSE : un `FROM caddy` sans `<majeure>.<mineure>`. Les autres
images de base (python, node) restent à étiquette flottante par choix
(`dependabot.yml` : leurs mineures changent assez pour que Dependabot les suive),
et ne sont pas jugées ici.
"""

import re

from tests.conftest import racine_depot

DOCKERFILE = racine_depot() / "Dockerfile.caddy"
_FROM = re.compile(r"^\s*FROM\s+(?P<image>caddy)(?::(?P<tag>\S+))?(\s+AS\s+\S+)?\s*$", re.I | re.M)
_MINEURE = re.compile(r"^\d+\.\d+(\.\d+)?(-[A-Za-z0-9.]+)?$")


def _bases() -> list[tuple[str, str | None]]:
    return [(m["image"], m["tag"]) for m in _FROM.finditer(DOCKERFILE.read_text(encoding="utf-8"))]


def test_le_dockerfile_de_caddy_est_lu():
    """Cas zéro : un contrôle qui ne trouve aucun `FROM caddy` n'a rien jugé."""
    assert _bases(), "aucun `FROM caddy` lu dans Dockerfile.caddy"


def test_caddy_porte_une_mineure_explicite():
    flottantes = [f"caddy:{tag or '(latest)'}" for _, tag in _bases() if not (tag and _MINEURE.match(tag))]
    assert not flottantes, (
        f"image(s) de base sans version mineure : {flottantes} — écrire `caddy:<majeure>.<mineure>` "
        "(la mineure servie se lit : `docker exec hostachy_caddy caddy version`)"
    )
