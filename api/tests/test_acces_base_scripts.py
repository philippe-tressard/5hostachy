"""Aucun script versionné n'ouvre `app.db` pendant que l'API tourne.

POURQUOI CE TEST — trois incidents, une seule cause :

Un process TIERS qui ouvre `app.db` alors que l'API tourne casse la base. Les
connexions du pool SQLAlchemy sont ouvertes mais **sans verrou** quand elles sont
idle : le process tiers se croit donc dernière connexion, checkpointe, puis `unlink`
les fichiers WAL et SHM sous le pool. L'API écrit ensuite dans des inodes orphelins —
writes invisibles, `disk I/O error` en rafales, 503, puis perte des données au
prochain arrêt. Corruptions `telemetry_event` des 05 et 17/06/2026, panne de connexion
du 17/07/2026 (~12 h d'écritures perdues).

Ces trois incidents ont été corrigés **au cas par cas** : le contrôle fautif de
`check-reliability.sh` a été supprimé, UNE purge de `maintenance.sh` (1d) est
passée in-process — et ce paragraphe affirmait « la purge », au singulier défini,
alors que cinq autres ouvraient encore la base chaque dimanche par `docker exec
… python` (#1232, 24/09/2026). Le test ne les voyait pas : il ne cherchait que
`sqlite3`. Personne n'avait corrigé la **classe** — et le 04/08/2026 on a retrouvé
dans `setup-rpi5.sh` un installeur qui posait un cron `sqlite3 … ".backup"` côté hôte
à 03:00. Il datait de l'époque mono-RPi, il était encore inscrit dans `/etc/crontab`
de rpi1, et il n'était inoffensif que parce que le script appelé avait disparu.
Un piège armé, en attente d'une réinstallation.

CE QUE CE TEST NE FAIT PAS : interdire `sqlite3`. Trois usages sont légitimes et
nécessaires — sur une **copie**, ou sur la base **au repos, API arrêtée**. Un garde-fou
qui les interdirait serait contourné dès la semaine suivante, donc inutile. Il les
inscrit à la place dans une liste d'exceptions **justifiées**, vérifiée dans les deux
sens : une exception qui ne correspond plus à rien fait échouer le test, sinon la
liste grossit à chaque cas et finit par tout couvrir (même règle que
`test_endpoints_orphelins.py`).
"""

import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]

#: Ouvertures de `app.db` autorisées, avec la raison qui les rend sûres.
#: Clé = (fichier, motif exact attendu dans la ligne). Toute autre ouverture
#: échoue ; toute entrée devenue introuvable échoue aussi.
EXCEPTIONS_JUSTIFIEES = {
    (
        "bascule.sh",
        "/tmp/sync_app_data/app.db",
    ): "copie fraîchement rsyncée sur le peer, dont AUCUNE API ne tient les fichiers "
    "ouverts (conteneurs du peer arrêtés en phase 0) — c'est le contrôle d'intégrité "
    "qui précède l'installation dans le volume",
    (
        "maintenance.sh",
        "$DB_DIR/app.db",
    ): "VACUUM hebdomadaire, exécuté API STOPPÉE (0 writer) — la seule façon sûre de "
    "compacter, et la raison pour laquelle la maintenance arrête la pile d'abord",
    (
        "export-hors-site.sh",
        "$TMP/app.db",
    ): "copie extraite d'une archive .tar.gz sur le POSTE, jamais la base de "
    "production — aucun process ne la tient ouverte",
}

#: Motifs interdits sans exception possible : ils désignent toujours la base d'un
#: nœud en fonctionnement.
TOUJOURS_INTERDIT = (
    re.compile(r"docker\s+exec[^\n]*sqlite3"),
    re.compile(r"docker\s+exec[^\n]*PRAGMA"),
)

#: Une invocation de sqlite3 sur un fichier .db (pas une simple mention du mot).
OUVERTURE = re.compile(r"sqlite3\s+\"?(\$?[^\s\"]*\.db)")


