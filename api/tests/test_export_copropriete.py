"""L'export neutre d'une copropriété se réimporte à l'identique, et l'import vérifie (#1749).

Ce que ces tests tiennent :
- l'aller-retour : export d'une base peuplée, import dans une base neuve, même
  contenu table par table (empreintes) — date, booléen, énumération, texte
  accentué, NULL ;
- l'import REFUSE une archive altérée, et la base cible reste vide ;
- `verifier_restauration` dit qu'une base se restaure ;
- une valeur sans forme neutre lève, au lieu d'une empreinte fausse.

Sous le workflow « PostgreSQL », `moteur_memoire` rend des bases PostgreSQL : le même
aller-retour y prouve que le format ne doit rien à SQLite (D4).
"""

from __future__ import annotations

import io
import json
import tarfile
from datetime import datetime

import pytest
from sqlmodel import Session, select

from app.models.core import ConfigSite, FaqItem, RoleUtilisateur, Utilisateur
from app.utils import export_copropriete as ex
from tests.aides_base import compte, moteur_memoire


def _base_peuplee(*, partage: bool = False):
    moteur = moteur_memoire(partage=partage)
    with Session(moteur) as s:
        compte(s, prenom="Élodie", nom="D'Aubigné", role=RoleUtilisateur.conseil_syndical)
        compte(s, prenom="Zoé", nom="Martin", actif=False)
        s.add(ConfigSite(cle="site_nom", valeur="Résidence « Les Tilleuls »"))
        s.add(ConfigSite(cle="vide", valeur=""))
        s.add(
            FaqItem(
                categorie="Vie pratique",
                question="Où sont les poubelles ?",
                reponse="Au sous-sol — porte B.",
            )
        )
        s.commit()
    return moteur


def test_l_aller_retour_rend_le_meme_contenu(tmp_path):
    source = _base_peuplee()
    archive = tmp_path / "export.tar.gz"
    manifeste = ex.exporter(source, archive)
    assert manifeste["tables"]["utilisateur"]["lignes"] == 2
    assert manifeste["tables"]["config_site"]["lignes"] == 2

    cible = moteur_memoire()
    bilan = ex.importer(archive, cible)
    assert bilan.ecarts == [] and bilan.lignes >= 5

    with Session(cible) as s:
        elodie = s.exec(select(Utilisateur).where(Utilisateur.prenom == "Élodie")).one()
        assert elodie.nom == "D'Aubigné" and elodie.actif is True
        assert isinstance(elodie.cree_le, datetime)
        assert s.exec(select(ConfigSite).where(ConfigSite.cle == "vide")).one().valeur == ""
        assert elodie.etage is None, "un NULL reste un NULL"
    #  Et la cible relue donne EXACTEMENT les empreintes de la source.
    with cible.connect() as c:
        relu, _, _ = ex.lire(c)
    par_nom = {t.name: t for t in ex.tables()}
    for nom, attendu in manifeste["tables"].items():
        assert ex.empreinte_table(par_nom[nom], relu[nom]) == attendu["empreinte"], nom


def _alterer(archive, sortie, table, remplacer):
    with tarfile.open(archive, "r:gz") as a, tarfile.open(sortie, "w:gz") as b:
        for membre in a.getmembers():
            donnees = a.extractfile(membre).read()
            if membre.name == f"tables/{table}.jsonl":
                donnees = remplacer(donnees)
            info = tarfile.TarInfo(membre.name)
            info.size = len(donnees)
            b.addfile(info, io.BytesIO(donnees))


def test_une_archive_alteree_est_refusee_et_la_cible_reste_vide(tmp_path):
    source = _base_peuplee()
    archive = tmp_path / "export.tar.gz"
    ex.exporter(source, archive)
    alteree = tmp_path / "alteree.tar.gz"
    _alterer(archive, alteree, "faq_item", lambda d: d.replace("sous-sol".encode(), b"grenier"))

    cible = moteur_memoire()
    with pytest.raises(ex.ImportRefuse, match="faq_item"):
        ex.importer(alteree, cible)
    with Session(cible) as s:
        assert s.exec(select(FaqItem)).all() == [], "la transaction annulée laisse la cible vide"


def test_une_ligne_perdue_est_refusee(tmp_path):
    source = _base_peuplee()
    archive = tmp_path / "export.tar.gz"
    ex.exporter(source, archive)
    amputee = tmp_path / "amputee.tar.gz"
    _alterer(archive, amputee, "config_site", lambda d: d.split(b"\n", 1)[1])
    with pytest.raises(ex.ImportRefuse, match="config_site : 1 ligne"):
        ex.importer(amputee, moteur_memoire())


def test_les_fichiers_voyagent_avec_leur_empreinte(tmp_path):
    televerses = tmp_path / "uploads"
    (televerses / "photos").mkdir(parents=True)
    (televerses / "photos" / "fuite.jpg").write_bytes(b"\xff\xd8\xff photo")
    archive = tmp_path / "export.tar.gz"
    manifeste = ex.exporter(_base_peuplee(), archive, fichiers=televerses)
    assert [f["chemin"] for f in manifeste["fichiers"]] == ["photos/fuite.jpg"]

    restaures = tmp_path / "restaures"
    bilan = ex.importer(archive, moteur_memoire(), fichiers=restaures)
    assert bilan.fichiers == 1
    assert (restaures / "photos" / "fuite.jpg").read_bytes() == b"\xff\xd8\xff photo"


def test_verifier_restauration_dit_qu_une_base_se_restaure(tmp_path):
    manifeste, bilan = ex.verifier_restauration(_base_peuplee(), tmp_path)
    assert bilan.ecarts == [] and bilan.tables == len(manifeste["tables"])
    assert list(tmp_path.iterdir()) == [], "rien ne reste derrière la vérification"


