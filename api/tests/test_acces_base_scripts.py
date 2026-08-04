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
`check-reliability.sh` a été supprimé, la purge de `maintenance.sh` est passée
in-process. Personne n'avait corrigé la **classe** — et le 04/08/2026 on a retrouvé
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


def scripts_versionnes() -> list[Path]:
    return sorted(RACINE.glob("*.sh")) + sorted(RACINE.glob(".githooks/*"))


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
    assert len(scripts) >= 10, f"seulement {len(scripts)} script(s) trouvé(s) — chemin de scan cassé ?"
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
            for cible in OUVERTURE.findall(ligne):
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


def test_installeur_ne_pose_aucun_cron_de_sauvegarde():
    """`setup-rpi5.sh` ne doit plus jamais installer de sauvegarde côté hôte.

    Retiré le 04/08/2026. Le vérifier ici plutôt que de s'en remettre au commentaire
    laissé dans le script : un commentaire n'empêche personne de le réintroduire, et
    c'est précisément parce que personne n'avait relu ce fichier depuis mars 2026
    que le piège y a survécu à la mise en haute disponibilité.
    """
    installeur = RACINE / "setup-rpi5.sh"
    contenu = installeur.read_text(encoding="utf-8")
    for interdit in ("scripts/backup.sh", "hostachy-backup", "5hostachy-backup"):
        for numero, ligne in lignes_de_code(installeur):
            assert interdit not in ligne, (
                f"setup-rpi5.sh:{numero} réintroduit une sauvegarde côté hôte "
                f"(« {interdit} ») : la sauvegarde est in-process depuis la v2.18 "
                f"(api/app/utils/backup.py). Voir le commentaire de la section 6."
            )
    assert "SAUVEGARDE" in contenu, (
        "le commentaire qui explique POURQUOI la sauvegarde n'est pas dans "
        "l'installeur a disparu — sans lui, quelqu'un la remettra"
    )