#: Une ouverture de base en **Python** — `sqlite3.connect("…/app.db")`.
#:
#: Le motif shell ci-dessus ne pouvait pas la voir, et le scan ne regardait que
#: les `*.sh` : deux fichiers Python versionnés à la racine ouvraient
#: `/app/data/app.db` en direct depuis des mois (`debug_cc.py`,
#: `_query_events.py`, supprimés le 15/08/2026). Le contrôle qui existe pour
#: empêcher la corruption de base ne les voyait ni par son motif, ni par sa
#: portée — « la portée du contrôle fait partie du contrôle »
#: (standards/05 §9).
OUVERTURE_PY = re.compile(r"sqlite3\.connect\(\s*\"?([^\s\"\)]*\.db)")


def scripts_versionnes() -> list[Path]:
    """Tout ce qu'un humain peut lancer À CÔTÉ de l'API, quel que soit le langage.

    `api/` en est exclu : ce code s'exécute DANS le process de l'application, où
    l'accès passe par le pool SQLAlchemy — c'est un autre régime, couvert
    ailleurs. Ce test-ci vise les process **tiers**.
    """
    from tests.conftest import scripts_shell_versionnes

    fichiers = list(scripts_shell_versionnes())
    #  Les `.py` lancés à la main comptent autant que les `.sh` : deux d'entre eux
    #  ouvraient la base en direct sans que ce test les regarde.
    fichiers += sorted(RACINE.glob("*.py"))
    fichiers += sorted(RACINE.glob("scripts/**/*.py"))
    fichiers += sorted(RACINE.glob("infra/**/*.py"))
    return sorted(set(fichiers))


def lignes_de_code(chemin: Path):
    """Rend (numéro, ligne) en ignorant commentaires et lignes vides.

    Un motif cité dans un commentaire explicatif — il y en a, et ils sont utiles —
    n'est pas une ouverture de base.
    """
    for numero, ligne in enumerate(chemin.read_text(encoding="utf-8").splitlines(), 1):
        nue = ligne.strip()
        if nue and not nue.startswith("#"):
            yield numero, ligne


def test_le_detecteur_voit_quelque_chose():
    """Garde-fou du garde-fou : un scan qui ne trouve aucun script rendrait tout vert.

    C'est le « cas zéro » de standards/04 §2 appliqué à ce test-ci : sans cette
    vérification, un chemin de base faux le rendrait vert à vide, pour toujours.
    """
    scripts = scripts_versionnes()
    assert len(scripts) >= 10, (
        f"seulement {len(scripts)} script(s) trouvé(s) — chemin de scan cassé ?"
    )
    assert any(OUVERTURE.search(s.read_text(encoding="utf-8")) for s in scripts), (
        "aucune ouverture de base détectée nulle part : le motif de détection ne "
        "fonctionne plus, et ce test ne protège donc plus de rien"
    )


def test_aucune_ouverture_de_base_non_justifiee():
    """Toute ouverture d'`app.db` doit figurer dans la liste des exceptions."""
    trouvees = set()
    fautes = []
    for script in scripts_versionnes():
        for numero, ligne in lignes_de_code(script):
            for cible in OUVERTURE.findall(ligne) + OUVERTURE_PY.findall(ligne):
                cle = (script.name, cible)
                if cle in EXCEPTIONS_JUSTIFIEES:
                    trouvees.add(cle)
                else:
                    fautes.append(
                        f"{script.name}:{numero} ouvre « {cible} ».\n"
                        f"    {ligne.strip()}\n"
                        f"    Si l'API tourne, cela CASSE la base (règle d'or, cf. "
                        f"CLAUDE.md et .claude/skills/infra-rpi).\n"
                        f"    À chaud, passer par les endpoints in-process : "
                        f"POST /admin/db/checkpoint, GET /admin/db/integrite.\n"
                        f"    Si l'accès est réellement sûr (copie, ou API arrêtée), "
                        f"l'inscrire dans EXCEPTIONS_JUSTIFIEES avec sa raison."
                    )
    assert not fautes, "\n\n".join(fautes)

    # Sens inverse : une exception qui ne correspond plus à rien doit disparaître.
    obsoletes = set(EXCEPTIONS_JUSTIFIEES) - trouvees
    assert not obsoletes, (
        "exception(s) devenue(s) sans objet, à retirer de EXCEPTIONS_JUSTIFIEES — "
        "une liste qu'on ne nettoie pas finit par tout autoriser : "
        + ", ".join(f"{f} → {c}" for f, c in sorted(obsoletes))
    )