def test_une_valeur_sans_forme_neutre_leve():
    with pytest.raises(TypeError):
        ex.valeur_neutre(object())
    assert ex.valeur_neutre(b"\x00\x01") == {"$b64": "AAE="}
    assert json.dumps(ex.valeur_neutre(datetime(2026, 10, 9, 1, 2, 3)))


def test_le_manifeste_nomme_ce_qu_il_ne_porte_pas(tmp_path):
    moteur = _base_peuplee()
    from sqlalchemy import text

    with moteur.begin() as c:
        c.execute(text("CREATE TABLE table_historique (x INTEGER)"))
    manifeste = ex.exporter(moteur, tmp_path / "e.tar.gz")
    assert manifeste["ignorees"] == ["table_historique"]


# ── Les routes d'administration ──────────────────────────────────────────────

from app.routers.admin import export_copropriete as routes  # noqa: E402
from tests.aides_http import base_http, client_http  # noqa: E402


@pytest.fixture
def http_admin(monkeypatch, tmp_path):
    """Un client admin, la base de l'APPLICATION remplacée par une base peuplée."""
    import app.database

    #  Partagée : le client de test lit depuis un autre fil, et une base en mémoire
    #  non partagée y serait vide.
    monkeypatch.setattr(app.database, "engine", _base_peuplee(partage=True))

    class _Reglages:
        backup_dir = str(tmp_path / "sauvegardes")
        uploads_dir = str(tmp_path / "uploads")

    monkeypatch.setattr(routes, "get_settings", lambda: _Reglages)
    with base_http() as moteur:
        http, _ = client_http(moteur, RoleUtilisateur.admin)
        yield http, tmp_path


@pytest.mark.parametrize("role", [None, RoleUtilisateur.résident, RoleUtilisateur.conseil_syndical])
def test_les_routes_sont_reservees_a_l_administration(role):
    with base_http() as moteur:
        http, _ = client_http(moteur, role)
        assert http.post("/admin/export-copropriete/verifier").status_code in (401, 403)
        assert http.post("/admin/export-copropriete").status_code in (401, 403)
        assert http.get("/admin/export-copropriete/dernier").status_code in (401, 403)


def test_la_route_dit_que_la_base_se_restaure(http_admin):
    http, _ = http_admin
    corps = http.post("/admin/export-copropriete/verifier").json()
    assert corps["restaurable"] is True and corps["ecarts"] == []
    assert corps["tables"] > 10 and corps["lignes"] >= 5


def test_l_export_ecrit_une_archive_entiere_et_se_relit(http_admin):
    http, dossier = http_admin
    (dossier / "uploads").mkdir()
    (dossier / "uploads" / "plan.pdf").write_bytes(b"%PDF-1.7")
    assert http.get("/admin/export-copropriete/dernier").json()["archive"] is None
    nom = http.post("/admin/export-copropriete").json()["archive"]  # tâche de fond jouée
    assert nom.startswith(routes.PREFIXE) and nom.endswith("_paris.tar.gz")
    dernier = http.get("/admin/export-copropriete/dernier").json()
    assert dernier["archive"] == nom and dernier["fichiers"] == 1 and dernier["lignes"] >= 5
    assert not list((dossier / "sauvegardes").glob("*.partiel")), "aucun reste d'écriture"


def test_on_ne_garde_que_les_derniers_exports(http_admin, monkeypatch):
    http, dossier = http_admin
    sauvegardes = dossier / "sauvegardes"
    sauvegardes.mkdir()
    for i in range(5):
        (sauvegardes / f"{routes.PREFIXE}2026010{i}_000000_paris.tar.gz").write_bytes(b"x")
    (sauvegardes / "hostachy_backup_20260101_000000_paris.tar.gz").write_bytes(b"x")
    http.post("/admin/export-copropriete")
    restants = sorted(p.name for p in sauvegardes.iterdir())
    assert len([n for n in restants if n.startswith(routes.PREFIXE)]) == routes.GARDER
    assert "hostachy_backup_20260101_000000_paris.tar.gz" in restants, (
        "les sauvegardes ne sont pas touchées"
    )


def test_l_import_en_ligne_de_commande_verifie_et_le_dit(tmp_path):
    """Le geste de DI-7 : une archive, une base cible neuve, et un verdict lisible."""
    import os
    import subprocess
    import sys

    archive = tmp_path / "e.tar.gz"
    ex.exporter(_base_peuplee(), archive)
    cible = f"sqlite:///{(tmp_path / 'cible.db').as_posix()}"
    #  L'enfant écrit en UTF-8 quel que soit le poste (la console Windows est en cp1252).
    env = {**os.environ, "SECRET_KEY": "x" * 40, "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run(
        [sys.executable, "-m", "app.utils.export_copropriete", "importer", str(archive), cible],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=os.getcwd(),
    )
    assert r.returncode == 0, r.stderr[-500:]
    assert "Importé et vérifié" in r.stdout
    alteree = tmp_path / "alteree.tar.gz"
    _alterer(archive, alteree, "faq_item", lambda d: d.replace("sous-sol".encode(), b"grenier"))
    cible2 = f"sqlite:///{(tmp_path / 'cible2.db').as_posix()}"
    r = subprocess.run(
        [sys.executable, "-m", "app.utils.export_copropriete", "importer", str(alteree), cible2],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=os.getcwd(),
    )
    assert r.returncode != 0 and "IMPORT REFUSÉ" in r.stderr