def test_aucun_docker_exec_sur_la_base():
    """`docker exec … sqlite3` et `docker exec … PRAGMA` visent toujours un nœud vivant.

    Aucune exception n'est prévue : c'est exactement la commande qui figurait dans le
    pré-check jusqu'au 17/07/2026, et qui a produit l'incident qu'elle était censée
    prévenir.
    """
    fautes = []
    for script in scripts_versionnes():
        for numero, ligne in lignes_de_code(script):
            for motif in TOUJOURS_INTERDIT:
                if motif.search(ligne):
                    fautes.append(f"{script.name}:{numero} : {ligne.strip()}")
    assert not fautes, (
        "accès à la base par `docker exec` — interdit sans exception, l'API tourne "
        "forcément dans ce conteneur :\n" + "\n".join(fautes)
    )


#: Du Python lancé DANS le conteneur de l'API qui importe son moteur de base :
#: `docker exec hostachy_api python -c "from app.database import engine …"`.
#: C'est un process TIERS aussi sûrement qu'un `sqlite3` hôte — même conteneur,
#: autre PID, autre pool. Aucune exception : à chaud, la base se touche par une
#: route de l'API (`POST /admin/maintenance/purges`, `/admin/db/checkpoint`…).
BASE_PAR_LE_CODE_DE_L_API = re.compile(r"\bapp\.database\b")


def test_aucun_script_n_importe_la_base_de_l_api():
    """Un script shell n'importe jamais `app.database` (#1232, 24/09/2026).

    `maintenance.sh` purgeait cinq tables chaque dimanche à 03:00 par
    `docker exec hostachy_api python -c "from app.database import engine …"`,
    API en marche — la forme exacte que la règle d'or interdit, que ce fichier
    ne voyait pas parce qu'il ne cherchait que `sqlite3`.
    """
    fautes = []
    for script in scripts_versionnes():
        if script.suffix != ".sh":
            continue
        for numero, ligne in lignes_de_code(script):
            if BASE_PAR_LE_CODE_DE_L_API.search(ligne):
                fautes.append(f"{script.name}:{numero} : {ligne.strip()}")
    assert not fautes, (
        "un script ouvre la base par le code de l'API, depuis un process tiers — "
        "passer par une route in-process :\n" + "\n".join(fautes)
    )


def test_aucun_script_ne_pose_de_cron_de_sauvegarde_cote_hote():
    """Aucun script versionné ne doit installer de sauvegarde côté hôte.

    Retiré de `setup-rpi5.sh` le 04/08/2026. Le vérifier ici plutôt que de s'en
    remettre au commentaire laissé dans le script : un commentaire n'empêche
    personne de le réintroduire, et c'est précisément parce que personne n'avait
    relu ce fichier depuis mars 2026 que le piège y a survécu à la mise en haute
    disponibilité.

    ⚠️ Ce test ne visait QUE `setup-rpi5.sh` jusqu'au 20/09/2026 (#1029). Le
    script a été supprimé — et le test est mort avec lui, sur un
    `FileNotFoundError`. Une protection attachée à un **nom de fichier** ne
    survit pas au fichier : elle protège l'endroit où le défaut est apparu une
    fois, pas le geste. Il porte donc maintenant sur tous les scripts du dépôt,
    et il n'a plus rien à perdre quand l'un d'eux disparaît.
    """
    fautes = []
    for script in sorted((RACINE / "scripts").rglob("*.sh")):
        for numero, ligne in lignes_de_code(script):
            for interdit in ("scripts/backup.sh", "hostachy-backup", "5hostachy-backup"):
                if interdit in ligne:
                    fautes.append(f"{script.relative_to(RACINE)}:{numero} (« {interdit} »)")
    assert not fautes, (
        "sauvegarde côté hôte réintroduite dans un script versionné :\n"
        + "\n".join(fautes)
        + "\n\nLa sauvegarde est in-process depuis la v2.18 (api/app/utils/backup.py), "
        'avec `PRAGMA quick_check` préalable : un `sqlite3 ".backup"` lancé depuis '
        "l'hôte pendant que l'API tourne casse la base."
    )
